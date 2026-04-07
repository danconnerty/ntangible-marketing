import re


_ORDINAL_RE = re.compile(r"\b\d+(?:st|nd|rd|th)\b", re.IGNORECASE)
_LABEL_RE = re.compile(r"\b[A-Z]\d+\b")
_HASHTAG_NUM_RE = re.compile(r"#\d+")
_TIME_DATE_RE = re.compile(
    r"\b\d{1,2}:\d{2}\b|\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b|\b\d{4}-\d{2}-\d{2}\b"
)

_CLAIM_PATTERNS = [
    re.compile(r"\$[\d,]+(?:\.\d+)?[KMBkmb]?\+?"),
    re.compile(r"\d[\d,]*(?:\.\d+)?%"),
    re.compile(r"\b\d+ sports\b"),
    re.compile(r"\b\d{1,3}(?:,\d{3})+\+(?=\s|$|[^\w])"),
    re.compile(r"\b\d{1,3}(?:,\d{3})+\b"),
    re.compile(r"\b\d[\d,]*(?:\.\d+)?[KMBkmb]\+?(?=\b|[^\w]|$)"),
    re.compile(r"\b\d{3,}\+(?=\s|$|[^\w])"),
    re.compile(r"\b\d{3,}\b"),
]


def _spans_overlap(start: int, end: int, spans: list[tuple[int, int]]) -> bool:
    return any(not (end <= span_start or start >= span_end) for span_start, span_end in spans)


def extract_claim_numerics(text: str) -> list[str]:
    """Extract numeric claims while ignoring labels, ordinals, and similar noise."""
    if not text:
        return []

    excluded_spans: list[tuple[int, int]] = []
    for pattern in (_ORDINAL_RE, _LABEL_RE, _HASHTAG_NUM_RE, _TIME_DATE_RE):
        excluded_spans.extend((match.start(), match.end()) for match in pattern.finditer(text))

    matches: list[tuple[int, int, str]] = []
    for pattern in _CLAIM_PATTERNS:
        for match in pattern.finditer(text):
            start, end = match.span()
            if _spans_overlap(start, end, excluded_spans):
                continue
            if _spans_overlap(start, end, [(span_start, span_end) for span_start, span_end, _ in matches]):
                continue
            matches.append((start, end, match.group()))

    matches.sort(key=lambda item: item[0])
    return [token for _, _, token in matches]
