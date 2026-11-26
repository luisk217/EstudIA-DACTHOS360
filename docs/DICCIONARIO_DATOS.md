# Diccionario de datos del modelo normalizado

Este documento describe las tablas que el pipeline deja en `data/processed` (versión 2.0.0). El modelo sigue un esquema de dimensiones y hechos: una entidad por tabla, formato tidy (una fila por observación, sin columnas que esconden valores), claves foráneas consistentes y nombres de columna en `snake_case` sin tildes ni espacios. Las tablas se generan desde `pipeline/esquema.py`, que es la única fuente de verdad: si el esquema cambia, este documento se regenera con `python -I eda/generar_documentos.py` y una prueba automática verifica que ambos coincidan.

## Convenciones

Las fechas se escriben `AAAA-MM-DD`. Los booleanos son `True` o `False` y los valores ausentes quedan vacíos (nulos reales): los marcadores como «Sin dato», «N/A» o «-» se convierten en nulo y no aparecen en el modelo. Las claves son códigos anonimizados legibles: `EMP-0000` para empresas, `P-00000` para personas, `EV01` para eventos y `EJ-A` para ejecutivas. Los catálogos (`dim_nivel`, `dim_ciudad`, etc.) salen de `config/homologacion.json`, por lo que un valor que no esté en el catálogo se reporta como huérfano en lugar de pasar inadvertido.

## Relaciones

```
dim_ejecutiva 1---* dim_afiliado 1---* fact_comunidad_afiliado
dim_afiliado  1---* fact_asistencia *---1 dim_evento
dim_afiliado  1---* fact_encuesta   *---1 dim_evento (nulo si no se pudo asignar)
dim_persona   1---* fact_asistencia, fact_encuesta, dim_afiliado.persona_principal_id
fact_encuesta 1---* fact_encuesta_aspecto, fact_encuesta_tema
dim_afiliado  1---* fact_renovacion, fact_afiliacion_nueva, fact_oportunidad_ganada, fact_score_afiliado
fact_score_afiliado 1---* fact_score_factor
dim_nivel, dim_estado_membresia, dim_tipo_membresia, dim_sector, dim_ciudad, dim_modalidad, dim_linea_evento, dim_nivel_cargo: catálogos
```

Las claves foráneas hacia `dim_afiliado` (empresas) tienen severidad «aviso»: la asistencia, las encuestas y algunos informes incluyen empresas que no están en el CRM (no afiliadas o aún no cargadas). Esos casos no se ocultan ni se inventan filas para ellos: quedan listados en `control_huerfanos.csv`. Las demás relaciones deben cumplirse sin excepción, y la verificación falla si no es así.

## Resumen de tablas

| Tabla | Clase | Grano | Clave primaria |
|---|---|---|---|
| `dim_nivel` | catalogo | un nivel | `nivel` |
| `dim_estado_membresia` | catalogo | un estado | `estado_membresia` |
| `dim_tipo_membresia` | catalogo | un tipo | `tipo_membresia` |
| `dim_sector` | catalogo | un sector | `sector` |
| `dim_ciudad` | catalogo | una ciudad | `ciudad` |
| `dim_modalidad` | catalogo | una modalidad | `modalidad` |
| `dim_linea_evento` | catalogo | una línea o formato | `linea` |
| `dim_nivel_cargo` | catalogo | un nivel de cargo | `nivel_cargo` |
| `dim_ejecutiva` | dimension | una ejecutiva | `ejecutiva_id` |
| `dim_afiliado` | dimension | una empresa del CRM | `empresa_id` |
| `dim_persona` | dimension | una persona | `persona_id` |
| `dim_evento` | dimension | un evento | `evento_id` |
| `fact_asistencia` | hecho | una inscripción de una persona a un evento | `asistencia_id` |
| `fact_encuesta` | hecho | una respuesta de encuesta | `respuesta_id` |
| `fact_encuesta_aspecto` | hecho | un aspecto de una respuesta | `respuesta_id`, `aspecto` |
| `fact_encuesta_tema` | hecho | un tema marcado en una respuesta | `respuesta_id`, `tema` |
| `fact_comunidad_afiliado` | hecho | una empresa en una comunidad | `empresa_id`, `comunidad` |
| `fact_renovacion` | hecho | una renovación | `renovacion_id` |
| `fact_afiliacion_nueva` | hecho | una afiliación nueva | `afiliacion_id` |
| `fact_oportunidad_ganada` | hecho | una oportunidad ganada | `oportunidad_id` |
| `fact_score_afiliado` | hecho | un afiliado vigente | `empresa_id` |
| `fact_score_factor` | hecho | un factor de un afiliado | `empresa_id`, `orden` |

