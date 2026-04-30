"""
Protocolo común de SheetBuilder.

Cada hoja del workbook implementa este Protocol y se invoca desde
WorkbookOrchestrator. Cada builder es independiente — puede reutilizar
helpers comunes de `output.helpers` pero NO depende del estado de otra hoja.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from openpyxl.workbook import Workbook
from openpyxl.worksheet.worksheet import Worksheet

from quimibond.config_loader import Config
from quimibond.models import PipelineData
from quimibond.output.styles import StyleSet


@runtime_checkable
class SheetBuilder(Protocol):
    """Cada hoja implementa este protocolo."""

    name: str  # nombre exacto que aparece en la pestaña

    def build(
        self,
        wb: Workbook,
        ws: Worksheet,
        data: PipelineData,
        config: Config,
        styles: StyleSet,
    ) -> None:
        """
        Llena el worksheet `ws` que ya fue creado con `wb.create_sheet(name)`.

        - Debe ser idempotente: dos llamadas con el mismo input producen el
          mismo output.
        - No debe acceder a otras hojas del workbook.
        - Si una columna lleva fórmula Excel para que sea editable, asegurar
          que no rompe si el usuario no recalcula.
        """
        ...
