from lector_gerbers.parser import inspect_file
from lector_gerbers.svg import render_svg
from lector_gerbers.excellon import inspect_drill
from lector_gerbers.svg import render_board
from lector_gerbers.svg import _transform_point
from lector_gerbers.gcode import generate_isolation_gcode
from lector_gerbers.isolation import IsolationParameters, isolation_paths
from lector_gerbers.simulation import simulate_gcode, simulate_gcode_files
from lector_gerbers.project import discover_fabrication_files
from lector_gerbers.drilling import DrillingParameters, generate_drilling_gcode


def test_inspect_detects_common_rs274x_metadata(tmp_path):
    gerber = tmp_path / "copper.gbr"
    gerber.write_text(
        "%FSLAX46Y46*%\n%MOMM*%\n%ADD10C,0.200*%\nD10*\nX100000Y200000D02*\nM02*\n",
        encoding="ascii",
    )

    info = inspect_file(gerber)

    assert info.units == "mm"
    assert info.coordinate_format == "L; X4.6/Y4.6"
    assert info.apertures == ("10",)
    assert info.aperture_sizes == (("D10", 0.2),)
    assert info.command_count == 6


def test_inspect_accepts_inch_units(tmp_path):
    gerber = tmp_path / "outline.gko"
    gerber.write_text("%FSLAX24Y24*%\n%MOIN*%\nM02*\n", encoding="ascii")

    info = inspect_file(gerber)

    assert info.units == "in"
    assert info.coordinate_format == "L; X2.4/Y2.4"


def test_parse_draw_and_flash_commands(tmp_path):
    gerber = tmp_path / "geometry.gbr"
    gerber.write_text(
        "%FSLAX24Y24*%\n%MOMM*%\n%ADD10C,0.200*%\nD10*\n"
        "X010000Y020000D02*\nX030000D01*\nX040000Y050000D03*\nM02*\n",
        encoding="ascii",
    )

    info = inspect_file(gerber)

    assert info.primitives[0].kind == "draw"
    assert info.primitives[0].start == (1.0, 2.0)
    assert info.primitives[0].end == (3.0, 2.0)
    assert info.primitives[0].aperture == "D10"
    assert info.primitives[0].width == 0.2
    assert info.primitives[1].kind == "flash"
    assert info.primitives[1].end == (4.0, 5.0)


def test_parse_kicad_style_coordinates_with_omitted_leading_zeroes(tmp_path):
    gerber = tmp_path / "silkscreen.gbr"
    gerber.write_text(
        "%FSLAX46Y46*%\n%MOMM*%\n%ADD10C,0.120000*%\nD10*\n"
        "X114045001Y-109405001D02*\nX118745001Y-109405001D01*\nM02*\n",
        encoding="ascii",
    )

    info = inspect_file(gerber)

    assert len(info.primitives) == 1
    assert info.primitives[0].start == (114.045001, -109.405001)
    assert info.primitives[0].end == (118.745001, -109.405001)


def test_render_svg_contains_parsed_draws(tmp_path):
    gerber = tmp_path / "line.gbr"
    gerber.write_text(
        "%FSLAX24Y24*%\n%MOMM*%\n%ADD10C,0.200*%\nD10*\n"
        "X010000Y020000D02*\n"
        "X030000Y020000D01*\nM02*\n",
        encoding="ascii",
    )

    svg = render_svg(inspect_file(gerber))

    assert svg.startswith("<svg ")
    assert svg.count("<line") == 1
    assert 'stroke-width="2.0000"' in svg


def test_parse_region_and_clear_polarity(tmp_path):
    gerber = tmp_path / "region.gbr"
    gerber.write_text(
        "%FSLAX24Y24*%\n%MOMM*%\n%LPC*%\nG36*\n"
        "X010000Y010000D02*\nX030000Y010000D01*\n"
        "X030000Y030000D01*\nX010000Y030000D01*\n"
        "X010000Y010000D01*\nG37*\nM02*\n",
        encoding="ascii",
    )

    info = inspect_file(gerber)
    svg = render_svg(info)

    assert info.polarity == "clear"
    assert len(info.primitives) == 1
    assert info.primitives[0].kind == "region"
    assert len(info.primitives[0].points) == 5
    assert '<polygon points="' in svg


