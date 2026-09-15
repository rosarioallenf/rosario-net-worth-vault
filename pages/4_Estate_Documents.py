"""Estate Documents - an index of estate-planning documents (Revocable
Trust, will, powers of attorney, etc.) plus, optionally, a PDF COPY of each
kept in a private Supabase Storage bucket.

This is deliberately a convenience copy, never the primary record: the
signed, notarized originals stay exactly where they already are (the home
safe) - this page just tracks what exists, where the real original lives,
and optionally a PDF to glance at without digging out the folder. Nothing
here is meant to replace the original or the estate attorney's own file.

Blocks entirely in Demo Mode, same treatment as Manual Entry - unlike the
account data elsewhere in this app, there's no safe way to fake "sample"
estate documents that wouldn't be misleading, and even the real index
content (document titles, where originals are kept) is sensitive enough
that a passphrase-less visitor shouldn't see it at all.
"""
import base64

import streamlit as st

from lib import (
    require_passphrase,
    is_demo,
    load_estate_documents,
    save_estate_document_entry,
    upload_estate_document_pdf,
    download_estate_document_pdf,
    slugify_doc_key,
    ensure_estate_bucket,
)

st.set_page_config(page_title="Estate Documents", page_icon="🗂️", layout="wide")
require_passphrase()

st.title("Estate Documents")

if is_demo():
    st.warning(
        "Estate Documents is turned off in Demo Mode - even the index here "
        "(document titles, where originals are kept) is real, sensitive "
        "information. Reload the page and enter the real passphrase to use it."
    )
    st.stop()

ensure_estate_bucket()

st.caption(
    "An index of estate-planning documents and, optionally, a PDF copy of "
    "each for quick reference. This is a convenience copy only - the signed, "
    "notarized originals stay in the home safe (or with the estate attorney), "
    "never only here."
)

documents = load_estate_documents()

if not documents:
    st.info("No estate documents indexed yet - add one below.")
else:
    for doc in documents:
        with st.expander(f"**{doc['title']}**", expanded=True):
            if doc.get("description"):
                st.write(doc["description"])
            if doc.get("original_location"):
                st.caption(f"📍 Original: {doc['original_location']}")
            if doc.get("notes"):
                st.caption(doc["notes"])

            storage_path = doc.get("storage_path")
            if storage_path:
                st.caption(
                    f"PDF copy on file"
                    + (f" (uploaded {doc['uploaded_at'][:10]})" if doc.get("uploaded_at") else "")
                    + "."
                )
                try:
                    pdf_bytes = download_estate_document_pdf(storage_path)
                except Exception as e:
                    pdf_bytes = None
                    st.error(f"Couldn't load the PDF from storage: {e}")

                if pdf_bytes:
                    col1, col2 = st.columns([1, 1])
                    with col1:
                        st.download_button(
                            "Download PDF",
                            data=pdf_bytes,
                            file_name=f"{doc['doc_key']}.pdf",
                            mime="application/pdf",
                            key=f"dl_{doc['doc_key']}",
                        )
                    with st.popover("View PDF"):
                        b64 = base64.b64encode(pdf_bytes).decode()
                        st.markdown(
                            f'<iframe src="data:application/pdf;base64,{b64}" '
                            f'width="100%" height="600" style="border:none;"></iframe>',
                            unsafe_allow_html=True,
                        )

                replace_file = st.file_uploader(
                    "Replace this PDF", type=["pdf"], key=f"replace_{doc['doc_key']}"
                )
                if replace_file is not None:
                    if st.button("Save replacement", key=f"save_replace_{doc['doc_key']}"):
                        upload_estate_document_pdf(doc["doc_key"], replace_file.getvalue())
                        st.success("Replaced.")
                        st.rerun()
            else:
                st.caption("No PDF copy uploaded yet.")
                new_file = st.file_uploader(
                    "Upload a PDF copy", type=["pdf"], key=f"upload_{doc['doc_key']}"
                )
                if new_file is not None:
                    if st.button("Save PDF", key=f"save_upload_{doc['doc_key']}"):
                        upload_estate_document_pdf(doc["doc_key"], new_file.getvalue())
                        st.success("Uploaded.")
                        st.rerun()

st.divider()
st.subheader("Add a document to the index")
st.caption(
    "Add an entry for a document that isn't listed above yet (e.g. a will, "
    "a power of attorney, a healthcare directive) - a PDF copy can be added "
    "now or later."
)
with st.form("add_estate_doc_form", clear_on_submit=True):
    title = st.text_input("Title (e.g. \"Last Will and Testament\")")
    description = st.text_area("Description (optional)")
    original_location = st.text_input(
        "Where the real original lives (e.g. \"Home safe\", \"Estate attorney's file\")"
    )
    notes = st.text_input("Notes (optional)")
    submitted = st.form_submit_button("Add to index")

if submitted:
    if not title.strip():
        st.error("Title is required.")
    else:
        doc_key = slugify_doc_key(title)
        existing_keys = {d["doc_key"] for d in documents}
        if doc_key in existing_keys:
            st.error(f"An entry with key '{doc_key}' already exists - edit it above instead.")
        else:
            save_estate_document_entry(
                doc_key=doc_key,
                title=title.strip(),
                description=description.strip() or None,
                original_location=original_location.strip() or None,
                notes=notes.strip() or None,
            )
            st.success(f"Added '{title}' to the index.")
            st.rerun()
