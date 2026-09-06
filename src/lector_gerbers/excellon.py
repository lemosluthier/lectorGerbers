"""Lectura inicial de archivos de taladros Excellon."""

from dataclasses import dataclass
from pathlib import Path
import re


@dataclass(frozen=True)
class DrillHit:
    """Taladro ejecutado con una herramienta determinada."""

    x: float
    y: float
    tool: str
    diameter: float | None


@dataclass(frozen=True)
class ExcellonFileInfo:
    """Metadatos y taladros encontrados en un archivo Excellon."""

    path: Path
    units: str | None
    tools: tuple[tuple[str, float], ...]
    hits: tuple[DrillHit, ...]


_TOOL_RE = re.compile(r"^T(\d+)C([0-9]+(?:\.[0-9]+)?)$")
_HIT_RE = re.compile(r"^X([+-]?[0-9]+(?:\.[0-9]+)?)Y([+-]?[0-9]+(?:\.[0-9]+)?)$")
_TOOL_SELECT_RE = re.compile(r"^T(\d+)$")


def inspect_drill(path: str | Path) -> ExcellonFileInfo:
    """Lee herramientas y posiciones de taladrado de un archivo Excellon."""
    file_path = Path(path)
    lines = [line.strip().upper() for line in file_path.read_text(encoding="ascii", errors="replace").splitlines()]
    units = "mm" if any(line.startswith("METRIC") for line in lines) else "in" if any(line.startswith("INCH") for line in lines) else None
    tools: dict[str, float] = {}
    hits: list[DrillHit] = []
    active_tool: str | None = None

    for line in lines:
        tool_match = _TOOL_RE.match(line)
        if tool_match:
            tools[f"T{tool_match.group(1)}"] = float(tool_match.group(2))
            continue
        selection_match = _TOOL_SELECT_RE.match(line)
        if selection_match:
            active_tool = f"T{selection_match.group(1)}"
            continue
        hit_match = _HIT_RE.match(line)
        if hit_match and active_tool is not None:
            hits.append(
                DrillHit(
                    float(hit_match.group(1)),
                    float(hit_match.group(2)),
                    active_tool,
                    tools.get(active_tool),
                )
            )

    return ExcellonFileInfo(file_path, units, tuple(tools.items()), tuple(hits))
