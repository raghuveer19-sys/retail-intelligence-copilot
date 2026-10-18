# Chunking experiment and local preparation

Date: 2026-10-15. The original preview is now a reusable Python comparison tool. A preparation command also saves whole-section chunks for all eligible policies. These are local steps within Phase 2, not the full ingestion pipeline.

## Run the saved comparison

From the Week2 folder, this command runs the Python module (a file containing reusable functions) and prints the three variants. It reads local policies and makes no API calls:

```powershell
uv run --no-active python -m retail_copilot.chunking
```

`-m retail_copilot.chunking` tells Python which module to run. The document, section, word limit and overlap come from `[chunking_experiment]` in `config/settings.toml`. The default is AUTH-1001-v1, section `delegation`, 20 words and five-word overlap. The project now includes `langchain-core` for its document containers; the README's `uv sync --no-active` command installs the locked dependencies if this environment has not been updated.

Expect the source filename, document/version and section heading, followed by each passage and its word positions. The three summaries are 3 passages/43 words, 3 passages/53 words, and 1 passage/43 words. These are the same results as the initial preview below.

To inspect the SIM policy's required-checks section instead, the command accepts a different document and section:

```powershell
uv run --no-active python -m retail_copilot.chunking --document-id SIM-1024-v2 --section-id checks
```

An ineligible or unknown document produces a plain-language message and an unsuccessful exit. An unknown section is also reported. A zero/negative word size or overlap greater than or equal to the size is rejected: otherwise the window could fail to advance. Configuration errors should be corrected in `settings.toml`.

## The code in small pieces

- `fixed_size_chunks` splits each section into word windows. It restarts at section boundaries, so a passage never mixes two sections.
- `section_chunks` returns one passage per complete section, preserving the loaded section text.
- `compare_section` selects the requested section from all three results.
- `main` reads settings, loads the library, applies eligibility checks and prints the comparison.

The key overlap calculation is `step = words_per_chunk - overlap_words`: 20 minus 5 makes each next passage start 15 words later. When a passage reaches the final source word, splitting stops; it does not emit an extra passage containing only already-seen words.

Each chunk is now a LangChain `Document`: `page_content` holds its passage, and `metadata` holds copied title, version, status, effective dates, disclaimer, actual source filename, section details and inclusive one-based word positions. Each chunk has an independent metadata copy and omits the parent's full `sections` collection. Whole-section chunks receive a persistent `id`; fixed-window comparison chunks have no persistent ID scheme. The preparation command described below saves these containers in our existing JSON format; provider-specific upload formatting remains future work.

The splitting functions expect documents already loaded and validated. They do not independently decide eligibility because they have no selected date; both the comparison and preparation commands call `approved_documents` first. Future cloud ingestion must preserve that order.

## Question

Does repeating words between small passages keep the complete rule together?

Input: the approved [AUTH-1001-v1 source](../data/knowledge/AUTH-1001-v1.json), section `delegation` ("Delegated SIM authority"), eligible on 2026-10-15. The section contains 43 whitespace-separated words. Its first sentence contains 28 words and states the delegation and identity conditions.

A chunk is a passage taken from a source. Overlap repeats some source words in neighbouring passages. Keeping a complete section is a different way of choosing passage boundaries.

## Method

We explicitly chose **20 words per fixed-size passage**, with either **zero or five words of overlap**. These deliberately small teaching settings make boundary problems visible. They are saved comparison defaults, not selected ingestion defaults. The third method keeps this entire section together.

For the overlapping version, the next passage starts 15 words after the previous start: 20 minus 5. Stop when the last source word has been included. Fixed-size passages are created from whitespace-separated words; punctuation stays attached to those words. Rejoining those words normalises whitespace without rewriting the guidance. The complete-section method preserves the loaded text, including internal line breaks. No general text-cleaning component was introduced.

```text
No overlap:     1–20, 21–40, 41–43
5-word overlap: 1–20, 16–35, 31–43
Whole section:  1–43
```

## Observed comparison

“Combined words” adds the words in all output passages, including repeated words. It is not a model token count or measured bill.

| Method | Passages | Combined words | Repeated words | Complete first rule sentence in one passage? |
| --- | ---: | ---: | ---: | --- |
| 20 words, no overlap | 3 | 43 | 0 | No |
| 20 words, 5-word overlap | 3 | 53 | 10 | No |
| Complete section | 1 | 43 | 0 | Yes |

Five-word overlap adds 10 repeated words across two boundaries: 53 combined words instead of 43, about 23% more. It does not make a 20-word passage capable of containing the full 28-word sentence.

This is a literal boundary check, not a semantic judgement or a model-quality score. A future retriever might return multiple neighbouring passages; whether it does so reliably still needs evaluation.

## Actual passages

All passages below come from `AUTH-1001-v1.json`, document `AUTH-1001-v1`, section `delegation`. Passage numbering is local to this report, not a persistent chunk-ID design.

### 20 words, no overlap

Passage 1, source words 1–20:

> A delegate may request a SIM replacement only when an authorised colleague confirms an active delegation record that explicitly includes

