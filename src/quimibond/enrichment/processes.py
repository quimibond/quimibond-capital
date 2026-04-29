"""
Detector de procesos Quimibond presentes en una empresa.

Devuelve la tupla de proceso names (los keys del YAML) que matchean por
keyword en activity_description / main_products / main_emis.

Orden de salida estable (mismo que el YAML).
"""

from __future__ import annotations

from quimibond.config_loader import Classifiers
from quimibond.enrichment.subsector import _build_haystack
from quimibond.models import RawCompany


def detect_quimibond_processes(
    raw: RawCompany,
    classifiers: Classifiers,
) -> tuple[str, ...]:
    """Lista de procesos Quimibond detectados (orden estable según YAML)."""
    haystack = _build_haystack(raw)
    if not haystack:
        return ()

    detected: list[str] = []
    for proc_name, rule in classifiers.quimibond_processes.items():
        if any(kw.lower() in haystack for kw in rule.keywords):
            detected.append(proc_name)
    return tuple(detected)
