"""Source loaders del pipeline (EMIS, DENUE, ...)."""

from quimibond.ingestion.base import SourceLoader
from quimibond.ingestion.emis import EmisLoader

__all__ = ["EmisLoader", "SourceLoader"]
