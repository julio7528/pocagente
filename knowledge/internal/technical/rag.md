# RAG Technical Architecture

The Getnet Support RAG architecture uses PostgreSQL Full Text Search for
lexical retrieval, pgvector for semantic retrieval, and Reciprocal Rank Fusion
(RRF) to combine candidates while preserving provenance. Embeddings are
generated locally and remain independent from the configured LLM provider.

## Approved embedding configuration

- Provider: FastEmbed `0.8.0`.
- Model: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`.
- Runtime: ONNX Runtime through FastEmbed on local CPU.
- GPU: optional only; it is never required.
- Dimension: 384.
- pgvector representation: `VECTOR(384)`.
- Pooling: the current FastEmbed mean-pooling behavior for this model.
- Manual normalization: none.
- External embedding API and credential: not used.

The model supports multilingual content, including Portuguese. Local CPU
validation confirmed a 384-dimensional output and suitable cached-run POC
performance. The initial model download/load is not steady-state embedding
latency.

## Compatibility

Embeddings must use one compatible representation. E5 embeddings, prior
sentence-transformers runtime embeddings, and embeddings produced with a
different model, dimension, pooling behavior, normalization policy, or semantic
input-processing behavior must be fully regenerated before retrieval use. Do
not convert vectors between dimensions.

## Approved lexical retrieval configuration

Lexical retrieval uses PostgreSQL Full Text Search with a mandatory
`rag.chunks.search_vector TSVECTOR NOT NULL`. The standard `portuguese`
configuration handles stemming, morphology, and business rules; `simple`
handles exact technical identifiers, acronyms, and field names. No custom
parser, tokenizer, thesaurus, or synonym configuration is used.

The application generates the vector with PostgreSQL native
`to_tsvector(...)` before atomic publication. Inputs are document title, chunk
section, and chunk content. PostgreSQL weights are `A` for title, `B` for
section, `C` for Portuguese content, and `D` for technical/exact text using
`simple`. Metadata, embeddings, keys, statuses, timestamps, and operational
fields are excluded.

User queries use combined native
`websearch_to_tsquery('portuguese', user_query)` and
`websearch_to_tsquery('simple', user_query)` parsing. Raw `to_tsquery()` is not
used for user input. Lexical ranking uses `ts_rank_cd`, preserving positional
information and term proximity. The planned GIN index is
`gin_chunks__search_vector`; it has not been created.

Active source and document status are required. Lexical retrieval contributes
at most 10 candidates; semantic retrieval contributes at most 10 candidates;
RRF combines them and the final context is Top-K 5 without an ML reranker.
Changes to title, section, or content regenerate affected search vectors.

## Approved semantic retrieval configuration

Semantic retrieval stores required embeddings as `VECTOR(384)` and uses cosine
distance through the pgvector `<=>` operator, ordered ascending. The initial
strategy is an exact nearest-neighbor scan with no active ANN index. HNSW is a
future-only preference before IVFFlat if benchmarks require ANN; it is not
created or tuned in the POC physical-model phase.

Semantic candidates are limited to 10 and require active source and document
statuses. Hybrid fusion uses RRF rank positions rather than combining or
normalizing raw lexical and vector scores, with no ML reranker. Lexical,
semantic, and provenance retrieval for one request must observe one consistent
committed chunk snapshot through one statement/CTE or a read-only
`REPEATABLE READ` transaction.

## Deferred implementation and retrieval choices

The FastEmbed adapter remains a skeleton; executable ingestion, embedding, and
retrieval are not implemented. FTS runtime generation and the planned GIN index
remain unimplemented. The approved semantic contract is documented above, but
the executable semantic retrieval implementation remains pending. Phase 4.5
is COMPLETED / APPROVED after its documentation gate. Phase 4.6 — CRIAR
TABELAS / DDL / MIGRATIONS is next. No vector index or database object has
been created by the physical-model documentation phase.
