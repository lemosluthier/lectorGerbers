# Análisis de factibilidad: módulo G-code sender (Etapa 7)

Este documento evalúa si conviene **construir** un módulo propio de control de
máquina (conexión GRBL/FluidNC, jog, homing, ajuste de cero en Z, sondeo de
superficie y mapa de alturas) dentro de `lector_gerbers`, o **adoptar** una
herramienta existente y dejar que `lectorGerbers` siga enfocado en lo que ya
hace bien: interpretar Gerbers/Excellon y generar G-code de aislamiento y
taladrado correctamente alineado.

Ver la Etapa 7 de [PLAN.md](PLAN.md) para el detalle original de lo que se
había previsto implementar. Este análisis no reemplaza esa etapa, la informa.

## Requisitos que se pidieron evaluar

- Manejar controladoras **GRBL** (clásica, 8/32 bits) y **FluidNC** (firmware
  para ESP32, protocolo compatible con GRBL 1.1 pero configuración por YAML).
- **Jog**: mover los ejes manualmente, con control de paso/avance.
- **Búsqueda de home** (`$H`, requiere finales de carrera cableados).
- **Ajuste de cero en Z** ("touch off") sobre la superficie de la placa.
- Idealmente, **sondeo de superficie** (grilla de puntos con `G38.2`) y
  **mapa de alturas** para compensar el alabeo del cobre durante el
  aislamiento — que es la razón de ser de esta herramienta (grabado de PCB).

## Qué implica construirlo propio

No es "agregar una pantalla más" a la GUI existente: es implementar una capa
completa de control de un dispositivo físico en tiempo real, con las
siguientes piezas, todas necesarias para que sea mínimamente seguro:

1. **Conexión serie** (`pyserial`): detección de puertos COM, conectar/
   desconectar, reconexión ante corte de cable, y correrlo en un hilo aparte
   del hilo de Tkinter (la GUI no puede bloquearse esperando el puerto serie).
2. **Protocolo de streaming de GRBL**: no es "mandar líneas de texto una por
   una". GRBL tiene un buffer de recepción de 127 bytes; hay que implementar
   el método de *character-counting* (contar bytes enviados vs. confirmados
   con `ok`/`error`) para no desbordarlo, más el manejo de bytes de
   tiempo-real que se mandan *fuera* de ese buffer (`?` estado, `!` feed
   hold, `~` resume, `0x18` soft-reset, `0x85` cancelar jog).
3. **Jog**: GRBL 1.1+ tiene un comando `$J=` con su propio mecanismo de
   cancelación; hay que decidir semántica de "click para mover un paso" vs.
   "mantener apretado para mover continuo" y no encolar jogs mientras uno
   está en curso.
4. **Homing**: mandar `$H` y manejar el estado de alarma hasta que se
   complete. Requiere finales de carrera realmente cableados y `$22=1` — algo
   que, como ya marca `PLAN.md`, **no está confirmado en el hardware real**
   todavía.
5. **Ajuste de cero en Z**: jog manual hasta tocar la superficie (o un ciclo
   de sondeo con placa de contacto) y fijar el cero de la pieza (`G10 L20` o
   `G92`).
6. **Sondeo de superficie y mapa de alturas**: definir una grilla sobre el
   área de trabajo, correr `G38.2` en cada punto (con elevación segura entre
   puntos), guardar los Z medidos, interpolar (bilineal como mínimo) entre
   puntos vecinos, y **reprocesar el G-code de aislamiento** para aplicar la
   corrección de Z solo a los movimientos de corte, subdividiendo tramos
   largos para que la interpolación no sea grosera — sin tocar los rápidos ni
   las alturas seguras. Esto ya está identificado como tarea en `PLAN.md`.
7. **Control del trabajo**: iniciar/pausar/continuar/detener con transiciones
   de estado limpias, recuperación de alarmas, manejo de desconexión
   inesperada a mitad de un trabajo.
