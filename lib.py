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
