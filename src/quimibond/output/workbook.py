"""
Orquestador del workbook.

Crea el .xlsx, registra estilos, ejecuta los SheetBuilders en orden, y
guarda. Es el único punto de entrada para generar el output.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import structlog
from openpyxl import Workbook

from quimibond.config_loader import Config
from quimibond.models import PipelineData
from quimibond.output.sheets.base import SheetBuilder
from quimibond.output.sheets.fuentes import FuentesSheet
from quimibond.output.sheets.inicio import InicioSheet
from quimibond.output.sheets.investment_memo import InvestmentMemoSheet
from quimibond.output.sheets.multiple_arbitrage import MultipleArbitrageSheet
from quimibond.output.sheets.owner_fatigue import OwnerFatigueSheet
from quimibond.output.sheets.pipeline_pe import PipelinePESheet
from quimibond.output.sheets.rubrica_pe import RubricaPESheet
from quimibond.output.sheets.saturation_check import SaturationCheckSheet
from quimibond.output.sheets.tres_palancas import TresPalancasSheet
from quimibond.output.sheets.universo_raw import UniversoRawSheet
from quimibond.output.sheets.vista_familiar import VistaFamiliarSheet
from quimibond.output.styles import StyleSet
from quimibond.validation import assert_invariants

log = structlog.get_logger()


def default_builders() -> tuple[SheetBuilder, ...]:
    """Las 11 hojas, en el orden exacto del workbook final."""
    return (
        InicioSheet(),
        UniversoRawSheet(),
        PipelinePESheet(),
        TresPalancasSheet(),
        MultipleArbitrageSheet(),
        OwnerFatigueSheet(),
        SaturationCheckSheet(),
        VistaFamiliarSheet(),
        InvestmentMemoSheet(),
        RubricaPESheet(),
        FuentesSheet(),
    )


def generate_workbook(
    data: PipelineData,
    config: Config,
    output_path: Path,
    *,
    builders: Sequence[SheetBuilder] | None = None,
    skip_invariants: bool = False,
) -> Path:
    """
    Genera el workbook completo. Levanta InvariantViolation si la data falla
    invariantes (a menos que skip_invariants=True para tests internos).

    Returns:
        La ruta donde se guardó el workbook.
    """
    if not skip_invariants:
        assert_invariants(data, config)

    builders = builders or default_builders()

    log.info(
        "workbook.generate.start",
        output=str(output_path),
        n_companies=data.n_companies,
        n_sheets=len(builders),
    )

    wb = Workbook()
    # openpyxl crea una hoja default — la borramos y vamos a añadir las nuestras
    default_sheet = wb.active
    if default_sheet is not None:
        wb.remove(default_sheet)

    styles = StyleSet.register(wb)

    for builder in builders:
        ws = wb.create_sheet(title=builder.name)
        log.debug("workbook.sheet.start", sheet=builder.name)
        builder.build(wb, ws, data, config, styles)
        log.debug("workbook.sheet.done", sheet=builder.name)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(output_path)
    log.info("workbook.generate.done", output=str(output_path))
    return output_path
