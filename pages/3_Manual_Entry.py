"""Manual Entry - for updating any account's balance, one of three ways.

Built first for the LPL Financial "Shield" positions (LPL's statement
archive on Ascend's site is broken as of Sept 2026) as pure manual balance
entry. Extended (Sept 2026) with CSV/PDF statement import for the
high-transaction-volume accounts (Chase checking/savings/credit cards,
eventually JPM) that Allen can't afford to retype by hand every month -
folded into this same page as a mode switch, per Allen's own preference,
rather than a separate page:

  a) Manual entry of an ending balance + as-of date (original, unchanged) -
     for balance-only accounts: real estate, vehicles, LPL, Allianz, and
     Fidelity (whose own trading app already covers its transactions).
  b) Upload a CSV - for Chase bank and credit card "download activity"
     exports today; more institutions/profiles can be added to
     detect_csv_profile()/lib.py over time without changing this page.
  c) Upload a PDF - not built yet (JPM multi-account statements are next
     up after Chase CSVs are proven out); placeholder message for now.

Two-step institution -> account picker, per Allen's own suggestion, so this
scales cleanly as more accounts get added instead of one long dropdown -
shared across all three modes.
"""
import io
from datetime import date

import pandas as pd
import streamlit as st

from lib import (
    require_passphrase,
    is_demo,
    load_accounts,
    load_institutions,
    latest_summary_for_account,
    save_manual_entry,
    detect_csv_profile,
    parse_chase_bank_csv,
    parse_chase_creditcard_csv,
    find_new_transactions,
    check_for_gap,
    roll_forward_balance,
    commit_csv_import,
)

st.set_page_config(page_title="Manual Entry", page_icon="✏️", layout="wide")
require_passphrase()

st.title("Manual Entry")

demo = is_demo()
if demo:
    # This page WRITES data, so it's the one place Demo Mode doesn't just
    # swap in sample data - it blocks entirely. save_manual_entry()/
    # commit_csv_import() also no-op on demo=True as a second layer of
    # defense, but the real protection is simply never reaching them from
    # here.
    st.warning(
        "Manual Entry is turned off in Demo Mode, since it saves real changes. "
        "Reload the page and enter the real passphrase to use it."
    )
    st.stop()

