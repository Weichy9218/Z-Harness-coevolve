from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_readme_points_to_harnessx_terminal_bench_direction() -> None:
    text = read("README.md")
    assert "HarnessX" in text
    assert "Terminal-Bench 2.1" in text
    assert "terminal-bench/terminal-bench-2-1" in text
    assert "MiniLang/MiniAPI synthetic scaffold-adoption 路线已经归档" in text


def test_docs_have_active_plan_and_archive_boundary() -> None:
    direction = read("docs/DIRECTION.md")
    tb2 = read("docs/TERMINAL_BENCH_2_PLAN.md")
    archive = read("docs/archive/PRIOR_RESULTS_SUMMARY.md")

    assert "HarnessX/Terminal-Bench" in direction
    assert 'DATASET = "terminal-bench/terminal-bench-2-1"' in tb2
    assert "τ³-bench text domains" in tb2
    assert "no longer the active project direction" in archive


def test_pyproject_no_longer_packages_zharness() -> None:
    text = read("pyproject.toml")
    assert 'include = ["core*"]' in text
    assert "zharness" not in text
