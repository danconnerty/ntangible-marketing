from jinja2 import Environment, FileSystemLoader, select_autoescape


def test_blog_template_renders_drafts_and_publish_actions():
    env = Environment(
        loader=FileSystemLoader("app/web/templates"),
        autoescape=select_autoescape(["html", "xml"]),
    )
    template = env.get_template("blog.html")
    html = template.render(
        page="blog",
        articles=[
            {
                "id": "article-1",
                "status": "review_ready",
                "title": "Pressure Performance Assessment for Coaches",
                "meta_description": "A practical look at pressure performance assessment.",
                "word_count": 900,
                "target_keywords": ["pressure performance assessment", "mental performance testing"],
            }
        ],
        counts={"total": 1},
    )

    assert "SEO & Blog" in html
    assert "Pressure Performance Assessment for Coaches" in html
    assert "Publish" in html


def test_blog_publish_result_partial_renders_url_and_failure():
    env = Environment(
        loader=FileSystemLoader("app/web/templates"),
        autoescape=select_autoescape(["html", "xml"]),
    )
    template = env.get_template("partials/blog_publish_result.html")
    html = template.render(
        result={
            "title": "Pressure Performance Assessment for Coaches",
            "status": "published",
            "word_count": 900,
            "target_keywords": ["pressure performance assessment", "mental performance testing"],
            "canonical_url": "https://example.com/blog/pressure-performance-assessment",
            "failure_reason": None,
        }
    )

    assert "Pressure Performance Assessment for Coaches" in html
    assert "900 words" in html
    assert "https://example.com/blog/pressure-performance-assessment" in html
