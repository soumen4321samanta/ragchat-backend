"""
Generates open-ended Question & Answer pairs (not MCQ) from a document's
full text, automatically writing the questions/answers in the same
language as the document (currently supports Bengali and English).
"""
import json
from django.conf import settings
from .llm import get_client

# Unicode range for Bengali script: U+0980 to U+09FF
BENGALI_RANGE = (0x0980, 0x09FF)


def detect_language(text: str) -> str:
    """
    Lightweight, deterministic language detection: count how many
    characters fall in the Bengali Unicode block vs total letters.
    No LLM call needed -- fast and free.
    Returns 'bn' (Bengali) or 'en' (English/other).
    """
    bengali_count = 0
    letter_count = 0

    for ch in text:
        if ch.isalpha():
            letter_count += 1
            code = ord(ch)
            if BENGALI_RANGE[0] <= code <= BENGALI_RANGE[1]:
                bengali_count += 1

    if letter_count == 0:
        return "en"

    # If more than 25% of letters are Bengali script, treat the doc as Bengali
    return "bn" if (bengali_count / letter_count) > 0.25 else "en"


QA_SYSTEM_PROMPT_EN = (
    "You are a study guide generator. Based ONLY on the document text given "
    "to you, write clear question-and-answer pairs that help a student "
    "review the material. Write BOTH the questions and answers in English. "
    "Respond with ONLY a raw JSON array, no markdown fences, no extra text. "
    "Each item must have exactly this shape: "
    '{"question": "...", "answer": "..."}'
)

QA_SYSTEM_PROMPT_BN = (
    "তুমি একজন স্টাডি গাইড তৈরিকারী। ব্যবহারকারীর দেওয়া ডকুমেন্টের টেক্সট থেকে "
    "শুধুমাত্র সেই তথ্য ব্যবহার করে পরিষ্কার প্রশ্ন ও উত্তর তৈরি করো, যা একজন "
    "শিক্ষার্থীকে বিষয়টি রিভিশন করতে সাহায্য করবে। প্রশ্ন এবং উত্তর দুটোই অবশ্যই "
    "বাংলা ভাষায় লিখতে হবে। শুধুমাত্র একটি raw JSON array আকারে উত্তর দাও, কোনো "
    "markdown ফরম্যাটিং বা অতিরিক্ত টেক্সট ছাড়া। প্রতিটি আইটেমের গঠন ঠিক এরকম হবে: "
    '{"question": "...", "answer": "..."}'
)


def generate_qa_pairs(document_text: str, num_questions: int = 8) -> tuple[list[dict], str]:
    """
    Returns (qa_pairs, language) where language is 'bn' or 'en'.
    """
    language = detect_language(document_text)
    system_prompt = QA_SYSTEM_PROMPT_BN if language == "bn" else QA_SYSTEM_PROMPT_EN

    user_prompt = (
        f"Document text:\n{document_text}\n\n"
        f"Generate exactly {num_questions} question-answer pairs from this text."
    )

    client = get_client()
    response = client.chat.completions.create(
        model=settings.GROQ_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.4,
        max_tokens=2048,
    )

    raw = response.choices[0].message.content.strip()

    if raw.startswith('```'):
        raw = raw.strip('`')
        if raw.lower().startswith('json'):
            raw = raw[4:]
        raw = raw.strip()

    qa_pairs = _parse_qa_json(raw)
    return qa_pairs, language


def _parse_qa_json(raw: str) -> list[dict]:
    """Same defensive parsing strategy as quiz_generator.py, since Groq
    models sometimes return JSON Lines instead of a proper JSON array."""
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    pairs = []
    for line in raw.splitlines():
        line = line.strip().rstrip(',')
        if not line:
            continue
        try:
            pairs.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    if pairs:
        return pairs

    decoder = json.JSONDecoder()
    idx = 0
    raw_stripped = raw.strip()
    while idx < len(raw_stripped):
        sub = raw_stripped[idx:].lstrip()
        if not sub:
            break
        skip = len(raw_stripped) - len(sub)
        try:
            obj, end = decoder.raw_decode(sub)
            pairs.append(obj)
            idx += skip + end
        except json.JSONDecodeError:
            break

    if pairs:
        return pairs

    raise ValueError(f"Model did not return valid JSON.\nRaw output: {raw[:500]}")