Passage 2, source words 21–40:

> SIM replacement and completes the IDV-1001 identity checks. The copilot cannot inspect delegation records or decide whether a real person

Passage 3, source words 41–43:

> satisfies these conditions.

### 20 words, 5-word overlap

Passage 1, source words 1–20:

> A delegate may request a SIM replacement only when an authorised colleague confirms an active delegation record that explicitly includes

Passage 2, source words 16–35:

> delegation record that explicitly includes SIM replacement and completes the IDV-1001 identity checks. The copilot cannot inspect delegation records or

Passage 3, source words 31–43:

> cannot inspect delegation records or decide whether a real person satisfies these conditions.

### Complete section

Passage 1, source words 1–43:

> A delegate may request a SIM replacement only when an authorised colleague confirms an active delegation record that explicitly includes SIM replacement and completes the IDV-1001 identity checks. The copilot cannot inspect delegation records or decide whether a real person satisfies these conditions.

## What was checked

The initial temporary preview used the existing loader and eligibility selector. For each variant it checked that:

- each passage's word sequence matched the indicated span of the source;
- all original source word positions appeared across the passages;
- the counts above came from the generated passages;
- the complete original first sentence appeared in one passage only for the whole-section variant.

The initial source-span and coverage assertions passed before any application changes. The subsequent reusable implementation added `chunking.py`, comparison settings and 11 chunking tests. All **38 automated tests passed** on 2026-10-15, and the saved command reproduced the example above. Checks cover exact/end boundaries, overlap, missing source words, punctuation and whitespace, invalid settings, metadata preservation and rejection of archived documents through the command. The existing 27 tests also passed in that run. Streamlit application checks were not rerun because its code and behaviour were unchanged.

## Comparison across the approved library

The reusable functions were also run across all 11 eligible documents and 33 sections, containing 1,169 source words. The archive was excluded before splitting. These counts cover section body text only, excluding headings, disclaimers and any future prompt wrapper.

| Method | Passages | Combined words | Repeated words | Passage sizes |
| --- | ---: | ---: | ---: | --- |
| 20 words, no overlap, restarting per section | 74 | 1,169 | 0 | 1–20 words |
| 20 words, 5-word overlap, restarting per section | 86 | 1,434 | 265 | 6–20 words |
| One complete section per passage | 33 | 1,169 | 0 | 21–46 words |

Tests verified source-word coverage and source metadata across every eligible section. A separate synthetic long-section test confirmed that the complete-section method does not silently cut long text; it currently has no size cap. This is a visible limitation, not a claim that arbitrarily large passages are suitable for models.

**Provisional baseline for this corpus:** one existing section per chunk. It keeps the inspected authority rule together and avoids tiny remainder passages while our current sections are short. This is a structural choice to evaluate, not a demonstrated retrieval-quality improvement. Model token limits, longer-section handling and retrieval/answer evaluation are still required before treating it as an ingestion strategy ready for service use.

## What this teaches

Keeping this short section together preserves its rule, conditions and the copilot's limitations. This supports section-aware chunking as a candidate for our structured library, not as a universal winner. A large section may need further splitting, and a condition may refer to another section or policy.

More overlap duplicates text. That can increase later embedding work and stored data. It may also increase answer-generation input if overlapping passages are both selected without removing duplicated text. Latency depends on the actual requests and processing, so it must be measured; this experiment did not measure it.

There were no embedding, Pinecone or answer-generation requests and no API charges. We have not estimated future charges from word counts.

## Prepare the eligible library

The comparison helped choose a provisional strategy. `prepare_chunks.py` now uses **one existing section per chunk**, named `section-v1`, across eligible policies. There is no fixed word size or overlap in this preparation method; the 20-word/five-word comparison settings remain separate.

```text
12 policy files -> load and validate -> select 11 eligible policies
                -> keep their 33 sections -> add IDs and metadata
                -> save data/processed/chunks.json
```

From the Week2 PowerShell terminal, this command uses this project's Python directly to create the local file. It does not rely on whichever environment is shown in parentheses in the terminal:

```powershell
.\.venv\Scripts\python.exe -m retail_copilot.prepare_chunks
```

Actual successful output on 2026-10-15:

```text
Local chunk preparation (no API calls).
Loaded documents: 12
Approved and effective on 2026-10-15: 11
Excluded document IDs: SIM-1024-v1
Strategy: section-v1 (one complete section per chunk)
Saved 33 chunks to data/processed/chunks.json
Body text: 1169 words; chunk sizes: 21-46 words.
Word counts are not token counts. Model limits and retrieval quality remain untested.
```

Open `data/processed/chunks.json` in the editor and search for `AUTH-1001-v1:delegation:section-v1` to see the familiar complete authority passage. The file is JSON: readable text containing named fields and lists of records. Its top-level fields describe the strategy, chosen eligibility date, loaded/eligible document counts, exclusions and number of chunks.

Each saved chunk contains:

