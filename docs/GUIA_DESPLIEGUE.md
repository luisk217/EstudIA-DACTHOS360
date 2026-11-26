# Guía de despliegue

Esta guía explica cómo ejecutar DACTHO 360 en un computador, cómo actualizar los datos cada mes y cómo publicar el tablero sin costo. Quedan fuera de este documento los trámites de publicación en sí: no hemos desplegado nada, y quien lo haga debe leer antes el apartado de confidencialidad, que condiciona qué datos se pueden poner en internet.

## Ejecución local

Necesitamos Python 3.11 o superior. Desde la raíz del proyecto:

```
pip install -r requirements.txt
python -I run_pipeline.py
cd web
python -m http.server 8000
```

El primer comando instala `pandas`, `openpyxl` y `numpy`. El segundo lee los Excel y escribe los siete JSON en `web/data/` y cinco CSV intermedios en `data/processed/`. El tercero y el cuarto sirven el tablero en http://localhost:8000. No se puede abrir `web/index.html` directamente desde el explorador de archivos, porque el navegador bloquea la lectura de los JSON bajo `file://`; el tablero lo detecta y muestra un mensaje que explica cómo proceder.

El pipeline busca las exportaciones en `Material & Recursos/Recursos ACTHO`. Si están en otra parte, se indica con `--datos "ruta"` o con la variable de entorno `ACTHO_DATA_DIR`. El parámetro `--fecha-corte AAAA-MM-DD` fija la fecha de referencia, y `--salida-web` cambia la carpeta donde se escriben los JSON, algo útil para probar una ejecución sin tocar los archivos publicados. El valor por omisión de la fecha de corte es el 25 de noviembre de 2026, y no la fecha del sistema, para que los resultados sean reproducibles.

Conviene verificar la instalación con `python -m pytest` después de instalar `requirements-dev.txt`; las 20 pruebas usan datos sintéticos y tardan menos de un segundo.

## Actualización mensual de los datos

La rutina completa está en `docs/MANTENIMIENTO.md`; aquí damos el resumen operativo. Cada mes se exportan desde Zoho y desde los libros de asistencia y encuestas los mismos archivos que entregó ACTHO, se colocan con los mismos nombres y carpetas dentro de la carpeta de datos y se ejecuta el pipeline con la nueva fecha de corte:

```
python -I run_pipeline.py --fecha-corte 2026-12-31
```

Si los nombres de los archivos cambian, debe actualizarse el diccionario `FUENTES` de `pipeline/config.py`. Tras la ejecución se revisa la tabla de avisos de calidad en la vista de metodología, porque un aviso que antes no existía suele delatar un cambio de formato en la fuente. También se comprueba que el número de afiliados vigentes sea coherente con el informe del CRM. Por último, se vuelve a publicar la carpeta `web/`. Quienes usen el tablero ven los datos nuevos al recargar la página, y sus reglas de alerta se conservan porque viven en el navegador.

Dos advertencias prácticas. La fecha de corte que se cambia en la línea de comandos no modifica el texto «Corte: 25 de noviembre de 2026» del pie del menú lateral (`web/js/main.js`), ni las menciones fijas al 27 de octubre y a «octubre y noviembre de 2026» que aparecen en `web/js/vistas/eventos.js`, `resumen.js`, `encuestas.js` y `metodologia.js`; hay que revisarlas y actualizarlas a mano. Y si los libros de asistencia nuevos cubren más meses, la ventana de participación reciente se desplaza sola, porque se calcula desde el último evento registrado.

## Opciones gratuitas de publicación

Como el tablero es un sitio estático, cualquier servicio que sirva archivos sirve. Describimos dos, con la salvedad de que los planes gratuitos y sus condiciones cambian y deben confirmarse en la documentación vigente de cada proveedor antes de decidir.

### GitHub Pages

Se crea un repositorio con el contenido de la carpeta `web/` en su raíz (o se publica `web/` mediante una acción de GitHub), y en la configuración del repositorio se activa Pages sobre la rama elegida. La dirección resultante tiene la forma `https://usuario.github.io/repositorio/`. Las rutas del tablero son relativas, de modo que funciona bien dentro de un subdirectorio. Cada actualización consiste en reemplazar los JSON de `data/` y confirmar el cambio. Una limitación importante: en el plan gratuito, Pages publica desde repositorios públicos, y cualquier persona con el enlace puede ver el sitio y también el historial de archivos del repositorio. Esto es aceptable con datos anonimizados y no lo es con datos reales.

### Netlify

