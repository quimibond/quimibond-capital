"""
Tests del config loader. Cargan los YAMLs reales del repo y verifican que las
invariantes pydantic se cumplen — además de probar las que tiene que disparar
explícitamente (pesos no suman 1, brackets desordenados, etc.).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from quimibond.config_loader import Config, load_config


def test_real_config_loads(config: Config) -> None:
    """El config del repo debe cargar sin issues."""
    assert config.thresholds.revenue_brackets_usd_mm.platform_min == 50
    assert config.pe_playbook.exit_multiple_default == 9.0
    assert config.pe_playbook.exchange_rate_mxn_usd == 20.0
    assert "Crítica" in config.pe_playbook.subsector_priority_score
    assert "Subsidiaria/Extranjera" in config.pe_playbook.capital_origin_score
    assert "PLATFORM_CANDIDATE" in config.pe_playbook.role_combined_cap


def test_scoring_weights_sum_to_one(config: Config) -> None:
    w = config.pe_playbook.scoring_weights
    total = w.lever_cost + w.lever_revenue + w.lever_arbitrage
    assert abs(total - 1.0) < 1e-6


def test_classifiers_have_critical_tier(config: Config) -> None:
    critica = config.classifiers.subsectors["Crítica"]
    assert "no_tejidos" in critica.rules


def test_quimibond_processes_listed(config: Config) -> None:
    procs = config.classifiers.quimibond_processes
    expected = {"tejido_circular", "tejido_punto", "tintoreria", "acabado", "recubrimiento"}
    assert expected.issubset(procs.keys())


def test_families_present(config: Config) -> None:
    assert "Quintana" in config.families.families
    assert len(config.families.families) >= 10


def test_buy_multiples_increasing(config: Config) -> None:
    brackets = config.pe_playbook.buy_multiples_by_size
    last_max = -1.0
    seen_null = False
    for b in brackets:
        if b.max_revenue is None:
            assert not seen_null, "solo un bracket null permitido"
            seen_null = True
            continue
        assert b.max_revenue > last_max
        last_max = b.max_revenue


# ---------------------------------------------------------------------------
# Errores controlados
# ---------------------------------------------------------------------------


def _write_yaml(p: Path, data: dict[str, object]) -> None:
    p.write_text(yaml.safe_dump(data), encoding="utf-8")


@pytest.fixture
def bad_config_dir(tmp_path: Path, config_dir: Path) -> Path:
    """Copia el config del repo a tmp_path para que los tests lo muten."""
    target = tmp_path / "config"
    target.mkdir()
    for name in ["thresholds.yaml", "pe_playbook.yaml", "classifiers.yaml", "families.yaml"]:
        (target / name).write_bytes((config_dir / name).read_bytes())
    return target


def test_weights_not_summing_to_one_raises(bad_config_dir: Path) -> None:
    pe = yaml.safe_load((bad_config_dir / "pe_playbook.yaml").read_text())
    pe["scoring_weights"]["lever_cost"] = 0.50  # rompe la suma
    _write_yaml(bad_config_dir / "pe_playbook.yaml", pe)

    with pytest.raises(ValidationError) as exc:
        load_config(bad_config_dir)
    assert "scoring_weights" in str(exc.value)


def test_revenue_brackets_disordered_raises(bad_config_dir: Path) -> None:
    th = yaml.safe_load((bad_config_dir / "thresholds.yaml").read_text())
    th["revenue_brackets_usd_mm"]["bolt_on_max"] = 1.0  # < bolt_on_min
    _write_yaml(bad_config_dir / "thresholds.yaml", th)

    with pytest.raises(ValidationError):
        load_config(bad_config_dir)


def test_buy_multiples_not_increasing_raises(bad_config_dir: Path) -> None:
    pe = yaml.safe_load((bad_config_dir / "pe_playbook.yaml").read_text())
    pe["buy_multiples_by_size"] = [
        {"max_revenue": 50, "multiple": 6.0},
        {"max_revenue": 20, "multiple": 4.5},
        {"max_revenue": None, "multiple": 9.0},
    ]
    _write_yaml(bad_config_dir / "pe_playbook.yaml", pe)

    with pytest.raises(ValidationError):
        load_config(bad_config_dir)


def test_missing_yaml_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_config(tmp_path)


def test_priority_score_out_of_range_raises(bad_config_dir: Path) -> None:
    pe = yaml.safe_load((bad_config_dir / "pe_playbook.yaml").read_text())
    pe["subsector_priority_score"]["Crítica"] = 1.5
    _write_yaml(bad_config_dir / "pe_playbook.yaml", pe)

    with pytest.raises(ValidationError):
        load_config(bad_config_dir)