## Tablas de control

| Tabla | Contenido |
|---|---|
| `control_rechazos` | Filas de las fuentes que se descartaron, con su ubicación y motivo (pruebas, duplicados del CRM, filas sin código de empresa). |
| `control_huerfanos` | Valores de clave foránea que no existen en la tabla padre, con la cantidad de filas afectadas y su severidad. |
| `control_integridad` | Una fila por relación entre tablas: filas del hijo, nulos, huérfanas y severidad. |
| `control_calidad` | Métricas antes y después de la limpieza por fuente: filas, columnas, nulos, duplicados y anomalías corregidas. |

## Detalle por tabla

<!-- inicio:esquema -->
### `dim_nivel`

Niveles de la oferta 2027 y su equivalente en las categorías de Zoho. Grano: un nivel. Clave primaria: `nivel`. Fuente: config/homologacion.json (niveles).

| Columna | Tipo | Nulos | Descripción | Relación o dominio |
|---|---|---|---|---|
| `nivel` | texto | no | Nivel 2027 (Conectar, Crecer o Liderar). |  |
| `categoria_zoho` | texto | no | Categoría que usa Zoho CRM para ese nivel. |  |
| `orden` | entero | no | Orden de menor a mayor nivel. |  |
| `descripcion` | texto | no | Descripción del nivel. |  |

### `dim_estado_membresia`

Estados de la membresía en Zoho y si cuentan como afiliación vigente. Grano: un estado. Clave primaria: `estado_membresia`. Fuente: config/homologacion.json (estados_membresia).

| Columna | Tipo | Nulos | Descripción | Relación o dominio |
|---|---|---|---|---|
| `estado_membresia` | texto | no | Estado de la membresía. |  |
| `es_vigente` | booleano | no | Verdadero si el estado cuenta como afiliado vigente (Activo, Periodo de Gracia, Pronto a Expirar). |  |
| `orden` | entero | no | Orden de presentación. |  |

### `dim_tipo_membresia`

Tipos de afiliado (Empresa, Consultora, Persona natural, Universidad, Estudiante). Grano: un tipo. Clave primaria: `tipo_membresia`. Fuente: config/homologacion.json (tipos_membresia).

| Columna | Tipo | Nulos | Descripción | Relación o dominio |
|---|---|---|---|---|
| `tipo_membresia` | texto | no | Tipo de afiliado homologado. |  |

### `dim_sector`

Sectores económicos homologados. Grano: un sector. Clave primaria: `sector`. Fuente: config/homologacion.json (sectores).

| Columna | Tipo | Nulos | Descripción | Relación o dominio |
|---|---|---|---|---|
| `sector` | texto | no | Sector económico homologado. |  |

### `dim_ciudad`

Ciudades homologadas (sin tildes dañadas ni variantes de escritura). Grano: una ciudad. Clave primaria: `ciudad`. Fuente: config/homologacion.json (ciudades).

| Columna | Tipo | Nulos | Descripción | Relación o dominio |
|---|---|---|---|---|
| `ciudad` | texto | no | Nombre canónico de la ciudad. |  |

### `dim_modalidad`

Modalidades de los eventos. Grano: una modalidad. Clave primaria: `modalidad`. Fuente: config/homologacion.json (modalidades).

| Columna | Tipo | Nulos | Descripción | Relación o dominio |
|---|---|---|---|---|
| `modalidad` | texto | no | Presencial, Virtual o Híbrido. |  |

### `dim_linea_evento`

Líneas de la oferta 2027 y formatos transversales a los que se homologan los eventos. Grano: una línea o formato. Clave primaria: `linea`. Fuente: config/homologacion.json (lineas_evento).

| Columna | Tipo | Nulos | Descripción | Relación o dominio |
|---|---|---|---|---|
| `linea` | texto | no | Línea o formato. |  |
| `tipo` | texto | no | «linea» o «formato transversal». | Valores: linea, formato transversal |
| `descripcion` | texto | no | Descripción. |  |

