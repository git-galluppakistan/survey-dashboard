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
# We use cache_resource because it shares the memory pointer instead of copying data
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
            # Force everything to category (The biggest RAM saver)
            for col in chunk.columns:
                chunk[col] = chunk[col].astype('category')
            chunks.append(chunk)
        
        df = pd.concat(chunks, axis=0)
        del chunks
        gc.collect()

        # C. Load Codebook
        if os.path.exists("code.csv"):
            codes = pd.read_csv("code.csv")
            # Create rename dictionary
            rename_dict = {}
            for code, label in zip(codes.iloc[:, 0], codes.iloc[:, 1]):
                # Keep original filter names
                if code not in ['Province', 'District', 'Region', 'Tehsil', 'RSex', 'S4C5']:
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
    # --- FILTERS (Directly on Sidebar) ---
    st.sidebar.title("🔍 Filters")
    
    # Helper to find columns safely
    def get_col(candidates):
        for c in candidates:
            for col in df.columns:
                if c in col: return col
        return None

    # Get Columns
    prov_col = get_col(["Province"])
    reg_col = get_col(["Region"])
    sex_col = get_col(["S4C5", "RSex", "Gender"])

    # Create Filter Widgets
    # We use .unique().tolist() to avoid keeping large arrays in memory
    sel_prov = st.sidebar.multiselect("Province", df[prov_col].unique().tolist(), default=df[prov_col].unique().tolist())
    sel_reg = st.sidebar.multiselect("Region", df[reg_col].unique().tolist()) if reg_col else []
    sel_sex = st.sidebar.multiselect("Gender", df[sex_col].unique().tolist()) if sex_col else []

    # --- ZERO-COPY FILTERING ---
    # Instead of making a new dataframe, we create a simple True/False list (very small)
    # Start with all True
    mask = df[prov_col].isin(sel_prov)
    
    if sel_reg:
        mask = mask & df[reg_col].isin(sel_reg)
    if sel_sex:
        mask = mask & df[sex_col].isin(sel_sex)
        
    # Calculate Counts directly using the mask
    filtered_count = mask.sum()

    # --- KPI CARDS ---
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Database", f"{len(df):,.0f}")
    c2.metric("Filtered Size", f"{filtered_count:,.0f}")
    c3.metric("Selection Share", f"{(filtered_count/len(df)*100):.1f}%")
    
    st.markdown("---")

    # --- QUESTION ANALYSIS ---
    ignore = [prov_col, reg_col, sex_col, "District", "Tehsil", "Mouza", "Locality"]
    questions = [c for c in df.columns if c not in ignore]
    
    target_q = st.selectbox("Select Question to Analyze:", questions)

    if target_q:
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # MEMORY TRICK: Only slice the ONE column we need, then count
            # This avoids copying the whole 50-column dataframe
            counts = df.loc[mask, target_q].value_counts()
            
            # Convert to neat dataframe for plotting
            chart_df = counts.reset_index()
            chart_df.columns = ["Answer", "Count"]
            chart_df = chart_df[chart_df["Answer"].astype(str) != "#NULL!"] # Hide NULLs
            
            total = chart_df["Count"].sum()
            chart_df["Percentage"] = (chart_df["Count"] / total * 100).fillna(0)
            
            # Plot
            fig = px.bar(chart_df, x="Answer", y="Count", color="Answer",
                         text=chart_df["Percentage"].apply(lambda x: f"{x:.1f}%"),
                         title=f"Results: {target_q}")
            st.plotly_chart(fig, use_container_width=True)
            
        with col2:
            st.subheader("Data Table")
            display_df = chart_df.copy()
            display_df["Percentage"] = display_df["Percentage"].map("{:.1f}%".format)
            st.dataframe(display_df, hide_index=True)
