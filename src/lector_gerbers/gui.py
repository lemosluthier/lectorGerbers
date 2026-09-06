"""Interfaz grafica basica para generar trabajos CNC desde archivos de fabricacion."""

from pathlib import Path
from math import cos, sin
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .cli import _reference_bounds
from .drilling import DrillingParameters, generate_drilling_gcode
from .excellon import inspect_drill
from .gcode import generate_isolation_gcode
from .isolation import IsolationParameters
from .parser import inspect_file
from .project import discover_fabrication_files
from .simulation import _collect_moves, simulate_gcode_files
from .svg import _primitive_points


class GerberApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("Lector Gerbers y generador CNC")
        root.minsize(900, 700)
        self.values = {}
        self.gerber_canvas = None
        self.gcode_canvas = None
        self._gerber_scene = None
        self._gcode_scene = None
        self._build_form()

    def _build_form(self):
        frame = ttk.Frame(self.root, padding=12)
        frame.grid(sticky="nsew")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(0, weight=1)

        controls = ttk.Frame(frame)
        controls.grid(row=0, column=0, sticky="nw", padx=(0, 16))
        views = ttk.Frame(frame)
        views.grid(row=0, column=1, sticky="nsew")
        views.columnconfigure(0, weight=1)
        views.rowconfigure(1, weight=1)
        views.rowconfigure(3, weight=1)

        row = 0
        for label, key in (("Cobre Gerber", "copper"), ("Contorno Edge.Cuts", "reference"), ("Taladros Excellon", "drill")):
            ttk.Label(controls, text=label).grid(row=row, column=0, sticky="w", pady=4)
            variable = tk.StringVar()
            self.values[key] = variable
            ttk.Entry(controls, textvariable=variable, width=36).grid(row=row, column=1, sticky="ew", padx=8)
            ttk.Button(controls, text="Examinar", command=lambda k=key: self._choose_file(k)).grid(row=row, column=2)
            row += 1
        ttk.Button(controls, text="Cargar carpeta KiCad", command=self._choose_folder).grid(row=row, column=0, columnspan=3, pady=6)
        row += 1

        ttk.Separator(controls).grid(row=row, column=0, columnspan=3, sticky="ew", pady=10)
        row += 1
        fields = (
            ("Profundidad taladrado (mm)", "drill_depth", "1.6"),
            ("Diametro unico (mm, opcional)", "single_diameter", ""),
            ("Ancho punta (mm)", "tip_width", "0.2"),
            ("Angulo cono (grados)", "cone_angle", "60"),
            ("Profundidad aislamiento (mm)", "cut_depth", "0.1"),
            ("Pasadas aislamiento", "passes", "3"),
            ("Solapamiento", "overlap", "0.5"),
            ("Separacion cobre (mm)", "clearance", "0.1"),
            ("Altura segura (mm)", "safe_z", "2.0"),
            ("Avance descenso (mm/min)", "plunge_rate", "50"),
            ("RPM husillo", "spindle_speed", "10000"),
        )
        for label, key, default in fields:
            ttk.Label(controls, text=label).grid(row=row, column=0, sticky="w", pady=3)
            variable = tk.StringVar(value=default)
            self.values[key] = variable
            ttk.Entry(controls, textvariable=variable, width=18).grid(row=row, column=1, sticky="w", padx=8)
            row += 1

        self.mirror = tk.BooleanVar(value=True)
        self.origin = tk.BooleanVar(value=True)
        self.tool_change = tk.BooleanVar(value=True)
        for text, variable in (("Espejar X", self.mirror), ("Origen lower-left", self.origin), ("Pausar para cambiar herramientas", self.tool_change)):
            ttk.Checkbutton(controls, text=text, variable=variable).grid(row=row, column=0, columnspan=3, sticky="w", pady=2)
            row += 1
        ttk.Button(controls, text="Generar G-code y simulacion SVG", command=self._generate).grid(row=row, column=0, columnspan=3, pady=14)
        self.status = tk.StringVar(value="Seleccione los archivos de fabricacion.")
        ttk.Label(controls, textvariable=self.status, wraplength=400).grid(row=row + 1, column=0, columnspan=3, sticky="w")

        ttk.Label(views, text="Vista Gerber y taladros").grid(row=0, column=0, sticky="w", pady=(0, 4))
        self.gerber_canvas = tk.Canvas(views, background="#18212b", height=260, highlightthickness=0)
        self.gerber_canvas.grid(row=1, column=0, sticky="nsew", pady=(0, 10))
        ttk.Label(views, text="Vista recorridos G-code").grid(row=2, column=0, sticky="w", pady=(0, 4))
        self.gcode_canvas = tk.Canvas(views, background="#18212b", height=260, highlightthickness=0)
        self.gcode_canvas.grid(row=3, column=0, sticky="nsew")
        self.gerber_canvas.bind("<Configure>", self._redraw_canvases)
        self.gcode_canvas.bind("<Configure>", self._redraw_canvases)

    def _choose_file(self, key):
        path = filedialog.askopenfilename(filetypes=[("Archivos de fabricacion", "*.gbr *.gko *.drl"), ("Todos", "*.*")])
        if path:
            self.values[key].set(path)

    def _choose_folder(self):
        folder = filedialog.askdirectory(title="Carpeta de archivos de fabricacion")
        if not folder:
            return
        files = discover_fabrication_files(folder)
        for key, path in (("copper", files.copper), ("reference", files.reference), ("drill", files.drills)):
            if path:
                self.values[key].set(str(path))
        found = sum(path is not None for path in (files.copper, files.reference, files.drills))
        self.status.set(f"Carpeta cargada: {found}/3 archivos principales encontrados.")

    def _number(self, key, integer=False, optional=False):
        text = self.values[key].get().strip()
        if optional and not text:
            return None
        return int(text) if integer else float(text)

    def _generate(self):
        try:
            copper = Path(self.values["copper"].get())
            reference = Path(self.values["reference"].get())
            drill = Path(self.values["drill"].get())
            output = copper.parent
            bounds = _reference_bounds(reference)
            isolation = IsolationParameters(
                self._number("tip_width"), self._number("cone_angle"), self._number("cut_depth"),
                passes=self._number("passes", integer=True), overlap=self._number("overlap"),
                isolation_clearance=self._number("clearance"), safe_z=self._number("safe_z"),
                plunge_rate=self._number("plunge_rate"), spindle_speed=self._number("spindle_speed"),
                reference_bounds=bounds,
            )
            drilling = DrillingParameters(
                depth=self._number("drill_depth"), safe_z=self._number("safe_z"),
                plunge_rate=self._number("plunge_rate"), spindle_speed=self._number("spindle_speed"),
                mirror_x=self.mirror.get(), origin_lower_left=self.origin.get(),
                tool_change_pause=self.tool_change.get(), reference_bounds=bounds,
                single_tool_diameter=self._number("single_diameter", optional=True),
            )
            gerber_info = inspect_file(copper)
            reference_info = inspect_file(reference)
            drill_info = inspect_drill(drill)
            isolation_path = output / "isolation-gui.nc"
            drilling_path = output / "drilling-gui.nc"
            svg_path = output / "board-simulation-gui.svg"
            isolation_path.write_text(generate_isolation_gcode(gerber_info, isolation, self.mirror.get(), self.origin.get()), encoding="ascii")
            drilling_path.write_text(generate_drilling_gcode(drill_info, drilling), encoding="ascii")
            svg_path.write_text(simulate_gcode_files((isolation_path, drilling_path)), encoding="utf-8")
            self._draw_gerber(gerber_info, reference_info, drill_info, bounds, self.mirror.get(), self.origin.get())
            self._draw_gcode(isolation_path, drilling_path)
            self.status.set(f"Generados: {isolation_path.name}, {drilling_path.name} y {svg_path.name}")
            messagebox.showinfo("Trabajo generado", self.status.get())
        except (OSError, ValueError) as error:
            messagebox.showerror("No se pudo generar", str(error))

    def _draw_gerber(self, gerber_info, reference_info, drill_info, bounds, mirror_x, origin_lower_left):
        self._gerber_scene = (gerber_info, reference_info, drill_info, bounds, mirror_x, origin_lower_left)
        def board_transform(point):
            x, y = point
            if mirror_x:
                x = bounds[1] - x
            if origin_lower_left:
                x -= bounds[0]
                y -= bounds[2]
            return x, y

        items = []
        for info in (gerber_info, reference_info):
            for primitive in info.primitives:
                points = primitive.points or _primitive_points(primitive)
                items.extend(board_transform(point) for point in points)
                if primitive.kind == "flash":
                    center = board_transform(primitive.end)
                    half_width = (primitive.width or 0.15) / 2
                    half_height = (primitive.height or primitive.width or 0.15) / 2
                    items.extend((
                        (center[0] - half_width, center[1] - half_height),
                        (center[0] + half_width, center[1] + half_height),
                    ))
                elif primitive.kind in {"draw", "arc"}:
                    half_width = (primitive.width or 0.15) / 2
                    for point in points:
                        items.extend((
                            (point[0] - half_width, point[1] - half_width),
                            (point[0] + half_width, point[1] + half_width),
                        ))
        items.extend(board_transform((hit.x, hit.y)) for hit in drill_info.hits)
        if not items:
            return
        transform, scale = self._canvas_transform(self.gerber_canvas, items)
        self.gerber_canvas.delete("all")
        for primitive in reference_info.primitives:
            points = tuple(board_transform(point) for point in (primitive.points or _primitive_points(primitive)))
            if len(points) >= 2:
                self.gerber_canvas.create_line(
                    *(value for point in points for value in transform(point)),
                    fill="#6c7a89", width=max((primitive.width or 0.15) * scale, 1),
                    capstyle=tk.ROUND,
                )
        for primitive in gerber_info.primitives:
            points = tuple(board_transform(point) for point in (primitive.points or _primitive_points(primitive)))
            color = "#5eb6e4" if primitive.polarity == "clear" else "#d94f4f"
            if primitive.kind in {"draw", "arc"} and len(points) >= 2:
                self.gerber_canvas.create_line(
                    *(value for point in points for value in transform(point)),
                    fill=color, width=max((primitive.width or 0.15) * scale, 1),
                    capstyle=tk.ROUND,
                )
            elif primitive.kind == "region" and len(points) >= 3:
                self.gerber_canvas.create_polygon(
                    *(value for point in points for value in transform(point)),
                    fill=color, outline="#ff9f8a" if primitive.polarity == "dark" else "#9fe3ff"
                )
            elif primitive.kind == "flash":
                self._draw_flash(primitive, transform(board_transform(primitive.end)), scale)
        for hit in drill_info.hits:
            x, y = transform(board_transform((hit.x, hit.y)))
            radius = max((hit.diameter or 0.5) * scale / 2, 1)
            self.gerber_canvas.create_oval(x - radius, y - radius, x + radius, y + radius, fill="#f2d06b", outline="#fff3b0")

    def _draw_gcode(self, isolation_path, drilling_path):
        self._gcode_scene = (isolation_path, drilling_path)
        rapid = []
        cutting = []
        drilling = []
        for path in (isolation_path, drilling_path):
            file_rapid, file_cutting, file_drilling = _collect_moves(path)
            rapid.extend(file_rapid)
            cutting.extend(file_cutting)
            drilling.extend(file_drilling)
        items = [point for segment in rapid + cutting for point in segment] + drilling
        if not items:
            return
        transform, _scale = self._canvas_transform(self.gcode_canvas, items)
        self.gcode_canvas.delete("all")
        for segments, color in ((rapid, "#6c7a89"), (cutting, "#e85d4a")):
            for start, end in segments:
                self.gcode_canvas.create_line(*transform(start), *transform(end), fill=color, width=1)
        for point in drilling:
            x, y = transform(point)
            self.gcode_canvas.create_oval(x - 3, y - 3, x + 3, y + 3, fill="#f2d06b", outline="#fff3b0")

    @staticmethod
    def _canvas_transform(canvas, points):
        min_x = min(x for x, _ in points)
        max_x = max(x for x, _ in points)
        min_y = min(y for _, y in points)
        max_y = max(y for _, y in points)
        width = max(canvas.winfo_width(), 1)
        height = max(canvas.winfo_height(), 1)
        scale = min((width - 20) / max(max_x - min_x, 0.001), (height - 20) / max(max_y - min_y, 0.001))
        def transform(point):
            x, y = point
            return 10 + (x - min_x) * scale, height - 10 - (y - min_y) * scale
        return transform, scale

    def _redraw_canvases(self, _event=None):
        if self._gerber_scene:
            self._draw_gerber(*self._gerber_scene)
        if self._gcode_scene:
            self._draw_gcode(*self._gcode_scene)

    def _draw_flash(self, primitive, center, scale):
        x, y = center
        width = max((primitive.width or 0.15) * scale, 1)
        height = max((primitive.height or primitive.width or 0.15) * scale, 1)
        color = "#5eb6e4" if primitive.polarity == "clear" else "#d94f4f"
        if primitive.shape == "C":
            radius = width / 2
            self.gerber_canvas.create_oval(x - radius, y - radius, x + radius, y + radius, fill=color)
            return
        radius = min(width, height) / (2 if primitive.shape == "O" else 4)
        points = []
        for corner_x, corner_y, start in (
            (x - width / 2 + radius, y - height / 2 + radius, 180),
            (x + width / 2 - radius, y - height / 2 + radius, 270),
            (x + width / 2 - radius, y + height / 2 - radius, 0),
            (x - width / 2 + radius, y + height / 2 - radius, 90),
        ):
            for step in range(5):
                angle = (start + step * 90 / 4) * 3.141592653589793 / 180
                points.append((corner_x + radius * cos(angle), corner_y + radius * sin(angle)))
        self.gerber_canvas.create_polygon(*(value for point in points for value in point), fill=color, outline=color)


def main() -> int:
    root = tk.Tk()
    GerberApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
