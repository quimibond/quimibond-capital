# CLAUDE.md — Quimibond M&A Pipeline

Este archivo orienta a Claude Code para trabajar este proyecto. Léelo completo antes de empezar cualquier tarea.

## Contexto del proyecto

Este pipeline genera el universo de empresas textiles en México como inteligencia para la **tesis de consolidación industrial de Quimibond** (no tejidos automotriz, Toluca). El output final es un CSV maestro que se hace merge con la hoja "2. Universo" del workbook `Pipeline_MA_Textil_Mexico_Quimibond.xlsx`.

**No es un proyecto de software de producción.** Es una herramienta operativa para Jose (director de admón y finanzas, Quimibond). La prioridad es: **datos limpios y accionables**, no abstracciones elegantes.

## Arquitectura

```
quimibond_pipeline/
├── CLAUDE.md                       # este archivo
├── README.md                       # quickstart para humanos
├── .env.example                    # template de variables de entorno
├── .gitignore
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── config.py                   # constantes: NAICS, estados, HTS
│   ├── denue_client.py             # cliente API INEGI/DENUE
│   ├── denue_pipeline.py           # script principal DENUE
│   ├── cleaning.py                 # deduplicación y normalización
│   ├── enrichment.py               # cruce con hoja Universo existente
│   └── workbook_writer.py          # escribe nuevas filas al .xlsx
├── data/                            # raw + intermediate (gitignored)
│   └── .gitkeep
├── output/                          # CSVs finales y workbook actualizado
│   └── .gitkeep
└── docs/
    ├── DENUE_API.md                # notas sobre la API
    ├── NAICS_reference.md          # mapping NAICS → tesis
    └── workflow.md                 # flujo end-to-end
```

## Stack técnico

- **Python 3.11+**
- `requests` para API DENUE
- `pandas` para manipulación
- `openpyxl` para escribir al workbook
- `python-dotenv` para gestión de credenciales
- `rapidfuzz` para deduplicación fuzzy de razones sociales

## Convenciones específicas de Jose

Jose tiene preferencias claras en este proyecto:

1. **JSON-RPC sobre XML-RPC** (preferencia general suya, aplica si extiendes a Odoo)
2. **Tasa de descuento 12%** y **tipo de cambio 20 MXN/USD** como defaults
3. **Comentarios en español** en código orientado a operación; inglés en código de utilidad pura está bien
4. **Lenguaje directo y claro** — sin rodeos en mensajes de log o documentación
5. **Outputs profesionales** — los CSVs que vea Jose deben estar listos para abrir en Excel sin ajustes (encoding utf-8-sig, separador estándar)

## Flujo end-to-end

```
1. Jose obtiene token INEGI       → guarda en .env
2. python -m src.denue_pipeline   → descarga raw a data/raw/
3. python -m src.cleaning         → genera data/clean/denue_clean.csv
4. python -m src.enrichment       → merge con Universo del workbook
                                   → output/targets_consolidado.csv
5. python -m src.workbook_writer  → escribe nuevas filas al .xlsx
                                   → output/Pipeline_MA_Textil_Mexico_Quimibond_v2.xlsx
6. Jose abre el .xlsx, valida, hace scoring.
```

## NAICS objetivo (orden de prioridad)

| NAICS | Descripción | Por qué importa |
|-------|-------------|-----------------|
| 3149 | Otros productos textiles excepto prendas — **incluye no tejidos** | **Core de Quimibond** |
| 3133 | Acabado y telas recubiertas | Recubrimientos automotrices |
| 3169 | Similar cuero / sucedáneos cuero | Interior automotriz |
| 3132 | Fabricación de telas | Tapicería técnica |
| 3131 | Hilado de fibras textiles | Upstream — solo si técnicos |
| 3141 | Alfombras y blancos | Floor mats automotrices |

**Excluir explícitamente:** 3151 (calcetería moda), 3152 (confección de prendas), 3159 (accesorios de vestir).

## Estados objetivo (CVE_ENT INEGI)

Prioritarios (clúster textil): 09 (CDMX), 13 (Hidalgo), 15 (EdoMex), 21 (Puebla), 29 (Tlaxcala)
Secundarios (clúster automotriz): 19 (NL), 05 (Coahuila), 22 (Querétaro), 11 (Guanajuato), 14 (Jalisco)

## Estratos de personal ocupado (DENUE)

Códigos del campo `estrato`:
- 1: 0 a 5 personas
- 2: 6 a 10 personas
- 3: 11 a 30 personas
- 4: 31 a 50 personas
- **5: 51 a 100 personas** ← incluir
- **6: 101 a 250 personas** ← incluir
- **7: 251 y más personas** ← incluir

**Filtro mínimo:** estrato >= 5. Por debajo es taller, no plataforma de consolidación.

## Estructura de columnas del CSV final

El output `targets_consolidado.csv` debe tener **exactamente** estas columnas, en este orden, para hacer paste directo en la hoja "2. Universo" del workbook:

