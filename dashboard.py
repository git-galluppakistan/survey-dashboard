import streamlit as st
import pandas as pd
import plotly.express as px
import os
import gc  # Garbage Collection to free memory

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
    try:
        # A. DETECT FILE
        if os.path.exists("data.zip"):
            file_name = "data.zip"
        elif os.path.exists("Data.zip"):
            file_name = "Data.zip"
        else:
            st.error("CRITICAL ERROR: Could not find 'data.zip'.")
            st.stop()
            
        # B. LOAD DATA IN CHUNKS
        chunks = []
        # Load only necessary columns if possible, but for now we load all carefully
        for chunk in pd.read_csv(file_name, compression='zip', chunksize=50000, low_memory=True):
            # Optimize: Convert ALL objects to category
            for col in chunk.select_dtypes(include=['object']).columns:
                chunk[col] = chunk[col].astype('category')
            # Downcast integers to save space
            for col in chunk.select_dtypes(include=['int64']).columns:
                chunk[col] = pd.to_numeric(chunk[col], downcast='unsigned')
            chunks.append(chunk)
        
        df = pd.concat(chunks, axis=0)
        del chunks # Delete chunks to free RAM immediately
        gc.collect() # Force memory cleanup
        
        # C. LOAD CODEBOOK
        if os.path.exists("code.csv"):
            codes = pd.read_csv("code.csv")
        else:
            codes = pd.DataFrame(columns=["Code", "Label"])

        # --- STEP D: MAP VALUES ---
        gender_map = {
            "1": "Male", 1: "Male",
            "2": "Female", 2: "Female",
            "3": "Transgender", 3: "Transgender",
            "#NULL!": "Unknown"
        }
        
        if 'RSex' in df.columns:
            df['RSex'] = df['RSex'].astype(str).map(gender_map).fillna(df['RSex']).astype('category')
        if 'S4C5' in df.columns:
            df['S4C5'] = df['S4C5'].astype(str).map(gender_map).fillna(df['S4C5']).astype('category')

        # --- STEP E: RENAME COLUMNS ---
        protected_cols = ['Province', 'District', 'Region', 'Tehsil', 'Mouza', 'Locality', 'RSex']
        
        if not codes.empty:
            code_col = codes.columns[0]
            label_col = codes.columns[1]
            rename_dict = {}
            for code, label in zip(codes[code_col], codes[label_col]):
                if code not in protected_cols:
                    rename_dict[code] = f"{label} ({code})"
            df.rename(columns=rename_dict, inplace=True)
        
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
    
    # Helper to find columns
    def get_col(candidates):
        for c in candidates:
            for col_name in df.columns:
                if c in col_name: return col_name
        return None

    # Get Filter Columns
    prov_col = get_col(["Province"]) or df.columns[0]
    reg_col = get_col(["Region"])
    dist_col = get_col(["District"])
    sex_col = get_col(["S4C5", "RSex", "Gender"])

    # UI Options
    province = st.sidebar.multiselect("Province", df[prov_col].unique().tolist(), default=df[prov_col].unique().tolist())
    region = st.sidebar.multiselect("Region", df[reg_col].unique().tolist()) if reg_col else []
    gender = st.sidebar.multiselect("Gender", df[sex_col].unique().tolist()) if sex_col else []

    # --- MEMORY EFFICIENT FILTERING ---
    # Instead of creating a massive 'mask' of Trues/Falses (which takes RAM),
    # We filter step-by-step and use .copy() to drop the link to the big dataframe
    
    df_filtered = df[df[prov_col].isin(province)]
    
    if region:
        df_filtered = df_filtered[df_filtered[reg_col].isin(region)]
    if gender:
        df_filtered = df_filtered[df_filtered[sex_col].isin(gender)]
    
    # Force Garbage Collection after filtering
    gc.collect()

    # --- 4. KPI CARDS ---
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Database", f"{len(df):,.0f}")
    c2.metric("Filtered Size", f"{len(df_filtered):,.0f}")
    share = (len(df_filtered)/len(df)*100) if len(df) > 0 else 0
    c3.metric("Selection Share", f"{share:.1f}%")
    
    st.markdown("---")

    # --- 5. QUESTION ANALYSIS ---
    # Exclude filters from questions
    ignore_cols = [prov_col, reg_col, dist_col, sex_col, "Mouza", "Locality", "PCode", "EBCode"]
    questions = [x for x in df.columns if x not in ignore_cols]
    
    st.subheader("📝 Question Analysis")
    selected_q = st.selectbox("Select Question:", questions)

    if selected_q:
        # --- 6. VISUALIZATION ---
        col1, col2 = st.columns([2, 1])

        with col1:
            # GroupBy is faster and uses less RAM than value_counts on full frame
            chart_df = df_filtered[selected_q].value_counts(dropna=True).reset_index()
            chart_df.columns = ["Answer", "Count"]
            
            # Remove #NULL!
            chart_df = chart_df[chart_df["Answer"].astype(str) != "#NULL!"]
            
            total = chart_df["Count"].sum()
            chart_df["Percentage"] = (chart_df
