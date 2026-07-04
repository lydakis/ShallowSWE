from pathlib import Path

def test_fixture_present() -> None:
    assert Path(__file__).resolve().parents[1].exists()
