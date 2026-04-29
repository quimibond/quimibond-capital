"""
Cliente para la API DENUE de INEGI.

Documentación oficial: https://www.inegi.org.mx/servicios/api_denue.html

NOTA IMPORTANTE: La API de DENUE expone varios endpoints. El más útil para
nuestro caso es BuscarEntidad que filtra por entidad federativa, condición
de actividad y estrato. Sin embargo, el endpoint puede cambiar — siempre
verificar con --test antes de correr el pipeline completo.

Endpoints principales:
- /Buscar/{condicion}/{ae}/{registro_inicial}/{registro_final}/{token}
- /BuscarEntidad/{condicion}/{ae}/{entidad}/{registro_inicial}/{registro_final}/{token}
- /BuscarAreaActEstr/{entidad}/{municipio}/{localidad}/{ageb}/{manzana}/
   {sector_scian}/{registro_inicial}/{registro_final}/{estrato}/{token}
- /Ficha/{clee}/{token}

El que mejor sirve para filtrar por NAICS + estado + estrato es
BuscarAreaActEstr.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Iterator

import click
import requests
from dotenv import load_dotenv
import os

from src import config

load_dotenv()

logger = logging.getLogger(__name__)


@dataclass
class DenueClient:
    """Cliente HTTP para la API DENUE de INEGI."""

    token: str = field(default_factory=lambda: os.getenv("INEGI_TOKEN", ""))
    base_url: str = config.DENUE_BASE_URL
    timeout: int = config.DENUE_TIMEOUT
    max_retries: int = config.DENUE_MAX_RETRIES

    def __post_init__(self) -> None:
        if not self.token:
            raise ValueError(
                "Token INEGI no encontrado. Define INEGI_TOKEN en .env "
                "u obtén uno en https://www.inegi.org.mx/servicios/api_denue.html"
            )

    # ----------------------------------------------------------
    # Helpers HTTP
    # ----------------------------------------------------------
    def _get(self, url: str) -> list[dict] | dict | None:
        """GET con reintentos. Devuelve JSON parseado o None si falla."""
        last_err = None
        for attempt in range(1, self.max_retries + 1):
            try:
                r = requests.get(url, timeout=self.timeout)
                if r.status_code == 200:
                    # DENUE devuelve [] cuando no hay resultados (válido)
                    if r.text.strip() in ("", "[]"):
                        return []
                    return r.json()
                if r.status_code == 401:
                    raise PermissionError("Token inválido o expirado.")
                logger.warning(
                    "DENUE %s status=%d intento=%d", url, r.status_code, attempt
                )
            except requests.RequestException as e:
                last_err = e
                logger.warning("DENUE excepción %s intento=%d", e, attempt)
            time.sleep(2 ** attempt)  # backoff exponencial: 2s, 4s, 8s
        logger.error("DENUE falló después de %d intentos: %s", self.max_retries, last_err)
        return None

    # ----------------------------------------------------------
    # Endpoints
    # ----------------------------------------------------------
    def ping(self) -> bool:
        """
        Test rápido del token. Hace una búsqueda mínima.
        Devuelve True si la API responde con éxito.
        """
        # Búsqueda trivial: condición=textil, entidad=09 (CDMX), 1-1
        url = f"{self.base_url}/Buscar/textil/09/1/1/{self.token}"
        result = self._get(url)
        return result is not None

    def buscar_por_naics_estado_estrato(
        self,
        naics: str,
        entidad: str,
        estrato: str,
        registro_inicial: int = 1,
        registro_final: int = 1000,
    ) -> list[dict]:
        """
        Busca establecimientos filtrando por NAICS (sector_scian), entidad y estrato.

        Args:
            naics: código sector SCIAN/NAICS (ej. "3149")
            entidad: clave entidad federativa (ej. "15" para EdoMex)
            estrato: código de estrato (ej. "5" para 51-100 empleados)
            registro_inicial / registro_final: paginación (DENUE limita a 5000 por query)

        Returns:
            Lista de dicts con establecimientos. Vacía si no hay resultados.
        """
        # Endpoint BuscarAreaActEstr
        # Formato: /entidad/municipio/localidad/ageb/manzana/sector/inicio/fin/estrato/token
        # 0 en municipio/localidad/ageb/manzana significa "todos"
        url = (
            f"{self.base_url}/BuscarAreaActEstr/"
            f"{entidad}/0/0/0/0/{naics}/"
            f"{registro_inicial}/{registro_final}/{estrato}/{self.token}"
        )
        logger.debug("DENUE query: %s", url.replace(self.token, "***"))
        result = self._get(url)
        if result is None:
            return []
        if isinstance(result, dict):
            # Algunos endpoints envuelven en { "establecimientos": [...] }
            for key in ("establecimientos", "data", "results"):
                if key in result:
                    return result[key]
            return [result]
        return result if isinstance(result, list) else []

    def iterar_combinaciones(
        self,
        naics_list: list[str],
        entidades: list[str],
        estratos: list[str],
    ) -> Iterator[tuple[str, str, str, list[dict]]]:
        """
        Iterador: para cada combinación NAICS × entidad × estrato, devuelve resultados.

        Yields:
            Tuplas (naics, entidad, estrato, lista_establecimientos)
        """
        total = len(naics_list) * len(entidades) * len(estratos)
        contador = 0
        for naics in naics_list:
            for entidad in entidades:
                for estrato in estratos:
                    contador += 1
                    logger.info(
                        "[%d/%d] NAICS=%s entidad=%s estrato=%s",
                        contador, total, naics, entidad, estrato,
                    )
                    establecimientos = self.buscar_por_naics_estado_estrato(
                        naics=naics,
                        entidad=entidad,
                        estrato=estrato,
                    )
                    yield naics, entidad, estrato, establecimientos
                    # Cortesía con la API
                    time.sleep(0.5)


# ----------------------------------------------------------
# CLI para test rápido
# ----------------------------------------------------------
@click.command()
@click.option("--test", is_flag=True, help="Verifica que el token responde.")
@click.option("--naics", default="3149", help="NAICS para query de prueba.")
@click.option("--entidad", default="15", help="Entidad para query de prueba (15=EdoMex).")
@click.option("--estrato", default="5", help="Estrato para query de prueba.")
def main(test: bool, naics: str, entidad: str, estrato: str) -> None:
    """Test del cliente DENUE."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    client = DenueClient()

    if test:
        print("Probando token...")
        t0 = time.time()
        ok = client.ping()
        dt = time.time() - t0
        if ok:
            print(f"✓ Token válido. Endpoint responde en {dt:.1f} s.")
        else:
            print("✗ Token no responde correctamente. Revisa INEGI_TOKEN en .env.")
            raise SystemExit(1)
        return

    # Query de prueba con parámetros default
    print(f"Query de prueba: NAICS={naics}, entidad={entidad}, estrato={estrato}")
    resultados = client.buscar_por_naics_estado_estrato(naics, entidad, estrato)
    print(f"Resultados: {len(resultados)} establecimientos.")
    if resultados:
        print("\nPrimer establecimiento (campos disponibles):")
        primero = resultados[0]
        for k, v in primero.items():
            print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
