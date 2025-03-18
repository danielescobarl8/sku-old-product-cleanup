import streamlit as st
import pandas as pd
import io
from datetime import datetime

# Secure Access
PASSWORD = "specialized1974"
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if not st.session_state.logged_in:
    st.title("Secure Access")
    user_password = st.text_input("Enter Password:", type="password")
    if st.button("Login"):
        if user_password == PASSWORD:
            st.session_state.logged_in = True
            st.rerun()
        else:
            st.error("Incorrect password. Try again.")
if not st.session_state.logged_in:
    st.stop()

# App Title
st.title("SKU Unapproval Tool")

# Upload Files
st.subheader("Upload Inventory File (Excel)")
inventory_file = st.file_uploader("Choose an Excel file", type=["xlsx"], key="inventory")

st.subheader("Upload Data Feed (CSV or TXT)")
data_feed_file = st.file_uploader("Choose a CSV or TXT file", type=["csv", "txt"], key="datafeed")

# Select Country
country_options = ["Brazil", "Chile", "Mexico", "Colombia", "Argentina"]
selected_country = st.selectbox("Choose a country:", country_options)

# Select Year Filter
current_year = datetime.now().year
selected_year = st.selectbox("Choose model year threshold:", [current_year, current_year - 1, current_year - 2])

if st.button("Process Files"):
    if inventory_file and data_feed_file:
        try:
            df_inventory = pd.read_excel(inventory_file, sheet_name=0, usecols=["Item Number", "Available Qty"])
            df_inventory.rename(columns={"Item Number": "PID", "Available Qty": "Available_Qty"}, inplace=True)
        except Exception as e:
            st.error(f"Error reading inventory file: {e}")
            st.stop()

        try:
            df_feed = pd.read_csv(data_feed_file, sep=None, engine='python', usecols=["PID", "MPL_PRODUCT_ID", "MODEL_YEAR", "BASE_APPROVED", "COLOR_APPROVED", "SKU_APPROVED", "ECOM_ENABLED", "IS_BIKE"])
        except Exception as e:
            st.error(f"Error reading data feed: {e}")
            st.stop()

        # Convert columns to appropriate data types
        for col in ["BASE_APPROVED", "COLOR_APPROVED", "SKU_APPROVED", "ECOM_ENABLED", "IS_BIKE"]:
            df_feed[col] = df_feed[col].astype(str).str.strip().str.lower().replace({"true": True, "false": False}).astype(bool)
        df_feed["MODEL_YEAR"] = pd.to_numeric(df_feed["MODEL_YEAR"], errors='coerce')

        # Filter products
        df_filtered = df_feed.query("BASE_APPROVED & COLOR_APPROVED & SKU_APPROVED & ECOM_ENABLED")
        df_merged = df_filtered.merge(df_inventory, on="PID", how="left").fillna({"Available_Qty": 0})
        df_aggregated = df_merged.groupby("MPL_PRODUCT_ID")["Available_Qty"].sum().reset_index()
        df_final = df_merged.merge(df_aggregated, on="MPL_PRODUCT_ID", suffixes=("_sku", "_mpl"))

        # Bikes processing
        df_bikes = df_final.query("Available_Qty_mpl == 0 and MODEL_YEAR < @selected_year and IS_BIKE")
        df_bikes_output = df_bikes.drop_duplicates(subset=["MPL_PRODUCT_ID"])[["MPL_PRODUCT_ID"]].copy()
        df_bikes_output.rename(columns={"MPL_PRODUCT_ID": "PRODUCT_ID"}, inplace=True)
        df_bikes_output.insert(1, "CATALOG_VERSION", "SBC" + selected_country + "ProductCatalog")
        df_bikes_output.insert(2, "ARCHIVED", "TRUE")
        empty_cols = ["ECOM_ENABLED", "CN_PRODUCT_LINK", "JP_PRODUCT_LINK", "KR_PRODUCT_LINK", "NEW", "NEW_END_DATE", "IS_TESTABLE", "CNC_DISABLED", "HOME_DELIVERY", "CO_PRODUCT_LINK", "NON_RETURNABLE", "STH_DISABLED"]
        for col in empty_cols:
            df_bikes_output[col] = ""

        # Convert to CSV efficiently
        output_bikes = df_bikes_output.to_csv(sep="|", index=False, encoding='utf-8', errors='replace')
        st.download_button("Download Processed File (Bikes)", data=output_bikes, file_name="SBC_HYBRIS_BIKES_APPROVAL.txt", mime="text/plain")
