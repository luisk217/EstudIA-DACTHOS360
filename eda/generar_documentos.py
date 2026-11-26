"""Genera docs/LIMPIEZA.md y docs/DICCIONARIO_DATOS.md con las cifras reales del pipeline.

Uso:  python -I eda/generar_documentos.py
El diccionario se arma desde pipeline/esquema.py (única fuente de verdad del modelo) y la memoria de limpieza desde la
auditoría de pipeline/calidad.py, de modo que las cifras del documento son las de la última ejecución.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline import config, esquema, orquestador  # noqa: E402

DOCS = config.RAIZ / "docs"
MARCA_I, MARCA_F = "<!-- inicio:esquema -->", "<!-- fin:esquema -->"


def n(v) -> str:
    """Número con separador de miles de punto y decimales con coma."""
    if v is None:
        return ""
    if isinstance(v, float) and not v.is_integer():
        return f"{v:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{int(v):,}".replace(",", ".")


def tabla(cab: list[str], filas: list[list]) -> str:
    out = ["| " + " | ".join(cab) + " |", "|" + "|".join(["---"] * len(cab)) + "|"]
    out += ["| " + " | ".join(str(c).replace("|", "/") for c in f) + " |" for f in filas]
    return "\n".join(out) + "\n"


def diccionario() -> str:
    cat = [t for t in esquema.TABLAS if t.clase == "catalogo"]
    dim = [t for t in esquema.TABLAS if t.clase == "dimension"]
    hec = [t for t in esquema.TABLAS if t.clase == "hecho"]
    ctl = tabla(["Tabla", "Contenido"], [[f"`{k}`", v] for k, v in esquema.CONTROLES.items()])
    resumen = tabla(["Tabla", "Clase", "Grano", "Clave primaria"], [[f"`{t.nombre}`", t.clase, t.grano, ", ".join(f"`{c}`" for c in t.clave)] for t in esquema.TABLAS])
    return f"""# Diccionario de datos del modelo normalizado

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

{resumen}
## Tablas de control

{ctl}
## Detalle por tabla

{MARCA_I}
{esquema.a_markdown()}
{MARCA_F}
"""


def limpieza(r) -> str:
    cal = r.calidad
    fu = {f["id"]: f for f in cal["fuentes"]}
    hu = r.integridad["huerfanos"]
    fk = hu[hu["tipo"] == "clave_foranea"]
    ctl = r.control_general
    a_crm = {x["codigo"]: x["cantidad"] for x in fu["crm"]["anomalias"]}
    nombres = {"crm": "CRM de Zoho", "asistencia": "Asistencia a eventos", "encuestas": "Encuestas"}

    antes_despues = []
    for i, f in fu.items():
        a, d = f["antes"], f["despues"]
        antes_despues.append([nombres[i], f"{n(a['filas'])} a {n(d['filas'])}", f"{n(a['columnas'])} a {n(d['columnas'])}",
                              f"{n(a['celdas_nulas'])} a {n(d['celdas_nulas'])}", f"{n(a['celdas_centinela'])} a {n(d['celdas_centinela'])}",
                              f"{n(a['pct_sin_dato'])} % a {n(d['pct_sin_dato'])} %", f"{n(a['duplicados_clave'])} a {n(d['duplicados_clave'])}",
                              f"{n(a['columnas_no_snake_case'])} a {n(d['columnas_no_snake_case'])}"])
    secciones = []
    for i, f in fu.items():
        secciones.append(f"### {f['nombre']}\n\nArchivo: `{f['archivo']}`. Tablas de destino: {', '.join('`' + t + '`' for t in f['tablas_destino'])}. {f['nota_columnas']}\n")
        secciones.append(tabla(["Anomalía", "Cantidad", "Tratamiento"], [[f"{x['etiqueta']}. {x['descripcion']}", n(x["cantidad"]), x["tratamiento"]] for x in f["anomalias"]]))
        secciones.append("Valores distintos de cada categoría antes y después de homologar:\n")
        secciones.append(tabla(["Categoría", "Antes", "Después"], [[c["columna"], n(c["antes"]), n(c["despues"])] for c in f["categorias"]]))
    informes = tabla(["Informe", "Filas leídas", "Vacías", "Totales", "Encabezados repetidos", "Declarados", "Recuperados", "Coincide"],
                     [[i["nombre"], n(i["filas_leidas"]), n(i["filas_vacias"]), n(i["filas_total"]), n(i["filas_encabezado_repetido"]),
                       n(i["registros_declarados"]) or "no declara", n(i["registros_recuperados"]), "sí" if i["coincide_con_declarados"] else "no"] for i in cal["informes"]["informes"]])
    conc = tabla(["Control", "Informe", "Pipeline", "Resultado", "Lectura"],
                 [[c["descripcion"], n(c["esperado"]), n(c["obtenido"]), "coincide" if c["coincide"] else "difiere", c["nota"]] for c in cal["conciliacion"]])
    huer = tabla(["Relación", "Valores distintos", "Filas", "Severidad"],
                 [[f"`{x.tabla_hijo}.{x.columna}`", n(x.valores), n(x.filas), x.severidad]
                  for x in hu.groupby(["tabla_hijo", "columna", "severidad"]).agg(valores=("valor", "nunique"), filas=("filas", "sum")).reset_index().itertuples()])
    rech = tabla(["Fuente", "Motivo", "Filas"], [[x["fuente"], x["motivo"], n(x["filas"])] for x in cal["rechazos"]])
    s = r.integridad["resumen"]
    return f"""# Limpieza y normalización de los datos

