"""Regression checks for the JHora values supplied in the Indore screenshots."""

import pytest

from tests.jhora_parity import build_comparison, comparison_summary, load_reference


def test_screenshot_reference_has_all_three_jhora_tables():
    reference = load_reference()

    assert len(reference["sav_by_house"]) == 12
    assert set(reference["shadbala"]) == {"Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"}
    assert len(reference["bhava_bala"]) == 12
    assert sum(reference["sav_by_house"]) == 337


def test_parity_report_tracks_current_numeric_and_label_gaps():
    """Keep the report honest until the underlying formulas reach JHora parity."""
    summary = comparison_summary(build_comparison())

    # These are a deliberately explicit baseline, not a claim that all labels
    # are acceptable.  A formula change must update this expectation and the
    # strict xfail below will turn into a pass once every gap is removed.
    assert summary == {
        "sav": {"numeric_matches": 6, "numeric_total": 12, "label_matches": 11, "label_total": 12},
        "shadbala": {"numeric_matches": 0, "numeric_total": 7, "label_matches": 6, "label_total": 7},
        "bhava": {"numeric_matches": 0, "numeric_total": 12, "label_matches": 8, "label_total": 12},
    }


@pytest.mark.xfail(strict=True, reason="JHora numeric parity is not implemented for SAV, Shadbala, and Bhava Bala yet.")
def test_all_supplied_jhora_values_match_exactly():
    comparison = build_comparison()
    mismatches = [
        row
        for rows in comparison.values()
        for row in rows
        if row["delta"] != 0
    ]
    assert not mismatches, mismatches


@pytest.mark.xfail(strict=True, reason="Some qualitative labels still contradict the corresponding JHora values.")
def test_all_qualitative_outputs_are_acceptable_against_jhora_numbers():
    comparison = build_comparison()
    unacceptable = [
        row
        for rows in comparison.values()
        for row in rows
        if row["expected_band"] != row["actual_band"]
    ]
    assert not unacceptable, unacceptable
