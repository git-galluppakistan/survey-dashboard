import streamlit as st
import pandas as pd
import plotly.express as px
import os
import gc

# --- 1. SETUP ---
st.set_page_config(page_title="Gallup Pakistan Dashboard", layout="wide", page_icon="📊")

# Modern CSS
st.markdown("""
    <style>
    .block-container {padding-top: 1rem; padding-left: 1rem; padding-right: 1rem;}
    div[data-testid="metric-container"] {
        background-color: #f0f2f6;
        border: 1px solid #d6d6d6;
        padding: 10px;
        border-radius: 5px;
    }
    </style>
""", unsafe_allow_html=True)

st.title("📊 Gallup Pakistan: National LFS Survey")

# --- 2. ZERO-COPY DATA LOADER ---
@st.cache_resource
def load_data_optimized():
    try:
        # A. File Check
        file_name = "data.zip" if os.path.exists("data.zip") else "Data.zip"
        if not os.path.exists(file_name):
            st.error(f"File not found: {file_name}")
            return None

        # B. Chunk Load
        chunks = []
        for chunk in pd.read_csv(file_name, compression='zip', chunksize=50000, low_memory=True, dtype=str):
            for col in chunk.columns:
                chunk[col] = chunk[col].astype('category')
            
            # AGE FIX
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
                if code not in ['Province', 'District', 'Region', 'Tehsil', 'RSex', 'S4C5', 'S4C9', 'S4C6', 'Mouza', 'Locality']:
                    rename_dict[code] = f"{label} ({code})"
            df.rename(columns=rename_dict, inplace=True)

        return df

    except Exception as e:
        st.error(f"Error: {e}")
        return None

df = load_data_optimized()

