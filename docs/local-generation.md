# Writing a real answer locally

## What this adds

The evidence pack is like a folder of approved policy excerpts. The answering model reads that folder and drafts a response to the question. **Generation** means producing this new text. It is different from **embedding**, which produces numbers for search.

```text
Saved question and approved passages
    -> recheck against the local corpus
    -> add answering instructions
    -> local Ollama model writes a structured draft
    -> check format and source IDs
    -> build citations from actual metadata
    -> review each claim against its cited evidence
```

The current evaluation candidate is `qwen3:4b-instruct`, a local non-thinking answering model downloaded on 2026-10-18. It is a different model from the previously installed thinking-only `qwen3:4b`, which did not return an accepted answer in two attempts. We also tested the smaller `qwen2.5:1.5b`: it returned answers more quickly but omitted useful details. Neither model is assumed accurate because it completed a request. See [the actual answer reviews](answer-review.md).

The embedding model remains `embeddinggemma:300m`. No OpenAI key is needed. The saved E04 example contains eight passages retrieved earlier; this single-answer command does not perform another Pinecone search or alter the index.

## What goes in and comes out

`generate.py` rebuilds and validates the saved context before constructing the same instruction/evidence messages used in the answering preview. Expected evaluation answers are never sent to the model.

The request specifies a **JSON schema**: a description of the permitted response fields. Each claim needs its own source labels. The model proposes a response status; that status is not verified confidence. The Python draft checker still validates the reply even though a schema was requested. Citations use the original source registry, so a model cannot invent a bibliography.

A successful result records the final draft, rendered answer, evidence, messages, source registry, model fingerprint, settings, token usage and duration. The current configured path is `data/processed/generation-instruct-example.json`; earlier comparison files are preserved. A fingerprint is a hash identifying the model or content used; it does not establish accuracy. Internal thinking is neither saved nor displayed.

The result explicitly retains `claim_support_checked: false` and `action_claims_checked: false`. Those fields describe the automatic checker. A separate review records whether the actual answer's claims are supported. A real source label can still accompany an incorrect statement.

The first full baseline has now produced **15 real local answers**. All passed the format/source-ID checks, but only **6 of 15 cases passed the separate Codex semantic review**. Semantic review checks what the answer means, including conditions, completeness and response behavior. These are Codex judgments, not independent human validation or a production-accuracy guarantee. The saved results and individual reviews are in `data/processed/evaluation-baseline/`; see [the evaluation results](evaluation.md) and [review rubric](evaluation-review-rubric.md).

The **234 automated tests passed on 2026-10-18**, including generation and evaluation-runner checks. Their passing result and the six reviewed case passes measure different things: functioning code and acceptable model answers.

## Input size and incomplete answers

The configured context window is 16,384 tokens, with up to 1,024 generated tokens. Before inference, the command uses a conservative allowance based on input UTF-8 bytes plus 4,608 tokens reserved for the chat template. This is not an exact input-token measurement. The installed model must report a compatible byte-based tokenizer and a template small enough for that allowance. Changing models requires reviewing these assumptions. The current candidate reports a 262,144-token maximum and a 4,040-byte template; the smaller comparison model reported a 32,768-token maximum and a 1,482-byte template.

The full input allowance plus output allowance must fit the context window. The application never cuts policy passages to make them fit. It also checks actual returned token usage. The installed model's reported maximum context must support the requested window. Increasing the window consumes more memory; larger is not automatically better.

The official Qwen model card describes `qwen3:4b-instruct` as non-thinking only. This installed Ollama entry includes a thinking capability label but omits the control metadata. We therefore explicitly configured `thinking_when_metadata_missing = false`, after checking the model card. If control metadata is supplied, it takes precedence. Missing controls without a reviewed setting stop the request; unexpected thinking output with thinking disabled rejects the response without saving that content.

The earlier `qwen3:4b` reports `true` only and required internal thinking, which was not saved or displayed. For any supported thinking model, its output-token cap includes thinking tokens. If the model reaches its output limit, returns malformed JSON, cites an unknown label or requests a tool, the draft is rejected in full. There are no automatic inference retries.

Empty evidence returns the existing fixed insufficient-evidence response without contacting Ollama, including without model-listing calls.

The single-answer command asks Ollama to unload the model after the request. The evaluation runner keeps it available for up to five minutes between cases to reduce repeated loading; this is temporary local memory use, not conversation memory.

## Run one command at a time

From the Week2 Project terminal, preview the question and local configuration. This makes no service calls and saves no answer:

