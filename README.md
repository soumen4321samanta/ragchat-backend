# RAG Chatbot (Django + Groq + ChromaDB) — 100% Free Stack

Upload your own documents (PDF/DOCX/TXT) and chat with them using
Retrieval-Augmented Generation. No paid API needed.

## Stack
- **Backend:** Django + Django REST Framework
- **Embeddings:** `sentence-transformers` (runs locally, free)
- **Vector DB:** ChromaDB (local, free)
- **LLM:** Groq API (free tier, very fast Llama 3.3)
- **Frontend:** bring your own (React/Next.js) — this repo is API-only

## How RAG works here
1. You upload a document → text is extracted → split into overlapping chunks
2. Each chunk is embedded (turned into a vector) and stored in ChromaDB
3. When you ask a question, your question is embedded too, and ChromaDB
   finds the most similar chunks (semantic search)
4. Those chunks + your question are sent to the Groq LLM, which answers
   using ONLY that context (this prevents hallucination and lets you cite sources)

## Setup

### 1. Install dependencies
```bash
python3 -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Get a free Groq API key
- Go to https://console.groq.com/keys
- Sign up (free) → create an API key

### 3. Configure environment
```bash
cp .env.example .env
# then edit .env and paste your GROQ_API_KEY
```

### 4. Run migrations
```bash
python manage.py migrate
python manage.py createsuperuser   # optional, for /admin/
```

### 5. Start the server
```bash
python manage.py runserver
```
API is now live at `http://127.0.0.1:8000/api/`

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/documents/` | Upload a file (multipart, field name `file`) |
| GET | `/api/documents/` | List uploaded documents + their status |
| DELETE | `/api/documents/{id}/` | Delete a document + its vectors |
| POST | `/api/sessions/` | Create a chat session, pass `document_ids: [uuid, ...]` |
| GET | `/api/sessions/{id}/` | Get session + full message history |
| POST | `/api/sessions/{id}/ask/` | Ask a question `{ "question": "..." }` |

### Example flow (curl)
```bash
# 1. Upload a document
curl -X POST http://127.0.0.1:8000/api/documents/ \
  -F "file=@mynotes.pdf"
# -> returns {"id": "abc-123", "status": "ready", ...}

# 2. Create a chat session pointing at that document
curl -X POST http://127.0.0.1:8000/api/sessions/ \
  -H "Content-Type: application/json" \
  -d '{"title": "My Notes Chat", "document_ids": ["abc-123"]}'
# -> returns {"id": "session-xyz", ...}

# 3. Ask a question
curl -X POST http://127.0.0.1:8000/api/sessions/session-xyz/ask/ \
  -H "Content-Type: application/json" \
  -d '{"question": "Summarize the main points"}'
```

## Project structure
```
ragchat/
├── ragchat/              # Django project settings
├── chatapp/
│   ├── models.py         # Document, ChatSession, Message
│   ├── serializers.py    # DRF serializers
│   ├── views.py          # Upload, ingestion, ask endpoint
│   ├── urls.py
│   └── services/
│       ├── document_processor.py  # extract text + chunk
│       ├── vectorstore.py         # embeddings + ChromaDB
│       └── llm.py                 # Groq API call
├── requirements.txt
└── .env.example
```

## Next steps to extend this project
- Add user authentication (JWT via `djangorestframework-simplejwt`)
- Add streaming responses (Server-Sent Events) for a ChatGPT-like typing effect
- Swap the naive character-chunker for a sentence-aware splitter (LangChain's
  `RecursiveCharacterTextSplitter`) for better chunk quality
- Build a React/Next.js frontend with an upload zone + chat UI
- Deploy: backend → Render/Railway (free tier), frontend → Vercel

## Deployment notes
- ChromaDB persists to disk at `CHROMA_PERSIST_DIR` (set in settings.py) —
  make sure this path is on a persistent volume, not ephemeral storage
- Switch `DATABASES` to Postgres (e.g. free tier on Neon/Supabase) for production
- Set `DEBUG=False` and a real `DJANGO_SECRET_KEY` in production `.env`
