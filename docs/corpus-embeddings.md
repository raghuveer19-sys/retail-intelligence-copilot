# Preparing the complete local embedding corpus

Completed 2026-10-15: **33 real embeddings from 11 eligible policies**, each with 768 values. The archived SIM policy is excluded.

```text
Source policies -> validate eligibility -> section chunks
    -> reuse matching saved vectors OR embed changed/missing inputs locally
    -> validate every record -> save one complete corpus snapshot
    -> Pinecone upload (separate step)
```

`prepare_embeddings.py` repeats our one-passage operation across the corpus. A saved vector is reused only if the chunk ID, text, exact formatted input, template, provider, model, model digest and dimensions match. The digest identifies the installed model version. Vector and reported usage must also pass validation. Current validated metadata replaces old metadata; changes to a title alter the model input and require re-embedding.

Sources removed or made ineligible disappear from the new local snapshot. This does not remove future remote records; remote cleanup needs a separate design. Chunk ID alone is not proof that a vector is current.

Requests are sequential, so each passage has its own reported token count. The model stays loaded between new inputs and unloads after the final request. A failed run lets it expire after five minutes. Truncation remains disabled so a long passage cannot silently lose conditions. [Ollama API](https://docs.ollama.com/api/embed).

The command saves only after every result passes validation, using the existing complete-temporary-file-then-replace writer. Failed requests preserve any earlier complete file, which must not be mistaken for a successful current run. Partial new work is not checkpointed; an interrupted run may recompute it.

## Run and inspect

This command uses local Ollama, reuses matching results and writes the complete snapshot. It never reads a cloud credential:

```powershell
.\.venv\Scripts\python.exe -m retail_copilot.prepare_embeddings
```

The output is `data/processed/embedding-corpus.json`, configured under `[embedding_preparation]` and ignored by Git. Read the records to inspect actual vectors, exact policy text, source metadata, model input, digest and reported tokens.

The first corpus run generated **32** vectors and reused the authority example. It reported **1,745 new input tokens**, or **1,808 corpus tokens** including the example's 63. Per-chunk counts range from **36 to 70** for this model and formatted input. These are not the earlier OpenAI tokenizer counts.

The acceptance rerun reused all **33**, generated **zero**, and retained identical record contents while an assertion blocked unexpected embedding requests. A local model-list request still checked the installed digest. The latest file therefore shows `new_records: 0`, `reused_records: 33`, `new_input_tokens: 0` and `corpus_input_tokens: 1808`. Its measured 611,197-byte JSON size is not a Pinecone billing measurement.

All **114 tests passed**, including eleven new checks for reuse, changed inputs/model versions, source removal, source-metadata refresh, cache errors, safe paths and failed requests preserving old output. Independently checked all real saved records against the current source text/metadata and confirmed the file is ignored by Git. Retrieval quality remains unmeasured.

Local inference has no external per-token bill. Hardware, electricity and storage still use resources; these costs were not measured and no pricing rate changed during preparation. Subsequent [Pinecone indexing](pinecone-indexing.md) has uploaded and verified all 33 records. Next comes question embedding and retrieval. Credentials stay in Week2's ignored `.env`.
