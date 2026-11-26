# Decisiones de limpieza y su justificación

**Código de empresa como clave.** El NIT no está disponible. El código EMP-0000 es el único identificador común a las tres fuentes. Se valida su formato y se descartan los que no lo cumplen.

**Una fila por empresa en el CRM.** Hay 21 códigos repetidos. Se conserva el registro vigente; si ninguno lo es, el que tenga estado y fecha de expiración. Así una empresa con un registro cancelado antiguo y otro activo no se cuenta como baja.

**Registros de prueba.** Se excluyen las filas con etiqueta de prueba (2).

**Afiliado vigente.** Estado de membresía Activo, Periodo de Gracia o Pronto a Expirar. Cancelado, Expirado e Inactivo son salidas; las filas sin estado (70) no se puntúan porque no se sabe si son afiliados.

**Tildes dañadas.** El texto con codificación rota (por ejemplo «Bogotﾃ｡») se repara reinterpretando los bytes como UTF-8. Es una corrección determinista y reversible.

**Ciudades, sectores y categorías.** Se unifican variantes por clave sin tildes ni mayúsculas. «Estandar» y «Estándar» son el mismo nivel; Estándar Colaborador se trata como Conectar.

**Niveles.** Estándar, Premium y Elite de Zoho equivalen a Conectar, Crecer y Liderar (documento de oferta 2027). Si la categoría trae un valor de tipo, se infiere del tipo de membresía.

**Ejecutiva.** Vacío, «0» y «Sin asignar (cuenta ACTHO)» se tratan como sin asignar.

**Fechas.** Se aceptan ISO, dd/mm/aaaa y el formato en español de Zoho Survey. Una fecha de afiliación posterior al corte (2066) se descarta. Los eventos de varios días usan la fecha de fin del calendario.

**Asistencia.** Se recorre cada hoja por nombre de columna, sin depender de las fórmulas de la hoja GENERAL. Se descartan los repetidos de la misma persona en el mismo evento y los registros agendados. La hoja de febrero 13 no trae lista y queda sin asistentes.

**Encuestas.** Se unifican en una tabla de respuestas con satisfacción media de los aspectos de 1 a 5. El evento se infiere por fecha y modalidad; si dos eventos compatibles coinciden, queda ambiguo. Las respuestas de 2025 se usan para la satisfacción por empresa pero no se asignan a eventos.

**Satisfacción faltante no penaliza.** Solo 33.1% de los afiliados tiene respuestas; castigar la ausencia penalizaría por no haber sido encuestado. La ausencia queda como aviso y no como puntos.

**Ventana de participación reciente.** El libro termina el 27 de octubre de 2026; los 90 días se miden hasta el último evento registrado y no hasta la fecha de corte, para no marcar a todos como inactivos por un vacío de datos.

**Afiliados nuevos.** Con menos de 90 días de afiliación, las señales de ausencia de participación se reducen a la mitad.