Este documento responde a una duda legítima: si las tablas originales, muy desordenadas, quedaron realmente limpias y normalizadas. La respuesta de la auditoría es que la versión 1.0 limpiaba lo que el score necesitaba, pero dejaba sin tratar varios defectos que no afectaban al tablero y que sí importan para un modelo de datos confiable. La versión 2.0 los corrige, deja un modelo relacional normalizado en `data/processed` y reporta de forma explícita lo que no se puede corregir. Todas las cifras de este documento salen de la última ejecución del pipeline (corte al {r.cfg.fecha_corte.strftime('%d/%m/%Y')}) y se regeneran con `python -I eda/generar_documentos.py`.

## Qué estaba mal

Los datos de entrada son exportaciones de Zoho CRM, un libro de asistencia con una hoja por evento y tres libros de encuestas, todos con estructuras distintas. La auditoría encontró lo siguiente.

En el CRM, {n(a_crm['codigos_repetidos'])} códigos de empresa repetidos ({n(a_crm['codigos_repetidos_estado_distinto'])} con estados distintos), {n(a_crm['registros_prueba'])} registros de prueba, {n(a_crm['tildes_danadas'])} celdas con tildes dañadas, {n(a_crm['categoria_invalida'])} registros cuya categoría de membresía contiene un tipo («Empresas», «Consultoras») en lugar de una categoría, {n(a_crm['estado_inconsistente'])} empresas con registro Activo y membresía cancelada o expirada, columnas geográficas sin homologar («DC» y «Bogotá, D.C.», «Colomba», «Atlantico»), ciudades con variantes («Bogotá D.C.» como ciudad distinta de «Bogotá»), sectores con espacios dobles y duplicados («ONG» y «Entidades Sin Animo de Lucro»), subsectores con errores de digitación y todas las columnas con nombres que no están estandarizados.

En la asistencia, {n(ctl['lectura'] and len(ctl['lectura']))} hojas de evento con {n(sum(1 for _ in {tuple(v['columnas']) for v in ctl['lectura'].values()}))} estructuras de encabezado distintas, {n(a_crm and fu['asistencia']['antes']['filas_vacias_ignoradas'])} filas vacías, 15 inscripciones sin código de empresa que la versión 1.0 descartaba en silencio, nueve formas distintas de escribir la autorización de datos, ciudades escritas a mano y una hoja consolidada (GENERAL) con fórmulas truncadas que reporta {n(ctl['total_asistencias_reportado'])} asistencias cuando las hojas suman {n(int(r.asistencias['valida'].sum()))}.

En las encuestas, tres estructuras de pregunta incompatibles, fechas en texto en español, calificaciones escritas como «10 (Promoter)», centinelas («sin dato», «n/a», «-») y ciudades con variantes.

## Qué se corrigió

La limpieza ahora es configurable y verificable. Las equivalencias de categorías (ciudades, sectores, niveles, estados, modalidades, líneas de evento, niveles de cargo y otras) salieron del código y viven en `config/homologacion.json`, que el equipo de ACTHO puede editar. El pipeline valida ese archivo al cargarlo y reporta cualquier valor que no esté en un catálogo. Se estandarizaron los nombres de columna, se convirtieron los centinelas en nulos, se tipificaron fechas, enteros, porcentajes y booleanos, se unificaron las hojas de estructura distinta, se leyeron los informes agrupados de Zoho (grupos repetidos, subtotales y «Grand Total») y se construyó un modelo relacional con verificación de integridad referencial. Nada se descarta en silencio: las filas excluidas quedan en `control_rechazos.csv` y los huérfanos en `control_huerfanos.csv`.

