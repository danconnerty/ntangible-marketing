from app.content_brain.vite_chunks import extract_lazy_chunk_targets


def test_extract_lazy_chunk_targets_builds_source_targets_from_main_bundle():
    bundle = """
    const Team = lazy(() => import("./Team-D9JR-r6u.js"));
    const Research = lazy(() => import("./Research-NxzUk_U8.js"));
    const Partners = lazy(() => import("./PartnersPage-DeUS49va.js"));
    """

    targets = extract_lazy_chunk_targets(bundle, base_url="https://ntangible.co")

    slugs = [target.slug for target in targets]
    urls = [target.url for target in targets]

    assert slugs == [
        "ntangible_chunk_partners_page",
        "ntangible_chunk_research",
        "ntangible_chunk_team",
    ]
    assert urls == [
        "https://ntangible.co/assets/PartnersPage-DeUS49va.js",
        "https://ntangible.co/assets/Research-NxzUk_U8.js",
        "https://ntangible.co/assets/Team-D9JR-r6u.js",
    ]
    assert all(target.parser == "js_text_chunk" for target in targets)
