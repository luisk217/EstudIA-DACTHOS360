# Arquitectura

Este documento explica cómo está construido DACTHO 360, por qué se tomaron las decisiones principales y qué alternativas se descartaron. Está dirigido a quien deba mantener o ampliar el sistema. El detalle de cada paso del pipeline está en `docs/PIPELINE.md`.

## Flujo general

El sistema tiene tres etapas que se ejecutan en orden y se comunican solo mediante archivos. Primero, un pipeline en Python lee las exportaciones de ACTHO. Segundo, ese pipeline escribe tablas intermedias en CSV y siete archivos JSON. Tercero, un frontend estático lee los JSON y los presenta.

```
Excel (CRM, asistencia, encuestas, renovaciones)
        |
        v
  pipeline/ (Python)  ->  data/processed/*.csv   (auditoría, no se publica)
        |
        v
  web/data/*.json
        |
        v
  web/ (HTML, CSS, JS)  ->  reglas de alerta en localStorage del navegador
```

La separación importa por una razón práctica. El pipeline se ejecuta pocas veces, cuando llegan datos nuevos, y puede tardar el tiempo que necesite. El frontend se ejecuta muchas veces, en el equipo de cada persona, y no debe hacer más que leer archivos pequeños (en total, los JSON pesan unos 444 KB). Como el único contrato entre ambos son los JSON, cada parte puede cambiar sin tocar la otra mientras los campos se mantengan.

## Fuentes

Las nueve fuentes declaradas en `pipeline/config.py` son el CRM de Zoho, el libro de asistencia a eventos, los consolidados por KAM, las tres encuestas de eventos (presenciales, virtuales y post-evento), el instrumento de la encuesta de 90 días, el informe de renovaciones y el de nuevos afiliados. La clave que une todas las fuentes es el código de empresa (`EMP-0000`), que reemplazó al NIT en la anonimización. Cuando una fila no trae ese código, no se une; el pipeline lo reporta como aviso de calidad en lugar de intentar adivinarlo.

Un detalle de diseño: el pipeline lee los libros como datos y nunca evalúa su contenido. Se recomienda ejecutarlo con `python -I`, que impide que Python cargue módulos desde la carpeta actual, para que un archivo mal nombrado en esa carpeta no se ejecute por accidente.

## El pipeline

Los módulos de `pipeline/` siguen el orden del flujo. `carga.py` lee los Excel sin transformarlos y audita la hoja consolidada de asistencia. `limpieza.py` contiene funciones puras de normalización (texto, fechas, niveles, NPS), fáciles de probar de forma aislada. `integracion.py` limpia cada fuente, consolida el CRM a una fila por empresa, recorre las 34 hojas de evento y asigna cada respuesta de encuesta a un evento cuando la fecha y la modalidad lo permiten. `features.py` calcula las variables de cada afiliado a una fecha de referencia, y `score.py` las convierte en puntos, riesgo, salud, banda y lista de factores. `validacion.py` contrasta el score con las salidas históricas. `exportacion.py` escribe los archivos, y `orquestador.py` encadena todo y genera los avisos de calidad.

El cálculo de variables acepta una fecha de referencia distinta por empresa. Esa decisión permite reutilizar exactamente el mismo código en la validación retrospectiva, donde cada empresa que salió se mide a la fecha de su expiración, y en el cálculo normal, donde todas se miden al corte. Así evitamos mantener dos versiones de la lógica que podrían divergir.

El score es deliberadamente sencillo. Suma puntos por señales (vencimiento, participación, satisfacción, antigüedad, nivel, ejecutiva sin asignar, ausencia de comunidades), los divide por el máximo posible, que es 76 con los pesos actuales, y asigna una banda con dos umbrales. Todos los números viven en `config/pesos_score.json`. Elegimos un modelo aditivo y no un clasificador entrenado por tres motivos: hay solo 33 salidas observables, un modelo aprendido con tan pocos casos sería inestable; el equipo comercial necesita ver por qué un afiliado aparece en rojo; y las reglas de negocio de ACTHO pueden cambiar los pesos sin pedir ayuda técnica.

## El frontend

El tablero es un sitio estático con módulos ES nativos. `main.js` define las siete rutas y un enrutador por hash (`#/resumen`, `#/afiliados?banda=Riesgo alto`), de modo que cada vista tiene un enlace directo. `datos.js` carga los JSON, `reglas.js` contiene el motor de alertas y cada archivo de `js/vistas/` construye una vista. Los gráficos son SVG y CSS escritos en `graficos.js`, sin librerías. El diseño responde a pantallas de escritorio y móviles, ofrece tema claro y oscuro, y distingue las bandas por nombre, símbolo y trama además del color.