def test_inspect_excellon_drills(tmp_path):
    drill = tmp_path / "board.drl"
    drill.write_text(
        "M48\nFMAT,2\nMETRIC\nT1C0.400\nT2C1.000\n%\n"
        "G90\nT1\nX10.5Y-2.0\nT2\nX20Y30\nM30\n",
        encoding="ascii",
    )

    info = inspect_drill(drill)

    assert info.units == "mm"
    assert info.tools == (("T1", 0.4), ("T2", 1.0))
    assert len(info.hits) == 2
    assert info.hits[0].diameter == 0.4
    assert info.hits[1].x == 20.0


def test_discover_kicad_fabrication_files(tmp_path):
    for name in ("Board-B_Cu.gbr", "Board-Edge_Cuts.gbr", "Board-PTH.drl", "Board-NPTH.drl", "Board-F_Silkscreen.gbr"):
        (tmp_path / name).write_text("", encoding="ascii")

    files = discover_fabrication_files(tmp_path)

    assert files.copper.name == "Board-B_Cu.gbr"
    assert files.reference.name == "Board-Edge_Cuts.gbr"
    assert files.drills.name == "Board-PTH.drl"
    assert len(files.gerbers) == 3
    assert len(files.drill_files) == 2


def test_generate_drilling_gcode_uses_depth_and_tool_change(tmp_path):
    drill = tmp_path / "board.drl"
    drill.write_text(
        "M48\nMETRIC\nT1C0.400\nT2C1.000\n%\nT1\nX10Y20\n"
        "T2\nX30Y40\nM30\n",
        encoding="ascii",
    )

    gcode = generate_drilling_gcode(
        inspect_drill(drill),
        DrillingParameters(1.8, tool_change_pause=True, origin_lower_left=True),
    )

    assert "G21" in gcode
    assert "G1 Z-1.8000" in gcode
    assert "M0 (Cambiar a T2" in gcode
    assert gcode.count("G1 Z-1.8000") == 2
    assert gcode.index("M5") < gcode.index("M0 (Cambiar a T2")
    assert gcode.endswith("G0 X0 Y0\nM2\n")


def test_drilling_uses_reference_bounds_for_mirror(tmp_path):
    drill = tmp_path / "board.drl"
    drill.write_text(
        "M48\nMETRIC\nT1C0.400\n%\nT1\nX2Y3\nM30\n",
        encoding="ascii",
    )

    gcode = generate_drilling_gcode(
        inspect_drill(drill),
        DrillingParameters(
            1.0,
            mirror_x=True,
            origin_lower_left=True,
            reference_bounds=(0.0, 10.0, 0.0, 10.0),
        ),
    )

    assert "G0 X8.0000 Y3.0000" in gcode


def test_generate_drilling_gcode_can_use_one_tool_without_changes(tmp_path):
    drill = tmp_path / "board.drl"
    drill.write_text(
        "M48\nMETRIC\nT1C0.400\nT2C1.000\n%\nT1\nX10Y20\nT2\nX30Y40\nM30\n",
        encoding="ascii",
    )

    gcode = generate_drilling_gcode(
        inspect_drill(drill),
        DrillingParameters(1.0, single_tool_diameter=0.8),
    )

    assert "; tool: TALL, diameter: 0.8000 mm" in gcode
    assert gcode.count("G1 Z-1.0000") == 2
    assert "M0 (Cambiar" not in gcode


