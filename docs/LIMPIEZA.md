# Limpieza y normalización de los datos

Este documento responde a una duda legítima: si las tablas originales, muy desordenadas, quedaron realmente limpias y normalizadas. La respuesta de la auditoría es que la versión 1.0 limpiaba lo que el score necesitaba, pero dejaba sin tratar varios defectos que no afectaban al tablero y que sí importan para un modelo de datos confiable. La versión 2.0 los corrige, deja un modelo relacional normalizado en `data/processed` y reporta de forma explícita lo que no se puede corregir. Todas las cifras de este documento salen de la última ejecución del pipeline (corte al 25/11/2026) y se regeneran con `python -I eda/generar_documentos.py`.

## Qué estaba mal

Los datos de entrada son exportaciones de Zoho CRM, un libro de asistencia con una hoja por evento y tres libros de encuestas, todos con estructuras distintas. La auditoría encontró lo siguiente.

En el CRM, 21 códigos de empresa repetidos (10 con estados distintos), 2 registros de prueba, 580 celdas con tildes dañadas, 133 registros cuya categoría de membresía contiene un tipo («Empresas», «Consultoras») en lugar de una categoría, 8 empresas con registro Activo y membresía cancelada o expirada, columnas geográficas sin homologar («DC» y «Bogotá, D.C.», «Colomba», «Atlantico»), ciudades con variantes («Bogotá D.C.» como ciudad distinta de «Bogotá»), sectores con espacios dobles y duplicados («ONG» y «Entidades Sin Animo de Lucro»), subsectores con errores de digitación y todas las columnas con nombres que no están estandarizados.

En la asistencia, 33 hojas de evento con 13 estructuras de encabezado distintas, 11.091 filas vacías, 15 inscripciones sin código de empresa que la versión 1.0 descartaba en silencio, nueve formas distintas de escribir la autorización de datos, ciudades escritas a mano y una hoja consolidada (GENERAL) con fórmulas truncadas que reporta 1.285 asistencias cuando las hojas suman 3.292.

En las encuestas, tres estructuras de pregunta incompatibles, fechas en texto en español, calificaciones escritas como «10 (Promoter)», centinelas («sin dato», «n/a», «-») y ciudades con variantes.

## Qué se corrigió

La limpieza ahora es configurable y verificable. Las equivalencias de categorías (ciudades, sectores, niveles, estados, modalidades, líneas de evento, niveles de cargo y otras) salieron del código y viven en `config/homologacion.json`, que el equipo de ACTHO puede editar. El pipeline valida ese archivo al cargarlo y reporta cualquier valor que no esté en un catálogo. Se estandarizaron los nombres de columna, se convirtieron los centinelas en nulos, se tipificaron fechas, enteros, porcentajes y booleanos, se unificaron las hojas de estructura distinta, se leyeron los informes agrupados de Zoho (grupos repetidos, subtotales y «Grand Total») y se construyó un modelo relacional con verificación de integridad referencial. Nada se descarta en silencio: las filas excluidas quedan en `control_rechazos.csv` y los huérfanos en `control_huerfanos.csv`.

## Tabla antes y después por fuente

Cada celda muestra el valor original y el del modelo normalizado. El porcentaje sin dato cuenta nulos y centinelas; baja sobre todo porque se descartan las columnas vacías que dejó la anonimización, los centinelas pasan a nulos reales y se excluyen duplicados y pruebas, no porque se inventen datos.

| Fuente | Filas | Columnas | Celdas nulas | Centinelas | Sin dato | Duplicados por clave | Columnas fuera de snake_case |
|---|---|---|---|---|---|---|---|
| CRM de Zoho | 1.073 a 1.050 | 49 a 29 | 31.147 a 10.953 | 0 a 0 | 59,2 % a 36 % | 21 a 0 | 49 a 0 |
| Asistencia a eventos | 3.401 a 3.386 | 27 a 13 | 8.325 a 5.127 | 176 a 0 | 25,1 % a 11,6 % | 82 a 0 | 0 a 0 |
| Encuestas | 778 a 778 | 92 a 14 | 4.311 a 3.120 | 157 a 0 | 26,9 % a 28,6 % | 0 a 0 | 92 a 0 |