# --- 3. DASHBOARD LOGIC ---
if df is not None:
    # --- SIDEBAR FILTERS ---
    st.sidebar.title("🔍 Filter Panel")
    
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
    prov_list = df[prov_col].unique().tolist() if prov_col else []
    sel_prov = st.sidebar.multiselect("Province", prov_list, default=prov_list)
    
    # 2. Age Range
    if age_col:
        min_age, max_age = int(df[age_col].min()), int(df[age_col].max())
        sel_age = st.sidebar.slider("Age Range", min_age, max_age, (min_age, max_age))
    
    # 3. District
    valid_districts = df[df[prov_col].isin(sel_prov)][dist_col].unique().tolist() if (sel_prov and dist_col) else []
    sel_dist = st.sidebar.multiselect("District", valid_districts)

    # 4. Tehsil
    if sel_dist and tehsil_col:
        valid_tehsils = df[df[dist_col].isin(sel_dist)][tehsil_col].unique().tolist()
    else:
        valid_tehsils = []
    sel_tehsil = st.sidebar.multiselect("Tehsil", valid_tehsils)

    # 5. Other Filters
    sel_reg = st.sidebar.multiselect("Region", df[reg_col].unique().tolist()) if reg_col else []
    sel_sex = st.sidebar.multiselect("Gender", df[sex_col].unique().tolist()) if sex_col else []
    sel_edu = st.sidebar.multiselect("Education", df[edu_col].unique().tolist()) if edu_col else []

    # --- FILTER MASK ---
    mask = pd.Series(True, index=df.index)
    if prov_col: mask = mask & df[prov_col].isin(sel_prov)
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
    c2.metric("Filtered Respondents", f"{filtered_count:,.0f}")
    c3.metric("Selection Share", f"{(filtered_count/len(df)*100):.1f}%")
    
    st.markdown("---")

    # --- MAIN QUESTION SELECTION ---
    ignore = [prov_col, reg_col, sex_col, dist_col, tehsil_col, edu_col, age_col, "Mouza", "Locality", "PCode", "EBCode"]
    questions = [c for c in df.columns if c not in ignore]
    
    # Default: Marital Status
    default_target = "Marital status (S4C7)"
    default_index = questions.index(default_target) if default_target in questions else 0
    target_q = st.selectbox("Select Question to Analyze:", questions, index=default_index)

    if target_q:
        # Prepare Main Data
        cols_to_load = [target_q] + [c for c in [prov_col, sex_col, reg_col, dist_col, age_col] if c]
        main_data = df.loc[mask, cols_to_load]
        
        # Clean Data
        main_data[target_q] = main_data[target_q].astype(str)
        main_data = main_data[main_data[target_q] != "#NULL!"]
        main_data = main_data[main_data[target_q] != "nan"]
        
        # ==========================================================
        # ROW 1
        # ==========================================================
        col1, col2, col3 = st.columns([1.5, 1, 1])

        # 1. OVERALL BAR (Variable 'counts' defined here)
        with col1:
            st.markdown("**📊 Overall Results (%)**")
            counts = main_data[target_q].value_counts().reset_index()
            counts.columns = ["Answer", "Count"]
            total = counts["Count"].sum()
            counts["%"] = (counts["Count"] / total * 100).fillna(0)
            
            fig1 = px.bar(counts, x="Answer", y="%", color="Answer", 
                          text=counts["%"].apply(lambda x: f"{x:.1f}%"),
                          template="plotly_white", 
                          color_discrete_sequence=px.colors.qualitative.Bold)
            fig1.update_layout(showlegend=True, margin=dict(l=20, r=20, t=30, b=20))
            st.plotly_chart(fig1, use_container_width=True)

        # 2. PROVINCE BAR
        with col2:
            st.markdown("**🗺️ By Province (%)**")
            if prov_col:
                prov_grp = main_data.groupby([prov_col, target_q], observed=True).size().reset_index(name='Count')
                prov_totals = prov_grp.groupby(prov_col, observed=True)['Count'].transform('sum')
                prov_grp['%'] = (prov_grp['Count'] / prov_totals * 100).fillna(0)
                
                fig2 = px.bar(prov_grp, x=prov_col, y="%", color=target_q,
                              template="plotly_white", barmode="stack")
                fig2.update_layout(showlegend=True, margin=dict(l=20, r=20, t=30, b=20), yaxis_title="%")
                st.plotly_chart(fig2, use_container_width=True)

        # 3. GENDER DONUT
        with col3:
            st.markdown("**🚻 By Gender**")
            if sex_col:
                gender_counts = main_data[sex_col].value_counts().reset_index()
                gender_counts.columns = ["Gender", "Count"]
                
                fig3 = px.pie(gender_counts, names="Gender", values="Count", hole=0.5,
                              color_discrete_sequence=px.colors.qualitative.Pastel)
                fig3.update_layout(showlegend=True, margin=dict(l=20, r=20, t=30, b=20), 
                                   legend=dict(orientation="h"))
                st.plotly_chart(fig3, use_container_width=True)

        # ==========================================================
        # ROW 2
        # ==========================================================
        col4, col5, col6 = st.columns([1, 1.5, 1])

        # 4. REGION PIE
        with col4:
            st.markdown("**🏙️ By Region**")
            if reg_col:
                reg_counts = main_data[reg_col].value_counts().reset_index()
                reg_counts.columns = ["Region", "Count"]
                fig4 = px.pie(reg_counts, names="Region", values="Count", 
                              color_discrete_sequence=px.colors.qualitative.Set3)
                fig4.update_layout(showlegend=True, margin=dict(l=20, r=20, t=30, b=20), 
                                   legend=dict(orientation="h"))
                st.plotly_chart(fig4, use_container_width=True)

        # 5. AGE TRENDS
        with col5:
            st.markdown("**📈 Age Trends (%)**")
            if age_col:
                main_data['AgeGrp'] = pd.cut(main_data[age_col], bins=[0,18,30,45,60,100], labels=['<18','18-30','31-45','46-60','60+'])
                age_grp = main_data.groupby(['AgeGrp', target_q], observed=True).size().reset_index(name='Count')
                
                age_totals = age_grp.groupby('AgeGrp', observed=True)['Count'].transform('sum')
                age_grp['%'] = (age_grp['Count'] / age_totals * 100).fillna(0)
                
                fig5 = px.area(age_grp, x="AgeGrp", y="%", color=target_q,
                               template="plotly_white", markers=True)
                fig5.update_layout(showlegend=True, margin=dict(l=20, r=20, t=30, b=20), yaxis_title="%")
                st.plotly_chart(fig5, use_container_width=True)

        # 6. DISTRICT TREEMAP (FIXED VARIABLE NAME)
        with col6:
            if dist_col:
                # 1. Detect "Top Answer"
                top_ans = main_data[target_q].mode()[0]
                st.markdown(f"**🧱 District Heatmap**<br><span style='font-size:0.8em; color:gray'>Color = <b>% {top_ans}</b></span>", unsafe_allow_html=True)
                
                # 2. Get Top 10 Districts
                top_10 = main_data[dist_col].value_counts().head(10).index.tolist()
                subset = main_data[main_data[dist_col].isin(top_10)]
                
                # 3. Calculate % of Top Answer
                dist_stats = pd.crosstab(subset[dist_col], subset[target_q], normalize='index') * 100
                
                if top_ans in dist_stats.columns:
                    plot_df = dist_stats[[top_ans]].reset_index()
                    plot_df.columns = ["District", "Percent"]
                    
                    # 4. Add Sizes - RENAME VARIABLE HERE to 'tree_counts'
                    tree_counts = subset[dist_col].value_counts().reset_index()
                    tree_counts.columns = ["District", "Count"]
                    
                    # Merge using new variable
                    final_df = pd.merge(plot_df, tree_counts, on="District")
                    
                    # 5. Label
                    final_df["Label"] = final_df.apply(lambda x: f"{x['District']}<br>{x['Percent']:.1f}%", axis=1)

                    fig6 = px.treemap(final_df, path=["Label"], values="Count",
                                      color="Percent", color_continuous_scale="Viridis",
                                      title=None)
                    fig6.update_layout(margin=dict(l=10, r=10, t=10, b=10))
                    st.plotly_chart(fig6, use_container_width=True)
                else:
                    st.warning("Data insufficient for map")

        # ==========================================================
        # ROW 3: TABLES (Now 'counts' is safe!)
        # ==========================================================
        st.markdown("---")
        t1, t2 = st.columns(2)
        
        with t1:
            st.subheader("📋 Overall Data")
            # This safely uses the 'counts' from Row 1
            counts["%"] = counts["%"].map("{:.1f}%".format)
            st.dataframe(counts, use_container_width=True, hide_index=True)
            
        with t2:
            st.subheader("🏘️ District Rankings (Top %)")
            if dist_col:
                dist_pivot = pd.crosstab(main_data[dist_col], main_data[target_q], normalize='index') * 100
                if not dist_pivot.empty:
                    top_ans = dist_pivot.mean().idxmax()
                    dist_pivot = dist_pivot.sort_values(by=top_ans, ascending=False).head(50)
                    dist_display = dist_pivot.applymap(lambda x: f"{x:.1f}%")
                    st.dataframe(dist_display, use_container_width=True)

else:
    st.info("Awaiting Data...")
