# Pipeline de datos DACTHO 360

Este documento describe cómo ejecutar el pipeline, qué hace cada paso, las decisiones tomadas y los supuestos que condicionan la lectura de los resultados.

## Ejecución

El proyecto requiere Python 3.11 o superior. Para ejecutar solo el pipeline bastan `pandas`, `openpyxl` y `numpy` (`requirements.txt`). Para las pruebas y los reportes de análisis exploratorio se añaden `pytest`, `matplotlib` y `pypdf` (`requirements-dev.txt`).

```
pip install -r requirements-dev.txt
python -I run_pipeline.py                      # genera web/data/*.json y el modelo en data/processed/*.csv
python -I run_pipeline.py --estricto           # además falla si el modelo tiene errores de integridad
python -I run_pipeline.py --fecha-corte 2026-11-25 --datos "ruta/a/Recursos ACTHO"
python -I eda/run_eda.py                       # genera docs/eda/*.md y figuras
python -I eda/generar_documentos.py            # regenera docs/LIMPIEZA.md y docs/DICCIONARIO_DATOS.md
python -m pytest                               # pruebas con datos sintéticos
```

La carpeta de datos crudos se toma de `Material & Recursos/Recursos ACTHO` o de la variable de entorno `ACTHO_DATA_DIR`. Los archivos fuente están excluidos del control de versiones por `.gitignore`. La fecha de corte por defecto es el 25 de noviembre de 2026, que es la de los informes de Zoho entregados; no se usa la fecha del sistema para que los resultados sean reproducibles.

## Estructura

| Módulo | Responsabilidad |
|---|---|
| `pipeline/config.py` | Rutas, ventanas de análisis y carga validada del diccionario de homologación |
| `pipeline/carga.py` | Lectura de las fuentes Excel sin transformar contenido; auditoría de la hoja GENERAL |
| `pipeline/limpieza.py` | Funciones puras de normalización (texto, fechas, niveles, NPS) |
| `pipeline/integracion.py` | Limpieza por fuente, consolidación del CRM, asignación de encuestas a eventos, tasa de cruce |
| `pipeline/features.py` | Variables por afiliado a una fecha de referencia |
| `pipeline/score.py` | Score explicable y bandas |
| `pipeline/validacion.py` | Validación retrospectiva contra salidas históricas |
| `pipeline/exportacion.py` | CSV intermedios y JSON del frontend |
| `pipeline/orquestador.py` | Encadena todo y genera los avisos de calidad |
| `pipeline/esquema.py` | Esquema del modelo relacional (única fuente de verdad) |
| `pipeline/modelo.py` | Construcción de las tablas dim_* y fact_* |
| `pipeline/calidad.py` | Auditoría antes y después, anomalías y conciliación con informes de Zoho |
| `config/pesos_score.json` | Pesos y umbrales del score, editables sin tocar código |
| `config/homologacion.json` | Diccionario de categorías (ciudades, sectores, niveles, estados...), editable sin tocar código |

Los archivos se leen solo como datos: nunca se evalúa ni ejecuta su contenido, y se recomienda lanzar Python con la opción `-I`.

## Modelo de datos

La clave de unión es el código de empresa (`EMP-0000`). Corresponde a «Nombre de Empresa» en el CRM, a `ID_EMPRESA` en cada hoja de asistencia y en las encuestas. El NIT fue eliminado en la anonimización y no se intenta reidentificar nada.

El modelo integrado tiene una fila por afiliado vigente con atributos del CRM, variables de asistencia y encuestas, score y factores. Las tablas auxiliares son los eventos (catálogo con línea 2027, modalidad, asistentes y satisfacción), las asistencias (una fila por persona y evento), las respuestas de encuesta (con evento inferido y método de inferencia) y los agregados de encuestas por modalidad, línea, mes y nivel de afiliado.

Con corte al 25 de noviembre de 2026 el pipeline obtiene 474 afiliados vigentes. El 78,3% se cruza con al menos una asistencia de 2026 (21,7% sin cruce), el 33,1% con al menos una respuesta de encuesta (66,9% sin cruce) y el 20,9% no aparece en ninguna de las dos fuentes. Solo el 4,9% tiene una respuesta con NPS.

## Decisiones principales

