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
        st
