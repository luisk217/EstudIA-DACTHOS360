# Mantenimiento

Este documento reúne lo que necesita saber la persona que cuide DACTHO 360 después de la entrega: cómo ajustar el score, cómo incorporar fuentes nuevas, qué rutina seguir cada mes, qué límites tiene el modelo y cómo evolucionaría el sistema si ACTHO quisiera alertas compartidas entre usuarios.

## Ajustar los pesos del score

Todos los puntos y umbrales están en `config/pesos_score.json`. El archivo se puede editar con cualquier editor de texto y no exige tocar código. Después de cada cambio se ejecuta de nuevo `python -I run_pipeline.py`, que recalcula el score de todos los afiliados, regenera los JSON y vuelve a correr la validación con los pesos nuevos.

El archivo se organiza por grupos de señales. En `bandas`, `umbral_atencion` (35) y `umbral_riesgo_alto` (55) fijan los cortes entre Saludable, Atención y Riesgo alto sobre la escala de 0 a 100. En `vencimiento` se define cuántos puntos suma cada tramo de días a la expiración, desde 22 para una cuenta vencida hasta 0 para las que vencen en más de 180 días, y 8 si no hay fecha. En `participacion` están los puntos por no tener asistencia en el último trimestre registrado (12) o en el año (10), por una sola asistencia (4) y por depender de una sola persona de la empresa (4), además de dos parámetros que reducen a la mitad esas señales para afiliados con menos de 90 días. En `satisfaccion` se fijan los umbrales de promedio (4,0 y 4,5) y los puntos que suman. `antiguedad`, `nivel`, `ejecutiva` y `comunidad` completan el cuadro, y `renovacion_reciente` define cuántos puntos resta haber renovado en los últimos dos meses.

El riesgo de cada afiliado es la suma de sus puntos dividida entre el máximo posible, que el código calcula a partir del propio archivo. Con los pesos actuales es 76. Eso implica que, si se sube un peso, los demás pierden importancia relativa aunque no se hayan tocado, y que un cambio en un grupo mueve los umbrales de banda de forma indirecta. Por eso recomendamos modificar un solo grupo a la vez y comparar antes y después el número de afiliados en cada banda, que aparece en el resumen y en `web/data/resumen.json`.

Recomendamos tres precauciones. La primera, antes de cambiar nada, guardar una copia del archivo y anotar la fecha y el motivo en el `CHANGELOG.md`; el campo `version` del JSON se muestra en la vista de metodología, así que conviene incrementarlo. La segunda, no ajustar los pesos para que la validación mejore: con 33 salidas, es muy fácil acabar con un score que se adapta al ruido de esta muestra y no sirve para el futuro. Y la tercera, recordar que los umbrales actuales se escogieron para que la lista de riesgo alto sea manejable en una semana de trabajo comercial, no por un criterio estadístico. Si el equipo tiene más o menos capacidad de atención, los umbrales son la perilla correcta.

Solo se pueden cambiar los números existentes. Añadir una señal nueva, por ejemplo la mora en el pago, implica editar `pipeline/features.py` para calcular la variable, `pipeline/score.py` para convertirla en factor (con su texto y su acción sugerida, y su inclusión en `maximo_posible`) y el JSON de pesos. Las pruebas de `tests/test_score.py` sirven de ejemplo de cómo comprobarlo.

## Agregar fuentes

Incorporar una fuente nueva sigue el mismo camino que las actuales. Se declara su ruta relativa en el diccionario `FUENTES` de `pipeline/config.py`. Se escribe una función de lectura en `pipeline/carga.py`, que debe leer el archivo sin transformar su contenido y registrar lo que encuentre. Se limpia e integra en `pipeline/integracion.py`, donde la regla de oro es unir siempre por el código de empresa y reportar, en lugar de corregir en silencio, lo que no se pueda unir. En `pipeline/orquestador.py` se llama a esas funciones y se añaden los avisos de calidad pertinentes. Si la fuente aporta variables, se calculan en `features.py` y, si cambian el score, se declaran en `score.py` y en el JSON de pesos. Por último, se exponen los campos necesarios en `pipeline/exportacion.py` y se muestran en la vista correspondiente de `web/js/vistas/`.

Para el campo nuevo en las reglas de alerta, se añade una entrada al catálogo `campos()` de `web/js/reglas.js`, indicando su tipo (numérico, de lista o booleano). Desde ese momento aparece en el editor de reglas.

Dos candidatas naturales son la encuesta de 90 días, cuyo instrumento ya está cargado pero no tiene respuestas, y el registro de pagos o mora, que hoy no está en las fuentes. Cualquier fuente que traiga datos de personas, como nombres o correos, debe pasar por la revisión de protección de datos descrita en `docs/GUIA_DESPLIEGUE.md` antes de que sus campos lleguen a los JSON.

## Rutina de actualización