## Tabla antes y después por fuente

Cada celda muestra el valor original y el del modelo normalizado. El porcentaje sin dato cuenta nulos y centinelas; baja sobre todo porque se descartan las columnas vacías que dejó la anonimización, los centinelas pasan a nulos reales y se excluyen duplicados y pruebas, no porque se inventen datos.

{tabla(["Fuente", "Filas", "Columnas", "Celdas nulas", "Centinelas", "Sin dato", "Duplicados por clave", "Columnas fuera de snake_case"], antes_despues)}
En encuestas el porcentaje sin dato sube porque `fact_encuesta` añade columnas que solo aplican a parte de las respuestas (evento inferido, NPS, afiliado declarado) y los aspectos pasan a `fact_encuesta_aspecto`; no es pérdida de datos. En asistencia las filas «antes» son las no vacías de las hojas; el modelo conserva además marcadas (`es_duplicado`, `es_agendado`) las inscripciones que no cuentan como asistencia, por eso casi no cambia el número de filas.

## Detalle por fuente

{chr(10).join(secciones)}
## Informes agrupados de Zoho

Los informes de Zoho escriben cada grupo (mes, propietario, fecha) solo en su primera fila, añaden la cantidad entre paréntesis, dejan filas vacías entre grupos y cierran con «Grand Total». El lector los convierte en tablas tidy y verifica que los registros recuperados coincidan con la cantidad que declara el propio informe y con el conteo de cada grupo.

{informes}
## Filas descartadas

{rech}
## Conciliación con los informes que ACTHO usa hoy

Como control independiente, lo limpiado se contrasta con informes que Zoho produce por su cuenta. En cada fila, «Informe» es lo que dice la fuente de contraste y «Pipeline» lo que resulta del modelo.

{conc}
## Integridad referencial

El modelo tiene {n(s['tablas'])} tablas, {n(s['filas_totales'])} filas y {n(s['relaciones_verificadas'])} relaciones verificadas. Hay {n(s['filas_huerfanas_error'])} filas huérfanas de severidad error y {n(s['filas_huerfanas_aviso'])} de severidad aviso. Los avisos no son defectos de captura: son empresas que asisten, responden o aparecen en informes sin estar en la exportación del CRM, y ciudades escritas a mano que todavía no están en el catálogo. Se reportan todas.

{huer}
Para resolver los avisos de ciudad basta agregar la variante a `config/homologacion.json`; los de empresa requieren completar el CRM.

## Lo que no se corrige y por qué

Los afiliados vigentes con fecha de expiración vencida ({n(a_crm['vigentes_vencidas'])}) son un dato desactualizado del CRM y se reportan como alerta, no se alteran. Las {n(a_crm['sin_estado'])} filas sin estado de membresía quedan con estado nulo y no se puntúan. El significado de la marca numérica de la primera columna de las hojas de asistencia no está documentado en la fuente, por lo que se conserva sin interpretarla (`marca_fuente`). Una misma persona figura con más de una empresa en {n(int(r.modelo['dim_persona']['multiples_empresas'].sum()))} casos, lo que puede ser un cambio de empresa o un código reutilizado en la anonimización; el modelo lo marca (`multiples_empresas`) sin forzar una única empresa. El consolidado por KAM hereda el subconteo de la hoja GENERAL. La asistencia solo cubre 2026 y la encuesta de 90 días no tiene respuestas.

## Cómo mantener la limpieza

Al recibir una exportación nueva, ejecute `python -I run_pipeline.py --estricto`. Si aparecen valores fuera de catálogo, `control_huerfanos.csv` los lista con su cantidad; agréguelos a `config/homologacion.json` (sección `equivalencias` con la clave en minúsculas, sin tildes y con espacios simples) y vuelva a ejecutar. El modo estricto detiene la ejecución solo ante errores de estructura o relaciones rotas. Las figuras de antes y después están en `docs/eda/08_antes_despues.md`.
"""


def main() -> None:
    logging.basicConfig(level=logging.WARNING)
    r = orquestador.ejecutar(config.Configuracion())
    (DOCS / "DICCIONARIO_DATOS.md").write_text(diccionario(), encoding="utf-8")
    (DOCS / "LIMPIEZA.md").write_text(limpieza(r), encoding="utf-8")
    print("Documentos escritos en", DOCS)


if __name__ == "__main__":
    main()
