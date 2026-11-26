# DACTHO 360, frontend

Sitio estático (HTML, CSS y JavaScript con módulos ES). No requiere Node ni paso de compilación y no depende de servicios externos: las fuentes (Source Sans 3 y Fraunces) están en `fonts/` y los gráficos usan **Chart.js 4.5.1** (licencia MIT) servido localmente desde `vendor/chartjs/`, de modo que funciona igual en GitHub Pages sin CDN. No hay telemetría ni peticiones a otros dominios.

## Cómo ejecutarlo

Desde esta carpeta:

```
python -m http.server 8000
```

y abrir http://localhost:8000. No funciona con `file://` porque el navegador bloquea la lectura de los JSON. Todas las rutas son relativas, así que el sitio funciona en una subcarpeta (por ejemplo `https://luisk217.github.io/EstudIA-DACTHOS360/`) y el enrutador por hash (`#/resumen`) no necesita configuración del servidor.

Nota para desarrollo: `python -m http.server` permite que el navegador guarde en caché los módulos JS; si no ve un cambio, recargue con Ctrl+F5.

## Estructura

- `index.html`: estructura base, metadatos (Open Graph, favicon) y carga de la biblioteca de gráficos y los módulos.
- `css/tokens.css`: tokens (colores claro y oscuro, tipografía, espaciado, sombras, vidrio, textura y fondo). `css/app.css`: componentes y diseño responsive.
- `js/main.js`: tema, menú, enrutador por hash y esqueleto de carga.
- `js/datos.js`: carga de `data/*.json` (y `data/tendencias.json` si existe), bandas, tramos de vencimiento y fechas de referencia leídas de `meta.json`.
- `js/filtros.js`: estado de filtros compartido, sincronización con la URL, barra de filtros y chips.
- `js/analitica.js`: resúmenes de cartera, series mensuales, regresión lineal, media móvil y variaciones.
- `js/charts.js`: modelos de gráficos con Chart.js (líneas y áreas con tendencia, barras agrupadas y apiladas, dona y torta, radar, dispersión), patrones de relleno y complementos propios.
- `js/widgets.js`: sparklines, medidores (anillo y semicírculo), mapa de calor, tarjetas de gráfico, selector segmentado y esqueletos. `js/iconos.js`: iconografía SVG propia.
- `js/reglas.js`: motor de alertas (campos, operadores, Y/O, plantillas, persistencia, importar y exportar).
- `js/componentes.js`, `js/graficos.js`, `js/ficha.js`, `js/util.js`: piezas compartidas.
- `js/vistas/`: una vista por archivo (resumen, afiliados, ejecutivas, eventos, encuestas, alertas, metodologia).
- `vendor/chartjs/`: `chart.umd.min.js` (208 KB, unos 70 KB comprimido), `LICENSE.md` y `LEEME.txt` con el origen y la huella de integridad.
- `img/`: vista previa para redes (`og-dactho360.png`) e íconos PNG. `favicon.svg`: ícono del sitio.
- `data/`: JSON generados por el pipeline (no editar a mano).
- `tests/reglas.test.html`: pruebas del motor de reglas (74 casos). Ábrala desde el servidor local en `/tests/reglas.test.html`.

## Filtros e interacción

Cada vista muestra los filtros que le aplican (ejecutiva, nivel, estado, banda, tipo, sector, ciudad, tramo y rango de días a vencimiento, periodo de fechas, línea y modalidad de evento, y búsqueda en Afiliados). Los filtros son **globales**: se conservan al cambiar de vista, actualizan en vivo los indicadores, gráficos y tablas, se muestran como chips (con botón para quitar cada uno y «Limpiar filtros») y se reflejan en la URL, por ejemplo `#/resumen?banda=Riesgo alto&ejecutiva=KAM B`. El botón «Copiar enlace» comparte la vista con sus filtros.

Interacción cruzada: al hacer clic en un segmento de dona o torta, una barra, un mes o una celda del mapa de calor se activa el filtro correspondiente (otro clic lo quita). Los gráficos de una dimensión ignoran su propio filtro para resaltar la selección y atenuar el resto. En la dispersión de Afiliados, el clic en un punto abre la ficha. Cada gráfico tiene bajo él «Ver los datos en una tabla», una alternativa accesible con los mismos valores y, en los gráficos que filtran, botones para aplicar el filtro por teclado.

Alcance de cada filtro: los de cartera actúan sobre los 474 afiliados vigentes; el periodo (desde y hasta) acota las series mensuales y los eventos; línea y modalidad actúan sobre los eventos. El NPS post-evento, el resumen de personas y empresas distintas y la distribución por nivel de cargo son datos globales y no cambian con los filtros (cada tarjeta lo indica).

## Series mensuales (`data/tendencias.json`)

Si existe `data/tendencias.json` (lo genera el pipeline) se usa para las series de asistentes, empresas únicas, satisfacción, afiliaciones, vencimientos y salidas; admite filas por mes (`meses: [{mes, asistentes, empresas, satisfaccion, afiliaciones_vigentes, vencimientos, salidas}]`) y otras formas equivalentes (ver `normalizarTendencias` en `js/datos.js`). Si no existe o no se reconoce, las series se calculan en el navegador a partir de `afiliados.json`, `eventos.json` y `encuestas.json`. Con filtros de cartera activos, las series de afiliaciones y vencimientos se recalculan desde la lista filtrada. Las fechas de corte y del último evento se leen de `meta.json` y los eventos; ninguna vista las escribe a mano.

## Alertas

Las reglas se guardan en `localStorage` de este navegador; no hay servidor, así que no se comparten ni se sincronizan. Use «Exportar reglas (JSON)» e «Importar reglas (JSON)» para respaldarlas o moverlas. En la primera visita se siembran tres plantillas activas.

Claves de almacenamiento: `dactho360.reglas.v1` (reglas) y `dactho360.tema` (tema). Si existen las claves de versiones anteriores (`dacho360.reglas.v1`, `dacho360.tema`), su contenido se migra automáticamente una sola vez y la clave antigua se elimina. El formato de exportación pasó a `dactho360-reglas`; la importación sigue aceptando el antiguo `dacho360-reglas`.

## Accesibilidad y diseño

Tema automático, claro u oscuro (botón del menú; también `?tema=claro|oscuro`); el modo oscuro tiene fondo con degradado y textura, tarjetas de vidrio esmerilado y elevación. Las bandas y series se distinguen por nombre, símbolo, forma de punto, trama de relleno, etiquetas con valor y porcentaje, no solo por color. Las animaciones son sutiles y se desactivan con `prefers-reduced-motion`. Navegación por teclado, enlace de salto, diálogos nativos `<dialog>`, regiones en vivo para avisos y descripciones textuales de cada gráfico. Diseño responsive de 375 px a pantalla grande. No se usa `innerHTML`: todo el DOM se construye con `h()`/`svgEl()`, que insertan texto como nodos de texto.

## Capturas

`docs/capturas/` contiene capturas de escritorio y móvil en tema claro y oscuro (`escritorio-<vista>[-oscuro].png`, `movil-<vista>[-oscuro].png`).
