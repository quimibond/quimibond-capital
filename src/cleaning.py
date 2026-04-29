"""
Limpieza y normalización de datos crudos de DENUE.

Tareas:
- Normalizar nombres (strip, title case)
- Construir Ubicación a partir de campos sueltos
- Mapear NAICS → Subsector
- Mapear estrato → Tamaño + Empleados estimados
- Deduplicar por razón social fuzzy
- Eliminar comercializadoras puras
- Producir CSV con columnas esperadas por el workbook
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

import click
import pandas as pd
from rapidfuzz import fuzz

from src import config

logger = logging.getLogger(__name__)


# ============================================================
# NORMALIZACIÓN
# ============================================================

def normalizar_texto(texto: str | None) -> str:
    """Strip + collapse whitespace + title case sensato."""
    if texto is None or pd.isna(texto):
        return ""
    s = re.sub(r"\s+", " ", str(texto).strip())
    # Title case excepto siglas comunes
    palabras = []
    siglas = {"S.A.", "S.A", "SA", "DE", "C.V.", "CV", "S.A.B.", "S DE RL", "S.R.L."}
    for w in s.split():
        if w.upper() in siglas or w.isupper() and len(w) <= 4:
            palabras.append(w.upper())
        else:
            palabras.append(w.title())
    return " ".join(palabras)


def construir_ubicacion(row: pd.Series) -> str:
    """Construye 'Municipio, Entidad' a partir de campos DENUE.

    El endpoint actual devuelve un único campo `Ubicacion` con formato
    "LOCALIDAD, Municipio, ESTADO" (con espacios sobrantes). Lo parseamos
    si está disponible; si no, caemos a campos sueltos heredados.
    """
    ubic = row.get("Ubicacion") or row.get("ubicacion")
    if ubic and isinstance(ubic, str):
        partes = [p.strip() for p in ubic.split(",") if p.strip()]
        if len(partes) >= 2:
            municipio = normalizar_texto(partes[-2])
            entidad = normalizar_texto(partes[-1])
            return f"{municipio}, {entidad}" if municipio and entidad else (municipio or entidad)
        if len(partes) == 1:
            return normalizar_texto(partes[0])

    municipio = normalizar_texto(row.get("municipio") or row.get("nom_mun"))
    entidad = normalizar_texto(row.get("entidad") or row.get("nom_ent"))
    if municipio and entidad:
        return f"{municipio}, {entidad}"
    return municipio or entidad or ""


def mapear_subsector(naics_query: str, clase_actividad: str = "") -> str:
    """Devuelve la categoría de subsector según NAICS, con override por descripción."""
    naics_3 = naics_query[:3] if naics_query else ""
    naics_4 = naics_query[:4] if naics_query else ""

    # Override: si la descripción menciona algo específico, prevalece
    desc = (clase_actividad or "").lower()
    if "no tejido" in desc or "nonwoven" in desc or "no-tejido" in desc:
        return "No tejidos"
    if "alfombra" in desc or "tapete" in desc:
        return "Hogar / Alfombras"
    if "tapicer" in desc:
        return "Tapicería"

    return config.NAICS_A_SUBSECTOR.get(naics_4, "Textil — otro")


def mapear_tamaño(estrato: str) -> tuple[str, int | None]:
    """Devuelve (categoría_tamaño, empleados_estimados) según estrato."""
    return config.ESTRATO_A_TAMAÑO.get(str(estrato), ("Sin datos", None))


# ============================================================
# FILTROS DE EXCLUSIÓN
# ============================================================

PATRONES_EXCLUSION = [
    r"comercio al por mayor",
    r"comercio al por menor",
    r"venta al por mayor",
    r"distribuc",  # distribuidoras
    r"^tienda",
    r"importac",
]

def es_comercializadora(clase_actividad: str) -> bool:
    """True si la clase de actividad es de comercio puro, no fabricación."""
    if not clase_actividad:
        return False
    desc = clase_actividad.lower()
    return any(re.search(p, desc) for p in PATRONES_EXCLUSION)


# ============================================================
# DEDUPLICACIÓN
# ============================================================

def clave_dedup(nombre: str) -> str:
    """Clave normalizada para agrupar duplicados."""
    s = (nombre or "").upper()
    s = re.sub(r"[^\w\s]", "", s)  # quitar puntuación
    s = re.sub(r"\b(SA DE CV|SAB DE CV|S DE RL|SRL|SA|CV)\b", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def deduplicar(df: pd.DataFrame) -> pd.DataFrame:
    """
    Deduplica por nombre/razón social. Si fuzzy match >= threshold, se considera la misma.
    Quédate con el establecimiento de mayor estrato.
    """
    if df.empty:
        return df

    df = df.copy()
    df["_clave"] = df["Empresa"].apply(clave_dedup)

    # Pase 1: agrupación exacta por clave
    df = df.sort_values("Empleados Est.", ascending=False, na_position="last")

    # Pase 2: fuzzy entre claves
    claves_unicas = df["_clave"].unique().tolist()
    canonico: dict[str, str] = {}
    for c in claves_unicas:
        if c in canonico:
            continue
        canonico[c] = c
        for otra in claves_unicas:
            if otra == c or otra in canonico:
                continue
            if fuzz.ratio(c, otra) >= config.FUZZY_MATCH_THRESHOLD:
                canonico[otra] = c

    df["_canonico"] = df["_clave"].map(canonico)

    # Por cada grupo canónico, quédate con el de mayor estrato
    deduped = df.drop_duplicates(subset="_canonico", keep="first").copy()
    deduped = deduped.drop(columns=["_clave", "_canonico"])

    logger.info(
        "Deduplicación: %d → %d registros (%d eliminados)",
        len(df), len(deduped), len(df) - len(deduped),
    )
    return deduped


# ============================================================
# TRANSFORMACIÓN PRINCIPAL
# ============================================================

def transformar(df_raw: pd.DataFrame) -> pd.DataFrame:
    """
    Transforma DataFrame raw de DENUE al esquema del workbook.
    """
    if df_raw.empty:
        return pd.DataFrame(columns=config.COLUMNAS_FINAL)

    rows = []
    for _, r in df_raw.iterrows():
        # DENUE puede usar distintos nombres de campo según endpoint;
        # cubrimos los más comunes con .get fallbacks.
        nombre = (
            r.get("nombre")
            or r.get("nom_estab")
            or r.get("Nombre")
            or ""
        )
        razon_social = r.get("razon_social") or r.get("Razon_social") or ""
        clase_actividad = (
            r.get("clase_actividad")
            or r.get("nombre_act")
            or r.get("Clase_actividad")
            or ""
        )
        if es_comercializadora(clase_actividad):
            continue

        nombre_norm = normalizar_texto(nombre)
        razon_norm = normalizar_texto(razon_social)
        empresa = razon_norm if razon_norm else nombre_norm
        if not empresa:
            continue

        notas = ""
        if razon_norm and nombre_norm and razon_norm != nombre_norm:
            notas = f"Nombre comercial: {nombre_norm}"

        naics_query = str(r.get("_naics_query", ""))
        estrato_query = str(r.get("_estrato_query", ""))
        tamaño_cat, empleados_est = mapear_tamaño(estrato_query)

        rows.append({
            "ID": None,  # se asigna al final
            "Empresa": empresa,
            "Subsector": mapear_subsector(naics_query, clase_actividad),
            "Producto principal": clase_actividad or "",
            "Ubicación": construir_ubicacion(r),
            "Tamaño Est.": tamaño_cat,
            "Empleados Est.": empleados_est,
            "Ingresos Est. (MXN mm)": None,  # no disponible en DENUE
            "Cliente Auto?": "?",
            "Exporta?": "?",
            "Estructura": "?",
            "Fuente": f"DENUE {pd.Timestamp.now().strftime('%Y-%m')}",
            "Notas": notas,
            "Status": "Investigar",
            "RFC": r.get("rfc") or r.get("RFC") or "",
            "Teléfono": r.get("telefono") or r.get("Telefono") or "",
            "Email": (
                r.get("correo_e")
                or r.get("Correo_e")
                or r.get("correo_electronico")
                or ""
            ),
            "Web": r.get("sitio_internet") or r.get("Sitio_internet") or r.get("www") or "",
            "Latitud": r.get("latitud") or r.get("Latitud") or "",
            "Longitud": r.get("longitud") or r.get("Longitud") or "",
            "Fecha alta": r.get("fecha_alta") or r.get("Fecha_Alta") or "",
            "NAICS": naics_query,
            # Veritrade (vacíos)
            "Vol Exp 24m kg": None,
            "Valor Exp 24m USD": None,
            "Top cliente": "",
            "Concentración top1": None,
            "Crecimiento 24m": None,
            "Precio USD/kg": None,
            "# países destino": None,
        })

    df = pd.DataFrame(rows, columns=config.COLUMNAS_FINAL)
    df = deduplicar(df)

    # Asignar IDs incrementales
    df = df.reset_index(drop=True)
    df["ID"] = df.index + 1

    return df


# ============================================================
# VALIDACIÓN
# ============================================================

def validar(df: pd.DataFrame) -> list[str]:
    """Devuelve lista de issues. Vacía si todo bien."""
    issues = []
    n = len(df)

    if n < config.MIN_TARGETS_ESPERADOS:
        issues.append(
            f"Solo {n} targets — esperaba al menos {config.MIN_TARGETS_ESPERADOS}. "
            f"Filtros pueden estar muy estrechos."
        )
    if n > config.MAX_TARGETS_ESPERADOS:
        issues.append(
            f"{n} targets — esperaba máx {config.MAX_TARGETS_ESPERADOS}. "
            f"Filtros pueden estar muy laxos."
        )

    if df["Empresa"].duplicated().any():
        issues.append(f"{df['Empresa'].duplicated().sum()} duplicados de Empresa.")

    naics_invalidos = df[~df["NAICS"].astype(str).isin(config.NAICS_OBJETIVO.keys())]
    if not naics_invalidos.empty:
        issues.append(f"{len(naics_invalidos)} registros con NAICS fuera de objetivo.")

    return issues


# ============================================================
# CLI
# ============================================================

@click.command()
@click.option(
    "--input",
    "input_path",
    type=click.Path(exists=True, path_type=Path),
    help="CSV raw a procesar (default: el más reciente en data/raw/).",
)
@click.option(
    "--output",
    "output_path",
    type=click.Path(path_type=Path),
    default=None,
    help="CSV de salida (default: data/clean/denue_clean.csv).",
)
@click.option("-v", "--verbose", is_flag=True)
def main(input_path: Path | None, output_path: Path | None, verbose: bool) -> None:
    """Limpia el CSV raw de DENUE y produce el archivo intermedio."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(message)s")

    if input_path is None:
        candidatos = sorted(config.RAW_DIR.glob("denue_raw_*.csv"))
        if not candidatos:
            raise click.ClickException(
                "No hay CSVs en data/raw/. Corre 'python -m src.denue_pipeline' primero."
            )
        input_path = candidatos[-1]
        logger.info("Usando input más reciente: %s", input_path)

    if output_path is None:
        output_path = config.CLEAN_DIR / "denue_clean.csv"

    logger.info("Leyendo %s ...", input_path)
    df_raw = pd.read_csv(input_path, encoding=config.ENCODING)
    logger.info("Raw: %d registros", len(df_raw))

    df = transformar(df_raw)
    logger.info("Transformado: %d registros", len(df))

    issues = validar(df)
    if issues:
        logger.warning("Issues de validación:")
        for i in issues:
            logger.warning("  - %s", i)
    else:
        logger.info("✓ Validación OK")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False, encoding=config.ENCODING)
    logger.info("Output: %s", output_path)


if __name__ == "__main__":
    main()
