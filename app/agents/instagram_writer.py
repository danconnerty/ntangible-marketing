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


INSTAGRAM_REQUIRED_FIELDS = {
    "caption",
    "content_type",
    "pillar",
    "claim_keys_used",
    "hashtags",
    "intent",
    "cta_type",
    "template_family",
    "asset_plan",
}


def build_instagram_prompt(
    content_type: str,
    pillar: str,
    claims: list[str],
    context: str | None,
) -> dict[str, str]:
    brand = get_brand_voice()
    pillars = get_content_pillars()
    claims_config = get_approved_claims()
    platform = get_platform_config("instagram")["instagram"]

    pillar_data = pillars["pillars"][pillar]
    claims_lines: list[str] = []
    for key in claims:
        claim = claims_config["claims"].get(key)
        if claim:
            claims_lines.append(f"- {key}: {claim['text']} (Source: {claim['source']})")

    claims_block = "\n".join(claims_lines) if claims_lines else "No approved claims provided."
    system_prompt = f"""You are writing Instagram content for NTangible.

Brand personality: {brand['voice']['personality']}

DO:
{chr(10).join('- ' + item for item in brand['voice']['do'])}

DON'T:
{chr(10).join('- ' + item for item in brand['voice']['dont'])}

BANNED PHRASES:
{chr(10).join('- ' + item for item in brand['banned_phrases'])}

TRADEMARK RULES:
- Always write Clutch Factor™ with the ™ symbol
- Always capitalize NTangible Score and The Pressure Test correctly

INSTAGRAM CONSTRAINTS:
- Maximum {platform['max_caption_chars']} caption characters including CTA and hashtags
- Use exactly one hook/body/CTA structure
- Use 6-10 hashtags and place them at the end
- Voice must be visual-first, bold, and athlete-facing
- Output must be template-driven and ready for Canva autofill

AVAILABLE IMAGE TEMPLATES (always include image_request for Instagram):
- athlete_spotlight: data fields = athlete_name, sport, cf_score, school, event_name
- commitment_post: data fields = athlete_name, sport, cf_score, school, committed_to
- clutch_certified: data fields = athlete_name, cf_score, tier_label
- event_leaderboard: data fields = event_name, top_athletes, date
- bold_statement: data fields = quote_text, attribution

FACTUAL CLAIMS RULE:
Do not invent statistics, percentages, dollar amounts, client names, or outcomes.
Use only the approved claims provided below.

APPROVED CLAIMS:
{claims_block}

Return exactly one JSON object with:
caption, content_type, pillar, claim_keys_used, hashtags, intent, cta_type, template_family, asset_plan, image_request

image_request must be an object with template_family (one of the template names above) and data (object whose keys match that template's data fields). Always include image_request for Instagram posts.
"""

    user_prompt = f"""Write one Instagram {content_type} draft for the "{pillar}" pillar.

Pillar description: {pillar_data['description']}
Example angles: {', '.join(pillar_data['example_angles'])}
{f"Context: {context}" if context else "Context: None"}

The caption must have a punchy hook, short body, and exactly one CTA. The asset_plan must describe the text fields and slide structure needed for a template-driven Canva render.
"""
    return {"system": system_prompt, "user": user_prompt}


def parse_instagram_response(raw: dict[str, Any]) -> dict[str, Any]:
    missing = INSTAGRAM_REQUIRED_FIELDS - set(raw)
    if missing:
        raise ValueError(f"Missing fields in Instagram response: {sorted(missing)}")
    return raw


def generate_instagram_post(
    content_type: str,
    pillar: str,
    claims: list[str],
    context: str | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    settings = get_settings()
    prompt = build_instagram_prompt(content_type, pillar, claims, context)
    client = AzureOpenAI(
        api_key=settings.azure_openai_api_key,
        azure_endpoint=settings.azure_openai_endpoint,
        api_version=settings.azure_openai_api_version,
    )

    start = time.time()
    response = client.chat.completions.create(
        model=settings.azure_openai_model,
        max_completion_tokens=1800,
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
    parsed = parse_instagram_response(json.loads(raw_text))
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
