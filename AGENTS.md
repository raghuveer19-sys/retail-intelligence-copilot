Retail Intelligence Copilot
The copilot will assist as fictional telecommunications retail colleague by answering questions and help the retail staff from approved retail knowledge documents.

The copilot should support these knowledge areas:

SIM replacement
eSIM activation
Identity verification
International roaming
Billing enquiries
Device returns and refunds
Click and collect
Mobile plan information
Account ownership and authority
Common device troubleshooting
This is a demonstration only.

Use synthetic fictional content. Do not use confidential, proprietary or real company information. Do not present the fictional policies as representing any real telecommunications provider.

The solution should demonstrate knowledge assistance only. It must not:

modify a customer account;
process a payment;
activate or disconnect a service;
perform identity verification;
make decisions about a real customer;
claim authority to waive fees;
provide legal or regulatory determinations;
initiate transactions.
Where a question requires an action rather than knowledge, the assistant must explain that it can provide guidance but cannot perform the action.

3. Intended users
The primary user is a retail colleague assisting customers in a telecommunications store.

Example questions include:

What identification is required for a SIM replacement?
A customer's phone was stolen. How can they get their number working again?
What is the difference between a physical SIM replacement and an eSIM replacement?
What should a customer check before using international roaming?
What is the return process for a faulty device?
What must be checked before releasing a click-and-collect order?
Can a secondary account contact replace a SIM?
What should a colleague do if the approved knowledge does not answer the question?
What does policy SIM-1024 say?
Can you waive the customer's outstanding bill?
The last question should be handled as an unsupported action, not answered as if the copilot has authority.

4. Technology principles
Build the simplest architecture that demonstrates the complete RAG pipeline without hiding the important concepts from me.

Preferred initial stack:

Python
Streamlit for the user interface
Pinecone for vector storage and retrieval
an OpenAI embedding model, unless a simpler or safer alternative is justified
an OpenAI language model for answer generation
environment variables for API keys
pytest or another simple testing approach
CSV or JSON for the evaluation dataset
Git for version control
Avoid adding LangChain, LlamaIndex or other abstraction frameworks in the first version unless they are genuinely necessary.

User-directed exception, 2026-10-15: use `langchain_core.documents.Document` from the LangChain library as the container for loaded policies and chunks. Here LangChain refers to the library, not the separate practice folder. Keep policy validation, eligibility selection and chunking rules explicit in our Python functions. This choice does not require a broader migration to LangChain agents, chains or hosted services. Explain and evaluate any broader integration separately.

I want to understand the underlying RAG stages directly:

Load
Clean
Chunk
Embed
Store
Retrieve
Construct context
Generate
Cite
Evaluate
If you recommend a framework later, explain what it abstracts, its advantages, its disadvantages and what additional complexity it introduces.

Before selecting models, SDK versions or APIs, consult current official documentation. Do not rely on outdated tutorials or deprecated package names.

Use the current Pinecone SDK and current documented API patterns.

5. Coaching method
Follow a structured coaching approach.

For every major phase, use this sequence:

A. Explain
Before making changes, explain:

what we are about to build;
why this component is required;
where it sits in the architecture;
what goes into it;
what comes out of it;
what could go wrong;
what cost it may introduce.
Use plain language first.

Then introduce the correct technical term.

Use analogies where helpful, but also explain the limits of the analogy.

B. Visualise
Show a small text-based architecture or process diagram.

Example:

User question | v Create query embedding | v Search Pinecone | v Retrieve relevant chunks | v Build grounded prompt | v LLM generates answer | v Answer with citations

Keep diagrams synchronised with the actual implementation.

C. Check my understanding
Ask me one or two short questions that test understanding, not memorisation.

Examples:

In your own words, what does an embedding represent?
Why do we retrieve document chunks before asking the LLM to answer?
What is Pinecone responsible for in this architecture?
Do not block all progress waiting for a perfect answer. If my answer shows a misunderstanding, explain it differently and continue carefully.

D. Plan
Show the files you propose to create or change.

For each file, explain its purpose in one sentence.

Do not edit files until you have shown the plan for that phase.

E. Build incrementally
Make one coherent, testable change at a time.

After each change:

explain what changed;
show how I can test it;
tell me what successful output should look like;
explain common failure messages in plain language;
run the appropriate tests where possible;
do not proceed if the current stage is broken.
F. Reflect
At the end of each phase, provide:

What we built
What I learned
Key technical terms
Architecture impact
Cost impact
Risks or limitations
What comes next
6. Interaction rules
Because I am a non-technical learner:

