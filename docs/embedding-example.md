# One chunk: from text to an embedding

Date: 2026-10-15. The request integration is implemented and tested with simulated responses. The user confirmed that they still have no OpenAI API key and requested local preparation/testing. Live service use remains disabled. No real embedding has been generated.

**Current project update, 2026-10-15:** This page is the retained OpenAI comparison lesson. Its 1,536-dimensional model remains unrun. The user selected local Ollama, and one actual 768-dimensional embedding has now been saved. Read [the current local example](ollama-embedding-example.md) and [Pinecone record mapping](pinecone-records.md). The OpenAI command now reads `[openai_embedding]` settings.

## What an embedding adds

The tokenizer measured our authority passage as 50 tokens. An embedding model processes that text and produces a vector: a list of numbers used to compare related text. For our selected model/configuration, the expected vector has 1,536 numbers. A dimension is one position in that list; individual positions do not have simple labels such as "SIM" or "identity".

The input token count and output dimension are separate. A 50-token passage and a 57-token passage both produce 1,536-number vectors when using this same configuration. Later, we will embed a question with the same model and dimensions, then compare its vector with stored passage vectors. Similarity helps find candidate evidence; it does not prove that a passage answers the question.

```text
Approved AUTH section as a LangChain Document
    -> count exact page_content and estimate cost
    -> preview [runs now, no API call]

Future enabled live mode:
    -> one OpenAI embedding request
    -> validate returned vector and usage
    -> save vector + original text + source metadata locally
    -> Pinecone upload and retrieval [later]
```

## What the code does

| File | Responsibility |
| --- | --- |
| `embeddings.py` | Check one input and its allowance, call the SDK, validate the response, retain source details and usage |
| `embed_example.py` | Select the configured eligible section, preview by default, and control an explicitly enabled live run |
| `readiness.py` | Read credentials privately using the existing Week2-only file and environment precedence rules |
| `tests/test_embeddings.py` | Exercise the installed SDK against fictional responses without contacting OpenAI |

