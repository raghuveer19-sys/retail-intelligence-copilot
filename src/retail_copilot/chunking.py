"""Compare local word windows with complete sections; no model or database calls."""

import argparse
from copy import deepcopy
from datetime import date

from langchain_core.documents import Document

from retail_copilot.documents import (
    PROJECT_ROOT, approved_documents, load_documents, load_settings,
)


def _section_words(section: dict) -> list[str]:
    words = section["text"].split()
    if not words:
        raise ValueError(f"Section {section['section_id']} must contain text before chunking.")
    return words


def _make_chunk(
    document: Document, section: dict, text: str,
    first_word: int, last_word: int, chunk_id: str | None = None,
) -> Document:
    """Copy source details so modifying one chunk cannot modify another or its policy."""
    metadata = deepcopy({key: value for key, value in document.metadata.items() if key != "sections"})
    metadata.update(
        section_id=section["section_id"], section_heading=section["heading"],
        first_word=first_word, last_word=last_word,
    )
    return Document(id=chunk_id, page_content=text, metadata=metadata)


def fixed_size_chunks(
    document: Document, words_per_chunk: int, overlap_words: int,
) -> list[Document]:
    """Split each section into word windows, restarting at section boundaries.

    Call approved_documents before using this function for current evidence.
    Whitespace is normalised; word order, spelling and punctuation are preserved.
    """
    if type(words_per_chunk) is not int or words_per_chunk <= 0:
        raise ValueError("words_per_chunk must be a positive whole number.")
    if type(overlap_words) is not int or not 0 <= overlap_words < words_per_chunk:
        raise ValueError("overlap_words must be a whole number from zero to less than words_per_chunk.")

    chunks = []
    step = words_per_chunk - overlap_words
    for section in document.metadata["sections"]:
        words = _section_words(section)
        for start in range(0, len(words), step):
            end = min(start + words_per_chunk, len(words))
            chunks.append(_make_chunk(
                document=document, section=section,
                text=" ".join(words[start:end]), first_word=start + 1, last_word=end,
            ))
            if end == len(words):
                break  # Do not emit another passage containing only an overlap tail.
    return chunks


def section_chunks(document: Document) -> list[Document]:
    """Keep each section intact; this teaching method has no size limit yet."""
    return [
        _make_chunk(
            document=document, section=section, text=section["text"],
            first_word=1, last_word=len(_section_words(section)),
            chunk_id=f"{document.id}:{section['section_id']}:section-v1",
        )
        for section in document.metadata["sections"]
    ]


def compare_section(
    document: Document, section_id: str, words_per_chunk: int, overlap_words: int,
) -> dict[str, list[Document]]:
    """Return the three teaching variants for one known source section."""
    if not any(section["section_id"] == section_id for section in document.metadata["sections"]):
        raise ValueError(f"Section {section_id} was not found in {document.id}.")
    variants = {
        f"Fixed size: {words_per_chunk} words, no overlap": fixed_size_chunks(document, words_per_chunk, 0),
        f"Fixed size: {words_per_chunk} words, {overlap_words}-word overlap": fixed_size_chunks(document, words_per_chunk, overlap_words),
        "Complete section": section_chunks(document),
    }
    return {
        name: [chunk for chunk in chunks if chunk.metadata["section_id"] == section_id]
        for name, chunks in variants.items()
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect local chunk boundaries without API calls.")
    parser.add_argument("--document-id", help="Override the example document in settings.toml.")
    parser.add_argument("--section-id", help="Override the example section in settings.toml.")
    args = parser.parse_args(argv)
    try:
        settings = load_settings()
        demo = settings["demo"]
        experiment = settings["chunking_experiment"]
        as_of = date.fromisoformat(demo["as_of_date"])
        document_id = args.document_id or experiment["document_id"]
        section_id = args.section_id or experiment["section_id"]
        documents = load_documents(PROJECT_ROOT / demo["knowledge_directory"])
        eligible = approved_documents(documents, as_of)
        document = next((item for item in eligible if item.id == document_id), None)
        if document is None:
            raise ValueError(f"No approved, effective document {document_id} exists for {as_of}.")
        variants = compare_section(
            document, section_id, experiment["words_per_chunk"], experiment["overlap_words"],
        )
    except (KeyError, TypeError):
        print("Chunk comparison could not finish: check the demo and chunking_experiment fields in settings.toml.")
        return 1
    except (OSError, ValueError) as error:
        print(f"Chunk comparison could not finish: {error}")
        return 1

    section = next(item for item in document.metadata["sections"] if item["section_id"] == section_id)
    source_words = len(section["text"].split())
    metadata = document.metadata
    print("Local chunk comparison (no API calls). Sizes are teaching settings.")
    print(f"Document: {document.id} | Title: {metadata['document_title']} | Version: {metadata['version']}")
    print(f"Source: {metadata['source_file']} | Approved for: {as_of}")
    print(f"Section: {section_id} | Heading: {section['heading']} | Source words: {source_words}")
    for name, chunks in variants.items():
        total = sum(len(chunk.page_content.split()) for chunk in chunks)
        label = "passage" if len(chunks) == 1 else "passages"
        print(f"\n{name}: {len(chunks)} {label}, {total} combined words, {total - source_words} repeated words")
        for number, chunk in enumerate(chunks, start=1):
            print(f"  Passage {number} | source words {chunk.metadata['first_word']}-{chunk.metadata['last_word']}")
            print(f"  {chunk.page_content}")
    print("\nThese are word counts, not model token usage, billing or retrieval-quality results.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