Do not give me ten unexplained terminal commands at once.
Provide one logical command group at a time.
Explain what each command will do before running it.
Never expose full API keys in code, terminal output, logs or documentation.
Never hardcode secrets.
Use a .env file locally and provide a .env.example with placeholder values.
Ensure .env is included in .gitignore.
Ask me to perform an action only when it requires my account, credential, consent or external service.
When an error occurs, first translate the error into plain English.
Explain the likely cause before proposing the fix.
Do not silently replace the architecture because of an error.
Do not undertake major refactoring without explaining why.
Avoid jargon where a straightforward explanation is available.
When jargon is necessary, define it immediately.
Do not say “simply,” “obviously” or “just” when describing an unfamiliar technical step.
Never fabricate successful test results or claim that something works unless it has been tested.
Clearly distinguish:
what you know;
what you inferred;
what was tested;
what still needs validation.
Maintain a decision log so I can understand why decisions were made.
Preserve a clean, runnable version after every phase.
Prefer learning and maintainability over clever or compressed code.
7. Architecture requirements
The first working version should use this logical architecture:

Synthetic retail documents | v Document loader | v Text cleaning | v Chunking | v Embedding model | v Pinecone index | v User question | v Question embedding | v Pinecone retrieval | v Top relevant chunks | v Grounded prompt | v Language model | v Answer + citations + confidence indication

Explain that the confidence indication is a product-level signal based on available evidence and retrieval conditions. It must not be presented as a mathematically guaranteed probability unless we actually implement and validate such a measure.

The interface should make the pipeline observable.

For each question, provide an optional expandable section showing:

the rewritten retrieval query, if rewriting is used;
retrieved chunk titles;
source document names;
section names;
similarity or relevance scores;
selected context passed to the LLM;
approximate token usage;
approximate estimated cost;
response latency.
Do not expose chain-of-thought or hidden internal reasoning. Show retrieved evidence and concise system decisions only.

8. Document and metadata design
Create approximately 10 to 15 small synthetic retail knowledge documents.

Each document should clearly include:

document title;
policy or article ID;
knowledge category;
intended customer segment;
effective date;
version;
owner;
review date;
sections;
fictional disclaimer.
Design a metadata model before ingestion.

Consider metadata fields such as:

document_id
document_title
policy_id
category
customer_segment
product
process
effective_date
version
section
source_file
chunk_id
Explain:

why each field exists;
which fields support citations;
which fields support filtering;
which fields improve governance;
which fields should not be used;
any Pinecone metadata constraints that affect the design.
Use namespaces only if they have a clear purpose. Explain whether a namespace represents an environment, tenant, corpus or another segregation boundary.

Do not use namespaces and metadata filters interchangeably without explaining the distinction.

9. Chunking experiment
Do not choose chunk size silently.

Create a small experiment comparing at least two chunking strategies, such as:

fixed-size chunks;
section-aware chunks.
Teach me:

why entire documents are usually too large;
why overly small chunks may lose context;
why overly large chunks may dilute relevance and increase token cost;
what chunk overlap means;
how chunk size affects retrieval, answer quality and cost.
Document the chosen strategy and the reason for selecting it.

10. Retrieval requirements
Begin with semantic retrieval.

The first version should:

convert the user's question into an embedding;
search the correct Pinecone index and namespace;
retrieve a configurable number of candidate chunks;
return relevant metadata with each result;
display retrieval results for learning and debugging;
pass only the selected evidence to the LLM.
Introduce top_k in plain language and allow it to be configured in a settings file.

Later, if justified by test results, add:

metadata filtering;
query rewriting;
reranking;
hybrid or full-text retrieval.
Do not add advanced retrieval features merely to make the architecture look sophisticated.

For each enhancement:

identify the observed retrieval problem;
record a baseline result;
implement the enhancement;
rerun the same evaluation questions;
compare quality, latency and estimated cost;
retain the enhancement only if it produces a meaningful benefit.
Include exact-identifier questions such as policy IDs so that we can test where semantic search is weaker and keyword or hybrid retrieval may help.

11. Answer-generation and grounding rules
The generated answer must be based only on retrieved approved context.

The answer-generation prompt should instruct the LLM to:

use the retrieved context as the source of truth;
avoid inventing policy or process information;
state when evidence is insufficient;
avoid claiming that an action has been completed;
distinguish guidance from transactional execution;
cite the supporting document and section;
mention conflicting sources if conflicting content is retrieved;
favour the latest effective approved version only when the versioning rules support that choice;
avoid giving a confident answer from weak or irrelevant evidence.
Create a fallback response such as:

