# Manual de usuario

Este manual está escrito para el equipo comercial de ACTHO. No requiere conocimientos técnicos. Explica qué muestra cada vista de DACTHO 360, cómo leer el score de un afiliado y cómo crear y gestionar alertas. Las capturas de cada pantalla están en `docs/capturas/`, en versión de escritorio y móvil.

## Antes de empezar

El tablero se abre en el navegador con la dirección que le entregue el equipo técnico. A la izquierda, o bajo el botón «Menú» en el celular, aparecen las siete secciones. El botón «Tema» alterna entre automático, claro y oscuro. Los datos corresponden al corte indicado en la parte inferior del menú, el 25 de noviembre de 2026 en esta versión, y no se actualizan solos: se renuevan cuando el equipo técnico ejecuta el pipeline y publica los archivos nuevos.

Una advertencia que conviene tener presente desde el comienzo. Las reglas de alerta que usted cree viven únicamente en su navegador. No las ve nadie más y se pierden si borra los datos del sitio o cambia de equipo, salvo que las exporte. Más adelante se explica cómo hacerlo.

## Las siete vistas

### Resumen ejecutivo

Es la pantalla de entrada. Muestra cuántos afiliados vigentes hay, cuántos están en riesgo alto, cuántos vencen en 90 días o menos, el NPS post-evento, la satisfacción promedio, el porcentaje con asistencia en 2026 y en el último trimestre registrado, y la salud promedio de la cartera. Debajo aparecen la distribución por banda, los vencimientos por tramo, la composición del NPS, el perfil de la cartera por nivel, tipo y sector, y cinco listas ya calculadas para priorizar el trabajo: afiliados sin asistencia reciente, que vencen pronto, con un solo contacto, nuevos y promotores. Varios elementos son enlaces que llevan a la vista de afiliados con el filtro ya aplicado.

Un dato que conviene mirar de cerca: algunas cuentas figuran como vigentes en el CRM pero su fecha de expiración ya pasó. El resumen las cuenta aparte, porque suelen indicar un registro por regularizar o una renovación que no se capturó.

### Afiliados

Es una tabla con todos los afiliados vigentes. Se puede buscar por código, sector o ciudad, filtrar por banda, nivel, ejecutiva, estado y tramo de vencimiento, y ordenar por cualquier columna. Al seleccionar un código se abre la ficha del afiliado, que explica su score (la siguiente sección lo detalla) y muestra sus datos de membresía, participación y satisfacción, además de las reglas de alerta que activa en su navegador.

### Ejecutivas

Presenta una tarjeta por ejecutiva con el tamaño de su cartera, la distribución por banda, cuántas cuentas ya vencieron o vencen en 30, 60 y 90 días, cuántas no tienen asistencia, el riesgo promedio y una lista de afiliados prioritarios, que combina mayor riesgo y cercanía del vencimiento. En los datos entregados los nombres están anonimizados (KAM A a KAM F) y la fila «Sin asignar» agrupa las cuentas sin responsable, que conviene reasignar.

### Eventos y participación

Resume los eventos de 2026: cuántos fueron, cuántas asistencias válidas hubo, cuántas personas y empresas distintas participaron, y cómo se reparten por mes, línea, modalidad y nivel de cargo. Incluye una tabla de eventos y una lista de las empresas que asisten sin ser afiliadas vigentes, que son candidatas a una conversación de afiliación o de reafiliación. El libro de asistencia llega hasta el 27 de octubre de 2026, así que la participación de noviembre no aparece.

### Encuestas y NPS

Muestra la satisfacción media y el NPS de las encuestas de eventos, separados entre afiliados y no afiliados, y el detalle por fuente, modalidad, línea y nivel de afiliado. El NPS de 90 días figura como «Sin datos» porque esa encuesta aún no se aplica. Esta vista debe leerse con prudencia: el NPS post-evento se basa en 41 respuestas, sin ningún detractor, y es un valor optimista y poco estable. No equivale al NPS de la asociación.

