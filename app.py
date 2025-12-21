import streamlit as st
import pandas as pd
import gspread
import json  # <--- NEW IMPORT
from oauth2client.service_account import ServiceAccountCredentials
from datetime import date

# --- CONFIGURATION ---
SHEET_NAME = "Financial Blueprint - Jimmy & Lily" 

st.set_page_config(page_title="Cloud Finance Tracker", layout="centered")

# --- GOOGLE SHEETS CONNECTION ---
def get_google_sheet_data():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    # NEW LOGIC: Read the raw JSON string from secrets
    json_creds = json.loads(st.secrets["service_account_json"])
    
    creds = ServiceAccountCredentials.from_json_keyfile_dict(json_creds, scope)
    client = gspread.authorize(creds)
    
    sheet = client.open(SHEET_NAME)
    trans_worksheet = sheet.worksheet("Transaction")
    accounts_worksheet = sheet.worksheet("Accounts")
    
    return trans_worksheet, accounts_worksheet

# --- LOAD DATA ---
try:
    trans_ws, accounts_ws = get_google_sheet_data()
    
    # Load Accounts for Dropdowns
    accounts_data = accounts_ws.get_all_records()
    accounts_df = pd.DataFrame(accounts_data)
    account_options = accounts_df['Account'].unique().tolist() if not accounts_df.empty else []
    
    # Load Transactions for History
    trans_data = trans_ws.get_all_records()
    trans_df = pd.DataFrame(trans_data)
    
except Exception as e:
    st.error(f"Error connecting to Google Sheets: {e}")
    st.stop()

account_options.sort()
from_options = ["External Source"] + account_options
to_options = ["External Merchant"] + account_options

# --- APP INTERFACE ---
st.title("☁️ Jimmy & Lily Cloud Tracker")
st.markdown("---")

with st.form("transaction_form", clear_on_submit=True):
    col1, col2 = st.columns(2)
    
    with col1:
        # Date needs to be string for Google Sheets usually
        date_input = st.date_input("Date", date.today())
        owner = st.selectbox("Owner", ["Jimmy", "Lily", "Joint"])
        amount = st.number_input("Amount (CAD$)", step=0.01, format="%.2f")
        
    with col2:
        payment_from = st.selectbox("From (Source)", from_options, index=0)
        payment_to = st.selectbox("To (Destination)", to_options, index=0)
        category = st.selectbox("Category", [
            "Food/Groceries", "Housing", "Childcare", "Debt Repayment", 
            "Transportation", "Shopping", "Income", "Transfer", "Other"
        ])

    desc = st.text_input("Description", placeholder="e.g., Walmart, Rent")

    submitted = st.form_submit_button("☁️ Save to Google Sheets")

    if submitted:
        # Prepare row data
        # Note: We convert date to string explicitly for JSON compatibility
        new_row = [
            str(date_input),
            owner,
            payment_from,
            payment_to,
            category,
            desc,
            amount
        ]
        
        # Append to Google Sheet
        trans_ws.append_row(new_row)
        
        st.success("✅ Saved directly to the Cloud!")
        
        # Optional: Clear cache to force reload next time (Streamlit specific optimization)
        # st.experimental_rerun() is deprecated in newer versions, usually not needed for simple appends

# --- DISPLAY RECENT TRANSACTIONS ---
st.markdown("### 📝 Recent Cloud Data")
if not trans_df.empty:
    # We show the data we loaded at the start. 
    # To see the brand new row, you'd usually need to refresh the page.
    st.dataframe(trans_df.tail(5).iloc[::-1], use_container_width=True)
else:

    st.info("No transactions found on the sheet.")

