from jinja2 import Environment, FileSystemLoader, select_autoescape


def test_science_template_renders_generation_and_records():
    env = Environment(
        loader=FileSystemLoader("app/web/templates"),
        autoescape=select_autoescape(["html", "xml"]),
    )
    template = env.get_template("science.html")
    html = template.render(
        page="science",
        records=[
            {
                "science_type": "advisor_spotlight",
                "title": "Advisor Spotlight: Dr. Ed Levine",
                "summary": "Advisor spotlight content focused on the science team.",
                "workflow_slug": "science-advisor_spotlight-linkedin",
                "status": "review_ready",
            }
        ],
        counts={"total": 1},
    )

    assert "Science Credibility" in html
    assert "Advisor Spotlight" in html
    assert "Dr. Ed Levine" in html


def test_science_result_partial_renders_summary():
    env = Environment(
        loader=FileSystemLoader("app/web/templates"),
        autoescape=select_autoescape(["html", "xml"]),
    )
    template = env.get_template("partials/science_run_result.html")
    html = template.render(
        result={
            "title": "Advisor Spotlight: Dr. Ed Levine",
            "science_type": "advisor_spotlight",
            "status": "review_ready",
            "job_status": "completed",
            "summary": "Advisor spotlight content focused on the science team.",
            "workflow_slug": "science-advisor_spotlight-linkedin",
            "source_focus": "science team credibility",
            "draft_id": "draft-1",
        }
    )

    assert "Advisor Spotlight: Dr. Ed Levine" in html
    assert "review_ready" in html
    assert "Workflow job: completed" in html
    assert "Draft ID: draft-1" in html
