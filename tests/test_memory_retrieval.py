import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

from app.models.brain import KnowledgeNode
from app.models.review import ContentJob, DraftVariant
from app.models.trigger import TriggerEvent, TriggerType
from app.models.workflow import Platform, Workflow, WorkflowMode, WorkflowVersion, DraftState
from app.services.memory_retrieval import MemoryRetrievalService


def _knowledge_node(
    *,
    status: str = "approved",
    platform: str = "x",
    workflow_slug: str = "x-recruiting",
    content: str = "Pressure data helps coaches trust recruiting decisions.",
    title: str = "Recruiting pressure post",
) -> KnowledgeNode:
    return KnowledgeNode(
        id=uuid.uuid4(),
        kind="observation",
        title=title,
        content=content,
        status=status,
        metadata_={
            "source_kind": "draft_variant",
            "source_id": str(uuid.uuid4()),
            "platform": platform,
            "workflow_slug": workflow_slug,
            "hashtags": [],
            "search_text": f"{title} {content}",
        },
        created_at=datetime.now(timezone.utc),
    )


def test_search_ranks_matching_platform_bucket_and_overlap():
    service = MemoryRetrievalService(MagicMock())
    preferred = _knowledge_node(platform="linkedin")
    weaker = _knowledge_node(
        platform="linkedin",
        workflow_slug="linkedin-brand",
        content="Brand awareness matters when markets get noisy.",
        title="Brand post",
    )
    service._load_candidate_items = MagicMock(return_value=[weaker, preferred])

    results = service.search(
        query="recruiting pressure",
        platform=Platform.LINKEDIN,
        bucket=_BucketCompat("approved"),
        limit=5,
    )

    assert results[0]["id"] == str(preferred.id)
    assert results[0]["platform"] == "linkedin"
    assert results[0]["bucket"] == "approved"
    assert results[0]["score"] > results[1]["score"]


def test_build_generation_context_returns_approved_and_rejected_examples():
    service = MemoryRetrievalService(MagicMock())
    approved = _knowledge_node(status="approved", workflow_slug="tuesday-linkedin")
    rejected = _knowledge_node(
        status="rejected",
        workflow_slug="tuesday-linkedin",
        content="Corporate boilerplate with no proof.",
        title="Rejected corporate example",
    )
    service.search = MagicMock(
        side_effect=[
            [
                {
                    "id": str(approved.id),
                    "title": approved.title,
                    "content": approved.content,
                    "bucket": approved.status,
                    "workflow_slug": (approved.metadata_ or {}).get("workflow_slug"),
                    "platform": (approved.metadata_ or {}).get("platform"),
                    "metadata": approved.metadata_,
                    "score": 11,
                }
            ],
            [
                {
                    "id": str(rejected.id),
                    "title": rejected.title,
                    "content": rejected.content,
                    "bucket": rejected.status,
                    "workflow_slug": (rejected.metadata_ or {}).get("workflow_slug"),
                    "platform": (rejected.metadata_ or {}).get("platform"),
                    "metadata": rejected.metadata_,
                    "score": 6,
                }
            ],
        ]
    )

    context = service.build_generation_context(
        query="recruiting pressure",
        platform=Platform.LINKEDIN,
        approved_limit=3,
        rejected_limit=2,
    )

    assert context["approved_examples"][0]["id"] == str(approved.id)
    assert context["rejected_examples"][0]["id"] == str(rejected.id)
    assert str(approved.id) in context["memory_ids"]
    assert str(rejected.id) in context["memory_ids"]


