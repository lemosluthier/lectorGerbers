"""Generacion de G-code GRBL para taladrado Excellon."""

from dataclasses import dataclass

from .excellon import DrillHit, ExcellonFileInfo


@dataclass(frozen=True)
class DrillingParameters:
    """Parametros del ciclo de taladrado."""

    depth: float
    safe_z: float = 2.0
    plunge_rate: float = 50.0
    spindle_speed: float = 10000.0
    mirror_x: bool = False
    origin_lower_left: bool = False
    tool_change_pause: bool = False
    reference_bounds: tuple[float, float, float, float] | None = None
    single_tool_diameter: float | None = None


def generate_drilling_gcode(
    info: ExcellonFileInfo, parameters: DrillingParameters
) -> str:
    """Genera un ciclo de taladrado GRBL a partir de un archivo Excellon."""
    _validate_parameters(parameters)
    hits = _transform_hits(info.hits, parameters)
    scale = 25.4 if info.units == "in" else 1.0
    lines = [
        "; Excellon drilling for GRBL",
        f"; file: {info.path.name}",
        f"; depth: {parameters.depth:.4f} mm",
        f"; holes: {len(hits)}",
        "G21",
        "G90",
        f"G0 Z{parameters.safe_z:.4f}",
        f"M3 S{parameters.spindle_speed:.0f}",
    ]

    if parameters.single_tool_diameter is not None:
        tool_diameter = parameters.single_tool_diameter / scale
        hits = tuple(DrillHit(hit.x, hit.y, "TALL", tool_diameter) for hit in hits)
    grouped = _group_hits(hits)
    for group_index, (tool, tool_hits) in enumerate(grouped):
        diameter = tool_hits[0].diameter
        diameter_text = "unknown" if diameter is None else f"{diameter * scale:.4f} mm"
        if group_index and parameters.tool_change_pause:
            lines.extend(("G0 Z{:.4f}".format(parameters.safe_z), "M5"))
            lines.append(f"M0 (Cambiar a {tool}, {diameter_text}, continuar)")
            lines.append(f"M3 S{parameters.spindle_speed:.0f}")
        lines.append(f"; tool: {tool}, diameter: {diameter_text}")
        for hit in tool_hits:
            lines.append(f"G0 X{hit.x * scale:.4f} Y{hit.y * scale:.4f}")
            lines.append(f"G1 Z{-parameters.depth:.4f} F{parameters.plunge_rate:.2f}")
            lines.append(f"G0 Z{parameters.safe_z:.4f}")

    lines.extend((f"G0 Z{parameters.safe_z:.4f}", "M5", "G0 X0 Y0", "M2"))
    return "\n".join(lines) + "\n"


def _validate_parameters(parameters: DrillingParameters) -> None:
    if parameters.depth <= 0:
        raise ValueError("depth debe ser mayor que 0")
    if parameters.safe_z <= 0:
        raise ValueError("safe_z debe ser mayor que 0")
    if parameters.plunge_rate <= 0:
        raise ValueError("plunge_rate debe ser mayor que 0")
    if parameters.spindle_speed <= 0:
        raise ValueError("spindle_speed debe ser mayor que 0")
    if parameters.single_tool_diameter is not None and parameters.single_tool_diameter <= 0:
        raise ValueError("single_tool_diameter debe ser mayor que 0")


def _group_hits(hits: tuple[DrillHit, ...]) -> tuple[tuple[str, tuple[DrillHit, ...]], ...]:
    groups: dict[str, list[DrillHit]] = {}
    for hit in hits:
        groups.setdefault(hit.tool, []).append(hit)
    return tuple((tool, tuple(tool_hits)) for tool, tool_hits in groups.items())


_NEGATIVE_COORDINATE_TOLERANCE = 1e-6


def _transform_hits(
    hits: tuple[DrillHit, ...], parameters: DrillingParameters
) -> tuple[DrillHit, ...]:
    if not hits:
        return ()
    if parameters.reference_bounds is None:
        min_x = min(hit.x for hit in hits)
        max_x = max(hit.x for hit in hits)
        min_y = min(hit.y for hit in hits)
    else:
        min_x, max_x, min_y, _ = parameters.reference_bounds
    transformed = []
    for hit in hits:
        y = hit.y
        if parameters.mirror_x:
            # El espejo ya reubica el eje X en [0, max_x - min_x]; restar min_x
            # de nuevo lo correria fuera de rango cuando min_x != 0.
            x = max_x - hit.x
        else:
            x = hit.x - min_x if parameters.origin_lower_left else hit.x
        if parameters.origin_lower_left:
            y -= min_y
        transformed.append(DrillHit(x, y, hit.tool, hit.diameter))
    if parameters.origin_lower_left and parameters.reference_bounds is not None:
        _ensure_hits_within_reference(transformed)
    return tuple(transformed)


def _ensure_hits_within_reference(hits: list[DrillHit]) -> None:
    """Verifica que ningun taladro caiga fuera del origen compartido con --reference-gerber."""
    min_x = min(hit.x for hit in hits)
    min_y = min(hit.y for hit in hits)
    if min_x < -_NEGATIVE_COORDINATE_TOLERANCE or min_y < -_NEGATIVE_COORDINATE_TOLERANCE:
        raise ValueError(
            "un taladro queda fuera del contorno de referencia "
            f"(coordenada minima X={min_x:.4f} Y={min_y:.4f}); verificar que el Gerber "
            "de referencia (Edge_Cuts) cubra todo el archivo Excellon"
        )
