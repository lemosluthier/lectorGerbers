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

_DEFAULT_OUTPUT_SUBFOLDER = "salida-cnc"


def _resolve_output_directory(output_text: str, copper_path: Path) -> Path:
    """Determina la carpeta de salida: la elegida por el usuario o una subcarpeta
    junto al Gerber de cobre, para no mezclar los archivos generados con los
    Gerbers originales."""
    text = output_text.strip()
    return Path(text) if text else copper_path.parent / _DEFAULT_OUTPUT_SUBFOLDER


class GerberApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("Lector Gerbers y generador CNC")
        root.minsize(900, 700)
        self.values = {}
        self.layer_vars = {}
        self.canvas = None
        self._scene = None
        self._zoom = 1.0
        self._pan = (0.0, 0.0)
        self._pan_start = None
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
        views.rowconfigure(4, weight=1)

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

        ttk.Label(controls, text="Carpeta de salida").grid(row=row, column=0, sticky="w", pady=4)
        output_variable = tk.StringVar()
        self.values["output"] = output_variable
        ttk.Entry(controls, textvariable=output_variable, width=36).grid(row=row, column=1, sticky="ew", padx=8)
        ttk.Button(controls, text="Examinar", command=self._choose_output_folder).grid(row=row, column=2)
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

        ttk.Label(views, text="Vista combinada: diseño y recorridos G-code").grid(
            row=0, column=0, sticky="w", pady=(0, 4)
        )
        layers_row1 = ttk.Frame(views)
        layers_row1.grid(row=1, column=0, sticky="w", pady=(0, 2))
        layers_row2 = ttk.Frame(views)
        layers_row2.grid(row=2, column=0, sticky="w", pady=(0, 2))
        for key, text, default, row in (
            ("origin", "Origen (0,0)", True, layers_row1),
            ("reference", "Contorno", True, layers_row1),
            ("copper", "Cobre", True, layers_row1),
            ("drills", "Taladros diseño", True, layers_row1),
            ("cutting", "Recorrido aislamiento", True, layers_row2),
            ("drilling_gcode", "Taladrado G-code", True, layers_row2),
            ("rapid", "Recorrido rápido", False, layers_row2),
        ):
            variable = tk.BooleanVar(value=default)
            self.layer_vars[key] = variable
            ttk.Checkbutton(
                row, text=text, variable=variable, command=self._redraw_canvases
            ).pack(side="left", padx=(0, 10))

        # En su propia fila, nunca compartiendo espacio con los checkboxes, para
        # que no quede fuera del area visible si la ventana es angosta (eso
        # pasaba antes: a menos de ~1250px de ancho el boton quedaba recortado).
        toolbar = ttk.Frame(views)
        toolbar.grid(row=3, column=0, sticky="ew", pady=(0, 6))
        ttk.Button(toolbar, text="Centrar vista", command=self._reset_view).pack(side="left")

        self.canvas = tk.Canvas(views, background="#18212b", highlightthickness=0)
        self.canvas.grid(row=4, column=0, sticky="nsew")
        self.canvas.bind("<Configure>", self._redraw_canvases)
        self.canvas.bind("<MouseWheel>", self._on_mouse_wheel)
        self.canvas.bind("<ButtonPress-1>", self._on_pan_start)
        self.canvas.bind("<B1-Motion>", self._on_pan_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_pan_end)

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
        if not self.values["output"].get().strip():
            self.values["output"].set(str(Path(folder) / _DEFAULT_OUTPUT_SUBFOLDER))
        found = sum(path is not None for path in (files.copper, files.reference, files.drills))
        self.status.set(f"Carpeta cargada: {found}/3 archivos principales encontrados.")

    def _choose_output_folder(self):
        folder = filedialog.askdirectory(title="Carpeta de salida para G-code y simulacion")
        if folder:
            self.values["output"].set(folder)

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
            output = _resolve_output_directory(self.values["output"].get(), copper)
            output.mkdir(parents=True, exist_ok=True)
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
            self._draw_scene(
                gerber_info, reference_info, drill_info, bounds,
                self.mirror.get(), self.origin.get(), isolation_path, drilling_path,
            )
            self.status.set(
                f"Generados en {output}: {isolation_path.name}, {drilling_path.name} y {svg_path.name}"
            )
            messagebox.showinfo("Trabajo generado", self.status.get())
        except (OSError, ValueError) as error:
            messagebox.showerror("No se pudo generar", str(error))

    def _draw_scene(
        self, gerber_info, reference_info, drill_info, bounds,
        mirror_x, origin_lower_left, isolation_path, drilling_path,
    ):
        self._scene = (
            gerber_info, reference_info, drill_info, bounds,
            mirror_x, origin_lower_left, isolation_path, drilling_path,
        )
        self._zoom = 1.0
        self._pan = (0.0, 0.0)
        self._redraw_canvases()

    def _reset_view(self):
        self._zoom = 1.0
        self._pan = (0.0, 0.0)
        self._redraw_canvases()

    def _on_mouse_wheel(self, event):
        if not self._scene:
            return
        factor = 1.1 if event.delta > 0 else 1 / 1.1
        new_zoom = max(0.2, min(self._zoom * factor, 25.0))
        zoom_ratio = new_zoom / self._zoom
        pan_x, pan_y = self._pan
        self._pan = (
            event.x - zoom_ratio * (event.x - pan_x),
            event.y - zoom_ratio * (event.y - pan_y),
        )
        self._zoom = new_zoom
        self._redraw_canvases()

    def _on_pan_start(self, event):
        self._pan_start = (event.x, event.y, self._pan)

    def _on_pan_drag(self, event):
        if not self._pan_start:
            return
        start_x, start_y, (pan_x, pan_y) = self._pan_start
        self._pan = (pan_x + (event.x - start_x), pan_y + (event.y - start_y))
        self._redraw_canvases()

    def _on_pan_end(self, _event=None):
        self._pan_start = None

    def _apply_view(self, base_transform):
        zoom = self._zoom
        pan_x, pan_y = self._pan
        def transform(point):
            x, y = base_transform(point)
            return pan_x + x * zoom, pan_y + y * zoom
        return transform

    def _redraw_canvases(self, _event=None):
        if not self._scene:
            return
        (
            gerber_info, reference_info, drill_info, bounds,
            mirror_x, origin_lower_left, isolation_path, drilling_path,
        ) = self._scene
        show = {key: variable.get() for key, variable in self.layer_vars.items()}

        def board_transform(point):
            x, y = point
            if mirror_x:
                # El espejo ya reubica el eje X en [0, max_x - min_x]; restar
                # min_x de nuevo lo correria fuera de rango cuando min_x != 0.
                x = bounds[1] - x
            elif origin_lower_left:
                x -= bounds[0]
            if origin_lower_left:
                y -= bounds[2]
            return x, y

        rapid, cutting, drilling_sim = (), (), ()
        if show["rapid"] or show["cutting"] or show["drilling_gcode"]:
            rapid, cutting, drilling_sim = self._collect_gcode_moves(isolation_path, drilling_path)

        items = self._visible_items(
            show, gerber_info, reference_info, drill_info, board_transform, rapid, cutting, drilling_sim
        )
        self.canvas.delete("all")
        if not items:
            return
        base_transform, scale = self._canvas_transform(self.canvas, items)
        transform = self._apply_view(base_transform)
        scale *= self._zoom
        self._draw_layers(
            show, gerber_info, reference_info, drill_info, board_transform,
            transform, scale, rapid, cutting, drilling_sim,
        )

    @staticmethod
    def _collect_gcode_moves(isolation_path, drilling_path):
        rapid, cutting, drilling = [], [], []
        for path in (isolation_path, drilling_path):
            file_rapid, file_cutting, file_drilling = _collect_moves(path)
            rapid.extend(file_rapid)
            cutting.extend(file_cutting)
            drilling.extend(file_drilling)
        return rapid, cutting, drilling

    @staticmethod
    def _visible_items(show, gerber_info, reference_info, drill_info, board_transform, rapid, cutting, drilling_sim):
        """Junta los puntos de las capas activas para calcular un unico encuadre compartido."""
        items = []
        for info, enabled in ((gerber_info, show["copper"]), (reference_info, show["reference"])):
            if not enabled:
                continue
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
        if show["drills"]:
            items.extend(board_transform((hit.x, hit.y)) for hit in drill_info.hits)
        if show["rapid"]:
            items.extend(point for segment in rapid for point in segment)
        if show["cutting"]:
            items.extend(point for segment in cutting for point in segment)
        if show["drilling_gcode"]:
            items.extend(drilling_sim)
        if show["origin"]:
            items.append((0.0, 0.0))
        return items

    def _draw_layers(
        self, show, gerber_info, reference_info, drill_info, board_transform,
        transform, scale, rapid, cutting, drilling_sim,
    ):
        if show["reference"]:
            for primitive in reference_info.primitives:
                points = tuple(board_transform(point) for point in (primitive.points or _primitive_points(primitive)))
                if len(points) >= 2:
                    self.canvas.create_line(
                        *(value for point in points for value in transform(point)),
                        fill="#6c7a89", width=max((primitive.width or 0.15) * scale, 1),
                        capstyle=tk.ROUND,
                    )
        if show["rapid"]:
            for start, end in rapid:
                self.canvas.create_line(*transform(start), *transform(end), fill="#4a6fa5", width=1, dash=(3, 2))
        if show["copper"]:
            for primitive in gerber_info.primitives:
                points = tuple(board_transform(point) for point in (primitive.points or _primitive_points(primitive)))
                color = "#5eb6e4" if primitive.polarity == "clear" else "#d94f4f"
                if primitive.kind in {"draw", "arc"} and len(points) >= 2:
                    self.canvas.create_line(
                        *(value for point in points for value in transform(point)),
                        fill=color, width=max((primitive.width or 0.15) * scale, 1),
                        capstyle=tk.ROUND,
                    )
                elif primitive.kind == "region" and len(points) >= 3:
                    self.canvas.create_polygon(
                        *(value for point in points for value in transform(point)),
                        fill=color, outline="#ff9f8a" if primitive.polarity == "dark" else "#9fe3ff"
                    )
                elif primitive.kind == "flash":
                    self._draw_flash(primitive, transform(board_transform(primitive.end)), scale)
        if show["cutting"]:
            for start, end in cutting:
                self.canvas.create_line(*transform(start), *transform(end), fill="#7ee787", width=1.5)
        if show["drills"]:
            for hit in drill_info.hits:
                x, y = transform(board_transform((hit.x, hit.y)))
                radius = max((hit.diameter or 0.5) * scale / 2, 1)
                self.canvas.create_oval(x - radius, y - radius, x + radius, y + radius, fill="#f2d06b", outline="#fff3b0")
        if show["drilling_gcode"]:
            for point in drilling_sim:
                x, y = transform(point)
                self.canvas.create_oval(x - 3, y - 3, x + 3, y + 3, outline="#ff6b6b", width=1.5)
        if show["origin"]:
            self._draw_origin_marker(transform((0.0, 0.0)))

    def _draw_origin_marker(self, position):
        x, y = position
        size = 8
        self.canvas.create_line(x - size, y, x + size, y, fill="#ffffff", width=1.5)
        self.canvas.create_line(x, y - size, x, y + size, fill="#ffffff", width=1.5)
        self.canvas.create_oval(x - 3, y - 3, x + 3, y + 3, outline="#ffffff", width=1.5)
        self.canvas.create_text(
            x + size + 4, y - size - 4, text="(0, 0)", fill="#ffffff",
            anchor="sw", font=("TkDefaultFont", 8),
        )

    @staticmethod
    def _canvas_transform(canvas, points):
        min_x = min(x for x, _ in points)
        max_x = max(x for x, _ in points)
        min_y = min(y for _, y in points)
        max_y = max(y for _, y in points)
        width = max(canvas.winfo_width(), 1)
        height = max(canvas.winfo_height(), 1)
        span_x = max(max_x - min_x, 0.001)
        span_y = max(max_y - min_y, 0.001)
        scale = min((width - 20) / span_x, (height - 20) / span_y)
        # Centrar el contenido en el eje que sobra margen, en vez de anclarlo
        # siempre a 10px del borde (eso lo dejaba pegado a un costado cuando el
        # contenido no tiene la misma proporcion que el canvas).
        offset_x = (width - span_x * scale) / 2
        offset_y = (height - span_y * scale) / 2
        def transform(point):
            x, y = point
            return offset_x + (x - min_x) * scale, height - offset_y - (y - min_y) * scale
        return transform, scale

    def _draw_flash(self, primitive, center, scale):
        x, y = center
        width = max((primitive.width or 0.15) * scale, 1)
        height = max((primitive.height or primitive.width or 0.15) * scale, 1)
        color = "#5eb6e4" if primitive.polarity == "clear" else "#d94f4f"
        if primitive.shape == "C":
            radius = width / 2
            self.canvas.create_oval(x - radius, y - radius, x + radius, y + radius, fill=color)
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
        self.canvas.create_polygon(*(value for point in points for value in point), fill=color, outline=color)


def main() -> int:
    root = tk.Tk()
    GerberApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
