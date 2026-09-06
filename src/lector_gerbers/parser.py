"""Inspección básica de archivos Gerber RS-274X."""

from dataclasses import dataclass
from math import atan2, cos, hypot, pi, sin
from pathlib import Path
import re


@dataclass(frozen=True)
class GerberFileInfo:
    """Metadatos útiles para identificar una capa Gerber."""

    path: Path
    units: str | None
    coordinate_format: str | None
    apertures: tuple[str, ...]
    command_count: int
    polarity: str | None = None
    aperture_sizes: tuple[tuple[str, float], ...] = ()
    aperture_definitions: tuple[tuple[str, str, tuple[float, ...]], ...] = ()
    primitives: tuple["GerberPrimitive", ...] = ()


@dataclass(frozen=True)
class GerberPrimitive:
    """Elemento geométrico producido por un comando de interpolación lineal."""

    kind: str
    start: tuple[float, float] | None
    end: tuple[float, float]
    aperture: str | None = None
    width: float | None = None
    shape: str = "C"
    height: float | None = None
    center: tuple[float, float] | None = None
    clockwise: bool | None = None
    polarity: str = "dark"
    points: tuple[tuple[float, float], ...] = ()


_FORMAT_RE = re.compile(r"%FS([LTA])A?X(\d)(\d)Y(\d)(\d)\*%")
_APERTURE_RE = re.compile(r"%ADD([A-Z]?\d+)[^*]*\*%")
_APERTURE_DEF_RE = re.compile(r"%ADD([A-Z]?\d+)([A-Za-z][A-Za-z0-9]*),([^*]+)\*%")
_COORDINATE_RE = re.compile(r"([XY])([+-]?\d+)")
_OFFSET_RE = re.compile(r"([IJ])([+-]?\d+)")
_COMMAND_RE = re.compile(r"D(\d+)")
_INTERPOLATION_RE = re.compile(r"G0([123])")
def inspect_file(path: str | Path) -> GerberFileInfo:
    """Lee un Gerber y devuelve metadatos sin interpretar su geometría."""
    file_path = Path(path)
    content = file_path.read_text(encoding="ascii", errors="replace")

    units = None
    if "%MOMM*%" in content:
        units = "mm"
    elif "%MOIN*%" in content:
        units = "in"

    format_match = _FORMAT_RE.search(content)
    coordinate_format = None
    if format_match:
        zero_suppression, x_integer, x_decimal, y_integer, y_decimal = format_match.groups()
        coordinate_format = (
            f"{zero_suppression}; X{x_integer}.{x_decimal}/Y{y_integer}.{y_decimal}"
        )

    apertures = tuple(dict.fromkeys(_APERTURE_RE.findall(content)))
    aperture_definitions = _parse_aperture_definitions(content)
    aperture_sizes = tuple((code, dimensions[0]) for code, _, dimensions in aperture_definitions)
    command_count = sum(1 for token in content.split("*") if token.strip())
    polarity_match = re.search(r"%LP([DC])\*%", content)
    polarity = {"D": "dark", "C": "clear"}.get(polarity_match.group(1)) if polarity_match else None
    primitives = _parse_primitives(
        content,
        format_match,
        polarity or "dark",
        {code: (shape, dimensions) for code, shape, dimensions in aperture_definitions},
    )

    return GerberFileInfo(
        path=file_path,
        units=units,
        coordinate_format=coordinate_format,
        apertures=apertures,
        command_count=command_count,
        polarity=polarity,
        aperture_sizes=aperture_sizes,
        aperture_definitions=aperture_definitions,
        primitives=primitives,
    )