En encuestas el porcentaje sin dato sube porque `fact_encuesta` añade columnas que solo aplican a parte de las respuestas (evento inferido, NPS, afiliado declarado) y los aspectos pasan a `fact_encuesta_aspecto`; no es pérdida de datos. En asistencia las filas «antes» son las no vacías de las hojas; el modelo conserva además marcadas (`es_duplicado`, `es_agendado`) las inscripciones que no cuentan como asistencia, por eso casi no cambia el número de filas.

## Detalle por fuente

### CRM de Zoho (Base de datos de afiliados)

Archivo: `1. Base de datos de afiliados/Base de datos Hackaton_anonimizada.xlsx`. Tablas de destino: `dim_afiliado`, `fact_comunidad_afiliado`, `dim_ejecutiva`. Las columnas del CRM se reparten en dim_afiliado (atributos) y fact_comunidad_afiliado (seis columnas de comunidades pasadas a filas).

| Anomalía | Cantidad | Tratamiento |
|---|---|---|
| Columnas vacías. Columnas completamente vacías (eliminadas por la anonimización: NIT, teléfono, correos y otras). | 13 | Se descartan; quedan 33 columnas útiles. |
| Nombres de columna sin estandarizar. Nombres de columna con mayúsculas, tildes, espacios o etiquetas como «[anonimizado]». | 49 | Se renombran a snake_case sin tildes. |
| Tildes dañadas. Celdas con tildes dañadas por codificación (por ejemplo «Bogotﾃ｡»). | 580 | Se reparan reinterpretando los bytes como UTF-8. |
| Espacios sobrantes. Celdas con espacios al inicio, al final o dobles. | 3 | Se colapsan y se recortan. |
| Registros de prueba. Registros de prueba (etiqueta «Prueba»). | 2 | Se excluyen y se listan en control_rechazos. |
| Códigos de empresa repetidos. Filas con un código de empresa ya usado por otro registro. | 21 | Se conserva un registro por empresa (vigente, con estado, con vencimiento, más completo). |
| Repetidos con estado distinto. Empresas repetidas cuyos registros tienen estados de membresía distintos. | 10 | Se prefiere el registro vigente. |
| Sin estado de membresía. Registros sin estado de membresía. | 73 | Quedan con estado nulo; no se puntúan. |
| Categoría mal digitada. Registros cuya «categoría de membresía» trae un tipo («Empresas», «Consultoras», «Plus»...) en lugar de una categoría. | 133 | Se anula la categoría y el nivel se infiere del tipo de membresía cuando es posible. |
| Estado inconsistente. Empresas con registro Activo pero membresía cancelada, expirada o inactiva. | 8 | Se marcan con bandera; manda el estado de la membresía. |
| Fecha de afiliación imposible. Fechas de afiliación posteriores al corte (año 2066). | 1 | Se descartan (nulo) y se marcan con bandera. |
| Propietario «0». Propietarios con el centinela «0». | 1 | Pasan a «Sin asignar». |
| Booleanos en texto. Celdas Sí/No o true/false escritas como texto. | 1.666 | Se convierten a booleano. |
| Porcentajes en texto. Porcentajes escritos como texto («50%»). | 126 | Se convierten a número de 0 a 100. |
| Contadores en texto. Contadores de comunidades y de miembros guardados como texto. | 810 | Se convierten a entero; las comunidades pasan a filas (fact_comunidad_afiliado). |
| Vigentes con fecha vencida. Afiliados vigentes cuya fecha de expiración ya pasó (dato desactualizado en el CRM, no se corrige). | 41 | Se conservan y se reportan como alerta de captura. |

Valores distintos de cada categoría antes y después de homologar:

| Categoría | Antes | Después |
|---|---|---|
| ciudad | 58 | 39 |
| sector | 37 | 27 |
| subsector | 49 | 43 |
| rango_empleados | 11 | 6 |
| categoria_membresia | 10 | 4 |
| tipo_membresia | 11 | 5 |
| estado_membresia | 6 | 6 |
| region | 9 | 6 |
| departamento | 12 | 11 |
| pais | 4 | 2 |
| ejecutiva | 11 | 10 |
| nivel | 10 | 3 |

### Asistencia a eventos 2026 (34 hojas más GENERAL y HOMOLOGACION)

