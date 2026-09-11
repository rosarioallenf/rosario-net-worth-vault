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

# Compact styling for small screens (Allen's Dell laptop / mobile, 2026-09-11):
# Streamlit's default metric numbers and top page padding are sized for a
# big monitor. This trims both - smaller title, smaller st.metric value/
# label/delta (covers BOTH the top Net Worth row and the bottom subtotal
# row, since they're both built with st.metric), and less reserved space
# above the title. Only affects this page. If a future Streamlit version
# renames these internal data-testid hooks, this stops applying and the
# page just falls back to normal (larger) sizing - harmless either way.
st.markdown(
    """
    <style>
    .block-container { padding-top: 2rem; }
    h1 { font-size: 1.6rem !important; }
    div[data-testid="stMetric"] { padding: 0.15rem 0 !important; }
    div[data-testid="stMetricValue"] { font-size: 1.3rem !important; }
    div[data-testid="stMetricLabel"] { font-size: 0.78rem !important; }
    div[data-testid="stMetricDelta"] { font-size: 0.78rem !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

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
prior_total, prior_by_account = net_worth_as_of(summaries, datetime.strptime(prior_statement_date, "%Y-%m-%d").date()) if prior_statement_date else (None, {})
year_ago_total, year_ago_by_account = net_worth_as_of(summaries, one_year_ago)

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
member_names_present = sorted({
    accounts_by_key.get(key, {}).get("member", "")
    for key in current_by_account
    if accounts_by_key.get(key, {}).get("member")
})

filter_col1, filter_col2, toggle_col = st.columns([3, 2, 2])
institution_filter = filter_col1.selectbox("Institution", ["All institutions"] + inst_names_present)
member_filter = filter_col2.selectbox("Member", ["All members"] + member_names_present)
show_closed = toggle_col.checkbox("Show closed / zero-balance accounts", value=False)

rows = []
for key, balance in current_by_account.items():
    acct = accounts_by_key.get(key, {})
    if institution_filter != "All institutions" and acct.get("institution") != institution_filter:
        continue
    if member_filter != "All members" and acct.get("member") != member_filter:
        continue
    # "closed" here just means the latest balance is $0 - a paid-off card,
    # a fully drawn-down IRA, a matured/closed CD, etc. - not tied to any
    # one account_type, since zero balance can happen to any kind of account
    is_closed = abs(balance) < 0.01
    if is_closed and not show_closed:
        continue
    prior_balance = prior_by_account.get(key)
    year_ago_balance = year_ago_by_account.get(key)
    rows.append({
        "Institution": acct.get("institution", ""),
        "Member": acct.get("member", ""),
        "Account": acct.get("display_name", key),
        "Type": acct.get("account_type", ""),
        "Balance": balance,
        "+/- Since Last Update": (balance - prior_balance) if prior_balance is not None else None,
        "+/- Since 1 Year Ago": (balance - year_ago_balance) if year_ago_balance is not None else None,
    })
columns = ["Institution", "Member", "Account", "Type", "Balance", "+/- Since Last Update", "+/- Since 1 Year Ago"]
df = pd.DataFrame(rows, columns=columns)

# Same collapsible-per-institution look as the Accounts Directory page, per
# Allen's own request (2026-09-11) - one section per institution, all listed
# on screen at once, ordered the same way (most accounts first) so the two
# pages feel like the same system. Each section's own subtotal is right in
# its header so you don't have to expand it just to see the number.
if df.empty:
    st.info("No accounts to show for this filter.")
else:
    inst_order = (
        df.groupby("Institution")["Account"].count().sort_values(ascending=False).index.tolist()
    )
    for inst_name in inst_order:
        inst_df = df[df["Institution"] == inst_name].sort_values(["Member", "Account"])
        inst_subtotal = inst_df["Balance"].sum()
        with st.expander(f"**{inst_name}**  —  {len(inst_df)} account(s)  —  ${inst_subtotal:,.2f}"):
            st.dataframe(
                inst_df.drop(columns=["Institution"]),
                column_config={
                    "Balance": st.column_config.NumberColumn(format="$%.2f"),
                    "+/- Since Last Update": st.column_config.NumberColumn(format="$%.2f"),
                    "+/- Since 1 Year Ago": st.column_config.NumberColumn(format="$%.2f"),
                },
                hide_index=True,
                width="stretch",
            )

label_parts = []
if institution_filter != "All institutions":
    label_parts.append(institution_filter)
if member_filter != "All members":
    label_parts.append(member_filter)
label = " / ".join(label_parts) if label_parts else "all accounts shown"
sub1, sub2, sub3 = st.columns(3)
sub1.metric(f"Subtotal — {label}", f"${df['Balance'].sum():,.2f}" if not df.empty else "$0.00")
sub2.metric("+/- Since Last Update", f"${df['+/- Since Last Update'].sum():,.2f}" if not df.empty else "$0.00")
sub3.metric("+/- Since 1 Year Ago", f"${df['+/- Since 1 Year Ago'].sum():,.2f}" if not df.empty else "$0.00")
st.caption(f"{len(df)} account(s) shown" + ("" if show_closed else " (closed/zero-balance accounts hidden)"))

st.caption(f"Figures as of the most recent statement on file: {latest_statement_date}")
