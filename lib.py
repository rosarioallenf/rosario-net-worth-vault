"""Shared helpers for the Rosario Net Worth Vault Streamlit app."""
import io
from datetime import date

import pandas as pd
from dateutil.relativedelta import relativedelta
import streamlit as st
from supabase import create_client


def require_passphrase():
    """Gate every page behind one shared passphrase - OR let a visitor
    without the passphrase view a fixed, clearly-fake sample dataset instead
    (built 2026-09-11 so Allen can show family, e.g. Pratixa, what the app
    looks like/does without ever exposing his and Maria's real numbers).
    Call this as the first line of every page script."""
    if st.session_state.get("authed"):
        # Deliberate way back to the login/demo choice screen - without this,
        # once authed=True there was no way to reach Demo Mode again in the
        # same browser tab except a brand-new incognito session (found via
        # Allen's bug report 2026-09-12: he clicked "View demo" but the app
        # just kept showing his real numbers, because this branch returns
        # before demo_mode is ever checked).
        with st.sidebar:
            if st.button("Log out"):
                st.session_state.clear()
                st.rerun()
        return

    if st.session_state.get("demo_mode"):
        # The exit control now lives in the sidebar, matching the "Log out"
        # button in the authed branch above - not crammed into a thin column
        # next to the banner, which is where it got visually lost/overlapped
        # by Streamlit Cloud's own floating toolbar (Allen's report,
        # 2026-09-12: "no logout button" + "screen cut off at top" turned out
        # to be the same underlying layout issue).
        with st.sidebar:
            if st.button("Exit demo"):
                st.session_state["demo_mode"] = False
                st.rerun()
        st.info(
            "🔍 **Demo Mode** — you're viewing sample data, not Allen and Maria's real "
            "numbers. Reload the page and enter the real passphrase to see actual data."
        )
        return

    st.title("Rosario Net Worth Vault")
    # The passphrase field + its submit live inside their own st.form. This
    # matters: previously "Enter" was checked with `button("Enter") or pw`,
    # which went true any time the passphrase field simply HELD TEXT - e.g.
    # from a browser auto-filling a saved password into a password-type
    # field - regardless of which button was actually clicked. That let a
    # click on "View demo" get silently intercepted and logged in for real
    # instead (found via Allen's bug report 2026-09-12: choosing demo kept
    # showing his real numbers, even right after logging out). A st.form's
    # submit flag is only ever true from that form's own submit button being
    # pressed, never from a field merely being non-empty, so it can no
    # longer cross-talk with the separate "View demo" button below.
    with st.form("passphrase_form"):
        pw = st.text_input("Passphrase", type="password")
        submitted = st.form_submit_button("Enter")
    if submitted:
        if pw == st.secrets["APP_PASSPHRASE"]:
            st.session_state["authed"] = True
            st.rerun()
        else:
            st.error("Incorrect passphrase.")
    st.caption("Don't have the passphrase? You can still look around with sample data.")
    if st.button("View demo (sample data, no real numbers)"):
        st.session_state["demo_mode"] = True
        st.rerun()
    st.stop()


def is_demo():
    """True once a visitor has chosen "View demo" instead of the real
    passphrase. Pass this into every load_*/save_* call below, every time -
    each one takes an explicit `demo` argument (rather than checking session
    state internally) specifically so Streamlit's data cache keys real and
    demo results separately. Without that, a passphrase-less visitor could
    end up being served Allen's real data straight out of the cache just
    because someone else's authenticated session populated it first."""
    return bool(st.session_state.get("demo_mode"))


def get_client():
    """Supabase client using the service_role key - this key bypasses Row
    Level Security, which is intentional here: RLS is what keeps the
    project's public anon key from exposing any data if it ever leaked, and
    this app is the one trusted place that's meant to see everything. Never
    put the service_role key anywhere but Streamlit secrets.

    Hard circuit breaker, independent of every loader's own demo=True/False
    argument: this is the ONE function that actually talks to the real
    database, so if Demo Mode is active in session state, refuse outright -
    loudly, as a crash, rather than quietly handing back real data. This is
    what catches it if some page ever forgets to pass demo=is_demo() through
    correctly (a stale unpasted file, a copy-paste slip, a future edit that
    misses a call site) - the failure becomes an error on screen instead of
    Allen's real numbers appearing where sample data should be.

    This check deliberately sits OUTSIDE the cached part (_get_real_client,
    just below): st.cache_resource only re-runs a function's body on its
    very first call and hands back the same cached object every time after
    that - so if the check lived inside the cached function, it would only
    ever fire once, the first time this is called anywhere in the app. Once
    any real (non-demo) visit had cached a connection, a later demo-mode
    call would just receive that cached real client straight from cache,
    silently, with the safety check never re-executing at all. Keeping the
    check here, outside the cache, means it runs on every single call."""
    if st.session_state.get("demo_mode"):
        raise RuntimeError(
            "Refused to connect to the real database while Demo Mode is active. "
            "This should never happen - it means some page tried to load real "
            "data without passing demo=True through correctly. Reload the page "
            "(this resets Demo Mode) and, if this keeps happening, re-paste all "
            "of lib.py and every file under pages/ - one of them is likely an "
            "older version missing the demo-mode support."
        )
    return _get_real_client()


