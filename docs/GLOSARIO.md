# Glosario

Los términos están ordenados alfabéticamente. Las definiciones se refieren al uso que se da a cada palabra en DACTHO 360.

**Afiliado vigente.** Empresa o persona cuyo estado de membresía en el CRM es Activo, Periodo de Gracia o Pronto a Expirar. Cancelado, Expirado e Inactivo se consideran salidas históricas, y las filas sin estado no se puntúan. Con corte al 25 de noviembre de 2026 hay 474.

**Alerta.** Resultado de aplicar una regla a la cartera: el conjunto de afiliados que cumple sus condiciones. También se usa para nombrar la propia regla.

**Ámbito.** Límite opcional de una regla de alerta a la cartera de una ejecutiva.

**Anonimización y seudonimización.** La primera elimina la posibilidad de identificar al titular; la segunda reemplaza los identificadores por códigos, de modo que quien tenga la tabla de equivalencias puede revertirla. Los datos de este proyecto usan códigos, por lo que deben tratarse con cautela.

**AUC.** Área bajo la curva ROC. Mide, en una escala de 0,5 (azar) a 1, con qué frecuencia una empresa que salió recibe un riesgo mayor que una que permaneció. Un AUC de 0,77 indica una asociación moderada. No equivale a probar que el score prediga salidas futuras.

**Banda.** Clasificación del riesgo en tres categorías: Saludable (menos de 35), Atención (de 35 a menos de 55) y Riesgo alto (55 o más). Los umbrales se configuran en `config/pesos_score.json`.

**Código de empresa.** Identificador anonimizado con formato `EMP-0000` que reemplaza al NIT y une el CRM, la asistencia y las encuestas.

**Conectar, Crecer y Liderar.** Niveles de afiliación 2027. Corresponden a las categorías de Zoho Estándar (y Estándar colaborador), Premium y Elite, en ese orden.

**Corte, fecha de corte.** Fecha de referencia con la que se miden vencimientos, antigüedad y ventanas. En esta entrega es el 25 de noviembre de 2026.

**CRM.** Sistema de gestión de clientes. ACTHO usa Zoho CRM, de donde proviene la base de afiliados.

**Cruce, tasa de cruce.** Proporción de afiliados que aparece en otra fuente. Por ejemplo, el 78,3 % de los vigentes cruza con alguna asistencia de 2026.

**Detractor, pasivo, promotor.** Categorías de quien responde la pregunta de recomendación de 0 a 10. Detractor es de 0 a 6, pasivo de 7 a 8 y promotor de 9 a 10.

**EDA.** Análisis exploratorio de datos. Los reportes están en `docs/eda/` y se regeneran con `eda/run_eda.py`.

**Ejecutiva, KAM.** Responsable comercial de una cuenta. KAM significa gerente de cuenta clave. En los datos entregados se nombran KAM A a KAM F, y «Sin asignar» agrupa las cuentas sin responsable.

**Factor.** Cada señal que aporta puntos al riesgo de un afiliado, con su texto explicativo. La ficha del afiliado los lista de mayor a menor aporte.

**Ficha.** Ventana que se abre al seleccionar un afiliado, con su score, los factores, la acción sugerida y sus datos.

**Habeas data.** Derecho de las personas a conocer, actualizar y rectificar la información que sobre ellas se recoge en bases de datos. En Colombia se desarrolla en la Ley 1581 de 2012.

**JSON.** Formato de texto para intercambiar datos. El pipeline escribe siete archivos JSON en `web/data/` y el tablero los lee.

**localStorage.** Espacio de almacenamiento del navegador, ligado a la dirección del sitio y a cada equipo. Allí se guardan las reglas de alerta y la preferencia de tema.

**NPS.** Indicador de recomendación. Es el porcentaje de promotores menos el de detractores, y va de -100 a 100. El NPS post-evento (85,4) se calcula con 41 respuestas y no representa a la asociación; el de 90 días no tiene respuestas.

**Pesos.** Puntos que cada señal suma al riesgo, definidos en `config/pesos_score.json`.

**Pipeline.** Conjunto de pasos en Python que leen las fuentes, las limpian, las integran, calculan el score y escriben los JSON del tablero.

**Regla.** Expresión formada por una o más condiciones, unidas con Y u O, que se evalúa sobre cada afiliado. Tiene nombre, severidad y, si se desea, un ámbito.

**Riesgo y salud.** El riesgo es la suma de puntos dividida entre el máximo posible (76 con los pesos actuales) y llevada a una escala de 0 a 100. La salud es 100 menos el riesgo.

**Score.** Número que resume la salud o el riesgo de un afiliado, junto con su banda, sus factores y la acción sugerida. Es una medida de asociación con salidas pasadas y no un pronóstico.

**Severidad.** Importancia que el usuario asigna a una regla: alta, media o baja.

**Ventana reciente.** Periodo de 90 días que termina en el último evento registrado (27 de octubre de 2026) y se usa para medir la participación reciente.

**Zoho.** Plataforma de la que ACTHO exporta la base de afiliados, los informes de renovaciones y los de nuevos afiliados.
