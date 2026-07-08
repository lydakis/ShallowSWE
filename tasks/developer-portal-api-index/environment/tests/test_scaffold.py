from pathlib import Path


def test_fixture_present() -> None:
    root = Path(__file__).resolve().parents[1]
    assert (root / "catalog" / "services.json").exists()
    assert (root / "docs" / "pages").exists()