Archivo: `2. Registros de participación en actividades/BASE ASISTENCIA A EVENTOS 2026 - EAFIT_anonimizada.xlsx`. Tablas de destino: `fact_asistencia`, `dim_evento`, `dim_persona`. «Columnas» antes cuenta los nombres de columna distintos entre todas las hojas; los datos personales eliminados por la anonimización no se cuentan en el perfil.

| Anomalía | Cantidad | Tratamiento |
|---|---|---|
| Hojas con estructura distinta. Hojas de evento con 13 estructuras de encabezado distintas (columnas en otro orden, otro nombre o ausentes). | 33 | Se ubican las columnas por su texto y se unifican en una sola tabla. |
| Hojas con celdas combinadas. Hojas con celdas combinadas (título del evento sobre el encabezado). | 31 | Se localiza el encabezado «ID_EMPRESA» y se descartan las filas previas. |
| Filas vacías. Filas vacías de las hojas (las hojas llegan a 1.000 filas con pocas filas llenas). | 11.091 | Se ignoran. |
| Filas sin código de empresa. Inscripciones con persona pero sin código de empresa. | 15 | Se descartan y se listan una a una en control_rechazos. |
| Totales o encabezados repetidos. Totales o encabezados repetidos mezclados con los datos. | 0 | Se descartan (hoy no hay ninguno). |
| Duplicados persona y evento. Inscripciones repetidas de la misma persona en el mismo evento. | 82 | Se conservan marcadas (es_duplicado) y no cuentan como asistencia. |
| Registros agendados. Registros solo agendados que no asistieron. | 12 | Se conservan marcados (es_agendado) y no cuentan como asistencia. |
| Variantes de autorización. Formas distintas de escribir la autorización de datos (SI, Sí, SÍ, «SÍ, AUTORIZO...»). | 9 | Se convierten a booleano. |
| Nivel de cargo «Sin dato». Niveles de cargo con el centinela «Sin dato». | 176 | Pasan a nulo en el modelo. |
| Costo vacío. Inscripciones sin indicar si fueron con costo o sin costo. | 53 | Quedan nulas. |
| Hoja sin lista de asistentes. Hojas de evento sin lista de asistentes (febrero 13). | 1 | El evento se conserva con tiene_asistentes en falso. |
| GENERAL: rangos truncados. Columnas de la hoja consolidada GENERAL cuya fórmula no cubre todas las filas de su hoja. | 31 | No se usa GENERAL: la asistencia se recuenta hoja por hoja. |
| GENERAL: columnas sin fórmula. Columnas de evento de GENERAL sin fórmula. | 3 | Se recuentan desde las hojas. |
| GENERAL: totales truncados. Sumas de la fila de totales de GENERAL que no cubren todas las empresas listadas. | 36 | Se recalculan desde las hojas. |
| GENERAL: total reportado. Asistencias que reporta GENERAL (frente a las que se cuentan en las hojas). | 1.285 | Se reemplaza por el recuento real: 3292 asistencias válidas. |
| GENERAL: empresas no listadas. Empresas con asistencia real que GENERAL no lista. | 791 | Se incluyen en el recuento desde las hojas. |

Valores distintos de cada categoría antes y después de homologar:

| Categoría | Antes | Después |
|---|---|---|
| nivel_cargo | 7 | 6 |
| autoriza_datos | 9 | 2 |
| ciudad | 36 | 22 |
| linea_evento | 4 | 4 |
| modalidad_evento | 3 | 3 |

### Encuestas de eventos (presencial, virtual y post-evento)

Archivo: `3. Encuestas y NPS/ (tres libros)`. Tablas de destino: `fact_encuesta`, `fact_encuesta_aspecto`, `fact_encuesta_tema`. «Antes» suma los tres libros (55 columnas del post-evento incluidas); «después» es fact_encuesta, con los aspectos y los temas en tablas aparte.

