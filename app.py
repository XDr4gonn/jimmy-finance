import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import gspread
import pytz
import time
from oauth2client.service_account import ServiceAccountCredentials
from datetime import date, datetime

# --- CONFIGURATION ---
SHEET_NAME = "Financial Blueprint - Jimmy & Lily" 
CALGARY_TZ = pytz.timezone('America/Edmonton')

# PHONE FRIENDLY: Collapsed sidebar
st.set_page_config(
    page_title="Cloud Finance Tracker", 
    layout="centered", 
    initial_sidebar_state="collapsed"
)

# --- CUSTOM CSS (White & Smart Blue) ---
st.markdown("""
    <style>
    .stApp { background-color: #FFFFFF; }
    h1, h2, h3, h4, h5, h6 { color: #1565C0 !important; font-family: sans-serif; }
    p, label, .stMarkdown, .stSelectbox, .stTextInput, .stNumberInput { color: #0D47A1 !important; }
    div.stButton > button {
        background-color: #1565C0; color: white; border-radius: 8px; border: none; padding: 10px 24px; font-weight: bold;
    }
    div.stButton > button:hover { background-color: #0D47A1; color: white; }
    div[data-testid="column"] { display: flex; align-items: center; } 
    div[data-testid="stMetric"] {
        background-color: #F0F2F6 !important; 
        padding: 15px;
        border-radius: 10px;
        border: 1px solid #d0d0d0;
        box-shadow: 1px 1px 4px rgba(0,0,0,0.1);
    }
    [data-testid="stMetricLabel"] { color: #0D47A1 !important; font-weight: bold; }
    [data-testid="stMetricValue"] { color: #1565C0 !important; font-size: 1.8rem !important; }
    </style>
    """, unsafe_allow_html=True)

# --- JAVASCRIPT: MOBILE OPTIMIZATION ---
def inject_mobile_logic():
    components.html("""
        <script>
            function applyMobileOptimizations() {
                // 1. Force Decimal Keypad
                const numInputs = window.parent.document.querySelectorAll('input[type="number"], input[type="password"]');
                numInputs.forEach(input => {
                    input.setAttribute('inputmode', 'decimal');
                });
                // 2. iOS Friendly Dropdowns
                const selectInputs = window.parent.document.querySelectorAll('div[data-testid="stSelectbox"] input');
                selectInputs.forEach(input => {
                    input.setAttribute('inputmode', 'none'); 
                    input.setAttribute('autocomplete', 'off');
                    input.style.caretColor = 'transparent'; 
                });
            }
            const observer = new MutationObserver(() => { applyMobileOptimizations(); });
            observer.observe(window.parent.document.body, { childList: true, subtree: true });
            applyMobileOptimizations();
        </script>
    """, height=0, width=0)

# --- SECURITY & USER DETECTION ---
def check_password():
    def password_entered():
        entered_pin = st.session_state["password"]
        if entered_pin == st.secrets["jimmy_pin"]:
            st.session_state["password_correct"] = True
            st.session_state["current_user"] = "Jimmy"
            del st.session_state["password"]
        elif entered_pin == st.secrets["lily_pin"]:
            st.session_state["password_correct"] = True
            st.session_state["current_user"] = "Lily"
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.text_input("Enter Your PIN", type="password", max_chars=4, on_change=password_entered, key="password")
        inject_mobile_logic() 
        return False
    elif not st.session_state["password_correct"]:
        st.text_input("Enter Your PIN", type="password", max_chars=4, on_change=password_entered, key="password")
        st.error("😕 Incorrect PIN")
        inject_mobile_logic() 
        return False
    else:
        return True

