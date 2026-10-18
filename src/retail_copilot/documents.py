"""Read fictional policies and select evidence approved for a given date."""

import argparse
import json
import re
import tomllib
from datetime import date
from pathlib import Path

from langchain_core.documents import Document


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def load_settings() -> dict:
    with (PROJECT_ROOT / "config" / "settings.toml").open("rb") as handle:
        return tomllib.load(handle)


def _required_text(record: dict, fields: tuple[str, ...], label: str) -> dict[str, str]:
    if any(not isinstance(record.get(key), str) or not record[key].strip() for key in fields):
        raise ValueError(f"{label} is missing required text or metadata: {', '.join(fields)}.")
    return {key: record[key].strip() for key in fields}


def _read_date(value: object, label: str) -> date:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError(f"{label} needs a valid YYYY-MM-DD date.")
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ValueError(f"{label} needs a valid YYYY-MM-DD date.") from None


def _parse_document(record: object, source: str) -> Document:
    if not isinstance(record, dict):
        raise ValueError(f"{source} must contain one document object with named fields.")
    fields = _required_text(record, (
        "document_id", "policy_id", "title", "category", "customer_segment",
        "product", "process", "version", "status", "owner", "disclaimer",
    ), source)
    if record.get("synthetic") is not True:
        raise ValueError(f"{source} must be explicitly marked synthetic.")
    if not fields["disclaimer"].startswith("FICTIONAL TRAINING CONTENT."):
        raise ValueError(f"{source} needs the explicit fictional training disclaimer.")
    if fields["status"] not in {"approved", "draft", "archived"}:
        raise ValueError(f"{source} has an unsupported approval status.")
    if (
        not re.fullmatch(r"[A-Z]+-\d{4}", fields["policy_id"])
        or not re.fullmatch(r"[1-9]\d*", fields["version"])
        or fields["document_id"] != f"{fields['policy_id']}-v{fields['version']}"
    ):
        raise ValueError(f"{source} needs matching policy, version and document IDs (e.g. SIM-1024-v2).")

    starts = _read_date(record.get("effective_from"), f"{source}: effective_from")
    ends_raw = record.get("effective_to")
    ends = None if ends_raw is None else _read_date(ends_raw, f"{source}: effective_to")
    review = _read_date(record.get("review_date"), f"{source}: review_date")
    if ends is not None and ends < starts:
        raise ValueError(f"{source} ends before it takes effect.")
    if review < starts:
        raise ValueError(f"{source} has a review date before it takes effect.")

    raw_sections = record.get("sections")
    if not isinstance(raw_sections, list) or not raw_sections:
        raise ValueError(f"{source} needs a non-empty list of sections.")
    sections = []
    seen_sections = set()
    for position, section in enumerate(raw_sections, start=1):
        if not isinstance(section, dict):
            raise ValueError(f"{source}: section {position} must have named fields.")
        values = _required_text(section, ("section_id", "heading", "text"), f"{source}: section {position}")
        section_id = values["section_id"]
        if not re.fullmatch(r"[a-z][a-z0-9_]*", section_id):
            raise ValueError(f"{source} needs simple lowercase section IDs, such as required_checks.")
        if section_id in seen_sections:
            raise ValueError(f"{source}: section IDs must be unique within a document.")
        seen_sections.add(section_id)
        sections.append(values)

    # Keep section boundaries in local metadata; chunks will carry only their own section.
    metadata = {
        "document_id": fields["document_id"],
        "policy_id": fields["policy_id"],
        "document_title": fields.pop("title"),
        **fields,
        "effective_from": starts.isoformat(),
        "effective_to": ends.isoformat() if ends else None,
        "review_date": review.isoformat(),
        "synthetic": True,
        "source_file": source,
        "sections": sections,
    }
    return Document(
        id=metadata["document_id"],
        page_content="\n\n".join(section["text"] for section in sections),
        metadata=metadata,
    )


def load_documents(path: Path) -> list[Document]:
    """Read one JSON document or a folder of documents; no network requests."""
    try:
        files = sorted(path.glob("*.json")) if path.is_dir() else [path]
    except OSError:
        raise ValueError("The knowledge folder could not be read.") from None
    if not files:
        raise ValueError("The knowledge folder contains no JSON documents.")
    documents = []
    seen_ids = set()
    for file in files:
        try:
            record = json.loads(file.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            raise ValueError(f"{file.name} could not be read as valid UTF-8 JSON.") from None
        document = _parse_document(record, file.name)
        if document.id in seen_ids:
            raise ValueError("Document IDs must be unique so sources remain unambiguous.")
        seen_ids.add(document.id)
        documents.append(document)
    return documents


def approved_documents(documents: list[Document], as_of: date) -> list[Document]:
    """Use inclusive effective dates; stop if approved versions overlap."""
    selected = [
        document for document in documents
        if document.metadata["status"] == "approved"
        and date.fromisoformat(document.metadata["effective_from"]) <= as_of
        and (document.metadata["effective_to"] is None
             or as_of <= date.fromisoformat(document.metadata["effective_to"]))
    ]
    seen_policies = set()
    for document in selected:
        policy_id = document.metadata["policy_id"]
        if policy_id in seen_policies:
            raise ValueError(
                f"Conflicting approved versions of {policy_id} exist for {as_of}. "
                "Resolve the policy versions before using this library."
            )
        seen_policies.add(policy_id)
    return selected


def main() -> None:
    settings = load_settings()["demo"]
    parser = argparse.ArgumentParser(description="Check the fictional retail policy library.")
    parser.add_argument("--as-of", type=date.fromisoformat,
                        default=date.fromisoformat(settings["as_of_date"]))
    args = parser.parse_args()
    try:
        documents = load_documents(PROJECT_ROOT / settings["knowledge_directory"])
        approved = approved_documents(documents, args.as_of)
    except ValueError as error:
        parser.exit(1, f"Policy check failed: {error}\n")
    print(f"Loaded {len(documents)} synthetic documents.")
    print(f"Approved and effective on {args.as_of}: {len(approved)}.")
    print(f"Excluded from current evidence: {len(documents) - len(approved)}.")
    for document in approved:
        metadata = document.metadata
        print(f"  {document.id}: {metadata['document_title']} (source: {metadata['source_file']})")
