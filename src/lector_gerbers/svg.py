"""Renderizado SVG de primitivas Gerber básicas."""

from html import escape

from .excellon import ExcellonFileInfo
from .parser import GerberFileInfo, GerberPrimitive


def render_svg(
    info: GerberFileInfo,
    scale: float = 10.0,
    margin: float = 5.0,
    mirror_x: bool = False,
    origin_lower_left: bool = False,
) -> str:
    """Devuelve un SVG con los trazos y flashes de una capa Gerber."""
    if mirror_x or origin_lower_left:
        return render_board(
            (info,), scale=scale, margin=margin, mirror_x=mirror_x,
            origin_lower_left=origin_lower_left
        )
    if not info.primitives:
        return _empty_svg(info.path.name)

    points = [point for primitive in info.primitives for point in _primitive_points(primitive)]
    min_x = min(point[0] for point in points)
    max_x = max(point[0] for point in points)
    min_y = min(point[1] for point in points)
    max_y = max(point[1] for point in points)
    width = max((max_x - min_x) * scale + margin * 2, margin * 2)
    height = max((max_y - min_y) * scale + margin * 2, margin * 2)

    elements = []
    for primitive in info.primitives:
        color = "#d94f4f" if primitive.polarity == "dark" else "#5eb6e4"
        if primitive.kind == "draw" and primitive.start is not None:
            start = _to_svg_point(primitive.start, min_x, max_y, scale, margin)
            end = _to_svg_point(primitive.end, min_x, max_y, scale, margin)
            elements.append(
                f'<line x1="{start[0]:.4f}" y1="{start[1]:.4f}" '
                f'x2="{end[0]:.4f}" y2="{end[1]:.4f}" '
                f'stroke="{color}" stroke-width="{_width(primitive, scale):.4f}" '
                'stroke-linecap="round" />'
            )
        elif primitive.kind == "flash":
            center = _to_svg_point(primitive.end, min_x, max_y, scale, margin)
            elements.append(_flash_svg(primitive, center, color, scale))
        elif primitive.kind == "region":
            points = " ".join(
                f"{_to_svg_point(point, min_x, max_y, scale, margin)[0]:.4f},"
                f"{_to_svg_point(point, min_x, max_y, scale, margin)[1]:.4f}"
                for point in primitive.points
            )
            elements.append(f'<polygon points="{points}" fill="{color}" fill-opacity="0.7" />')
        elif primitive.kind == "arc":
            points = " ".join(
                f"{_to_svg_point(point, min_x, max_y, scale, margin)[0]:.4f},"
                f"{_to_svg_point(point, min_x, max_y, scale, margin)[1]:.4f}"
                for point in primitive.points
            )
            elements.append(
                f'<polyline points="{points}" fill="none" stroke="{color}" '
                f'stroke-width="{_width(primitive, scale):.4f}" stroke-linecap="round" />'
            )

    title = escape(info.path.name)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.2f}" '
        f'height="{height:.2f}" viewBox="0 0 {width:.2f} {height:.2f}">'
        f'<title>{title}</title><rect width="100%" height="100%" fill="#18212b" />'
        f'{"".join(elements)}</svg>'
    )