def test_render_board_combines_gerber_and_drills(tmp_path):
    gerber = tmp_path / "copper.gbr"
    gerber.write_text(
        "%FSLAX24Y24*%\n%MOMM*%\nD10*\nX010000Y020000D02*\n"
        "X030000Y020000D01*\nM02*\n",
        encoding="ascii",
    )
    drill = tmp_path / "board.drl"
    drill.write_text(
        "M48\nMETRIC\nT1C0.400\n%\nT1\nX20Y30\nM30\n",
        encoding="ascii",
    )

    svg = render_board((inspect_file(gerber),), (inspect_drill(drill),))

    assert svg.count("<line") == 1
    assert svg.count("<circle") == 1
    assert "#f2d06b" in svg


def test_bottom_transform_mirrors_and_places_origin_at_lower_left():
    assert _transform_point((2.0, 5.0), 2.0, 12.0, 5.0, True, True) == (8.0, 0.0)
    assert _transform_point((2.0, 5.0), 2.0, 12.0, 5.0, False, True) == (0.0, 0.0)


def test_isolation_parameters_calculate_effective_width_and_step():
    parameters = IsolationParameters(0.2, 60.0, 0.1, passes=3, overlap=0.5)

    assert round(parameters.effective_width, 6) == 0.31547
    assert round(parameters.pass_step, 6) == 0.157735


def test_generate_isolation_gcode_contains_grbl_setup_and_passes(tmp_path):
    gerber = tmp_path / "line.gbr"
    gerber.write_text(
        "%FSLAX24Y24*%\n%MOMM*%\n%ADD10C,0.200*%\nD10*\n"
        "X010000Y020000D02*\nX030000Y020000D01*\nM02*\n",
        encoding="ascii",
    )
    parameters = IsolationParameters(0.2, 60.0, 0.1, passes=2, overlap=0.5, spindle_speed=12000)
    info = inspect_file(gerber)

    paths = isolation_paths(info, parameters)
    gcode = generate_isolation_gcode(info, parameters)

    assert len(paths) == 2
    assert "G21" in gcode
    assert "G90" in gcode
    assert "M3 S12000" in gcode
    assert gcode.index("M3 S12000") < gcode.index("G1 Z-0.1000")
    assert "M5" in gcode
    assert gcode.index("M5") < gcode.index("M2")
    assert gcode.count("G1 Z-0.1000") == 2
    assert gcode.endswith("G0 X0 Y0\nM2\n")


def test_isolation_paths_with_origin_have_no_negative_coordinates(tmp_path):
    gerber = tmp_path / "line.gbr"
    gerber.write_text(
        "%FSLAX24Y24*%\n%MOMM*%\n%ADD10C,0.200*%\nD10*\n"
        "X010000Y020000D02*\nX030000Y020000D01*\nM02*\n",
        encoding="ascii",
    )
    parameters = IsolationParameters(0.2, 60.0, 0.1)

    paths = isolation_paths(inspect_file(gerber), parameters, origin_lower_left=True)

    assert min(point[0] for path in paths for point in path) >= 0
    assert min(point[1] for path in paths for point in path) >= 0


def test_isolation_paths_support_disconnected_regions(tmp_path):
    gerber = tmp_path / "regions.gbr"
    gerber.write_text(
        "%FSLAX24Y24*%\n%MOMM*%\nG36*"
        "X010000Y010000D02*X020000Y010000D01*X020000Y020000D01*"
        "X010000Y020000D01*X010000Y010000D01*G37*G36*"
        "X040000Y010000D02*X050000Y010000D01*X050000Y020000D01*"
        "X040000Y020000D01*X040000Y010000D01*G37*M02*\n",
        encoding="ascii",
    )

    paths = isolation_paths(inspect_file(gerber), IsolationParameters(0.2, 60.0, 0.1))

    assert len(paths) == 2
    assert all(len(path) >= 4 for path in paths)