@st.cache_resource
def _get_real_client():
    """The actual (expensive) connection setup - this part is fine to
    cache, since by the time it's called get_client() has already confirmed
    Demo Mode is not active for this call."""
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_SERVICE_KEY"])


# ---------------------------------------------------------------------------
# Demo-mode sample data - entirely hand-written fiction, never derived from
# or connected to the real Supabase tables in any way. Two made-up members
# ("Sam" and "Jordan") and institutions clearly labeled "Sample ___" so
# nothing here could be mistaken for Allen and Maria's real accounts. Covers
# a representative spread of account types (checking/savings/CD, credit
# card, brokerage, Roth IRA, life insurance, real estate, vehicle) so a
# visitor without the passphrase can see the full shape of what the app
# does, end to end.
# ---------------------------------------------------------------------------
DEMO_INSTITUTIONS = [
    {"name": "Sample Credit Union", "phone": "555-0100", "website": "example.com",
     "mailing_address": "123 Sample St, Anytown, ST 00000", "member_service_email": None,
     "notes": "Demo data - not a real institution."},
    {"name": "Sample Brokerage", "phone": "555-0101", "website": "example.com",
     "mailing_address": None, "member_service_email": None,
     "notes": "Demo data - not a real institution."},
    {"name": "Sample Insurance Co", "phone": "555-0102", "website": None,
     "mailing_address": None, "member_service_email": None,
     "notes": "Demo data - not a real institution."},
    {"name": "Sample Card Co", "phone": "555-0103", "website": None,
     "mailing_address": None, "member_service_email": None,
     "notes": "Demo data - not a real institution."},
    {"name": "Real Estate (Sample)", "phone": None, "website": None,
     "mailing_address": None, "member_service_email": None,
     "notes": "Demo data - not a real institution, just a grouping like the real vault uses."},
    {"name": "Vehicles (Sample)", "phone": None, "website": None,
     "mailing_address": None, "member_service_email": None,
     "notes": "Demo data - not a real institution, just a grouping like the real vault uses."},
]

DEMO_ACCOUNTS = [
    {"account_key": "demo-chk-1", "external_id": "1001", "institution": "Sample Credit Union",
     "account_type": "checking", "display_name": "Everyday Checking", "member": "Sam",
     "joint_owner": "Jordan", "first_statement_date": "2024-01-31", "last_statement_date": "2026-08-31",
     "last_ending_balance": 8450.00, "last4": "1001", "notes": "Demo data - not real."},
    {"account_key": "demo-sav-1", "external_id": "1002", "institution": "Sample Credit Union",
     "account_type": "savings", "display_name": "Emergency Savings", "member": "Sam",
     "joint_owner": "Jordan", "first_statement_date": "2024-01-31", "last_statement_date": "2026-08-31",
     "last_ending_balance": 22000.00, "last4": "1002", "notes": "Demo data - not real."},
    {"account_key": "demo-cd-1", "external_id": "1003", "institution": "Sample Credit Union",
     "account_type": "cd", "display_name": "12-Month CD", "member": "Jordan",
     "joint_owner": None, "first_statement_date": "2025-06-30", "last_statement_date": "2026-08-31",
     "last_ending_balance": 10500.00, "last4": "1003", "notes": "Demo data - not real."},
    {"account_key": "demo-brk-1", "external_id": "2001", "institution": "Sample Brokerage",
     "account_type": "investment", "display_name": "Joint Brokerage Account", "member": "Sam",
     "joint_owner": "Jordan", "first_statement_date": "2022-03-31", "last_statement_date": "2026-08-31",
     "last_ending_balance": 145000.00, "last4": "2001", "notes": "Demo data - not real."},
    {"account_key": "demo-ira-1", "external_id": "2002", "institution": "Sample Brokerage",
     "account_type": "roth_ira", "display_name": "Sam's Roth IRA", "member": "Sam",
     "joint_owner": None, "first_statement_date": "2021-12-31", "last_statement_date": "2026-08-31",
     "last_ending_balance": 38000.00, "last4": "2002", "notes": "Demo data - not real."},
    {"account_key": "demo-card-1", "external_id": "3001", "institution": "Sample Card Co",
     "account_type": "credit_card", "display_name": "Rewards Visa", "member": "Jordan",
     "joint_owner": None, "first_statement_date": "2023-05-31", "last_statement_date": "2026-08-31",
     "last_ending_balance": -1250.00, "last4": "3001",
     "notes": "Demo data - not real. Negative balance = amount owed, same convention as the real vault."},
    {"account_key": "demo-life-1", "external_id": "4001", "institution": "Sample Insurance Co",
     "account_type": "life_insurance", "display_name": "Indexed Universal Life Policy", "member": "Jordan",
     "joint_owner": None, "first_statement_date": "2022-07-31", "last_statement_date": "2026-07-31",
     "last_ending_balance": 61000.00, "last4": "4001", "notes": "Demo data - not real."},
    {"account_key": "demo-home-1", "external_id": "5001", "institution": "Real Estate (Sample)",
     "account_type": "real_estate", "display_name": "Primary Home", "member": "Sam",
     "joint_owner": "Jordan", "first_statement_date": "2026-01-01", "last_statement_date": "2026-01-01",
     "last_ending_balance": 425000.00, "last4": "5001", "notes": "Demo data - not real."},
    {"account_key": "demo-car-1", "external_id": "6001", "institution": "Vehicles (Sample)",
     "account_type": "vehicle", "display_name": "Family SUV", "member": "Jordan",
     "joint_owner": "Sam", "first_statement_date": "2026-01-01", "last_statement_date": "2026-01-01",
     "last_ending_balance": 28000.00, "last4": "6001", "notes": "Demo data - not real."},
]

