# CLAUDE.md — Quimibond Capital PE Pipeline

Léelo completo antes de tocar código. Este archivo es la única referencia
autoritativa para sesiones de Claude Code en este repo.

---

## Contexto de negocio (NO opcional)

**Quimibond Capital** es la holding que adquiere targets. **Quimibond**
(Productora de No Tejidos Quimibond S.A. de C.V.) es la empresa operativa
ancla en Toluca: tejido circular + tintorería + acabado para clientes
Tier-1 automotrices (LEAR, SHAWMUT). Jose es director de admón y finanzas
en Quimibond y arquitecto de la tesis.

La tesis es un **roll-up clásico**: comprar empresas familiares textiles
mexicanas a 4–6× EBITDA integrándolas alrededor de Quimibond como ancla
operativa, vendiendo el consolidado a 8–9×. Aprovecha nearshoring + T-MEC +
transición EVs + fragmentación del sector mexicano.

**Output del pipeline:** un workbook Excel multi-hoja con clasificación
PE de un universo de empresas textiles mexicanas. Input principal: export
EMIS / ISI Markets (~700 empresas). Fuentes secundarias futuras:
DENUE/INEGI, Statista, Capital IQ, CANAINTEX.

**Esto NO es software de producción.** Es una herramienta operativa para
que Jose tome decisiones de M&A. Prioridad: **datos correctos y trazables**,
no abstracciones elegantes — pero **sí robustez de tipos, tests e
invariantes**, porque las decisiones de millones se basan en este output.

---

## Arquitectura

```
config/                          # editable, validado por pydantic
  thresholds.yaml                # cortes de tamaño/edad/saturación
  pe_playbook.yaml               # múltiplos, pesos, tasas de descuento
  classifiers.yaml               # keywords subsector / proceso / cliente
  families.yaml                  # apellidos textiles MX clásicos

src/quimibond/
  models.py                      # pydantic v2 frozen — RawCompany, Company, ...
  config_loader.py               # carga + valida YAMLs
  logging_setup.py               # structlog
  cli.py                         # entry point click

  ingestion/                     # SourceLoader implementations
    base.py                      # protocolo SourceLoader
    emis.py                      # EMIS xlsx
    denue.py                     # DENUE INEGI (futuro)
    statista.py                  # stub
    capital_iq.py                # stub

  enrichment/
    normalizers.py               # parse_revenue, parse_employees, ...
    shareholders.py              # detección familia, capital origin
    subsector.py                 # clasificador subsector + priority
    processes.py                 # detector procesos Quimibond
    clients.py                   # tipo cliente B2B

  pe_classification/
    role.py                      # Platform/Bolt-on/Tuck-in/Strategic
    fatigue.py                   # owner fatigue scoring
    levers.py                    # tres palancas + score combinado
    arbitrage.py                 # LBO simplificado, MOIC, IRR
    saturation.py                # análisis por subsegmento

  scoring/
    composite.py                 # ranking final

  output/
    workbook.py                  # orquestador
    styles.py                    # NamedStyles centralizadas
    sheets/                      # una clase por hoja
      base.py                    # SheetBuilder protocol
      inicio.py
      universo_raw.py
      pipeline_pe.py
      tres_palancas.py
      multiple_arbitrage.py
      owner_fatigue.py
      saturation_check.py
      vista_familiar.py
      investment_memo.py
      rubrica_pe.py
      fuentes.py

  validation/
    invariants.py                # asserts de runtime ANTES de output

  traceability/
    lineage.py                   # CellLineage, openpyxl comments

tests/
  unit/                          # pytest unit
  integration/                   # end-to-end con fixtures
  fixtures/                      # emis_sample_50.xlsx, expected_outputs.json

data/                            # gitignored
  raw/                           # exports EMIS originales
  interim/                       # parquet enriquecido / clasificado
  processed/                     # workbook final
```

---

## Stack técnico (no negociable)

- **Python 3.11+**, type hints estrictos, **mypy strict** sin warnings.
- **Pydantic v2** con `frozen=True` para inmutabilidad.
- **pyproject.toml** con hatchling (no `requirements.txt` suelto).
- **pytest** + `pytest-cov` (objetivo 80% en `enrichment/`, `pe_classification/`, `scoring/`).
- **structlog** estructurado — NO `print()`, NO `logging.basicConfig()` directo.
- **click** para CLI.
- **openpyxl** para workbook (LibreOffice recalc para fórmulas).
- **rapidfuzz** para fuzzy matching de nombres.
- Sin deps exóticas. Cualquier dep nueva requiere justificación.

---

## Plan de fases

| Fase | Estado | Qué entrega |
|------|--------|-------------|
| **F1** | ✅ Completada | Scaffolding, models, config YAMLs, CLI stub, tests + mypy strict pasando. |
| **F2** | Pendiente | `ingestion/emis.py` + tests con fixture. Requiere export1 de EMIS pusheado. |
| **F3** | Pendiente | `enrichment/*.py` (normalizers, shareholders, subsector, processes, clients). |
| **F4** | Pendiente | `pe_classification/*.py` + `validation/invariants.py`. |
| **F5** | Pendiente | `output/workbook.py` + las 11 hojas. |
| **F6** | Pendiente | `traceability/lineage.py`, recalc helper, README/CLAUDE.md finales. |

Cada fase pasa pytest + mypy strict antes de la siguiente. Commits atómicos
por fase con prefijo `F<n>:` en el mensaje.

---

## Principios non-negotiable

### 1. Configuración fuera del código
Toda decisión de negocio (thresholds, múltiplos, keywords, familias) vive en
`config/*.yaml`. Si te encuentras hardcodeando un número o un keyword en
`.py`, **detente**: muévelo al YAML.