| Anomalía | Cantidad | Tratamiento |
|---|---|---|
| Tres estructuras de encuesta. Tres libros de encuesta con estructuras de pregunta distintas (4 aspectos, 4 aspectos y 7 aspectos más NPS). | 3 | Se unifican en fact_encuesta y los aspectos pasan a filas (fact_encuesta_aspecto). |
| Fechas en texto. Fechas en texto en español de Zoho Survey («oct. 21, 2026 09:22:34 a. m.»). | 778 | Se convierten a fecha. |
| NPS escrito con texto. Calificaciones NPS escritas con texto («10 (Promoter)»). | 41 | Se extrae el número y se clasifica en Promotor, Pasivo o Detractor. |
| Variantes de ciudad. Ciudades escritas a mano con variantes («Bogota», «Bogotá, Bogotá D.C., Colombia»). | 56 | Se homologan; quedan 39 valores distintos. |
| Centinelas en texto. Celdas con centinelas («sin dato», «n/a», «-», «ninguno», «no aplica»). | 157 | Pasan a nulo. |
| Respuestas sin empresa. Respuestas en las que no se pudo identificar la empresa. | 142 | Se conservan con empresa nula. |
| Respuestas sin evento. Respuestas que no se pudieron asignar a un evento 2026 (2025, ambiguas o fuera de ventana). | 474 | Se conservan con evento nulo y el método registrado. |
| Respuestas de 2025. Respuestas de 2025 (la asistencia solo cubre 2026). | 421 | Se conservan para la satisfacción por empresa. |
| Encuesta de 90 días sin respuestas. Respuestas en la encuesta de 90 días. | 0 | Se documenta que no hay datos para el NPS de la asociación. |
| Texto libre excluido. Respuestas con temas solicitados en texto libre (no se publican). | 546 | Se excluyen del modelo por privacidad. |

Valores distintos de cada categoría antes y después de homologar:

| Categoría | Antes | Después |
|---|---|---|
| ciudad | 56 | 39 |
| nivel_cargo (post-evento) | 6 | 6 |

## Informes agrupados de Zoho

Los informes de Zoho escriben cada grupo (mes, propietario, fecha) solo en su primera fila, añaden la cantidad entre paréntesis, dejan filas vacías entre grupos y cierran con «Grand Total». El lector los convierte en tablas tidy y verifica que los registros recuperados coincidan con la cantidad que declara el propio informe y con el conteo de cada grupo.

| Informe | Filas leídas | Vacías | Totales | Encabezados repetidos | Declarados | Recuperados | Coincide |
|---|---|---|---|---|---|---|---|
| Renovaciones de los últimos 2 meses | 25 | 10 | 1 | 0 | 14 | 14 | sí |
| Afiliaciones de los últimos 2 meses | 40 | 25 | 1 | 0 | 14 | 14 | sí |
| Nuevos afiliados de agosto y septiembre | 18 | 2 | 0 | 2 | no declara | 10 | sí |
| Estados de oportunidades ganadas por KAM | 46 | 7 | 0 | 0 | 39 | 39 | sí |
| Informe por segmento Elite y Premium | 89 | 0 | 0 | 0 | 89 | 89 | sí |
| Informe por subsectores | 19 | 0 | 0 | 0 | 19 | 19 | sí |
| Informe de membresías (con subtotales) | 21 | 0 | 7 | 0 | 481 | 481 | sí |
| Base de datos de afiliados ACTHO | 472 | 0 | 0 | 0 | no declara | 472 | sí |
| Consolidado de asistencia por KAM (bloques repetidos) | 600 | 110 | 0 | 0 | 460 | 460 | sí |

## Filas descartadas

| Fuente | Motivo | Filas |
|---|---|---|
| asistencia | sin código de empresa | 15 |
| crm | código repetido: se conservó otro registro de la misma empresa | 21 |
| crm | registro de prueba | 2 |

## Conciliación con los informes que ACTHO usa hoy

Como control independiente, lo limpiado se contrasta con informes que Zoho produce por su cuenta. En cada fila, «Informe» es lo que dice la fuente de contraste y «Pipeline» lo que resulta del modelo.

