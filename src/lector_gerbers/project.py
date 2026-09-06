"""Descubrimiento de archivos de fabricacion exportados por KiCad."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FabricationFiles:
    """Archivos relevantes encontrados en una carpeta de fabricacion."""

    copper: Path | None = None
    reference: Path | None = None
    drills: Path | None = None
    gerbers: tuple[Path, ...] = ()
    drill_files: tuple[Path, ...] = ()


_COPPER_SUFFIXES = ("_F_CU", "_B_CU", "-F_CU", "-B_CU")
_REFERENCE_SUFFIXES = ("_EDGE_CUTS", "-EDGE_CUTS", "_GKO", "-GKO")


def discover_fabrication_files(folder: str | Path) -> FabricationFiles:
    """Detecta archivos Gerber y Excellon comunes de una exportacion KiCad."""
    directory = Path(folder)
    files = tuple(sorted(path for path in directory.iterdir() if path.is_file()))
    gerbers = tuple(path for path in files if path.suffix.lower() in {".gbr", ".gtl", ".gbl", ".gko"})
    drill_files = tuple(path for path in files if path.suffix.lower() in {".drl", ".xln"})

    def normalized(path: Path) -> str:
        return path.stem.upper().replace(" ", "_")

    copper = next((path for path in gerbers if normalized(path).endswith(_COPPER_SUFFIXES)), None)
    reference = next((path for path in gerbers if normalized(path).endswith(_REFERENCE_SUFFIXES)), None)
    drills = next((path for path in drill_files if "NPTH" not in normalized(path)), None)
    return FabricationFiles(copper, reference, drills, gerbers, drill_files)