def test_parse_rectangular_and_oblong_apertures(tmp_path):
    gerber = tmp_path / "pads.gbr"
    gerber.write_text(
        "%FSLAX24Y24*%\n%MOMM*%\n%ADD10R,1.905X2.000*%\n"
        "%ADD11O,1.600X2.400*%\nD10*X010000Y010000D03*"
        "D11*X020000Y020000D03*M02*\n",
        encoding="ascii",
    )

    info = inspect_file(gerber)

    assert info.aperture_definitions == (
        ("D10", "R", (1.905, 2.0)),
        ("D11", "O", (1.6, 2.4)),
    )
    assert [(primitive.shape, primitive.height) for primitive in info.primitives] == [
        ("R", 2.0),
        ("O", 2.4),
    ]


def test_parse_round_rect_aperture(tmp_path):
    gerber = tmp_path / "round-pad.gbr"
    gerber.write_text(
        "%FSLAX24Y24*%\n%MOMM*%\n%AMRoundRect*%\n"
        "%ADD18RoundRect,0.250000X0.550000X-0.550000X0.550000*%\n"
        "D18*X010000Y010000D03*M02*\n",
        encoding="ascii",
    )

    info = inspect_file(gerber)

    assert info.aperture_definitions == (("D18", "RoundRect", (0.25, 0.55)),)
    assert (info.primitives[0].shape, info.primitives[0].width, info.primitives[0].height) == (
        "RoundRect", 0.25, 0.55
    )


def test_parse_counterclockwise_arc(tmp_path):
    gerber = tmp_path / "arc.gbr"
    gerber.write_text(
        "%FSLAX24Y24*%\n%MOMM*%\n%ADD10C,0.200*%\nD10*\n"
        "X030000Y020000D02*G03*X020000Y030000I-010000J000000D01*M02*\n",
        encoding="ascii",
    )

    info = inspect_file(gerber)
    primitive = info.primitives[0]

    assert primitive.kind == "arc"
    assert primitive.clockwise is False
    assert primitive.center == (2.0, 2.0)
    assert len(primitive.points) == 33
    assert primitive.points[0] == primitive.start
    assert primitive.points[-1] == primitive.end


def test_simulate_gcode_separates_rapid_and_cutting_moves(tmp_path):
    gcode = tmp_path / "test.nc"
    gcode.write_text(
        "G21\nG90\nG0 Z2\nG0 X1 Y1\nG1 Z-0.1\nG1 X3 Y1\nG0 Z2\nM5\nM2\n",
        encoding="ascii",
    )

    svg = simulate_gcode(gcode)

    assert "Simulacion: test.nc" in svg
    assert svg.count("stroke=\"#6c7a89\"") == 1
    assert svg.count("stroke=\"#e85d4a\"") == 1


def test_simulate_drilling_marks_holes(tmp_path):
    gcode = tmp_path / "drilling.nc"
    gcode.write_text(
        "; Excellon drilling for GRBL\nG21\nG90\nG0 Z2\n"
        "G0 X1 Y2\nG1 Z-1.6 F50\nG0 Z2\n"
        "G0 X3 Y4\nG1 Z-1.6 F50\nG0 Z2\nM2\n",
        encoding="ascii",
    )

    svg = simulate_gcode(gcode)

    assert svg.count("<circle") == 2
    assert "#f2d06b" in svg


def test_simulate_gcode_files_superimposes_isolation_and_drilling(tmp_path):
    isolation = tmp_path / "isolation.nc"
    isolation.write_text(
        "G21\nG90\nG0 X0 Y0\nG1 Z-0.1\nG1 X4 Y0\nM2\n",
        encoding="ascii",
    )
    drilling = tmp_path / "drilling.nc"
    drilling.write_text(
        "; Excellon drilling for GRBL\nG21\nG90\nG0 X2 Y2\n"
        "G1 Z-1 F50\nG0 Z2\nM2\n",
        encoding="ascii",
    )

    svg = simulate_gcode_files((isolation, drilling))

    assert "Simulacion: isolation.nc + drilling.nc" in svg
    assert svg.count("stroke=\"#e85d4a\"") == 1
    assert svg.count("<circle") == 1