```
ID, Empresa, Subsector, Producto principal, Ubicación, Tamaño Est.,
Empleados Est., Ingresos Est. (MXN mm), Cliente Auto?, Exporta?,
Estructura, Fuente, Notas, Status,
RFC, Teléfono, Email, Web, Latitud, Longitud, Fecha alta, NAICS,
Vol Exp 24m kg, Valor Exp 24m USD, Top cliente, Concentración top1,
Crecimiento 24m, Precio USD/kg, # países destino
```

Las últimas 8 columnas (Veritrade) quedan vacías hasta que Jose tenga acceso a esa fuente.

## Reglas de mapping DENUE → workbook

| Campo DENUE | Campo workbook | Transformación |
|-------------|----------------|----------------|
| `nombre` o `nom_estab` | Empresa | strip + title case |
| `razon_social` | Notas | "Razón social: {valor}" si difiere de Empresa |
| `clase_actividad` | Subsector | mapping NAICS → categoría tesis (ver config.py) |
| `estrato` | Tamaño Est. | mapping 5→"Mediana", 6→"Mediana-Grande", 7→"Grande" |
| `estrato` | Empleados Est. | mapping 5→75, 6→175, 7→500 (punto medio) |
| dirección campos | Ubicación | "{municipio}, {entidad}" |
| `fecha_alta` | Fecha alta | parse a YYYY-MM-DD |
| (todos) | Fuente | "DENUE {YYYY-MM}" |
| (todos) | Status | "Investigar" (default; el scoring real lo hace Jose) |

## Reglas de deduplicación

Una empresa real puede aparecer múltiples veces en DENUE (un establecimiento por planta). Para deduplicar:

1. Agrupa por `razon_social` (si está) o por `nombre` normalizado.
2. Si hay match fuzzy >= 90% en nombre → mismo grupo.
3. Quédate con el establecimiento de **mayor estrato** (más empleados).
4. Suma o concatena: si los establecimientos están en distintos municipios, deja "Plantas: Toluca, Lerma" en Ubicación.

## Cómo validar la salida

Antes de declarar éxito, el pipeline debe:

- [ ] Total de empresas en CSV final entre 150 y 500. Si <100, los filtros están demasiado estrechos. Si >800, demasiado laxos.
- [ ] 0 duplicados (mismo nombre normalizado).
- [ ] 100% de empresas con NAICS válido en lista objetivo.
- [ ] 100% de empresas con estrato >= 5.
- [ ] Encoding UTF-8 con BOM (`utf-8-sig`) para que Excel mexicano lea acentos correctamente.

## Anti-patrones a evitar

❌ **No inventes datos.** Si DENUE no tiene un campo, déjalo vacío. Mejor `None` honesto que estimación falsa.

❌ **No hagas scraping de sitios privados.** El workbook ya identifica empresas por nombre; el enriquecimiento web manual lo hace Jose o un asistente humano, no este pipeline.

❌ **No uses APIs de pago sin confirmación explícita.** Veritrade, Capital IQ, etc. requieren autorización por sesión. DENUE/INEGI es gratis con token.

❌ **No subas el workbook completo a logs o prints.** Es información estratégica de Quimibond.

❌ **No commitees `.env`, `data/raw/`, ni el workbook.** Ya están en `.gitignore`.

## Tareas que Claude Code puede hacer en este proyecto

Cuando Jose abra Claude Code en este folder, las tareas naturales son:

1. **Setup inicial:** crear `.env` desde template, verificar dependencias, validar token INEGI con un ping al endpoint.
2. **Correr pipeline:** ejecutar el flujo completo end-to-end y reportar conteos de cada etapa.
3. **Debugging:** si DENUE devuelve un error o estructura inesperada, ajustar `denue_client.py`.
4. **Iterar filtros:** si el universo final tiene <100 o >800, ajustar parámetros en `config.py` y volver a correr.
5. **Extender:** agregar nuevos estados, nuevos NAICS, o un nuevo paso de enriquecimiento (ej: cruzar contra socios CANAINTEX si se obtiene la lista).

## Cuando estés en duda

- **Sobre estructura de datos DENUE** → primero hacer una request de prueba con `denue_client.py` y ver el JSON real antes de codear el parser.
- **Sobre lógica de negocio** → preguntar a Jose. No asumir.
- **Sobre dependencias nuevas** → preferir librerías establecidas (pandas, openpyxl, requests). Evitar deps exóticas.

---

## Estado del proyecto al inicio

Este proyecto se entrega con **scaffolding completo y código stub funcional** pero sin haber sido ejecutado contra el API real de DENUE. La primera corrida en Claude Code debe ser:

```bash
# 1. Verificar que el token funciona
python -m src.denue_client --test

# 2. Si funciona, correr el pipeline completo
python -m src.denue_pipeline
```

Si el endpoint de DENUE cambió (las APIs gubernamentales mexicanas mutan), el primer trabajo de Claude Code será ajustar `denue_client.py` con la estructura real del response.
