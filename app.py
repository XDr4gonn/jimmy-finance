import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import date, datetime

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
owner_options = ["Jimmy", "Lily", "Joint"]
cat_options = ["Food/Groceries", "Housing", "Childcare", "Debt Repayment", "Transportation", "Shopping", "Income", "Transfer", "Other"]

# --- HELPER FUNCTIONS ---
def get_index(options, value):
    """Helper to find the index of a value in a list (for dropdown defaults)."""
    try:
        return options.index(value)
    except ValueError:
        return 0

# --- APP INTERFACE ---
st.title("💰 Jimmy & Lily Finance")

tab1, tab2, tab3 = st.tabs(["➕ Add Entry", "🏦 Balances", "✏️ Manage History"])

# --- TAB 1: ENTRY FORM ---
with tab1:
    st.header("New Transaction")
    with st.form("add_transaction_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            date_input = st.date_input("Date", date.today())
            owner = st.selectbox("Owner", owner_options)
            amount = st.number_input("Amount ($)", step=0.01, format="%.2f")
        with col2:
            payment_from = st.selectbox("From", from_options, index=0)
            payment_to = st.selectbox("To", to_options, index=0)
            category = st.selectbox("Category", cat_options)
        desc = st.text_input("Description", placeholder="e.g. Costco")
        
        submitted = st.form_submit_button("Submit Transaction", use_container_width=True)

        if submitted:
            if payment_from == "External Source" and payment_to == "External Merchant":
                st.error("🚫 Invalid: Money cannot go from 'External' to 'External'.")
            elif payment_from == payment_to:
                 st.error("🚫 Invalid: 'From' and 'To' cannot be the same.")
            else:
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

# --- TAB 3: MANAGE HISTORY (EDIT & DELETE) ---
with tab3:
    st.header("Manage Transactions")
    
    if not trans_df.empty:
        # Prepare Data for Dropdowns
        # Calculate Google Sheet Row Number (Index + 2 because of header)
        trans_df['GS_Row_Num'] = trans_df.index + 2
        trans_df['Label'] = (
            "Row " + trans_df['GS_Row_Num'].astype(str) + ": " + 
            trans_df['Date'].astype(str) + " | " + 
            trans_df['Description'] + " | $" + 
            trans_df['Amount'].astype(str)
        )
        # Reverse list to show newest first
        selection_options = trans_df['Label'].tolist()[::-1]

        # --- SECTION: EDIT ---
        with st.expander("✏️ Edit a Transaction", expanded=False):
            edit_selection = st.selectbox("Select Transaction to Edit", selection_options, key="edit_select")
            
            if edit_selection:
                # Find the data for the selected row
                row_num = int(edit_selection.split(":")[0].replace("Row ", ""))
                # Adjust for 0-based dataframe index (Row 2 in sheet is Index 0)
                df_index = row_num - 2
                current_data = trans_df.loc[df_index]
                
                # Parse Date
                try:
                    current_date = pd.to_datetime(current_data['Date']).date()
                except:
                    current_date = date.today()

                # --- EDIT FORM ---
                with st.form("edit_form"):
                    st.caption(f"Editing Row {row_num}")
                    ecol1, ecol2 = st.columns(2)
                    with ecol1:
                        new_date = st.date_input("Date", current_date)
                        new_owner = st.selectbox("Owner", owner_options, index=get_index(owner_options, current_data['Owner']))
                        new_amount = st.number_input("Amount ($)", value=float(current_data['Amount']), step=0.01, format="%.2f")
                    with ecol2:
                        new_from = st.selectbox("From", from_options, index=get_index(from_options, current_data['From']))
                        new_to = st.selectbox("To", to_options, index=get_index(to_options, current_data['To']))
                        new_cat = st.selectbox("Category", cat_options, index=get_index(cat_options, current_data['Category']))
                    
                    new_desc = st.text_input("Description", value=current_data['Description'])
                    
                    update_submitted = st.form_submit_button("💾 Update Transaction", type="primary")
                    
                    if update_submitted:
                        # Logic Validation
                        if new_from == "External Source" and new_to == "External Merchant":
                            st.error("🚫 Invalid: Money cannot go from 'External' to 'External'.")
                        elif new_from == new_to:
                            st.error("🚫 Invalid: 'From' and 'To' cannot be the same.")
                        else:
                            # Update Google Sheet
                            # Note: update uses range (A5:G5).
                            range_name = f"A{row_num}:G{row_num}"
                            updated_values = [[str(new_date), new_owner, new_from, new_to, new_cat, new_desc, new_amount]]
                            trans_ws.update(range_name=range_name, values=updated_values)
                            
                            st.success("Transaction updated successfully!")
                            st.rerun()

        # --- SECTION: DELETE ---
        with st.expander("🗑️ Delete a Transaction", expanded=False):
            delete_selection = st.selectbox("Select Transaction to Delete", selection_options, key="del_select")
            
            if st.button("Confirm Delete 🗑️", type="primary"):
                if delete_selection:
                    row_num_del = int(delete_selection.split(":")[0].replace("Row ", ""))
                    try:
                        trans_ws.delete_rows(row_num_del)
                        st.success(f"Deleted row {row_num_del} successfully!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Could not delete: {e}")

        # --- HISTORY VIEW ---
        st.markdown("### Recent Activity")
        display_df = trans_df.drop(columns=['GS_Row_Num', 'Label'])
        st.dataframe(display_df.tail(15).iloc[::-1], use_container_width=True, hide_index=True)
    else:
        st.info("No history yet.")
