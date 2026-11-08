# How ArchiveLens maps to IBM Content Aware Storage (CAS)

IBM Content Aware Storage (part of IBM Storage Scale / IBM Fusion) moves AI data preparation *into the storage
layer*: it notices new or changed files, extracts and enriches their content, and keeps a vector database up to
date for retrieval-augmented generation (RAG).

ArchiveLens is a small-scale version of the same idea, built with open-source tools:

| CAS capability | ArchiveLens equivalent |
|---|---|
| Detects new/changed content automatically | `app/watcher.py` watch folder + SHA-256 change/duplicate check |
| Extracts content from unstructured files | Tesseract OCR, PDF text layer, Gemini transcription |
| Adds semantic metadata | Gemini fills Dublin Core fields |
| Built-in vector database | PostgreSQL + pgvector `chunks` table |
| Serves RAG queries | `search.retrieve_passages` + `ai.answer` with citations |

## How this could move onto CAIR infrastructure

1. Keep the **metadata standard, review UI and search front end** from ArchiveLens.
2. Replace the watch folder and pgvector with **CAS ingestion and its vector store** on IBM Storage Scale.
3. Point the FastAPI search/RAG endpoints at the CAS retrieval API.
4. Benefit: scale to very large collections and run models on CAIR's own hardware, so data stays on-premises.

Open questions to explore: CAS supported file types, how custom metadata fields are stored, and access control
for future public access.
