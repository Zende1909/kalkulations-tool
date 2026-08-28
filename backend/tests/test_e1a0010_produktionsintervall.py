"""e1a0010: Produktionsintervall am Werk + Losgrößenmodus an Spritzguss."""

from pathlib import Path

REVISION = "e1a0010_produktionsintervall_losgroesse_modus"
PREV = "e1a0009_werk_operating_params"


def test_e1a0010_revision_module_contract():
    source = Path(__file__).resolve().parents[1].joinpath(
        "alembic", "versions", f"{REVISION}.py"
    ).read_text(encoding="utf-8")
    assert f'revision: str = "{REVISION}"' in source
    assert PREV in source
    assert "produktionsintervall_arbeitstage" in source
    assert "losgroesse_modus" in source
    assert "losgroesse_manuell" in source