| Control | Informe | Pipeline | Resultado | Lectura |
|---|---|---|---|---|
| Registros con estado Activo del CRM frente al total del informe de membresías. | 481 | 481 | coincide | El informe se generó el 13 de noviembre; la exportación del CRM es de la misma época. |
| Combinaciones tipo y categoría del informe que coinciden con el recuento del CRM. | 14 | 14 | coincide |  |
| Empresas del informe Elite y Premium que existen en el CRM. | 89 | 89 | coincide |  |
| Empresas del informe cuya categoría en el CRM coincide con la del informe. | 89 | 89 | coincide |  |
| Empresas del informe cuya fecha de expiración coincide con la del CRM. | 89 | 89 | coincide |  |
| Afiliados de la base de ACTHO (472) frente a los vigentes que puntúa el pipeline. | 472 | 466 | difiere | El pipeline puntúa 474 vigentes; 8 no están en la base y 6 de la base no son vigentes en el CRM. |
| Empresas renovadas que existen en el CRM. | 14 | 14 | coincide |  |
| Renovaciones cuya nueva fecha de expiración ya está reflejada en el CRM. | 14 | 14 | coincide |  |
| Oportunidades ganadas cuya empresa existe en el CRM. | 39 | 38 | difiere |  |
| Oportunidades cuya ejecutiva coincide con la del CRM. | 38 | 35 | difiere | Las diferencias suelen ser cuentas reasignadas después de ganar la oportunidad. |
| Afiliaciones recientes cuya empresa existe en el CRM. | 14 | 14 | coincide |  |
| Nuevos afiliados de agosto y septiembre que existen en el CRM. | 10 | 7 | difiere | Los códigos faltantes indican desfase de captura entre el informe y la exportación del CRM. |
| Bloques del consolidado por KAM cuyo resumen coincide con sus filas. | 6 | 6 | coincide |  |
| Empresas del consolidado por KAM cuyo total de asistentes coincide con el recuento del pipeline. | 460 | 183 | difiere | El consolidado por KAM hereda el subconteo de la hoja GENERAL (rangos truncados): las diferencias son del consolidado, no del pipeline. |
| Asistentes que suma el consolidado por KAM frente a los que cuenta el pipeline para las mismas empresas. | 925 | 1.950 | difiere | El pipeline recuenta hoja por hoja y por eso supera al consolidado. |

## Integridad referencial

El modelo tiene 22 tablas, 14.855 filas y 33 relaciones verificadas. Hay 0 filas huérfanas de severidad error y 1.275 de severidad aviso. Los avisos no son defectos de captura: son empresas que asisten, responden o aparecen en informes sin estar en la exportación del CRM, y ciudades escritas a mano que todavía no están en el catálogo. Se reportan todas.

| Relación | Valores distintos | Filas | Severidad |
|---|---|---|---|
| `dim_afiliado.ciudad` | 2 | 4 | aviso |
| `dim_afiliado.ciudad_facturacion` | 2 | 5 | aviso |
| `fact_afiliacion_nueva.empresa_id` | 3 | 3 | aviso |
| `fact_asistencia.ciudad` | 7 | 7 | aviso |
| `fact_asistencia.empresa_id` | 721 | 1.087 | aviso |
| `fact_encuesta.ciudad` | 1 | 1 | aviso |
| `fact_encuesta.empresa_id` | 140 | 167 | aviso |
| `fact_oportunidad_ganada.empresa_id` | 1 | 1 | aviso |

Para resolver los avisos de ciudad basta agregar la variante a `config/homologacion.json`; los de empresa requieren completar el CRM.

## Lo que no se corrige y por qué

Los afiliados vigentes con fecha de expiración vencida (41) son un dato desactualizado del CRM y se reportan como alerta, no se alteran. Las 73 filas sin estado de membresía quedan con estado nulo y no se puntúan. El significado de la marca numérica de la primera columna de las hojas de asistencia no está documentado en la fuente, por lo que se conserva sin interpretarla (`marca_fuente`). Una misma persona figura con más de una empresa en 103 casos, lo que puede ser un cambio de empresa o un código reutilizado en la anonimización; el modelo lo marca (`multiples_empresas`) sin forzar una única empresa. El consolidado por KAM hereda el subconteo de la hoja GENERAL. La asistencia solo cubre 2026 y la encuesta de 90 días no tiene respuestas.

## Cómo mantener la limpieza

Al recibir una exportación nueva, ejecute `python -I run_pipeline.py --estricto`. Si aparecen valores fuera de catálogo, `control_huerfanos.csv` los lista con su cantidad; agréguelos a `config/homologacion.json` (sección `equivalencias` con la clave en minúsculas, sin tildes y con espacios simples) y vuelva a ejecutar. El modo estricto detiene la ejecución solo ante errores de estructura o relaciones rotas. Las figuras de antes y después están en `docs/eda/08_antes_despues.md`.
