import uuid
from datetime import date
from types import SimpleNamespace

import pytest

from app.agents.campaign_planner import CampaignPlannerAgent
from app.models.brain import EntityEdge, EntityNode, KnowledgeNode
from app.models.trigger import TriggerEvent, TriggerType
from app.models.workflow import Platform, Workflow, WorkflowMode, WorkflowVersion
from app.schemas.workflow_config import WorkflowVersionConfig
from app.services.brain_query import BrainQuery
from app.services.campaign_service import CampaignService, _CampaignContext, _WorkflowContext
from app.services.platform_generation import GeneratedCandidate
from app.services.prompt_assembler import PromptAssembler
from app.services.workflow_engine import WorkflowEngine


class FakeDB:
    def __init__(self):
        self.added = []
        self.flush_count = 0

    def add(self, obj):
        self.added.append(obj)

    def flush(self):
        self.flush_count += 1

    def query(self, *args, **kwargs):
        return _FakeQuery()


class _FakeQuery:
    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return None

    def all(self):
        return []

    def limit(self, n):
        return self

    def count(self):
        return 0


def _make_campaign_entity(**kwargs) -> EntityNode:
    entity_id = kwargs.pop("id", uuid.uuid4())
    slug = kwargs.pop("slug", "spring-coaches-push")
    canonical_name = kwargs.pop("canonical_name", "Spring Coaches Push")
    status = kwargs.pop("status", "active")
    metadata = kwargs.pop("metadata_", {
        "name": "Spring Coaches Push",
        "objective": "Drive clinic registrations",
        "audience": "Travel ball coaches",
        "theme": "Proof over promises",
    })
    entity = EntityNode(
        id=entity_id,
        entity_type="campaign",
        canonical_name=canonical_name,
        slug=slug,
        status=status,
        metadata_=metadata,
    )
    return entity


def _make_workflow_entity(**kwargs) -> EntityNode:
    entity_id = kwargs.pop("id", uuid.uuid4())
    slug = kwargs.pop("slug", "tuesday-linkedin-tl")
    canonical_name = kwargs.pop("canonical_name", "Tuesday LinkedIn TL")
    metadata = kwargs.pop("metadata_", {
        "name": "Tuesday LinkedIn TL",
        "platform": "linkedin",
        "content_type": "thought_leadership",
        "enabled": True,
    })
    entity = EntityNode(
        id=entity_id,
        entity_type="workflow",
        canonical_name=canonical_name,
        slug=slug,
        status="active",
        metadata_=metadata,
    )
    return entity


def _make_scope_edge(campaign_id: uuid.UUID, workflow_entity_id: uuid.UUID, role: str = "awareness") -> EntityEdge:
    return EntityEdge(
        id=uuid.uuid4(),
        source_id=campaign_id,
        target_id=workflow_entity_id,
        source_type="entity",
        target_type="entity",
        relation="scopes",
        metadata_={"role": role},
    )


def test_campaign_entity_fields():
    campaign = _make_campaign_entity()
    assert campaign.entity_type == "campaign"
    assert campaign.slug == "spring-coaches-push"
    assert campaign.status == "active"
    assert campaign.metadata_["objective"] == "Drive clinic registrations"
    assert campaign.metadata_["audience"] == "Travel ball coaches"
    assert campaign.metadata_["theme"] == "Proof over promises"


def test_campaign_context_adapter():
    campaign = _make_campaign_entity()
    ctx = _CampaignContext(campaign)
    assert ctx.name == "Spring Coaches Push"
    assert ctx.slug == "spring-coaches-push"
    assert ctx.objective == "Drive clinic registrations"
    assert ctx.audience == "Travel ball coaches"
    assert ctx.theme == "Proof over promises"
    assert ctx.status.value == "active"


def test_campaign_planner_builds_manual_request():
    campaign = _make_campaign_entity()
    workflow_entity = _make_workflow_entity()
    workflow = Workflow(
        id=uuid.uuid4(),
        name="Tuesday LinkedIn TL",
        slug="tuesday-linkedin-tl",
        description="Thought leadership",
        mode=WorkflowMode.MANUAL,
        platform=Platform.LINKEDIN,
        content_type="thought_leadership",
        enabled=True,
    )

    campaign_ctx = _CampaignContext(campaign)
    workflow_ctx = _WorkflowContext(workflow_entity, workflow)
    request_text = CampaignPlannerAgent().build_manual_request(campaign_ctx, workflow_ctx)

    assert "Spring Coaches Push" in request_text
    assert "Drive clinic registrations" in request_text
    assert "Travel ball coaches" in request_text
    assert "Proof over promises" in request_text
    assert "Tuesday LinkedIn TL" in request_text
    assert "linkedin" in request_text


