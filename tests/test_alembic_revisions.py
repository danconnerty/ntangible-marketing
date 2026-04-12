from alembic.config import Config
from alembic.script import ScriptDirectory


def test_alembic_has_single_head_revision():
    config = Config("alembic.ini")
    script = ScriptDirectory.from_config(config)

    heads = script.get_heads()

    assert tuple(heads) == ("98fbddb3c753",)
