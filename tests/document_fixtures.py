"""Create independent Document variations for eligibility and chunking tests."""

from copy import deepcopy
from datetime import date

from langchain_core.documents import Document


def replace_document(document: Document, **changes) -> Document:
    metadata = deepcopy(document.metadata)
    metadata.update({
        key: value.isoformat() if isinstance(value, date) else deepcopy(value)
        for key, value in changes.items()
    })
    return Document(
        id=metadata["document_id"],
        page_content="\n\n".join(section["text"] for section in metadata["sections"]),
        metadata=metadata,
    )