if check_password():
    current_user = st.session_state.get("current_user", "Joint")
    
    # --- GOOGLE SHEETS CONNECTION ---
    def get_google_sheet_data():
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        sheet = client.open(SHEET_NAME)
        return sheet

    try:
        sheet = get_google_sheet_data()
        trans_ws = sheet.worksheet("Transaction")
        accounts_ws = sheet.worksheet("Accounts")
        
        # Load Accounts
        accounts_df = pd.DataFrame(accounts_ws.get_all_records())
        if not accounts_df.empty:
            accounts_df.columns = accounts_df.columns.str.strip() 
            accounts_df['DisplayName'] = (
                accounts_df.get('Owner', pd.Series(['Unknown']*len(accounts_df))) + " - " + 
                accounts_df.get('Account', pd.Series(['Unknown']*len(accounts_df)))
            )
            account_options = accounts_df['DisplayName'].unique().tolist()
        else:
            account_options = []

        # Load Transactions
        trans_df = pd.DataFrame(trans_ws.get_all_records())
        if not trans_df.empty:
            trans_df.columns = trans_df.columns.str.strip() 
        
        # Load Frequent Transactions (New Sheet)
        try:
            freq_ws = sheet.worksheet("Frequent Transactions")
            freq_df = pd.DataFrame(freq_ws.get_all_records())
            if not freq_df.empty:
                freq_df.columns = freq_df.columns.str.strip()
        except:
            freq_df = pd.DataFrame() # Graceful fallback if sheet missing

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
        try: return options.index(value)
        except ValueError: return 0 

    def get_current_date():
        return datetime.now(CALGARY_TZ).date()

    def parse_account_string(account_str, default_owner):
        if " - " in account_str:
            parts = account_str.split(" - ", 1)
            if parts[0] in ["Jimmy", "Lily", "Joint"]:
                return parts[0], parts[1] 
        return default_owner, account_str 

    # --- CORE SAVE LOGIC (USED BY BOTH BUTTONS & FORM) ---
    def save_transaction(date_obj, owner_val, from_val, to_val, cat_val, desc_val, amount_val):
        if amount_val is None or amount_val == 0:
            st.error("🚫 Invalid Amount")
            return

        final_amount = round(float(amount_val), 2)
        all_values = trans_ws.get_all_values()
        next_row = len(all_values) + 1
        
        is_transfer = (from_val != "External Source") and (to_val != "External Merchant")

        if is_transfer:
            # Transfer Split Logic
            owner_from, account_from = parse_account_string(from_val, owner_val)
            row_withdrawal = [str(date_obj), owner_from, account_from, "", "Transfer", desc_val, final_amount]
            
            owner_to, account_to = parse_account_string(to_val, owner_val)
            row_deposit = [str(date_obj), owner_to, "", account_to, "Transfer", desc_val, final_amount]
            
            trans_ws.update(range_name=f"A{next_row}:G{next_row}", values=[row_withdrawal])
            trans_ws.update(range_name=f"A{next_row+1}:G{next_row+1}", values=[row_deposit])
            st.success(f"✅ Saved Transfer: {desc_val}")
        else:
            # Single Row Logic
            final_category = cat_val
            if from_val == "External Source": final_category = "Income"
            elif to_val == "External Merchant" and cat_val == "Transfer": final_category = "Shopping" 

            row_owner, row_from_acc = parse_account_string(from_val, owner_val)
            _, row_to_acc = parse_account_string(to_val, owner_val)
            
            save_from = row_from_acc if from_val != "External Source" else "External Source"
            save_to = row_to_acc if to_val != "External Merchant" else "External Merchant"
            
            new_row = [str(date_obj), owner_val, save_from, save_to, final_category, desc_val, final_amount]
            trans_ws.update(range_name=f"A{next_row}:G{next_row}", values=[new_row])
            st.success(f"✅ Saved: {desc_val} (${final_amount})")
        
        time.sleep(1.0) # Pause so user sees success message
        st.rerun()

    # --- APP INTERFACE ---
    st.title(f"💰 {current_user}'s Finance View")
    
    if st.sidebar.button("🔒 Lock App"):
        del st.session_state["password_correct"]
        st.rerun()

    tab1, tab2, tab3 = st.tabs(["➕ Add Entry", "🏦 Balances", "✏️ Manage History"])

    # --- TAB 1: ENTRY FORM ---
    with tab1:
        
        # ⚡ SECTION A: FREQUENT TRANSACTIONS (BUTTONS)
        if not freq_df.empty:
            st.subheader("⚡ Quick Add")
            f_cols = st.columns(2) # Grid layout
            for index, row in freq_df.iterrows():
                label = row.get('Label', 'Txn')
                amt_val = row.get('Amount', 0.0)
                
                # Alternate columns for grid effect
                if f_cols[index % 2].button(f"{label} (${amt_val})", use_container_width=True):
                    # Prepare data
                    d_owner = row.get('Owner', current_user) # Default to logged-in user if blank
                    if pd.isna(d_owner) or d_owner == "": d_owner = current_user
                    
                    d_from = row.get('From', 'External Source')
                    d_to = row.get('To', 'External Merchant')
                    d_cat = row.get('Category', 'Other')
                    d_desc = row.get('Description', label)
                    
                    # Execute Save
                    save_transaction(get_current_date(), d_owner, d_from, d_to, d_cat, d_desc, amt_val)
            
            st.divider()

        # 📝 SECTION B: MANUAL FORM
        st.subheader("New Transaction")
        
        with st.form("add_transaction_form", clear_on_submit=True):
            c_ratio = [3, 7]

            c1, c2 = st.columns(c_ratio)
            with c1: st.markdown("**Date**")
            with c2: date_input = st.date_input("Date", get_current_date(), label_visibility="collapsed")
            
            c1, c2 = st.columns(c_ratio)
            with c1: st.markdown("**Owner**")
            with c2: 
                default_owner_idx = get_index(owner_options, current_user)
                owner_input = st.selectbox("Owner", owner_options, index=default_owner_idx, label_visibility="collapsed")
            
            c1, c2 = st.columns(c_ratio)
            with c1: st.markdown("**Amount ($)**")
            with c2: amount = st.number_input("Amount", min_value=0.0, step=0.01, format="%.2f", value=None, placeholder="0.00", label_visibility="collapsed")
            
            inject_mobile_logic()

            c1, c2 = st.columns(c_ratio)
            with c1: st.markdown("**From**")
            with c2:
                default_from_val = "External Source"
                if current_user == "Jimmy": default_from_val = "Jimmy - Credit Card"
                elif current_user == "Lily": default_from_val = "Lily - Credit Card"
                from_idx = get_index(from_options, default_from_val)
                payment_from = st.selectbox("From", from_options, index=from_idx, label_visibility="collapsed")
            
            c1, c2 = st.columns(c_ratio)
            with c1: st.markdown("**To**")
            with c2: payment_to = st.selectbox("To", to_options, index=0, label_visibility="collapsed")
            
            c1, c2 = st.columns(c_ratio)
            with c1: st.markdown("**Category**")
            with c2: category = st.selectbox("Category", cat_options, index=get_index(cat_options, "Transfer"), label_visibility="collapsed")
            
            c1, c2 = st.columns(c_ratio)
            with c1: st.markdown("**Note**")
            with c2: desc = st.text_input("Description", placeholder="e.g. E-Transfer", label_visibility="collapsed")
            
            st.markdown("###") 
            submitted = st.form_submit_button("Submit Transaction", use_container_width=True)

            if submitted:
                # Validation checks before calling save
                if amount is None:
                    st.error("🚫 Please enter an amount.")
                elif payment_from == "External Source" and payment_to == "External Merchant":
                    st.error("🚫 Invalid transaction.")
                elif payment_from == payment_to:
                     st.error("🚫 Invalid: Same account.")
                else:
                    # Call shared save function
                    save_transaction(date_input, owner_input, payment_from, payment_to, category, desc, amount)

    # --- TAB 2: MONTHLY PERFORMANCE ---
    with tab2:
        st.header("Monthly Performance")
        if not trans_df.empty:
            trans_df['DateObj'] = pd.to_datetime(trans_df['Date'], errors='coerce')
            trans_df['Amount'] = pd.to_numeric(trans_df['Amount'], errors='coerce').fillna(0)
            today = get_current_date()
            current_month_df = trans_df[
                (trans_df['DateObj'].dt.month == today.month) & 
                (trans_df['DateObj'].dt.year == today.year)
            ]
            total_gain = current_month_df[current_month_df['Category'] == "Income"]['Amount'].sum()
            spend_df = current_month_df[(~current_month_df['Category'].isin(["Income", "Transfer"]))]
            total_spend = spend_df['Amount'].sum()
            net_gain = total_gain - total_spend

            m1, m2, m3 = st.columns(3)
            with m1: st.metric("Total Gain", f"${total_gain:,.2f}")
            with m2: st.metric("Total Spend", f"${total_spend:,.2f}")
            with m3: st.metric("Net Gain", f"${net_gain:,.2f}")
            st.caption(f"Showing data for {today.strftime('%B %Y')}")
            st.divider()

        st.subheader("Account Balances")
        if not accounts_df.empty:
            display_cols = ["Owner", "Account", "Current Amount", "Next Payment"]
            existing_cols = [c for c in display_cols if c in accounts_df.columns]
            st.dataframe(accounts_df[existing_cols], use_container_width=True, hide_index=True)
        else:
            st.info("No account data found.")

    # --- TAB 3: MANAGE HISTORY ---
    with tab3:
        st.header("Manage Transactions")
        if not trans_df.empty:
            trans_df['GS_Row_Num'] = trans_df.index + 2
            trans_df['Label'] = (
                "Row " + trans_df['GS_Row_Num'].astype(str) + ": " + 
                trans_df['Date'].astype(str) + " | " + 
                trans_df['Description'].astype(str) + " | $" + 
                trans_df['Amount'].astype(str)
            )
            selection_options = trans_df['Label'].tolist()[::-1]

            # DELETE
            with st.expander("🗑️ Delete a Transaction", expanded=False):
                delete_selection = st.selectbox("Select Transaction to Delete", selection_options, key="del_select")
                if st.button("Confirm Delete 🗑️", type="primary"):
                    if delete_selection:
                        row_num_del = int(delete_selection.split(":")[0].replace("Row ", ""))
                        try:
                            trans_ws.delete_rows(row_num_del)
                            st.success(f"Deleted row {row_num_del}!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {e}")

            # EDIT
            with st.expander("✏️ Edit a Transaction", expanded=False):
                edit_selection = st.selectbox("Select Transaction to Edit", selection_options, key="edit_select")
                if edit_selection:
                    row_num = int(edit_selection.split(":")[0].replace("Row ", ""))
                    df_index = row_num - 2
                    current_data = trans_df.loc[df_index]
                    try: current_date = pd.to_datetime(current_data['Date']).date()
                    except: current_date = get_current_date()

                    with st.form("edit_form"):
                        st.caption(f"Editing Row {row_num}")
                        ecol1, ecol2 = st.columns(2)
                        with ecol1:
                            new_date = st.date_input("Date", current_date)
                            new_owner = st.selectbox("Owner", owner_options, index=get_index(owner_options, current_data['Owner']))
                            new_amount = st.number_input("Amount ($)", value=float(current_data['Amount']), step=0.01, format="%.2f")
                        with ecol2:
                            def find_full_name(short_name, options):
                                if not short_name: return options[0]
                                for opt in options:
                                    if short_name == "External Source" or short_name == "External Merchant": return short_name
                                    if short_name in opt: return opt
                                return options[0]
                            curr_from_full = find_full_name(current_data['From'], from_options)
                            curr_to_full = find_full_name(current_data['To'], to_options)
                            new_from = st.selectbox("From", from_options, index=get_index(from_options, curr_from_full))
                            new_to = st.selectbox("To", to_options, index=get_index(to_options, curr_to_full))
                            new_cat = st.selectbox("Category", cat_options, index=get_index(cat_options, current_data['Category']))
                        
                        new_desc = st.text_input("Description", value=current_data['Description'])
                        update_submitted = st.form_submit_button("💾 Update Transaction", type="primary")
                        
                        if update_submitted:
                            range_name = f"A{row_num}:G{row_num}"
                            _, clean_from = parse_account_string(new_from, new_owner)
                            _, clean_to = parse_account_string(new_to, new_owner)
                            if new_from == "External Source": clean_from = "External Source"
                            if new_to == "External Merchant": clean_to = "External Merchant"
                            updated_values = [[str(new_date), new_owner, clean_from, clean_to, new_cat, new_desc, new_amount]]
                            trans_ws.update(range_name=range_name, values=updated_values)
                            st.success("Updated!")
                            st.rerun()

            st.markdown("### Recent Activity")
            display_df = trans_df.drop(columns=['GS_Row_Num', 'Label'])
            st.dataframe(display_df.tail(15).iloc[::-1], use_container_width=True, hide_index=True)
        else:
            st.info("No transaction history found.")
