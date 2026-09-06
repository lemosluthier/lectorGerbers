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


_COPPER_SUFFIXES = (
    "_F_CU",
    "_B_CU",
    "-F_CU",
    "-B_CU",
    "_F_COPPER",
    "_B_COPPER",
    "-F_COPPER",
    "-B_COPPER",
)
_REFERENCE_SUFFIXES = (
    "_EDGE_CUTS",
    "-EDGE_CUTS",
    "_GKO",
    "-GKO",
    "_OUTLINE",
    "-OUTLINE",
)
_GERBER_EXTENSIONS = {".gbr", ".gtl", ".gbl", ".gko", ".gto", ".gbo", ".gts", ".gbs"}
_DRILL_EXTENSIONS = {".drl", ".xln"}


def discover_fabrication_files(folder: str | Path) -> FabricationFiles:
    """Detecta archivos Gerber y Excellon comunes de una exportacion KiCad."""
    directory = Path(folder)
    if not directory.exists() or not directory.is_dir():
        return FabricationFiles()

    files = tuple(sorted(path for path in directory.iterdir() if path.is_file()))
    gerbers = tuple(path for path in files if path.suffix.lower() in _GERBER_EXTENSIONS)
    drill_files = tuple(path for path in files if path.suffix.lower() in _DRILL_EXTENSIONS)

    def normalized(path: Path) -> str:
        return path.stem.upper().replace(" ", "_")

    copper = next((path for path in gerbers if normalized(path).endswith(_COPPER_SUFFIXES)), None)
    reference = next((path for path in gerbers if normalized(path).endswith(_REFERENCE_SUFFIXES)), None)
    drills = next((path for path in drill_files if "NPTH" not in normalized(path)), None)
    return FabricationFiles(copper, reference, drills, gerbers, drill_files)
