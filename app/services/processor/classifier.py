from __future__ import annotations
import json
import logging
from dataclasses import dataclass, field

from openai import AzureOpenAI

from app.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class ClassificationResult:
    summary: str
    is_knowledge: bool = False
    knowledge_kind: str | None = None
    topic_key: str | None = None
    confidence: float = 0.5
    knowledge_entities: list[dict] = field(default_factory=list)
    is_workflow_trigger: bool = False
    workflow_slugs: list[str] = field(default_factory=list)
    workflow_reason: str | None = None
    is_alert: bool = False
    alert_reason: str | None = None


def _get_openai_client() -> AzureOpenAI:
    settings = get_settings()
    return AzureOpenAI(
        api_key=settings.azure_openai_api_key,
        azure_endpoint=settings.azure_openai_endpoint,
        api_version=settings.azure_openai_api_version,
    )


def build_classifier_prompt(*, source_type: str, raw_payload: dict, active_workflows: list[dict], entity_types: list[str], topics: list[dict] | None = None) -> tuple[str, str]:
    workflow_list = "\n".join(f"- {w['slug']}: {w.get('description') or w.get('name', '')}" for w in active_workflows) or "No active workflows."
    entity_type_list = ", ".join(entity_types) or "none defined"
    topic_list = "\n".join(f"- {t['key']}: {t.get('label', t['key'])}" for t in (topics or [])) or "No topics defined."

    system_prompt = f"""You are a knowledge processing agent for a marketing engine.
You receive incoming data (emails, calendar events, documents) and classify each item.

For each item, determine ALL that apply:

1. KNOWLEDGE: Does this contain information worth storing in our knowledge graph?
   If yes, set is_knowledge to true and provide:
   - knowledge_kind: one of fact, event, task, deadline, observation
     * fact — a statement of truth about an entity (e.g. "Company X has 50 employees")
     * event — something that happened or is scheduled (e.g. "Meeting with partner on Monday")
     * task — an action item or to-do (e.g. "Follow up with Dan by Friday")
     * deadline — a time-bound requirement (e.g. "Proposal due April 15")
     * observation — a subjective note or impression (e.g. "Partner seems interested in co-marketing")
   - topic_key: the most relevant topic from the list below (or null if none fit)
   - confidence: a float from 0.0 to 1.0 indicating how confident you are this is worth storing
   - knowledge_entities: extract entities (people, companies, topics, etc.) and their relationships

   Available topics:
   {topic_list}

2. WORKFLOW TRIGGER: Should this trigger any of these active workflows?
   Active workflows:
   {workflow_list}
   Only trigger a workflow if the content is clearly relevant to it.

3. ALERT: Is this important enough to notify the user immediately?
   Only flag as alert for time-sensitive or high-importance items.

Known entity types in our graph: {entity_type_list}

Respond with valid JSON matching this exact schema:
{{"summary": "one-line summary", "is_knowledge": true/false, "knowledge_kind": "fact|event|task|deadline|observation" or null, "topic_key": "topic-key" or null, "confidence": 0.0-1.0, "knowledge_entities": [{{"name": "...", "type": "...", "relation": "..."}}], "is_workflow_trigger": true/false, "workflow_slugs": ["slug1"], "workflow_reason": "why" or null, "is_alert": true/false, "alert_reason": "why" or null}}"""

    if source_type == "gmail":
        sender = raw_payload.get("from", "unknown")
        subject = raw_payload.get("subject", "")
        body = raw_payload.get("body", "")
        user_prompt = f"Source: gmail\nFrom: {sender}\nSubject: {subject}\n\n{body}"
    elif source_type == "calendar":
        summary = raw_payload.get("summary", "")
        description = raw_payload.get("description", "")
        start = raw_payload.get("start", "")
        attendees = raw_payload.get("attendees", [])
        attendee_str = ", ".join(a.get("email", "") for a in attendees)
        user_prompt = f"Source: calendar\nEvent: {summary}\nWhen: {start}\nAttendees: {attendee_str}\n\n{description}"
    else:
        file_name = raw_payload.get("file_name", "unknown")
        content = raw_payload.get("content", "")
        user_prompt = f"Source: {source_type}\nFile: {file_name}\n\n{content}"

    if len(user_prompt) > 8000:
        user_prompt = user_prompt[:8000] + "\n\n[TRUNCATED]"

    return system_prompt, user_prompt


def parse_classification(raw: dict) -> ClassificationResult:
    return ClassificationResult(
        summary=raw.get("summary", ""),
        is_knowledge=bool(raw.get("is_knowledge", False)),
        knowledge_kind=raw.get("knowledge_kind"),
        topic_key=raw.get("topic_key"),
        confidence=float(raw.get("confidence", 0.5)),
        knowledge_entities=raw.get("knowledge_entities", []),
        is_workflow_trigger=bool(raw.get("is_workflow_trigger", False)),
        workflow_slugs=raw.get("workflow_slugs", []),
        workflow_reason=raw.get("workflow_reason"),
        is_alert=bool(raw.get("is_alert", False)),
        alert_reason=raw.get("alert_reason"),
    )


def classify_item(*, source_type: str, raw_payload: dict, active_workflows: list[dict], entity_types: list[str], topics: list[dict] | None = None) -> ClassificationResult:
    settings = get_settings()
    client = _get_openai_client()
    system_prompt, user_prompt = build_classifier_prompt(source_type=source_type, raw_payload=raw_payload, active_workflows=active_workflows, entity_types=entity_types, topics=topics)
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
    logger.info("Classifier LLM call: %d prompt tokens, %d completion tokens", response.usage.prompt_tokens, response.usage.completion_tokens)
    parsed = json.loads(raw_text)
    return parse_classification(parsed)
