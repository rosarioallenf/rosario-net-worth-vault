"""Browse the full transaction ledger for any account."""
import pandas as pd
import streamlit as st

from lib import require_passphrase, load_accounts, load_transactions

st.set_page_config(page_title="Transactions", page_icon="\U0001F4C4", layout="wide")
require_passphrase()

st.title("Transactions")

accounts = load_accounts()
labels = {a["account_key"]: f"{a['member']} - {a['display_name']} ({a['account_key']})" for a in accounts}
account_key = st.selectbox("Account", options=list(labels.keys()), format_func=lambda k: labels[k])

search = st.text_input("Search description (optional)")

txns = load_transactions(account_key=account_key)
df = pd.DataFrame(txns)
if not df.empty:
    if search:
        df = df[df["description"].str.contains(search, case=False, na=False)]
    df = df[["txn_date", "deposit", "withdrawal", "balance", "description", "source_file"]]
    df.columns = ["Date", "Deposit", "Withdrawal", "Balance", "Description", "Source statement"]
    st.dataframe(
        df,
        column_config={
            "Deposit": st.column_config.NumberColumn(format="$%.2f"),
            "Withdrawal": st.column_config.NumberColumn(format="$%.2f"),
            "Balance": st.column_config.NumberColumn(format="$%.2f"),
        },
        hide_index=True,
        width="stretch",
    )
    st.caption(f"{len(df)} transactions")
else:
    st.info("No transactions found for this account.")
