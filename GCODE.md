# Especificación de insolado y G-code GRBL

## Alcance inicial

La primera operación de fabricación será el insolado de la capa de cobre. El proyecto también genera movimientos de agujereado a partir de archivos Excellon.

El resultado será un archivo G-code para GRBL con recorridos de aislamiento alrededor de pistas, pads, islas y regiones de cobre.

## Taladrado Excellon

El comando `drill-info` puede generar un archivo de taladrado con `--depth` (profundidad en milímetros), `--safe-z`, `--plunge-rate` y `--tool-change`. Los taladros se agrupan por herramienta y los archivos Excellon expresados en pulgadas se convierten a milímetros para `G21`.

Antes de mecanizar se debe verificar que la profundidad atraviese la placa sin exceder lo permitido por la mesa o el material de soporte.

## Datos de la herramienta

La fresa de grabado cónica tendrá tres parámetros:

- `tip_width`: ancho o diámetro plano de la punta.
- `cone_angle`: ángulo total del cono.
- `cut_depth`: profundidad de penetración en el cobre.

Suposición inicial: `tip_width` representa el ancho de corte en la punta cuando la profundidad es cero y `cone_angle` es el ángulo total incluido entre ambos lados del cono.

El ancho efectivo de corte se calculará como:

```text
effective_width = tip_width + 2 * cut_depth * tan(cone_angle / 2)
```

Los tres valores deben usar las mismas unidades, preferentemente milímetros. El ángulo se ingresará en grados y se convertirá internamente a radianes.

## Recorridos de aislamiento

Para evitar cortar las pistas, el centro del recorrido debe mantenerse fuera del límite del cobre al menos una distancia equivalente a:

```text
tool_radius = effective_width / 2
safety_clearance = tool_radius + isolation_clearance
```

La primera pasada se ubicará sobre ese desplazamiento exterior. Nunca se generará un recorrido dentro del área de cobre.

## Pasadas múltiples

Parámetros previstos:

- `passes`: cantidad de pasadas de aislamiento.
- `overlap`: proporción de solapamiento entre pasadas, entre `0` y `1`.
- `isolation_clearance`: separación adicional respecto del borde del cobre.
- `spindle_speed`: velocidad del husillo en RPM.

La separación entre centros de pasadas será:

```text
pass_step = effective_width * (1 - overlap)
```

La distancia de cada pasada respecto del cobre será:

```text
pass_offset(n) = safety_clearance + n * pass_step
```

donde `n` comienza en `0`. Con este esquema cada pasada se aleja del borde y se solapa con la anterior, reduciendo la posibilidad de que queden restos de cobre.

## Transformaciones

Antes de calcular los recorridos se aplicarán las mismas transformaciones ya implementadas para la vista:

1. Espejo horizontal para la capa Bottom.
2. Traslación del diseño al origen inferior izquierdo.
3. Conservación de la escala y unidades en milímetros.

Cuando **no** se usa `--reference-gerber`, el origen inferior izquierdo se recalcula sobre el límite real de los recorridos de la herramienta (incluyendo el offset exterior de aislamiento), así que nunca hay coordenadas negativas.

Cuando **sí** se usa `--reference-gerber` (necesario para que aislamiento y taladrado compartan el mismo origen), el límite inferior izquierdo se fija con los límites del Gerber de referencia (contorno/Edge_Cuts), no con los del propio archivo. Por eso la fórmula de espejo y traslación debe cumplir un invariante preciso para no generar coordenadas negativas:

```text
mirror_x            -> x' = max_x - x                  (ya queda en [0, max_x - min_x])
origin_lower_left    -> x' = x - min_x                  (solo si NO hay espejo)
mirror_x + origin_lower_left -> x' = max_x - x           (el espejo YA deja el origen en 0;
                                                           restar min_x de nuevo lo saca de rango)
origin_lower_left (Y, siempre) -> y' = y - min_y
```

Es decir: **el eje X nunca debe recibir las dos correcciones (espejo y `- min_x`) a la vez**; el espejo alrededor de `max_x` ya reubica el rango en `[0, max_x - min_x]`. Aplicar ambas correcciones fue un bug real detectado el 2026-09-09: con los Gerbers de muestra del proyecto (`Gerbers/Dimmer-*`) y el comando documentado más abajo (`--mirror-x --origin-lower-left --reference-gerber`), el G-code de aislamiento resultante tenía coordenadas cercanas a **X = -21 mm** — es decir, la fresa se habría movido 21 mm hacia afuera del área de trabajo esperada. La corrección está implementada de forma independiente (sin una función compartida) en cuatro lugares que deben mantenerse sincronizados manualmente: `isolation.transform_info`, `drilling._transform_hits`, `svg._transform_point` y el `board_transform` inline dentro de `gui.py` (`GerberApp._draw_gerber`). Cualquier cambio a esta fórmula debe replicarse en los cuatro y agregar un test para cada uno con `min_x != 0` (los tests con `min_x == 0` no detectan este tipo de bug porque el término de más se anula).

