import streamlit as st
import pandas as pd
import io
from datetime import datetime

# 🔐 Set password protection
PASSWORD = "specialized1974"
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if not st.session_state.logged_in:
    st.title("🔒 Secure Access")
    user_password = st.text_input("Enter Password:", type="password")
    if st.button("Login"):
        if user_password == PASSWORD:
            st.session_state.logged_in = True
            st.rerun()
        else:
            st.error("❌ Incorrect password. Try again.")
if not st.session_state.logged_in:
    st.stop()

# App Title
st.title("SKU Unapproval Tool")

# Upload Files
st.subheader("Upload Inventory File (Excel)")
st.markdown("Download the latest inventory file from [Tableau](https://us-west-2b.online.tableau.com/#/site/specialized/views/GlobalHybrisInventory_16535184102250/TodaysInventory?:iid=1). Navigate to your country's tab and export as an Excel file.")
inventory_file = st.file_uploader("Choose an Excel file", type=["xlsx"])

st.subheader("Upload Data Feed (CSV or TXT) (From your country)")
data_feed_file = st.file_uploader("Choose a CSV or TXT file", type=["csv", "txt"])

# Select Country
st.subheader("Select Country")
country_options = ["Brazil", "Chile", "Mexico", "Colombia", "Argentina"]
selected_country = st.selectbox("Choose a country:", country_options)

# Select Year Filter
st.subheader("Select the earliest model year to keep active")
st.markdown("Products from the selected year or newer will be **excluded** from this analysis. For example, if you select **2023**, any product from 2023, 2024, or newer will remain active, while older products will be considered for deactivation.")
current_year = datetime.now().year
selected_year = st.selectbox("Choose model year threshold:", [current_year, current_year - 1, current_year - 2])

if st.button("Process Files"):
    if inventory_file and data_feed_file:
        # Load inventory file
        df_inventory = pd.read_excel(inventory_file, sheet_name=0)
        df_inventory = df_inventory.rename(columns={
            "Item Number": "PID",
            "Available Qty": "Available_Qty"
        })
        
        # Load data feed
        if data_feed_file.name.endswith(".csv"):
            df_feed = pd.read_csv(data_feed_file, delimiter=";")
        else:
            df_feed = pd.read_csv(data_feed_file, delimiter="|")
        
        # Ensure required columns exist
        required_columns = {"PID", "MPL_PRODUCT_ID", "MODEL_YEAR", "BASE_APPROVED", "COLOR_APPROVED", "SKU_APPROVED", "ECOM_ENABLED", "IS_BIKE"}
        if not required_columns.issubset(df_feed.columns):
            st.error(f"Data Feed is missing required columns: {required_columns - set(df_feed.columns)}")
            st.stop()
        
        # Convert approval columns to boolean
        approval_columns = ["BASE_APPROVED", "COLOR_APPROVED", "SKU_APPROVED", "ECOM_ENABLED", "IS_BIKE"]
        for col in approval_columns:
            df_feed[col] = df_feed[col].astype(str).str.strip().str.lower().replace({"true": True, "false": False}).astype(bool)
        
        # Convert MODEL_YEAR to numeric
        df_feed["MODEL_YEAR"] = pd.to_numeric(df_feed["MODEL_YEAR"], errors='coerce')
        
        # Filter only rows where all approval columns are True
        df_feed_filtered = df_feed[
            (df_feed["BASE_APPROVED"] == True) &
            (df_feed["COLOR_APPROVED"] == True) &
            (df_feed["SKU_APPROVED"] == True) &
            (df_feed["ECOM_ENABLED"] == True)
        ]
        
        # Merge with inventory to get Available Qty using PID as the key
        df_merged = df_feed_filtered.merge(df_inventory[['PID', 'Available_Qty']], on="PID", how="left")
        df_merged["Available_Qty"].fillna(0, inplace=True)
        
        # Aggregate Available Qty at MPL_PRODUCT_ID level
        df_aggregated = df_merged.groupby("MPL_PRODUCT_ID")["Available_Qty"].sum().reset_index()
        
        # Merge aggregated data back to original DataFrame
        df_final = df_merged.merge(df_aggregated, on="MPL_PRODUCT_ID", suffixes=("_sku", "_mpl"))
        
        # Apply correct filtering logic
        df_bikes = df_final[(df_final["Available_Qty_mpl"] == 0) & (df_final["MODEL_YEAR"] < selected_year) & (df_final["IS_BIKE"] == True)]
        df_non_bikes = df_final[(df_final["Available_Qty_mpl"] == 0) & (df_final["MODEL_YEAR"] < selected_year) & (df_final["IS_BIKE"] == False)]
        
        # Prepare output files
        timestamp = datetime.now().strftime("%d%m%Y%H%M")
        output_filename_non_bikes = f"SBC_HYBRIS_SIZEVARIANT_APPROVAL_{timestamp}.txt"
        output_filename_bikes = f"SBC_HYBRIS_SIZEVARIANT_APPROVAL_{timestamp}-1.txt"
        
        # Store processed files in session state for persistent downloads
        if "processed_file_content_non_bikes" not in st.session_state:
            st.session_state.processed_file_content_non_bikes = df_non_bikes.to_csv(sep="|", index=False)
        if "processed_file_content_bikes" not in st.session_state:
            st.session_state.processed_file_content_bikes = df_bikes.to_csv(sep="|", index=False)
        
        # Show success message and download buttons
        st.success("✅ Files successfully generated!")
        st.download_button(
            label="Download Processed File (Non-Bikes)",
            data=st.session_state.processed_file_content_non_bikes,
            file_name=output_filename_non_bikes,
            mime="text/plain"
        )
        st.download_button(
            label="Download Processed File (Bikes)",
            data=st.session_state.processed_file_content_bikes,
            file_name=output_filename_bikes,
            mime="text/plain"
        )
