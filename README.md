# Quimibond M&A Pipeline — Textil México

Pipeline de inteligencia de targets para la tesis de consolidación industrial de Quimibond en el sector textil mexicano.

## Qué hace

1. Descarga el universo de empresas textiles formales de México vía DENUE (INEGI, gratis).
2. Filtra por NAICS, estado y tamaño relevantes para la tesis.
3. Limpia y deduplica.
4. Genera CSV listo para mergearse con la hoja "2. Universo" del workbook `Pipeline_MA_Textil_Mexico_Quimibond.xlsx`.

## Setup (5 minutos)

### 1. Obtén tu token INEGI

Ve a https://www.inegi.org.mx/servicios/api_denue.html y solicita un token gratuito (lo recibes por correo en minutos).

### 2. Clona y configura

```bash
cd quimibond_pipeline
python -m venv .venv
source .venv/bin/activate  # Mac/Linux
# o: .venv\Scripts\activate  # Windows

pip install -r requirements.txt

cp .env.example .env
# Edita .env y pega tu INEGI_TOKEN
```

### 3. Verifica que el token funcione

```bash
python -m src.denue_client --test
```

Output esperado: `✓ Token válido. Endpoint responde en X.X s.`

### 4. Corre el pipeline completo

```bash
python -m src.denue_pipeline
```

Tarda ~5-15 min dependiendo de cuántos estados/NAICS escanees. Output en `output/targets_consolidado.csv`.

### 5. Mergea con tu workbook

Coloca tu workbook actual en `data/Pipeline_MA_Textil_Mexico_Quimibond.xlsx` y corre:

```bash
python -m src.workbook_writer
```

Genera `output/Pipeline_MA_Textil_Mexico_Quimibond_v2.xlsx` con las nuevas filas agregadas a la hoja "2. Universo".

## Estructura

Ver `CLAUDE.md` para la guía completa.

## Comandos útiles

```bash
# Solo descargar (sin limpiar)
python -m src.denue_pipeline --raw-only

# Solo un estado
python -m src.denue_pipeline --estados 15  # Solo EdoMex

# Solo un NAICS
python -m src.denue_pipeline --naics 3149  # Solo no tejidos

# Modo verbose
python -m src.denue_pipeline -v
```

## Troubleshooting

**"Token inválido" o 401:** Tu token expiró o fue mal copiado. Genera uno nuevo en INEGI.

**Timeout:** DENUE puede ser lento. Sube el timeout en `config.py` (default: 30s).

**CSV no abre bien en Excel:** El encoding default es `utf-8-sig` precisamente para Excel mexicano. Si lo abres con Numbers/LibreOffice y se ven mal los acentos, cambia `ENCODING` en `config.py`.

## Soporte

Este pipeline se mantiene con Claude Code. Si algo se rompe, abre el folder en Claude Code y describe el error — la guía en `CLAUDE.md` orienta a Claude para hacer el debug.