DEMO_SUMMARIES = [
    # A year-ago + latest snapshot per account - just enough for Home's
    # "change since last update" / "change from a year ago" math to have
    # something real to compute against.
    {"account_key": "demo-chk-1", "statement_date": "2025-08-31", "beginning_balance": 7900.00,
     "total_deposits": 500.0, "total_withdrawals": 0.0, "ending_balance": 8100.00,
     "dividends_paid": 0.0, "source_file": "demo"},
    {"account_key": "demo-chk-1", "statement_date": "2026-08-31", "beginning_balance": 8100.00,
     "total_deposits": 350.0, "total_withdrawals": 0.0, "ending_balance": 8450.00,
     "dividends_paid": 0.0, "source_file": "demo"},
    {"account_key": "demo-sav-1", "statement_date": "2025-08-31", "beginning_balance": 20500.00,
     "total_deposits": 500.0, "total_withdrawals": 0.0, "ending_balance": 21000.00,
     "dividends_paid": 40.0, "source_file": "demo"},
    {"account_key": "demo-sav-1", "statement_date": "2026-08-31", "beginning_balance": 21000.00,
     "total_deposits": 950.0, "total_withdrawals": 0.0, "ending_balance": 22000.00,
     "dividends_paid": 55.0, "source_file": "demo"},
    {"account_key": "demo-cd-1", "statement_date": "2026-08-31", "beginning_balance": 10000.00,
     "total_deposits": 0.0, "total_withdrawals": 0.0, "ending_balance": 10500.00,
     "dividends_paid": 500.0, "source_file": "demo"},
    {"account_key": "demo-brk-1", "statement_date": "2025-08-31", "beginning_balance": 118000.00,
     "total_deposits": 0.0, "total_withdrawals": 0.0, "ending_balance": 124000.00,
     "dividends_paid": 900.0, "source_file": "demo"},
    {"account_key": "demo-brk-1", "statement_date": "2026-08-31", "beginning_balance": 124000.00,
     "total_deposits": 0.0, "total_withdrawals": 0.0, "ending_balance": 145000.00,
     "dividends_paid": 1100.0, "source_file": "demo"},
    {"account_key": "demo-ira-1", "statement_date": "2025-08-31", "beginning_balance": 30000.00,
     "total_deposits": 6500.0, "total_withdrawals": 0.0, "ending_balance": 34000.00,
     "dividends_paid": 0.0, "source_file": "demo"},
    {"account_key": "demo-ira-1", "statement_date": "2026-08-31", "beginning_balance": 34000.00,
     "total_deposits": 7000.0, "total_withdrawals": 0.0, "ending_balance": 38000.00,
     "dividends_paid": 0.0, "source_file": "demo"},
    {"account_key": "demo-card-1", "statement_date": "2025-08-31", "beginning_balance": -900.00,
     "total_deposits": 0.0, "total_withdrawals": 0.0, "ending_balance": -1050.00,
     "dividends_paid": 0.0, "source_file": "demo"},
    {"account_key": "demo-card-1", "statement_date": "2026-08-31", "beginning_balance": -1050.00,
     "total_deposits": 0.0, "total_withdrawals": 0.0, "ending_balance": -1250.00,
     "dividends_paid": 0.0, "source_file": "demo"},
    {"account_key": "demo-life-1", "statement_date": "2025-07-31", "beginning_balance": 48000.00,
     "total_deposits": 10000.0, "total_withdrawals": 0.0, "ending_balance": 52000.00,
     "dividends_paid": 1200.0, "source_file": "demo"},
    {"account_key": "demo-life-1", "statement_date": "2026-07-31", "beginning_balance": 52000.00,
     "total_deposits": 10000.0, "total_withdrawals": 0.0, "ending_balance": 61000.00,
     "dividends_paid": 1800.0, "source_file": "demo"},
    {"account_key": "demo-home-1", "statement_date": "2026-01-01", "beginning_balance": 425000.00,
     "total_deposits": 0.0, "total_withdrawals": 0.0, "ending_balance": 425000.00,
     "dividends_paid": 0.0, "source_file": "demo - estimate"},
    {"account_key": "demo-car-1", "statement_date": "2026-01-01", "beginning_balance": 28000.00,
     "total_deposits": 0.0, "total_withdrawals": 0.0, "ending_balance": 28000.00,
     "dividends_paid": 0.0, "source_file": "demo - estimate"},
]

