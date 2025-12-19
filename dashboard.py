import streamlit as st
import pandas as pd
import plotly.express as px

# --- SAFETY NET: IF THIS FAILS, IT PRINTS THE ERROR ---
try:
    # 1. SETUP
    st.set_page_config(page_title="Gallup Dashboard", layout="wide", page_icon="📊")
    
    st.markdown("""
        <style>
        .block-container {padding-top: 1rem; padding-bottom: 0rem;}
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        </style>
    """, unsafe_allow_html=True)

    st.title("📊 Gallup Pakistan: National LFS Survey Dashboard")

# 2. LOAD & CLEAN DATA (MEMORY OPTIMIZED)
@st.cache_data
def load_data():
    try:
        # Load Data in Chunks to prevent crashing (Memory Saver)
        chunks = []
        # Read file in pieces of 50,000 rows
        for chunk in pd.read_csv("data.zip", compression='zip', chunksize=50000, low_memory=True):
            # Optimize: Convert text columns to 'category' (Saves 90% RAM)
            for col in chunk.select_dtypes(include=['object']).columns:
                chunk[col] = chunk[col].astype('category')
            chunks.append(chunk)
        
        # Combine all pieces
        df = pd.concat(chunks, axis=0)
        
        # Load Codebook
        codes = pd.read_csv("code.csv")
        
        # --- STEP A: MAP VALUES (1->Male, 2->Female) ---
        gender_map = {
            "1": "Male", 1: "Male",
            "2": "Female", 2: "Female",
            "3": "Transgender", 3: "Transgender",
            "#NULL!": "Unknown"
        }
        
        # Apply to RSex (Convert to object temporarily if needed, then re-categorize)
        if 'RSex' in df.columns:
            df['RSex'] = df['RSex'].astype(str).map(gender_map).fillna(df['RSex']).astype('category')
        if 'S4C5' in df.columns:
            df['S4C5'] = df['S4C5'].astype(str).map(gender_map).fillna(df['S4C5']).astype('category')

        # --- STEP B: RENAME COLUMNS ---
        protected_cols = ['Province', 'District', 'Region', 'Tehsil', 'Mouza', 'Locality', 'RSex']
        
        # Create rename dict
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

    df = load_data()

    if df is not None:
        # 3. SIDEBAR FILTERS (Now includes ALL your highlighted variables)
        st.sidebar.title("🔍 Filter Panel")
        st.sidebar.subheader("Demographics")
        
        # Helper to safely find columns
        def get_col(candidates):
            for c in candidates:
                for col_name in df.columns:
                    if c in col_name: return col_name
            return None

        # --- A. GEOGRAPHY FILTERS ---
        # 1. Province
        prov_col = get_col(["Province"]) or df.columns[0]
        province = st.sidebar.multiselect("Province", df[prov_col].unique(), default=df[prov_col].unique())
        
        # 2. Region (Rural/Urban)
        reg_col = get_col(["Region"])
        region = st.sidebar.multiselect("Region", df[reg_col].unique(), default=df[reg_col].unique()) if reg_col else []

        # 3. District
        dist_col = get_col(["District"])
        district = st.sidebar.multiselect("District", df[dist_col].unique()) if dist_col else []
        
        # 4. Tehsil
        tehsil_col = get_col(["Tehsil"])
        tehsil = st.sidebar.multiselect("Tehsil", df[tehsil_col].unique()) if tehsil_col else []
        
        # --- B. DEMOGRAPHIC FILTERS ---
        # 5. Gender (Try S4C5 first, then RSex)
        sex_col = get_col(["S4C5", "RSex", "Gender"])
        gender = st.sidebar.multiselect("Gender", df[sex_col].unique(), default=df[sex_col].unique()) if sex_col else []
        
        # 6. Education (S4C9) - Search for it because it might be renamed
        edu_col = get_col(["S4C9", "Highest class"])
        education = st.sidebar.multiselect("Education (Class Passed)", df[edu_col].unique()) if edu_col else []

        # --- APPLY FILTERS ---
        # Start with all data
        mask = pd.Series(True, index=df.index)
        
        # Apply each filter only if the user selected something (or left defaults)
        if prov_col: mask &= df[prov_col].isin(province)
        if reg_col and region: mask &= df[reg_col].isin(region)
        if dist_col and district: mask &= df[dist_col].isin(district)
        if tehsil_col and tehsil: mask &= df[tehsil_col].isin(tehsil)
        if sex_col and gender: mask &= df[sex_col].isin(gender)
        if edu_col and education: mask &= df[edu_col].isin(education)
        
        df_filtered = df[mask]

        # 4. KPI CARDS
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Database", f"{len(df):,.0f}")
        c2.metric("Filtered Size", f"{len(df_filtered):,.0f}")
        share = (len(df_filtered)/len(df)*100) if len(df) > 0 else 0
        c3.metric("Selection Share", f"{share:.1f}%")
        
        st.markdown("---")

        # 5. QUESTION SELECTOR
        # Exclude the filter columns from the analysis list
        filter_cols = [prov_col, reg_col, dist_col, tehsil_col, sex_col, edu_col, "Mouza", "Locality", "PCode", "EBCode"]
        all_cols = df.columns.tolist()
        questions = [x for x in all_cols if x not in filter_cols and x is not None]
        
        st.subheader("📝 Question Analysis")
        selected_q = st.selectbox("Select Question:", questions)

        # 6. VISUALIZATION
        col1, col2 = st.columns([2, 1])

        with col1:
            # Prepare Data
            clean_chart_data = df_filtered[df_filtered[selected_q] != "#NULL!"]
            chart_df = clean_chart_data[selected_q].value_counts().reset_index()
            chart_df.columns = ["Answer", "Count"]
            
            # Percentage
            total = chart_df["Count"].sum()
            chart_df["Percentage"] = (chart_df["Count"] / total * 100) if total > 0 else 0
            
            # Chart
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

except Exception as e:

    st.error(f"CRITICAL ERROR: {e}")