### `dim_nivel_cargo`

Niveles de cargo de las personas que asisten. Grano: un nivel de cargo. Clave primaria: `nivel_cargo`. Fuente: config/homologacion.json (niveles_cargo).

| Columna | Tipo | Nulos | Descripción | Relación o dominio |
|---|---|---|---|---|
| `nivel_cargo` | texto | no | Nivel de cargo homologado. |  |
| `orden` | entero | no | Orden de mayor a menor jerarquía. |  |

### `dim_ejecutiva`

Ejecutivas de cuenta (KAM) anonimizadas, más la etiqueta «Sin asignar». Grano: una ejecutiva. Clave primaria: `ejecutiva_id`. Fuente: CRM, informes de renovaciones, afiliaciones y oportunidades.

| Columna | Tipo | Nulos | Descripción | Relación o dominio |
|---|---|---|---|---|
| `ejecutiva_id` | texto | no | Identificador (EJ-A, EJ-B... o EJ-SIN_ASIGNAR). |  |
| `ejecutiva` | texto | no | Etiqueta anonimizada de la ejecutiva (KAM A...). |  |
| `es_asignada` | booleano | no | Falso para «Sin asignar» (cuentas sin ejecutiva o canceladas que se reasignaron). |  |

### `dim_afiliado`

Empresas del CRM de Zoho, una fila por código de empresa, ya consolidadas y homologadas. Grano: una empresa del CRM. Clave primaria: `empresa_id`. Fuente: 1. Base de datos de afiliados (Zoho CRM) y 5. Base de datos afiliados ACTHO.

| Columna | Tipo | Nulos | Descripción | Relación o dominio |
|---|---|---|---|---|
| `empresa_id` | texto | no | Código anonimizado de la empresa (EMP-0000); reemplaza al NIT. |  |
| `id_registro_crm` | texto | sí | Identificador del registro en la exportación del CRM. |  |
| `ejecutiva_id` | texto | no | Ejecutiva propietaria de la cuenta. | Clave foránea a `dim_ejecutiva.ejecutiva_id` |
| `naturaleza` | texto | sí | Tipo de empresa (nacional privada, multinacional...). | Catálogo `naturaleza_empresa` (8 valores) |
| `tipo_compania` | texto | sí | Tipo de compañía en Zoho (Asociado, Cliente...). |  |
| `tipo_membresia` | texto | sí | Tipo de afiliado homologado. | Clave foránea a `dim_tipo_membresia.tipo_membresia` |
| `tipo_membresia_zoho` | texto | sí | Tipo de membresía tal como aparece en Zoho (limpio, sin homologar). |  |
| `categoria_membresia` | texto | sí | Categoría de Zoho (Estándar, Premium, Elite...) cuando la columna trae una categoría válida. | Catálogo `categorias_membresia` (4 valores) |
| `nivel` | texto | sí | Nivel 2027 (Conectar, Crecer, Liderar); nulo si no se puede inferir. | Clave foránea a `dim_nivel.nivel` |
| `estado_membresia` | texto | sí | Estado de la membresía; nulo si el CRM no lo trae. | Clave foránea a `dim_estado_membresia.estado_membresia` |
| `estado_registro` | texto | sí | Estado del registro en el CRM (Activo o Inactivo). | Catálogo `estados_registro_crm` (2 valores) |
| `sector` | texto | sí | Sector económico homologado. | Clave foránea a `dim_sector.sector` (aviso si no existe) |
| `subsector` | texto | sí | Subsector económico homologado. |  |
| `tipo_consultora` | texto | sí | Tipo de consultora (solo afiliados consultoras). |  |
| `ciudad` | texto | sí | Ciudad (la del registro o, si falta, la de facturación) homologada. | Clave foránea a `dim_ciudad.ciudad` (aviso si no existe) |
| `ciudad_facturacion` | texto | sí | Ciudad de facturación homologada. | Clave foránea a `dim_ciudad.ciudad` (aviso si no existe) |
| `departamento` | texto | sí | Departamento homologado. | Catálogo `departamentos` (11 valores) |
| `region` | texto | sí | Región comercial homologada. | Catálogo `regiones` (6 valores) |
| `pais` | texto | sí | País de facturación homologado. | Catálogo `paises` (2 valores) |
| `tamano` | texto | sí | Tamaño de la empresa (Micro, Pequeña, Mediana, Grande). | Catálogo `tamanos` (4 valores) |
| `rango_empleados` | texto | sí | Rango de empleados con formato único (1-50, 51-200...). | Catálogo `rangos_empleados` (6 valores) |
| `es_independiente` | booleano | sí | Verdadero si el afiliado es independiente. |  |
| `pct_mujeres` | decimal | sí | Porcentaje de mujeres en la compañía (0 a 100). | Rango 0 a 100 |
| `fecha_afiliacion` | fecha | sí | Fecha de afiliación; nula si venía vacía o con una fecha imposible. |  |
| `fecha_expiracion` | fecha | sí | Fecha de expiración de la afiliación. |  |
| `miembro_desde` | fecha | sí | Fecha «Miembro desde» del CRM. |  |
| `vinculado_comunidades` | booleano | no | Verdadero si el CRM marca vinculación a comunidades o hay miembros en alguna. |  |
| `cantidad_miembros` | entero | sí | Cantidad de miembros declarados. | Rango 0 a 100000 |
| `persona_principal_id` | texto | sí | Persona de contacto principal del afiliado (anonimizada). | Clave foránea a `dim_persona.persona_id` |
| `fecha_afiliacion_invalida` | booleano | no | Bandera: la fecha de afiliación original era posterior al corte y se descartó. |  |
| `fechas_incoherentes` | booleano | no | Bandera: la expiración es anterior a la afiliación. |  |
| `estado_inconsistente` | booleano | no | Bandera: el registro figura Activo pero la membresía está cancelada, expirada o inactiva. |  |
| `categoria_invalida` | booleano | no | Bandera: la columna de categoría traía un tipo («Empresas», «Consultoras»...) en lugar de una categoría. |  |

