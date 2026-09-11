"""Accounts Directory - the survivor-facing page: which institutions hold
money, how to contact them, and which accounts exist - without ever showing
a full account number (those stay in LastPass Emergency Access, on purpose).

Every institution is listed as its own collapsible section, all on one
screen (per Allen's own redesign request, 2026-09-11) - so you can scan all
of them at a glance and only expand the ones you actually need right now,
rather than picking one at a time from a dropdown.
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
    "money' map. Click an institution to expand its contact info and accounts."
)

institutions = load_institutions()
accounts = load_accounts()

if not institutions:
    st.info("No institutions on file yet.")
    st.stop()

inst_by_name = {i["name"]: i for i in institutions}
accounts_by_inst = {}
for a in accounts:
    accounts_by_inst.setdefault(a["institution"], []).append(a)

# order institutions by how many accounts they hold, most first, so the
# ones Allen visits most often sort near the top of the page
inst_names = sorted(
    inst_by_name.keys(),
    key=lambda n: -len(accounts_by_inst.get(n, [])),
)

member_names_present = sorted({a.get("member") for a in accounts if a.get("member")})
member_filter = st.selectbox("Member (optional filter)", ["All members"] + member_names_present)

st.caption(f"{len(inst_names)} institution(s) on file")

for name in inst_names:
    inst = inst_by_name[name]
    inst_accounts = accounts_by_inst.get(name, [])
    if member_filter != "All members":
        inst_accounts = [a for a in inst_accounts if a.get("member") == member_filter]
        if not inst_accounts:
            # this institution has no accounts for the selected member -
            # skip it entirely rather than showing an empty expander
            continue

    with st.expander(f"**{name}**  —  {len(inst_accounts)} account(s)"):
        cols = st.columns(3)
        cols[0].write(f"**Phone:** {inst.get('phone') or '—'}")
        cols[1].write(f"**Member service email:** {inst.get('member_service_email') or '—'}")
        cols[2].write(f"**Mailing address:** {inst.get('mailing_address') or '—'}")
        if inst.get("website"):
            st.write(f"**Website:** {inst['website']}")
        if inst.get("notes"):
            st.write(f"**Notes:** {inst['notes']}")

        df = pd.DataFrame([{
            "Member": a["member"],
            "Joint owner": a.get("joint_owner") or "",
            "Account": a["display_name"],
            "Type": a["account_type"],
            "Last 4": a.get("last4") or "(see LastPass)",
            "Opened (first statement on file)": a["first_statement_date"],
            "Status": "Closed" if a["last_ending_balance"] in (0, 0.0) and a["account_type"] == "cd" else "Open",
        } for a in sorted(inst_accounts, key=lambda a: (a["member"], a["display_name"]))])
        st.dataframe(df, hide_index=True, width="stretch")
