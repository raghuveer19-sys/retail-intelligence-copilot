"""Phase 1: inspect fictional telecom evidence before adding retrieval."""

from datetime import date

import streamlit as st

from retail_copilot.documents import (
    PROJECT_ROOT, approved_documents, load_documents, load_settings,
)


st.set_page_config(page_title="Retail Intelligence Copilot", page_icon="📚")
settings = load_settings()["demo"]
st.title("Retail Intelligence Copilot")
st.caption(f"{settings['retailer_name']} · Fictional telecom training example")
st.info("Inspect the fictional policy library. Search and question answering are not available yet. These policies do not represent a real provider.")
as_of = st.date_input("Policy date", value=date.fromisoformat(settings["as_of_date"]))

try:
    documents = load_documents(PROJECT_ROOT / settings["knowledge_directory"])
    approved = approved_documents(documents, as_of)
except ValueError as error:
    st.error(str(error))
    st.stop()

left, right = st.columns(2)
left.metric("Approved policies for this date", len(approved))
right.metric("Excluded documents", len(documents) - len(approved))
st.subheader("Approved policy library")
if not approved:
    st.warning("No approved policies cover this date. There is insufficient evidence to answer policy questions.")
for document in approved:
    metadata = document.metadata
    with st.expander(f"{metadata['policy_id']} · {metadata['document_title']}", expanded=False):
        st.caption(metadata["disclaimer"])
        for section in metadata["sections"]:
            st.markdown(f"**{section['heading']}**")
            st.write(section["text"])
            st.caption(f"Section ID: {section['section_id']}")
        st.caption(
            f"Source: {metadata['source_file']} · Document: {document.id} · "
            f"Version: {metadata['version']} · Status: {metadata['status']} · "
            f"Effective: {metadata['effective_from']} to {metadata['effective_to'] or 'open-ended'}"
        )
        st.caption(
            f"Category: {metadata['category']} · Segment: {metadata['customer_segment']} · "
            f"Owner: {metadata['owner']} · Review due: {metadata['review_date']}"
        )
        if date.fromisoformat(metadata["review_date"]) < as_of:
            st.warning("Review is overdue. This is a governance reminder, not automatic expiry; consult the policy owner.")
with st.expander("Why are some documents excluded?"):
    st.write("Only approved documents within their effective dates can support current answers. Draft, archived, expired and future policies are excluded.")
    selected_ids = {document.id for document in approved}
    for document in documents:
        if document.id not in selected_ids:
            metadata = document.metadata
            st.write(f"{document.id} — {metadata['status']}; effective {metadata['effective_from']} to {metadata['effective_to'] or 'open-ended'}")