### `dim_persona`

Personas anonimizadas que aparecen en asistencia, encuestas o como contacto principal. Grano: una persona. Clave primaria: `persona_id`. Fuente: asistencia, encuestas, base de afiliados y nuevos afiliados.

| Columna | Tipo | Nulos | Descripción | Relación o dominio |
|---|---|---|---|---|
| `persona_id` | texto | no | Código anonimizado de la persona (P-00000). |  |
| `fuentes` | texto | no | Fuentes donde aparece, separadas por «;» (asistencia, encuesta, afiliado_principal). |  |
| `n_empresas_asociadas` | entero | no | Cantidad de empresas distintas con las que figura en asistencia o encuestas. | Rango 0 a 100 |
| `multiples_empresas` | booleano | no | Verdadero si figura con más de una empresa (cambio de empresa o código reutilizado). |  |

### `dim_evento`

Catálogo de eventos 2026 homologado con la oferta 2027. Grano: un evento. Clave primaria: `evento_id`. Fuente: 2. Registros de participación (hoja HOMOLOGACION y GENERAL).

| Columna | Tipo | Nulos | Descripción | Relación o dominio |
|---|---|---|---|---|
| `evento_id` | texto | no | Identificador del evento (EV01...). |  |
| `evento_n` | entero | no | Número del evento en la hoja GENERAL y en la homologación. |  |
| `hoja_origen` | texto | no | Hoja del libro de asistencia de la que sale la lista de asistentes. |  |
| `nombre` | texto | no | Nombre del evento. |  |
| `fecha_inicio` | fecha | no | Primer día del evento. |  |
| `fecha_fin` | fecha | no | Último día del evento (igual al primero en eventos de un día). |  |
| `mes` | texto | no | Mes de inicio en formato AAAA-MM. |  |
| `linea` | texto | sí | Línea o formato de la oferta 2027; nulo si no está clasificado. | Clave foránea a `dim_linea_evento.linea` |
| `experiencia` | texto | sí | Experiencia o detalle dentro de la línea. |  |
| `modalidad` | texto | sí | Modalidad (Presencial, Virtual, Híbrido). | Clave foránea a `dim_modalidad.modalidad` |
| `tiene_asistentes` | booleano | no | Falso si la hoja del evento no trae lista de asistentes. |  |

### `fact_asistencia`

Un registro por inscripción de una persona a un evento, con marcas de validez. Grano: una inscripción de una persona a un evento. Clave primaria: `asistencia_id`. Fuente: 2. Registros de participación (una hoja por evento).