| Field | Meaning |
| --- | --- |
| `chunk_id` | Repeatable label for the policy version, section and method |
| `text` | Complete section text as returned by the loader; no summarising or truncation |
| `word_count` | Count of whitespace-separated body words, for inspection only |
| `metadata` | Document/policy IDs, title, section ID/heading, actual filename, scope, version, approval, dates, owner and fictional disclaimer |

The loader strips outer whitespace when reading required text; preparation preserves the resulting section text, including internal line breaks, case and punctuation. It does not rewrite guidance or remove repeated language. A separate general cleaning component has not been added.

## Follow one section through the code

The preparation function first performs eligibility selection:

```python
eligible = approved_documents(documents, as_of)
```

This means "use only policies approved and effective on the chosen date." Next it visits every selected policy, then every whole-section chunk:

```python
for document in eligible:
    for chunk in section_chunks(document):
```

`for` repeats an instruction for each item in a collection. `section_chunks` is our existing function that keeps each section intact. Inside that function, the passage's label is assigned to the LangChain container's `id`:

```python
chunk_id = f"{document.id}:{section['section_id']}:section-v1"
```

The `f` tells Python to insert the named values into the text. Preparation reads `chunk.id` and saves it as `chunk_id`; it reads `chunk.page_content` and saves it as `text`. For the SIM checks section:

```text
SIM-1024-v2       : checks  : section-v1
policy version     section   method
```

The method version is separate from the policy version. If we later change chunk boundaries, we must define a new method/ID scheme. This ID identifies a passage location, not a content fingerprint: editing text under the same document/section IDs keeps the same ID. A policy revision should receive a new document version. Future embedding updates must handle changed text and obsolete records explicitly.

## Repeatability and failure behaviour

`[chunk_preparation]` in `config/settings.toml` selects the method and output file. Preparation supports `section-v1` only and requires a `.json` output inside `data/processed/` so it cannot be pointed at the source policy folder. Generated output is ignored by Git because it can be recreated from the versioned sources.

Records are sorted by ID. The file records the chosen eligibility date, not a changing run timestamp, so identical inputs/settings produce identical file bytes. Successful runs replace the whole snapshot rather than appending duplicates. Sections removed from the eligible library therefore disappear from the next successful output.

The command writes a complete temporary file before replacing the previous output. If validation fails, no eligible policies remain, versions conflict, settings are invalid or a file cannot be saved, the command reports an error and exits unsuccessfully. An earlier output may still exist: it is not evidence that the latest run succeeded. Fix the cause and rerun before using it. No automatic cloud synchronization is implemented.

The snapshot reflects the configured demo date, 2026-10-15, not today's date automatically. Later ingestion and retrieval must recheck relevant approval and date rules; a saved export does not grant permanent eligibility.

## Preparation validation and boundaries

At the initial preparation milestone, all **50 automated tests passed**: the existing 38 plus 12 preparation tests. Checks cover every eligible section's exact text and source metadata, unique/stable IDs, input reordering, version changes, ineligible sources, empty/conflicting evidence, long and Unicode text, repeatable saved bytes, removal of old sections, failed file replacement and command failures. The actual project command saved 33 chunks; Streamlit was unchanged at that milestone.

The later LangChain container migration passed **52 automated tests**, adding checks for actual `Document` objects, JSON-safe metadata and independent metadata copies. A regenerated export matched the pre-migration snapshot in content, including all text, IDs and metadata. The three viewer scenarios passed their assertions, with a Windows temporary-folder cleanup permission error reported at process exit. These are local structural checks, not retrieval-quality results.

This is a local preparation format, not a Pinecone payload. It contains no embeddings and preserves missing end dates as JSON `null`. The future uploader must apply provider metadata requirements and size checks before sending anything.

A token is a model's unit of text, which may be a word, part of a word or punctuation. There is no reliable universal word-to-token conversion. The separate [token report](embedding-preparation.md) now measures the proposed input for `text-embedding-3-small`: 1,404 tokens across 33 chunks, with sizes of 26–57. All pass the configured per-input limit. Preparation itself still preserves long sections for inspection without checking model limits; the report flags oversized inputs without truncating them. All 68 tests passed after the token report was added. No embedding or Pinecone requests were made.

## Next learning step

Inspect one saved record and distinguish its evidence text, source metadata and stable ID. Understanding check: should an unchanged section get the same ID when preparation is run again, and why? The user correctly identified repeatability for unchanged methods and inputs. We clarified that strategy is not the only influence: policy text, versions, eligibility and size/overlap settings can also change results. Stable IDs identify the same passage across runs; they are not proof that its text has never changed. Fixed-size comparison variants still have no persistent ID scheme.

Next, inspect [model tokens, input limits and the measured estimate](embedding-preparation.md) before embedding. Keeping sections intact does not automatically bring in referenced policies, so later retrieval and answer evaluation must test whether all necessary evidence is found.

The full Phase 2 remains incomplete. Local comparison, saved chunk preparation and a separate per-input token report now exist. General cleaning for other input formats, request-wide checks, embeddings, cloud serialization, Pinecone ingestion and cloud record verification remain pending.