def test_campaign_service_run_campaign_creates_brain_executions(monkeypatch):
    fake_db = FakeDB()

    campaign = _make_campaign_entity()
    workflow_entity = _make_workflow_entity()
    scope_edge = _make_scope_edge(campaign.id, workflow_entity.id, role="awareness")

    workflow = Workflow(
        id=uuid.uuid4(),
        name="Tuesday LinkedIn TL",
        slug="tuesday-linkedin-tl",
        description="Thought leadership",
        mode=WorkflowMode.MANUAL,
        platform=Platform.LINKEDIN,
        content_type="thought_leadership",
        enabled=True,
    )

    created_trigger_nodes = []

    class FakeBrainQuery:
        def __init__(self, db):
            self.db = db

        def list_entities_by_type(self, entity_type, status="active", limit=50):
            return []

        def get_entity(self, entity_id):
            if entity_id == campaign.id:
                return campaign
            if entity_id == workflow_entity.id:
                return workflow_entity
            return None

        def get_entity_by_slug(self, entity_type, slug):
            if entity_type == "campaign" and slug == campaign.slug:
                return campaign
            return None

        def create_knowledge_node(self, *, kind, title, status="active", confidence=0.5, trust_score=0.5, metadata=None):
            node = KnowledgeNode(
                id=uuid.uuid4(),
                kind=kind,
                title=title,
                status=status,
                confidence=confidence,
                trust_score=trust_score,
                metadata_=metadata or {},
            )
            if kind == "trigger":
                created_trigger_nodes.append(node)
            return node

        def create_edge(self, **kwargs):
            return EntityEdge(
                id=uuid.uuid4(),
                source_id=kwargs["source_id"],
                target_id=kwargs["target_id"],
                source_type=kwargs["source_type"],
                target_type=kwargs["target_type"],
                relation=kwargs["relation"],
            )

    class FakeScopesQuery:
        def filter(self, *args, **kwargs):
            return self

        def all(self):
            return [scope_edge]

    class FakeDBWithScopes(FakeDB):
        def query(self, model):
            from app.models.brain import EntityEdge as EE
            if model is EE:
                return FakeScopesQuery()
            return _FakeQueryWithWorkflow(workflow)

    class _FakeQueryWithWorkflow:
        def __init__(self, wf):
            self._wf = wf

        def filter(self, *args, **kwargs):
            return self

        def first(self):
            return self._wf

        def all(self):
            return []

    fake_db_with_scopes = FakeDBWithScopes()

    class FakeWorkflowEngine:
        def __init__(self, db):
            self.db = db

        def execute_brain(self, trigger_node):
            return KnowledgeNode(
                id=uuid.uuid4(),
                kind="job",
                title="Job: Tuesday LinkedIn TL",
                status="completed",
                metadata_={"drafts_created": 1},
            )

    monkeypatch.setattr("app.services.campaign_service.BrainQuery", FakeBrainQuery)
    monkeypatch.setattr("app.services.campaign_service.WorkflowEngine", FakeWorkflowEngine)

    service = CampaignService(fake_db_with_scopes)
    summary = service.run_campaign(campaign.id, actor="planner")

    assert summary["campaign_slug"] == "spring-coaches-push"
    assert summary["actor"] == "planner"
    assert summary["workflow_runs"][0]["workflow_slug"] == "tuesday-linkedin-tl"
    assert summary["workflow_runs"][0]["status"] == "completed"
    assert summary["workflow_runs"][0]["role"] == "awareness"
    assert len(created_trigger_nodes) == 1
    trigger_meta = created_trigger_nodes[0].metadata_
    assert trigger_meta["campaign"]["slug"] == "spring-coaches-push"
    assert trigger_meta["campaign"]["role"] == "awareness"
    assert trigger_meta["campaign_slug"] == "spring-coaches-push"