“I could not find sufficient approved information in the Retail Intelligence Copilot knowledge base to answer this reliably. Please consult the authorised support channel or policy owner.”

Do not use this exact wording if a clearer context-specific response is better.

Citations must be assembled from retrieved metadata, not invented by the LLM.

12. Evaluation requirements
Treat evaluation as part of the build, not an optional final task.

Create an evaluation set of approximately 30 questions covering:

Direct-answer questions
The answer appears clearly in one chunk.

Paraphrased questions
The wording differs from the source.

Cross-document questions
Evidence must be combined from more than one source.

Exact identifier questions
The user references a policy or article ID.

Ambiguous questions
Clarification should be requested.

Unsupported questions
The knowledge base does not contain the answer.

Action requests
The user asks the copilot to perform an action it cannot perform.

Conflicting or outdated content
The retrieval pipeline must identify version or source conflicts.

For each test case, store:

test_id
category
user_question
expected_source
expected_behaviour
reference_answer
must_include
must_not_include
retrieval_success
answer_groundedness
citation_correctness
notes
Teach me the difference between:

retrieval quality;
answer relevance;
groundedness or faithfulness;
citation correctness;
completeness;
latency;
cost.
Provide a simple baseline scorecard that a business stakeholder can understand.

Do not claim production-grade accuracy from a small synthetic evaluation set.
Observability requirements:
Add basic logging that helps answer:

Was the document ingestion successful?
How many documents were loaded?
How many chunks were created?
How many records were written to Pinecone?
Which sources were retrieved?
How long did retrieval take?
How long did generation take?
How many tokens were used?
What did the query approximately cost?
Did the system use the insufficient-evidence fallback?
Did an error occur?
Do not log:

API keys;
secrets;
full customer personal information;
unnecessary sensitive content.
Use synthetic data throughout.
Suggested project structure
Propose a final structure similar to the following, but explain any changes:

retail-intelligence-copilot/ | |-- AGENTS.md |-- README.md |-- requirements.txt or pyproject.toml |-- .env.example |-- .gitignore | |-- app/ | |-- streamlit_app.py | |-- src/ | |-- config.py | |-- document_loader.py | |-- chunker.py | |-- embeddings.py | |-- pinecone_store.py | |-- retriever.py | |-- prompt_builder.py | |-- generator.py | |-- citations.py | |-- cost_tracker.py | |-- evaluation.py | |-- config/ | |-- settings.yaml | |-- pricing.yaml | |-- data/ | |-- knowledge/ | |-- evaluation/ | |-- docs/ | |-- architecture.md | |-- learning-journal.md | |-- decision-log.md | |-- cost-model.md | |-- scripts/ | |-- ingest_documents.py | |-- run_evaluation.py | |-- tests/

Keep the first version smaller if needed. Avoid empty architectural layers that add complexity without value.
17. Delivery phases
Build the project in these phases:

Phase 0: Orientation and setup
assess the local environment;
explain Python, terminal, repository, dependency and environment-variable concepts;
confirm prerequisites;
create the project structure;
establish Git safely;
create the initial architecture diagram;
create the learning journal and decision log.
Phase 1: Synthetic knowledge base
design the fictional retail content;
create the documents;
define metadata;
explain document governance and versioning;
validate that no real customer or confidential information is included.
Phase 2: Ingestion pipeline
load documents;
clean text;
compare chunking options;
create embeddings;
create or connect to the Pinecone index;
write records;
verify record count and metadata.
Phase 3: Retrieval pipeline
accept a question;
create a question embedding;
retrieve relevant chunks;
display sources, sections and retrieval scores;
test direct, paraphrased and exact-ID questions.
Phase 4: Grounded response generation
create the context;
create the answer-generation prompt;
call the LLM;
add citations;
add insufficient-evidence handling;
test unsupported and action-oriented questions.
Phase 5: User interface
build a simple Streamlit interface;
include question input;
show answer and citations;
include expandable retrieval evidence;
include approximate latency, token and cost information;
include a clear fictional-demo disclaimer.
Phase 6: Evaluation
create the 15-question test set;
establish baseline metrics;
identify retrieval failures;
improve only where evidence supports improvement;
compare before-and-after results.
20. How to begin
Do not start coding immediately.

Begin by:

Restating the project purpose in plain language.
Showing the end-to-end architecture.
Explaining the difference between the build outcome and learning outcome.
Identifying required accounts, software, credentials and expected costs.
Showing the proposed phase plan.
Highlighting decisions that I will need to make.
Identifying any assumption you have made.
Creating an initial learning checklist.
Proposing the Phase 0 file plan.
Pausing for my response before making external account changes or incurring charges.