El CRM se consolida a una fila por empresa. De los 21 códigos repetidos, 10 tienen estados distintos; se conserva el registro vigente y, a igualdad, el que tiene estado, fecha de expiración y más campos completos. Se excluyen las filas con etiqueta de prueba. Un afiliado es vigente si su estado de membresía es Activo, Periodo de Gracia o Pronto a Expirar; Cancelado, Expirado e Inactivo cuentan como salidas históricas y las filas sin estado no se puntúan.

Las tildes dañadas del CRM (por ejemplo `Bogotﾃ｡`) se reparan reinterpretando los bytes como UTF-8. Ciudades, sectores, tipos de membresía y rangos de empleados se unifican por clave sin tildes ni mayúsculas. Los niveles Estándar, Premium y Elite de Zoho se presentan como Conectar, Crecer y Liderar.

La asistencia se obtiene recorriendo las 34 hojas de evento por nombre de columna, sin depender de la hoja GENERAL, cuyos rangos de COUNTIFS están truncados y que omite una columna de evento. El pipeline cuenta 3.292 asistencias válidas (3.386 inscripciones menos 82 repetidos de persona y evento y 12 registros agendados), de las cuales 2.238 son de empresas del CRM. La cifra de aproximadamente 2.170 del documento de solución es coherente con esta última. La hoja de febrero 13 no trae lista de inscritos.

Las encuestas sí traen el código de empresa en la mayoría de los casos, pero ninguna trae el evento. Se asigna cada respuesta al evento 2026 compatible por modalidad más cercano en los dos días posteriores a su fecha; si dos eventos coinciden, la respuesta queda ambigua. De 778 respuestas, 304 se asignan a un evento; 421 son de 2025 y las demás son ambiguas o caen fuera de ventana. Por eso la satisfacción se informa por segmento (modalidad, línea, mes, nivel de afiliado) además de por evento. El NPS post-evento reproduce los valores esperados: 35 promotores, 6 pasivos y ningún detractor sobre 41 respuestas, NPS de 85,4. La encuesta de 90 días no tiene respuestas.

## Score de salud y riesgo

El riesgo suma puntos por señales y se divide por el máximo posible (76 con los pesos actuales) para quedar entre 0 y 100. La salud es 100 menos el riesgo. Los grupos de señales son vencimiento (hasta 22 puntos), participación (hasta 22), satisfacción y NPS (hasta 15), antigüedad e historial (hasta 6), nivel (hasta 2), ejecutiva sin asignar (6) y ausencia de comunidades (3). Una renovación en los últimos dos meses resta 6 puntos. Cada afiliado conserva la lista de factores con sus puntos y un texto en español, y una acción sugerida derivada del factor principal.

Las bandas son Saludable (riesgo menor a 35), Atención (de 35 a menos de 55) y Riesgo alto (55 o más). Con los pesos actuales resultan 205 afiliados saludables, 209 en atención y 60 en riesgo alto. Los umbrales se fijaron para que la lista roja sea atendible en una semana; no se obtuvieron de un ajuste estadístico y se pueden cambiar en `config/pesos_score.json`.

La ausencia de datos de satisfacción no suma puntos, porque solo un tercio de los afiliados tiene respuestas y se penalizaría por no haber sido encuestado. Los afiliados con menos de 90 días ven reducidas a la mitad las señales de ausencia de participación. La ventana reciente de 90 días termina en el último evento del libro (27 de octubre de 2026) y no en la fecha de corte, para no clasificar como inactivos a quienes simplemente no tuvieron eventos en noviembre.

## Calidad del score

Se aplicó el score, sin las señales de vencimiento, ejecutiva y comunidad, a 33 empresas que salieron con fecha de expiración entre abril y noviembre de 2026 y a los 474 vigentes. El AUC es 0,77 con intervalo de 95% de 0,69 a 0,85. Por terciles de riesgo, salieron 2,4% (bajo), 3,0% (medio) y 14,2% (alto). La señal más informativa es la participación: el 33% de los que salieron tenía alguna asistencia registrada frente al 78% de los vigentes.

Esta prueba mide asociación, no capacidad predictiva demostrada. Quienes renovaron pierden su fecha de vencimiento anterior y no sirven como casos negativos del mismo momento; la asistencia solo existe desde enero de 2026; no se conoce la fecha real de cancelación y se usa la de expiración; y son pocos los casos de salida. Se excluyeron vencimiento (circular), ejecutiva (las cuentas canceladas se reasignan a «Sin asignar») y comunidad (estado actual). El nivel Conectar no discrimina (AUC 0,45), por lo que su peso es bajo y de criterio de negocio. Se recomienda recalibrar cuando existan historiales de asistencia de más de un año.