Las reglas de alerta son la única parte con estado del lado del usuario. Se evalúan en el navegador sobre los afiliados ya cargados y se guardan en `localStorage` bajo la clave `dactho360.reglas.v1` (si existe la clave antigua `dacho360.reglas.v1`, su contenido se migra una vez). Una regla tiene nombre, severidad, ámbito opcional (una ejecutiva) y una lista de condiciones unidas por Y u O, donde la Y tiene precedencia. Como no hay servidor, no existe un lugar compartido donde guardarlas; por eso se pueden exportar e importar como JSON.

## Decisiones y alternativas descartadas

**Power BI.** Fue la primera alternativa considerada, porque ACTHO ya conoce el entorno de Microsoft. La descartamos porque compartir un tablero con el equipo exige que cada persona inicie sesión con una cuenta de la organización y tenga licencia, y porque la publicación abierta de Power BI no ofrece control sobre quién ve datos de afiliados. Además, un reporte de ese tipo no permite que cada usuario defina reglas con condiciones libres y las exporte sin construir una solución adicional. Un sitio estático puede abrirse con solo un enlace, o incluso desde un USB en una reunión, sin cuentas ni licencias.

**Una aplicación con servidor y base de datos.** Habría permitido compartir reglas entre usuarios y guardar historial, pero requiere hospedaje, mantenimiento, copias de seguridad, autenticación y un responsable técnico permanente. Para una primera versión cuyo objetivo es demostrar el valor del cruce de datos, ese costo no se justifica. El plan de evolución en `docs/MANTENIMIENTO.md` describe cuándo y cómo daría sentido dar ese paso.

**Hojas de cálculo con fórmulas.** Es lo que ACTHO hace hoy y de ahí vienen los problemas que el pipeline corrige: la hoja consolidada tiene rangos truncados que subestiman la asistencia, y cada encuesta usa su propio formato. Un pipeline con pruebas deja las reglas de limpieza escritas, repetibles y revisables.

**Un modelo de aprendizaje automático.** Se descartó por la razón explicada arriba. No excluimos que se pueda probar más adelante, cuando haya más de un año de asistencia y más salidas, pero hoy un modelo opaco daría una falsa sensación de precisión.

**Marcos de JavaScript y librerías de gráficos.** Habrían acortado algunas tareas, pero añaden un paso de compilación, dependencias que se desactualizan y llamadas a servicios externos. Sin ellas, el tablero funciona con cualquier servidor de archivos y no depende de que un tercero siga publicando un paquete.

## Escalabilidad

El tablero carga todos los afiliados en memoria y filtra en el navegador. Con 474 afiliados el rendimiento no es un problema, y con unos pocos miles de filas seguiría siendo cómodo, pues `afiliados.json` pesa hoy menos de 400 KB. Más allá de eso, habría que paginar desde un servidor o dividir los JSON. El pipeline, que usa `pandas`, procesa los libros actuales en segundos y escala sin cambios a varios años de histórico. El límite más probable no es técnico sino de datos: la calidad de la captura de la asistencia y de las encuestas determina cuánto puede decir el score, con independencia del tamaño de la cartera.

## Sostenibilidad con costo cero

Todos los componentes funcionan sin pagar licencias ni hospedaje. Python, pandas, openpyxl y numpy son software libre. El sitio puede publicarse en GitHub Pages o Netlify con sus planes gratuitos, o incluso servirse desde un computador de la oficina. No hay claves de API, cuentas de servicio ni cobros por uso. La sostenibilidad se apoya además en tres decisiones: pocas dependencias, todas estables; pesos y umbrales en un archivo de configuración legible; y una documentación que permite a una persona con conocimientos básicos de Python repetir la actualización cada mes. El costo real es el tiempo de esa persona, y el costo de cuidar los datos, que se trata en `docs/GUIA_DESPLIEGUE.md`.

## Pruebas y reproducibilidad

El repositorio incluye 20 pruebas con datos sintéticos que cubren la limpieza, la integración y el score, y se ejecutan con `python -m pytest`. La fecha de corte es un parámetro explícito, y la validación usa una semilla fija (2026) para el intervalo de confianza del AUC, de modo que los resultados se repiten. Los reportes de `docs/eda/` se regeneran con `python -I eda/run_eda.py` a partir del mismo pipeline, lo que evita que la documentación y el tablero muestren cifras distintas.