Como red de seguridad adicional, si aun así un recorrido de aislamiento o un taladro cae en coordenadas negativas respecto del contorno de referencia (por ejemplo porque el margen entre el cobre y el borde de la placa es menor que el offset de la fresa), `isolation_paths` y `generate_drilling_gcode` levantan un `ValueError` explícito en vez de generar un archivo con coordenadas fuera de rango. El mensaje indica que hay que agrandar el margen del Gerber de referencia o generar el aislamiento sin `--reference-gerber`.

Estas transformaciones deben ser compartidas por el render SVG y el generador G-code para que la vista previa coincida con el mecanizado. `svg.render_svg`/`render_board` aceptan un parámetro `reference_bounds` equivalente al de `isolation.py`/`drilling.py` (antes solo existía en estos dos últimos); `cli.py` lo pasa automáticamente cuando se usa `--reference-gerber` junto con `--svg`.

## Generación GRBL

El archivo deberá incluir, como mínimo:

- Configuración de unidades en milímetros: `G21`.
- Coordenadas absolutas: `G90`.
- Altura segura configurable.
- Velocidad de avance configurable.
- Velocidad de descenso configurable.
- Movimientos rápidos con `G0`.
- Movimientos de corte con `G1`.
- Encendido del husillo con `M3 S<velocidad>`.
- Apagado del husillo con `M5` antes del cierre.
- Levantamiento de herramienta entre recorridos.
- Comentarios con los parámetros utilizados.
- Cierre seguro del programa.

## Validaciones obligatorias

Antes de generar un archivo utilizable en la máquina se deberá verificar:

- Ningún recorrido atraviesa el cobre que se desea conservar.
- Las pasadas permanecen dentro del área de trabajo. Cuando se usa `--reference-gerber`, `isolation_paths`/`generate_drilling_gcode` validan esto automáticamente y levantan un error si un recorrido o un taladro queda fuera del contorno de referencia, en vez de generar coordenadas negativas silenciosamente.
- El origen y el espejo coinciden con la vista previa.
- Las unidades y profundidades son coherentes.
- El archivo puede simularse visualmente antes de enviarlo al CNC.

## Limitaciones conocidas

- Las aperturas rectangulares y oblongas tienen soporte inicial para flashes; las formas especiales todavía requieren soporte geométrico completo.
- Los arcos Gerber se muestrean como polilíneas para renderizado y aislamiento; todavía falta evaluar la emisión directa como `G2`/`G3`.
- El cálculo de offsets robustos requiere una biblioteca geométrica o un algoritmo específico para uniones, esquinas y regiones complejas.
- El G-code no debe enviarse a la máquina hasta validar la simulación y realizar una prueba sobre material descartable.
- El decodificador de coordenadas de `excellon.py` solo admite taladros escritos con punto decimal explícito (`X1.234Y5.678`), que es lo que exporta KiCad. No replica la decodificación de sufijo de ceros (`_decode_coordinate` en `parser.py`) que sí tiene el parser Gerber; un archivo Excellon sin punto decimal (formato con ceros suprimidos, común en exportaciones de otros programas de diseño) se interpretaría con las unidades equivocadas.

## Alcance actual: validado solo contra exportaciones de KiCad

Todo el parser (Gerber y Excellon), la detección automática de archivos de fabricación (`project.py`) y los ejemplos de este documento fueron probados únicamente contra Gerbers RS-274X y Excellon exportados por **KiCad**. El objetivo del proyecto es soportar Gerbers de cualquier programa de diseño de PCB común (Eagle, Altium, EasyEDA, DipTrace, OrCAD, etc.), pero eso todavía no está implementado ni probado. Ver la nueva etapa dedicada a esto en `PLAN.md` ("Etapa 8") para el detalle de tareas pendientes y los riesgos concretos esperados (macros de apertura `%AM`, aperturas de bloque/step-repeat, modo de arco de un solo cuadrante `G74`, convenciones de nombre de archivo específicas de cada herramienta, etc.).
