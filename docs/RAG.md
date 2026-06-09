# RAG pipeline

## Goals

1. Answer in the user's locale (Arabic by default), never fabricate citations.
2. Provide page-anchored citations a lawyer can click to verify.
3. Combine the firm's own files with the platform-curated Saudi-law corpus.
4. Stay tenant-isolated.

## Components

### Ingestion (`app/services/document_processor.py`)

- **PDF**: `pdfplumber` extracts text per page, preserving page numbers.
- **DOCX**: `python-docx` flattens paragraphs into a single page.
- **Text**: best-effort UTF-8 decode.
- **Chunker**: token-aware (`tiktoken` cl100k), default 600 tokens with 80
  overlap. Returns `(chunk_index, page_number, content, token_count)` tuples.

### Embeddings (`app/services/embeddings.py`)

- OpenAI by default (`text-embedding-3-large`, 3072-d).
- Pluggable: implement `EmbeddingsProvider.embed(texts)` for a swap.
- Batched (64 inputs at a time) to amortize round-trips.

### Indexing (`app/services/rag.py::index_document_chunks`)

- Triggered by `app.workers.tasks.ingest_document_task` (Celery, queue `ingestion`).
- Inserts `DocumentChunk` rows with `embedding`, `tenant_id`, `document_id`.
- Idempotent: re-running on the same document inserts new rows; the dashboard
  can issue a delete-then-reindex to refresh.

### Retrieval

Hybrid:

```
score = COSINE_WEIGHT * cosine_similarity     (TOP_K_VECTOR = 12)
      + KEYWORD_WEIGHT * trigram_similarity   (TOP_K_KEYWORD = 8)
```

Default weights `0.7 / 0.3`. The keyword leg matters for Arabic legal
phrases that the embedding model can mis-encode (e.g., specific article
references). Final top-k = 6.

`tenant_scope` always includes the caller's tenant; we additionally fan out
to the `platform` tenant so the firm gets answers grounded in base
statutes (Companies Law, Labor Law, etc.) without re-uploading them.

### Generation

Prompts live in `app/services/prompts.py`. Each route picks the AR or EN
system prompt, then the user prompt is assembled like:

```
<system>      You are an expert legal assistant…
<history>     last 8 messages
<user>        Retrieved legal context:
              [#1] <title> — page 12
              <chunk content>
              ...
              [#N] ...
              Question: <user message>
```

The model is instructed to cite sources inline as `[#1]`, `[#2]`, … which
the UI can match to the citation list returned alongside the answer.

### Persistence

After generation we save the assistant `Message` row with `citations` =
list of `{document_id, chunk_id, title, page_number, snippet, score}`.
The dashboard re-renders this list on every page load — no re-running of
the LLM.

## Tuning

| Knob                       | Where                       | Notes                            |
| -------------------------- | --------------------------- | -------------------------------- |
| Chunk size / overlap       | `document_processor.py`     | smaller chunks → better recall   |
| HNSW `m` / `ef_construction` | initial migration         | more accurate but slower index   |
| Top-K (vector / kw / final)| `services/rag.py` constants |                                  |
| Cosine vs keyword weight   | `services/rag.py` constants | tune for Arabic vs English mix   |
| Embedding model / dim      | env (`EMBEDDINGS_*`)        | requires re-index if changed     |
| LLM model                  | env (`LLM_*`)               | swap providers any time          |
