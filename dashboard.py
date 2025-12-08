import streamlit as st
import pandas as pd
import plotly.express as px
import os

# Set page configuration
st.set_page_config(page_title="Survey Dashboard", layout="wide")

# --- 1. Intelligent Data Loader ---
@st.cache_data
def load_data():
    # Check for Zip first (for the 300k file)
    if os.path.exists('data.zip'):
        return pd.read_csv('data.zip', compression='zip', low_memory=False)
    
    # Check for any CSV
    csv_files = [f for f in os.listdir('.') if f.endswith('.csv')]
    if csv_files:
        largest_csv = max(csv_files, key=os.path.getsize)
        return pd.read_csv(largest_csv, low_memory=False)
    
    return None

try:
    df = load_data()
    if df is None:
        st.error("No data found! Please ensure 'data.zip' or a .csv file is in the folder.")
        st.stop()
except Exception as e:
    st.error(f"Error loading data: {e}")
    st.stop()

# --- 2. Dynamic Column Mapping ---
st.sidebar.title("⚙️ Configuration")
st.sidebar.info("Since you renamed columns, please match them below:")

all_cols = list(df.columns)

def get_default_index(columns, keywords):
    """Try to auto-find the column based on keywords"""
    for i, col in enumerate(columns):
        if any(k.lower() in col.lower() for k in keywords):
            return i
    return 0

# Allow user to map the columns dynamically
c_gender = st.sidebar.selectbox("Column for GENDER", all_cols, index=get_default_index(all_cols, ['gender', 'sex', 's4c5']))
c_province = st.sidebar.selectbox("Column for PROVINCE", all_cols, index=get_default_index(all_cols, ['province', 'prov']))
c_district = st.sidebar.selectbox("Column for DISTRICT", all_cols, index=get_default_index(all_cols, ['district', 'city', 's4c16']))
c_urban = st.sidebar.selectbox("Column for URBAN/RURAL", all_cols, index=get_default_index(all_cols, ['urban', 'rural', 'region', 'area']))
c_edu = st.sidebar.selectbox("Column for EDUCATION", all_cols, index=get_default_index(all_cols, ['education', 'degree', 'qualification', 's4c9']))

st.sidebar.markdown("---")
st.sidebar.header("🔍 Filters")

# --- 3. Filter Logic (Safe & Robust) ---

def get_unique_safe(column_name):
    if column_name not in df.columns:
        return []
    return df[column_name].unique()

# Gender Filter
gender_opts = [x for x in get_unique_safe(c_gender) if pd.notna(x)]
selected_gender = st.sidebar.multiselect("Select Gender", gender_opts, default=gender_opts)

# Province Filter
prov_opts = [x for x in get_unique_safe(c_province) if pd.notna(x)]
selected_province = st.sidebar.multiselect("Select Province", prov_opts, default=prov_opts)

# Urban/Rural Filter
ur_opts = [x for x in get_unique_safe(c_urban) if pd.notna(x)]
selected_ur = st.sidebar.multiselect("Select Urban/Rural", ur_opts, default=ur_opts)

# Education Filter
edu_opts = [x for x in get_unique_safe(c_edu) if pd.notna(x)]
selected_edu = st.sidebar.multiselect("Select Education", edu_opts, default=edu_opts)

# District Filter (Fix for the Sorting Crash)
raw_districts = get_unique_safe(c_district)
# Convert to string to avoid crash, and filter out 'NULL' text
clean_districts = sorted([str(x) for x in raw_districts if str(x).upper() not in ['#NULL!', 'NAN', 'NONE'] and pd.notna(x)])
selected_districts = st.sidebar.multiselect("Select District", clean_districts)

# --- 4. Apply Filters ---
mask = (
    df[c_gender].isin(selected_gender) &
    df[c_province].isin(selected_province) &
    df[c_urban].isin(selected_ur) &
    df[c_edu].isin(selected_edu)
)

if selected_districts:
    # Compare as strings to match the dropdown
    mask = mask & df[c_district].astype(str).isin(selected_districts)

filtered_df = df[mask]

# --- 5. Main Dashboard ---
st.title("📊 Survey Data Dashboard")

# KPI Cards
c1, c2, c3 = st.columns(3)
c1.metric("Total Rows", f"{len(df):,}")
c2.metric("Filtered Rows", f"{len(filtered_df):,}")
c3.metric("Percentage", f"{(len(filtered_df)/len(df)*100):.1f}%")

st.markdown("---")

# Question Analysis
st.subheader("📝 Question Analysis")

# Exclude the filter columns from the question list
exclude_cols = ['PCode', 'EBCode', 'HHNo', 'SNo', 'Name', c_gender, c_province, c_district, c_urban, c_edu]
question_cols = [c for c in df.columns if c not in exclude_cols]

selected_question = st.selectbox("Select a Question to Visualize:", question_cols, index=0 if question_cols else None)

if selected_question:
    st.write(f"**Results for:** {selected_question}")
    
    # Prepare Count Data
    counts = filtered_df[selected_question].value_counts().reset_index()
    counts.columns = ['Response', 'Count']
    counts = counts.sort_values('Count', ascending=False)
    
    # Plot
    fig = px.bar(
        counts, 
        x='Count', 
        y='Response', 
        orientation='h', 
        title=f"Distribution: {selected_question}",
        text='Count',
        color='Count',
        color_continuous_scale='Blues'
    )
    st.plotly_chart(fig, use_container_width=True)
    
    # Data Table Expander
    with st.expander("View Filtered Data Table"):
        # Show relevant columns
        display_cols = [c_province, c_gender, selected_question]
        st.dataframe(filtered_df[display_cols].head(500))

# --- Instructions for 300k File ---
# Remember to DELETE 'data.zip' on GitHub and upload the new one when you get the 300k file.