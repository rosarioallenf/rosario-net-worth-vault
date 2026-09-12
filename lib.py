"""Manual Entry - for any asset/liability whose institution doesn't give us
a clean statement feed. Built first for the LPL Financial "Shield" positions
(LPL's statement archive on Ascend's site is broken as of Sept 2026), but
works for any account: pick the institution, pick the account, enter what
it's worth as of a date, save.

Two-step institution -> account picker, per Allen's own suggestion, so this
scales cleanly as more accounts get added instead of one long dropdown.
"""
from datetime import date

import streamlit as st

from lib import (
    require_passphrase,
    is_demo,
    load_accounts,
    load_institutions,
    latest_summary_for_account,
    save_manual_entry,
)

st.set_page_config(page_title="Manual Entry", page_icon="✏️", layout="wide")
require_passphrase()

st.title("Manual Entry")

demo = is_demo()
if demo:
    # This page WRITES data, so it's the one place Demo Mode doesn't just
    # swap in sample data - it blocks entirely. save_manual_entry() also
    # no-ops on demo=True as a second layer of defense, but the real
    # protection is simply never reaching it from here.
    st.warning(
        "Manual Entry is turned off in Demo Mode, since it saves real changes. "
        "Reload the page and enter the real passphrase to use it."
    )
    st.stop()

st.caption(
    "For accounts without a working statement feed - right now, that's the LPL "
    "Financial 'Shield' positions (Ascend's LPL statement archive is broken; "
    "expected to be a temporary problem, resolving as those products mature "
    "over the next few months). Pick an account, enter its current value as "
    "of a date, and save - it'll show up on Home and the Accounts Directory "
    "exactly like any statement-fed account."
)

institutions = load_institutions()
accounts = load_accounts()

if not institutions or not accounts:
    st.info("No institutions/accounts on file yet.")
    st.stop()

inst_names = sorted({i["name"] for i in institutions})
# default to LPL if it exists, since that's the motivating case
default_inst_idx = next(
    (i for i, name in enumerate(inst_names) if "LPL" in name), 0
)
institution = st.selectbox("Institution", inst_names, index=default_inst_idx)

inst_accounts = sorted(
    [a for a in accounts if a["institution"] == institution],
    key=lambda a: (a["member"], a["display_name"]),
)
if not inst_accounts:
    st.info("No accounts on file for this institution yet.")
    st.stop()

acct_labels = {a["account_key"]: f"{a['member']} - {a['display_name']} ({a['account_key']})" for a in inst_accounts}
account_key = st.selectbox("Account", options=list(acct_labels.keys()), format_func=lambda k: acct_labels[k])
account = next(a for a in inst_accounts if a["account_key"] == account_key)

prior = latest_summary_for_account(account_key)
if prior:
    st.caption(
        f"Last entry on file: **{prior['statement_date']}** — "
        f"**${prior['ending_balance']:,.2f}** (source: {prior['source_file']})"
    )
else:
    st.caption("No entries on file yet for this account - this will be the first one.")

# sticky default: the data-source text carries forward from this account's
# last entry until Allen types something different, so he isn't retyping
# the same label every time he comes back to update a value
default_source = prior["source_file"] if prior else "Manual entry"

with st.form("manual_entry_form", clear_on_submit=False):
    col1, col2 = st.columns(2)
    as_of_date = col1.date_input("As of date", value=date.today())
    ending_balance = col2.number_input(
        "Current value ($)", value=float(prior["ending_balance"]) if prior else 0.0,
        step=0.01, format="%.2f",
    )
    data_source = st.text_input("Data source", value=default_source)

    with st.expander("Deposits / withdrawals this period (optional - leave at $0 for a pure value update)"):
        c1, c2 = st.columns(2)
        deposits = c1.number_input("Deposits", value=0.0, step=0.01, format="%.2f", min_value=0.0)
        withdrawals = c2.number_input("Withdrawals", value=0.0, step=0.01, format="%.2f", min_value=0.0)

    submitted = st.form_submit_button("Save entry")

if submitted:
    save_manual_entry(
        account_key=account_key,
        statement_date=as_of_date,
        ending_balance=ending_balance,
        source_file=data_source,
        total_deposits=deposits,
        total_withdrawals=withdrawals,
    )
    st.success(f"Saved: {acct_labels[account_key]} — {as_of_date.isoformat()} — ${ending_balance:,.2f}")
    st.rerun()
