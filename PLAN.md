# Plan de trabajo

## Objetivo

Construir una herramienta en Python para inspeccionar, visualizar y analizar archivos Gerber y Excellon utilizados en la fabricación de placas de circuito impreso.

## Estado actual

- [x] Crear la estructura inicial del paquete Python.
- [x] Incorporar un parser básico de metadatos Gerber.
- [x] Crear la CLI `gerber-info`.
- [x] Agregar pruebas automatizadas iniciales.
- [x] Validar el parser con un archivo Gerber real.
- [x] Interpretar movimientos, trazas y flashes básicos (`D01`, `D02` y `D03`).
- [x] Validar coordenadas negativas y ceros iniciales omitidos con sintaxis de KiCad.
- [x] Exportar trazos básicos a SVG para inspección visual.
- [x] Detectar polaridad y regiones poligonales básicas (`G36`/`G37`).
- [x] Leer herramientas y posiciones básicas de archivos Excellon.
- [x] Interpretar arcos Gerber `G02` y `G03` mediante muestreo geométrico.
- [x] Validar Gerbers y Excellon con el conjunto de muestra `Gerbers/`.
- [x] Combinar una capa Gerber y taladros Excellon en una exportación SVG.
- [x] Conservar el ancho de pistas definido por las aperturas circulares.
- [x] Agregar espejo horizontal para capas Bottom y origen inferior izquierdo.
- [x] Documentar los requisitos de insolado y generación de G-code GRBL.
- [x] Implementar cálculo del ancho efectivo de la fresa cónica.
- [x] Generar la primera pasada de aislamiento fuera del cobre.
- [x] Agregar pasadas múltiples con solapamiento configurable.
- [x] Generar un primer archivo G-code GRBL de prueba.
- [x] Generar G-code de taladrado Excellon con profundidad configurable.
- [x] Simular perforaciones en la vista SVG del G-code.
- [x] Superponer aislamiento y taladrado en una simulación SVG común.
- [x] Crear una interfaz gráfica inicial para seleccionar archivos y parámetros CNC.
- [x] Permitir taladrado con una única herramienta seleccionable.
- [x] Detectar automáticamente archivos de fabricación exportados por KiCad.
- [x] Encender y apagar el husillo con `M3 S` y `M5`.
- [x] Crear una simulación SVG básica del recorrido G-code.
- [x] Resolver el acceso directo al comando `gerber-info` en Windows cuando la carpeta de scripts de Python no está en `PATH`.

### Registro de avances