8. **UX de seguridad**: confirmaciones antes de homing/movimiento, indicación
   visible de alarma, de finales de carrera y del pin de `Probe`.

### El problema real: no es la cantidad de código, es el riesgo y el testing

Casi nada de esto se puede probar con la suite de tests actual (`pytest`
corre en 0.3s sobre fixtures sintéticas, sin hardware). El código de control
en tiempo real solo se valida de verdad con la máquina física conectada — y
un bug ahí no genera "un archivo con un dato mal", genera que la fresa se
estrelle contra la placa, contra un tope mecánico, o que un jog no se
cancele a tiempo. Es exactamente el tipo de código donde "probarlo hasta que
funcione" en la propia placa real es la única validación posible, con el
costo/riesgo que eso implica.

**Estimación aproximada** (orientativa, no un compromiso): una primera
versión funcional de conexión + jog + home + touch-off + sondeo + mapa de
alturas + compensación, escrita desde cero, son varios fines de semana
completos de trabajo enfocado — y eso antes de la etapa de "aparecen bugs de
timing raros que solo se ven con la máquina real", que históricamente es la
parte más larga e impredecible en este tipo de proyectos.

## Alternativa: herramientas existentes

El caso de uso — GRBL/FluidNC + jog + home + touch-off + autolevel para PCB —
**no es nicho**: es exactamente para lo que existen varias herramientas de
código abierto, algunas construidas puntualmente para grabado de PCB.
Estado relevado (2026-09-10):

| Herramienta | Lenguaje/plataforma | Licencia | Último push | FluidNC | Autolevel/heightmap PCB nativo |
|---|---|---|---|---|---|
| **bCNC** | Python (multiplataforma) | GPL-2.0 | 2026-04-15 | **Sí, lo recomienda explícitamente** en su propio README para controladoras de 32 bits | **Sí** — sondeo Z, autolevel alterando el G-code, mapa de colores de altura |
| **Candle** | C++/Qt (Windows/Linux, builds listas) | GPL-3.0 | 2026-08-29 (muy activo) | No documentado; el protocolo de streaming/jog es el mismo que GRBL 1.1 así que debería andar a nivel básico, pero no está confirmado por el proyecto | **Sí** — función de "Height Map" para PCB (nightly builds incluidas) |
| **Universal Gcode Sender (UGS)** | Java (multiplataforma) | GPL-3.0 | 2026-09-10 (el más activo) | **Sí, soporte explícito** (wiki: "GRBL, FluidNC, Smoothieware, g2core, TinyG") | No confirmado como feature nativo — habría que validarlo a mano |
| **OpenCNCPilot** | C#/WPF (solo Windows) | MIT | 2025-04-28 (sin actividad reciente) | No documentado | **Sí, es su feature central** — "probe user-defined areas for warpage and wrap the toolpath around the curved surface", pensado para aislamiento de PCB |
| **CNCjs** | Node.js/web (Electron o navegador) | MIT | activo | No documentado en el core (sí GRBL/Marlin/Smoothieware/TinyG/g2core) | Vía extensión de comunidad (`cncjs-autolevel`), no nativo |
| **WebUI de FluidNC** | Integrada en el propio firmware (ESP32) | — | — | Es FluidNC | Jog y home sí; sondeo/autolevel con flujo de trabajo dedicado, no |

Notas sobre la tabla:
- Los datos de licencia/actividad son de la API de GitHub al momento de
  escribir esto; conviene reconfirmarlos si esta decisión se retoma más
  adelante en el tiempo.
- Usar cualquiera de estas herramientas **como aplicación externa separada**
  (generás el `.nc` con `lectorGerbers`, lo abrís en bCNC/Candle/UGS) no
  genera ninguna obligación de licencia sobre este proyecto — la GPL solo
  importaría si se copiara/vendorizara código de ellas hacia acá.

### Por qué esto inclina la balanza contra "hacerlo propio"