```powershell
.\.venv\Scripts\python.exe -m retail_copilot.generate
```

To ask the local model for one real draft, add `--run`:

```powershell
.\.venv\Scripts\python.exe -m retail_copilot.generate --run
```

A successful run prints **DRAFT FOR REVIEW**, the answer with sources, reported token usage and elapsed generation time. Existing output files are not overwritten. To deliberately compare another run while preserving the first, choose a new path, for example `--run --output data/processed/generation-second.json`.

If generation stops, it prints a short explanation and creates no current answer. Earlier reports remain unchanged. A timeout means the computer did not return a complete response within the configured time; it is not proof that no computation occurred. Do not treat an earlier file as the failed run's result.

## Preserved experiments and the active prompt

Current settings again select the original `prompts/answering.md`. It already tells the model to ask for clarification when a question is ambiguous. That requirement is not reliably followed: for "Can I replace it?", the model inferred a SIM topic from the retrieved passages instead of asking what the user meant. A policy statement can be factually supported while answering an assumption about the user's intent.

Three controlled alternatives were rejected, with their evidence preserved:

- `data/processed/evaluation-completeness/`: all 15 real answers were reviewed; 7 passed versus 6 in the original baseline. Despite that one-case improvement, the alternative introduced material regressions: E11 treated missing authority evidence as a prohibition, and E12 omitted proof of purchase. The broader prompt was not retained.
- `data/processed/evaluation-clarification/`: an original-prompt variant strengthened only ambiguity handling. E01 still passed, E07 still failed to ask for specifics, and E11 lost its insufficient-evidence response without explaining the missing authority evidence. Both baseline and trial E11 failed the authored completeness check; the changed status is an additional regression. The prepared extra "Can I change that?" input was not sent to the model, so it has no result.
- `data/processed/question-last-E07.json`: an isolated format experiment repeated the actual question after the full unchanged passages, using the clarification instructions. All four generated policy claims were supported by their cited passages, but the model again returned `supported` with no clarifying question. No application-code change was adopted. Its separate review is `question-last-E07-review.json`.

These focused checks do not establish general accuracy or fix clarification. The original baseline, trial answers and separate Codex reviews remain unchanged by the prompt-selection decision.

Preview the evaluation using the restored original prompt without service calls or new files:

```powershell
.\.venv\Scripts\python.exe -m retail_copilot.evaluate
```

The following command resumes the original baseline. All 15 matching completed cases are reused, with no new generation or retrieval for those cases:

```powershell
.\.venv\Scripts\python.exe -m retail_copilot.evaluate --run
```

The evaluation command defaults to `data/processed/evaluation-baseline`, which matches the restored prompt. Do not resume either rejected trial directory using current settings. The runner checks the saved prompt, model and configuration fingerprints and rejects a mismatch instead of mixing experiments. For a new experiment, select a new result directory. A new experiment without cached retrieval can require Pinecone reads; the completed comparisons reused saved retrieval evidence.

## Costs and remaining work

This path uses local computation and has no external inference charge. Electricity, hardware and storage costs are unmeasured. Downloads were approximately 986 MB for `qwen2.5:1.5b` and 2.5 GB for `qwen3:4b-instruct`, plus local model storage. Token counts and timings help compare local efficiency; they are not a cloud invoice. No Pinecone reads or writes are made by this single-answer command. The separate evaluation command can make new Pinecone reads. Local HTTP requests are restricted to this computer, with proxies and redirects disabled; cloud-backed model entries are rejected.

Generation, the initial 15-case evaluation and these controlled prompt experiments are complete. Quality corrections remain: omitted criteria, changed conditions and response-status mistakes, including the user's requested clarification behavior. Further changes need review against the same criteria and regression checks. A correct citation can still accompany an incomplete, inaccurate or irrelevant answer.

Streamlit remains a library viewer. The selected direction is focused chat with limited recent conversation history, but final design approval and implementation are pending. The interface will follow the quality work; it must not make the unfinished answer checks look like a guarantee. The final user-journey tests and learning walkthrough remain to be completed.

Official references checked on 2026-10-18: [current model and download size](https://ollama.com/library/qwen3:4b-instruct), [Qwen's non-thinking model card](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507), [smaller comparison model](https://ollama.com/library/qwen2.5:1.5b), [chat request and usage](https://docs.ollama.com/api/chat), [structured responses](https://docs.ollama.com/capabilities/structured-outputs), [thinking controls](https://docs.ollama.com/capabilities/thinking), and [context-window memory](https://docs.ollama.com/context-length).