- 2026-08-27: se creó el paquete inicial con `pyproject.toml`, código en `src/` y pruebas en `tests/`.
- 2026-08-27: `py -m pytest` finaliza correctamente con 2 pruebas exitosas.
- 2026-08-27: la CLI fue ejecutada sobre un Gerber real y detectó unidades `mm`, formato `X4.6/Y4.6` y 14 comandos.
- 2026-08-27: se documentó que `py -m lector_gerbers.cli` es la forma más confiable de ejecutar la herramienta mientras `gerber-info` no esté disponible en el `PATH`.
- 2026-08-27: el parser interpreta coordenadas absolutas, conserva ejes omitidos y genera primitivas `draw` y `flash`.
- 2026-08-27: una capa real de KiCad fue analizada correctamente: 159 comandos, 2 aperturas y 107 elementos geométricos.
- 2026-08-27: se agregó exportación SVG con `py -m lector_gerbers.cli archivo.gbr --svg capa.svg`.
- 2026-08-27: se agregó detección de polaridad (`LPD`/`LPC`) y exportación SVG de regiones.
- 2026-08-27: se agregó el lector Excellon y `py -m lector_gerbers.excellon_cli archivo.drl`.
- 2026-08-27: se agregó soporte de arcos `G02`/`G03` para renderizado y cálculo de aislamiento.
- 2026-08-27: un archivo real de KiCad fue analizado correctamente: 2 herramientas y 5 taladros.
- 2026-08-27: el conjunto `Gerbers/` fue validado: cobre con 263 elementos, contorno con 4, PTH con 25 taladros y NPTH válido sin taladros.
- 2026-08-27: se agregó una vista SVG combinada de Gerber y Excellon mediante la opción `--drill`.
- 2026-08-27: el SVG usa el diámetro real de cada apertura circular para representar el ancho de las pistas.
- 2026-08-27: se agregaron `--mirror-x` y `--origin-lower-left` para preparar el diseño para CNC.
- 2026-08-27: se agregó `gcode-preview` para visualizar movimientos rápidos y de corte antes del mecanizado.
- 2026-08-27: se documentaron en `GCODE.md` los parámetros de la fresa, offsets de aislamiento y estrategia de pasadas múltiples.
- 2026-08-27: se generó `Gerbers/dimmer-bottom-isolation.nc` con tres pasadas para la capa de cobre de muestra.
- 2026-08-27: el origen inferior izquierdo del G-code se ajustó al límite de los recorridos para evitar coordenadas negativas producidas por el offset de aislamiento.
- 2026-08-27: se documentó el estado consolidado, los archivos de salida y las limitaciones conocidas del proyecto.
- 2026-08-27: se instaló el paquete en Python 3.14, `py -m pytest` pasó 15 pruebas y `gerber-info.exe` quedó disponible en `C:\Python314\Scripts`.
- 2026-08-27: se robustecieron los offsets para regiones desconectadas y geometrías inválidas; la suite pasó 16 pruebas y el G-code real se simuló sin coordenadas XY negativas.
- 2026-09-09: se corrigió un bug real en la transformación compartida espejo+origen (`isolation.transform_info`, `drilling._transform_hits`, `svg._transform_point` y el `board_transform` inline de `gui.py`): al combinar `--mirror-x` con `--origin-lower-left` y `--reference-gerber`, se restaba `min_x` dos veces, produciendo coordenadas cercanas a X=-21mm con los Gerbers de muestra reales. Ver el detalle de la fórmula corregida en `GCODE.md`.
- 2026-09-09: se agregó una validación explícita (`ValueError`) en `isolation_paths` y `generate_drilling_gcode` para el caso en que, aun con la transformación correcta, un recorrido o un taladro caiga fuera del contorno de referencia (margen insuficiente entre el cobre y el borde de la placa), en vez de generar coordenadas negativas silenciosamente.
- 2026-09-09: `svg.render_svg`/`render_board` ahora aceptan `reference_bounds`, igual que `isolation.py`/`drilling.py`; `cli.py --svg` lo usa automáticamente junto con `--reference-gerber`.
- 2026-09-09: una revisión de código sobre el fix anterior detectó que `svg.render_board` dimensionaba el canvas con `reference_bounds` pero seguía anclando el dibujo al bounding box del contenido dibujado, no al del marco de referencia; el contenido quedaba mal ubicado dentro del canvas cuando no tocaba los bordes del marco (el caso normal). Se corrigió calculando el ancla a partir de las esquinas transformadas del marco (`min_x`/`max_x`/`min_y`/`max_y`), no de los puntos dibujados. La suite pasó de 31 a 32 pruebas.
- 2026-09-09: la GUI (`gui.py`) ahora permite elegir una carpeta de salida separada de los Gerbers originales (por defecto una subcarpeta `salida-cnc`), y se fusionaron las dos vistas previas (Gerber arriba, G-code abajo) en una única vista superpuesta con checkboxes por capa (contorno, cobre, taladros de diseño, recorrido de aislamiento, taladrado G-code, recorrido rápido, origen (0,0)), zoom con la rueda del mouse centrado en el cursor, paneo con clic y arrastre, y un botón "Centrar vista". De paso se corrigió un bug de encuadre (`_canvas_transform` anclaba el contenido a una esquina en vez de centrarlo) y un problema de layout real: con ventanas de ancho normal (~1200px) la fila de checkboxes + el botón de centrar se salían del área visible y quedaban inalcanzables; se separaron en filas propias. La suite pasó de 32 a 34 pruebas (con `_resolve_output_directory`, la función pura que decide la carpeta de salida).
- 2026-09-10: se hizo un análisis de factibilidad sobre construir un módulo propio de G-code sender (conexión GRBL/FluidNC, jog, home, touch-off, sondeo y mapa de alturas) para la Etapa 7. Conclusión: no conviene desarrollarlo propio — ver [ANALISIS_GCODE_SENDER.md](ANALISIS_GCODE_SENDER.md) y el replanteo de la Etapa 7 más abajo.

## Etapa 1: Base del proyecto

- [x] Confirmar la instalación editable y las dependencias (`shapely`, `pytest`).
- [ ] Configurar el intérprete de Python de VS Code.
- [x] Verificar instalación, pruebas y ejecución de las CLI.
- [x] Documentar el flujo de desarrollo.

**Resultado esperado:** proyecto reproducible y ejecutable desde VS Code.