def render_board(
    gerbers: tuple[GerberFileInfo, ...],
    drills: tuple[ExcellonFileInfo, ...] = (),
    scale: float = 10.0,
    margin: float = 5.0,
    mirror_x: bool = False,
    origin_lower_left: bool = False,
) -> str:
    """Renderiza varias capas Gerber y taladros Excellon en un SVG común."""
    gerber_points = [
        point
        for info in gerbers
        for primitive in info.primitives
        for point in _primitive_points(primitive)
    ]
    drill_points = [(hit.x, hit.y) for info in drills for hit in info.hits]
    points = gerber_points + drill_points
    if not points:
        return _empty_svg("placa")

    min_x = min(point[0] for point in points)
    max_x = max(point[0] for point in points)
    min_y = min(point[1] for point in points)
    max_y = max(point[1] for point in points)
    transformed_points = [
        _transform_point(point, min_x, max_x, min_y, mirror_x, origin_lower_left)
        for point in points
    ]
    transformed_min_x = min(point[0] for point in transformed_points)
    transformed_max_y = max(point[1] for point in transformed_points)
    width = max((max_x - min_x) * scale + margin * 2, margin * 2)
    height = max((max_y - min_y) * scale + margin * 2, margin * 2)
    elements = []

    for info in gerbers:
        for primitive in info.primitives:
            color = "#d94f4f" if primitive.polarity == "dark" else "#5eb6e4"
            if primitive.kind == "draw" and primitive.start is not None:
                start = _to_svg_point(_transform_point(primitive.start, min_x, max_x, min_y, mirror_x, origin_lower_left), transformed_min_x, transformed_max_y, scale, margin)
                end = _to_svg_point(_transform_point(primitive.end, min_x, max_x, min_y, mirror_x, origin_lower_left), transformed_min_x, transformed_max_y, scale, margin)
                elements.append(
                    f'<line x1="{start[0]:.4f}" y1="{start[1]:.4f}" '
                    f'x2="{end[0]:.4f}" y2="{end[1]:.4f}" '
                    f'stroke="{color}" stroke-width="{_width(primitive, scale):.4f}" '
                    'stroke-linecap="round" />'
                )
            elif primitive.kind == "flash":
                center = _to_svg_point(_transform_point(primitive.end, min_x, max_x, min_y, mirror_x, origin_lower_left), transformed_min_x, transformed_max_y, scale, margin)
                elements.append(_flash_svg(primitive, center, color, scale))
            elif primitive.kind == "region":
                polygon_points = " ".join(
                    f"{_to_svg_point(_transform_point(point, min_x, max_x, min_y, mirror_x, origin_lower_left), transformed_min_x, transformed_max_y, scale, margin)[0]:.4f},"
                    f"{_to_svg_point(_transform_point(point, min_x, max_x, min_y, mirror_x, origin_lower_left), transformed_min_x, transformed_max_y, scale, margin)[1]:.4f}"
                    for point in primitive.points
                )
                elements.append(
                    f'<polygon points="{polygon_points}" fill="{color}" fill-opacity="0.7" />'
                )
            elif primitive.kind == "arc":
                arc_points = " ".join(
                    f"{_to_svg_point(_transform_point(point, min_x, max_x, min_y, mirror_x, origin_lower_left), transformed_min_x, transformed_max_y, scale, margin)[0]:.4f},"
                    f"{_to_svg_point(_transform_point(point, min_x, max_x, min_y, mirror_x, origin_lower_left), transformed_min_x, transformed_max_y, scale, margin)[1]:.4f}"
                    for point in primitive.points
                )
                elements.append(
                    f'<polyline points="{arc_points}" fill="none" stroke="{color}" '
                    f'stroke-width="{_width(primitive, scale):.4f}" stroke-linecap="round" />'
                )

    for info in drills:
        for hit in info.hits:
            center = _to_svg_point(_transform_point((hit.x, hit.y), min_x, max_x, min_y, mirror_x, origin_lower_left), transformed_min_x, transformed_max_y, scale, margin)
            radius = max((hit.diameter or 0.5) * scale / 2, 1.5)
            elements.append(
                f'<circle cx="{center[0]:.4f}" cy="{center[1]:.4f}" r="{radius:.4f}" '
                'fill="#f2d06b" fill-opacity="0.8" stroke="#fff3b0" stroke-width="0.5" />'
            )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.2f}" '
        f'height="{height:.2f}" viewBox="0 0 {width:.2f} {height:.2f}">'
        '<title>Vista combinada de placa</title>'
        '<rect width="100%" height="100%" fill="#18212b" />'
        f'{"".join(elements)}</svg>'
    )


def _primitive_points(primitive: GerberPrimitive) -> tuple[tuple[float, float], ...]:
    if primitive.points:
        return primitive.points
    if primitive.start is None:
        return (primitive.end,)
    return primitive.start, primitive.end


def _width(primitive: GerberPrimitive, scale: float) -> float:
    """Convierte el ancho de la apertura a unidades del SVG."""
    return max((primitive.width or 0.15) * scale, 0.2)


def _radius(primitive: GerberPrimitive, scale: float) -> float:
    return _width(primitive, scale) / 2


def _flash_svg(primitive: GerberPrimitive, center, color: str, scale: float) -> str:
    width = max((primitive.width or 0.15) * scale, 0.2)
    height = max((primitive.height or primitive.width or 0.15) * scale, 0.2)
    x = center[0] - width / 2
    y = center[1] - height / 2
    if primitive.shape == "C":
        return f'<circle cx="{center[0]:.4f}" cy="{center[1]:.4f}" r="{width / 2:.4f}" fill="{color}" />'
    if primitive.shape == "O":
        radius = min(width, height) / 2
        return f'<rect x="{x:.4f}" y="{y:.4f}" width="{width:.4f}" height="{height:.4f}" rx="{radius:.4f}" fill="{color}" />'
    radius = min(width, height) / (4 if primitive.shape == "RoundRect" else 20)
    return f'<rect x="{x:.4f}" y="{y:.4f}" width="{width:.4f}" height="{height:.4f}" rx="{radius:.4f}" fill="{color}" />'


def _transform_point(
    point: tuple[float, float],
    min_x: float,
    max_x: float,
    min_y: float,
    mirror_x: bool,
    origin_lower_left: bool,
) -> tuple[float, float]:
    x, y = point
    if mirror_x:
        x = max_x - x
    if origin_lower_left:
        x -= min_x
        y -= min_y
    return x, y


def _to_svg_point(
    point: tuple[float, float], min_x: float, max_y: float, scale: float, margin: float
) -> tuple[float, float]:
    return margin + (point[0] - min_x) * scale, margin + (max_y - point[1]) * scale


def _empty_svg(name: str) -> str:
    title = escape(name)
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="240" height="100" '
        'viewBox="0 0 240 100"><title>'
        f'{title}</title><rect width="100%" height="100%" fill="#18212b" />'
        '<text x="120" y="55" text-anchor="middle" fill="#d7dee7" '
        'font-family="sans-serif">Sin geometría</text></svg>'
    )