DEMO_TRANSACTIONS = [
    {"account_key": "demo-chk-1", "statement_date": "2026-08-31", "txn_date": "2026-08-05",
     "deposit": 350.0, "withdrawal": None, "balance": 8450.00,
     "description": "Paycheck deposit (sample)", "source_file": "demo"},
    {"account_key": "demo-sav-1", "statement_date": "2026-08-31", "txn_date": "2026-08-10",
     "deposit": 950.0, "withdrawal": None, "balance": 22000.00,
     "description": "Transfer from checking (sample)", "source_file": "demo"},
    {"account_key": "demo-card-1", "statement_date": "2026-08-31", "txn_date": "2026-08-15",
     "deposit": None, "withdrawal": 200.0, "balance": -1250.00,
     "description": "Sample grocery purchase", "source_file": "demo"},
    {"account_key": "demo-ira-1", "statement_date": "2026-08-31", "txn_date": "2026-01-15",
     "deposit": 7000.0, "withdrawal": None, "balance": 38000.00,
     "description": "Annual Roth contribution (sample)", "source_file": "demo"},
]


@st.cache_data(ttl=300)
def load_accounts(demo=False):
    if demo:
        return DEMO_ACCOUNTS
    client = get_client()
    resp = client.table("accounts").select("*").order("account_key").execute()
    return resp.data


@st.cache_data(ttl=300)
def load_institutions(demo=False):
    if demo:
        return DEMO_INSTITUTIONS
    client = get_client()
    resp = client.table("institutions").select("*").execute()
    return resp.data


@st.cache_data(ttl=300)
def load_monthly_summaries(demo=False):
    if demo:
        return DEMO_SUMMARIES
    client = get_client()
    resp = client.table("account_monthly_summaries").select("*").execute()
    return resp.data


@st.cache_data(ttl=300)
def load_transactions(account_key=None, demo=False):
    if demo:
        rows = DEMO_TRANSACTIONS
        if account_key:
            rows = [r for r in rows if r["account_key"] == account_key]
        return sorted(rows, key=lambda r: r["txn_date"], reverse=True)
    client = get_client()
    q = client.table("transactions").select("*")
    if account_key:
        q = q.eq("account_key", account_key)
    resp = q.order("txn_date", desc=True).execute()
    return resp.data


# ---------------------------------------------------------------------------
# CSV statement import (built 2026-09-13, starting with Chase - other
# institutions get added the same way: one detector entry + one parser
# function, below). Each institution's downloadable CSV has its own fixed
# column layout, so rather than one generic parser this is a small registry
# of per-institution profiles, matched by which columns are actually present
# in the uploaded file.
#
# The core design point Allen and Claude worked through together: a bank
# account's CSV (Chase checking/savings) already includes a running Balance
# column - Chase gives us the actual bank-stated balance directly, so no
# math is needed, same reliability as typing in a number from a PDF
# statement. A credit card's CSV has no such column, since the true
# statement balance depends on things (interest, fees) outside the raw
# transaction list - so for cards, the new ending balance has to be
# computed by rolling forward from whatever the account's last confirmed
# balance already was. Handily, Chase's own signed Amount column (negative
# for a purchase, positive for a payment or return) lines up exactly with
# this vault's own "negative ending_balance = amount owed" convention for
# credit cards, so the roll-forward is just plain addition - no sign-
# flipping by transaction Type needed.
# ---------------------------------------------------------------------------