## Etapa 2: Parser Gerber

- [x] Detectar unidades, formato de coordenadas y polaridad.
- [x] Interpretar comandos `D01`, `D02`, `D03` y `M02`.
- [x] Leer definiciones de aperturas.
- [x] Representar movimientos, trazas, flashes, regiones y arcos muestreados.
- [x] Agregar pruebas con distintos formatos y archivos reales.

**Resultado esperado:** modelo interno confiable de una capa Gerber.

## Etapa 3: Visualización

- [x] Incorporar exportación 2D a SVG.
- [x] Mostrar trazas, pads, regiones, contornos y taladros.
- [ ] Agregar zoom y desplazamiento interactivos.
- [x] Permitir seleccionar archivos mediante la CLI.
- [x] Diferenciar visualmente las capas y movimientos.

**Resultado esperado:** visualizar una capa Gerber de forma clara.

## Etapa 4: Archivos Excellon

- [x] Leer archivos de taladros `.drl`.
- [x] Detectar unidades y formato de coordenadas básicas.
- [x] Interpretar herramientas y diámetros.
- [x] Mostrar los taladros junto con las capas Gerber.

**Resultado esperado:** representar las perforaciones de la placa.

## Etapa 5: Proyecto completo de PCB

- [x] Cargar automáticamente un conjunto de archivos de una placa (`project.discover_fabrication_files`).
- [x] Reconocer extensiones como `.gtl`, `.gbl`, `.gto`, `.gbo`, `.gko` y `.drl` (y `.xln`).
- [x] Asociar nombres de archivo con tipos de capa (por sufijo, ver limitación en Etapa 8: es específico de la convención de KiCad).
- [x] Crear una vista combinada de la placa (`svg.render_board`, usada por la GUI).
- [ ] Exportar la visualización a PNG (hoy solo hay exportación a SVG).

**Resultado esperado:** inspeccionar una placa completa desde sus archivos de fabricación.

Nota (2026-09-09): esta etapa estaba mucho más avanzada de lo que reflejaba este checklist; `project.py` y `render_board` ya cubren la mayor parte desde el commit "Add fabrication file discovery and G-code simulation". Solo falta la exportación a PNG.

## Etapa 6: Calidad y distribución

- Validar archivos inválidos y mostrar mensajes claros.
- Aumentar la cobertura de pruebas.
- Probar con Gerbers de distintos programas de diseño.
- Mejorar la documentación y agregar ejemplos.
- Preparar una versión ejecutable para Windows.

**Resultado esperado:** herramienta estable, documentada y fácil de utilizar.

## Etapa 7: Panel de control CNC y mapa de alturas

> **2026-09-10: replanteada tras un análisis de factibilidad.** Ver
> [ANALISIS_GCODE_SENDER.md](ANALISIS_GCODE_SENDER.md). La conclusión es **no
> desarrollar un sender/controlador GRBL propio**: existen herramientas
> maduras (bCNC, Candle, Universal Gcode Sender) que ya resuelven jog, home,
> touch-off y autolevel/mapa de alturas para PCB, incluyendo soporte
> explícito de FluidNC en al menos dos de ellas. La "Implementación prevista"
> de esta etapa queda como referencia histórica de lo que se había pensado
> construir; el plan de acción vigente es el de la sección "Recomendación"
> del análisis (probar herramientas existentes contra el hardware real antes
> de escribir código, y dejar como mucho una integración liviana — abrir el
> `.nc` generado en la herramienta elegida, o importar su mapa de alturas
> para dibujarlo en la vista combinada de la GUI).

### Objetivo (histórico, ver replanteo arriba)

Agregar a la GUI un panel para conectar una controladora GRBL por USB/serie,
supervisar sus estados y enviar trabajos G-code con controles de seguridad.
Incorporar además un ciclo de sondeo para medir la superficie de la placa y
aplicar la compensación de altura al G-code de aislamiento.

### Dependencias y decisiones pendientes

- Confirmar el modelo de controladora y la versión de GRBL.
- Confirmar el puerto serie y la velocidad de comunicación, normalmente `115200`.
- Confirmar el cableado y la lógica de las entradas `PROBE` y de los finales de carrera.
- Definir el área útil, margen de seguridad y cantidad de puntos de la malla.
- Definir si la compensación se aplicará solo al aislamiento o también al taladrado.

### Implementación prevista