def _parse_primitives(
    content: str,
    format_match: re.Match[str] | None,
    polarity: str,
    aperture_definitions: dict[str, tuple[str, tuple[float, ...]]],
) -> tuple[GerberPrimitive, ...]:
    """Interpreta movimientos, trazas y flashes con coordenadas absolutas."""
    if format_match is None:
        return ()

    zero_suppression, x_integer, x_decimal, y_integer, y_decimal = format_match.groups()
    x_width = int(x_integer) + int(x_decimal)
    y_width = int(y_integer) + int(y_decimal)
    current: tuple[float, float] | None = None
    aperture: str | None = None
    shape = "C"
    dimensions: tuple[float, ...] = ()
    in_region = False
    region_points: list[tuple[float, float]] = []
    interpolation = 1
    primitives: list[GerberPrimitive] = []

    for token in content.split("*"):
        if "G36" in token:
            in_region = True
            region_points = []
            continue
        if "G37" in token:
            if len(region_points) >= 3:
                primitives.append(
                    GerberPrimitive(
                        kind="region",
                        start=region_points[0],
                        end=region_points[-1],
                        aperture=aperture,
                        polarity=polarity,
                        points=tuple(region_points),
                    )
                )
            in_region = False
            region_points = []
            continue

        coordinates = dict(_COORDINATE_RE.findall(token))
        offsets = dict(_OFFSET_RE.findall(token))
        interpolation_match = _INTERPOLATION_RE.search(token)
        if interpolation_match:
            interpolation = int(interpolation_match.group(1))
        command_match = _COMMAND_RE.search(token)
        if command_match is not None:
            command = int(command_match.group(1))
            if command >= 10:
                aperture = f"D{command}"
                shape, dimensions = aperture_definitions.get(aperture, ("C", ()))
                continue

            if not coordinates:
                continue
            if current is None and ("X" not in coordinates or "Y" not in coordinates):
                continue
            point = (
                _decode_coordinate(coordinates["X"], x_width, int(x_decimal), zero_suppression)
                if "X" in coordinates
                else current[0],
                _decode_coordinate(coordinates["Y"], y_width, int(y_decimal), zero_suppression)
                if "Y" in coordinates
                else current[1],
            )
            if command == 2:
                current = point
                if in_region:
                    region_points = [point]
            elif command == 1 and current is not None:
                if in_region:
                    region_points.append(point)
                elif interpolation in (2, 3) and "I" in offsets and "J" in offsets:
                    center = (
                        current[0] + _decode_coordinate(offsets["I"], x_width, int(x_decimal), "L"),
                        current[1] + _decode_coordinate(offsets["J"], y_width, int(y_decimal), "L"),
                    )
                    arc_points = _sample_arc(current, point, center, interpolation == 2)
                    primitives.append(
                        GerberPrimitive(
                            kind="arc", start=current, end=point, aperture=aperture,
                            width=dimensions[0] if dimensions else None,
                            shape=shape, height=dimensions[1] if len(dimensions) > 1 else None,
                            polarity=polarity, points=arc_points, center=center,
                            clockwise=interpolation == 2,
                        )
                    )
                else:
                    primitives.append(
                        GerberPrimitive(
                            kind="draw", start=current, end=point, aperture=aperture,
                            width=dimensions[0] if dimensions else None,
                            shape=shape,
                            height=dimensions[1] if len(dimensions) > 1 else None,
                            polarity=polarity,
                        )
                    )
                current = point
            elif command == 3:
                primitives.append(
                    GerberPrimitive(
                        kind="flash", start=current, end=point, aperture=aperture,
                        width=dimensions[0] if dimensions else None,
                        shape=shape,
                        height=dimensions[1] if len(dimensions) > 1 else None,
                        polarity=polarity,
                    )
                )
                current = point

    return tuple(primitives)


def _sample_arc(
    start: tuple[float, float],
    end: tuple[float, float],
    center: tuple[float, float],
    clockwise: bool,
    samples: int = 32,
) -> tuple[tuple[float, float], ...]:
    """Aproxima un arco Gerber con puntos para renderizado y offsets."""
    start_angle = atan2(start[1] - center[1], start[0] - center[0])
    end_angle = atan2(end[1] - center[1], end[0] - center[0])
    if clockwise:
        sweep = (start_angle - end_angle) % (2 * pi)
        step = -sweep / samples
    else:
        sweep = (end_angle - start_angle) % (2 * pi)
        step = sweep / samples
    radius = hypot(start[0] - center[0], start[1] - center[1])
    return tuple(
        (
            center[0] + radius * cos(start_angle + step * index),
            center[1] + radius * sin(start_angle + step * index),
        )
        for index in range(samples + 1)
    )


def _parse_aperture_definitions(
    content: str,
) -> tuple[tuple[str, str, tuple[float, ...]], ...]:
    """Lee dimensiones de aperturas circulares, rectangulares y oblongas."""
    definitions: list[tuple[str, str, tuple[float, ...]]] = []
    for match in _APERTURE_DEF_RE.finditer(content):
        code, shape, parameters = match.groups()
        if shape in {"C", "R", "O", "RoundRect"}:
            dimensions = tuple(float(value) for value in parameters.split("X")[:2])
            definitions.append((f"D{code}", shape, dimensions))
    unique = {}
    for code, shape, dimensions in definitions:
        unique[code] = (code, shape, dimensions)
    return tuple(unique.values())


def _decode_coordinate(
    value: str, width: int, decimals: int, zero_suppression: str
) -> float:
    """Convierte una coordenada Gerber sin punto decimal explícito."""
    sign = -1 if value.startswith("-") else 1
    digits = value.lstrip("+-")
    if zero_suppression == "L":
        digits = digits.rjust(width, "0")
    elif zero_suppression == "T":
        digits = digits.ljust(width, "0")
    return sign * int(digits) / (10**decimals)
