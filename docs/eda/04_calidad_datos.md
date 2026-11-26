# Calidad de los datos

## Avisos del pipeline

| fuente | severidad | descripcion | cantidad |
|---|---|---|---|
| CRM | media | Celdas con tildes dañadas (codificación) que se repararon al cargar. | 580 |
| CRM | baja | Registros de prueba excluidos. | 2 |
| CRM | media | Códigos de empresa repetidos; se conservó un registro por empresa. | 21 |
| CRM | media | Empresas sin estado de membresía; no se puntúan. | 70 |
| CRM | alta | Afiliados vigentes sin ejecutiva asignada. | 7 |
| CRM | alta | Afiliados con estado vigente cuya fecha de expiración ya pasó. | 41 |
| CRM | media | Afiliados vigentes sin fecha de expiración. | 8 |
| CRM | media | Afiliados vigentes sin nivel interpretable (Conectar, Crecer, Liderar). | 4 |
| CRM | baja | Variantes de categoría como «Estándar» y «Estandar» unificadas. | 31 |
| CRM | baja | Fechas de afiliación posteriores al corte, descartadas. | 1 |
| Asistencia | alta | La hoja consolidada tiene rangos truncados y columnas sin fórmula; subestima las asistencias reales. | 34 |
| Asistencia | baja | Registros repetidos de la misma persona en el mismo evento, descartados. | 82 |
| Asistencia | baja | Registros en estado «agendado», que no se cuentan como asistencia. | 12 |
| Asistencia | media | Empresas con asistencia que no están en el CRM (posibles no afiliadas). | 721 |
| Encuestas | alta | Respuestas sin empresa identificada. | 142 |
| Encuestas | alta | Respuestas que no se pudieron asignar a un evento 2026 por fecha. | 474 |
| Encuestas | alta | El NPS post-evento se basa en muestra pequeña; no es un NPS de la asociación. | 41 |
| Encuestas | alta | La encuesta de 90 días no tiene respuestas todavía. | 0 |
| Integración | alta | Porcentaje de afiliados vigentes sin ninguna asistencia registrada. | 21,7 |
| Integración | alta | Porcentaje de afiliados vigentes sin ninguna respuesta de encuesta. | 66,9 |
| CRM | media | Empresas con registro Activo pero membresía cancelada, expirada o inactiva. | 8 |
| CRM | baja | Registros cuya categoría de membresía trae un tipo en lugar de una categoría; el nivel se infiere del tipo. | 133 |
| Asistencia | media | Inscripciones con persona pero sin código de empresa; se descartan y se listan en control_rechazos. | 15 |
| Integración | alta | Filas de hechos (asistencia, encuestas, renovaciones, afiliaciones, oportunidades) cuya empresa no existe en el CRM. | 1.258 |
| Integración | baja | Filas con una ciudad que no está en el catálogo de config/homologacion.json. | 17 |
| Integración | baja | Errores de estructura o relaciones rotas del modelo relacional. | 0 |

## Nulos, duplicados e inconsistencias del CRM

El CRM tiene 21 códigos de empresa repetidos, 10 de ellos con estados distintos (por ejemplo, un registro activo y otro cancelado de la misma empresa). Se conserva el registro vigente. Los registros duplicados cancelados suelen estar en manos de «Sin asignar», lo que sesga cualquier análisis por ejecutiva si no se deduplica.

Los valores únicos de ciudad pasan de 44 a 39 y los de sector de 37 a 27 tras reparar tildes dañadas y unificar variantes. Cuatro propietarios (KAM G, KAM H, KAM I y «0») aparecen en una sola cuenta cancelada cada uno.

Categorías de membresía crudas:

| categoria_membresia | registros |
|---|---|
| Estándar | 550 |
| Premium | 135 |
| Empresas | 48 |
| Persona Natural | 36 |
| Consultoras | 35 |
| Estandar | 31 |
| Estándar Colaborador | 21 |
| Personal | 13 |
| Elite | 12 |
| Plus | 1 |

### Ejecutiva asignada según estado

Las cuentas «Sin asignar» son sobre todo canceladas: al cancelarse, la cuenta se reasigna. Por eso la ejecutiva no se usa como señal en la validación retrospectiva, y entre los vigentes solo 7 cuentas carecen de ejecutiva.

| estado | con ejecutiva | sin ejecutiva |
|---|---|---|
| Cancelado | 344 | 146 |
| Activo | 426 | 7 |
| Sin estado | 60 | 10 |
| Periodo de Gracia | 33 | 0 |
| Expirado | 13 | 1 |
| Pronto a Expirar | 8 | 0 |
| Inactivo | 2 | 0 |

## Fórmulas rotas en la hoja consolidada de asistencia

| control | valor |
|---|---|
| Columnas de evento sin fórmula | [27, 35, 36] |
| Columnas con rango truncado | 31 |
| Empresas con asistencia que la hoja no lista | 791 |
| Total reportado por la hoja | 1285 |
| Total contado en las hojas | 3292 |

## Inconsistencias de nombres, NIT y niveles

El NIT fue eliminado en la anonimización y el código de empresa es el único identificador compartido. Todos los códigos con formato EMP-0000 son válidos; 1087 registros de asistencia usan códigos fuera del CRM (EMP-1053 en adelante), que son empresas no afiliadas o afiliadas todavía no cargadas. El informe de nuevos afiliados de agosto y septiembre incluye 3 códigos (EMP-1771, EMP-1774 y EMP-1775) que no están en la exportación del CRM, lo que indica un desfase de captura. Los niveles de Zoho (Estándar, Estandar, Estándar Colaborador, Premium, Elite) se llevan a Conectar, Crecer y Liderar.