CHASE_BANK_CSV_COLUMNS = {"Details", "Posting Date", "Description", "Amount", "Type", "Balance"}
CHASE_CARD_CSV_COLUMNS = {"Transaction Date", "Post Date", "Description", "Type", "Amount"}
ASCEND_BANK_CSV_COLUMNS = {"Account ID", "Transaction ID", "Date", "Description", "Amount", "Balance"}


def detect_csv_profile(df):
    """Given a freshly-read CSV as a DataFrame, return which known
    institution/account-type profile it matches ('chase_bank', 'chase_card',
    'ascend_bank'), or None if it doesn't match anything built yet. Matching
    is by column presence, not file name, since Allen renames/downloads
    these however his browser or the bank names them."""
    cols = set(df.columns)
    if CHASE_BANK_CSV_COLUMNS.issubset(cols):
        return "chase_bank"
    if CHASE_CARD_CSV_COLUMNS.issubset(cols):
        return "chase_card"
    if ASCEND_BANK_CSV_COLUMNS.issubset(cols):
        return "ascend_bank"
    return None


def parse_chase_bank_csv(raw_bytes):
    """Parse a Chase checking/savings 'Download activity' CSV. Returns
    (transactions, ending_balance, statement_date):
      - transactions: list of dicts (txn_date, description, deposit,
        withdrawal, balance), oldest first.
      - ending_balance: taken directly from the CSV's own Balance column on
        the most recent (max Posting Date) row - Chase already gives us the
        real bank-stated balance, so this isn't computed from the
        transactions at all.
      - statement_date: that same most recent Posting Date.
    """
    # index_col=False: Chase's own bank-CSV export ends every data row with a
    # trailing ",," (one more field than the header row has), which pandas
    # would otherwise interpret as "this file has an implicit index column"
    # and silently shift every named column one position off from the real
    # data. index_col=False tells pandas not to do that guess.
    df = pd.read_csv(io.BytesIO(raw_bytes), index_col=False)
    df["Posting Date"] = pd.to_datetime(df["Posting Date"], format="%m/%d/%Y").dt.date
    df = df.sort_values("Posting Date")
    txns = []
    for _, row in df.iterrows():
        amount = float(row["Amount"])
        txns.append({
            "txn_date": row["Posting Date"].isoformat(),
            "description": str(row["Description"]).strip(),
            "deposit": amount if amount > 0 else None,
            "withdrawal": round(abs(amount), 2) if amount < 0 else None,
            "balance": round(float(row["Balance"]), 2),
        })
    last_row = df.iloc[-1]
    return txns, round(float(last_row["Balance"]), 2), last_row["Posting Date"].isoformat()


def _ascend_money(val):
    """Ascend's own CSV export writes Amount/Balance as literal dollar
    strings - '$47.05', '-$262.62' - rather than plain numbers. Strip the
    '$' and any thousands comma, then let float() handle the sign (Ascend
    always puts the '-' before the '$', which float() parses fine once the
    '$' itself is gone)."""
    return float(str(val).replace("$", "").replace(",", ""))


def parse_ascend_bank_csv(raw_bytes):
    """Parse an Ascend Federal Credit Union 'Transactions' CSV export -
    checking, savings, or money market, anything with Ascend's own per-row
    running balance. Same shape and same authoritative-balance convention
    as parse_chase_bank_csv: Ascend already gives its own real balance on
    every row, so the ending balance is read straight off the last row
    rather than computed.

    Folds the optional Category and Check Number columns into the
    description, same convention as Chase's optional Category/Card columns.
    'Tags' and 'Transaction ID' are dropped - Tags is blank in every sample
    row Allen's Ascend account has produced, and Transaction ID is Ascend's
    own internal reference with nowhere to live in this vault's schema.

    Ascend's own 'Account ID' column (e.g. '3386320-S0007') identifies
    which physical sub-account a file belongs to, but isn't used to
    auto-select the account here - same as Chase, Allen picks the account
    from the dropdown above and the import page shows this column's value
    in the preview so he can visually confirm it matches before importing.

    Returns (transactions, ending_balance, statement_date) - same shape as
    parse_chase_bank_csv, plus each transaction dict also carries
    'source_account_id' (the file's own Account ID for that row) purely for
    the page's preview table - commit_csv_import doesn't write it anywhere,
    since the transactions table has no column for it."""
    df = pd.read_csv(io.BytesIO(raw_bytes), index_col=False)
    df["Date"] = pd.to_datetime(df["Date"], format="%m/%d/%y").dt.date
    df = df.sort_values("Date")
    txns = []
    for _, row in df.iterrows():
        amount = _ascend_money(row["Amount"])
        description = str(row["Description"]).strip()
        category = row.get("Category")
        if pd.notna(category) and str(category).strip():
            description = f"{description} ({category})"
        check_no = row.get("Check Number")
        if pd.notna(check_no):
            description = f"{description} [check #{int(check_no)}]"
        txns.append({
            "txn_date": row["Date"].isoformat(),
            "description": description,
            "deposit": amount if amount > 0 else None,
            "withdrawal": round(abs(amount), 2) if amount < 0 else None,
            "balance": round(_ascend_money(row["Balance"]), 2),
            "source_account_id": row.get("Account ID"),
        })
    last_row = df.iloc[-1]
    return txns, round(_ascend_money(last_row["Balance"]), 2), last_row["Date"].isoformat()


