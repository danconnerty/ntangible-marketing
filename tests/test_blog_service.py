import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

from app.models.blog import BlogArticle, BlogArticleStatus
from app.models.brain import EntityNode, KnowledgeNode
from app.publishers.blog_base import BlogPublishResult
from app.services.blog_service import BlogService


class FakeDB:
    def __init__(self):
        self.added = []
        self.flushed = 0

    def add(self, obj):
        self.added.append(obj)

    def flush(self):
        self.flushed += 1


def test_generate_draft_creates_review_ready_article():
    db = FakeDB()
    service = BlogService(db)

    result = service.generate_draft(
        topic="Pressure performance assessment",
        audience="college coaches",
        target_keywords=["pressure performance assessment", "mental performance testing"],
        angle="Explain how evidence changes recruiting decisions.",
        source_notes=["White paper excerpt", "Validation milestone"],
    )

    assert result["status"] == BlogArticleStatus.REVIEW_READY.value
    assert result["word_count"] >= 800
    assert "pressure performance assessment" in result["body_markdown"].lower()
    assert any(isinstance(item, BlogArticle) for item in db.added)


def test_generate_draft_creates_canonical_workflow_links(monkeypatch):
    db = FakeDB()
    service = BlogService(db)
    workflow_entity_id = uuid.uuid4()
    trigger_node_id = uuid.uuid4()
    job_node_id = uuid.uuid4()
    draft_node_id = uuid.uuid4()

    monkeypatch.setattr(
        "app.services.blog_service.generate_blog_draft",
        lambda **kwargs: {
            "slug": "pressure-performance-assessment",
            "title": "Pressure Performance Assessment for Coaches",
            "meta_description": "A practical look at pressure performance assessment.",
            "audience": kwargs["audience"],
            "topic": kwargs["topic"],
            "angle": kwargs["angle"],
            "body_markdown": "# Title\n\nSome body text",
            "body_html": "<h1>Title</h1><p>Some body text</p>",
            "target_keywords": kwargs["target_keywords"],
            "headings": ["Why this matters"],
            "word_count": 900,
            "excerpt": "Practical evidence for coaches.",
        },
    )
    monkeypatch.setattr(
        "app.services.blog_service.run_blog_compliance_checks",
        lambda draft: SimpleNamespace(
            passed=True,
            corrected_body_markdown=draft["body_markdown"],
            failure_reason=None,
            checks_run=["seo", "claims"],
        ),
    )

    workflow_entity = EntityNode(
        id=workflow_entity_id,
        entity_type="workflow",
        canonical_name="Blog Authority Engine",
        slug="blog-authority-engine",
        status="active",
        metadata_={"platform": "blog", "content_type": "blog_article", "mode": "manual"},
    )
    trigger_node = KnowledgeNode(
        id=trigger_node_id,
        kind="trigger",
        title="Manual trigger",
        status="active",
        metadata_={"trigger_type": "manual", "workflow_entity_id": str(workflow_entity_id)},
    )
    job_node = KnowledgeNode(
        id=job_node_id,
        kind="job",
        title="Job: Blog Authority Engine",
        status="completed",
        metadata_={"workflow_entity_id": str(workflow_entity_id), "trigger_id": str(trigger_node_id)},
    )
    draft_node = KnowledgeNode(
        id=draft_node_id,
        kind="draft",
        title="Blog draft",
        content="Some body text",
        status="review_required",
        metadata_={},
    )

    monkeypatch.setattr(
        service,
        "_resolve_workflow",
        lambda: workflow_entity,
        raising=False,
    )
    monkeypatch.setattr(
        service,
        "_create_trigger",
        lambda request_text, wf_entity, topic, audience, target_keywords, angle, source_notes: trigger_node,
        raising=False,
    )
    monkeypatch.setattr(
        service,
        "_execute_workflow",
        lambda trigger, wf_entity: job_node,
        raising=False,
    )
    monkeypatch.setattr(
        service,
        "_latest_draft_for_job",
        lambda incoming_job_id: draft_node,
        raising=False,
    )

    result = service.generate_draft(
        topic="Pressure performance assessment",
        audience="college coaches",
        target_keywords=["pressure performance assessment", "mental performance testing"],
        angle="Explain how evidence changes recruiting decisions.",
        source_notes=["White paper excerpt", "Validation milestone"],
    )

    assert result["status"] == BlogArticleStatus.REVIEW_READY.value
    assert result["workflow_slug"] == "blog-authority-engine"
    assert result["trigger_event_id"] == str(trigger_node_id)
    assert result["content_job_id"] == str(job_node_id)
    assert result["draft_variant_id"] == str(draft_node_id)
    assert any(
        isinstance(item, BlogArticle)
        and getattr(item, "workflow_id", None) == workflow_entity_id
        and getattr(item, "draft_variant_id", None) == draft_node_id
        for item in db.added
    )


