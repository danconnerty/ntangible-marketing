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


LINKEDIN_REQUIRED_FIELDS = {
    "content",
    "content_type",
    "pillar",
    "claim_keys_used",
    "hashtags",
    "media_needed",
    "intent",
}


def build_linkedin_prompt(
    content_type: str,
    pillar: str,
    claims: list[str],
    context: str | None,
) -> dict[str, str]:
    brand = get_brand_voice()
    pillars = get_content_pillars()
    claims_config = get_approved_claims()
    platform = get_platform_config("linkedin")["linkedin"]

    pillar_data = pillars["pillars"][pillar]
    claims_lines: list[str] = []
    for key in claims:
        claim = claims_config["claims"].get(key)
        if claim:
            claims_lines.append(f"- {key}: {claim['text']} (Source: {claim['source']})")

    claims_block = "\n".join(claims_lines) if claims_lines else "No approved claims provided."
    system_prompt = f"""You are writing a LinkedIn company page post for NTangible.

Voice: Professional but not corporate. Founder-in-the-arena. Short paragraphs. Data-backed claims.
Brand voice: {brand['voice']['personality']}

DO:
{chr(10).join('- ' + item for item in brand['voice']['do'])}

DON'T:
{chr(10).join('- ' + item for item in brand['voice']['dont'])}

BANNED PHRASES:
{chr(10).join('- ' + item for item in brand['banned_phrases'])}

TRADEMARK RULES:
- Always write Clutch Factor™ with the ™ symbol
- Always capitalize NTangible Score and The Pressure Test correctly

PLATFORM CONSTRAINTS (LINKEDIN):
- Maximum {platform['max_chars']} characters
- 3-5 hashtags max
- Professional but not corporate
- Short paragraphs
- Soft CTA style only

AVAILABLE IMAGE TEMPLATES (include image_request for visual content):
- thought_leadership_header: data fields = headline, subtitle
- partner_announcement: data fields = partner_name, partner_logo_url, headline

FACTUAL CLAIMS RULE:
Do not invent statistics, percentages, dollar amounts, client names, or outcomes.
Use only the approved claims provided below.

APPROVED CLAIMS:
{claims_block}

Return exactly one JSON object with:
content, content_type, pillar, claim_keys_used, hashtags, media_needed, intent, image_request

image_request: (ONLY when media_needed is true) object with template_family (one of the template names above) and data (object whose keys match that template's data fields). Omit this field entirely when media_needed is false.
"""

    user_prompt = f"""Write one {content_type} LinkedIn post for the "{pillar}" pillar.

Pillar description: {pillar_data['description']}
Example angles: {', '.join(pillar_data['example_angles'])}
{f"Context: {context}" if context else "Context: None"}
"""
    return {"system": system_prompt, "user": user_prompt}


def parse_linkedin_response(raw: dict[str, Any]) -> dict[str, Any]:
    missing = LINKEDIN_REQUIRED_FIELDS - set(raw)
    if missing:
        raise ValueError(f"Missing fields in LinkedIn response: {sorted(missing)}")
    return raw


def generate_linkedin_post(
    content_type: str,
    pillar: str,
    claims: list[str],
    context: str | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    settings = get_settings()
    prompt = build_linkedin_prompt(content_type, pillar, claims, context)
    client = AzureOpenAI(
        api_key=settings.azure_openai_api_key,
        azure_endpoint=settings.azure_openai_endpoint,
        api_version=settings.azure_openai_api_version,
    )

    start = time.time()
    response = client.chat.completions.create(
        model=settings.azure_openai_model,
        max_completion_tokens=1400,
        messages=[
            {"role": "system", "content": prompt["system"]},
            {"role": "user", "content": prompt["user"]},
        ],
    )
    duration_ms = int((time.time() - start) * 1000)
    raw_text = response.choices[0].message.content.strip()
    # Strip markdown code fences if Claude wrapped the JSON
    if raw_text.startswith("```"):
        raw_text = raw_text.split("\n", 1)[1] if "\n" in raw_text else raw_text[3:]
        if raw_text.endswith("```"):
            raw_text = raw_text[:-3].strip()
    parsed = parse_linkedin_response(json.loads(raw_text))
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