def parse_chase_creditcard_csv(raw_bytes):
    """Parse a Chase credit card 'Download activity' CSV into a flat list of
    transactions - txn_date, description, deposit/withdrawal. No balance and
    no ending-balance total here: unlike the bank CSV, Chase's credit-card
    export has no running-balance column, AND a fresh "download activity"
    file routinely includes transactions from prior months that the vault
    already has on file, mixed in alongside the genuinely new ones (Chase
    doesn't limit the export to "since your last download"). Rolling a
    balance forward through every row in the file - including that stale
    overlap - would double-count it and produce a wrong total.

    Uses 'Transaction Date' (when the purchase happened) as this vault's
    txn_date, not 'Post Date' (when Chase settled it) - the truer "the
    transaction's own date" per this vault's own schema comment, though it
    does mean a card's txn_date and a bank account's txn_date aren't quite
    the same kind of date (posted vs. incurred) - worth knowing if the two
    are ever compared side by side.

    Folds the optional Category and Card columns into the description
    (rather than adding new database columns for them) - Category shows up
    when Chase provides it, Card only shows up when more than one physical
    card exists on the account (e.g., an authorized user's card).

    Call find_new_transactions() on the result first to drop the stale
    overlap, THEN roll_forward_balance() on just the new subset to get a
    correct suggested ending balance - never roll forward over this
    function's raw output directly."""
    # index_col=False for the same reason as parse_chase_bank_csv above -
    # harmless here even on files that don't have the extra trailing field.
    df = pd.read_csv(io.BytesIO(raw_bytes), index_col=False)
    df["Transaction Date"] = pd.to_datetime(df["Transaction Date"], format="%m/%d/%Y").dt.date
    df = df.sort_values("Transaction Date")
    txns = []
    for _, row in df.iterrows():
        amount = float(row["Amount"])
        description = str(row["Description"]).strip()
        category = row.get("Category")
        if pd.notna(category) and str(category).strip():
            description = f"{description} ({category})"
        card = row.get("Card")
        if pd.notna(card):
            description = f"{description} [card ending {card}]"
        txns.append({
            "txn_date": row["Transaction Date"].isoformat(),
            "description": description,
            "deposit": amount if amount > 0 else None,
            "withdrawal": round(abs(amount), 2) if amount < 0 else None,
        })
    statement_date = df["Transaction Date"].max().isoformat()
    return txns, statement_date


def roll_forward_balance(prior_ending_balance, new_txns):
    """Compute a suggested ending balance for an import with no authoritative
    balance column (credit cards): prior known balance plus the sum of every
    NEW (already deduped via find_new_transactions) transaction's signed
    amount, in date order - a Sale is negative (increases what's owed), a
    Payment or Return is positive (reduces it), which already matches this
    vault's own "negative ending_balance = amount owed" convention with no
    sign-flipping needed.

    Also stamps each transaction dict's own 'balance' field with its running
    total along the way, for the transactions table's audit trail. Returns
    (new_txns_sorted_with_balance, computed_ending_balance) - the caller
    shows computed_ending_balance in an EDITABLE field so Allen can override
    it with a real known figure before confirming the import.

    IMPORTANT: only ever call this on the post-dedup new_txns list, never on
    parse_chase_creditcard_csv's raw output - see that function's docstring
    for why."""
    ordered = sorted(new_txns, key=lambda t: t["txn_date"])
    running = prior_ending_balance
    for t in ordered:
        amount = t["deposit"] if t["deposit"] is not None else -(t["withdrawal"] or 0)
        running += amount
        t["balance"] = round(running, 2)
    return ordered, round(running, 2)


