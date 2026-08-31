"""Guardrails for the chart context sent to the reading model."""

from pathlib import Path

from prompts import COMMON_RULES, WORKFLOWS


def test_every_workflow_inherits_the_chart_evidence_rules():
    required_rules = (
        "D1 placement, functional lordship, and an active Dasha or verified transit are the primary evidence.",
        "Never treat one SAV number or a score cutoff as proof of an outcome.",
        "Never quote their raw numbers or treat a label as a verdict.",
        "Before calling any area Strong or Weak, require at least two independent supporting signals.",
        "Never turn a chart pattern into a guaranteed event",
    )

    for rule in required_rules:
        assert rule in COMMON_RULES
    for name, workflow in WORKFLOWS.items():
        for rule in required_rules:
            assert rule in workflow, f"{name} workflow lost shared safety rule: {rule}"


def test_app_marks_strength_data_as_approximate_and_avoids_ashtam_shani_predictions():
    app_source = (Path(__file__).parent.parent / "app.py").read_text(encoding="utf-8")

    assert "PLANETARY SHADBALA" in app_source
    assert "do not predict losses, illness, legal trouble, or psychological harm" in app_source

