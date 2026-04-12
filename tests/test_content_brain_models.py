from app.models.content_brain import (
    ContentBrainAsset,
    ContentBrainItem,
    ContentBrainMetricSnapshot,
    ContentSourceSnapshot,
    ContentSourceTarget,
)


def test_content_brain_table_names_are_registered():
    assert ContentSourceTarget.__tablename__ == "content_source_target"
    assert ContentSourceSnapshot.__tablename__ == "content_source_snapshot"
    assert ContentBrainItem.__tablename__ == "content_brain_item"
    assert ContentBrainAsset.__tablename__ == "content_brain_asset"
    assert ContentBrainMetricSnapshot.__tablename__ == "content_brain_metric_snapshot"


def test_content_brain_item_has_unique_canonical_key():
    canonical_key_column = ContentBrainItem.__table__.c.canonical_key
    assert canonical_key_column.unique is True
