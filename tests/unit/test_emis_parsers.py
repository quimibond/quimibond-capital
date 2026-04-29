"""Tests unitarios de los parsers individuales del export EMIS."""

from __future__ import annotations

from datetime import datetime

import pytest

from quimibond.ingestion.emis_parsers import (
    parse_all_naics,
    parse_bool_loose,
    parse_coord,
    parse_csv_list,
    parse_employees,
    parse_naics_first,
    parse_revenue_usd_mm,
    parse_text,
    parse_year,
)


class TestParseText:
    def test_strips(self) -> None:
        assert parse_text("  hola  ") == "hola"

    def test_empty_to_none(self) -> None:
        assert parse_text("") is None
        assert parse_text("   ") is None
        assert parse_text(None) is None


class TestParseRevenue:
    def test_float_passthrough(self) -> None:
        assert parse_revenue_usd_mm(818.09) == 818.09

    def test_int_to_float(self) -> None:
        assert parse_revenue_usd_mm(100) == 100.0

    def test_string_with_comma(self) -> None:
        assert parse_revenue_usd_mm("1,234.56") == 1234.56

    def test_zero(self) -> None:
        assert parse_revenue_usd_mm(" 0 ") == 0.0

    def test_invalid(self) -> None:
        assert parse_revenue_usd_mm("n/a") is None
        assert parse_revenue_usd_mm("-") is None
        assert parse_revenue_usd_mm("abc") is None
        assert parse_revenue_usd_mm("") is None
        assert parse_revenue_usd_mm(None) is None


class TestParseEmployees:
    def test_with_year_in_parens(self) -> None:
        assert parse_employees("3,500 (2024)") == 3500

    def test_plain_int(self) -> None:
        assert parse_employees("180") == 180
        assert parse_employees(180) == 180

    def test_float_truncates(self) -> None:
        assert parse_employees(180.7) == 180

    def test_dash(self) -> None:
        assert parse_employees("-") is None

    def test_empty(self) -> None:
        assert parse_employees("") is None
        assert parse_employees(None) is None

    def test_negative_rejected(self) -> None:
        assert parse_employees(-5) is None


class TestParseYear:
    def test_string(self) -> None:
        assert parse_year("1982") == 1982

    def test_int(self) -> None:
        assert parse_year(1982) == 1982

    def test_date_with_year(self) -> None:
        assert parse_year("1982-05-13") == 1982

    def test_datetime(self) -> None:
        assert parse_year(datetime(1990, 1, 1)) == 1990

    def test_out_of_range(self) -> None:
        assert parse_year(1500) is None
        assert parse_year(2300) is None

    def test_no_year_in_text(self) -> None:
        assert parse_year("Sin fecha") is None
        assert parse_year("") is None
        assert parse_year(None) is None


class TestParseNaicsFirst:
    def test_single(self) -> None:
        assert parse_naics_first("Broadwoven Fabric Mills(31321)") == "31321"

    def test_first_of_many(self) -> None:
        assert (
            parse_naics_first("Offices(551112); Broadwoven Fabric Mills(31321)")
            == "551112"
        )

    def test_no_paren(self) -> None:
        assert parse_naics_first("Sin código") is None

    def test_empty(self) -> None:
        assert parse_naics_first("") is None
        assert parse_naics_first(None) is None


class TestParseAllNaics:
    def test_dedup(self) -> None:
        assert parse_all_naics("A(551112); B(31321); C(551112)") == ("551112", "31321")

    def test_empty(self) -> None:
        assert parse_all_naics("") == ()
        assert parse_all_naics(None) == ()


class TestParseBoolLoose:
    def test_yes(self) -> None:
        assert parse_bool_loose("yes") is True
        assert parse_bool_loose("X") is True
        assert parse_bool_loose("Sí") is True

    def test_no(self) -> None:
        assert parse_bool_loose("no") is False
        assert parse_bool_loose("0") is False
        assert parse_bool_loose("-") is False

    def test_empty_returns_none(self) -> None:
        assert parse_bool_loose("") is None
        assert parse_bool_loose("   ") is None
        assert parse_bool_loose(None) is None

    def test_arbitrary_text_treated_as_truthy(self) -> None:
        # EMIS pone listas de países en Export — eso indica actividad exportadora.
        assert parse_bool_loose("US, CA, MX") is True


class TestParseCsvList:
    def test_basic(self) -> None:
        assert parse_csv_list("US, CA, MX") == ("US", "CA", "MX")

    def test_strips_blanks(self) -> None:
        assert parse_csv_list(" US , , MX ") == ("US", "MX")

    def test_empty(self) -> None:
        assert parse_csv_list("") == ()
        assert parse_csv_list(None) == ()


class TestParseCoord:
    def test_simple_float(self) -> None:
        assert parse_coord(-99.58) == -99.58

    def test_string(self) -> None:
        assert parse_coord("-99.58 W") == -99.58

    def test_empty(self) -> None:
        assert parse_coord("") is None
        assert parse_coord(None) is None


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("  3,500 (2024)  ", 3500),
        ("180 employees", 180),
        ("0 (2020)", 0),
    ],
)
def test_parse_employees_param(raw: str, expected: int) -> None:
    assert parse_employees(raw) == expected
