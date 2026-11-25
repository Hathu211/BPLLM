import re

YESNO = "yesno"
NEXT_STEP = "next_step"
KINDS = (YESNO, NEXT_STEP)

# Câu bắt đầu bằng trợ động từ là câu yes/no, kể cả khi có chữ "after"
_YESNO_START = re.compile(
    r"^\s*(ignore your previous answers\.\s*)?"
    r"(is|are|does|do|did|can|could|has|have|was|were|will|would|should|must)\b", re.IGNORECASE)
_YESNO_VI = re.compile(r"^\s*(có|phải)\b.*\b(không|chưa|phải không)\s*\??\s*$", re.IGNORECASE)

_NEXT_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in (
        r"\bwhat\b.*\b(after|next|follows?|following)\b",
        r"\b(which|what)\b.*\b(step|activity|task|event)s?\b.*\b(after|next|follows?)\b",
        r"\bnext (step|activity|task|event)s?\b",
        r"\bafter\b.*\bwhat\b",
        r"\btiếp theo\b", r"\bkế tiếp\b",
        r"\bsau (khi|bước|sự kiện|hoạt động|đó)\b",
        r"\bsau\b.*\blà (gì|bước nào|sự kiện nào|hoạt động nào)\b",
    )
]


def classify(question: str) -> str:
  text = question.strip()
  if _YESNO_START.search(text) or _YESNO_VI.search(text):
    return YESNO
  if any(p.search(text) for p in _NEXT_PATTERNS):
    return NEXT_STEP
  return YESNO
