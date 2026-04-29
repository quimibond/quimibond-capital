"""
Configuración central del pipeline.
Constantes de negocio: NAICS, estados, mappings.
"""

from pathlib import Path

# ============================================================
# RUTAS
# ============================================================
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
CLEAN_DIR = DATA_DIR / "clean"
OUTPUT_DIR = ROOT / "output"

for d in [DATA_DIR, RAW_DIR, CLEAN_DIR, OUTPUT_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ============================================================
# DENUE — API INEGI
# ============================================================
DENUE_BASE_URL = "https://www.inegi.org.mx/app/api/denue/v1/consulta"
DENUE_TIMEOUT = 30  # segundos
DENUE_MAX_RETRIES = 3
ENCODING = "utf-8-sig"  # con BOM para Excel mexicano

# ============================================================
# NAICS OBJETIVO
# ============================================================
# Códigos de subsector y rama relevantes para tesis Quimibond
NAICS_PRIORIDAD_CRITICA = {
    "3149": "Otros productos textiles excepto prendas (incluye no tejidos)",
    "3133": "Acabado de productos textiles y telas recubiertas",
    "3169": "Otros productos de cuero, piel y materiales sucedáneos",
}

NAICS_PRIORIDAD_ALTA = {
    "3132": "Fabricación de telas",
    "3141": "Confección de alfombras, blancos y similares",
}

NAICS_PRIORIDAD_MEDIA = {
    "3131": "Preparación e hilado de fibras textiles",
}

NAICS_OBJETIVO = {
    **NAICS_PRIORIDAD_CRITICA,
    **NAICS_PRIORIDAD_ALTA,
    **NAICS_PRIORIDAD_MEDIA,
}

# Mapping NAICS → Subsector (categoría de negocio para el workbook)
NAICS_A_SUBSECTOR = {
    "3149": "No tejidos",
    "3133": "Acabados / Recubrimientos",
    "3169": "Recubrimientos / Simil cuero",
    "3132": "Telas",
    "3141": "Hogar / Alfombras",
    "3131": "Hilados",
}

# ============================================================
# ESTADOS — CVE_ENT INEGI
# ============================================================
ESTADOS_PRIORITARIOS = {
    "09": "CDMX",
    "13": "Hidalgo",
    "15": "México",       # EdoMex — donde está Quimibond
    "21": "Puebla",
    "29": "Tlaxcala",
}

ESTADOS_SECUNDARIOS = {
    "05": "Coahuila",
    "11": "Guanajuato",
    "14": "Jalisco",
    "19": "Nuevo León",
    "22": "Querétaro",
}

ESTADOS_OBJETIVO = {**ESTADOS_PRIORITARIOS, **ESTADOS_SECUNDARIOS}

# ============================================================
# ESTRATOS DENUE (personal ocupado)
# ============================================================
# Códigos del campo `estrato` en DENUE
ESTRATOS = {
    "1": (0, 5),
    "2": (6, 10),
    "3": (11, 30),
    "4": (31, 50),
    "5": (51, 100),
    "6": (101, 250),
    "7": (251, None),
}

# Filtro mínimo: estrato 5 (51+ empleados)
ESTRATOS_OBJETIVO = ["5", "6", "7"]

# Mapping estrato → categoría tamaño y empleados estimados (punto medio)
ESTRATO_A_TAMAÑO = {
    "5": ("Mediana", 75),
    "6": ("Mediana-Grande", 175),
    "7": ("Grande", 500),
}

# ============================================================
# COLUMNAS DEL CSV FINAL
# ============================================================
# Orden EXACTO esperado por la hoja "2. Universo" del workbook
COLUMNAS_FINAL = [
    "ID",
    "Empresa",
    "Subsector",
    "Producto principal",
    "Ubicación",
    "Tamaño Est.",
    "Empleados Est.",
    "Ingresos Est. (MXN mm)",
    "Cliente Auto?",
    "Exporta?",
    "Estructura",
    "Fuente",
    "Notas",
    "Status",
    # Adicionales DENUE
    "RFC",
    "Teléfono",
    "Email",
    "Web",
    "Latitud",
    "Longitud",
    "Fecha alta",
    "NAICS",
    # Adicionales Veritrade (vacíos hasta tener acceso)
    "Vol Exp 24m kg",
    "Valor Exp 24m USD",
    "Top cliente",
    "Concentración top1",
    "Crecimiento 24m",
    "Precio USD/kg",
    "# países destino",
]

# ============================================================
# DEDUPLICACIÓN
# ============================================================
FUZZY_MATCH_THRESHOLD = 90  # % similitud para considerar duplicado

# ============================================================
# VALIDACIÓN
# ============================================================
MIN_TARGETS_ESPERADOS = 100
MAX_TARGETS_ESPERADOS = 800
