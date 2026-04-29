# Workflow end-to-end

```
┌─────────────────────────────────────────────────────────────┐
│ 0. SETUP                                                     │
│    - Token INEGI obtenido y guardado en .env                 │
│    - Workbook Pipeline_MA_Textil_Mexico_Quimibond.xlsx       │
│      colocado en data/                                       │
│    - pip install -r requirements.txt                         │
└──────────────────────┬───────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ 1. python -m src.denue_client --test                         │
│    Verifica que el token responda. Tarda 2-5s.               │
└──────────────────────┬───────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. python -m src.denue_pipeline                              │
│    Itera NAICS × estados × estratos.                         │
│    Output:                                                    │
│      - data/raw/{timestamp}/*.json (1 por combinación)       │
│      - data/raw/denue_raw_{timestamp}.csv (consolidado)      │
│    Tarda 5-15 min.                                           │
└──────────────────────┬───────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. python -m src.cleaning                                    │
│    - Normaliza nombres                                        │
│    - Filtra comercializadoras                                 │
│    - Mapea NAICS → Subsector y estrato → Tamaño              │
│    - Deduplica fuzzy                                          │
│    Output: data/clean/denue_clean.csv                        │
└──────────────────────┬───────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. python -m src.enrichment                                  │
│    - Lee universo actual del workbook (hoja "2. Universo")   │
│    - Filtra solo empresas NUEVAS (fuzzy match)               │
│    Output: output/targets_consolidado.csv                    │
└──────────────────────┬───────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. python -m src.workbook_writer                             │
│    - Copia el workbook                                        │
│    - Inserta nuevas filas preservando formato                │
│    Output: output/Pipeline_MA_Textil_Mexico_Quimibond_v2.xlsx│
└──────────────────────┬───────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ 6. ABRIR EN EXCEL                                             │
│    - Validar visualmente                                      │
│    - Ir a hoja "4. Scoring" y agregar filas con scores       │
│    - (Opcional) enriquecer con Veritrade en columnas 23-29   │
└─────────────────────────────────────────────────────────────┘
```

## Comandos útiles

```bash
# Solo descargar EdoMex + Puebla, NAICS críticos
python -m src.denue_pipeline \
  --estados 15 --estados 21 \
  --naics 3149 --naics 3133 --naics 3169

# Re-correr limpieza sobre un raw específico
python -m src.cleaning --input data/raw/denue_raw_20260429_120000.csv

# Workbook custom
python -m src.workbook_writer \
  --workbook data/mi_workbook.xlsx \
  --output output/mi_workbook_v2.xlsx
```

## Recuperación si algo falla

| Error | Solución |
|-------|----------|
| Token inválido (401) | Genera nuevo token en INEGI, actualiza .env |
| Timeout en DENUE | Sube `DENUE_TIMEOUT` en config.py o reintenta |
| 0 resultados en query | Verifica NAICS y estado contra catálogo SCIAN actual |
| Validación falla por <100 targets | Filtros muy estrechos: amplía estados/NAICS |
| Workbook se corrompe al escribir | Cierra el archivo en Excel antes de correr el writer |
| KeyError en cleaning | DENUE cambió nombres de campo: ajusta `transformar()` en cleaning.py |
