"""Interfaz de línea de comandos para archivos Excellon."""

import argparse
from pathlib import Path

from .drilling import DrillingParameters, generate_drilling_gcode
from .excellon import inspect_drill
from .parser import inspect_file


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspecciona un archivo Excellon.")
    parser.add_argument("file", help="Ruta del archivo de taladros")
    parser.add_argument("--gcode", type=Path, help="Genera G-code GRBL de taladrado")
    parser.add_argument("--depth", type=float, help="Profundidad de perforacion en mm")
    parser.add_argument("--safe-z", type=float, default=2.0, help="Altura segura en mm")
    parser.add_argument("--plunge-rate", type=float, default=50.0, help="Avance de descenso en mm/min")
    parser.add_argument("--spindle-speed", type=float, default=10000.0, help="Velocidad del husillo en RPM")
    parser.add_argument("--mirror-x", action="store_true", help="Espeja el patron en X")
    parser.add_argument(
        "--origin-lower-left",
        action="store_true",
        help="Traslada los taladros para que el minimo sea el origen",
    )
    parser.add_argument(
        "--tool-change",
        action="store_true",
        help="Inserta una pausa M0 entre herramientas",
    )
    parser.add_argument(
        "--single-tool-diameter",
        type=float,
        help="Usa una unica broca para todos los taladros, en mm",
    )
    parser.add_argument(
        "--reference-gerber",
        type=Path,
        help="Gerber de referencia para compartir limites de espejo y origen",
    )
    args = parser.parse_args()

    info = inspect_drill(args.file)
    print(f"Archivo: {info.path}")
    print(f"Unidades: {info.units or 'no detectadas'}")
    print(f"Herramientas: {len(info.tools)}")
    print(f"Taladros: {len(info.hits)}")
    if args.gcode:
        if args.depth is None:
            parser.error("--gcode requiere --depth")
        parameters = DrillingParameters(
            depth=args.depth,
            safe_z=args.safe_z,
            plunge_rate=args.plunge_rate,
            spindle_speed=args.spindle_speed,
            mirror_x=args.mirror_x,
            origin_lower_left=args.origin_lower_left,
            tool_change_pause=args.tool_change,
            reference_bounds=_reference_bounds(args.reference_gerber),
            single_tool_diameter=args.single_tool_diameter,
        )
        args.gcode.write_text(generate_drilling_gcode(info, parameters), encoding="ascii")
        print(f"G-code de taladrado exportado: {args.gcode}")
    return 0


def _reference_bounds(path: Path | None):
    if path is None:
        return None
    reference = inspect_file(path)
    points = [point for primitive in reference.primitives for point in _primitive_points(primitive)]
    if not points:
        raise ValueError("el Gerber de referencia no contiene geometria")
    return min(x for x, _ in points), max(x for x, _ in points), min(y for _, y in points), max(y for _, y in points)


def _primitive_points(primitive):
    if primitive.points:
        return primitive.points
    if primitive.start is None:
        return (primitive.end,)
    return primitive.start, primitive.end


if __name__ == "__main__":
    raise SystemExit(main())