"""Simulacion SVG de movimientos G-code GRBL."""

from html import escape
from pathlib import Path
import re


_MOVE_RE = re.compile(r"^G([01])\s*(.*)$")
_AXIS_RE = re.compile(r"([XYZ])(-?[0-9]+(?:\.[0-9]+)?)")


def simulate_gcode(path: str | Path) -> str:
    """Convierte los movimientos G0/G1 de un archivo GRBL en una vista SVG."""
    file_path = Path(path)
    rapid, cutting, drilling = _collect_moves(file_path)
    return _render_segments(file_path.name, rapid, cutting, drilling)


def simulate_gcode_files(paths: tuple[str | Path, ...]) -> str:
    """Superpone varios archivos G-code en una unica vista SVG."""
    rapid = []
    cutting = []
    drilling = []
    names = []
    for path in paths:
        file_path = Path(path)
        file_rapid, file_cutting, file_drilling = _collect_moves(file_path)
        rapid.extend(file_rapid)
        cutting.extend(file_cutting)
        drilling.extend(file_drilling)
        names.append(file_path.name)
    return _render_segments(" + ".join(names), rapid, cutting, drilling)


def _collect_moves(file_path: Path):
    current = (0.0, 0.0, 0.0)
    rapid: list[tuple[tuple[float, float], tuple[float, float]]] = []
    cutting: list[tuple[tuple[float, float], tuple[float, float]]] = []
    drilling: list[tuple[float, float]] = []
    is_drilling = False

    for raw_line in file_path.read_text(encoding="ascii", errors="replace").splitlines():
        if raw_line.strip().lower().startswith("; excellon drilling"):
            is_drilling = True
        line = raw_line.split(";", 1)[0].strip().upper()
        match = _MOVE_RE.match(line)
        if not match:
            continue
        axes = dict(_AXIS_RE.findall(match.group(2)))
        target = (
            float(axes.get("X", current[0])),
            float(axes.get("Y", current[1])),
            float(axes.get("Z", current[2])),
        )
        start_xy = current[:2]
        end_xy = target[:2]
        if start_xy != end_xy:
            segment = (start_xy, end_xy)
            if match.group(1) == "0":
                rapid.append(segment)
            elif target[2] < 0:
                cutting.append(segment)
        elif is_drilling and match.group(1) == "1" and target[2] < 0:
            drilling.append(start_xy)
        current = target

    return rapid, cutting, drilling


def _render_segments(name, rapid, cutting, drilling=()) -> str:
    segments = rapid + cutting
    if not segments and not drilling:
        return f'<svg xmlns="http://www.w3.org/2000/svg" width="240" height="100"><title>{escape(name)}</title></svg>'
    points = [point for segment in segments for point in segment] + list(drilling)
    min_x = min(point[0] for point in points)
    max_x = max(point[0] for point in points)
    min_y = min(point[1] for point in points)
    max_y = max(point[1] for point in points)
    scale = 10.0
    margin = 10.0
    width = max((max_x - min_x) * scale + 2 * margin, 2 * margin)
    height = max((max_y - min_y) * scale + 2 * margin, 2 * margin)

    def svg_point(point):
        return margin + (point[0] - min_x) * scale, margin + (max_y - point[1]) * scale

    elements = []
    for segments_to_render, color, stroke_width in (
        (rapid, "#6c7a89", 0.5), (cutting, "#e85d4a", 1.2)
    ):
        for start, end in segments_to_render:
            start_svg = svg_point(start)
            end_svg = svg_point(end)
            elements.append(
                f'<line x1="{start_svg[0]:.4f}" y1="{start_svg[1]:.4f}" '
                f'x2="{end_svg[0]:.4f}" y2="{end_svg[1]:.4f}" '
                f'stroke="{color}" stroke-width="{stroke_width}" />'
            )
    for x, y in drilling:
        drill_svg = svg_point((x, y))
        elements.append(
            f'<circle cx="{drill_svg[0]:.4f}" cy="{drill_svg[1]:.4f}" '
            'r="2.0000" fill="#f2d06b" stroke="#fff3b0" stroke-width="0.5" />'
        )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.2f}" height="{height:.2f}" '
        f'viewBox="0 0 {width:.2f} {height:.2f}"><title>Simulacion: {escape(name)}</title>'
        '<rect width="100%" height="100%" fill="#18212b" />'
        f'{"".join(elements)}</svg>'
    )
