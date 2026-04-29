"""
Contrato común a toda fuente de datos del pipeline.

Cualquier nuevo SourceLoader (DENUE, Statista, Capital IQ, manual, ...) debe
exponer `.load(path, source_as_of) -> tuple[RawCompany, ...]` y un atributo
`source_name` estable (ej. "EMIS", "DENUE") que aparece en `RawCompany.source`.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Protocol, runtime_checkable

from quimibond.models import RawCompany


@runtime_checkable
class SourceLoader(Protocol):
    """Protocolo para todos los loaders de fuente externa."""

    source_name: str

    def load(self, path: Path, source_as_of: date) -> tuple[RawCompany, ...]:
        """
        Lee el archivo en `path` y emite una tupla inmutable de RawCompany.

        Args:
            path: ruta al archivo de input (xlsx, csv, json, ...).
            source_as_of: fecha del snapshot de la fuente (no la fecha de hoy).

        Raises:
            FileNotFoundError: si `path` no existe.
            ValueError: si el archivo no tiene la estructura esperada.
        """
        ...