| Columna | Tipo | Nulos | Descripción | Relación o dominio |
|---|---|---|---|---|
| `asistencia_id` | texto | no | Identificador de la fila (AS-00001...), asignado en el orden de las hojas. |  |
| `evento_id` | texto | no | Evento al que corresponde la hoja. | Clave foránea a `dim_evento.evento_id` |
| `persona_id` | texto | sí | Persona inscrita. | Clave foránea a `dim_persona.persona_id` |
| `empresa_id` | texto | no | Empresa de la persona. | Clave foránea a `dim_afiliado.empresa_id` (aviso si no existe) |
| `nivel_cargo` | texto | sí | Nivel de cargo; nulo cuando la fuente dice «Sin dato». | Clave foránea a `dim_nivel_cargo.nivel_cargo` |
| `ciudad` | texto | sí | Ciudad declarada (solo algunas hojas la traen). | Clave foránea a `dim_ciudad.ciudad` (aviso si no existe) |
| `con_costo` | booleano | sí | Verdadero si el cupo fue con costo. |  |
| `autoriza_datos` | booleano | sí | Verdadero si autorizó el tratamiento de datos. |  |
| `registro_ubicacion` | booleano | sí | Estado de registro de ubicación principal (Sí o No), cuando la hoja lo trae. |  |
| `marca_fuente` | entero | sí | Marca numérica de la primera columna de la hoja («Tipo de asistente» o «Afiliado»); su significado no está documentado en la fuente. |  |
| `es_agendado` | booleano | no | Verdadero si el registro está solo agendado; no cuenta como asistencia. |  |
| `es_duplicado` | booleano | no | Verdadero si repite a la misma persona en el mismo evento. |  |
| `es_valida` | booleano | no | Verdadero si cuenta como asistencia (no agendada ni duplicada). |  |

### `fact_encuesta`

Una fila por respuesta de las tres encuestas de eventos, con satisfacción 1 a 5 y NPS. Grano: una respuesta de encuesta. Clave primaria: `respuesta_id`. Fuente: 3. Encuestas y NPS (presencial, virtual y post-evento).

| Columna | Tipo | Nulos | Descripción | Relación o dominio |
|---|---|---|---|---|
| `respuesta_id` | texto | no | Identificador de la respuesta (EP-0001, EV-0001, PE-0001). |  |
| `fuente` | texto | no | Encuesta de origen. | Catálogo `origenes_encuesta` (3 valores) |
| `modalidad` | texto | sí | Modalidad del evento que se evalúa. | Clave foránea a `dim_modalidad.modalidad` |
| `fecha_respuesta` | fecha | no | Fecha en que se completó la respuesta. |  |
| `persona_id` | texto | sí | Persona que responde. | Clave foránea a `dim_persona.persona_id` |
| `empresa_id` | texto | sí | Empresa de quien responde; nula si no se pudo identificar. | Clave foránea a `dim_afiliado.empresa_id` (aviso si no existe) |
| `ciudad` | texto | sí | Ciudad declarada. | Clave foránea a `dim_ciudad.ciudad` (aviso si no existe) |
| `evento_id` | texto | sí | Evento 2026 inferido por fecha y modalidad; nulo si no hay uno compatible. | Clave foránea a `dim_evento.evento_id` |
| `metodo_evento` | texto | no | Cómo se asignó (o por qué no se asignó) el evento. |  |
| `metodo_asignacion_empresa` | texto | sí | Cómo se identificó la empresa en la encuesta. |  |
| `afiliado_declarado` | booleano | sí | Verdadero si la persona dice ser afiliada (solo la encuesta post-evento lo pregunta). |  |
| `satisfaccion` | decimal | sí | Satisfacción media de 1 a 5 de los aspectos calificados. | Rango 1 a 5 |
| `nps_puntaje` | entero | sí | Recomendación de 0 a 10 (solo la encuesta post-evento). | Rango 0 a 10 |
| `nps_categoria` | texto | sí | Promotor, Pasivo o Detractor. | Valores: Promotor, Pasivo, Detractor |

### `fact_encuesta_aspecto`

Calificaciones de 1 a 5 por aspecto de cada respuesta (columnas pasadas a filas). Grano: un aspecto de una respuesta. Clave primaria: `respuesta_id`, `aspecto`. Fuente: 3. Encuestas y NPS.