st.caption(
    "Pick an account, then pick how you want to update it: type in a current "
    "value, upload a CSV of transactions, or (soon) upload a PDF statement. "
    "Whatever you save shows up on Home and the Accounts Directory exactly "
    "like any statement-fed account."
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

st.divider()
mode = st.radio(
    "How do you want to update this account?",
    ["Manual balance entry", "Upload a CSV", "Upload a PDF"],
    horizontal=True,
)

# ---------------------------------------------------------------------------
# Mode (a): manual balance entry - unchanged from the original page.
# ---------------------------------------------------------------------------
if mode == "Manual balance entry":
    # sticky default: the data-source text carries forward from this
    # account's last entry until Allen types something different, so he
    # isn't retyping the same label every time he comes back to update a
    # value
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

# ---------------------------------------------------------------------------
# Mode (b): CSV upload.
# ---------------------------------------------------------------------------
elif mode == "Upload a CSV":
    st.caption(
        "Works today for Chase checking/savings and Chase credit card "
        "'Download activity' exports. Every transaction gets archived, "
        "already-on-file rows are detected and skipped automatically, and "
        "you'll see everything before anything is saved."
    )
    uploaded = st.file_uploader("Chase CSV export", type=["csv"], key=f"csv_{account_key}")

    if uploaded is not None:
        raw = uploaded.getvalue()
        try:
            preview_df = pd.read_csv(io.BytesIO(raw), index_col=False)
        except Exception as e:
            st.error(f"Couldn't read this as a CSV: {e}")
            st.stop()

        profile = detect_csv_profile(preview_df)
        if profile is None:
            st.error(
                "Unrecognized CSV format - this doesn't match a Chase bank or "
                "Chase credit card 'Download activity' export. No columns "
                f"matched. File's columns: {list(preview_df.columns)}"
            )
            st.stop()

        if profile == "chase_bank":
            all_txns, file_ending_balance, statement_date = parse_chase_bank_csv(raw)
            authoritative_balance = True
        else:  # chase_card
            all_txns, statement_date = parse_chase_creditcard_csv(raw)
            authoritative_balance = False

        new_txns, dup_txns = find_new_transactions(account_key, all_txns, demo=demo)
        gap_days = check_for_gap(account_key, all_txns, demo=demo)

        st.write(
            f"Parsed **{len(all_txns)}** transaction(s) from this file "
            f"({'{}'.format('Chase bank/checking' if profile == 'chase_bank' else 'Chase credit card')} format), "
            f"covering through **{statement_date}**."
        )

        if gap_days:
            st.warning(
                f"This file's earliest transaction is {gap_days} day(s) after "
                f"the last statement date on file ({account.get('last_statement_date')}). "
                "That may mean this download's date range didn't reach back far "
                "enough, and some activity in between could be missing. Consider "
                "re-downloading with an earlier start date, or proceed if you "
                "know nothing happened in that window."
            )

        if dup_txns:
            st.caption(f"{len(dup_txns)} transaction(s) already on file - these will be skipped.")
            with st.expander("Show skipped (already-on-file) transactions"):
                st.dataframe(pd.DataFrame(dup_txns), hide_index=True, width="stretch")

        if not new_txns:
            st.info("Every transaction in this file is already on file - nothing new to import.")
            st.stop()

        # Compute the suggested ending balance and (for credit cards) stamp
        # a running balance onto just the new rows. Bank CSVs already carry
        # Chase's own authoritative per-row balance from parse_chase_bank_csv,
        # so there's no rolling to do there.
        if authoritative_balance:
            suggested_balance = file_ending_balance
            new_txns_final = new_txns
        else:
            prior_balance = prior["ending_balance"] if prior else float(account.get("last_ending_balance") or 0.0)
            new_txns_final, suggested_balance = roll_forward_balance(prior_balance, new_txns)
            st.caption(
                f"No balance column in this file - suggested ending balance is "
                f"computed as the last known balance (${prior_balance:,.2f}) plus "
                f"just these {len(new_txns_final)} new transaction(s). Check it "
                "against your statement and adjust below if it doesn't match."
            )

        st.write(f"**{len(new_txns_final)} new transaction(s) to import:**")
        st.dataframe(pd.DataFrame(new_txns_final), hide_index=True, width="stretch")

        with st.form(f"csv_import_form_{account_key}"):
            col1, col2 = st.columns(2)
            confirm_statement_date = col1.date_input(
                "Statement / as-of date", value=date.fromisoformat(statement_date)
            )
            confirm_ending_balance = col2.number_input(
                "Ending balance ($) - edit if it doesn't match your statement",
                value=float(suggested_balance), step=0.01, format="%.2f",
            )
            confirm_source = st.text_input("Data source", value=uploaded.name)
            confirm = st.form_submit_button(f"Import {len(new_txns_final)} transaction(s)")

        if confirm:
            commit_csv_import(
                account_key=account_key,
                statement_date=confirm_statement_date.isoformat(),
                ending_balance=confirm_ending_balance,
                new_txns=new_txns_final,
                source_file=confirm_source,
                demo=demo,
            )
            st.success(
                f"Imported {len(new_txns_final)} transaction(s) for {acct_labels[account_key]} "
                f"— {confirm_statement_date.isoformat()} — ${confirm_ending_balance:,.2f}"
            )
            st.rerun()

# ---------------------------------------------------------------------------
# Mode (c): PDF upload - not built yet.
# ---------------------------------------------------------------------------
else:
    st.info(
        "PDF statement import isn't built yet. It's next up after Chase CSVs "
        "are proven out end-to-end, starting with JPM's multi-account "
        "statement PDF. For now, use Manual balance entry or Upload a CSV."
    )