def test_publish_article_uses_blog_publisher(monkeypatch):
    db = FakeDB()
    service = BlogService(db)
    article_id = uuid.uuid4()
    article = SimpleNamespace(
        id=article_id,
        slug="pressure-performance-assessment",
        title="Pressure Performance Assessment for Coaches",
        meta_description="A practical look at pressure performance assessment.",
        audience="college coaches",
        topic="Pressure performance assessment",
        angle="Explain why evidence matters.",
        body_markdown="# Title\n\nSome body text",
        body_html="<h1>Title</h1><p>Some body text</p>",
        target_keywords=["pressure performance assessment"],
        headings=["Why this matters"],
        publish_payload={},
        status=BlogArticleStatus.REVIEW_READY,
        cms_provider=None,
        cms_article_id=None,
        canonical_url=None,
        failure_reason=None,
        published_at=None,
    )

    monkeypatch.setattr(service, "_get_article", lambda incoming_id: article)
    monkeypatch.setattr(
        "app.services.blog_service.get_blog_publisher",
        lambda: SimpleNamespace(
            publish_article=lambda **kwargs: BlogPublishResult(
                success=True,
                article_id="cms-123",
                url="https://example.com/blog/pressure-performance-assessment",
                published_at=datetime.now(timezone.utc),
            )
        ),
    )

    result = service.publish_article(article_id, actor="editor")

    assert result["status"] == BlogArticleStatus.PUBLISHED.value
    assert result["canonical_url"] == "https://example.com/blog/pressure-performance-assessment"


def test_publish_article_uses_active_connection_target(monkeypatch):
    db = FakeDB()
    service = BlogService(db)
    article_id = uuid.uuid4()
    article = SimpleNamespace(
        id=article_id,
        slug="pressure-performance-assessment",
        title="Pressure Performance Assessment for Coaches",
        meta_description="A practical look at pressure performance assessment.",
        audience="college coaches",
        topic="Pressure performance assessment",
        angle="Explain why evidence matters.",
        body_markdown="# Title\n\nSome body text",
        body_html="<h1>Title</h1><p>Some body text</p>",
        target_keywords=["pressure performance assessment"],
        headings=["Why this matters"],
        publish_payload={},
        status=BlogArticleStatus.REVIEW_READY,
        draft_variant_id=None,
        cms_provider=None,
        cms_article_id=None,
        canonical_url=None,
        failure_reason=None,
        published_at=None,
    )

    captured: dict[str, object] = {}

    class FakeConnectionService:
        def __init__(self, incoming_db):
            assert incoming_db is db

        def resolve_active_publish_target(self, channel):
            assert channel == "blog"
            return {
                "channel": "blog",
                "connection": object(),
                "destination": object(),
                "credentials": {"api_token": "runtime-blog-token"},
                "config": {
                    "provider_key": "wordpress",
                    "base_url": "https://cms.example.com",
                },
            }

    def fake_get_blog_publisher(*, runtime_config=None):
        captured["runtime_config"] = runtime_config
        return SimpleNamespace(
            publish_article=lambda **kwargs: BlogPublishResult(
                success=True,
                article_id="cms-456",
                url="https://cms.example.com/blog/pressure-performance-assessment",
                published_at=datetime.now(timezone.utc),
            )
        )

    monkeypatch.setattr(service, "_get_article", lambda incoming_id: article)
    monkeypatch.setattr(
        "app.services.blog_service.PublishingConnectionService",
        FakeConnectionService,
    )
    monkeypatch.setattr(
        "app.services.blog_service.get_blog_publisher",
        fake_get_blog_publisher,
    )

    result = service.publish_article(article_id, actor="editor")

    assert result["status"] == BlogArticleStatus.PUBLISHED.value
    assert captured["runtime_config"] == {
        "api_token": "runtime-blog-token",
        "provider_key": "wordpress",
        "base_url": "https://cms.example.com",
    }
