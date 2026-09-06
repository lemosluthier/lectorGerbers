"""Generacion de G-code GRBL para aislamiento de una capa."""

from .isolation import IsolationParameters, isolation_paths
from .parser import GerberFileInfo


def generate_isolation_gcode(
    info: GerberFileInfo,
    parameters: IsolationParameters,
    mirror_x: bool = False,
    origin_lower_left: bool = False,
) -> str:
    """Genera recorridos de aislamiento para la geometria interpretada."""
    paths = isolation_paths(info, parameters, mirror_x, origin_lower_left)
    lines = [
        "; Gerber isolation for GRBL",
        f"; file: {info.path.name}",
        f"; effective_width: {parameters.effective_width:.4f} mm",
        f"; passes: {parameters.passes}",
        f"; overlap: {parameters.overlap:.4f}",
        "G21",
        "G90",
        "G17",
        f"G0 Z{parameters.safe_z:.4f}",
        f"M3 S{parameters.spindle_speed:.0f}",
    ]

    for path in paths:
        if len(path) < 2:
            continue
        first_x, first_y = path[0]
        lines.append(f"G0 X{first_x:.4f} Y{first_y:.4f}")
        lines.append(f"G1 Z{-parameters.cut_depth:.4f} F{parameters.plunge_rate:.2f}")
        lines.append(f"G1 F{parameters.feed_rate:.2f}")
        for x, y in path[1:]:
            lines.append(f"G1 X{x:.4f} Y{y:.4f}")
        lines.append(f"G0 Z{parameters.safe_z:.4f}")

    lines.extend((f"G0 Z{parameters.safe_z:.4f}", "M5", "G0 X0 Y0", "M2"))
    return "\n".join(lines) + "\n"
