# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Python tool to inspect, visualize, and generate GRBL G-code from Gerber RS-274X and Excellon drill files, for CNC PCB isolation milling and drilling. Documentation and commit messages in this repo are written in Spanish.

**Scope caveat**: the goal is to support Gerbers from any common PCB design tool, but today the parser, Excellon reader, and `project.py`'s file-association logic are written and tested exclusively against **KiCad** exports (see `Gerbers/`). Expanding beyond KiCad — and the concrete problems to expect when doing so (aperture macros, `G74` single-quadrant arcs, non-KiCad filename conventions, zero-suppressed Excellon coordinates, etc.) — is tracked as Etapa 8 in `PLAN.md`.

## Commands

Dev install (Windows/PowerShell):

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -e ".[test]"
```

Run tests:

```powershell
py -m pytest
```

Run a single test:

```powershell
py -m pytest tests/test_parser.py::test_parse_counterclockwise_arc
```

Entry points (installed via `pyproject.toml` `[project.scripts]`; use the `py -m ...` form if the Scripts folder isn't on `PATH`):

```powershell
py -m lector_gerbers.cli Gerbers\Dimmer-B_Cu.gbr --svg out.svg
py -m lector_gerbers.excellon_cli Gerbers\Dimmer-PTH.drl --gcode out.nc --depth 1.6
py -m lector_gerbers.simulation_cli out.nc --svg out-sim.svg
gerber-cnc-gui   # Tkinter GUI, no server needed
```

Build a portable Windows executable (must be tested on a separate machine before distributing):

```powershell
pyinstaller --onefile --windowed --name GerberCNC --paths src gerber_cnc_gui.py
```

## Architecture

Everything lives under `src/lector_gerbers/`, a linear pipeline of pure, mostly-immutable modules connected through frozen dataclasses:

1. **`parser.py`** — regex-based RS-274X reader. `inspect_file()` returns a `GerberFileInfo` (units, coordinate format, apertures, polarity) whose `primitives` is a tuple of frozen `GerberPrimitive` (`draw`/`flash`/`region`/`arc`). Coordinates are decoded from the `%FS` zero-suppression format; arcs (`G02`/`G03`) are sampled into polylines (`_sample_arc`), not kept as true arcs.
2. **`excellon.py`** — analogous reader for `.drl`/`.xln` files. `inspect_drill()` returns `ExcellonFileInfo` with `tools` and a tuple of `DrillHit`.
3. **`project.py`** — `discover_fabrication_files()` scans a KiCad fabrication export folder and matches copper/edge-cuts/drill files by filename suffix convention (e.g. `*_B_Cu`, `*_Edge_Cuts`, `*.drl` excluding NPTH).
4. **`isolation.py`** — turns copper `GerberPrimitive`s into a `shapely` geometry (`copper_geometry`) and computes offset isolation rings for N passes (`isolation_paths`), based on tool geometry in `IsolationParameters` (`tip_width`, `cone_angle`, `cut_depth` → `effective_width`/`tool_radius`/`pass_step`, per the formulas in `GCODE.md`).
5. **`gcode.py`** / **`drilling.py`** — emit GRBL text from the isolation paths / drill hits respectively (`G21`/`G90`, spindle on/off, safe-Z lifts between paths, `M0` tool-change pauses).
6. **`svg.py`** / **`simulation.py`** — SVG renderers: `svg.py` draws the parsed Gerber/Excellon geometry (design view), `simulation.py` re-parses generated `.nc` G-code line-by-line and draws rapids (gray) vs. cuts (red) vs. drill hits (yellow) (machining preview).
7. **`cli.py`** / **`excellon_cli.py`** / **`simulation_cli.py`** — argparse entry points wrapping the above (`gerber-info`, `drill-info`, `gcode-preview`).
8. **`gui.py`** — Tkinter app (`gerber-cnc-gui`) that wires file selection, KiCad folder auto-discovery, parameter forms, and side-by-side autozoom canvases (Gerber view above, G-code simulation below) on top of the same functions the CLIs use. It reaches into several "private" helpers of other modules directly (`cli._reference_bounds`, `svg._primitive_points`, `simulation._collect_moves`).

### Shared coordinate transform (mirror + origin)

`--mirror-x` (mirror for Bottom layers) and `--origin-lower-left` (translate to origin at the tool-path bounding box, not the copper bounding box) are implemented **separately** in four places that must stay behaviorally consistent: `isolation.transform_info`, `svg._transform_point`, `drilling._transform_hits`, and the inline `board_transform` closure in `gui.py`'s `_draw_gerber`. When generating isolation + drilling G-code that must overlay correctly in a combined simulation, both must be generated with the same `--reference-gerber` (or `reference_bounds`) so they share one bounding box instead of each computing its own from its own geometry — see `GCODE.md` for the rationale and `README.md` for the exact command pairing.

**Critical invariant**: on the X axis, `mirror_x` and `origin_lower_left` are mutually exclusive corrections, never both applied — `x = max_x - x` (mirror) already re-anchors the range to `[0, max_x - min_x]`, so also subtracting `min_x` double-shifts it into negative X whenever `min_x != 0` (Y always gets `y -= min_y` unconditionally when `origin_lower_left`, since Y is never mirrored). This was a real bug fixed 2026-09-09 that produced ~-21mm X coordinates with the sample `Gerbers/` files under the documented `--mirror-x --origin-lower-left --reference-gerber` combo — see `GCODE.md`'s Transformaciones section for the exact formula. A test for this must use `reference_bounds`/geometry with `min_x != 0`; `min_x == 0` fixtures don't exercise the bug. `isolation_paths`/`generate_drilling_gcode` also validate post-transform that no path/hit ends up outside the reference bounds, raising `ValueError` instead of silently emitting out-of-range coordinates.

### Testing

All tests are in the single file `tests/test_parser.py` (despite covering the whole package: parser, excellon, svg, isolation, gcode, drilling, simulation, project). Tests write synthetic Gerber/Excellon fixtures inline via `tmp_path` rather than relying on files in `Gerbers/`; the `Gerbers/` folder holds a real KiCad export used for manual/documented CLI runs (see README examples).

### Project docs

- `PLAN.md` — Spanish-language roadmap and progress log; check the "Estado de avance" / "Hoja de arranque" sections at the bottom before starting GRBL-controller-related work (Etapa 7), which is unimplemented and explicitly must not send real motion commands until the physical controller/wiring is confirmed.
- `GCODE.md` — spec for the isolation tool-width math, multi-pass offset formulas, and GRBL output requirements; treat it as the source of truth when changing `isolation.py` or `gcode.py`.
