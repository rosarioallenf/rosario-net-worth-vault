"""Shared helpers for the Rosario Net Worth Vault Streamlit app."""
from datetime import date
from dateutil.relativedelta import relativedelta
import streamlit as st
from supabase import create_client


def require_passphrase():
    """Gate every page behind one shared passphrase. Call this as the first
    line of every page script. Stops the script (shows a login box instead
    of the page content) until the correct passphrase has been entered once
    per browser session."""
    if st.session_state.get("authed"):
        return
    st.title("Rosario Net Worth Vault")
    pw = st.text_input("Passphrase", type="password")
    if st.button("Enter") or pw:
        if pw == st.secrets["APP_PASSPHRASE"]:
            st.session_state["authed"] = True
            st.rerun()
        elif pw:
            st.error("Incorrect passphrase.")
    st.stop()


@st.cache_resource
def get_client():
    """Supabase client using the service_role key - this key bypasses Row
    Level Security, which is intentional here: RLS is what keeps the
    project's public anon key from exposing any data if it ever leaked, and
    this app is the one trusted place that's meant to see everything. Never
    put the service_role key anywhere but Streamlit secrets."""
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_SERVICE_KEY"])


@st.cache_data(ttl=300)
def load_accounts():
    client = get_client()
    resp = client.table("accounts").select("*").order("account_key").execute()
    return resp.data


@st.cache_data(ttl=300)
def load_institutions():
    client = get_client()
    resp = client.table("institutions").select("*").execute()
    return resp.data


@st.cache_data(ttl=300)
def load_monthly_summaries():
    client = get_client()
    resp = client.table("account_monthly_summaries").select("*").execute()
    return resp.data


@st.cache_data(ttl=300)
def load_transactions(account_key=None):
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


def latest_summary_for_account(account_key):
    """Most recent account_monthly_summaries row on file for one account (by
    statement_date), or None if it has no history yet. Bypasses the cached
    load_monthly_summaries() so it always reflects entries saved moments ago
    (e.g. by the Manual Entry page) without waiting on the 5-minute cache."""
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
                       total_deposits=0.0, total_withdrawals=0.0, dividends_paid=0.0):
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
    in sync too."""
    client = get_client()
    prior = latest_summary_for_account(account_key)
    beginning_balance = prior["ending_balance"] if prior else None

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
