"""Calculo de contornos de aislamiento a partir de una capa Gerber."""

from dataclasses import dataclass, replace
from math import radians, tan

from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

from .parser import GerberFileInfo, GerberPrimitive


@dataclass(frozen=True)
class IsolationParameters:
    """Parametros de la fresa y del recorrido de aislamiento."""

    tip_width: float
    cone_angle: float
    cut_depth: float
    passes: int = 1
    overlap: float = 0.5
    isolation_clearance: float = 0.0
    safe_z: float = 2.0
    feed_rate: float = 100.0
    plunge_rate: float = 50.0
    spindle_speed: float = 10000.0
    reference_bounds: tuple[float, float, float, float] | None = None

    @property
    def effective_width(self) -> float:
        """Ancho de corte a la profundidad indicada."""
        return self.tip_width + 2 * self.cut_depth * tan(radians(self.cone_angle) / 2)

    @property
    def tool_radius(self) -> float:
        return self.effective_width / 2

    @property
    def pass_step(self) -> float:
        return self.effective_width * (1 - self.overlap)


def copper_geometry(info: GerberFileInfo):
    """Construye el area de cobre a partir de las primitivas conocidas."""
    shapes = []
    for primitive in info.primitives:
        if primitive.kind in {"draw", "arc"} and primitive.start is not None:
            width = primitive.width or 0.15
            points = primitive.points or (primitive.start, primitive.end)
            shapes.append(LineString(points).buffer(width / 2))
        elif primitive.kind == "flash":
            shapes.append(_flash_geometry(primitive))
        elif primitive.kind == "region" and len(primitive.points) >= 3:
            shapes.append(Polygon(primitive.points))
    if not shapes:
        return None
    geometry = unary_union(shapes)
    return geometry if geometry.is_valid else geometry.buffer(0)


def _flash_geometry(primitive: GerberPrimitive):
    """Construye la forma de un flash circular, rectangular u oblonga."""
    x, y = primitive.end
    width = primitive.width or 0.15
    height = primitive.height or width
    if primitive.shape == "R":
        return box(x - width / 2, y - height / 2, x + width / 2, y + height / 2)
    if primitive.shape == "O":
        if width >= height:
            line = LineString(((x - width / 2 + height / 2, y), (x + width / 2 - height / 2, y)))
        else:
            line = LineString(((x, y - height / 2 + width / 2), (x, y + height / 2 - width / 2)))
        return line.buffer(min(width, height) / 2)
    return Point(primitive.end).buffer(width / 2)


def isolation_paths(
    info: GerberFileInfo,
    parameters: IsolationParameters,
    mirror_x: bool = False,
    origin_lower_left: bool = False,
):
    """Devuelve anillos exteriores para cada pasada de aislamiento."""
    if parameters.passes < 1:
        raise ValueError("passes debe ser mayor o igual que 1")
    if not 0 <= parameters.overlap < 1:
        raise ValueError("overlap debe estar entre 0 y 1, sin incluir 1")
    if parameters.effective_width <= 0:
        raise ValueError("el ancho efectivo debe ser positivo")

    info = transform_info(info, mirror_x, origin_lower_left, parameters.reference_bounds)
    copper = copper_geometry(info)
    if copper is None:
        return ()

    paths = []
    for pass_number in range(parameters.passes):
        offset = (
            parameters.tool_radius
            + parameters.isolation_clearance
            + pass_number * parameters.pass_step
        )
        boundary = copper.buffer(offset).boundary
        paths.extend(_line_coordinates(boundary))
    if origin_lower_left and paths:
        if parameters.reference_bounds is None:
            min_path_x = min(point[0] for path in paths for point in path)
            min_path_y = min(point[1] for path in paths for point in path)
            paths = [
                tuple((x - min_path_x, y - min_path_y) for x, y in path)
                for path in paths
            ]
        else:
            _ensure_paths_within_reference(paths)
    return tuple(paths)


_NEGATIVE_COORDINATE_TOLERANCE = 1e-6


def _ensure_paths_within_reference(paths) -> None:
    """Verifica que ningun recorrido de aislamiento caiga fuera del origen compartido.

    Con --reference-gerber el origen se fija segun el contorno de referencia, no
    segun los propios recorridos: si el offset de la fresa empuja un recorrido mas
    alla de ese contorno, se recorta a coordenadas negativas silenciosamente en vez
    de desplazar el origen (eso rompería la alineacion compartida con el taladrado).
    """
    min_x = min(point[0] for path in paths for point in path)
    min_y = min(point[1] for path in paths for point in path)
    if min_x < -_NEGATIVE_COORDINATE_TOLERANCE or min_y < -_NEGATIVE_COORDINATE_TOLERANCE:
        raise ValueError(
            "el recorrido de aislamiento queda fuera del contorno de referencia "
            f"(coordenada minima X={min_x:.4f} Y={min_y:.4f}); agrandar el margen del "
            "Gerber de referencia (Edge_Cuts) para que incluya el offset de la fresa, "
            "o generar el aislamiento sin --reference-gerber"
        )


def transform_info(
    info: GerberFileInfo,
    mirror_x: bool = False,
    origin_lower_left: bool = False,
    reference_bounds: tuple[float, float, float, float] | None = None,
) -> GerberFileInfo:
    """Aplica las transformaciones de fabricacion a todas las primitivas."""
    if not mirror_x and not origin_lower_left:
        return info
    points = [point for primitive in info.primitives for point in _primitive_points(primitive)]
    if not points:
        return info
    if reference_bounds is None:
        min_x = min(point[0] for point in points)
        max_x = max(point[0] for point in points)
        min_y = min(point[1] for point in points)
    else:
        min_x, max_x, min_y, _ = reference_bounds

    def transform(point):
        x, y = point
        if mirror_x:
            # El espejo ya reubica el eje X en [0, max_x - min_x]; restar min_x
            # de nuevo lo correria fuera de rango cuando min_x != 0.
            x = max_x - x
        elif origin_lower_left:
            x -= min_x
        if origin_lower_left:
            y -= min_y
        return x, y

    transformed = []
    for primitive in info.primitives:
        transformed.append(
            replace(
                primitive,
                start=transform(primitive.start) if primitive.start is not None else None,
                end=transform(primitive.end),
                points=tuple(transform(point) for point in primitive.points),
            )
        )
    return replace(info, primitives=tuple(transformed))


def _primitive_points(primitive: GerberPrimitive):
    if primitive.points:
        return primitive.points
    if primitive.start is None:
        return (primitive.end,)
    return primitive.start, primitive.end


def _line_coordinates(geometry):
    if geometry.geom_type == "LineString":
        return (tuple(geometry.coords),)
    if geometry.geom_type == "MultiLineString":
        return tuple(tuple(line.coords) for line in geometry.geoms)
    if geometry.geom_type == "Polygon":
        return _line_coordinates(geometry.boundary)
    if geometry.geom_type == "MultiPolygon":
        lines = []
        for polygon in geometry.geoms:
            lines.extend(_line_coordinates(polygon.boundary))
        return tuple(lines)
    if geometry.geom_type == "GeometryCollection":
        lines = []
        for item in geometry.geoms:
            lines.extend(_line_coordinates(item))
        return tuple(lines)
    return ()
