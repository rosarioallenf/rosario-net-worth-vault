"""Browse and search the full transaction ledger - one account at a time, or
across the whole vault's history at once. Two independent filters, combinable
just like stacking two column filters in Excel: a text "contains" search, and
a dollar-amount range."""
import pandas as pd
import streamlit as st

from lib import require_passphrase, is_demo, load_accounts, load_transactions

st.set_page_config(page_title="Transactions", page_icon="\U0001F4C4", layout="wide")
require_passphrase()

st.title("Transactions")

demo = is_demo()
accounts = load_accounts(demo=demo)
accounts_by_key = {a["account_key"]: a for a in accounts}
labels = {a["account_key"]: f"{a['member']} - {a['display_name']} ({a['account_key']})" for a in accounts}

account_key = st.selectbox(
    "Account",
    options=["All accounts"] + list(labels.keys()),
    format_func=lambda k: "All accounts" if k == "All accounts" else labels[k],
)

search = st.text_input(
    "Search (optional)",
    placeholder="e.g. walmart, costco, autopay...",
    help="Shows any transaction where this text appears anywhere in the description, "
         "account, institution, or source statement - not case-sensitive, and it doesn't "
         "need to match the whole word, just like Excel's \"contains\" filter.",
)

filter_amount = st.checkbox("Filter by dollar amount")
amount_min, amount_max = None, None
if filter_amount:
    amt_col1, amt_col2 = st.columns(2)
    amount_min = amt_col1.number_input("Amount from ($)", min_value=0.0, value=0.0, step=10.0, format="%.2f")
    amount_max = amt_col2.number_input("Amount to ($)", min_value=0.0, value=500.0, step=10.0, format="%.2f")
    st.caption(
        "Matches the transaction's dollar amount either way - a $450 charge or a $450 "
        "payment both count as \"$450,\" not just charges. Both ends are inclusive."
    )

show_all = account_key == "All accounts"
txns = load_transactions(account_key=None if show_all else account_key, demo=demo)
df = pd.DataFrame(txns)

if not df.empty:
    # attach account/institution/member context - mainly so results read clearly
    # when searching across every account at once
    df["account_display"] = df["account_key"].map(lambda k: accounts_by_key.get(k, {}).get("display_name", k))
    df["institution"] = df["account_key"].map(lambda k: accounts_by_key.get(k, {}).get("institution", ""))
    df["member"] = df["account_key"].map(lambda k: accounts_by_key.get(k, {}).get("member", ""))

    if search:
        haystack = (
            df["description"].fillna("") + " "
            + df["account_display"].fillna("") + " "
            + df["institution"].fillna("") + " "
            + df["source_file"].fillna("")
        )
        df = df[haystack.str.contains(search, case=False, na=False, regex=False)]

    if filter_amount:
        deposit = pd.to_numeric(df["deposit"], errors="coerce")
        withdrawal = pd.to_numeric(df["withdrawal"], errors="coerce")
        amount = deposit.fillna(withdrawal)
        df = df[amount.between(amount_min, amount_max)]

    base_cols = ["txn_date", "deposit", "withdrawal", "balance", "description", "source_file"]
    base_names = ["Date", "Deposit", "Withdrawal", "Balance", "Description", "Source statement"]
    if show_all:
        df = df[["account_display", "institution", "member"] + base_cols]
        df.columns = ["Account", "Institution", "Member"] + base_names
        df = df.sort_values("Date", ascending=False)
    else:
        df = df[base_cols]
        df.columns = base_names

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
    filters_applied = []
    if search:
        filters_applied.append(f'"{search}"')
    if filter_amount:
        filters_applied.append(f"${amount_min:,.2f}-${amount_max:,.2f}")
    suffix = f" matching {' and '.join(filters_applied)}" if filters_applied else ""
    st.caption(f"{len(df)} transaction(s){suffix}")
else:
    st.info("No transactions found.")
