import streamlit as st
import pandas as pd
import plotly.express as px
import os

# --- 1. SETUP & CONFIGURATION ---
st.set_page_config(page_title="Gallup Pakistan Dashboard", layout="wide", page_icon="📊")

# Hide Streamlit Branding for Professional Look
st.markdown("""
    <style>
    .block-container {padding-top: 1rem; padding-bottom: 0rem;}
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

st.title("📊 Gallup Pakistan: National LFS Survey Dashboard")

# --- 2. SMART DATA LOADER (MEMORY OPTIMIZED) ---
@st.cache_data
def load_data():
    status = st.empty()
    status.info("⏳ Loading massive dataset... this may take 30-60 seconds...")
    
    try:
        # A. HANDLE CASE SENSITIVE FILE NAMES
        # GitHub is case sensitive. We check which file exists.
        if os.path.exists("data.zip"):
            file_name = "data.zip"
        elif os.path.exists("Data.zip"):
            file_name = "Data.zip"
        else:
            st.error("CRITICAL ERROR: Could not find 'data.zip' or 'Data.zip'. Please check GitHub.")
            st.stop()
            
        # B. LOAD DATA IN CHUNKS (THE MEMORY FIX)
        # We read the file in small pieces (50k rows) and compress text to 'category'
        # This reduces RAM usage by 90%, preventing the "Oh No" crash.
        chunks = []
        for chunk in pd.read_csv(file_name, compression='zip', chunksize=50000, low_memory=True):
            # Optimize: Convert all text columns to 'category' to save memory
            for col in chunk.select_dtypes(include=['object']).columns:
                chunk[col] = chunk[col].astype('category')
            chunks.append(chunk)
        
        # Combine chunks back into one dataframe
        df = pd.concat(chunks, axis=0)
        
        # C. LOAD CODEBOOK
        if os.path.exists("code.csv"):
            codes = pd.read_csv("code.csv")
        else:
            st.warning("⚠️ 'code.csv' not found. Dashboard will use raw codes.")
            codes = pd.DataFrame(columns=["Code", "Label"])

        # --- STEP D: CLEAN & MAP VALUES (1->Male, 2->Female) ---
        gender_map = {
            "1": "Male", 1: "Male",
            "2": "Female", 2: "Female",
            "3": "Transgender", 3: "Transgender",
            "#NULL!": "Unknown"
        }
        
        # Apply to RSex (Convert to object briefly, map, then re-categorize)
        if 'RSex' in df.columns:
            df['RSex'] = df['RSex'].astype(str).map(gender_map).fillna(df['RSex']).astype('category')
        if 'S4C5' in df.columns:
            df['S4C5'] = df['S4C5'].astype(str).map(gender_map).fillna(df['S4C5']).astype('category')

        # --- STEP E: RENAME COLUMNS ---
        # Protected columns stay as they are (filters)
        protected_cols = ['Province', 'District', 'Region', 'Tehsil', 'Mouza', 'Locality', 'RSex']
        
        if not codes.empty:
            code_col = codes.columns[0]
            label_col = codes.columns[1]
            rename_dict = {}
            
            for code, label in zip(codes[code_col], codes[label_col]):
                if code not in protected_cols:
                    rename_dict[code] = f"{label} ({code})"
            
            df.rename(columns=rename_dict, inplace=True)
        
        status.empty() # Clear the loading message
        return df

    except Exception as e:
        st.error(f"DATA LOADING ERROR: {e}")
        return None

# Load the data
df = load_data()

# --- 3. DASHBOARD LOGIC ---
if df is not None:
    # --- SIDEBAR FILTERS ---
    st.sidebar.title("🔍 Filter Panel")
    st.sidebar.subheader("Demographics")
    
    # Helper to safely find columns even if renamed
    def get_col(candidates):
        for c in candidates:
            for col_name in df.columns:
                if c in col_name: return col_name
        return None

    # 1. Province
    prov_col = get_col(["Province"]) or df.columns[0]
    # Convert categories to list for dropdowns
    prov_options = df[prov_col].unique().tolist()
    province = st.sidebar.multiselect("Province", prov_options, default=prov_options)
    
    # 2. Region
    reg_col = get_col(["Region"])
    region = st.sidebar.multiselect("Region", df[reg_col].unique().tolist()) if reg_col else []

    # 3. District
    dist_col = get_col(["District"])
    district = st.sidebar.multiselect("District", df[dist_col].unique().tolist()) if dist_col else []
    
    # 4. Tehsil
    tehsil_col = get_col(["Tehsil"])
    tehsil = st.sidebar.multiselect("Tehsil", df[tehsil_col].unique().tolist()) if tehsil_col else []
    
    # 5. Gender
    sex_col = get_col(["S4C5", "RSex", "Gender"])
    gender = st.sidebar.multiselect("Gender", df[sex_col].unique().tolist()) if sex_col else []
    
    # --- APPLY FILTERS ---
    # We build a boolean mask
    # Note: For category data, we ensure we match against the category type
    mask = df[prov_col].isin(province)
    
    if reg_col and region: mask &= df[reg_col].isin(region)
    if dist_col and district: mask &= df[dist_col].isin(district)
    if tehsil_col and tehsil: mask &= df[tehsil_col].isin(tehsil)
    if sex_col and gender: mask &= df[sex_col].isin(gender)
    
    df_filtered = df[mask]

    # --- 4. KPI CARDS ---
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Database", f"{len(df):,.0f}")
    c2.metric("Filtered Size", f"{len(df_filtered):,.0f}")
    share = (len(df_filtered)/len(df)*100) if len(df) > 0 else 0
    c3.metric("Selection Share", f"{share:.1f}%")
    
    st.markdown("---")

    # --- 5. QUESTION ANALYSIS ---
    # Exclude filters from the question list to avoid clutter
    filter_cols = [prov_col, reg_col, dist_col, tehsil_col, sex_col, "Mouza", "Locality", "PCode", "EBCode"]
    all_cols = df.columns.tolist()
    questions = [x for x in all_cols if x not in filter_cols]
    
    st.subheader("📝 Question Analysis")
    selected_q = st.selectbox("Select Question:", questions)

    # --- 6. VISUALIZATION ---
    col1, col2 = st.columns([2, 1])

    with col1:
        # Prepare Data
        # Filter out #NULL! for cleaner charts
        clean_chart_data = df_filtered[df_filtered[selected_q].astype(str) != "#NULL!"]
        
        # Value Counts
        chart_df = clean_chart_data[selected_q].value_counts().reset_index()
        chart_df.columns = ["Answer", "Count"]
        
        # Calculate Percentage
        total = chart_df["Count"].sum()
        chart_df["Percentage"] = (chart_df["Count"] / total * 100) if total > 0 else 0
        
        # Bar Chart
        fig = px.bar(chart_df, x="Answer", y="Count", color="Answer", 
                     text=chart_df["Percentage"].apply(lambda x: f"{x:.1f}%"),
                     title=f"Results for: {selected_q}", template="plotly_white")
        fig.update_traces(textposition='outside')
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Stats Table")
        display_df = chart_df.copy()
        display_df["Percentage"] = display_df["Percentage"].map("{:.1f}%".format)
        st.dataframe(display_df, use_container_width=True, hide_index=True)

else:
    st.info("Awaiting Data...")
