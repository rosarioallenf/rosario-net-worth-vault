"""Accounts Directory - the survivor-facing page: which institutions hold
money, how to contact them, and which accounts exist - without ever showing
a full account number (those stay in LastPass Emergency Access, on purpose).
"""
import pandas as pd
import streamlit as st

from lib import require_passphrase, load_accounts, load_institutions

st.set_page_config(page_title="Accounts Directory", page_icon="\U0001F4C7", layout="wide")
require_passphrase()

st.title("Accounts Directory")
st.caption(
    "Full account numbers are intentionally NOT stored here - see LastPass "
    "Emergency Access for those. This page is the 'where do we even have "
    "money' map."
)

institutions = load_institutions()
accounts = load_accounts()

if not institutions:
    st.info("No institutions on file yet.")
    st.stop()

inst_by_name = {i["name"]: i for i in institutions}
# order institutions by how many accounts they hold, most first, so the
# ones Allen visits most often sort near the top of the dropdown
inst_names = sorted(
    inst_by_name.keys(),
    key=lambda n: -sum(1 for a in accounts if a["institution"] == n),
)
institution = st.selectbox("Institution", inst_names)
inst = inst_by_name[institution]

st.subheader(inst["name"])
cols = st.columns(3)
cols[0].write(f"**Phone:** {inst.get('phone') or '—'}")
cols[1].write(f"**Member service email:** {inst.get('member_service_email') or '—'}")
cols[2].write(f"**Mailing address:** {inst.get('mailing_address') or '—'}")
if inst.get("website"):
    st.write(f"**Website:** {inst['website']}")
if inst.get("notes"):
    st.write(f"**Notes:** {inst['notes']}")

inst_accounts = [a for a in accounts if a["institution"] == inst["name"]]
df = pd.DataFrame([{
    "Member": a["member"],
    "Joint owner": a.get("joint_owner") or "",
    "Account": a["display_name"],
    "Type": a["account_type"],
    "Last 4": a.get("last4") or "(see LastPass)",
    "Opened (first statement on file)": a["first_statement_date"],
    "Status": "Closed" if a["last_ending_balance"] in (0, 0.0) and a["account_type"] == "cd" else "Open",
} for a in inst_accounts])
st.dataframe(df, hide_index=True, width="stretch")
st.caption(f"{len(inst_accounts)} account(s) at {inst['name']}")
