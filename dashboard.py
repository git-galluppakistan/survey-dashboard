import streamlit as st
import pandas as pd
import plotly.express as px
import os
import gc

# --- 1. SETUP ---
st.set_page_config(page_title="Gallup Pakistan Dashboard", layout="wide", page_icon="📊")
st.markdown("""<style>.block-container {padding-top: 1rem;}</style>""", unsafe_allow_html=True)
st.title("📊 Gallup Pakistan: National LFS Survey")

# --- 2. ZERO-COPY DATA LOADER ---
@st.cache_resource
def load_data_optimized():
    try:
        # A. File Check
        file_name = "data.zip" if os.path.exists("data.zip") else "Data.zip"
        if not os.path.exists(file_name):
            st.error(f"File not found: {file_name}")
            return None, None

        # B. Chunk Load & Compress
        chunks = []
        for chunk in pd.read_csv(file_name, compression='zip', chunksize=50000, low_memory=True):
            # Force everything to category
            for col in chunk.columns:
                chunk[col] = chunk[col].astype('category')
            
            # AGE FIX (S4C6)
            age_col = next((c for c in chunk.columns if c in ['S4C6', 'Age']), None)
            if age_col:
                chunk[age_col] = pd.to_numeric(chunk[age_col], errors='coerce')

            chunks.append(chunk)
        
        df = pd.concat(chunks, axis=0)
        del chunks
        gc.collect()

        # C. Load Codebook
        if os.path.exists("code.csv"):
            codes = pd.read_csv("code.csv")
            rename_dict = {}
            for code, label in zip(codes.iloc[:, 0], codes.iloc[:, 1]):
                # Keep original filter names + S4C6
                if code not in ['Province', 'District', 'Region', 'Tehsil', 'RSex', 'S4C5', 'S4C9', 'S4C6', 'Mouza', 'Locality']:
                    rename_dict[code] = f"{label} ({code})"
            df.rename(columns=rename_dict, inplace=True)

        return df

    except Exception as e:
        st.error(f"Error: {e}")
        return None

# Load Data
df = load_data_optimized()

# --- 3. DASHBOARD LOGIC ---
if df is not None:
    # --- FILTERS ---
    st.sidebar.title("🔍 Filters")
    
    # Helper to find columns
    def get_col(candidates):
        for c in candidates:
            for col in df.columns:
                if c in col: return col
        return None

    # Get Columns
    prov_col = get_col(["Province"])
    reg_col = get_col(["Region"])
    dist_col = get_col(["District"])
    tehsil_col = get_col(["Tehsil"])
    sex_col = get_col(["S4C5", "RSex", "Gender"])
    edu_col = get_col(["S4C9", "Education", "Highest class"])
    age_col = get_col(["S4C6", "Age"])

    # 1. Province
    sel_prov = st.sidebar.multiselect("Province", df[prov_col].unique().tolist(), default=df[prov_col].unique().tolist())
    
    # 2. Age Slider
    if age_col:
        min_age = int(df[age_col].min())
        max_age = int(df[age_col].max())
        sel_age = st.sidebar.slider("Age Range", min_age, max_age, (min_age, max_age))
    
    # 3. Dynamic Filters
    if sel_prov and dist_col:
        valid_districts = df[df[prov_col].isin(sel_prov)][dist_col].unique().tolist()
        sel_dist = st.sidebar.multiselect("District", valid_districts)
    else:
        sel_dist = []

    if sel_prov and tehsil_col:
        valid_tehsils = df[df[prov_col].isin(sel_prov)][tehsil_col].unique().tolist()
        sel_tehsil = st.sidebar.multiselect("Tehsil", valid_tehsils)
    else:
        sel_tehsil = []

    sel_reg = st.sidebar.multiselect("Region", df[reg_col].unique().tolist()) if reg_col else []
    sel_sex = st.sidebar.multiselect("Gender", df[sex_col].unique().tolist()) if sex_col else []
    sel_edu = st.sidebar.multiselect("Education", df[edu_col].unique().tolist()) if edu_col else []

    # --- FILTERING LOGIC ---
    mask = df[prov_col].isin(sel_prov)
    
    if age_col: mask = mask & (df[age_col] >= sel_age[0]) & (df[age_col] <= sel_age[1])
    if sel_dist: mask = mask & df[dist_col].isin(sel_dist)
    if sel_tehsil: mask = mask & df[tehsil_col].isin(sel_tehsil)
    if sel_reg: mask = mask & df[reg_col].isin(sel_reg)
    if sel_sex: mask = mask & df[sex_col].isin(sel_sex)
    if sel_edu: mask = mask & df[edu_col].isin(sel_edu)
        
    filtered_count = mask.sum()

    # --- KPI CARDS ---
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Database", f"{len(df):,.0f}")
    c2.metric("Filtered Size", f"{filtered_count:,.0f}")
    c3.metric("Selection Share", f"{(filtered_count/len(df)*100):.1f}%")
    
    st.markdown("---")

    # --- ANALYSIS SECTION ---
    ignore = [prov_col, reg_col, sex_col, dist_col, tehsil_col, edu_col, age_col, "Mouza", "Locality", "PCode", "EBCode"]
    questions = [c for c in df.columns if c not in ignore]
    
    target_q = st.selectbox("Select Question to Analyze:", questions)

    if target_q:
        # Create Two Columns for Charts
        chart_col1, chart_col2 = st.columns(2)

        # --- CHART 1: OVERALL RESULTS (LEFT) ---
        with chart_col1:
            st.subheader("📊 Overall Results")
            counts = df.loc[mask, target_q].value_counts()
            
            chart_df = counts.reset_index()
            chart_df.columns = ["Answer", "Count"]
            chart_df = chart_df[chart_df["Answer"].astype(str) != "#NULL!"]
            
            total = chart_df["Count"].sum()
            chart_df["Percentage"] = (chart_df["Count"] / total * 100).fillna(0)
            
            fig = px.bar(chart_df, x="Answer", y="Count", color="Answer",
                         text=chart_df["Percentage"].apply(lambda x: f"{x:.1f}%"),
                         template="plotly_white")
            st.plotly_chart(fig, use_container_width=True)

        # --- CHART 2: PROVINCIAL SPLIT (RIGHT) ---
        with chart_col2:
            st.subheader("🗺️ Provincial Breakdown")
            # We group by Province AND the Answer
            # Note: We filter out #NULL! answers for clarity
            prov_data = df.loc[mask, [prov_col, target_q]]
            prov_data = prov_data[prov_data[target_q].astype(str) != "#NULL!"]
            
            # Group and Count
            prov_counts = prov_data.groupby([prov_col, target_q], observed=True).size().reset_index(name='Count')
            
            # Stacked Bar Chart
            fig_prov = px.bar(prov_counts, x=prov_col, y="Count", color=target_q,
                              title="Comparison by Province",
                              barmode="group", # Side-by-side bars (Change to 'stack' if preferred)
                              template="plotly_white")
            st.plotly_chart(fig_prov, use_container_width=True)

        # --- DATA TABLE (BOTTOM) ---
        st.subheader("📋 Detailed Data Table")
        display_df = chart_df.copy()
        display_df["Percentage"] = display_df["Percentage"].map("{:.1f}%".format)
        st.dataframe(display_df, use_container_width=True, hide_index=True)

else:
    st.info("Awaiting Data...")
