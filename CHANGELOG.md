# Registro de cambios

Los cambios se anotan por versión, con la más reciente primero. El número de versión del pipeline está en `pipeline/__init__.py` y el de los pesos del score en `config/pesos_score.json`; ambos se muestran en la vista de metodología del tablero.

## 2.0.0 Mejoras v2 (25 de noviembre de 2026)

Refuerzo de la limpieza y modelo relacional normalizado, sin cambiar el contrato de los JSON del tablero (solo se añaden campos y un archivo).

La limpieza lee ahora un diccionario editable, `config/homologacion.json`, en lugar de mapeos incrustados, estandariza nombres de columna, convierte centinelas en nulos, tipifica fechas, enteros, porcentajes y booleanos, y homologa país, departamento, región, tamaño, subsector, modalidad, línea, nivel de cargo y autorización de datos. Detecta y cuenta filas vacías, totales y encabezados repetidos, lee con un lector común los informes agrupados de Zoho y los bloques repetidos del consolidado por KAM, y lista en `control_rechazos.csv` las 38 filas descartadas, entre ellas 15 inscripciones sin código de empresa que antes se perdían sin aviso.

`data/processed` pasa a ser un modelo de 22 tablas (`dim_afiliado`, `dim_evento`, `dim_ejecutiva`, `dim_persona`, `fact_asistencia`, `fact_encuesta` y otras) con tablas de control. `pipeline/validacion.py` verifica tipos, claves y 33 relaciones y reporta los huérfanos (por ejemplo 721 empresas con asistencia que no están en el CRM) en `control_huerfanos.csv`. Nuevo `web/data/tendencias.json` con series mensuales y `meta.json` con los bloques `homologacion`, `modelo`, `integridad` y `calidad`. Las cifras del tablero no cambian; solo se unifican 10 etiquetas de sector.

Nueva documentación: `docs/LIMPIEZA.md`, `docs/DICCIONARIO_DATOS.md`, sección «Mejoras v2» de `docs/PIPELINE.md` y reporte `docs/eda/08_antes_despues.md` con figuras. Se añaden 211 pruebas (325 en total).

## 1.0.0 (25 de noviembre de 2026)

Primera versión entregable de DACTHO 360, con corte de datos al 25 de noviembre de 2026.

El pipeline integra el CRM de Zoho, el libro de asistencia a eventos de 2026, las encuestas de eventos y el informe de renovaciones por código de empresa. Consolida el CRM a una fila por empresa, repara las tildes dañadas, unifica ciudades, sectores y tipos de membresía, recalcula la asistencia recorriendo las 34 hojas de evento (la hoja consolidada tiene rangos truncados) y asigna cada respuesta de encuesta a un evento por modalidad y fecha cuando es posible. Produce 474 afiliados vigentes con score de salud y riesgo, bandas, factores explicados y acción sugerida, y escribe siete JSON para el tablero y cinco CSV intermedios.

La validación retrospectiva compara el score con 33 empresas que salieron entre abril y noviembre de 2026 y obtiene un AUC de 0,77 (intervalo de 95 % de 0,69 a 0,85). Se interpreta como una asociación, no como una predicción comprobada.

El tablero incluye siete vistas (resumen, afiliados, ejecutivas, eventos, encuestas, alertas y metodología), tema claro y oscuro, diseño adaptable a móvil, navegación por teclado y por hash. El módulo de alertas permite crear, editar, duplicar, activar y eliminar reglas con condiciones Y/O y ámbito por ejecutiva, partir de siete plantillas, exportar listas a CSV y exportar e importar las reglas en JSON. Las reglas se guardan en el navegador de cada persona.

La documentación incluye el README, la arquitectura, el manual de usuario, la guía de despliegue, el manual de mantenimiento y el glosario, además de la descripción del pipeline y siete reportes de análisis exploratorio. Se añaden 20 pruebas automáticas con datos sintéticos.

Limitaciones conocidas de esta versión: la asistencia cubre del 1 de enero al 27 de octubre de 2026; solo el 33,1 % de los afiliados tiene respuestas de encuesta y el 4,9 % una calificación de recomendación; el NPS post-evento se basa en 41 respuestas; la encuesta de 90 días no tiene respuestas; y las reglas de alerta no se comparten entre usuarios.
