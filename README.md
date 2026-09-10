# Lector Gerbers

Proyecto Python para inspeccionar y visualizar archivos Gerber de placas de circuito impreso.

El estado y la hoja de ruta del proyecto están documentados en [PLAN.md](PLAN.md). Los requisitos técnicos del futuro G-code están en [GCODE.md](GCODE.md). El análisis de factibilidad sobre el control de la máquina (GRBL/FluidNC, jog, home, sondeo y mapa de alturas) está en [ANALISIS_GCODE_SENDER.md](ANALISIS_GCODE_SENDER.md).

## Requisitos

- Python 3.11 o superior

## Instalación de desarrollo

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -e ".[test]"
```

## Uso

La forma recomendada de ejecutarlo en Windows es:

```powershell
py -m lector_gerbers.cli ruta\a\capa.gbr
```

Para abrir la interfaz gráfica:

```powershell
gerber-cnc-gui
```

La interfaz permite seleccionar el cobre, `Edge_Cuts` y los taladros Excellon, configurar aislamiento y perforación, generar ambos G-code y crear la simulación SVG superpuesta. El campo `Diametro unico` permite usar una sola broca para todos los agujeros; esto evita cambios de herramienta, pero solo es correcto si esa broca es adecuada para todos los diámetros requeridos.

El campo `Carpeta de salida` indica dónde se guardan `isolation-gui.nc`, `drilling-gui.nc` y `board-simulation-gui.svg`. Si se deja vacío, se usa automáticamente una subcarpeta `salida-cnc` junto al Gerber de cobre (se crea sola si no existe), para no mezclar los archivos generados con los Gerbers originales; también se puede elegir cualquier otra carpeta con "Examinar". Al usar "Cargar carpeta KiCad" se sugiere `salida-cnc` dentro de esa carpeta si el campo todavía está vacío.

Al generar, la ventana muestra una única vista combinada a la derecha con checkboxes para superponer o esconder cada capa: contorno, cobre, taladros de diseño, recorrido de aislamiento, taladrado G-code, recorrido rápido y el origen de coordenadas (0,0). Al usar la misma escala y posición para todo, se puede verificar de un vistazo que el recorrido de aislamiento efectivamente rodea el cobre y que cada taladro del G-code (anillo rojo) cae sobre su pad de diseño (círculo amarillo).

La vista tiene autozoom (se reencuadra sola al generar un trabajo nuevo o redimensionar la ventana), y además zoom y paneo manuales: rueda del mouse para acercar/alejar centrado en el cursor, clic izquierdo y arrastrar para desplazarse, y el botón "Centrar vista" para volver al encuadre automático.

También puede cargarse directamente la carpeta de fabricación exportada por KiCad con `Cargar carpeta KiCad`. Se reconocen capas como `F_Cu`, `B_Cu`, `Edge_Cuts`, archivos `.drl` y `.xln`; se selecciona automáticamente `PTH` como archivo principal de taladros y se dejan disponibles los campos para corregir la selección.

También existe el comando `gerber-info`, aunque puede requerir agregar la carpeta de scripts de Python al `PATH` del sistema.

La herramienta informa el nombre del archivo, unidades, formato de coordenadas, aperturas declaradas, cantidad de comandos y elementos geométricos. Interpreta movimientos, trazos, flashes, regiones y arcos básicos (`D02`, `D01`, `D03`, `G36`, `G37`, `G02` y `G03`). También detecta polaridad oscura o clara y conserva las dimensiones de las aperturas. Los archivos Gerber son de solo lectura.

Para exportar la geometría interpretada a un archivo SVG:

```powershell
py -m lector_gerbers.cli ruta\a\capa.gbr --svg capa.svg
```

El SVG puede abrirse directamente en un navegador. La geometría oscura aparece en rojo y la clara en celeste sobre un fondo oscuro.

Para inspeccionar un archivo Excellon de taladros:

```powershell
py -m lector_gerbers.excellon_cli ruta\a\taladros.drl
```

La herramienta informa las unidades, herramientas y cantidad de taladros encontrados.

Para generar G-code GRBL de taladrado con profundidad configurable:

```powershell
py -m lector_gerbers.excellon_cli Gerbers\Dimmer-PTH.drl `
	--gcode Gerbers\dimmer-drilling.nc `
	--depth 1.6 --safe-z 2.0 --plunge-rate 50 `
	--spindle-speed 10000 --origin-lower-left --tool-change
```

`--depth` es obligatoria y se expresa en milímetros. `--tool-change` inserta una pausa `M0` entre herramientas para realizar el cambio manual. La profundidad de ejemplo debe ajustarse al espesor real de la placa y verificarse antes de mecanizar.

Para simular las perforaciones generadas:

```powershell
py -m lector_gerbers.simulation_cli Gerbers\dimmer-drilling.nc `
	--svg Gerbers\dimmer-drilling-simulation.svg
```

La simulación muestra los desplazamientos rápidos en gris y cada perforación en amarillo.

Para superponer el aislamiento y el taladrado en una vista definitiva, ambos archivos deben generarse con el mismo espejo, origen y límites de un Gerber de referencia. Usar `--mirror-x --origin-lower-left --reference-gerber Gerbers\Dimmer-Edge_Cuts.gbr` en ambos comandos:

```powershell
py -m lector_gerbers.simulation_cli `
	Gerbers\dimmer-bottom-isolation-aligned.nc `
	Gerbers\dimmer-drilling-aligned.nc `
	--svg Gerbers\dimmer-board-simulation.svg
```