### Alertas

Es el módulo de trabajo, descrito en detalle más abajo.

### Metodología

Documenta dentro del propio tablero el corte de datos, las fuentes, el cálculo del score, la validación y sus límites, los supuestos y una tabla de avisos de calidad con la cantidad de registros afectados en cada caso. Es útil para responder a una pregunta de la dirección sobre de dónde sale una cifra.

## Cómo leer el score

Cada afiliado tiene un riesgo de 0 a 100 y una salud, que es 100 menos el riesgo. Un riesgo mayor indica que se acumulan más señales asociadas con la salida de afiliados en el pasado, una frase que se debe leer con cuidado, como se explica al final de esta sección. Con ese número, el afiliado cae en una de tres bandas: Saludable si el riesgo es menor a 35, Atención de 35 a menos de 55, y Riesgo alto desde 55. En la pantalla cada banda se distingue por nombre, símbolo y trama, no solo por color.

El número no es una caja negra. La ficha lista los factores que lo componen, cada uno con sus puntos y una frase en español, por ejemplo «La afiliación vence en 25 días» o «No registra ninguna asistencia a eventos en 2026». Los factores se agrupan en vencimiento, participación en eventos, satisfacción, antigüedad, nivel, ausencia de ejecutiva y ausencia de comunidades. Los puntos se suman, se dividen por el máximo posible y se expresan en escala de 0 a 100. Una renovación reciente, en los últimos dos meses, resta puntos. El factor con más puntos determina la acción sugerida, que es una recomendación breve de contacto, por ejemplo llamar para escuchar la experiencia o invitar a una actividad.

Hay varias reglas que evitan lecturas injustas. La falta de respuestas de encuesta no suma puntos, porque dos de cada tres afiliados no han sido encuestados y sería castigarlos por algo que no depende de ellos. A quienes llevan menos de 90 días afiliados se les reduce a la mitad el peso de la falta de participación. Y la «asistencia reciente» se mide hasta el último evento registrado, no hasta la fecha de corte.

Sobre el alcance del score, debemos ser claros. Al compararlo con 33 empresas que salieron en 2026 obtuvimos un AUC de 0,77, lo que significa que, en esa muestra, quienes salieron tendían a tener más riesgo que quienes permanecieron. Es una asociación observada hacia atrás, con pocos casos y con poca historia de asistencia; no es una predicción comprobada. El score sirve para ordenar prioridades y empezar conversaciones, no para decidir por sí solo sobre un afiliado. Los umbrales de las bandas se escogieron para que la lista roja sea atendible en una semana y no por un ajuste estadístico.

## Alertas

Una alerta es una regla que usted define sobre los datos de los afiliados, por ejemplo «riesgo alto y vence en menos de 60 días». El tablero evalúa cada regla activa sobre toda la cartera y le muestra quiénes la cumplen.

### Crear una regla

Se pulsa «Nueva regla», o «Usar plantilla» en una de las plantillas de la parte inferior. Se escribe un nombre, una descripción opcional y se elige la severidad (alta, media o baja). El ámbito opcional limita la regla a la cartera de una ejecutiva; si se deja vacío, aplica a toda la cartera. Luego se agregan las condiciones. Cada una tiene un campo (banda, riesgo, días a vencimiento, nivel, ejecutiva, asistencias, satisfacción, antigüedad, pertenencia a una comunidad, entre otros), un operador («es», «es menor que», «está entre», «no tiene dato», etc., según el tipo de campo) y un valor.

Las condiciones se unen con Y u O. La Y se evalúa antes que la O, de modo que «A Y B O C» significa «(A y B) o C». Si necesita una combinación distinta, conviene separarla en dos reglas. Cuando un afiliado no tiene dato en un campo numérico, esa comparación no se cumple; así, «satisfacción menor que 4,2» no incluye a quienes nunca respondieron una encuesta. Mientras escribe, el editor indica cuántos afiliados activaría la regla con los datos actuales, lo cual ayuda a detectar condiciones demasiado amplias o demasiado estrictas. Al guardar, la regla aparece en la lista.

