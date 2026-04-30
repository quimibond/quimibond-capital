"""
CLI de Quimibond Capital pipeline.

Subcomandos:

    quimibond pipeline run        — orquesta ingestion → enrichment → classify → workbook
    quimibond enrich              — solo enriquecimiento (futuro)
    quimibond classify            — solo clasificación PE (futuro)
    quimibond workbook            — solo workbook (asume input ya clasificado)
    quimibond validate            — corre invariantes (futuro)
    quimibond inspect             — detalle de una empresa por id (futuro)
    quimibond config show         — muestra config cargada
    quimibond config validate     — valida YAMLs sin correr nada más
"""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

import click
import structlog

from quimibond.config_loader import Config, load_config
from quimibond.ingestion import EmisLoader
from quimibond.logging_setup import configure_logging
from quimibond.output import generate_workbook
from quimibond.pe_classification import classify_universe
from quimibond.validation import InvariantViolation

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
@click.option("--output-dir", type=click.Path(path_type=Path), default=Path("data/processed"))
@click.option("--config-dir", type=click.Path(exists=True, path_type=Path), default=DEFAULT_CONFIG_DIR)
@click.option("--source-as-of", type=click.DateTime(formats=["%Y-%m-%d"]), default=None,
              help="Fecha del snapshot del input (default: hoy).")
def pipeline_run(
    input_path: Path,
    output_dir: Path,
    config_dir: Path,
    source_as_of: datetime | None,
) -> None:
    """Pipeline completo: ingest → enrich → classify → validate → workbook."""
    config = _load_or_die(config_dir)
    today = date.today()
    snapshot_date = source_as_of.date() if source_as_of else today

    log.info(
        "pipeline.start",
        input=str(input_path),
        output_dir=str(output_dir),
        snapshot=snapshot_date.isoformat(),
    )

    raws = EmisLoader().load(input_path, source_as_of=snapshot_date)
    data = classify_universe(raws, config, today=today)

    output_path = output_dir / f"Quimibond_Capital_PE_Pipeline_{today.isoformat()}.xlsx"
    try:
        generate_workbook(data, config, output_path)
    except InvariantViolation as exc:
        click.echo(f"ERROR: invariante violada — {exc}", err=True)
        raise click.exceptions.Exit(1) from exc

    click.echo(f"✓ Workbook generado: {output_path}")
    click.echo(f"  Empresas: {data.n_companies} · Subsectores: {len(data.saturation)}")


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
@click.option("--input", "input_path", type=click.Path(exists=True, path_type=Path), required=True,
              help="EMIS xlsx (carga + clasifica + genera workbook en un paso).")
@click.option("--output", "output_path", type=click.Path(path_type=Path), required=True)
@click.option("--config-dir", type=click.Path(exists=True, path_type=Path), default=DEFAULT_CONFIG_DIR)
@click.option("--source-as-of", type=click.DateTime(formats=["%Y-%m-%d"]), default=None)
def workbook(
    input_path: Path,
    output_path: Path,
    config_dir: Path,
    source_as_of: datetime | None,
) -> None:
    """Genera el workbook desde un EMIS xlsx (one-shot)."""
    config = _load_or_die(config_dir)
    today = date.today()
    snapshot_date = source_as_of.date() if source_as_of else today

    raws = EmisLoader().load(input_path, source_as_of=snapshot_date)
    data = classify_universe(raws, config, today=today)
    try:
        generate_workbook(data, config, output_path)
    except InvariantViolation as exc:
        click.echo(f"ERROR: invariante violada — {exc}", err=True)
        raise click.exceptions.Exit(1) from exc
    click.echo(f"✓ Workbook generado: {output_path}")


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