El resultado combina el aislamiento en rojo, los movimientos rápidos en gris y las perforaciones en amarillo.

Si el margen entre el cobre y el borde de la placa de referencia es menor que el offset de la fresa, `--gcode` falla con un error explícito en vez de generar coordenadas fuera del área de trabajo; en ese caso hay que agrandar el contorno de referencia o generar el aislamiento sin `--reference-gerber`.

## Estado actual

El parser Gerber y el lector Excellon fueron probados con archivos sintéticos y **archivos reales de KiCad únicamente**. Actualmente reconstruye trazos, flashes, regiones y arcos muestreados con coordenadas absolutas, incluyendo coordenadas negativas y ejes omitidos. También conserva las dimensiones de aperturas circulares, rectangulares y oblongas.

El objetivo del proyecto es soportar Gerbers de cualquier programa de diseño de PCB común (Eagle, Altium, EasyEDA, DipTrace, OrCAD, etc.), pero eso todavía no está implementado ni probado: la detección de capas por nombre de archivo, el parser de aperturas y el lector Excellon usan supuestos específicos de KiCad. El detalle de qué falta y los problemas concretos esperados con otros programas está en la Etapa 8 de [PLAN.md](PLAN.md).

## Pruebas

```powershell
py -m pytest
```

## Versión portable para Windows

La GUI usa Tkinter, incluido normalmente con Python, y no necesita un servidor web. Para crear un ejecutable en una máquina de desarrollo:

```powershell
py -m pip install pyinstaller
pyinstaller --onefile --windowed --name GerberCNC src\lector_gerbers\gui.py
```

Para conservar los imports del paquete, empaquetar el lanzador incluido en el proyecto:

```powershell
pyinstaller --onefile --windowed --name GerberCNC --paths src gerber_cnc_gui.py
```

El ejecutable quedará en `dist\GerberCNC.exe`. Debe probarse en otra PC antes de distribuirlo.

## Archivos de muestra

La carpeta `Gerbers/` contiene un conjunto real de fabricación para probar el proyecto:

- `Dimmer-B_Cu.gbr`: capa de cobre con 263 elementos geométricos.
- `Dimmer-Edge_Cuts.gbr`: contorno de placa con 4 elementos geométricos.
- `Dimmer-PTH.drl`: archivo Excellon con 6 herramientas y 25 taladros.
- `Dimmer-NPTH.drl`: archivo Excellon válido sin taladros no metalizados.

Para analizar todas las capas Gerber desde PowerShell:

```powershell
Get-ChildItem Gerbers -Filter *.gbr | ForEach-Object { py -m lector_gerbers.cli $_.FullName }
```

Para analizar los taladros:

```powershell
Get-ChildItem Gerbers -Filter *.drl | ForEach-Object { py -m lector_gerbers.excellon_cli $_.FullName }
```

Para exportar una capa Gerber junto con los taladros a una vista común:

```powershell
py -m lector_gerbers.cli Gerbers\Dimmer-B_Cu.gbr --drill Gerbers\Dimmer-PTH.drl --drill Gerbers\Dimmer-NPTH.drl --svg Gerbers\dimmer.svg
```

La vista combinada usa los trazos de la capa y círculos con el diámetro de cada taladro.

Para generar un primer archivo G-code de aislamiento:

```powershell
py -m lector_gerbers.cli Gerbers\Dimmer-B_Cu.gbr `
	--gcode Gerbers\dimmer-bottom-isolation.nc `
	--tip-width 0.2 --cone-angle 60 --cut-depth 0.1 `
	--passes 3 --overlap 0.5 --clearance 0.1 `
	--spindle-speed 12000 `
	--mirror-x --origin-lower-left
```

El archivo generado debe simularse y verificarse antes de enviarlo al CNC. Los valores del ejemplo son demostrativos y deben ajustarse a la herramienta, material y máquina reales.

Para visualizar el recorrido generado:

```powershell
py -m lector_gerbers.simulation_cli Gerbers\dimmer-bottom-isolation.nc --svg Gerbers\dimmer-bottom-simulation.svg
```

En la simulación, los movimientos rápidos aparecen en gris y los movimientos de corte en rojo.

Para preparar una capa Bottom para el CNC, espejando X y colocando el origen en el vértice inferior izquierdo:

```powershell
py -m lector_gerbers.cli Gerbers\Dimmer-B_Cu.gbr `
	--drill Gerbers\Dimmer-PTH.drl `
	--svg Gerbers\dimmer-bottom.svg `
	--mirror-x --origin-lower-left
```

`--mirror-x` refleja izquierda/derecha y `--origin-lower-left` traslada todo el conjunto al origen `(0, 0)`.

## Archivos generados

Las salidas de ejemplo se guardan en `Gerbers/`:

- `dimmer-board.svg`: vista combinada sin transformación.
- `dimmer-bottom.svg`: vista Bottom espejada y trasladada.
- `dimmer-bottom-isolation.nc`: G-code GRBL de aislamiento.
- `dimmer-bottom-simulation.svg`: simulación visual del G-code.
- `dimmer-board-simulation.svg`: simulación superpuesta de aislamiento y taladrado.

## Próximos pasos

El detalle de las etapas pendientes está en [PLAN.md](PLAN.md). La próxima tarea es validar el G-code mediante simulación y mejorar la robustez de los offsets para geometrías complejas.
