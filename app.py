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
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    
    sheet = client.open(SHEET_NAME)
    return sheet

# --- LOAD DATA ---
try:
    sheet = get_google_sheet_data()
    trans_ws = sheet.worksheet("Transaction")
    accounts_ws = sheet.worksheet("Accounts")
    
    # Load Accounts
    accounts_data = accounts_ws.get_all_records()
    accounts_df = pd.DataFrame(accounts_data)
    account_options = accounts_df['Account'].unique().tolist() if not accounts_df.empty else []

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
        desc = st.text_input("Description", placeholder="e.g. Costco")
        
        submitted = st.form_submit_button("Submit Transaction", use_container_width=True)

        if submitted:
            # --- NEW VALIDATION LOGIC ---
            if payment_from == "External Source" and payment_to == "External Merchant":
                st.error("🚫 Invalid Transaction: Money cannot go from 'External' to 'External'. One side must be your account.")
            
            elif payment_from == payment_to:
                 st.error("🚫 Invalid Transaction: 'From' and 'To' cannot be the same account.")
                 
            else:
                # Only save if logic passes
                new_row = [str(date_input), owner, payment_from, payment_to, category, desc, amount]
                trans_ws.append_row(new_row)
                st.success("Saved!")
                st.rerun()

# --- TAB 2: ACCOUNTS OVERVIEW ---
with tab2:
    st.header("Current Balances")
    if st.button("🔄 Refresh Data"):
        st.cache_data.clear()
        st.rerun()
        
    if not accounts_df.empty:
        display_cols = ["Owner", "Account", "Current Amount", "Next Payment"]
        existing_cols = [c for c in display_cols if c in accounts_df.columns]
        st.dataframe(accounts_df[existing_cols], use_container_width=True, hide_index=True)
    else:
        st.info("No account data found.")

# --- TAB 3: HISTORY & DELETE ---
with tab3:
    st.header("Manage Transactions")
    
    if not trans_df.empty:
        with st.expander("🗑️ Delete a Transaction", expanded=False):
            st.warning("Warning: This permanently removes the row from Google Sheets.")
            
            trans_df['GS_Row_Num'] = trans_df.index + 2
            trans_df['Label'] = (
                "Row " + trans_df['GS_Row_Num'].astype(str) + ": " + 
                trans_df['Date'].astype(str) + " | " + 
                trans_df['Description'] + " | $" + 
                trans_df['Amount'].astype(str)
            )
            
            delete_options = trans_df['Label'].tolist()[::-1]
            selected_to_delete = st.selectbox("Select Entry to Delete", delete_options)
            
            if st.button("Confirm Delete 🗑️", type="primary"):
                if selected_to_delete:
                    row_num_to_delete = int(selected_to_delete.split(":")[0].replace("Row ", ""))
                    try:
                        trans_ws.delete_rows(row_num_to_delete)
                        st.success(f"Deleted row {row_num_to_delete} successfully!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Could not delete: {e}")

        # View History
        st.markdown("### Recent Activity")
        display_df = trans_df.drop(columns=['GS_Row_Num', 'Label'])
        st.dataframe(display_df.tail(15).iloc[::-1], use_container_width=True, hide_index=True)
    else:
        st.info("No history yet.")
