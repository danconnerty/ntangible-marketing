import json
import time
from typing import Any

from openai import AzureOpenAI

from app.config import (
    get_approved_claims,
    get_brand_voice,
    get_content_pillars,
    get_platform_config,
    get_settings,
)


NEWSLETTER_REQUIRED_FIELDS = {
    "segment",
    "subject",
    "preview_text",
    "hook",
    "proof_point",
    "product_update",
    "cta",
    "body_markdown",
}


def build_newsletter_prompt(
    content_type: str,
    pillar: str,
    claims: list[str],
    context: str | None,
    segment: str,
) -> dict[str, str]:
    brand = get_brand_voice()
    pillars = get_content_pillars()
    claims_config = get_approved_claims()
    platform = get_platform_config("newsletter")["newsletter"]

    pillar_data = pillars["pillars"][pillar]
    claims_lines: list[str] = []
    for key in claims:
        claim = claims_config["claims"].get(key)
        if claim:
            claims_lines.append(f"- {key}: {claim['text']} (Source: {claim['source']})")

    claims_block = "\n".join(claims_lines) if claims_lines else "No approved claims provided."
    system_prompt = f"""You are writing NTangible's monthly newsletter for the audience segment "{segment}".

Brand personality: {brand['voice']['personality']}

DO:
{chr(10).join('- ' + item for item in brand['voice']['do'])}

DON'T:
{chr(10).join('- ' + item for item in brand['voice']['dont'])}

BANNED PHRASES:
{chr(10).join('- ' + item for item in brand['banned_phrases'])}

NEWSLETTER CONSTRAINTS:
- Subject line max {platform['subject_max_chars']} characters
- Preview text max {platform['preview_max_chars']} characters
- Body length between {platform['min_body_chars']} and {platform['max_body_chars']} characters
- Include exactly one hook, one proof_point, one product_update, and one cta
- No fluff, filler, or generic company updates

FACTUAL CLAIMS RULE:
Do not invent statistics, percentages, dollar amounts, client names, or outcomes.
Use only the approved claims provided below.

APPROVED CLAIMS:
{claims_block}

Return exactly one JSON object with:
segment, subject, preview_text, hook, proof_point, product_update, cta, body_markdown, body_html
"""

    user_prompt = f"""Write one {content_type} newsletter draft for the "{pillar}" pillar.

Audience segment: {segment}
Pillar description: {pillar_data['description']}
Example angles: {', '.join(pillar_data['example_angles'])}
{f"Context: {context}" if context else "Context: None"}

The final draft must teach something, prove something, and give the operator a clean CTA. The body_markdown should read like a real newsletter draft rather than bullet notes.
"""
    return {"system": system_prompt, "user": user_prompt}


def parse_newsletter_response(raw: dict[str, Any]) -> dict[str, Any]:
    missing = NEWSLETTER_REQUIRED_FIELDS - set(raw)
    if missing:
        raise ValueError(f"Missing fields in newsletter response: {sorted(missing)}")
    return raw


def generate_newsletter_draft(
    content_type: str,
    pillar: str,
    claims: list[str],
    context: str | None,
    segment: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    settings = get_settings()
    prompt = build_newsletter_prompt(content_type, pillar, claims, context, segment)
    client = AzureOpenAI(
        api_key=settings.azure_openai_api_key,
        azure_endpoint=settings.azure_openai_endpoint,
        api_version=settings.azure_openai_api_version,
    )

    start = time.time()
    response = client.chat.completions.create(
        model=settings.azure_openai_model,
        max_completion_tokens=2200,
        messages=[
            {"role": "system", "content": prompt["system"]},
            {"role": "user", "content": prompt["user"]},
        ],
    )
    duration_ms = int((time.time() - start) * 1000)
    raw_text = response.choices[0].message.content.strip()
    if raw_text.startswith("```"):
        raw_text = raw_text.split("\n", 1)[1] if "\n" in raw_text else raw_text[3:]
        if raw_text.endswith("```"):
            raw_text = raw_text[:-3].strip()
    parsed = parse_newsletter_response(json.loads(raw_text))
    log_data = {
        "prompt_snapshot": prompt["system"] + "\n---\n" + prompt["user"],
        "response": {"raw_text": raw_text},
        "model": settings.azure_openai_model,
        "tokens_in": response.usage.prompt_tokens,
        "tokens_out": response.usage.completion_tokens,
        "cost_estimate": (response.usage.prompt_tokens * 0.00005 + response.usage.completion_tokens * 0.0004) / 1000,
        "duration_ms": duration_ms,
    }
    return parsed, log_data
