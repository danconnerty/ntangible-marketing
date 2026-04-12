import uuid

from app.models.revenue import (
    ConversionEvent,
    ConversionGoal,
    RevenueExecution,
    RevenuePlaybook,
    SalesEnablementPackage,
)


def test_revenue_playbook_fields():
    playbook = RevenuePlaybook(
        id=uuid.uuid4(),
        slug="alliance-registration-push",
        name="Alliance Registration Push",
        description="Drive event registrations with proof-led copy.",
        playbook_type="registration_push",
        persona="event_operator",
        offer="Register now",
        cta="Reserve your spot",
        default_audience="travel ball coaches",
        default_proof_points=["Pressure data", "Attendance history"],
        active=True,
    )

    assert playbook.slug == "alliance-registration-push"
    assert playbook.playbook_type == "registration_push"
    assert playbook.default_proof_points == ["Pressure data", "Attendance history"]


def test_revenue_execution_fields():
    execution = RevenueExecution(
        id=uuid.uuid4(),
        revenue_playbook_id=uuid.uuid4(),
        source_kind="partner_event",
        source_id="evt-1",
        trigger_event_id=uuid.uuid4(),
        actor="sales",
        status="completed",
        summary={"intent": "revenue"},
    )

    assert execution.source_kind == "partner_event"
    assert execution.summary["intent"] == "revenue"


def test_conversion_goal_and_event_fields():
    goal = ConversionGoal(
        id=uuid.uuid4(),
        slug="alliance-registration-completions",
        name="Alliance registration completions",
        metric_type="registrations",
        attribution_window_days=14,
        active=True,
    )
    event = ConversionEvent(
        id=uuid.uuid4(),
        conversion_goal_id=goal.id,
        external_event_id="conv-1",
        source_kind="partner_event",
        source_reference="evt-1",
        metric_value=1,
        metadata_json={"utm_campaign": "alliance-spring"},
    )

    assert goal.metric_type == "registrations"
    assert event.metric_value == 1
    assert event.metadata_json["utm_campaign"] == "alliance-spring"


def test_sales_enablement_package_fields():
    package = SalesEnablementPackage(
        id=uuid.uuid4(),
        partner_account_id=uuid.uuid4(),
        partner_event_record_id=uuid.uuid4(),
        revenue_playbook_id=uuid.uuid4(),
        package_kind="registration_push",
        status="needs_review",
        headline="Register now",
        body_copy="Proof-led registration copy",
        cta="Reserve your spot",
        asset_ids=[],
        payload={"channel": "email"},
    )

    assert package.package_kind == "registration_push"
    assert package.payload["channel"] == "email"
