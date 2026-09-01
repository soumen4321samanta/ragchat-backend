"""
Uses the Groq LLM to generate multiple-choice questions from a document's
full text. Unlike llm.py (which answers a specific user question), this
asks the model to produce a structured JSON list of MCQs.
"""
import json
from django.conf import settings
from .llm import get_client

MCQ_SYSTEM_PROMPT = (
    "You are a quiz generator. Based ONLY on the document text the user gives you, "
    "create multiple-choice questions that test understanding of that content. "
    "Respond with ONLY a raw JSON array -- no markdown code fences, no extra "
    "commentary before or after. Each item in the array must have exactly this shape:\n"
    '{"question": "...", "options": {"A": "...", "B": "...", "C": "...", "D": "..."}, '
    '"correct_option": "A", "explanation": "..."}\n'
    "The 'correct_option' must be one of \"A\", \"B\", \"C\", or \"D\". "
    "Keep questions and options concise. Do not repeat the same question twice."
)


def generate_mcqs(document_text: str, num_questions: int = 5) -> list[dict]:
    client = get_client()

    user_prompt = (
        f"Document text:\n{document_text}\n\n"
        f"Generate exactly {num_questions} multiple-choice questions from this text."
    )

    response = client.chat.completions.create(
        model=settings.GROQ_MODEL,
        messages=[
            {"role": "system", "content": MCQ_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.4,
        max_tokens=2048,
    )

    raw = response.choices[0].message.content.strip()

    # Some models wrap JSON in ```json ... ``` fences even when told not to.
    # Strip those off before parsing.
    if raw.startswith('```'):
        raw = raw.strip('`')
        if raw.lower().startswith('json'):
            raw = raw[4:]
        raw = raw.strip()

    return _parse_mcq_json(raw)


def _parse_mcq_json(raw: str) -> list[dict]:
    """
    Groq/Llama models sometimes ignore the "return a JSON array" instruction
    and instead return one JSON object per line (JSON Lines / JSONL), e.g.:
        {"question": "...", ...}
        {"question": "...", ...}
    instead of:
        [{"question": "...", ...}, {"question": "...", ...}]

    This tries the strict array format first, and falls back to parsing
    line-by-line if that fails.
    """
    # Attempt 1: standard JSON array
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Attempt 2: JSON Lines -- one object per line
    mcqs = []
    for line in raw.splitlines():
        line = line.strip().rstrip(',')  # some models add trailing commas
        if not line:
            continue
        try:
            mcqs.append(json.loads(line))
        except json.JSONDecodeError:
            continue  # skip lines that aren't valid JSON (e.g. stray text)

    if mcqs:
        return mcqs

    # Attempt 3: use a JSON decoder that can pull multiple objects out of
    # one blob of text, in case they're all on one line with no separator
    decoder = json.JSONDecoder()
    idx = 0
    raw_stripped = raw.strip()
    while idx < len(raw_stripped):
        raw_stripped_sub = raw_stripped[idx:].lstrip()
        if not raw_stripped_sub:
            break
        skip = len(raw_stripped) - len(raw_stripped_sub)
        try:
            obj, end = decoder.raw_decode(raw_stripped_sub)
            mcqs.append(obj)
            idx += skip + end
        except json.JSONDecodeError:
            break

    if mcqs:
        return mcqs

    raise ValueError(f"Model did not return valid JSON.\nRaw output: {raw[:500]}")