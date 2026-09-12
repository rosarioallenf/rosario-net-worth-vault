"""Shared helpers for the Rosario Net Worth Vault Streamlit app."""
from datetime import date
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
        banner_col, exit_col = st.columns([5, 1])
        banner_col.info(
            "🔍 **Demo Mode** — you're viewing sample data, not Allen and Maria's real "
            "numbers. Reload the page and enter the real passphrase to see actual data."
        )
        if exit_col.button("Exit demo"):
            st.session_state["demo_mode"] = False
            st.rerun()
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
