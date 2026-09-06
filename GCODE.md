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

Cuando se genera G-code, el origen inferior izquierdo se calcula sobre el límite de los recorridos de la herramienta. Esto incluye el offset exterior de aislamiento y evita coordenadas negativas aunque la fresa trabaje fuera del cobre.

Estas transformaciones deberán ser compartidas por el render SVG y el generador G-code para que la vista previa coincida con el mecanizado.

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
- Las pasadas permanecen dentro del área de trabajo.
- El origen y el espejo coinciden con la vista previa.
- Las unidades y profundidades son coherentes.
- El archivo puede simularse visualmente antes de enviarlo al CNC.

## Limitaciones conocidas

- Las aperturas rectangulares y oblongas tienen soporte inicial para flashes; las formas especiales todavía requieren soporte geométrico completo.
- Los arcos Gerber se muestrean como polilíneas para renderizado y aislamiento; todavía falta evaluar la emisión directa como `G2`/`G3`.
- El cálculo de offsets robustos requiere una biblioteca geométrica o un algoritmo específico para uniones, esquinas y regiones complejas.
- El G-code no debe enviarse a la máquina hasta validar la simulación y realizar una prueba sobre material descartable.