- **bCNC** ya es, hoy, prácticamente el checklist completo de la Etapa 7 en
  un solo programa: Python (mismo lenguaje que este proyecto, reduce la
  barrera si algún día hay que tocarle algo), FluidNC recomendado de forma
  explícita por el propio proyecto, y autolevel/heightmap ya integrado y
  probado por años de uso de la comunidad de grabado de PCB — que es
  exactamente el público de esta herramienta.
- **OpenCNCPilot** demuestra que "sondeo + mapa de alturas + compensación de
  G-code para aislamiento de PCB" es un problema tan común que existe un
  proyecto entero (aunque hoy parado) dedicado nada más que a eso.
- Construir esto de cero significa reimplementar, con recursos de una sola
  persona y sin flota de usuarios reales probándolo, la parte del sistema
  con **mayor riesgo físico** y **menor cobertura de test posible** — para
  terminar, en el mejor de los casos, en un lugar donde estas herramientas
  ya están hoy.

### Dónde sí hay una ventaja real de hacerlo propio

Ninguna de estas herramientas sabe nada de Gerbers, KiCad, ni de la
alineación espejo+origen que ya resuelve `lectorGerbers`. La ventaja genuina
de una integración propia sería mostrar el mapa de alturas sondeado
**superpuesto en la misma vista combinada** que ya tiene la GUI (cobre +
aislamiento + taladrado, ver `gui.py`), en vez de mirarlo en una ventana
aparte. Eso es un problema de **visualización**, no de control de máquina en
tiempo real, y se puede resolver sin tocar una sola línea de protocolo GRBL:
importando el archivo de mapa de alturas que ya exportan estas herramientas
(bCNC guarda el suyo en un formato de texto simple) y dibujándolo como una
capa más del canvas existente.

## Recomendación

1. **No construir un sender/controlador GRBL propio.** El costo (varias
   semanas de desarrollo de la parte más riesgosa del proyecto, sin forma
   realista de testearla sin hardware) no se justifica frente a herramientas
   maduras que ya resuelven exactamente este caso de uso.
2. **Antes de decidir cuál adoptar, probar a mano** (sin escribir código)
   bCNC y Candle contra la controladora FluidNC real, en cuanto esté
   confirmado el modelo/cableado (sigue siendo un prerequisito de la Etapa 7
   original). Es una tarde de trabajo, no un sprint, y saca la decisión del
   terreno teórico.
   - Si bCNC anda bien con FluidNC: es la opción más alineada (Python,
     autolevel nativo, recomendado por el propio proyecto de FluidNC).
   - Si bCNC se siente pesado o con fricción, UGS es la alternativa más
     activamente mantenida con soporte FluidNC confirmado, aunque haya que
     validar su autolevel a mano.
3. **`lectorGerbers` sigue siendo el generador**, no el controlador: su
   trabajo termina en un `.nc` correctamente alineado y simulado, como ya
   hace. Eso es lo que ya está bien resuelto y probado (34 tests) en este
   proyecto, y no lo resuelve ninguna herramienta externa por sí sola.
4. **Integración liviana, más adelante y opcional**: un botón "Abrir en
   bCNC" (o el que se elija) que lance la herramienta externa con el `.nc`
   generado, y/o importar su archivo de mapa de alturas para dibujarlo en la
   vista combinada de la GUI. Ninguna de las dos cosas requiere reimplementar
   el control de la máquina.

## Impacto en la Etapa 7 del plan

Esto reemplaza el enfoque de "implementar `controller.py` propio" que tenía
la Etapa 7. La hoja de arranque de esa etapa en `PLAN.md` queda obsoleta en
ese punto; antes de retomar la Etapa 7 conviene reescribirla con el enfoque
de este análisis (adoptar + integración liviana) en vez del de desarrollo
propio.

Se mantienen sin cambios los prerequisitos de seguridad ya documentados: no
mover la máquina real ni probar sondeo hasta confirmar controladora, versión
de firmware, puerto, cableado de entradas y área útil.
