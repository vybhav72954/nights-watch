"""Tests for src/evidence/scale_benchmark.py -- structure/JSON-safety on a
tiny, fast slice. The deck's actual scale numbers come from
`python -m src.evidence.scale_benchmark` at the real DEFAULT_SWEEP sizes;
these tests only guard that the timing/counting mechanism itself is correct.
"""
from __future__ import annotations

import json

from src.evidence.scale_benchmark import (
    ScaleBenchmarkRun,
    benchmark_at_scale,
    main as scale_benchmark_main,
    run_sweep,
)


def test_benchmark_at_scale_counts_and_times_are_sane():
    # n_victims=500 clears the point where every legit merchant node's degree
    # exceeds hub_degree_cap=40 (hub_share=0.4, 4 common payees -> 0.15 each,
    # needs >267 victims) -- below that, legit fan-in into a shared merchant
    # can itself form a spurious "ring", which is a real small-scale artifact
    # of connected-component clustering, not a bug in this benchmark.
    run = benchmark_at_scale(n_victims=500, n_rings=3, cards_per_ring=4)
    assert isinstance(run, ScaleBenchmarkRun)
    assert run.n_reports > 500  # legit background + planted ring incidents
    assert run.n_graph_nodes > 0 and run.n_graph_edges > 0
    assert run.n_rings_detected == 3  # all 3 planted rings recovered, no legit false rings
    assert run.generate_seconds >= 0
    assert run.build_graph_seconds >= 0
    assert run.detect_rings_seconds >= 0
    assert run.rank_kingpins_seconds >= 0
    assert run.total_seconds == round(
        run.generate_seconds + run.build_graph_seconds
        + run.detect_rings_seconds + run.rank_kingpins_seconds, 4,
    )


def test_run_sweep_returns_one_result_per_config_in_order():
    configs = [{"n_victims": 30, "n_rings": 2}, {"n_victims": 60, "n_rings": 4}]
    runs = run_sweep(configs)
    assert [r.n_victims for r in runs] == [30, 60]
    assert [r.n_rings for r in runs] == [2, 4]


def test_scale_benchmark_run_to_dict_is_json_safe_and_consistent():
    run = benchmark_at_scale(n_victims=30, n_rings=2, cards_per_ring=4)
    d = run.to_dict()
    json.dumps(d)  # must not raise
    assert d["n_reports"] == run.n_reports
    assert d["total_seconds"] == run.total_seconds


def test_scale_benchmark_main_writes_json_artifact_and_figure(tmp_path):
    out_path = tmp_path / "scale_benchmark.json"
    figure_path = tmp_path / "scale_benchmark.png"
    configs = [{"n_victims": 30, "n_rings": 2}, {"n_victims": 60, "n_rings": 3}]
    result = scale_benchmark_main(configs=configs, out_path=out_path, figure_path=figure_path)
    written = json.loads(out_path.read_text(encoding="utf-8"))
    assert len(written["runs"]) == 2
    assert "code_version" in written
    assert figure_path.exists() and figure_path.stat().st_size > 0
    assert result["runs"] == written["runs"]