- [ ] Incorporar `pyserial` como dependencia opcional o principal.
- [ ] Crear una capa de comunicación serie independiente de la GUI.
- [ ] Detectar puertos COM y conectar/desconectar de forma segura.
- [ ] Consultar el estado GRBL y mostrar posición, estado, husillo y alarmas.
- [ ] Mostrar indicadores para `Probe`, límite X, límite Y y límite Z.
- [ ] Implementar envío línea por línea esperando `ok` y gestionar `error`/`ALARM`.
- [ ] Agregar controles de iniciar, pausar, continuar, detener y reset.
- [ ] Añadir confirmaciones y bloqueo de acciones ante una alarma.
- [ ] Crear el ciclo de sondeo con movimientos `G38.2` y lectura de la posición Z.
- [ ] Guardar y cargar mapas de alturas asociados a una placa y origen concretos.
- [ ] Mostrar la malla medida en tabla y mapa de colores.
- [ ] Interpolar la altura entre puntos vecinos.
- [ ] Aplicar la compensación solo a movimientos de corte, conservando alturas seguras.
- [ ] Previsualizar el G-code compensado antes de enviarlo.
- [ ] Agregar pruebas unitarias para comunicación simulada, interpolación y compensación.
- [ ] Validar el flujo primero sin herramienta y después sobre material descartable.

**Resultado esperado:** controlar una máquina GRBL desde la aplicación, verificar
los sensores y ejecutar un aislamiento compensado por la inclinación o irregularidad
de la superficie de la placa.

### Estado de avance al 2026-09-03

- [x] Confirmada la viabilidad técnica con la arquitectura actual.
- [x] Identificado que el proyecto ya genera y simula G-code compatible con GRBL.
- [x] Definida la separación prevista entre comunicación, sondeo, mapa y GUI.
- [ ] No implementada todavía la comunicación con una controladora real.
- [ ] No definido todavía el modelo de controladora ni su cableado.
- [ ] No implementado todavía el mapa de alturas ni la compensación.

### Hoja de arranque para la próxima sesión

Para continuar sin volver a analizar el proyecto, seguir este orden:

1. Confirmar únicamente los datos físicos de la máquina: modelo de controladora,
	versión de GRBL, puerto COM, velocidad, área útil y cableado de entradas.
2. Instalar `pyserial` en el entorno editable y agregarlo a `pyproject.toml`.
3. Implementar `controller.py` con conexión, desconexión, consulta de estado,
	envío de una línea y manejo de respuestas.
4. Añadir a la GUI una pestaña de control que permita conectar, consultar estado
	e indicar `Probe`, `X`, `Y` y `Z`, sin ejecutar movimientos automáticamente.
5. Probar la conexión con la máquina detenida y validar las señales de entrada.
6. Implementar el envío controlado de un archivo, con pausa ante `error` o
	`ALARM`, y con botones de pausa, continuar, detener y reset.
7. Implementar el sondeo de una malla pequeña inicial de `3 x 3` puntos,
	manteniendo una altura segura configurable.
8. Guardar el mapa junto con origen, límites, separación y fecha de medición.
9. Implementar interpolación bilineal y aplicar la corrección Z solo a G-code
	de corte, sin modificar rápidos ni alturas seguras.
10. Previsualizar el archivo corregido y ejecutar la primera prueba sin herramienta
	 sobre material descartable.

Valores iniciales previstos para la primera implementación:

- Protocolo: GRBL por USB/serie.
- Velocidad: `115200` baudios.
- Sondeo: `G38.2`.
- Malla inicial: `3 x 3`.
- Compensación: aislamiento únicamente.
- Estado inicial: conexión y lectura, sin movimiento automático.

No se debe enviar movimiento ni probar el sondeo hasta confirmar físicamente la
controladora y el cableado. Esa comprobación es específica de la máquina y no
puede sustituirse de forma segura por una suposición en el plan.

## Etapa 8: Soporte de Gerbers de cualquier programa de diseño (no solo KiCad)

### Objetivo

El objetivo del proyecto es leer Gerbers/Excellon de cualquier programa de diseño
de PCB común (Eagle, Altium, EasyEDA, DipTrace, OrCAD, Fusion 360/Ultraboard,
etc.), no solo de KiCad. Hoy (2026-09-09) el parser, el lector Excellon y la
detección automática de archivos fueron escritos y probados **exclusivamente**
contra exportaciones de KiCad (ver `Gerbers/` y `tests/test_parser.py`). Esta
etapa junta lo que falta para ampliar ese alcance y, sobre todo, los problemas
concretos que hay que resolver o al menos detectar y reportar con un error claro
en vez de fallar en silencio.