| Columna | Tipo | Nulos | Descripción | Relación o dominio |
|---|---|---|---|---|
| `respuesta_id` | texto | no | Respuesta calificada. | Clave foránea a `fact_encuesta.respuesta_id` |
| `aspecto` | texto | no | Aspecto calificado. | Catálogo `aspectos_encuesta` (11 valores) |
| `calificacion` | entero | no | Calificación de 1 a 5. | Rango 1 a 5 |

### `fact_encuesta_tema`

Temas de interés marcados en la encuesta post-evento (opciones cerradas, sin texto libre). Grano: un tema marcado en una respuesta. Clave primaria: `respuesta_id`, `tema`. Fuente: 3. Encuestas y NPS (post-evento, pregunta 18).

| Columna | Tipo | Nulos | Descripción | Relación o dominio |
|---|---|---|---|---|
| `respuesta_id` | texto | no | Respuesta que marcó el tema. | Clave foránea a `fact_encuesta.respuesta_id` |
| `tema` | texto | no | Tema marcado. |  |

### `fact_comunidad_afiliado`

Miembros de cada empresa en cada comunidad de ACTHO (columnas pasadas a filas). Grano: una empresa en una comunidad. Clave primaria: `empresa_id`, `comunidad`. Fuente: 1. Base de datos de afiliados.

| Columna | Tipo | Nulos | Descripción | Relación o dominio |
|---|---|---|---|---|
| `empresa_id` | texto | no | Empresa afiliada. | Clave foránea a `dim_afiliado.empresa_id` |
| `comunidad` | texto | no | Comunidad (HR Estratégico, Mujeres HR...). |  |
| `miembros` | entero | no | Cantidad de miembros de la empresa en la comunidad. | Rango 1 a 1000 |

### `fact_renovacion`

Renovaciones facturadas en los últimos dos meses del informe de Zoho. Grano: una renovación. Clave primaria: `renovacion_id`. Fuente: 5. Informe Renovaciones - Últimos 2 meses.

| Columna | Tipo | Nulos | Descripción | Relación o dominio |
|---|---|---|---|---|
| `renovacion_id` | texto | no | Identificador (RN-001...). |  |
| `empresa_id` | texto | no | Empresa que renovó. | Clave foránea a `dim_afiliado.empresa_id` (aviso si no existe) |
| `ejecutiva_id` | texto | no | Ejecutiva de la cuenta. | Clave foránea a `dim_ejecutiva.ejecutiva_id` |
| `mes_factura` | fecha | sí | Primer día del mes de la factura de renovación. |  |
| `fecha_expiracion_nueva` | fecha | sí | Nueva fecha de expiración tras renovar. |  |

### `fact_afiliacion_nueva`

Afiliaciones nuevas de agosto a octubre: negocios ganados y lista de nuevos afiliados, unidos por empresa. Grano: una afiliación nueva. Clave primaria: `afiliacion_id`. Fuente: 5. Afiliaciones - Últimos 2 meses y Nuevos Afiliados AGO-SEP.

| Columna | Tipo | Nulos | Descripción | Relación o dominio |
|---|---|---|---|---|
| `afiliacion_id` | texto | no | Identificador (AF-001...). |  |
| `empresa_id` | texto | no | Empresa nueva. | Clave foránea a `dim_afiliado.empresa_id` (aviso si no existe) |
| `ejecutiva_id` | texto | sí | Ejecutiva que cerró el negocio; nula si la empresa solo figura en la lista de nuevos. | Clave foránea a `dim_ejecutiva.ejecutiva_id` |
| `fecha_cierre` | fecha | sí | Fecha de cierre del negocio. |  |
| `categoria_membresia` | texto | sí | Categoría de membresía del negocio, tal como la digitó el CRM. |  |
| `nivel` | texto | sí | Nivel 2027 inferido de la categoría. | Clave foránea a `dim_nivel.nivel` |
| `mes_lista_nuevos` | fecha | sí | Primer día del mes en que figura en la lista de nuevos afiliados. |  |
| `persona_principal_id` | texto | sí | Afiliado principal de la lista de nuevos. | Clave foránea a `dim_persona.persona_id` |
| `en_informe_afiliaciones` | booleano | no | Verdadero si figura en el informe de afiliaciones de los últimos dos meses. |  |
| `en_lista_nuevos` | booleano | no | Verdadero si figura en la lista de nuevos afiliados de agosto y septiembre. |  |

