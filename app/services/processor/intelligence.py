"""Stage 2: Intelligence reasoning. Given extracted knowledge + existing graph context,
reasons about relationships, contradictions, and implications."""
from __future__ import annotations
import json
import logging
from dataclasses import dataclass, field
from openai import AzureOpenAI
from app.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class IntelligenceResult:
    new_edges: list[dict] = field(default_factory=list)
    updated_knowledge: list[dict] = field(default_factory=list)
    contradictions: list[dict] = field(default_factory=list)
    implications: str | None = None


def _get_openai_client() -> AzureOpenAI:
    settings = get_settings()
    return AzureOpenAI(
        api_key=settings.azure_openai_api_key,
        azure_endpoint=settings.azure_openai_endpoint,
        api_version=settings.azure_openai_api_version,
    )


def build_intelligence_prompt(*, stage1_output: dict, graph_context: dict) -> tuple[str, str]:
    system_prompt = """You are an intelligence analyst for a knowledge graph. You receive:
1. Newly extracted knowledge (from Stage 1)
2. Existing graph context for the entities mentioned

Your job is to reason about HOW this new knowledge connects to what's already known.

Determine:
- new_edges: What new relationships should be created? Include both entity edges (between entities) and knowledge edges (between knowledge nodes — supports, contradicts, depends_on, updates, causes, related_to).
- updated_knowledge: Should any existing knowledge nodes be marked as superseded or updated?
- contradictions: Does the new information conflict with anything already known?
- implications: What does this mean in the broader context? (Free text, stored as an observation)

Respond with valid JSON matching this exact schema:
{"new_edges": [{"source": "name", "target": "name", "relation": "relation_type", "confidence": 0.0-1.0, "edge_type": "entity|knowledge"}], "updated_knowledge": [{"id": "uuid", "update": "description"}], "contradictions": [{"existing_id": "uuid", "description": "what conflicts"}], "implications": "free text reasoning" or null}

If there are no meaningful connections, return empty arrays and null implications."""

    entities_context = ""
    for ent in graph_context.get("entities", []):
        edges_str = ", ".join(f"{e.get('relation', '?')} → {e.get('target', '?')}" for e in ent.get("edges", []))
        knowledge_str = "\n    ".join(f"- [{k.get('kind', '?')}] {k.get('title', '?')}" for k in ent.get("knowledge", []))
        entities_context += f"\n  {ent['name']} ({ent.get('type', '?')}):"
        if edges_str:
            entities_context += f"\n    Edges: {edges_str}"
        if knowledge_str:
            entities_context += f"\n    Known facts:\n    {knowledge_str}"

    user_prompt = f"""NEW KNOWLEDGE (from Stage 1):
Summary: {stage1_output.get('summary', '')}
Kind: {stage1_output.get('knowledge_kind', 'unknown')}
Entities extracted: {json.dumps(stage1_output.get('entities', []))}

EXISTING GRAPH CONTEXT:{entities_context or ' (no existing context for these entities)'}"""

    if len(user_prompt) > 6000:
        user_prompt = user_prompt[:6000] + "\n\n[TRUNCATED]"

    return system_prompt, user_prompt


def parse_intelligence_output(raw: dict) -> IntelligenceResult:
    return IntelligenceResult(
        new_edges=raw.get("new_edges", []),
        updated_knowledge=raw.get("updated_knowledge", []),
        contradictions=raw.get("contradictions", []),
        implications=raw.get("implications"),
    )


def run_intelligence_stage(*, stage1_output: dict, graph_context: dict) -> IntelligenceResult:
    settings = get_settings()
    client = _get_openai_client()
    system_prompt, user_prompt = build_intelligence_prompt(stage1_output=stage1_output, graph_context=graph_context)
    response = client.chat.completions.create(
        model=settings.azure_openai_model,
        messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
        max_completion_tokens=512,
        temperature=0.1,
    )
    raw_text = response.choices[0].message.content.strip()
    if raw_text.startswith("```"):
        lines = raw_text.split("\n")
        raw_text = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])
    logger.info("Intelligence LLM call: %d prompt tokens, %d completion tokens", response.usage.prompt_tokens, response.usage.completion_tokens)
    parsed = json.loads(raw_text)
    return parse_intelligence_output(parsed)
