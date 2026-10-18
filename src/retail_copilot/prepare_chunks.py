"""Prepare a local, inspectable section-chunk export without calling services."""

import json
from datetime import date
from pathlib import Path
from tempfile import NamedTemporaryFile

from langchain_core.documents import Document

from retail_copilot.chunking import section_chunks
from retail_copilot.documents import (
    PROJECT_ROOT, approved_documents, load_documents, load_settings,
)


def build_chunk_export(
    documents: list[Document], as_of: date, strategy: str,
) -> dict:
    """Use validated documents; select eligible evidence before creating records."""
    if strategy != "section-v1":
        raise ValueError("Chunk preparation supports strategy 'section-v1' only.")
    eligible = approved_documents(documents, as_of)
    if not eligible:
        raise ValueError(f"No approved, effective policies exist for {as_of}.")

    records = []
    seen_ids = set()
    for document in eligible:
        for chunk in section_chunks(document):
            chunk_id = chunk.id
            if chunk_id in seen_ids:
                raise ValueError(f"Duplicate chunk ID: {chunk_id}.")
            seen_ids.add(chunk_id)
            records.append({
                "chunk_id": chunk_id,
                "text": chunk.page_content,
                "word_count": len(chunk.page_content.split()),
                "metadata": {
                    key: value for key, value in chunk.metadata.items()
                    if key not in {"first_word", "last_word"}
                },
            })

    eligible_ids = {document.id for document in eligible}
    return {
        "schema_version": 1,
        "strategy": strategy,
        "as_of_date": as_of.isoformat(),
        "loaded_documents": len(documents),
        "eligible_documents": len(eligible),
        "excluded_document_ids": sorted(
            document.id for document in documents
            if document.id not in eligible_ids
        ),
        "chunk_count": len(records),
        "chunks": sorted(records, key=lambda record: record["chunk_id"]),
    }


def save_chunk_export(export: dict, output_path: Path) -> None:
    """Replace the generated snapshot only after writing a complete temporary file."""
    contents = json.dumps(export, ensure_ascii=False, indent=2) + "\n"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None
    try:
        with NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="\n", dir=output_path.parent,
            prefix="chunks-", suffix=".tmp", delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            handle.write(contents)
        temporary_path.replace(output_path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def main() -> int:
    try:
        settings = load_settings()
        demo = settings["demo"]
        preparation = settings["chunk_preparation"]
        as_of = date.fromisoformat(demo["as_of_date"])
        output_path = (PROJECT_ROOT / preparation["output_file"]).resolve()
        generated_directory = (PROJECT_ROOT / "data" / "processed").resolve()
        if not output_path.is_relative_to(generated_directory) or output_path.suffix != ".json":
            raise ValueError("The output must be a .json file inside data/processed/.")

        documents = load_documents(PROJECT_ROOT / demo["knowledge_directory"])
        export = build_chunk_export(documents, as_of, preparation["strategy"])
        save_chunk_export(export, output_path)
    except (KeyError, TypeError):
        print("Chunk preparation could not finish: check demo and chunk_preparation in settings.toml.")
        print("Do not use an earlier export as evidence of a successful run.")
        return 1
    except (OSError, ValueError) as error:
        print(f"Chunk preparation could not finish: {error}")
        print("Do not use an earlier export as evidence of a successful run.")
        return 1

    counts = [record["word_count"] for record in export["chunks"]]
    print("Local chunk preparation (no API calls).")
    print(f"Loaded documents: {export['loaded_documents']}")
    print(f"Approved and effective on {as_of}: {export['eligible_documents']}")
    excluded = ", ".join(export["excluded_document_ids"]) or "none"
    print(f"Excluded document IDs: {excluded}")
    print(f"Strategy: {export['strategy']} (one complete section per chunk)")
    print(f"Saved {export['chunk_count']} chunks to {output_path.relative_to(PROJECT_ROOT.resolve()).as_posix()}")
    print(f"Body text: {sum(counts)} words; chunk sizes: {min(counts)}-{max(counts)} words.")
    print("Word counts are not token counts. Model limits and retrieval quality remain untested.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
