"""
Calls Groq's free/fast LLM API to generate the final answer using
retrieved chunks as context (this is the "Generation" step of RAG).
"""
from django.conf import settings
from groq import Groq

_client = None

SYSTEM_PROMPT = (
    "You are a helpful assistant that answers questions using ONLY the "
    "provided context from the user's documents. If the answer is not "
    "contained in the context, say you don't know based on the uploaded "
    "documents -- do not make things up. Keep answers concise and clear."
)


def get_client():
    global _client
    if _client is None:
        if not settings.GROQ_API_KEY:
            raise RuntimeError(
                "GROQ_API_KEY is not set. Add it to your .env file. "
                "Get a free key at https://console.groq.com/keys"
            )
        _client = Groq(api_key=settings.GROQ_API_KEY)
    return _client


def build_context(chunks: list[dict]) -> str:
    parts = []
    for i, c in enumerate(chunks, start=1):
        parts.append(f"[Source {i}]\n{c['text']}")
    return '\n\n'.join(parts)


def generate_answer(question: str, chunks: list[dict], chat_history: list[dict] | None = None) -> str:
    context = build_context(chunks)

    user_content = (
        f"Context from documents:\n{context}\n\n"
        f"Question: {question}\n\n"
        "Answer using only the context above, and mention which "
        "[Source N] you used."
    )

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if chat_history:
        messages.extend(chat_history)  # [{role, content}, ...] for follow-up context
    messages.append({"role": "user", "content": user_content})

    client = get_client()
    response = client.chat.completions.create(
        model=settings.GROQ_MODEL,
        messages=messages,
        temperature=0.2,
        max_tokens=1024,
    )
    return response.choices[0].message.content
