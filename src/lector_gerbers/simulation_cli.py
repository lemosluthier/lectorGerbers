"""Interfaz de línea de comandos para simular G-code."""

import argparse
from pathlib import Path

from .simulation import simulate_gcode_files


def main() -> int:
    parser = argparse.ArgumentParser(description="Genera una vista SVG de un G-code GRBL.")
    parser.add_argument("file", type=Path, nargs="+", help="Archivos G-code de entrada")
    parser.add_argument("--svg", type=Path, required=True, help="Archivo SVG de salida")
    args = parser.parse_args()
    args.svg.write_text(simulate_gcode_files(tuple(args.file)), encoding="utf-8")
    print(f"Simulación G-code exportada: {args.svg}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())