import json
import logging
import time
from typing import Any

import anthropic

from app.config import (
    get_approved_claims,
    get_brand_voice,
    get_content_pillars,
    get_platform_config,
    get_settings,
)


logger = logging.getLogger(__name__)

REQUIRED_FIELDS = {
    "content",
    "content_type",
    "pillar",
    "claim_keys_used",
    "hashtags",
    "media_needed",
    "intent",
}


def build_prompt(
    content_type: str,
    pillar: str,
    claims: list[str],
    context: str | None,
) -> dict[str, str]:
    brand = get_brand_voice()
    pillars = get_content_pillars()
    claims_config = get_approved_claims()
    platform = get_platform_config("x")

    pillar_data = pillars["pillars"][pillar]
    claims_lines: list[str] = []
    for key in claims:
        claim = claims_config["claims"].get(key)
        if claim:
            claims_lines.append(f"- {key}: {claim['text']} (Source: {claim['source']})")

    claims_text = "\n".join(claims_lines)
    system_prompt = f"""You are a social media content writer for NTangible, a sports tech company that measures athlete mental performance under pressure using Clutch Factor™.

BRAND VOICE:
{brand['voice']['personality']}

DO:
{chr(10).join('- ' + rule for rule in brand['voice']['do'])}

DON'T:
{chr(10).join('- ' + rule for rule in brand['voice']['dont'])}

BANNED PHRASES (never use these):
{chr(10).join('- "' + phrase + '"' for phrase in brand['banned_phrases'])}

TRADEMARK RULES:
- Always write "Clutch Factor™" with the ™ symbol
- Always capitalize "NTangible Score" and "The Pressure Test" correctly

PLATFORM CONSTRAINTS (X/Twitter):
- Maximum {platform['x']['single_tweet_max_chars']} characters
- Maximum {platform['x']['max_hashtags']} hashtags
- Single tweet only (no threads)

FACTUAL CLAIMS RULE:
Do not invent statistics, percentages, dollar amounts, client names, or outcomes. Use ONLY the approved claims provided below. If no claims are provided, do not include any numeric assertions.

{f"APPROVED CLAIMS YOU MAY USE:{chr(10)}{claims_text}" if claims_text else "NO APPROVED CLAIMS PROVIDED — do not include any numeric facts."}

VERIFIED CLIENTS (only these may be named):
{chr(10).join('- ' + client for client in brand['verified_clients'])}

OUTPUT FORMAT:
Return exactly 3 JSON objects separated by newlines. Each must have these fields:
- content: the tweet text (string)
- content_type: "{content_type}"
- pillar: "{pillar}"
- claim_keys_used: list of approved claim keys actually referenced in the tweet (may be empty)
- hashtags: list of 0-{platform['x']['max_hashtags']} hashtags
- media_needed: boolean
- intent: "brand" | "partner" | "revenue"
"""

    user_prompt = f"""Generate 3 variations of a {content_type} tweet for the "{pillar}" content pillar.

Pillar description: {pillar_data['description']}
Example angles: {', '.join(pillar_data['example_angles'])}

{f"Context: {context}" if context else ""}

Return exactly 3 JSON objects, one per line. Each must be valid JSON."""

    return {"system": system_prompt, "user": user_prompt}


def parse_generation_response(raw: dict[str, Any]) -> dict[str, Any]:
    missing = REQUIRED_FIELDS - set(raw)
    if missing:
        raise ValueError(f"Missing fields in generation response: {sorted(missing)}")
    return raw


def generate_tweets(
    content_type: str,
    pillar: str,
    claims: list[str],
    context: str | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    settings = get_settings()
    prompt = build_prompt(content_type, pillar, claims, context)
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    start = time.time()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=prompt["system"],
        messages=[{"role": "user", "content": prompt["user"]}],
    )
    duration_ms = int((time.time() - start) * 1000)
    raw_text = response.content[0].text

    variations: list[dict[str, Any]] = []
    for line in raw_text.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            parsed = json.loads(line)
            variations.append(parse_generation_response(parsed))
        except (ValueError, json.JSONDecodeError) as exc:
            logger.warning("Skipping malformed generation line: %s", exc)

    log_data = {
        "prompt_snapshot": prompt["system"] + "\n---\n" + prompt["user"],
        "response": {"raw_text": raw_text, "parsed_count": len(variations)},
        "model": "claude-sonnet-4-6",
        "tokens_in": response.usage.input_tokens,
        "tokens_out": response.usage.output_tokens,
        "cost_estimate": (response.usage.input_tokens * 0.003 + response.usage.output_tokens * 0.015) / 1000,
        "duration_ms": duration_ms,
    }
    return variations, log_data
