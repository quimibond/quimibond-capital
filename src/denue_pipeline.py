"""
Pipeline principal de descarga DENUE.

Itera por combinaciones NAICS × entidad × estrato y guarda raw + un CSV
agregado en data/raw/.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

import click
import pandas as pd

from src import config
from src.denue_client import DenueClient

logger = logging.getLogger(__name__)


def correr_pipeline(
    naics_list: list[str],
    entidades: list[str],
    estratos: list[str],
    raw_only: bool = False,
) -> Path:
    """
    Corre el pipeline completo de descarga.

    Returns:
        Path al CSV consolidado raw.
    """
    client = DenueClient()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    raw_dir = config.RAW_DIR / timestamp
    raw_dir.mkdir(parents=True, exist_ok=True)

    todos: list[dict] = []

    for naics, entidad, estrato, establecimientos in client.iterar_combinaciones(
        naics_list=naics_list,
        entidades=entidades,
        estratos=estratos,
    ):
        # Guardar raw por combinación (debugging y auditoría)
        archivo_raw = raw_dir / f"naics{naics}_ent{entidad}_estrato{estrato}.json"
        archivo_raw.write_text(
            json.dumps(establecimientos, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        # Anotar metadata para deduplicación posterior
        for est in establecimientos:
            est["_naics_query"] = naics
            est["_entidad_query"] = entidad
            est["_estrato_query"] = estrato
        todos.extend(establecimientos)
        logger.info(
            "  → %d establecimientos (acumulado: %d)",
            len(establecimientos),
            len(todos),
        )

    # Consolidar a CSV
    if not todos:
        logger.warning("No se recibieron resultados. Revisa filtros y token.")
        return raw_dir

    df = pd.DataFrame(todos)
    csv_path = config.RAW_DIR / f"denue_raw_{timestamp}.csv"
    df.to_csv(csv_path, index=False, encoding=config.ENCODING)

    logger.info("=" * 60)
    logger.info("Descarga completa.")
    logger.info("Total establecimientos: %d", len(todos))
    logger.info("Archivos raw por combinación: %s", raw_dir)
    logger.info("CSV consolidado: %s", csv_path)
    logger.info("=" * 60)

    if not raw_only:
        logger.info("Siguiente paso: python -m src.cleaning")

    return csv_path


@click.command()
@click.option(
    "--naics",
    multiple=True,
    help="Códigos NAICS específicos (default: todos los del config).",
)
@click.option(
    "--estados",
    multiple=True,
    help="Claves de entidad (default: todos los del config).",
)
@click.option(
    "--estratos",
    multiple=True,
    help="Códigos de estrato (default: 5, 6, 7).",
)
@click.option("--raw-only", is_flag=True, help="Solo descarga, sin pasos siguientes.")
@click.option("-v", "--verbose", is_flag=True, help="Logging DEBUG.")
def main(
    naics: tuple[str, ...],
    estados: tuple[str, ...],
    estratos: tuple[str, ...],
    raw_only: bool,
    verbose: bool,
) -> None:
    """Corre el pipeline DENUE end-to-end."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(message)s")

    naics_list = list(naics) if naics else list(config.NAICS_OBJETIVO.keys())
    entidades = list(estados) if estados else list(config.ESTADOS_OBJETIVO.keys())
    estratos_list = list(estratos) if estratos else config.ESTRATOS_OBJETIVO

    logger.info("Configuración:")
    logger.info("  NAICS: %s", naics_list)
    logger.info("  Estados: %s", entidades)
    logger.info("  Estratos: %s", estratos_list)
    logger.info("  Total combinaciones: %d", len(naics_list) * len(entidades) * len(estratos_list))

    correr_pipeline(
        naics_list=naics_list,
        entidades=entidades,
        estratos=estratos_list,
        raw_only=raw_only,
    )


if __name__ == "__main__":
    main()