def find_new_transactions(account_key, parsed_txns, demo=False):
    """Split freshly parsed transactions into (new, already_on_file) two
    different ways, since a transaction can be "already covered" without
    being an exact text match:

    1. Textual fingerprint - matching on (txn_date, description, signed
       amount) against what's already stored for this account. This isn't a
       perfect fingerprint - two genuinely separate but identical-looking
       transactions (same merchant, same day, same amount) would look like
       one duplicate - which is exactly why the import page shows every
       matched row explicitly rather than just printing a count, so Allen
       can catch that rare case before confirming rather than have it
       silently dropped.

    2. Statement-coverage boundary - ANY transaction dated on or before the
       account's own last_statement_date is treated as already covered,
       full stop, regardless of whether its exact wording matches anything
       already on file. This matters whenever an account's history came
       from more than one source - e.g. Ascend statements loaded from PDFs
       for years, now switching to CSV exports going forward: the same
       real transaction gets described differently by the two sources
       (the PDF parser writes 'Deposit ACH Acorns Invest | TYPE: ...',
       Ascend's own CSV export writes 'Deposit ACH Acorns Invest TYPE: ...
       Entry Class Code: PPD' for that identical transaction), so a purely
       textual fingerprint would miss the overlap entirely and silently
       double up a whole month of transactions. Statements are complete,
       non-overlapping monthly records, so this boundary is a hard
       guarantee, not a heuristic - if the account is already covered
       through a given date, nothing dated at or before it is ever new."""
    existing = load_transactions(account_key=account_key, demo=demo)
    existing_keys = set()
    for t in existing:
        amt = t["deposit"] if t.get("deposit") is not None else -(t.get("withdrawal") or 0)
        existing_keys.add((t["txn_date"], (t.get("description") or "").strip(), round(float(amt), 2)))

    accounts = load_accounts(demo=demo)
    acct = next((a for a in accounts if a["account_key"] == account_key), None)
    last_statement_date = acct.get("last_statement_date") if acct else None

    new_txns, dup_txns = [], []
    for t in parsed_txns:
        amt = t["deposit"] if t["deposit"] is not None else -(t["withdrawal"] or 0)
        key = (t["txn_date"], t["description"], round(float(amt), 2))
        already_covered_by_prior_statement = (
            last_statement_date is not None and t["txn_date"] <= last_statement_date
        )
        (dup_txns if (key in existing_keys or already_covered_by_prior_statement) else new_txns).append(t)
    return new_txns, dup_txns


def check_for_gap(account_key, parsed_txns, demo=False):
    """Warn if the earliest transaction in a fresh upload starts more than a
    day after this account's current last_statement_date - the opposite
    risk from duplicates: a downloaded date range that didn't reach back far
    enough would silently under-count activity rather than over-count it.
    Returns the gap size in days, or None if there's no account on file yet,
    no transactions to check, or no gap."""
    accounts = load_accounts(demo=demo)
    acct = next((a for a in accounts if a["account_key"] == account_key), None)
    if not acct or not acct.get("last_statement_date") or not parsed_txns:
        return None
    last_on_file = date.fromisoformat(acct["last_statement_date"])
    earliest_new = min(date.fromisoformat(t["txn_date"]) for t in parsed_txns)
    gap_days = (earliest_new - last_on_file).days
    return gap_days if gap_days > 1 else None


def commit_csv_import(account_key, statement_date, ending_balance, new_txns, source_file, demo=False):
    """Write one CSV-import batch: every row in new_txns (already filtered
    down to the non-duplicate ones by the page before calling this) into
    `transactions`, one account_monthly_summaries row summarizing the batch,
    and a refresh of the account's own last_statement_date/
    last_ending_balance - same end result as save_manual_entry(), just
    covering a batch of transactions instead of one typed-in balance.

    demo=True no-ops immediately, same as save_manual_entry - this is a
    write path and Demo Mode never writes, and the import UI itself never
    even renders in Demo Mode, so this is a second layer of defense rather
    than the only guard."""
    if demo:
        return
    if not new_txns:
        return
    client = get_client()
    prior = latest_summary_for_account(account_key)
    beginning_balance = prior["ending_balance"] if prior else (ending_balance - sum(
        (t["deposit"] or 0) - (t["withdrawal"] or 0) for t in new_txns
    ))
    total_deposits = round(sum(t["deposit"] for t in new_txns if t["deposit"]), 2)
    total_withdrawals = round(sum(t["withdrawal"] for t in new_txns if t["withdrawal"]), 2)

    rows = [{
        "account_key": account_key,
        "statement_date": statement_date,
        "txn_date": t["txn_date"],
        "deposit": t["deposit"],
        "withdrawal": t["withdrawal"],
        "balance": t["balance"],
        "description": t["description"],
        "source_file": source_file,
    } for t in new_txns]
    client.table("transactions").insert(rows).execute()

    client.table("account_monthly_summaries").upsert({
        "account_key": account_key,
        "statement_date": statement_date,
        "beginning_balance": round(beginning_balance, 2),
        "total_deposits": total_deposits,
        "total_withdrawals": total_withdrawals,
        "ending_balance": round(ending_balance, 2),
        "dividends_paid": 0.0,
        "source_file": source_file,
    }, on_conflict="account_key,statement_date").execute()

    current_last = prior["statement_date"] if prior else None
    if current_last is None or statement_date >= current_last:
        client.table("accounts").update({
            "last_statement_date": statement_date,
            "last_ending_balance": round(ending_balance, 2),
        }).eq("account_key", account_key).execute()

    load_monthly_summaries.clear()
    load_accounts.clear()
    load_transactions.clear()


