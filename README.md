# DACTHO 360

DACTHO 360 es el Tablero Integral de Gestión de Afiliados de ACTHO. Reúne en un solo lugar tres fuentes que hoy viven separadas, el CRM de Zoho, los registros de asistencia a eventos y las encuestas de satisfacción, y las convierte en una vista por afiliado con un score de salud, las razones que lo explican y una acción sugerida para el equipo comercial. El tablero es un sitio estático: no necesita servidor, base de datos ni inicio de sesión, y se puede abrir en cualquier navegador una vez publicados los archivos.

El proyecto se desarrolló con datos anonimizados entregados por ACTHO para el reto. Los afiliados se identifican por un código de empresa (por ejemplo `EMP-0366`) y las ejecutivas por nombres genéricos (`KAM A` a `KAM F`). Con corte al 25 de noviembre de 2026, el modelo integrado contiene 474 afiliados vigentes.

## Cómo funciona en una frase

Un pipeline en Python lee los libros de Excel, los limpia, los cruza por código de empresa, calcula el score y escribe siete archivos JSON; un frontend en HTML, CSS y JavaScript sin dependencias lee esos archivos y los muestra en siete vistas, entre ellas un módulo de alertas configurable por el usuario.

## Estructura de carpetas

```
Acthos-estudIA/
  run_pipeline.py        punto de entrada del pipeline
  pyproject.toml         metadatos y configuración de pytest
  requirements.txt       dependencias para ejecutar el pipeline
  requirements-dev.txt   añade pruebas y reportes de análisis exploratorio
  config/
    pesos_score.json     pesos y umbrales del score, editables sin tocar código
  pipeline/              carga, limpieza, integración, variables, score, validación y exportación
  eda/run_eda.py         genera los reportes de análisis exploratorio
  tests/                 325 pruebas automáticas con datos sintéticos
  web/                   el tablero (sitio estático)
    index.html, css/, js/, fonts/
    data/                JSON generados por el pipeline
  data/processed/        modelo relacional normalizado en CSV, 22 tablas (no se versionan)
  docs/                  documentación; docs/eda tiene los reportes y docs/capturas las imágenes
  Material & Recursos/   fuentes crudas anonimizadas (no se versionan)
```

La carpeta `web/` es lo único que se publica. Todo lo demás existe para producir y documentar los datos que ella consume.

## Inicio rápido de 5 minutos

Se necesita Python 3.11 o superior. Desde la raíz del proyecto instalamos las dependencias, regeneramos los datos y servimos el tablero.

```
pip install -r requirements.txt
python -I run_pipeline.py
cd web
python -m http.server 8000
```

Después abrimos http://localhost:8000 en el navegador. El tablero no funciona abriendo `index.html` con doble clic, porque los navegadores bloquean la lectura de los JSON desde `file://`.

Si solo queremos ver el tablero, el segundo paso no es necesario: los JSON de `web/data/` ya vienen generados con corte al 25 de noviembre de 2026. El pipeline solo hace falta cuando tengamos exportaciones nuevas o cambiemos los pesos del score. Para correr las pruebas, instalamos `requirements-dev.txt` y ejecutamos `python -m pytest`.

El pipeline busca los Excel en `Material & Recursos/Recursos ACTHO`. Para usar otra carpeta, pasamos `--datos "ruta"` o definimos la variable de entorno `ACTHO_DATA_DIR`. La fecha de corte es un parámetro (`--fecha-corte AAAA-MM-DD`) y no se toma del reloj del equipo, de modo que dos ejecuciones con los mismos archivos producen los mismos resultados.

## Requisitos

Para el pipeline, Python 3.11 o superior con `pandas`, `openpyxl` y `numpy`. Para las pruebas y los reportes exploratorios, además `pytest`, `matplotlib` y `pypdf`. Para el tablero basta un navegador actual y cualquier servidor de archivos estáticos; `python -m http.server` es suficiente en local. No se usa Node, ni compilación, ni servicios externos: las fuentes tipográficas están incluidas en `web/fonts/` y los gráficos usan Chart.js 4.5.1 (licencia MIT), incluido en `web/vendor/`.

## Qué contiene el tablero

Siete vistas: resumen ejecutivo, afiliados (con ficha individual del score), ejecutivas, eventos y participación, encuestas y NPS, alertas y metodología. Las reglas de alerta se crean y se evalúan en el navegador de cada persona, y se respaldan exportándolas a un archivo JSON. El detalle de uso está en `docs/MANUAL_USUARIO.md`.

## Resultados clave

Con los datos entregados, 205 afiliados quedan en la banda Saludable, 209 en Atención y 60 en Riesgo alto. De los 474 vigentes, el 78,3 % tiene al menos una asistencia registrada en 2026 y el 21,7 % ninguna. Solo el 33,1 % tiene alguna respuesta de encuesta, y apenas el 4,9 % tiene una respuesta con calificación de recomendación, de modo que la satisfacción por afiliado es parcial. El pipeline recalcula 3.292 asistencias válidas a partir de las 34 hojas de evento, porque la hoja consolidada del libro original tiene rangos truncados y omite una columna de evento.

El score se contrastó con 33 empresas que salieron entre abril y noviembre de 2026. Su área bajo la curva ROC fue de 0,77 (intervalo de 95 % de 0,69 a 0,85), y la tasa de salida fue de 2,4 % en el tercil de menor riesgo, 3,0 % en el medio y 14,2 % en el de mayor riesgo. Conviene leer estas cifras con cuidado: muestran que el score se asocia con las salidas pasadas, no que prediga las futuras. Hay pocos casos de salida, la asistencia solo existe desde enero de 2026 y no se conoce la fecha real de cancelación. Antes de automatizar cualquier decisión sobre un afiliado, el modelo debe recalibrarse con más historia.

El NPS post-evento es de 85,4, pero se basa en 41 respuestas, con 35 promotores, 6 pasivos y ningún detractor. No es el NPS de la asociación. La encuesta de 90 días, que sí lo mediría, todavía no tiene respuestas.

## Documentación

`docs/ARQUITECTURA.md` explica el flujo y las decisiones de diseño. `docs/MANUAL_USUARIO.md` está escrito para el equipo comercial. `docs/GUIA_DESPLIEGUE.md` cubre la ejecución local, la actualización mensual y la publicación gratuita, con un apartado sobre confidencialidad y protección de datos personales. `docs/MANTENIMIENTO.md` trata los pesos, las nuevas fuentes y el plan de evolución. `docs/GLOSARIO.md` define los términos, y `CHANGELOG.md` registra los cambios. El detalle técnico del pipeline está en `docs/PIPELINE.md` y los análisis exploratorios en `docs/eda/`.

## Confidencialidad

Los archivos fuente están sujetos al acuerdo de confidencialidad del reto y por eso `.gitignore` los excluye. Los JSON de `web/data/` contienen únicamente códigos anonimizados y cifras agregadas. Antes de publicar el tablero con cualquier otro conjunto de datos, leemos el apartado de confidencialidad de `docs/GUIA_DESPLIEGUE.md`.
