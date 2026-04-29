"""
CLI de Quimibond Capital pipeline.

Subcomandos (todos stub salvo `config show/validate` en F1):

    quimibond pipeline run        — orquesta ingestion → enrichment → classify → workbook
    quimibond enrich              — solo enriquecimiento
    quimibond classify            — solo clasificación PE
    quimibond workbook            — solo workbook
    quimibond validate            — corre invariantes
    quimibond inspect             — detalle de una empresa por id
    quimibond config show         — muestra config cargada
    quimibond config validate     — valida YAMLs sin correr nada más
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import click
import structlog

from quimibond.config_loader import Config, load_config
from quimibond.logging_setup import configure_logging

DEFAULT_CONFIG_DIR = Path("config")
log = structlog.get_logger()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_or_die(config_dir: Path) -> Config:
    try:
        return load_config(config_dir)
    except Exception as exc:  # noqa: BLE001  — CLI debe morir limpio
        click.echo(f"ERROR cargando config en {config_dir}: {exc}", err=True)
        raise click.exceptions.Exit(2) from exc


def _config_to_dict(config: Config) -> dict[str, Any]:
    return config.model_dump(mode="json")


# ---------------------------------------------------------------------------
# Root group
# ---------------------------------------------------------------------------


@click.group()
@click.option("--log-level", default="INFO", show_default=True,
              type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"]))
@click.option("--log-format", default="console", show_default=True,
              type=click.Choice(["console", "json"]))
@click.pass_context
def cli(ctx: click.Context, log_level: str, log_format: str) -> None:
    """Quimibond Capital — pipeline PE de consolidación textil México."""
    configure_logging(level=log_level, fmt=log_format)  # type: ignore[arg-type]
    ctx.ensure_object(dict)


# ---------------------------------------------------------------------------
# pipeline group
# ---------------------------------------------------------------------------


@cli.group()
def pipeline() -> None:
    """Comandos de pipeline end-to-end."""


@pipeline.command("run")
@click.option("--input", "input_path", type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--output", "output_dir", type=click.Path(path_type=Path), default=Path("data/processed"))
@click.option("--config-dir", type=click.Path(exists=True, path_type=Path), default=DEFAULT_CONFIG_DIR)
def pipeline_run(input_path: Path, output_dir: Path, config_dir: Path) -> None:
    """Pipeline completo: ingest → enrich → classify → validate → workbook."""
    config = _load_or_die(config_dir)
    log.info("pipeline.start", input=str(input_path), output=str(output_dir),
             config_companies=config.thresholds.revenue_brackets_usd_mm.platform_min)
    raise click.exceptions.UsageError("F1: pipeline run no implementado todavía (llega en F5).")


# ---------------------------------------------------------------------------
# Etapas individuales
# ---------------------------------------------------------------------------


@cli.command()
@click.option("--input", "input_path", type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--output", "output_path", type=click.Path(path_type=Path), required=True)
@click.option("--config-dir", type=click.Path(exists=True, path_type=Path), default=DEFAULT_CONFIG_DIR)
def enrich(input_path: Path, output_path: Path, config_dir: Path) -> None:
    """Solo enriquecimiento: RawCompany → Company sin clasificar."""
    _load_or_die(config_dir)
    raise click.exceptions.UsageError("F1: enrich no implementado (llega en F3).")


@cli.command()
@click.option("--input", "input_path", type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--output", "output_path", type=click.Path(path_type=Path), required=True)
@click.option("--config-dir", type=click.Path(exists=True, path_type=Path), default=DEFAULT_CONFIG_DIR)
def classify(input_path: Path, output_path: Path, config_dir: Path) -> None:
    """Solo clasificación PE."""
    _load_or_die(config_dir)
    raise click.exceptions.UsageError("F1: classify no implementado (llega en F4).")


@cli.command()
@click.option("--input", "input_path", type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--output", "output_path", type=click.Path(path_type=Path), required=True)
@click.option("--config-dir", type=click.Path(exists=True, path_type=Path), default=DEFAULT_CONFIG_DIR)
def workbook(input_path: Path, output_path: Path, config_dir: Path) -> None:
    """Solo generación del workbook (asume clasificación previa)."""
    _load_or_die(config_dir)
    raise click.exceptions.UsageError("F1: workbook no implementado (llega en F5).")


@cli.command()
@click.option("--input", "input_path", type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--config-dir", type=click.Path(exists=True, path_type=Path), default=DEFAULT_CONFIG_DIR)
def validate(input_path: Path, config_dir: Path) -> None:
    """Corre invariantes contra un dataset clasificado."""
    _load_or_die(config_dir)
    raise click.exceptions.UsageError("F1: validate no implementado (llega en F4).")


@cli.command()
@click.option("--emis-id", required=True, help="EMIS ID de la empresa a inspeccionar.")
@click.option("--input", "input_path", type=click.Path(exists=True, path_type=Path), required=True)
def inspect(emis_id: str, input_path: Path) -> None:
    """Imprime el detalle de una empresa por EMIS ID."""
    raise click.exceptions.UsageError("F1: inspect no implementado (llega en F4).")


# ---------------------------------------------------------------------------
# config group
# ---------------------------------------------------------------------------


@cli.group("config")
def config_group() -> None:
    """Inspección y validación de YAMLs de config."""


@config_group.command("show")
@click.option("--config-dir", type=click.Path(exists=True, path_type=Path), default=DEFAULT_CONFIG_DIR)
def config_show(config_dir: Path) -> None:
    """Imprime la config cargada como JSON (todas las invariantes ya validadas)."""
    config = _load_or_die(config_dir)
    click.echo(json.dumps(_config_to_dict(config), indent=2, ensure_ascii=False, default=str))


@config_group.command("validate")
@click.option("--config-dir", type=click.Path(exists=True, path_type=Path), default=DEFAULT_CONFIG_DIR)
def config_validate(config_dir: Path) -> None:
    """Valida los YAMLs y termina con exit 0 si todo OK."""
    _load_or_die(config_dir)
    click.echo(f"OK — config en {config_dir} válida.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    cli(obj={})


if __name__ == "__main__":
    main()