### 2. Modelos pydantic estrictos y frozen
- `frozen=True` en todos los modelos del dominio.
- Campos opcionales con `| None`, no `Optional[...]`.
- Validaciones de dominio dentro del modelo (`field_validator`, `model_validator`).
- Si un YAML viola las invariantes pydantic, el pipeline NO arranca.

### 3. Determinismo e idempotencia
- Iteraciones siempre con orden explícito (`sorted()`, no order de dict).
- IDs estables: usa `emis_id` como key primaria.
- Sin random sin seed.
- Funciones puras: `classify_role(company, config) -> PERole` sin side effects.
- El workbook generado dos veces con el mismo input debe ser byte-idéntico
  (excepto timestamps de metadata).

### 4. Trazabilidad por celda (F6)
Cada valor calculado en el workbook debe poder explicarse via
`CellLineage(value, source, formula, inputs)`. Las celdas calculadas
críticas llevan comment openpyxl con su lineage.

### 5. Validación con invariantes (F4)
Antes de generar el workbook, `validation/invariants.assert_invariants()`
verifica:
- No duplicados por `emis_id`.
- Todos los `pe_role` válidos.
- `scoring_weights` suman 1.0.
- `lever_combined ∈ [0, 1]` para todas.
- `PLATFORM_CANDIDATE` ⇒ `revenue_usd_mm >= platform_min`.
- `lever_combined == mean(cost, revenue, arbitrage)` dentro de tolerancia (o
  según fórmula explícita del playbook).

Si una invariante falla → exit 1 con stack trace claro. Sin workbook.

### 6. Testing real
- TDD cuando sea posible: test antes que implementación.
- Cada función pública con ≥3 tests (happy, edge, invalid).
- Fixtures comunes en `tests/conftest.py`.
- Sample EMIS reducido en `tests/fixtures/` (50 empresas representativas)
  para integration tests rápidos.

### 7. CLI clara
Subcomandos en `cli.py`:
```
quimibond pipeline run         end-to-end
quimibond enrich               solo enriquecer
quimibond classify             solo clasificar
quimibond workbook             solo workbook
quimibond validate             solo invariantes
quimibond inspect --emis-id X  detalle de una empresa
quimibond config show          imprime config cargada
quimibond config validate      valida YAMLs
```

### 8. Logging estructurado
```python
import structlog
log = structlog.get_logger()

log.info("pipeline.start", emis_input=path, total_rows=700)
log.info("classification.role_assigned",
         company=name, role="PRIMARY_BOLT_ON", score=0.77)
log.warning("missing_revenue", emis_id=id, action="set_unknown_fit")
log.error("invariant_failed", invariant="weights_sum_to_one", actual=0.99)
```

---

## Anti-patrones

❌ NO uses `os.path` — usa `pathlib.Path`.
❌ NO uses `print()` para debugging — usa structlog.
❌ NO uses `requirements.txt` — usa `pyproject.toml`.
❌ NO uses `assert` para validación de runtime — usa exceptions explícitas
   (assert solo en tests).
❌ NO hardcodees keywords en `.py` — todo en `config/classifiers.yaml`.
❌ NO permitas que dos hojas accedan a la misma data por caminos distintos —
   todo pasa por `PipelineData`.
❌ NO uses `pd.read_excel` directo — encapsula en `EmisLoader`.
❌ NO commits de archivos en `data/` — solo `tests/fixtures/`.
❌ NO generes el workbook si las invariantes fallan.
❌ NO mezcles lógica de negocio con presentación.
❌ NO inventes datos. Si la fuente no tiene un campo, queda `None`.

---

## Convenciones específicas de Jose

1. **JSON-RPC sobre XML-RPC** (preferencia general, aplica si extiendes a Odoo).
2. **Tasa de descuento 12%** y **tipo de cambio 20 MXN/USD** como defaults
   (en `config/pe_playbook.yaml`).
3. **Comentarios en español** en lógica de negocio; inglés en utilidades puras
   está bien.
4. **Lenguaje directo y claro** — sin rodeos en logs ni docs.
5. **Outputs profesionales** — el workbook que vea Jose o un LP debe estar
   listo sin ajustes.

---

## Cómo añadir una fuente nueva

1. Crear `src/quimibond/ingestion/<fuente>.py` que implemente `SourceLoader`.
2. Sus `RawCompany.source` debe ser un identificador estable (ej. `"DENUE"`).
3. Mappear los campos nativos al esquema de `RawCompany`. Lo que no exista
   queda `None` — no inventar.
4. Tests unitarios con un fixture de `tests/fixtures/<fuente>_sample.xlsx`
   o `.json`.
5. Agregar al CLI vía argumento `--source <fuente>` si aplica.
6. Documentar la fuente en `docs/<FUENTE>.md` (limitaciones, rate limits,
   campos disponibles).

---

## Cuando estés en duda

- **Estructura de datos de una fuente nueva** → primero hacer query de
  prueba y ver el JSON/xlsx real antes de codear el parser.
- **Lógica de negocio** → preguntar a Jose. No asumir. No inventar
  thresholds.
- **Dependencias nuevas** → preferir librerías ya en `pyproject.toml`. Cualquier dep
  nueva requiere justificación.

---

## Forma de reportar avance

Bullets concisos:
- Qué completaste.
- Qué tests pasan (`pytest -k <pattern>`).
- Qué decisiones tomaste y por qué.
- Qué te falta o qué necesitas confirmar con Jose.

No expliques el código línea por línea. Asume que Jose sabe Python y conoce
la tesis. Solo confirma decisiones cuando haya ambigüedad real.