### `fact_oportunidad_ganada`

Oportunidades ganadas por ejecutiva según el informe de Zoho. Grano: una oportunidad ganada. Clave primaria: `oportunidad_id`. Fuente: 5. Estados oportunidades ganadas por KAM.

| Columna | Tipo | Nulos | Descripción | Relación o dominio |
|---|---|---|---|---|
| `oportunidad_id` | texto | no | Identificador (OP-001...). |  |
| `empresa_id` | texto | no | Empresa de la oportunidad. | Clave foránea a `dim_afiliado.empresa_id` (aviso si no existe) |
| `ejecutiva_id` | texto | no | Ejecutiva propietaria del trato. | Clave foránea a `dim_ejecutiva.ejecutiva_id` |

### `fact_score_afiliado`

Variables, puntos, riesgo y banda del score de cada afiliado vigente a la fecha de corte. Grano: un afiliado vigente. Clave primaria: `empresa_id`. Fuente: Resultado del score (pipeline/score.py).

| Columna | Tipo | Nulos | Descripción | Relación o dominio |
|---|---|---|---|---|
| `empresa_id` | texto | no | Afiliado vigente puntuado. | Clave foránea a `dim_afiliado.empresa_id` |
| `fecha_corte` | fecha | no | Fecha de corte del cálculo. |  |
| `dias_vencimiento` | entero | sí | Días entre el corte y la expiración (negativo si ya venció). |  |
| `dias_afiliacion` | entero | sí | Días desde la afiliación hasta el corte. |  |
| `antiguedad_anios` | decimal | sí | Antigüedad en años. | Rango 0 a 100 |
| `asistencias` | entero | no | Asistencias válidas de 2026 hasta el corte. | Rango 0 a 100000 |
| `asistencias_90d` | entero | no | Asistencias en los 90 días previos al último evento registrado. | Rango 0 a 100000 |
| `eventos_distintos` | entero | no | Eventos distintos con asistencia. | Rango 0 a 100 |
| `personas_distintas` | entero | no | Personas distintas que asistieron. | Rango 0 a 100000 |
| `ultima_asistencia` | fecha | sí | Fecha de la última asistencia. |  |
| `dias_ultima_asistencia` | entero | sí | Días desde la última asistencia. |  |
| `n_respuestas` | entero | no | Respuestas de encuesta en los últimos 12 meses. | Rango 0 a 100000 |
| `satisfaccion` | decimal | sí | Satisfacción media de 1 a 5 en los últimos 12 meses. | Rango 1 a 5 |
| `nps_minimo` | entero | sí | Calificación mínima de recomendación en los últimos 12 meses. | Rango 0 a 10 |
| `detractor` | booleano | no | Verdadero si alguna calificación de recomendación fue de 0 a 6. |  |
| `renovo_recientemente` | booleano | no | Verdadero si renovó en los últimos dos meses. |  |
| `puntos` | decimal | no | Puntos de riesgo acumulados. | Rango 0 a 1000 |
| `riesgo` | decimal | no | Riesgo de 0 a 100. | Rango 0 a 100 |
| `salud` | decimal | no | Salud de 0 a 100 (100 menos el riesgo). | Rango 0 a 100 |
| `banda` | texto | no | Saludable, Atención o Riesgo alto. | Valores: Saludable, Atención, Riesgo alto |
| `accion` | texto | no | Acción sugerida derivada del factor principal. |  |

### `fact_score_factor`

Factores que explican el score de cada afiliado, ordenados por puntos. Grano: un factor de un afiliado. Clave primaria: `empresa_id`, `orden`. Fuente: Resultado del score (pipeline/score.py).

| Columna | Tipo | Nulos | Descripción | Relación o dominio |
|---|---|---|---|---|
| `empresa_id` | texto | no | Afiliado puntuado. | Clave foránea a `fact_score_afiliado.empresa_id` |
| `orden` | entero | no | Posición del factor (1 es el que más pesa). | Rango 1 a 50 |
| `codigo` | texto | no | Código del factor. |  |
| `puntos` | decimal | no | Puntos que aporta al riesgo (negativos si lo reducen). |  |
| `texto` | texto | no | Explicación en español. |  |

<!-- fin:esquema -->