Cada mes proponemos seguir estos pasos, en este orden. Se exportan los archivos nuevos y se reemplazan en la carpeta de datos. Se ejecuta `python -m pytest` si hubo cambios de código. Se corre el pipeline con la fecha de corte nueva y se lee la salida del registro en busca de advertencias; la hoja sin encabezado de febrero 13, por ejemplo, genera una advertencia conocida. Se abre el tablero en local y se revisa la tabla de avisos de calidad de la vista de metodología, comparándola con la del mes anterior. Se contrastan los afiliados vigentes con el total del informe del CRM. Si todo cuadra, se regeneran los reportes con `python -I eda/run_eda.py`, se actualizan los textos con fechas fijas mencionados en la guía de despliegue, se anota el cambio en `CHANGELOG.md` y se publica la carpeta `web/`.

Cada tres a seis meses vale la pena una revisión más profunda: ver si la validación sigue mostrando una asociación similar, si cambió la proporción de afiliados sin asistencia o sin encuesta, y si los pesos todavía reflejan cómo ACTHO entiende el riesgo.

## Límites del modelo

Los límites de lo que el tablero puede afirmar están documentados en la vista de metodología y los resumimos aquí porque determinan cómo se debe usar.

El AUC de 0,77 (intervalo de 95 % de 0,69 a 0,85) mide asociación con salidas históricas, no capacidad de anticipar salidas futuras. La muestra tiene solo 33 empresas que salieron entre abril y noviembre de 2026. Quienes renovaron pierden la fecha de vencimiento anterior en el CRM y no sirven como casos negativos comparables. No se conoce la fecha real de cancelación, y se usa la de expiración. La asistencia solo existe desde enero de 2026, así que el comportamiento anterior a esa fecha es invisible. Y la validación excluye las señales de vencimiento, ejecutiva y comunidad: la primera por circularidad, y las otras dos porque la cuenta se reasigna a «Sin asignar» cuando se cancela. Por lo tanto, la validación no evalúa el score completo que ve el equipo comercial. La diferencia entre terciles bajo y medio (2,4 % y 3,0 %) no es concluyente; la separación evidente es la del tercil alto (14,2 %).

La satisfacción se apoya en pocos datos. Solo el 33,1 % de los afiliados tiene alguna respuesta de encuesta, solo el 4,9 % tiene una calificación de recomendación y el NPS post-evento (85,4) proviene de 41 respuestas sin detractores, de modo que no puede leerse como el NPS de la asociación. Las encuestas no identifican el evento: el pipeline lo infiere por modalidad y fecha, y de 778 respuestas solo asigna 304. El nivel Conectar casi no discrimina (AUC 0,45), de modo que su peso pequeño responde a un criterio de negocio y no a la evidencia.

La participación reciente se mide hasta el 27 de octubre, último evento del libro, y puede estar subestimada. Las reglas de alerta se evalúan sobre el corte cargado y no consideran movimientos ocurridos después. Y el score no sustituye el conocimiento de la ejecutiva sobre su cuenta, que incluye información, como una conversación reciente, que ninguna fuente contiene.

## Plan de evolución: alertas compartidas

Hoy las reglas viven en el navegador de cada persona. Es una decisión consciente que mantiene el costo en cero, pero tiene consecuencias: no hay reglas comunes del equipo, no hay historial de cuándo se activó una alerta, no se registra quién la atendió y las reglas se pierden al borrar los datos del sitio. Si ACTHO comprueba que el tablero se usa y que esas carencias duelen, el siguiente paso sería un backend con base de datos. Lo planteamos en etapas, para que cada una aporte valor por sí sola.

En una primera etapa se mantiene el sitio estático y se añade un servicio pequeño, por ejemplo una API en Python con una base PostgreSQL o SQLite, que guarda las reglas y las devuelve al tablero en lugar de `localStorage`. Con eso las reglas pasan a ser del equipo, y la exportación a JSON queda como respaldo. Esta etapa exige autenticación (cada persona con su cuenta), porque quien edite reglas compartidas debe estar identificado, y un lugar de hospedaje con copia de seguridad.

En una segunda etapa se guarda en esa base el resultado de cada ejecución del pipeline, con la fecha, y se registran las alertas generadas y su gestión: quién las vio, qué se hizo y con qué resultado. Esto permite medir lo que hoy no se puede, como cuántas alertas llevaron a una renovación, y con ese historial se vuelve posible validar el score contra resultados reales en lugar de salidas pasadas con las limitaciones descritas.

En una tercera etapa el pipeline se programa para ejecutarse solo, leyendo directamente de Zoho mediante su interfaz de programación en lugar de exportaciones manuales, y se evalúa si, con suficiente historia, un modelo estadístico mejora al score aditivo. Si se llegara a ese punto, el modelo aditivo debería conservarse como línea base y como forma de explicar cada decisión.

Cada etapa trae costos que hoy no existen: hospedaje, seguridad, mantenimiento y una persona responsable. Antes de emprender cualquiera, conviene confirmar con el equipo comercial que el uso actual justifica la inversión, y volver a evaluar los requisitos de protección de datos, pues una base de datos con historial de gestión sobre empresas y personas amplía las obligaciones descritas en la guía de despliegue.
