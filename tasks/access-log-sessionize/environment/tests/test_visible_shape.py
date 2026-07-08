from pathlib import Path


def test_input_logs_exist():
    assert sorted(path.name for path in Path("input").glob("*.log")) == ["api.log", "edge.log"]