def test_sync_control_room_memory_includes_newsletter_metadata_in_search_text():
    workflow_id = uuid.uuid4()
    trigger_id = uuid.uuid4()
    job_id = uuid.uuid4()
    version_id = uuid.uuid4()

    workflow = Workflow(
        id=workflow_id,
        name="Monthly Newsletter",
        slug="monthly-newsletter",
        description="Monthly owned-media workflow",
        mode=WorkflowMode.MANUAL,
        platform=Platform.NEWSLETTER,
        content_type="monthly_newsletter",
        enabled=True,
    )
    version = WorkflowVersion(
        id=version_id,
        workflow_id=workflow_id,
        version_number=1,
        config={},
        author="human",
    )
    trigger = TriggerEvent(
        id=trigger_id,
        trigger_type=TriggerType.CALENDAR,
        workflow_id=workflow_id,
        source_payload={"request": "April newsletter", "campaign": "spring"},
    )
    job = ContentJob(
        id=job_id,
        workflow_id=workflow_id,
        workflow_version_id=version.id,
        trigger_event_id=trigger_id,
        status="completed",
    )
    draft = DraftVariant(
        id=uuid.uuid4(),
        content_job_id=job_id,
        platform=Platform.NEWSLETTER,
        content="Newsletter body for the April edition.",
        hashtags=[],
        state=DraftState.MANUAL_READY,
        timezone="America/Toronto",
        compliance_result={
            "subject": "April pressure data coaches should use",
            "preview_text": "What the latest dataset changed.",
            "segment": "coaches_front_offices",
        },
    )

    db = MagicMock()

    def _query(model):
        query = MagicMock()
        if model is DraftVariant:
            query.order_by.return_value.limit.return_value.all.return_value = [draft]
        elif model is ContentJob:
            query.filter.return_value.all.return_value = [job]
        elif model is Workflow:
            query.filter.return_value.all.return_value = [workflow]
        elif model is TriggerEvent:
            query.filter.return_value.all.return_value = [trigger]
        elif model is KnowledgeNode:
            query.filter.return_value.first.return_value = None
        return query

    db.query.side_effect = _query
    service = MemoryRetrievalService(db)
    service.sync_legacy_memory = MagicMock(return_value=0)
    service._upsert_memory_item = MagicMock(return_value=1)

    created = service.sync_control_room_memory(limit=5)

    assert created == 1
    kwargs = service._upsert_memory_item.call_args.kwargs
    assert kwargs["platform"] == Platform.NEWSLETTER
    assert "April pressure data coaches should use" in kwargs["search_text"]
    assert "What the latest dataset changed." in kwargs["search_text"]
    assert "coaches_front_offices" in kwargs["search_text"]


class _BucketCompat:
    """Test helper matching the service's _BucketCompat shim."""

    def __init__(self, value: str):
        self.value = value


def _fact_node(*, title="NTangible fact", content="Dan Connerty is CEO of NTangible", topic="work"):
    return KnowledgeNode(
        id=uuid.uuid4(),
        kind="fact",
        title=title,
        content=content,
        status="active",
        metadata_={"source": "agent_engine", "search_text": f"{title} {content}"},
        created_at=datetime.now(timezone.utc),
    )


def test_search_brain_facts_returns_matching_facts():
    service = MemoryRetrievalService(MagicMock())
    fact1 = _fact_node(title="Dan Connerty Is CEO", content="Dan Connerty founded NTangible.")
    fact2 = _fact_node(title="Vercel Hosting", content="NTangible is hosted on Vercel hobby plan.")
    service.bq = MagicMock()
    service.bq.list_knowledge_by_kind = MagicMock(return_value=[fact1, fact2])

    results = service._search_brain_facts(query="Dan Connerty NTangible", limit=5)

    assert len(results) >= 1
    assert results[0]["id"] == str(fact1.id)
    assert results[0]["title"] == "Dan Connerty Is CEO"


def test_search_brain_facts_not_filtered_by_platform_or_bucket():
    service = MemoryRetrievalService(MagicMock())
    fact = _fact_node(title="Alliance Partnership", content="Alliance Fastpitch partnered with NTangible.")
    service.bq = MagicMock()
    service.bq.list_knowledge_by_kind = MagicMock(return_value=[fact])

    results = service._search_brain_facts(query="Alliance partnership", limit=5)

    assert len(results) == 1


def test_build_generation_context_includes_brain_facts():
    service = MemoryRetrievalService(MagicMock())
    fact = _fact_node()
    approved = _knowledge_node(status="approved")
    rejected = _knowledge_node(status="rejected")

    service._load_candidate_items = MagicMock(return_value=[approved, rejected])
    service.bq = MagicMock()
    service.bq.list_knowledge_by_kind = MagicMock(return_value=[fact])

    result = service.build_generation_context(
        query="NTangible",
        platform=Platform.LINKEDIN,
        workflow_slug="linkedin-thought-leadership",
    )

    assert "brain_facts" in result
    assert "approved_examples" in result
    assert "rejected_examples" in result