### Problemas conocidos a esperar con Gerbers de otros programas

- **Macros de apertura (`%AMxxx*%`)**: `parser._parse_aperture_definitions` solo
  entiende aperturas estándar (`C`, `R`, `O`, `RoundRect`). Pads con forma
  personalizada definidos con macro de apertura (frecuentes en exportaciones de
  Eagle/Altium para relieves térmicos o pads especiales) no se reconocen: el
  flash cae al ancho por defecto (0.15mm circular), lo que produce geometría de
  cobre y aislamiento incorrectos sin ningún aviso.
- **Aperturas de bloque y step-repeat (`%AB`, `%SR`)**: no están implementadas.
  Se usan para paneles o arreglos repetidos en algunos flujos de fabricación.
- **Modo de arco de un solo cuadrante (`G74`)**: `parser._parse_primitives`
  siempre interpreta los offsets `I`/`J` como si estuviera en modo multi-cuadrante
  (`G75`, el que usa KiCad). Un Gerber que use `G74` (todavía emitido por algunas
  herramientas más viejas) generaría arcos con el barrido equivocado.
- **Identificación de capas por nombre de archivo**: `project.py`
  (`_COPPER_SUFFIXES`, `_REFERENCE_SUFFIXES`) reconoce específicamente los
  sufijos de KiCad (`_F_Cu`, `_B_Cu`, `_Edge_Cuts`, `_GKO`). Otros programas usan
  convenciones totalmente distintas (Eagle: `.cmp`/`.sol`, Altium: nombres
  configurables por el usuario, EasyEDA: `Gerber_TopLayer.GTL`). La forma
  correcta y agnóstica de la herramienta es leer los atributos Gerber X2
  (`%TF.FileFunction,Copper,...*%`, `%TO.P*%`), que hoy se ignoran por completo.
- **Formato de coordenadas Excellon**: `excellon._HIT_RE` solo admite taladros
  con punto decimal explícito. Herramientas que exportan Excellon con supresión
  de ceros y sin punto decimal (común fuera de KiCad) se leerían con las
  unidades equivocadas sin ningún error.
- **Detección de unidades y formato Gerber**: `parser.inspect_file` solo busca
  `%MOMM*%`/`%MOIN*%` y un `%FS` con modo absoluto (`A`) y el patrón exacto
  `X##Y##`. Un archivo con modo incremental o con la información de formato en
  otro lugar hace que `format_match` sea `None` y el archivo se procese como si
  no tuviera geometría (0 primitivas), sin levantar ningún error que indique
  "formato no soportado".

### Tareas pendientes

- [ ] Conseguir/generar un conjunto de Gerbers de muestra de al menos dos
      programas de diseño distintos de KiCad (por ejemplo Eagle y EasyEDA) para
      usar como fixtures de test, igual que se hizo con `Gerbers/` para KiCad.
- [ ] Reemplazar (o complementar) la identificación de capas por sufijo de
      nombre de archivo en `project.py` con lectura de atributos Gerber X2
      (`%TF.FileFunction%`), manteniendo el sufijo como respaldo.
- [ ] Soportar el modo de arco de un solo cuadrante (`G74`) además del actual
      (`G75`).
- [ ] Detectar y reportar con un error explícito (no en silencio) los casos no
      soportados: macros de apertura, aperturas de bloque/step-repeat, formato
      `%FS` no reconocido.
- [ ] Extender `excellon.py` para decodificar coordenadas con supresión de
      ceros sin punto decimal, reutilizando la lógica de `_decode_coordinate`.
- [ ] Agregar pruebas automatizadas por cada programa de diseño soportado.

**Resultado esperado:** poder analizar y generar aislamiento/taladrado a partir
de Gerbers de cualquier programa de diseño de PCB común, o recibir un error
claro indicando qué construcción del archivo no está soportada todavía.

## Próximo paso concreto

Confirmar el modelo de controladora GRBL, su versión, el esquema de entradas y el
área útil. Luego implementar primero la conexión serie y la lectura de estados sin
permitir aún el movimiento automático de la máquina.

La Etapa 8 (soporte de Gerbers de otros programas de diseño) es independiente de
la Etapa 7 (control GRBL) y puede avanzarse en paralelo sin ningún riesgo de
mover la máquina física.
