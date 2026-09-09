"""Rosario Net Worth Vault - Home / Net Worth Report.

Shows current net worth, the change since the last statement update, and
the change from a year ago, broken down by account.
"""
from datetime import datetime, date

import pandas as pd
import streamlit as st

from lib import (
    require_passphrase,
    load_accounts,
    load_institutions,
    load_monthly_summaries,
    net_worth_as_of,
    a_year_ago,
)

st.set_page_config(page_title="Rosario Net Worth Vault", page_icon="\U0001F4B0", layout="wide")
require_passphrase()

st.title("Net Worth Vault")

accounts = load_accounts()
summaries = load_monthly_summaries()

if not summaries:
    st.info("No statement data loaded yet.")
    st.stop()

accounts_by_key = {a["account_key"]: a for a in accounts}

latest_statement_date = max(r["statement_date"] for r in summaries)
statement_dates = sorted({r["statement_date"] for r in summaries})
# the statement date immediately before the latest one, across the whole
# dataset - used for the "change since last update" figure
prior_statement_date = statement_dates[-2] if len(statement_dates) > 1 else None

today = datetime.strptime(latest_statement_date, "%Y-%m-%d").date()
one_year_ago = a_year_ago(today)

current_total, current_by_account = net_worth_as_of(summaries, today)
prior_total, _ = net_worth_as_of(summaries, datetime.strptime(prior_statement_date, "%Y-%m-%d").date()) if prior_statement_date else (None, {})
year_ago_total, _ = net_worth_as_of(summaries, one_year_ago)

col1, col2, col3 = st.columns(3)
col1.metric("Net Worth", f"${current_total:,.2f}", help=f"As of {latest_statement_date}")
if prior_total is not None:
    col2.metric("Change since last update", f"${current_total - prior_total:,.2f}",
                delta=f"{current_total - prior_total:,.2f}")
else:
    col2.metric("Change since last update", "n/a")
col3.metric("Change from a year ago", f"${current_total - year_ago_total:,.2f}",
            delta=f"{current_total - year_ago_total:,.2f}",
            help=f"vs. {one_year_ago.isoformat()}")

st.divider()
st.subheader("By account")

institutions = load_institutions()
inst_names_present = sorted({
    accounts_by_key.get(key, {}).get("institution", "")
    for key in current_by_account
    if accounts_by_key.get(key, {}).get("institution")
})
institution_filter = st.selectbox("Institution", ["All institutions"] + inst_names_present)

rows = []
for key, balance in current_by_account.items():
    acct = accounts_by_key.get(key, {})
    if institution_filter != "All institutions" and acct.get("institution") != institution_filter:
        continue
    rows.append({
        "Member": acct.get("member", ""),
        "Institution": acct.get("institution", ""),
        "Account": acct.get("display_name", key),
        "Type": acct.get("account_type", ""),
        "Balance": balance,
    })
df = pd.DataFrame(rows).sort_values(["Member", "Type", "Account"])
st.dataframe(
    df,
    column_config={"Balance": st.column_config.NumberColumn(format="$%.2f")},
    hide_index=True,
    width="stretch",
)
if institution_filter != "All institutions":
    st.caption(f"Showing {len(df)} account(s) at {institution_filter} — ${df['Balance'].sum():,.2f} subtotal")

st.caption(f"Figures as of the most recent statement on file: {latest_statement_date}")
