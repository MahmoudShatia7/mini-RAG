# mini-RAG

Minimal FastAPI RAG API for uploading documents, processing them into chunks, indexing them in Qdrant, and answering questions with an LLM.

This release is the MongoDB baseline before the planned PostgreSQL refactor.

## Current Stack

- FastAPI for the API server
- MongoDB for projects, assets, and chunks
- Qdrant local storage for vector search
- Cohere embeddings
- Ollama local generation through the OpenAI-compatible API

## Requirements

- Python 3.10+
- Docker
- Ollama
- MongoDB service from Docker Compose

## Setup

Install Python dependencies:

```bash
cd src
pip install -r requirements.txt
cd ..
```

Create the app environment file:

```bash
cp src/.env.example src/.env
```

For local Ollama generation with Qwen, use:

```env
GENERATION_BACKEND = "OPENAI"
OPENAI_API_URL = "http://localhost:11434/v1/"
OPENAI_KEY = "ollama"
GENERATION_MODEL_ID = "qwen2.5:3b-instruct-q3_K_S"
```

For Cohere embeddings, use:

```env
EMBEDDING_BACKEND = "COHERE"
COHERE_API_KEY = "your-cohere-key"
EMBEDDING_MODEL_ID = "embed-multilingual-light-v3.0"
EMBEDDING_MODEL_SIZE = 384
```

## Start Services

Start MongoDB:

```bash
docker compose --env-file docker/.env -f docker/docker_compose.yml up -d
```

Start Ollama and make sure the Qwen model is installed:

```bash
ollama serve
ollama pull qwen2.5:3b-instruct-q3_K_S
```

## Run The API

From the project root:

```bash
python -m uvicorn src.main:app --reload
```

Open the docs:

```text
http://127.0.0.1:8000/docs
```

## RAG Workflow

Use Postman or the FastAPI docs to test this order:

1. Upload a file

```text
POST /api/v1/data/upload/{project_id}
```

2. Process files into chunks

```text
POST /api/v1/data/process/{project_id}
```

3. Push chunks into Qdrant

```text
POST /api/v1/nlp/index/push/{project_id}
```

Example body:

```json
{
  "do_reset": 1
}
```

4. Check vector index info

```text
GET /api/v1/nlp/index/info/{project_id}
```

5. Search the vector index

```text
POST /api/v1/nlp/index/search/{project_id}
```

Example body:

```json
{
  "text": "How can AI chatbots be manipulated to spread misinformation?",
  "limit": 3
}
```

6. Generate a RAG answer

```text
POST /api/v1/nlp/index/answer/{project_id}
```

Example body:

```json
{
  "text": "How can AI chatbots be manipulated to spread misinformation?",
  "limit": 3
}
```

## Release Notes

`v0.1.0` captures the working MongoDB RAG baseline before moving persistence to PostgreSQL.

