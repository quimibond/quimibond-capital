"""
Recalc helper: invoca LibreOffice en modo headless para forzar recálculo de
fórmulas en un xlsx generado por openpyxl y guardar valores cacheados.

Útil porque openpyxl escribe fórmulas pero NO calcula sus resultados.
Cuando alguien abre el .xlsx en una máquina sin Excel/LO, las celdas con
fórmula se ven como `=B5*C5` en vez del valor.

Uso:
    python scripts/recalc.py path/al/Quimibond.xlsx

Devuelve exit 0 si el recálculo fue exitoso, 1 si LibreOffice no está
instalado o falló la conversión.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


def find_libreoffice() -> str | None:
    """Busca el binario de LibreOffice en el PATH."""
    for candidate in ("soffice", "libreoffice"):
        path = shutil.which(candidate)
        if path:
            return path
    # Mac default install
    mac_path = "/Applications/LibreOffice.app/Contents/MacOS/soffice"
    if Path(mac_path).is_file():
        return mac_path
    return None


def recalc(xlsx_path: Path) -> bool:
    """
    Recalcula el xlsx in-place vía LibreOffice headless.

    Returns:
        True si el recálculo se completó, False si LO no está o el
        comando falló.
    """
    if not xlsx_path.is_file():
        print(f"ERROR: archivo no encontrado: {xlsx_path}", file=sys.stderr)
        return False

    soffice = find_libreoffice()
    if soffice is None:
        print(
            "ERROR: LibreOffice no encontrado. Instala con:\n"
            "  macOS:   brew install --cask libreoffice\n"
            "  Linux:   apt install libreoffice / yum install libreoffice\n"
            "  Windows: https://www.libreoffice.org/download/",
            file=sys.stderr,
        )
        return False

    out_dir = xlsx_path.parent
    cmd = [
        soffice,
        "--headless",
        "--calc",
        "--convert-to", "xlsx",
        "--outdir", str(out_dir),
        str(xlsx_path),
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    except subprocess.TimeoutExpired:
        print("ERROR: LibreOffice tardó más de 120s. Aborto.", file=sys.stderr)
        return False

    if result.returncode != 0:
        print(f"ERROR LibreOffice: rc={result.returncode}", file=sys.stderr)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        return False

    print(f"✓ Recalculado: {xlsx_path}")
    return True


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        return 1
    xlsx = Path(sys.argv[1]).resolve()
    return 0 if recalc(xlsx) else 1


if __name__ == "__main__":
    sys.exit(main())
