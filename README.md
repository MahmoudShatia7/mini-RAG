# mini-RAG

A minimal Retrieval-Augmented Generation service built with FastAPI.

Upload documents to a project, split them into chunks, embed those chunks into a
vector store, and answer questions grounded in the retrieved context.

The LLM backend, the embedding backend, and the vector database are each selected
from configuration and sit behind interfaces, so any of them can be swapped
without touching the routes.

## Stack

| Layer | Technology |
|---|---|
| API | FastAPI (async, ASGI lifespan) |
| Metadata store | PostgreSQL via async SQLAlchemy + asyncpg |
| Migrations | Alembic |
| Vector store | pgvector, with HNSW indexing (Qdrant also supported) |
| Embeddings | Cohere `embed-multilingual-v3.0` (1024 dimensions) |
| Generation | Ollama via the OpenAI-compatible API (Qwen 2.5) |
| Prompts | Per-language templates, English and Arabic |

## Architecture

```
routes/        HTTP layer: request schemas, status codes, response signals
controllers/   Business logic: file validation, chunking, retrieval, prompts
models/        SQLAlchemy schemes and data access (projects, assets, chunks)
stores/llm/    LLMInterface + factory -> OpenAI-compatible and Cohere providers
stores/vectordb/  VectorDBInterface + factory -> pgvector and Qdrant providers
```

Every provider call is asynchronous, so embedding a large document or waiting on a
generation response never blocks the event loop.

## Requirements

- Python 3.10+
- Docker (PostgreSQL with the pgvector extension)
- Ollama, for local generation
- A Cohere API key, for embeddings

## Setup

Install dependencies:

```bash
cd src
pip install -r requirements.txt
cd ..
```

Create the environment file:

```bash
cp src/.env.example src/.env
```

Start PostgreSQL:

```bash
docker compose --env-file docker/.env -f docker/docker_compose.yml up -d pgvector
```

Apply migrations:

```bash
cd src/models/db_schemes/minirag
alembic upgrade head
cd -
```

Start Ollama and pull the generation model:

```bash
ollama serve
ollama pull qwen2.5:3b-instruct-q3_K_S
```

## Configuration

Generation through a local Ollama server:

```env
GENERATION_BACKEND   = "OPENAI"
OPENAI_API_URL       = "http://localhost:11434/v1/"
OPENAI_KEY           = "ollama"
GENERATION_MODEL_ID  = "qwen2.5:3b-instruct-q3_K_S"
```

Embeddings through Cohere:

```env
EMBEDDING_BACKEND    = "COHERE"
COHERE_API_KEY       = "your-cohere-key"
EMBEDDING_MODEL_ID   = "embed-multilingual-v3.0"
EMBEDDING_MODEL_SIZE = 1024
```

Vector storage:

```env
VECTOR_DB_BACKEND         = "PGVECTOR"
VECTOR_DB_DISTANCE_METHOD = "cosine"
PGVECTOR_INDEX_THRESHOLD  = 100
```

A collection is named `collection_{embedding_size}_{project_id}`, so changing
`EMBEDDING_MODEL_SIZE` produces a separate collection rather than mixing vectors
of different widths. Two different models of the *same* width would share a
collection, so reset the collection when switching between them.

## Running

From the project root:

```bash
python -m uvicorn src.main:app --reload
```

Interactive docs: http://127.0.0.1:8000/docs

## API

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/api/v1/data/upload/{project_id}` | Upload a `.txt` or `.pdf` file |
| POST | `/api/v1/data/process/{project_id}` | Split stored files into chunks |
| POST | `/api/v1/nlp/index/push/{project_id}` | Embed chunks into the vector store |
| GET | `/api/v1/nlp/index/info/{project_id}` | Collection size, dimensions, metric |
| POST | `/api/v1/nlp/index/search/{project_id}` | Vector similarity search |
| POST | `/api/v1/nlp/index/answer/{project_id}` | Retrieve, then generate an answer |

### Typical flow

**1. Upload**

```text
POST /api/v1/data/upload/1
Body: form-data, key `file`
```

Allowed media types come from `FILE_ALLOWED_TYPES`; the declared `Content-Type` is
matched by media type alone, so `text/plain; charset=utf-8` is accepted.

**2. Process**

```json
{ "chunk_size": 512, "overlap_size": 64, "do_reset": 1 }
```

`chunk_size` is measured in characters of text and is a hard maximum: no chunk
exceeds it. It is unrelated to `FILE_DEFAULT_CHUNK_SIZE`, which is the upload
streaming buffer in bytes.

**3. Index**

```json
{ "do_reset": 1 }
```

**4. Search**

```json
{ "text": "How can AI chatbots be manipulated?", "limit": 3 }
```

**5. Answer**

```json
{ "text": "How can AI chatbots be manipulated?", "limit": 3 }
```

Returns the generated answer along with the prompt that produced it.

## Processing and chunking

Text is split on line breaks and accumulated until the next piece would exceed
`chunk_size`. A single line longer than `chunk_size` is broken at the last space
inside the limit, so words stay intact; a run with no whitespace is cut at the
limit rather than allowed to overflow.

- `chunk_size` is enforced as a ceiling, not a target
- `overlap_size` characters of the previous chunk are carried forward, beginning
  at a line or word boundary
- each loaded document is split independently, so a chunk never spans a document
  or PDF page boundary
- source metadata is preserved on every chunk

## Indexing

Chunks are read from PostgreSQL in pages sized to the embedding provider's batch,
so a full page becomes a single provider call.

The HNSW index is built **once, after** the bulk load completes, rather than
during it, and only when the collection reaches `PGVECTOR_INDEX_THRESHOLD` rows.
Below that threshold an exact scan is both faster and exhaustive. The index
operator class follows `VECTOR_DB_DISTANCE_METHOD`, and `ANALYZE` runs afterwards
so the query planner works from current statistics.

If the embedding provider fails partway through, the request returns
`502 Bad Gateway` with the number of chunks indexed before the failure:

```json
{
  "signal": "insert_into_vectordb_error",
  "inserted_items_count": 900,
  "total_chunks_count": 1057
}
```

Rate-limit errors are retried with exponential backoff; quota-exhaustion errors
are not retried, since they will not clear on their own.

## Multilingual prompts

Prompt templates live under `src/stores/llm/templates/locales/`, one package per
language. The query language is detected from the proportion of Arabic script in
the text, so an English question containing an Arabic term is still answered in
English. Retrieval itself is language-agnostic: an English query will match
relevant Arabic passages through the multilingual embedding model.

## Project layout

```
docker/                     Compose definition for PostgreSQL/pgvector
src/
  main.py                   Application startup and dependency wiring
  helpers/config.py         Settings loaded from .env
  routes/                   API endpoints and request schemas
  controllers/              Validation, chunking, retrieval, prompt assembly
  models/                   SQLAlchemy schemes, data access, Alembic migrations
  stores/llm/               LLM and embedding providers
  stores/vectordb/          Vector database providers
  assets/files/             Uploaded documents, per project
```

## License

See [LICENSE](LICENSE).
