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
inventory_file = st.file_uploader("Choose an Excel file", type=["xlsx"])

st.subheader("Upload Data Feed (CSV or TXT)")
data_feed_file = st.file_uploader("Choose a CSV or TXT file", type=["csv", "txt"])

# Select Country
st.subheader("Select Country")
country_options = ["Brazil", "Chile", "Mexico", "Colombia", "Argentina"]
selected_country = st.selectbox("Choose a country:", country_options)

# Select Year Filter
st.subheader("Select Year Threshold")
current_year = datetime.now().year
selected_year = st.selectbox("Select the earliest model year to keep active:", [current_year, current_year - 1, current_year - 2])

if st.button("Process Files"):
    if inventory_file and data_feed_file:
        # Load inventory file
        df_inventory = pd.read_excel(inventory_file, sheet_name=0)
        df_inventory = df_inventory.rename(columns={
            "Mpl Product Id": "MPL_PRODUCT_ID",
            "Item Number": "PID",
            "Available Qty": "Available_Qty"
        })

        # Load data feed
        if data_feed_file.name.endswith(".csv"):
            df_feed = pd.read_csv(data_feed_file, delimiter=";")
        else:
            df_feed = pd.read_csv(data_feed_file, delimiter="|")

        # Ensure required columns exist
        required_columns = {"PID", "MPL_PRODUCT_ID", "COLOR_ID", "BASE_APPROVED", "COLOR_APPROVED", "SKU_APPROVED", "ECOM_ENABLED", "MODEL_YEAR"}
        if not required_columns.issubset(df_feed.columns):
            st.error("Data Feed is missing required columns.")
            st.stop()
        
        # Convert MODEL_YEAR to numeric
        df_feed["MODEL_YEAR"] = pd.to_numeric(df_feed["MODEL_YEAR"], errors='coerce')
        
        # Filter data feed: Only True values in all approval columns
        df_feed_filtered = df_feed[
            (df_feed["BASE_APPROVED"] == True) &
            (df_feed["COLOR_APPROVED"] == True) &
            (df_feed["SKU_APPROVED"] == True) &
            (df_feed["ECOM_ENABLED"] == True)
        ]
        
        # Merge with inventory to get Available Qty
        df_merged = df_feed_filtered.merge(df_inventory, on="PID", how="left")
        df_merged["Available_Qty"].fillna(0, inplace=True)
        
        # Aggregate Available Qty at MPL_PRODUCT_ID level
        df_aggregated = df_merged.groupby("MPL_PRODUCT_ID")["Available_Qty"].sum().reset_index()
        
        # Merge aggregated data back to original DataFrame
        df_final = df_merged.merge(df_aggregated, on="MPL_PRODUCT_ID", suffixes=("_sku", "_mpl"))
        
        # Filter: Available Qty (aggregated) = 0 and MODEL_YEAR < selected year
        df_final_filtered = df_final[(df_final["Available_Qty_mpl"] == 0) & (df_final["MODEL_YEAR"] < selected_year)]
        
        # Prepare output file
        df_output = df_final_filtered[["PID", "MPL_PRODUCT_ID", "COLOR_ID"]].copy()
        df_output["CATALOG_VERSION"] = "SBC" + selected_country + "ProductCatalog"
        df_output["APPROVAL_STATUS"] = "unapproved"
        df_output.rename(columns={"PID": "SKU", "MPL_PRODUCT_ID": "Base Product ID"}, inplace=True)
        
        # Generate timestamp for filename
        timestamp = datetime.now().strftime("%d%m%Y%H%M")
        output_filename = f"SBC_HYBRIS_SIZEVARIANT_APPROVAL_{timestamp}.txt"
        
        # Convert to text format
        output = io.StringIO()
        df_output.to_csv(output, sep="|", index=False)
        processed_file_content = output.getvalue()
        
        # Show success message and download button
        st.success("✅ File successfully generated!")
        st.download_button(
            label="Download Processed File",
            data=processed_file_content,
            file_name=output_filename,
            mime="text/plain"
        )