## Salidas para el frontend

El pipeline escribe en `web/data` siete archivos JSON, cada uno pensado para una vista: `meta.json`, `resumen.json`, `afiliados.json`, `eventos.json`, `ejecutivas.json`, `encuestas.json` y `segmentos.json`. Las fechas son cadenas `AAAA-MM-DD`, los valores ausentes son `null` y no hay datos personales: solo códigos de empresa anonimizados. Los campos se describen en el informe de entrega y se pueden inspeccionar en los propios archivos.

## Supuestos y límites

El corte es el 25 de noviembre de 2026. Los eventos de varios días (Semana del Talento y el evento de julio) usan su fecha de fin del calendario. Las respuestas con asignación de empresa por dominio de correo se aceptan, pero su método queda registrado. El libro de asistencia no incluye eventos posteriores al 27 de octubre, lo que limita la medición de participación reciente. Tres códigos de empresa del informe de nuevos afiliados no están en el CRM, lo que indica desfase de captura. Todo lo que se publique debe mantenerse en cifras agregadas o códigos anonimizados, de acuerdo con el acuerdo de confidencialidad del reto.

## Recomendaciones de captura

Pedir el código o NIT de la empresa en todas las inscripciones y encuestas, incluir el nombre del evento en cada encuesta, usar una única plantilla de asistencia con encabezados fijos y fechas en un solo formato, no reasignar a «Sin asignar» las cuentas canceladas sin conservar la ejecutiva anterior, y activar la encuesta de 90 días para medir el NPS de la asociación.

## Mejoras v2

La versión 2.0.0 refuerza la limpieza y deja un modelo relacional documentado. El detalle con cifras está en `docs/LIMPIEZA.md` y el diccionario de datos en `docs/DICCIONARIO_DATOS.md`.

**Homologación editable.** Los mapeos de categorías ya no están en el código: viven en `config/homologacion.json`, con un catálogo y unas equivalencias por sección. El archivo se valida al cargarlo (claves normalizadas, destinos dentro del catálogo) y un valor sin homologar se reporta en lugar de pasar inadvertido.

**Limpieza reforzada.** Se estandarizan nombres de columna, se convierten los centinelas («N/A», «-», «sin dato», errores de Excel, fechas 1900 y 9999) en nulos, se tipifican fechas, enteros, porcentajes y booleanos, y se homologan país, departamento, región, tamaño, subsector, estado del registro, modalidad, línea, nivel de cargo y autorización de datos. Se detectan y cuentan filas vacías, totales mezclados con datos y encabezados repetidos; las filas descartadas se listan en `control_rechazos.csv`. Los informes agrupados de Zoho, las hojas de asistencia de estructura distinta, los títulos en celdas combinadas y los bloques repetidos del consolidado por KAM se leen con un lector común que verifica los conteos declarados.

**Modelo relacional.** `data/processed` contiene 22 tablas (8 catálogos, 4 dimensiones y 10 hechos, entre ellas `dim_afiliado`, `dim_evento`, `dim_ejecutiva`, `fact_asistencia` y `fact_encuesta`) y cuatro tablas de control. Las tablas anchas de la v1 pasaron a `data/processed/intermedias/`. En el modelo los centinelas internos («Sin dato», «Sin estado») son nulos reales; el JSON del tablero sigue mostrándolos como antes.

**Integridad referencial.** `pipeline/validacion.py` verifica columnas, tipos, claves primarias, rangos, reglas de negocio y las 33 claves foráneas. Los huérfanos se listan en `control_huerfanos.csv` con su severidad: las empresas que no están en el CRM son avisos explicados y no se rellenan con filas inventadas; cualquier otra relación rota es un error (con `--estricto` detiene la ejecución).

**JSON del tablero.** Los siete archivos conservan todos sus campos (una prueba compara contra la v1) y `meta.json` añade `homologacion`, `modelo`, `integridad` y `calidad`. Nuevo `web/data/tendencias.json`: serie mensual contigua desde 2024-01 con asistentes, personas, empresas, satisfacción, NPS, afiliaciones, vencimientos, salidas y renovaciones, fechas reales de los eventos, cobertura por serie (`null` significa fuera de cobertura) y totales que cuadran con los demás archivos.

**Pruebas.** 211 pruebas nuevas cubren cada regla de limpieza, los lectores de Excel con libros sintéticos, el modelo, la integridad referencial, el contrato de los JSON, las tendencias y la coherencia del diccionario.
