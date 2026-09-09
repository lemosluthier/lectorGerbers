"""Interfaz de línea de comandos para el lector Gerbers."""

import argparse
from pathlib import Path

from .excellon import inspect_drill
from .gcode import generate_isolation_gcode
from .isolation import IsolationParameters
from .parser import inspect_file
from .svg import render_board, render_svg


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspecciona un archivo Gerber RS-274X.")
    parser.add_argument("file", help="Ruta del archivo Gerber")
    parser.add_argument("--svg", type=Path, help="Exporta la geometría a un archivo SVG")
    parser.add_argument("--gcode", type=Path, help="Genera G-code GRBL de aislamiento")
    parser.add_argument("--tip-width", type=float, help="Ancho de punta de la fresa, en mm")
    parser.add_argument("--cone-angle", type=float, help="Angulo total del cono, en grados")
    parser.add_argument("--cut-depth", type=float, help="Profundidad de corte, en mm")
    parser.add_argument("--passes", type=int, default=1, help="Cantidad de pasadas")
    parser.add_argument("--overlap", type=float, default=0.5, help="Solapamiento entre pasadas")
    parser.add_argument("--clearance", type=float, default=0.0, help="Separacion adicional del cobre")
    parser.add_argument("--safe-z", type=float, default=2.0, help="Altura segura en mm")
    parser.add_argument("--feed-rate", type=float, default=100.0, help="Avance XY en mm/min")
    parser.add_argument("--plunge-rate", type=float, default=50.0, help="Avance vertical en mm/min")
    parser.add_argument("--spindle-speed", type=float, default=10000.0, help="Velocidad del husillo en RPM")
    parser.add_argument(
        "--drill",
        action="append",
        type=Path,
        help="Agrega un archivo Excellon a la exportación SVG; puede repetirse",
    )
    parser.add_argument(
        "--mirror-x",
        action="store_true",
        help="Espeja el diseño en X, recomendado para capas Bottom",
    )
    parser.add_argument(
        "--origin-lower-left",
        action="store_true",
        help="Traslada el conjunto para colocar el origen en la esquina inferior izquierda",
    )
    parser.add_argument(
        "--reference-gerber",
        type=Path,
        help="Gerber de referencia para compartir limites de espejo y origen",
    )
    args = parser.parse_args()


    info = inspect_file(args.file)
    print(f"Archivo: {info.path}")
    print(f"Unidades: {info.units or 'no detectadas'}")
    print(f"Formato: {info.coordinate_format or 'no detectado'}")
    print(f"Aperturas: {', '.join(info.apertures) or 'ninguna'}")
    print(f"Comandos: {info.command_count}")
    print(f"Elementos geométricos: {len(info.primitives)}")
    reference_bounds = _reference_bounds(args.reference_gerber)
    if args.svg:
        if args.drill:
            drill_infos = tuple(inspect_drill(path) for path in args.drill)
            args.svg.write_text(
                render_board(
                    (info,), drill_infos,
                    mirror_x=args.mirror_x,
                    origin_lower_left=args.origin_lower_left,
                    reference_bounds=reference_bounds,
                ),
                encoding="utf-8",
            )
        else:
            args.svg.write_text(
                render_svg(
                    info,
                    mirror_x=args.mirror_x,
                    origin_lower_left=args.origin_lower_left,
                    reference_bounds=reference_bounds,
                ),
                encoding="utf-8",
            )
        print(f"SVG exportado: {args.svg}")
    if args.gcode:
        required = (args.tip_width, args.cone_angle, args.cut_depth)
        if any(value is None for value in required):
            parser.error("--gcode requiere --tip-width, --cone-angle y --cut-depth")
        parameters = IsolationParameters(
            tip_width=args.tip_width,
            cone_angle=args.cone_angle,
            cut_depth=args.cut_depth,
            passes=args.passes,
            overlap=args.overlap,
            isolation_clearance=args.clearance,
            safe_z=args.safe_z,
            feed_rate=args.feed_rate,
            plunge_rate=args.plunge_rate,
            spindle_speed=args.spindle_speed,
            reference_bounds=reference_bounds,
        )
        args.gcode.write_text(
            generate_isolation_gcode(
                info, parameters, args.mirror_x, args.origin_lower_left
            ),
            encoding="ascii",
        )
        print(f"G-code exportado: {args.gcode}")
    return 0


def _reference_bounds(path: Path | None):
    if path is None:
        return None
    reference = inspect_file(path)
    points = [point for primitive in reference.primitives for point in _primitive_points(primitive)]
    if not points:
        parser_error = "el Gerber de referencia no contiene geometria"
        raise ValueError(parser_error)
    return min(x for x, _ in points), max(x for x, _ in points), min(y for _, y in points), max(y for _, y in points)


def _primitive_points(primitive):
    if primitive.points:
        return primitive.points
    if primitive.start is None:
        return (primitive.end,)
    return primitive.start, primitive.end


if __name__ == "__main__":
    raise SystemExit(main())