Las plantillas disponibles son riesgo alto con vencimiento en menos de 60 días, sin asistencia en 2026, vigente con fecha de expiración vencida, vence en 30 días y sin asistencia reciente, satisfacción baja, afiliación nueva sin participación y sin ejecutiva asignada. La primera vez que se abre el módulo se siembran las tres primeras como reglas activas. Conviene revisarlas y ajustarlas a su criterio.

### Gestionar las reglas

La lista de la izquierda muestra cada regla con su severidad, su ámbito y cuántos afiliados la activan. Al seleccionar una regla se ve a la derecha su condición en lenguaje natural, la distribución por ejecutiva y la tabla de afiliados. Un interruptor activa o desactiva cada regla; las desactivadas se pueden consultar, pero no cuentan en los totales. Los botones permiten editar, duplicar (útil para crear una variante por ejecutiva) y eliminar. Eliminar es definitivo en este navegador, y por eso el tablero pide confirmación.

Encima de la lista, tres indicadores resumen el estado: cuántas reglas están activas, cuántos afiliados distintos tienen alguna alerta y cuántos tienen una de severidad alta. Los afiliados que cumplen varias reglas se cuentan una sola vez.

### Exportar listas para el trabajo comercial

El botón «Exportar lista a CSV» descarga los afiliados de la regla seleccionada, con su banda, riesgo, nivel, ejecutiva, estado, vencimiento, asistencias, satisfacción y acción sugerida. «Exportar alertas activas a CSV» reúne las listas de todas las reglas activas; un afiliado que cumple dos reglas aparece en dos filas, una por regla. Los CSV se abren en Excel. Los archivos contienen códigos de empresa anonimizados y deben tratarse con el mismo cuidado que cualquier base de clientes.

### Respaldar y compartir reglas

Como las reglas se guardan solo en su navegador, hacemos énfasis en este paso. «Exportar reglas (JSON)» descarga un archivo, `dactho360-reglas.json`, con todas sus reglas. «Importar reglas (JSON)» lo lee y agrega las reglas al navegador actual. Es la forma de pasarlas a otro equipo, de entregarlas a una compañera o de recuperarlas si se borraron los datos del sitio. La importación añade las reglas y no reemplaza las existentes, así que importar dos veces el mismo archivo duplica las reglas. Las reglas inválidas o mal formadas se descartan y el tablero informa cuántas fueron.

Recomendamos exportar las reglas después de cada cambio importante y guardar el archivo en una carpeta compartida del equipo. Si dos personas crean reglas por separado, cada una verá solo las suyas hasta que se las intercambien. Si el navegador está en modo privado o bloquea el almacenamiento, el tablero avisa que las reglas valdrán mientras la página esté abierta.

Cuando el equipo técnico publique un corte nuevo, las reglas guardadas se aplicarán a los datos nuevos sin necesidad de recrearlas, siempre que usted abra el tablero en la misma dirección web y en el mismo navegador. El almacenamiento del navegador está ligado a la dirección: si el tablero se traslada a otro dominio, las reglas no se ven y hay que importarlas desde el archivo JSON.

## Cómo interpretar con prudencia

Hay cuatro límites que conviene recordar al conversar con un afiliado o presentar resultados a la dirección. Primero, el 21,7 % de los afiliados no aparece en ninguna asistencia de 2026 y el 66,9 % no tiene respuestas de encuesta; en parte se trata de captura incompleta y no de falta de interés. Segundo, la asistencia solo cubre de enero al 27 de octubre de 2026. Tercero, el NPS es de una muestra pequeña. Cuarto, el score se asocia con salidas pasadas, pero no está probado como predictor. Ante la duda, la ficha del afiliado y la vista de metodología muestran de dónde viene cada número.
