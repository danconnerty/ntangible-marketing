from __future__ import annotations

import re
from typing import Any


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "untitled"


def _normalize_keywords(topic: str, target_keywords: list[str]) -> list[str]:
    keywords = [keyword.strip() for keyword in target_keywords if keyword and keyword.strip()]
    if not keywords:
        keywords = [topic.strip()]
    return keywords[:5]


def _word_count(text: str) -> int:
    return len(re.findall(r"\b[\w'-]+\b", text))


def _paragraph(topic: str, audience: str, keyword: str, angle: str, note: str, section: str, idx: int) -> str:
    base = [
        f"{topic} matters because {audience} leaders need a practical way to evaluate what happens when the pressure rises.",
        f"The point of this section is not to hype the idea, but to show how {keyword} changes the next decision in a measurable way.",
        f"{angle} keeps the conversation grounded in outcomes, while the operating detail in section {idx + 1} makes the argument usable in the real world.",
        f"{note} is included here so the article keeps one foot in the evidence and one foot in the operational takeaway.",
        f"When teams think about {section}, they should be asking which part of the process can be repeated, tracked, and explained without turning the message into jargon.",
    ]
    return " ".join(base)


def _build_section(topic: str, audience: str, keyword: str, angle: str, note: str, section: str, idx: int) -> str:
    paragraph_one = _paragraph(topic, audience, keyword, angle, note, section, idx)
    paragraph_two = (
        f"That is why the practical version of {keyword} should show up as a decision tool, not a slogan. "
        f"{topic} becomes easier to trust when the reader can connect the concept to a recruiting, coaching, or partner workflow they already understand. "
        f"{audience.capitalize()} teams can use the frame immediately, because it gives them a cleaner way to explain why the right data matters."
    )
    return f"## {section}\n\n{paragraph_one}\n\n{paragraph_two}"


def _padding_paragraph(topic: str, audience: str, keyword: str, angle: str) -> str:
    return (
        f"{topic} also deserves repetition because the reader is rarely starting from the same place. "
        f"Some {audience} readers want the strategic framing, while others want the practical checklist, and both need to see how {keyword} moves the decision forward. "
        f"{angle} stays useful when it is tied to concrete behavior, a visible outcome, and a clear way to reuse the insight next week. "
        f"The article should therefore keep returning to the same core logic: explain the evidence, make the implication obvious, and point the reader at the next action."
    )


def _markdown_to_html(markdown: str) -> str:
    html_lines: list[str] = []
    paragraphs: list[str] = []
    for line in markdown.splitlines():
        stripped = line.strip()
        if not stripped:
            if paragraphs:
                html_lines.append(f"<p>{' '.join(paragraphs)}</p>")
                paragraphs = []
            continue
        if stripped.startswith("# "):
            if paragraphs:
                html_lines.append(f"<p>{' '.join(paragraphs)}</p>")
                paragraphs = []
            html_lines.append(f"<h1>{stripped[2:].strip()}</h1>")
        elif stripped.startswith("## "):
            if paragraphs:
                html_lines.append(f"<p>{' '.join(paragraphs)}</p>")
                paragraphs = []
            html_lines.append(f"<h2>{stripped[3:].strip()}</h2>")
        else:
            paragraphs.append(stripped)
    if paragraphs:
        html_lines.append(f"<p>{' '.join(paragraphs)}</p>")
    return "\n".join(html_lines)


def generate_blog_draft(
    *,
    topic: str,
    audience: str,
    target_keywords: list[str],
    angle: str | None = None,
    source_notes: list[str] | None = None,
) -> dict[str, Any]:
    keywords = _normalize_keywords(topic, target_keywords)
    primary_keyword = keywords[0]
    angle_text = angle or f"{topic} should be explained through evidence, not hype"
    notes = source_notes or []

    title = f"{topic}: What {audience} Need to Know"
    if primary_keyword and primary_keyword.lower() not in title.lower():
        title = f"{primary_keyword.title()} for {audience.title()}: {topic}"

    meta_description = (
        f"Learn how {primary_keyword} changes the way {audience} evaluate {topic}. "
        f"This article turns the idea into practical guidance, evidence, and next steps."
    )
    meta_description = meta_description[:168].rstrip(".") + "."

    sections = [
        "Why This Matters Now",
        "The Evidence Behind the Argument",
        "How Teams Should Use It",
        "What It Means for NTangible",
        "Next Steps and Practical Takeaways",
    ]
    intro = (
        f"{topic} sits at the intersection of data, trust, and action. "
        f"For {audience}, that means the best explanation is not a slogan. It is a clean story about what changes, why it changes, and how to use it."
    )
    body_parts = [f"# {title}", "", intro, ""]

    for idx, section in enumerate(sections):
        keyword = keywords[idx % len(keywords)]
        note = notes[idx % len(notes)] if notes else f"Core source note for {section.lower()}"
        body_parts.append(_build_section(topic, audience, keyword, angle_text, note, section, idx))
        body_parts.append("")

    conclusion = (
        f"In the end, {topic} matters because it gives {audience} a better decision frame. "
        f"If the reader remembers one thing, it should be that evidence plus clarity beats generic commentary every time. "
        f"That is the standard this article tries to set, and it is the standard the content engine should keep using."
    )
    body_parts.extend(
        [
            "## Final Takeaway",
            "",
            conclusion,
            "",
            f"CTA: If you want to use {primary_keyword} in a way that is specific to your team, partner, or recruiting workflow, start with one clear use case and build from there.",
        ]
    )

    body_markdown = "\n".join(body_parts).strip()
    word_count = _word_count(body_markdown)
    while word_count < 820:
        body_markdown += f"\n\n{_padding_paragraph(topic, audience, primary_keyword, angle_text)}"
        word_count = _word_count(body_markdown)

    headings = sections + ["Final Takeaway"]
    return {
        "title": title,
        "slug": _slugify(title),
        "meta_description": meta_description,
        "topic": topic,
        "audience": audience,
        "angle": angle_text,
        "target_keywords": keywords,
        "headings": headings,
        "body_markdown": body_markdown,
        "body_html": _markdown_to_html(body_markdown),
        "word_count": word_count,
        "excerpt": intro[:220],
    }