Se crea un sitio nuevo, se arrastra la carpeta `web/` a la página de despliegues manuales o se conecta un repositorio, sin comando de compilación y con `web` como directorio de publicación. Netlify entrega una dirección propia y permite asignar un dominio. Cada actualización se hace volviendo a arrastrar la carpeta o enviando un cambio al repositorio. Los controles de acceso del sitio, como la protección con contraseña, suelen estar en planes de pago; si se necesitan, hay que verificarlo antes de elegir esta opción.

Una tercera vía, la más conservadora, es no publicar nada en internet y servir `web/` desde un computador o servidor de la red interna de ACTHO con `python -m http.server` o con cualquier servidor web. Con eso los datos no salen de la organización.

## Confidencialidad y protección de datos

Este apartado es el más importante de la guía. Lo que publiquemos queda accesible a cualquiera que tenga la dirección, y los JSON de `web/data/` contienen, además de cifras agregadas, una fila por afiliado con su sector, ciudad, nivel, ejecutiva, fechas, asistencia y satisfacción.

**Demostraciones públicas.** Un sitio abierto en internet solo debe contener datos anonimizados o seudonimizados. En esta entrega los afiliados aparecen como `EMP-xxxx`, las ejecutivas como `KAM A` a `KAM F` y no hay nombres de personas, NIT ni correos. Aun así, recordamos que la seudonimización no es lo mismo que la anonimización: si ACTHO conserva una tabla que relaciona los códigos con las empresas reales, quien la tenga puede reidentificarlas, y la combinación de sector, ciudad, tamaño y fechas puede apuntar a una empresa conocida en un nicho pequeño. Antes de publicar una demostración, conviene revisar `web/data/afiliados.json` buscando combinaciones poco comunes, y considerar si ofrece algo adicional a una versión más agregada. Además, los archivos Excel originales y los CSV de `data/processed/` no deben subirse nunca; `.gitignore` ya los excluye, y esa exclusión debe mantenerse en cualquier repositorio nuevo. Los datos de entrega están sujetos al acuerdo de confidencialidad del reto, y cualquier publicación debe contar con la autorización de ACTHO.

**Datos reales.** Si ACTHO quisiera usar el tablero con los datos reales de sus afiliados, un enlace público no es admisible. El sitio debe quedar detrás de un control de acceso: una red interna, una VPN, o un servicio que exija autenticación de cada persona (por ejemplo, un proxy con inicio de sesión de la organización o la protección de acceso que ofrezca el hosting elegido en su plan correspondiente). También hay que pensar en el historial de versiones, porque un repositorio que alguna vez contuvo datos reales los conserva aunque se borren después. La restricción debe cubrir los archivos JSON, no solo la página de entrada, porque basta conocer la ruta de un JSON para descargarlo. Y debemos recordar que el tablero guarda las reglas en el navegador de cada persona y que los CSV exportados salen del control del sitio, por lo que los equipos de quienes lo usan también hacen parte del perímetro de seguridad.

**Habeas data en Colombia.** El tratamiento de datos personales en Colombia se rige por la Ley 1581 de 2012 y sus decretos reglamentarios, y la autoridad de control es la Superintendencia de Industria y Comercio. Las empresas, como personas jurídicas, no son titulares de datos personales en el sentido de la ley, pero los datos de las personas que trabajan en ellas sí lo son: nombres, correos, cargos y la asistencia a eventos de cada persona. Esta última información existe en los libros de origen, aunque el pipeline no la lleva a los JSON del tablero. Si ACTHO extiende el tablero para mostrar personas, o si publica los libros de asistencia, debe asegurarse de contar con autorización previa, expresa e informada de los titulares, de que la finalidad del tratamiento sea la informada, de aplicar medidas de seguridad proporcionales y de atender las solicitudes de consulta, corrección y supresión. También debe verificar si debe inscribir las bases de datos en el Registro Nacional de Bases de Datos y mantener actualizada su política de tratamiento. Este texto es orientación técnica y no reemplaza la opinión del área jurídica o del oficial de protección de datos de ACTHO, a quien recomendamos consultar antes de cualquier uso con datos reales.

## Lista de verificación antes de publicar

Antes de poner el sitio en línea comprobamos que `web/` no contiene Excel ni CSV; que los JSON corresponden a datos anonimizados y fueron revisados; que el repositorio, si existe, no tiene datos reales en su historial; que el sitio abre sin errores en la consola; y que ACTHO conoce y autorizó la publicación. Si alguna respuesta es negativa, se pospone el despliegue.