def test_prompt_assembler_includes_campaign_context(monkeypatch):
    class FakeMemoryRetrievalService:
        def __init__(self, db):
            self.db = db

        def sync_control_room_memory(self, limit):
            return None

        def build_generation_context(self, **kwargs):
            return {
                "approved_examples": [{"title": "Example", "content": "Use proof points."}],
                "rejected_examples": [],
                "memory_ids": [],
            }

    monkeypatch.setattr(
        "app.services.prompt_assembler.MemoryRetrievalService",
        FakeMemoryRetrievalService,
    )

    workflow = Workflow(
        id=uuid.uuid4(),
        name="Tuesday LinkedIn TL",
        slug="tuesday-linkedin-tl",
        description="Thought leadership",
        mode=WorkflowMode.MANUAL,
        platform=Platform.LINKEDIN,
        content_type="thought_leadership",
        enabled=True,
    )
    version = WorkflowVersion(
        id=uuid.uuid4(),
        workflow_id=workflow.id,
        version_number=2,
        config=WorkflowVersionConfig(
            retrieval={"include_campaign_context": True},
        ).model_dump(),
        version_note="Campaign aware",
        author="planner",
        is_active=True,
    )
    trigger = TriggerEvent(
        id=uuid.uuid4(),
        trigger_type=TriggerType.MANUAL_REQUEST,
        workflow_id=workflow.id,
        source_payload={
            "request": "Write a campaign-aligned post.",
            "campaign": {
                "id": str(uuid.uuid4()),
                "slug": "spring-coaches-push",
                "name": "Spring Coaches Push",
                "objective": "Drive clinic registrations",
                "audience": "Travel ball coaches",
                "theme": "Proof over promises",
                "role": "awareness",
            },
        },
    )

    payload = PromptAssembler(db=None).assemble(workflow, version, trigger)

    assert payload["campaign_context"]["slug"] == "spring-coaches-push"
    assert "Campaign context" in payload["user"]
    assert "Drive clinic registrations" in payload["user"]
    assert payload["workflow_version_config"]["retrieval"]["include_campaign_context"] is True


def test_workflow_engine_prompt_snapshot_includes_campaign_context(monkeypatch):
    fake_db = FakeDB()
    workflow = Workflow(
        id=uuid.uuid4(),
        name="Tuesday LinkedIn TL",
        slug="tuesday-linkedin-tl",
        description="Thought leadership",
        mode=WorkflowMode.MANUAL,
        platform=Platform.X,
        content_type="thought_leadership",
        enabled=True,
    )
    version = WorkflowVersion(
        id=uuid.uuid4(),
        workflow_id=workflow.id,
        version_number=1,
        config=WorkflowVersionConfig().model_dump(),
        version_note="Initial",
        author="planner",
        is_active=True,
    )
    trigger = TriggerEvent(
        id=uuid.uuid4(),
        trigger_type=TriggerType.MANUAL_REQUEST,
        workflow_id=workflow.id,
        source_payload={"request": "Write the post."},
    )

    class FakeAssembler:
        def __init__(self, db):
            self.db = db

        def assemble(self, workflow, version, trigger):
            return {
                "system": "sys",
                "user": "usr",
                "context": "usr",
                "content_type": "thought_leadership",
                "pillar": "brand",
                "intent": "engagement",
                "claims": [],
                "retrieved_examples": {"approved_examples": [], "rejected_examples": [], "memory_ids": []},
                "retrieved_memory_ids": [],
                "campaign_context": {"slug": "spring-coaches-push", "objective": "Drive clinic registrations"},
            }

    class FakePlatformGenerationService:
        def __init__(self, db):
            self.db = db

        def generate(self, workflow, version, payload):
            return [
                GeneratedCandidate(
                    content="Proof beats noise.",
                    hashtags=["#NTangible"],
                    compliance_result={"passed": True},
                    generation_trace={},
                    prompt_snapshot="prompt",
                )
            ]

    monkeypatch.setattr("app.services.workflow_engine.PromptAssembler", FakeAssembler)
    monkeypatch.setattr(
        "app.services.workflow_engine.PlatformGenerationService",
        FakePlatformGenerationService,
    )
    monkeypatch.setattr(WorkflowEngine, "resolve_workflow", lambda self, trigger: workflow)
    monkeypatch.setattr(WorkflowEngine, "get_active_version", lambda self, workflow: version)

    job = WorkflowEngine(fake_db).execute(trigger)

    assert job.status == "completed"
    assert job.prompt_snapshot["campaign_context"]["slug"] == "spring-coaches-push"
    assert job.prompt_snapshot["campaign_context"]["objective"] == "Drive clinic registrations"


