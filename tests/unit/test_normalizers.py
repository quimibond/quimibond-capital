"""Tests de normalizers (age, productividad, location)."""

from __future__ import annotations

from datetime import date

import pytest

from quimibond.enrichment.normalizers import (
    build_location_label,
    compute_age_years,
    compute_productivity_usd_per_employee,
    is_edad_madura,
    lower_text,
)


class TestComputeAge:
    def test_basic(self) -> None:
        assert compute_age_years(2000, date(2026, 4, 29)) == 26

    def test_same_year(self) -> None:
        assert compute_age_years(2026, date(2026, 4, 29)) == 0

    def test_future_year_rejected(self) -> None:
        assert compute_age_years(2030, date(2026, 4, 29)) is None

    def test_none(self) -> None:
        assert compute_age_years(None, date(2026, 4, 29)) is None

    def test_too_old(self) -> None:
        # 200 años es el cap
        assert compute_age_years(1820, date(2026, 4, 29)) is None


class TestComputeProductivity:
    def test_basic(self) -> None:
        # 10M USD / 100 emp = 100k USD / emp
        assert compute_productivity_usd_per_employee(10.0, 100) == 100_000.0

    def test_missing_revenue(self) -> None:
        assert compute_productivity_usd_per_employee(None, 100) is None

    def test_zero_employees(self) -> None:
        assert compute_productivity_usd_per_employee(10.0, 0) is None

    def test_missing_employees(self) -> None:
        assert compute_productivity_usd_per_employee(10.0, None) is None


class TestBuildLocationLabel:
    def test_municipality_state(self) -> None:
        assert build_location_label("Toluca", "Estado de Mexico") == "Toluca, Estado de Mexico"

    def test_city_fallback(self) -> None:
        assert build_location_label(None, "Estado de Mexico", "Toluca") == "Toluca, Estado de Mexico"

    def test_only_state(self) -> None:
        assert build_location_label(None, "Puebla") == "Puebla"

    def test_all_none(self) -> None:
        assert build_location_label(None, None, None) is None

    def test_strips_blanks(self) -> None:
        assert build_location_label("  ", "  ", None) is None


class TestEdadMadura:
    def test_at_threshold(self) -> None:
        assert is_edad_madura(20, threshold=20) is True

    def test_below(self) -> None:
        assert is_edad_madura(15, threshold=20) is False

    def test_none(self) -> None:
        assert is_edad_madura(None, threshold=20) is False


class TestLowerText:
    def test_concat_lowercase(self) -> None:
        assert lower_text("Hola", " MUNDO ", None, "  ") == "hola mundo"

    def test_all_none(self) -> None:
        assert lower_text(None, None) == ""


@pytest.mark.parametrize(
    "rev_mm,emp,expected",
    [
        (1.0, 1, 1_000_000.0),
        (50.0, 100, 500_000.0),
        (0.5, 50, 10_000.0),
    ],
)
def test_productivity_param(rev_mm: float, emp: int, expected: float) -> None:
    assert compute_productivity_usd_per_employee(rev_mm, emp) == expected