def nearest_statement_on_or_before(summaries_for_account, target_date):
    """Given one account's monthly summaries (each with a 'statement_date'
    string YYYY-MM-DD) and a target date, return the row with the latest
    statement_date that is <= target_date, or None."""
    candidates = [r for r in summaries_for_account if r["statement_date"] <= target_date.isoformat()]
    if not candidates:
        return None
    return max(candidates, key=lambda r: r["statement_date"])


def net_worth_as_of(all_summaries, target_date):
    """Sum each account's most recent ending_balance as of target_date
    (accounts not yet opened, or already fully closed with no statement by
    then, simply don't contribute)."""
    by_account = {}
    for row in all_summaries:
        by_account.setdefault(row["account_key"], []).append(row)
    total = 0.0
    per_account = {}
    for account_key, rows in by_account.items():
        latest = nearest_statement_on_or_before(rows, target_date)
        if latest:
            total += latest["ending_balance"]
            per_account[account_key] = latest["ending_balance"]
    return total, per_account


def a_year_ago(d: date) -> date:
    return d - relativedelta(years=1)


def latest_summary_for_account(account_key, demo=False):
    """Most recent account_monthly_summaries row on file for one account (by
    statement_date), or None if it has no history yet. Bypasses the cached
    load_monthly_summaries() so it always reflects entries saved moments ago
    (e.g. by the Manual Entry page) without waiting on the 5-minute cache.
    (In practice the Manual Entry page blocks itself entirely in Demo Mode,
    so the demo branch here is just a safety net, not the only guard.)"""
    if demo:
        candidates = [r for r in DEMO_SUMMARIES if r["account_key"] == account_key]
        return max(candidates, key=lambda r: r["statement_date"]) if candidates else None
    client = get_client()
    resp = (
        client.table("account_monthly_summaries")
        .select("*")
        .eq("account_key", account_key)
        .order("statement_date", desc=True)
        .limit(1)
        .execute()
    )
    return resp.data[0] if resp.data else None


def save_manual_entry(account_key, statement_date, ending_balance, source_file,
                       total_deposits=0.0, total_withdrawals=0.0, dividends_paid=0.0, demo=False):
    """Add (or correct) one manually-entered balance snapshot for an account
    that doesn't have a working statement feed - e.g. LPL/Ascend right now.
    beginning_balance is chained automatically from whatever the account's
    latest prior entry was (same continuity convention used everywhere else
    in this vault), so the caller never has to supply it. Upserts on
    (account_key, statement_date): re-saving the same as-of date corrects
    that entry in place rather than erroring, since a manual figure is more
    likely to need a typo fix than a PDF-derived one ever was. Also nudges
    the account's own last_statement_date/last_ending_balance forward when
    this entry is the newest one on file, so the Accounts Directory page
    (which reads those convenience fields, not the summaries table) stays
    in sync too.

    demo=True is a no-op (returns immediately, touches nothing) - Demo Mode
    is meant to be looked at, not written to, and the Manual Entry page
    itself never even renders its form in Demo Mode, so this should never
    actually be reached with demo=True. Kept as a second layer of defense
    rather than relying on the page alone."""
    if demo:
        return
    client = get_client()
    prior = latest_summary_for_account(account_key)
    # for a brand-new account with no prior entry, beginning has to equal
    # ending (the table has a not-null constraint on beginning_balance, and
    # with deposits/withdrawals both 0 for this row there's nothing else it
    # could correctly be - same treatment as any account's first-ever
    # statement elsewhere in this vault)
    beginning_balance = prior["ending_balance"] if prior else ending_balance

    client.table("account_monthly_summaries").upsert({
        "account_key": account_key,
        "statement_date": statement_date.isoformat(),
        "beginning_balance": beginning_balance,
        "total_deposits": round(total_deposits, 2),
        "total_withdrawals": round(total_withdrawals, 2),
        "ending_balance": round(ending_balance, 2),
        "dividends_paid": round(dividends_paid, 2),
        "source_file": source_file,
    }, on_conflict="account_key,statement_date").execute()

    acct = client.table("accounts").select("last_statement_date").eq("account_key", account_key).execute()
    current_last = acct.data[0]["last_statement_date"] if acct.data else None
    if current_last is None or statement_date.isoformat() >= current_last:
        client.table("accounts").update({
            "last_statement_date": statement_date.isoformat(),
            "last_ending_balance": round(ending_balance, 2),
        }).eq("account_key", account_key).execute()

    load_monthly_summaries.clear()
    load_accounts.clear()