An SDK is a library that handles the details of communicating with a service. We installed the official `openai` Python SDK, version 3.31.0, and locked it in `uv.lock`. LangChain still supplies our `Document` container; the OpenAI SDK handles the embedding request. [Official Python SDK](https://developers.openai.com/api/reference/python).

This is the request inside `embeddings.py`:

```python
response = client.embeddings.create(
    model=embedding["model"],
    input=[chunk.page_content],
    dimensions=embedding["dimensions"],
    encoding_format="float",
)
```

`input` contains one passage; `float` requests numerical values in the response. Only the passage text is sent. IDs and metadata remain local and are attached to the returned vector for source tracking. The configured example is `AUTH-1001-v1:delegation:section-v1`. [Embedding API reference](https://developers.openai.com/api/reference/python/resources/embeddings/methods/create).

## Run the local preview

From the Week2 PowerShell terminal, this command selects and measures the example, then describes the expected request. It does not read a credential, construct an API client or create a vector file:

```powershell
.\.venv\Scripts\python.exe -m retail_copilot.embed_example
```

Verified output includes:

```text
One-chunk embedding example: PREVIEW ONLY
Input: 50 tokens of exact page_content; no metadata sent.
Model: text-embedding-3-small | Expected output: 1536 numbers.
Estimated request cost: USD 0.00000100 (not an invoice).
Preview complete. No embedding API call, no vector and no result file created.
```

The tokenizer vocabulary is already cached in this environment. On a fresh installation its first use needs a download; this still does not send passage text to the embedding service.

## Live mode is prepared but disabled

Before a future live run, review current pricing, account access and the chosen allowance. The current local configuration check reports the OpenAI key as missing. A real key belongs only in Week2's ignored `.env` or a private environment variable; never paste it in chat or `.env.example`.

Live mode requires all of the following: the existing `paid_service_use_enabled` setting changed to boolean `true` after cost/account review, the explicit `--live` option, a positive `--max-cost-usd` allowance covering the estimate, and a private API key. Nothing was enabled during this step. The default preview remains usable without credentials.

The allowance checks the estimate for one attempt; it is not a provider-enforced or cumulative account spending limit. One passage under the configured 8,192-token input cap is also below the documented 300,000-token request total. Multiple-input batching and its input-count/total-token checks remain future work. The first lesson does not loop over the full corpus.

The client uses the explicit configured OpenAI URL, a 30-second timeout setting and zero automatic retries. A timeout can occur after the service has processed a request; check usage before repeating it. API error bodies are not printed. [SDK timeouts and retries](https://developers.openai.com/api/reference/python).

## Keeping the vector linked to its evidence

An embedding does not replace the original passage. Think of one saved record as a card with four connected parts:

| Saved field | Purpose | Our authority example |
| --- | --- | --- |
| `chunk_id` | Identify the exact chunk | `AUTH-1001-v1:delegation:section-v1` |
| `text` | Preserve the passage that can support an answer | The complete delegation section, including its conditions and the copilot's limitations |
| `metadata` | Identify and describe the source | Policy `AUTH-1001`, version `1`, section `Delegated SIM authority`, file `AUTH-1001-v1.json`, and approval/date information |
| `vector` | Help compare this passage with an embedded question | 1,536 numbers expected from a future successful request; no real vector exists yet |

The first three parts come from our existing LangChain `Document`: `id`, `page_content` and `metadata`. The fourth would come from the embedding API. The current `embed_one_chunk` function assembles these into one result after validating the response. Only `page_content` is sent for embedding; retaining metadata locally is different from sending it to the model.

Later, retrieval will use this relationship:

```text
Question vector -> find candidate passage vectors
                            |
                            v
                   corresponding chunk records
                   /                          \
         text: evidence to read       metadata: source to cite
```

This diagram describes future retrieval, not a running feature. A close vector match alone does not establish that a source is eligible or that it answers the whole question. If the source information were attached to the wrong passage, a citation could look plausible while pointing to the wrong evidence. We therefore preserve the text and its metadata together; later citation construction must use the metadata of the actual retrieved source.

The vector is not a substitute for storing the original policy wording. The saved local example is also not yet the Pinecone upload format; that mapping will be a separate small step. The local preview creates none of these embedding-result records and incurs no embedding API charge.

## Returned result and failures

A live response is accepted only if it identifies the requested model, contains one result for input index zero, has the requested vector length, contains finite numeric values with at least one nonzero value, and supplies valid input/total usage. These structural checks cannot establish semantic quality.

After validation, the example saves `data/processed/embedding-example.json` with the vector, exact text, independent source metadata, model, dimensions, eligibility date, creation time, local token count, reported usage and dated cost estimates. It reuses the existing complete-then-replace JSON writer. This file is ignored by Git and is not a Pinecone upload payload. No such file was created in the project during this step.

An existing output file stops a live run before sending, to prompt inspection instead of another charge. A missing key, disabled service setting, inadequate allowance or oversized input also stops before a request. If an API request succeeds but saving fails, usage may still be billed. Invalid responses are not saved and may also represent billable processing; inspect provider usage before retrying.

## Cost and verification

The standard public price was rechecked on 2026-10-15: **USD 0.02 per million input tokens**. One 50-token example is estimated at **50 / 1,000,000 × 0.02 = USD 0.000001**. Each real resubmission can create more usage; retaining and reusing a valid result avoids unnecessary repeat calls. This estimate excludes all other application costs, taxes and currency conversion. [Official model price](https://developers.openai.com/api/docs/models/text-embedding-3-small).

For a live result, `usage_based_cost_usd` uses the API-reported input tokens and the recorded rate; it is still an estimate to reconcile with provider billing. The local estimate is retained separately so differences are visible. No real usage or bill was measured here.

All **85 automated tests passed**: the previous 68 plus 15 embedding tests and two credential-reader tests. The installed SDK handled simulated HTTP responses while socket connections were blocked. Tests cover request contents, metadata retention, output dimensions, usage, disabled calls, allowances, error sanitization, no automatic retries, output protection and save failures. Simulated vectors exist only as test fixtures in temporary test folders; they are not meaningful embeddings or evidence of retrieval quality.

Next, walk through the preview and the distinction between tokens and dimensions. Once API access is available, explain and run one authorised real request before embedding the full corpus. No account, cloud resource, Pinecone integration or transactional capability was added by this step.
