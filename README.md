# Quimibond Capital — Pipeline PE

Pipeline reproducible que genera un workbook de clasificación PE para
Quimibond Capital, vehículo de consolidación textil mexicano.

Tesis: roll-up de empresas familiares textiles MX a 4–6× EBITDA, integradas
alrededor de Quimibond (operadora ancla en Toluca: tejido circular +
tintorería + acabado para clientes Tier-1 automotrices) y vendidas a 8–9×
una vez consolidadas. Aprovecha nearshoring + T-MEC + transición EVs +
fragmentación del sector.

## Quickstart

```bash
git clone <repo>
cd quimibond-capital
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

cp .env.example .env       # editar con INEGI_TOKEN si vas a usar DENUE
quimibond config validate  # verifica que los YAMLs están bien
```

Coloca el export EMIS en `data/raw/emis/EMIS_export_<fecha>.xlsx` (gitignored)
y corre:

```bash
quimibond pipeline run \
  --input data/raw/emis/EMIS_export_2026-04-29.xlsx \
  --output-dir data/processed
# ✓ Workbook generado: data/processed/Quimibond_Capital_PE_Pipeline_2026-04-30.xlsx
#   Empresas: 698 · Subsectores: 13
```

Para que las fórmulas de "Multiple Arbitrage" muestren valores recalculados
al abrir el archivo (en máquinas sin Excel), corre el recalc helper:

```bash
python scripts/recalc.py data/processed/Quimibond_Capital_PE_Pipeline_2026-04-30.xlsx
```

Requiere LibreOffice instalado.

## El workbook (11 hojas)

| # | Hoja | Para qué |
|---|---|---|
| 1 | Inicio | Portada + stats agregadas + mapa del workbook. |
| 2 | Universo Raw | Las 698 empresas con todos los campos enriquecidos. |
| 3 | Pipeline PE | Vista operativa: PLATFORM/BOLT_ON/TUCK_IN ordenadas por combined. |
| 4 | Tres Palancas | Detalle cost/revenue/arbitrage con justificaciones. |
| 5 | Multiple Arbitrage | LBO simplificado con asunciones EDITABLES (amarillo). |
| 6 | Owner Fatigue | Score 0–1 + signals detectados. |
| 7 | Saturation Check | Análisis de saturación por subsegmento. |
| 8 | Vista Familiar | Targets agrupados por familia textil clásica. |
| 9 | Investment Memo | Estructura para presentación a LPs. |
| 10 | Rúbrica PE | Playbook documentado: thresholds, múltiplos, pesos. |
| 11 | Fuentes | Roadmap multi-fuente. |

Las celdas calculadas críticas tienen un comentario hover con el detalle de
cómo se calculó (CellLineage).

## Estructura

```
config/                          # YAMLs editables — la única fuente de verdad de los thresholds
  thresholds.yaml                # cortes de tamaño/edad/saturación
  pe_playbook.yaml               # múltiplos, pesos, tasas de descuento
  classifiers.yaml               # keywords + naics_prefixes por subsector/cliente
  families.yaml                  # apellidos textiles MX clásicos

src/quimibond/
  models.py                      # pydantic v2 frozen
  config_loader.py               # validación pydantic de cada YAML
  logging_setup.py               # structlog (console o JSON)
  cli.py                         # entry point click
  ingestion/{base,emis,emis_parsers}.py
  enrichment/{normalizers,subsector,processes,clients,shareholders}.py
  pe_classification/{role,fatigue,levers,arbitrage,saturation}.py
  output/{workbook,styles,helpers}.py
  output/sheets/{1_inicio…11_fuentes}.py
  validation/invariants.py
  traceability/lineage.py

tests/
  unit/                          # 200+ tests por módulo
  integration/                   # end-to-end con fixture de 50 empresas
  fixtures/emis_sample_50.xlsx

scripts/
  build_emis_fixture.py          # genera el sample 50 desde el export real
  recalc.py                      # LibreOffice headless recalc
```

## Comandos disponibles

```bash
quimibond config show          # imprime la config cargada (json)
quimibond config validate      # valida los YAMLs

quimibond pipeline run \
  --input <emis.xlsx> \
  --output-dir <dir>           # ingest → enrich → classify → invariants → workbook

quimibond workbook \
  --input <emis.xlsx> \
  --output <ruta.xlsx>         # mismo flujo, output one-shot
```

## Cómo ajustar criterios

Toda decisión de negocio vive en `config/*.yaml` y se valida con pydantic
al arrancar el pipeline. No hay valores hardcoded en `.py`. Edita el YAML,
re-ejecuta — sin tocar código.

Ejemplos:
- Cambiar exit multiple objetivo: `config/pe_playbook.yaml` →
  `exit_multiple_default: 9.0`.
- Subir el threshold de "platform": `config/thresholds.yaml` →
  `revenue_brackets_usd_mm.platform_min: 60`.
- Agregar una nueva familia textil clásica: `config/families.yaml` añadir
  el apellido a la lista.
- Agregar keywords o NAICS prefix para un subsector: `config/classifiers.yaml`.

Si un YAML viola las invariantes (pesos no suman 1, brackets desordenados,
score fuera de [0,1]) el pipeline NO arranca y reporta el error puntual.

## Calidad

- **240 tests** (unit + integration), `pytest -q` los corre en <2s.
- **mypy strict** sin warnings sobre 43 archivos.
- **Invariantes pre-output** validan el dataset antes de generar el workbook
  — si fallan, exit 1 con stack trace claro y NO se genera el output.

```bash
pytest                # 240 verdes
mypy src/quimibond    # 0 issues
```

## Estado

| Fase | Status | Entrega |
|---|---|---|
| F1 | ✅ | Scaffolding, models pydantic, config YAMLs, CLI stub. |
| F2 | ✅ | Ingestion EMIS (loader + parsers, 698 empresas validadas). |
| F3 | ✅ | Enrichment (subsector, processes, clients, shareholders) + NAICS-aware. |
| F4 | ✅ | Clasificación PE (role, fatigue, levers, arbitrage, saturation) + invariantes. |
| F5 | ✅ | Workbook con 11 hojas + CLI conectado end-to-end. |
| F6 | ✅ | Trazabilidad por celda + recalc helper + docs finales. |

## Para futuras sesiones de Claude Code

Lee `CLAUDE.md` antes de tocar nada — define principios, anti-patrones, y
convenciones específicas. Cualquier feature nueva debe respetar:

- Configuración fuera del código (todo en YAML).
- Pydantic frozen, mypy strict, structlog (NO `print()`).
- TDD cuando sea posible. Cada función pública con ≥3 tests.
- Si añades una fuente de datos, implementa `SourceLoader` y documenta en
  `docs/<FUENTE>.md`.