def test_prompt_assembler_includes_revenue_context(monkeypatch):
    class FakeMemoryRetrievalService:
        def __init__(self, db):
            self.db = db

        def sync_control_room_memory(self, limit):
            return None

        def build_generation_context(self, **kwargs):
            return {
                "approved_examples": [],
                "rejected_examples": [],
                "memory_ids": [],
            }

    monkeypatch.setattr(
        "app.services.prompt_assembler.MemoryRetrievalService",
        FakeMemoryRetrievalService,
    )

    workflow = Workflow(
        id=uuid.uuid4(),
        name="Revenue LinkedIn Push",
        slug="revenue-linkedin-push",
        description="Revenue workflow",
        mode=WorkflowMode.MANUAL,
        platform=Platform.LINKEDIN,
        content_type="company_update",
        enabled=True,
    )
    version = WorkflowVersion(
        id=uuid.uuid4(),
        workflow_id=workflow.id,
        version_number=1,
        config=WorkflowVersionConfig(
            retrieval={"include_revenue_context": True},
            routing={"target_intent": "revenue"},
        ).model_dump(),
        version_note="Revenue aware",
        author="sales",
        is_active=True,
    )
    trigger = TriggerEvent(
        id=uuid.uuid4(),
        trigger_type=TriggerType.MANUAL_REQUEST,
        workflow_id=workflow.id,
        source_payload={
            "request": "Drive more registrations.",
            "revenue_context": {
                "playbook_slug": "alliance-registration-push",
                "persona": "event_operator",
                "offer": "Register now",
                "cta": "Reserve your spot",
            },
        },
    )

    payload = PromptAssembler(db=None).assemble(workflow, version, trigger)

    assert payload["revenue_context"]["playbook_slug"] == "alliance-registration-push"
    assert "Revenue context" in payload["user"]
    assert "Register now" in payload["user"]
    assert payload["workflow_version_config"]["retrieval"]["include_revenue_context"] is True


def test_workflow_engine_prompt_snapshot_includes_revenue_context(monkeypatch):
    fake_db = FakeDB()
    workflow = Workflow(
        id=uuid.uuid4(),
        name="Revenue LinkedIn Push",
        slug="revenue-linkedin-push",
        description="Revenue workflow",
        mode=WorkflowMode.MANUAL,
        platform=Platform.X,
        content_type="data_drop",
        enabled=True,
    )
    version = WorkflowVersion(
        id=uuid.uuid4(),
        workflow_id=workflow.id,
        version_number=1,
        config=WorkflowVersionConfig().model_dump(),
        version_note="Initial",
        author="sales",
        is_active=True,
    )
    trigger = TriggerEvent(
        id=uuid.uuid4(),
        trigger_type=TriggerType.MANUAL_REQUEST,
        workflow_id=workflow.id,
        source_payload={"request": "Write the revenue post."},
    )

    class FakeAssembler:
        def __init__(self, db):
            self.db = db

        def assemble(self, workflow, version, trigger):
            return {
                "system": "sys",
                "user": "usr",
                "context": "usr",
                "content_type": "data_drop",
                "pillar": "client_proof",
                "intent": "revenue",
                "claims": [],
                "retrieved_examples": {"approved_examples": [], "rejected_examples": [], "memory_ids": []},
                "retrieved_memory_ids": [],
                "campaign_context": {},
                "revenue_context": {"playbook_slug": "alliance-registration-push", "cta": "Reserve your spot"},
            }

    class FakePlatformGenerationService:
        def __init__(self, db):
            self.db = db

        def generate(self, workflow, version, payload):
            return [
                GeneratedCandidate(
                    content="Proof beats noise.",
                    hashtags=["#NTangible"],
                    compliance_result={"passed": True},
                    generation_trace={},
                    prompt_snapshot="prompt",
                )
            ]

    monkeypatch.setattr("app.services.workflow_engine.PromptAssembler", FakeAssembler)
    monkeypatch.setattr(
        "app.services.workflow_engine.PlatformGenerationService",
        FakePlatformGenerationService,
    )
    monkeypatch.setattr(WorkflowEngine, "resolve_workflow", lambda self, trigger: workflow)
    monkeypatch.setattr(WorkflowEngine, "get_active_version", lambda self, workflow: version)

    job = WorkflowEngine(fake_db).execute(trigger)

    assert job.status == "completed"
    assert job.prompt_snapshot["revenue_context"]["playbook_slug"] == "alliance-registration-push"
    assert job.prompt_snapshot["revenue_context"]["cta"] == "Reserve your spot"
