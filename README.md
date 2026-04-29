# Quimibond Capital — Pipeline PE

Pipeline reproducible que genera el workbook de pipeline PE para Quimibond
Capital, vehículo de consolidación industrial textil mexicano.

## Quickstart

```bash
git clone <repo>
cd quimibond-capital
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

cp .env.example .env  # editar con INEGI_TOKEN si vas a usar fuente DENUE

quimibond config validate
pytest
mypy src/
```

## Estado

Sistema en desarrollo iterativo por fases (F1 → F6). Ver `CLAUDE.md` para el
plan completo y las decisiones de arquitectura.

- **F1 (en este branch):** scaffolding, models pydantic, config YAMLs, CLI stub.
- **F2:** ingestion EMIS.
- **F3:** enrichment.
- **F4:** clasificación PE + invariantes.
- **F5:** workbook (11 hojas).
- **F6:** trazabilidad por celda + CLAUDE.md final.

## Estructura

```
config/                          # YAMLs editables (thresholds, playbook, classifiers, families)
src/quimibond/
  models.py                      # pydantic v2 frozen (RawCompany, Company, ...)
  config_loader.py               # carga + valida YAMLs
  cli.py                         # entry point click
  ingestion/                     # EMIS, DENUE, ...
  enrichment/                    # subsector, processes, shareholders, ...
  pe_classification/             # role, fatigue, levers, arbitrage, saturation
  scoring/
  output/sheets/                 # una clase por hoja del workbook
  validation/                    # invariantes pre-output
  traceability/                  # cell lineage
tests/
  unit/                          # pytest unit
  integration/                   # end-to-end con fixtures
  fixtures/                      # sample EMIS data
data/                            # gitignored: raw/, interim/, processed/
```

## Comandos

```bash
quimibond config show
quimibond config validate
quimibond pipeline run --input data/raw/emis_export.xlsx
quimibond enrich --input data/raw/emis_export.xlsx --output data/interim/enriched.parquet
quimibond classify --input data/interim/enriched.parquet --output data/interim/classified.parquet
quimibond workbook --input data/interim/classified.parquet --output data/processed/
quimibond validate --input data/interim/classified.parquet
quimibond inspect --emis-id 8340045 --input data/interim/classified.parquet
```
