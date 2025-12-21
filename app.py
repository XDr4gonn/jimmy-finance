import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import date

# --- CONFIGURATION ---
SHEET_NAME = "Financial Blueprint - Jimmy & Lily" 

st.set_page_config(page_title="Cloud Finance Tracker", layout="centered")

# --- GOOGLE SHEETS CONNECTION ---
def get_google_sheet_data():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    # Read secrets
    creds_dict = dict(st.secrets["gcp_service_account"])
    
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    
    sheet = client.open(SHEET_NAME)
    trans_worksheet = sheet.worksheet("Transaction")
    accounts_worksheet = sheet.worksheet("Accounts")
    
    return trans_worksheet, accounts_worksheet

# --- LOAD DATA ---
try:
    trans_ws, accounts_ws = get_google_sheet_data()
    
    # Load Accounts
    accounts_data = accounts_ws.get_all_records()
    accounts_df = pd.DataFrame(accounts_data)
    
    # Populate Dropdowns
    if not accounts_df.empty:
        account_options = accounts_df['Account'].unique().tolist()
        # Clean up data for display (optional: ensure amounts are strings or floats as needed)
    else:
        account_options = []

    # Load Transactions
    trans_data = trans_ws.get_all_records()
    trans_df = pd.DataFrame(trans_data)
    
except Exception as e:
    st.error(f"Error connecting to Google Sheets: {e}")
    st.stop()

account_options.sort()
from_options = ["External Source"] + account_options
to_options = ["External Merchant"] + account_options

# --- APP INTERFACE ---
st.title("💰 Jimmy & Lily Finance")

# Create 3 Tabs for better mobile navigation
tab1, tab2, tab3 = st.tabs(["➕ Add Entry", "🏦 Balances", "📜 History"])

# --- TAB 1: ENTRY FORM ---
with tab1:
    st.header("New Transaction")
    with st.form("transaction_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        
        with col1:
            date_input = st.date_input("Date", date.today())
            owner = st.selectbox("Owner", ["Jimmy", "Lily", "Joint"])
            amount = st.number_input("Amount ($)", step=0.01, format="%.2f")
            
        with col2:
            payment_from = st.selectbox("From", from_options, index=0)
            payment_to = st.selectbox("To", to_options, index=0)
            category = st.selectbox("Category", [
                "Food/Groceries", "Housing", "Childcare", "Debt Repayment", 
                "Transportation", "Shopping", "Income", "Transfer", "Other"
            ])

        desc = st.text_input("Description", placeholder="e.g. Costco, Rent")

        submitted = st.form_submit_button("Submit Transaction", use_container_width=True)

        if submitted:
            new_row = [
                str(date_input),
                owner,
                payment_from,
                payment_to,
                category,
                desc,
                amount
            ]
            trans_ws.append_row(new_row)
            st.success("Saved!")

# --- TAB 2: ACCOUNTS OVERVIEW ---
with tab2:
    st.header("Current Balances")
    # Button to refresh data manually in case you edited the sheet elsewhere
    if st.button("Refresh Data"):
        st.cache_data.clear()
        
    if not accounts_df.empty:
        # Display the main columns to save space
        display_cols = ["Owner", "Account", "Current Amount", "Next Payment"]
        
        # Check if columns exist before trying to show them
        existing_cols = [c for c in display_cols if c in accounts_df.columns]
        
        st.dataframe(
            accounts_df[existing_cols], 
            use_container_width=True, 
            hide_index=True
        )
    else:
        st.info("No account data found.")

# --- TAB 3: HISTORY ---
with tab3:
    st.header("Recent Activity")
    if not trans_df.empty:
        # Show newest first
        st.dataframe(
            trans_df.tail(15).iloc[::-1], 
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No history yet.")
