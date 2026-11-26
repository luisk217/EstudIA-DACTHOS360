"""Auditoría de calidad de los datos: métricas antes y después de la limpieza, anomalías corregidas y conciliación entre fuentes.

``auditar`` recibe el ``Resultado`` del pipeline y devuelve un diccionario serializable con, por fuente, el perfil
de la tabla original (filas, columnas, nulos, centinelas, duplicados, nombres de columna no estandarizados) frente al
de la tabla del modelo normalizado, la lista de anomalías corregidas con su cantidad real y el número de valores distintos
de cada categoría antes y después de homologarla. ``conciliar`` contrasta lo limpiado con los informes de Zoho que
ACTHO usa hoy, como control independiente. Nada se calcula con supuestos: todas las cifras salen de los archivos.
"""
from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any

import pandas as pd

from . import carga, config
from . import limpieza as lp

if TYPE_CHECKING:  # pragma: no cover
    from .orquestador import Resultado

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Perfil genérico de una tabla
# ---------------------------------------------------------------------------

def _celdas(df: pd.DataFrame, f: Any) -> int:
    """Cuenta las celdas de texto que cumplen la condición ``f``."""
    return int(df.map(lambda v: isinstance(v, str) and bool(f(v))).sum().sum()) if df.size else 0


def perfil(df: pd.DataFrame, clave: str | list[str] | None = None, excluir: tuple[str, ...] = ()) -> dict[str, Any]:
    """Perfil de calidad de una tabla: tamaño, nulos, centinelas, duplicados y nombres de columna no estandarizados."""
    d = df.drop(columns=[c for c in excluir if c in df.columns])
    n, k = d.shape
    vacia = d.isna() | d.map(lambda v: isinstance(v, str) and not v.strip())
    nulas = int(vacia.sum().sum()) if d.size else 0
    cent = _celdas(d, lp.es_centinela)
    celdas = n * k
    return {
        "filas": int(n), "columnas": int(k), "celdas": int(celdas), "celdas_nulas": nulas, "celdas_centinela": cent,
        "pct_sin_dato": round(100 * (nulas + cent) / celdas, 1) if celdas else 0.0,
        "columnas_vacias": int(vacia.all().sum()) if n else int(k),
        "duplicados_exactos": int(d.astype(str).duplicated().sum()) if n else 0,
        "duplicados_clave": int(df.duplicated(clave).sum()) if clave and n else None,
        "columnas_no_snake_case": int(sum(not lp.es_snake_case(c) for c in d.columns)),
    }


def _distintos(*series: pd.Series) -> int:
    """Valores distintos (no nulos, no centinela) de una o varias columnas, tal como están escritos."""
    vals: set[str] = set()
    for s in series:
        vals |= {str(v).strip() for v in s.dropna().unique() if not lp.es_centinela(v) and str(v).strip()}
    return len(vals)


#: Etiquetas cortas (con tildes) de cada anomalía, para gráficos y tablas.
ETIQUETAS: dict[str, str] = {
    "columnas_vacias": "Columnas vacías", "nombres_no_estandar": "Nombres de columna sin estandarizar", "tildes_danadas": "Tildes dañadas",
    "espacios_sobrantes": "Espacios sobrantes", "registros_prueba": "Registros de prueba", "codigos_repetidos": "Códigos de empresa repetidos",
    "codigos_repetidos_estado_distinto": "Repetidos con estado distinto", "sin_estado": "Sin estado de membresía", "categoria_invalida": "Categoría mal digitada",
    "estado_inconsistente": "Estado inconsistente", "fecha_afiliacion_imposible": "Fecha de afiliación imposible", "propietario_cero": "Propietario «0»",
    "booleanos_en_texto": "Booleanos en texto", "porcentajes_en_texto": "Porcentajes en texto", "contadores_en_texto": "Contadores en texto",
    "vigentes_vencidas": "Vigentes con fecha vencida", "estructuras_distintas": "Hojas con estructura distinta", "celdas_combinadas": "Hojas con celdas combinadas",
    "filas_vacias": "Filas vacías", "filas_sin_codigo_empresa": "Filas sin código de empresa", "filas_total_o_encabezado": "Totales o encabezados repetidos",
    "duplicados_persona_evento": "Duplicados persona y evento", "agendados": "Registros agendados", "variantes_autorizacion": "Variantes de autorización",
    "nivel_cargo_sin_dato": "Nivel de cargo «Sin dato»", "costo_vacio": "Costo vacío", "hojas_sin_lista": "Hoja sin lista de asistentes",
    "general_rangos_truncados": "GENERAL: rangos truncados", "general_columnas_sin_formula": "GENERAL: columnas sin fórmula",
    "general_totales_truncados": "GENERAL: totales truncados", "general_total_reportado": "GENERAL: total reportado",
    "general_empresas_no_listadas": "GENERAL: empresas no listadas", "tres_estructuras": "Tres estructuras de encuesta", "fechas_en_texto": "Fechas en texto",
    "escala_con_texto": "NPS escrito con texto", "variantes_ciudad": "Variantes de ciudad", "centinelas_en_texto": "Centinelas en texto",
    "respuestas_sin_empresa": "Respuestas sin empresa", "respuestas_sin_evento": "Respuestas sin evento", "respuestas_2025": "Respuestas de 2025",
    "encuesta_90_sin_respuestas": "Encuesta de 90 días sin respuestas", "campos_texto_libre": "Texto libre excluido",
}


def _anomalia(codigo: str, descripcion: str, cantidad: int | float, tratamiento: str) -> dict[str, Any]:
    return {"codigo": codigo, "etiqueta": ETIQUETAS.get(codigo, codigo), "descripcion": descripcion,
            "cantidad": int(cantidad) if float(cantidad).is_integer() else cantidad, "tratamiento": tratamiento}


def _flags(tabla: str) -> tuple[str, ...]:
    """Columnas de bandera de una tabla del modelo (no vienen de la fuente, por lo que se excluyen del perfil de nulos)."""
    from . import esquema  # noqa: PLC0415
    return tuple(c.nombre for c in esquema.ESQUEMA[tabla].columnas if c.descripcion.startswith("Bandera"))


# ---------------------------------------------------------------------------
# Fuentes
# ---------------------------------------------------------------------------

def _crm(res: "Resultado") -> dict[str, Any]:
    raw, crm, emp, st = res.crm_completo, res.crm, res.empresas, res.stats_crm
    m = res.modelo
    af = m["dim_afiliado"]
    antes = perfil(raw, "Nombre de Empresa [anonimizado]")
    despues = perfil(af, "empresa_id", excluir=_flags("dim_afiliado"))
    despues["tablas_destino"] = 3
    mal = lambda c: c in raw  # noqa: E731
    sin_estado = int((crm["estado"] == "Sin estado").sum())
    vig = emp[emp["vigente"]]
    anom = [
        _anomalia("columnas_vacias", "Columnas completamente vacías (eliminadas por la anonimización: NIT, teléfono, correos y otras).", antes["columnas_vacias"], f"Se descartan; quedan {res.controles['crm']['columnas_utiles']} columnas útiles."),
        _anomalia("nombres_no_estandar", "Nombres de columna con mayúsculas, tildes, espacios o etiquetas como «[anonimizado]».", antes["columnas_no_snake_case"], "Se renombran a snake_case sin tildes."),
        _anomalia("tildes_danadas", "Celdas con tildes dañadas por codificación (por ejemplo «Bogotﾃ｡»).", _celdas(raw, lambda v: bool(lp._PAT_MOJIBAKE.search(v))), "Se reparan reinterpretando los bytes como UTF-8."),
        _anomalia("espacios_sobrantes", "Celdas con espacios al inicio, al final o dobles.", _celdas(raw, lambda v: v != re.sub(r"\s+", " ", v).strip()), "Se colapsan y se recortan."),
        _anomalia("registros_prueba", "Registros de prueba (etiqueta «Prueba»).", st["registros_de_prueba"], "Se excluyen y se listan en control_rechazos."),
        _anomalia("codigos_repetidos", "Filas con un código de empresa ya usado por otro registro.", st["filas_duplicadas_descartadas"], "Se conserva un registro por empresa (vigente, con estado, con vencimiento, más completo)."),
        _anomalia("codigos_repetidos_estado_distinto", "Empresas repetidas cuyos registros tienen estados de membresía distintos.", st["empresas_con_duplicado_y_estados_distintos"], "Se prefiere el registro vigente."),
        _anomalia("sin_estado", "Registros sin estado de membresía.", sin_estado, "Quedan con estado nulo; no se puntúan."),
        _anomalia("categoria_invalida", "Registros cuya «categoría de membresía» trae un tipo («Empresas», «Consultoras», «Plus»...) en lugar de una categoría.", int(crm["categoria_invalida"].sum()), "Se anula la categoría y el nivel se infiere del tipo de membresía cuando es posible."),
        _anomalia("estado_inconsistente", "Empresas con registro Activo pero membresía cancelada, expirada o inactiva.", int(emp["estado_inconsistente"].sum()), "Se marcan con bandera; manda el estado de la membresía."),
        _anomalia("fecha_afiliacion_imposible", "Fechas de afiliación posteriores al corte (año 2066).", int(crm["fecha_afiliacion_invalida"].sum()), "Se descartan (nulo) y se marcan con bandera."),
        _anomalia("propietario_cero", "Propietarios con el centinela «0».", int((raw["Propietario de Empresa [anonimizado]"] == "0").sum()), "Pasan a «Sin asignar»."),
        _anomalia("booleanos_en_texto", "Celdas Sí/No o true/false escritas como texto.", int(raw["Vinculado a Comunidades"].notna().sum() + raw["Independiente"].notna().sum()), "Se convierten a booleano."),
        _anomalia("porcentajes_en_texto", "Porcentajes escritos como texto («50%»).", int(raw["% de Mujeres en la Compañía"].notna().sum()), "Se convierten a número de 0 a 100."),
        _anomalia("contadores_en_texto", "Contadores de comunidades y de miembros guardados como texto.", int(sum(raw[c].notna().sum() for c in ("HR Estratégico", "Mas que un Salario", "Talento que Elige", "Gente que Crece", "Mujeres HR", "Influenciador", "Cantidad Miembros") if c in raw)), "Se convierten a entero; las comunidades pasan a filas (fact_comunidad_afiliado)."),
        _anomalia("vigentes_vencidas", "Afiliados vigentes cuya fecha de expiración ya pasó (dato desactualizado en el CRM, no se corrige).", int((vig["fecha_expiracion"] < pd.Timestamp(res.cfg.fecha_corte)).sum()), "Se conservan y se reportan como alerta de captura."),
    ]
    pares = [("ciudad", ("Ciudad", "Ciudad de facturación"), ("ciudad", "ciudad_facturacion")), ("sector", ("Sector Económico",), ("sector",)),
             ("subsector", ("Subsector Económico [anonimizado]",), ("subsector",)), ("rango_empleados", ("Cantidad de Empleados",), ("rango_empleados",)),
             ("categoria_membresia", ("Categoría de Membresía",), ("categoria_membresia",)), ("tipo_membresia", ("Tipo de Membresía",), ("tipo_membresia",)),
             ("estado_membresia", ("Estado de la Membresía",), ("estado_membresia",)), ("region", ("Región",), ("region",)),
             ("departamento", ("Departamento",), ("departamento",)), ("pais", ("País de facturación",), ("pais",)),
             ("ejecutiva", ("Propietario de Empresa [anonimizado]",), ("ejecutiva_id",)), ("nivel", ("Categoría de Membresía",), ("nivel",))]
    cats = [{"columna": n, "antes": _distintos(*[raw[c] for c in cr if mal(c)]), "despues": _distintos(*[af[c] for c in cd])} for n, cr, cd in pares]
    return {"id": "crm", "nombre": "CRM de Zoho (Base de datos de afiliados)", "archivo": "1. Base de datos de afiliados/Base de datos Hackaton_anonimizada.xlsx",
            "tablas_destino": ["dim_afiliado", "fact_comunidad_afiliado", "dim_ejecutiva"], "antes": antes, "despues": despues, "anomalias": anom, "categorias": cats,
            "nota_columnas": "Las columnas del CRM se reparten en dim_afiliado (atributos) y fact_comunidad_afiliado (seis columnas de comunidades pasadas a filas)."}


def _estructura_asistencia(ctl: dict[str, Any]) -> tuple[int, int, int]:
    """(hojas de evento leídas, estructuras de encabezado distintas, columnas distintas entre todas las hojas)."""
    lect = ctl.get("lectura", {})
    estructuras = {tuple(v.get("columnas", [])) for v in lect.values()}
    columnas = {c for v in lect.values() for c in v.get("columnas", [])}
    return len(lect), len(estructuras), len(columnas)


def _asistencia(res: "Resultado") -> dict[str, Any]:
    ctl, raw, a = res.control_general, res.asistencias_raw, res.asistencias
    fa = res.modelo["fact_asistencia"]
    hojas, estructuras, cols_distintas = _estructura_asistencia(ctl)
    leidas = sum(v["filas_leidas"] for v in ctl["lectura"].values())
    vacias = sum(v["filas_vacias"] for v in ctl["lectura"].values())
    no_vacias = leidas - vacias
    antes = perfil(raw, None)
    antes.update({"filas_perfil": antes["filas"], "filas": int(no_vacias), "hojas": hojas, "estructuras_de_encabezado": estructuras, "columnas": cols_distintas, "filas_vacias_ignoradas": int(vacias)})
    despues = perfil(fa, "asistencia_id")
    validas = fa[fa["es_valida"]]
    despues.update({"hojas": 1, "estructuras_de_encabezado": 1,
                    "duplicados_clave": int(validas.duplicated(["evento_id", "persona_id"]).sum()), "duplicados_marcados": int(fa["es_duplicado"].sum()),
                    "duplicados_exactos": int(validas.duplicated().sum())})
    antes["duplicados_clave"] = int(a["duplicado"].sum())
    n_aut = raw["autoriza_datos"].dropna().map(lambda v: str(v)).nunique()
    anom = [
        _anomalia("estructuras_distintas", f"Hojas de evento con {estructuras} estructuras de encabezado distintas (columnas en otro orden, otro nombre o ausentes).", hojas, "Se ubican las columnas por su texto y se unifican en una sola tabla."),
        _anomalia("celdas_combinadas", "Hojas con celdas combinadas (título del evento sobre el encabezado).", sum(v.get("celdas_combinadas", 0) > 0 for v in ctl["lectura"].values()), "Se localiza el encabezado «ID_EMPRESA» y se descartan las filas previas."),
        _anomalia("filas_vacias", "Filas vacías de las hojas (las hojas llegan a 1.000 filas con pocas filas llenas).", vacias, "Se ignoran."),
        _anomalia("filas_sin_codigo_empresa", "Inscripciones con persona pero sin código de empresa.", sum(v["filas_sin_codigo"] for v in ctl["lectura"].values()), "Se descartan y se listan una a una en control_rechazos."),
        _anomalia("filas_total_o_encabezado", "Totales o encabezados repetidos mezclados con los datos.", sum(v["filas_total"] + v["filas_encabezado_repetido"] for v in ctl["lectura"].values()), "Se descartan (hoy no hay ninguno)."),
        _anomalia("duplicados_persona_evento", "Inscripciones repetidas de la misma persona en el mismo evento.", int(a["duplicado"].sum()), "Se conservan marcadas (es_duplicado) y no cuentan como asistencia."),
        _anomalia("agendados", "Registros solo agendados que no asistieron.", int(a["agendado"].sum()), "Se conservan marcados (es_agendado) y no cuentan como asistencia."),
        _anomalia("variantes_autorizacion", "Formas distintas de escribir la autorización de datos (SI, Sí, SÍ, «SÍ, AUTORIZO...»).", n_aut, "Se convierten a booleano."),
        _anomalia("nivel_cargo_sin_dato", "Niveles de cargo con el centinela «Sin dato».", int((a["nivel_cargo"] == "Sin dato").sum()), "Pasan a nulo en el modelo."),
        _anomalia("costo_vacio", "Inscripciones sin indicar si fueron con costo o sin costo.", int(raw["costo"].isna().sum()), "Quedan nulas."),
        _anomalia("hojas_sin_lista", "Hojas de evento sin lista de asistentes (febrero 13).", len(ctl.get("hojas_sin_encabezado", [])), "El evento se conserva con tiene_asistentes en falso."),
        _anomalia("general_rangos_truncados", "Columnas de la hoja consolidada GENERAL cuya fórmula no cubre todas las filas de su hoja.", len(ctl.get("columnas_con_rango_truncado", [])), "No se usa GENERAL: la asistencia se recuenta hoja por hoja."),
        _anomalia("general_columnas_sin_formula", "Columnas de evento de GENERAL sin fórmula.", len(ctl.get("columnas_evento_sin_formula", [])), "Se recuentan desde las hojas."),
        _anomalia("general_totales_truncados", "Sumas de la fila de totales de GENERAL que no cubren todas las empresas listadas.", ctl.get("sumas_con_rango_truncado", 0), "Se recalculan desde las hojas."),
        _anomalia("general_total_reportado", "Asistencias que reporta GENERAL (frente a las que se cuentan en las hojas).", ctl.get("total_asistencias_reportado", 0), f"Se reemplaza por el recuento real: {int(a['valida'].sum())} asistencias válidas."),
        _anomalia("general_empresas_no_listadas", "Empresas con asistencia real que GENERAL no lista.", ctl.get("empresas_con_asistencia_real_no_listadas", 0), "Se incluyen en el recuento desde las hojas."),
    ]
    cats = [
        {"columna": "nivel_cargo", "antes": _distintos(raw["nivel_cargo"]) + int(raw["nivel_cargo"].map(lp.es_centinela).any()), "despues": _distintos(fa["nivel_cargo"])},
        {"columna": "autoriza_datos", "antes": n_aut, "despues": int(fa["autoriza_datos"].nunique())},
        {"columna": "ciudad", "antes": _distintos(raw["ciudad"]), "despues": _distintos(fa["ciudad"])},
        {"columna": "linea_evento", "antes": _distintos(res.eventos["linea"]), "despues": _distintos(res.modelo["dim_evento"]["linea"])},
        {"columna": "modalidad_evento", "antes": _distintos(res.eventos["modalidad"]), "despues": _distintos(res.modelo["dim_evento"]["modalidad"])},
    ]
    return {"id": "asistencia", "nombre": "Asistencia a eventos 2026 (34 hojas más GENERAL y HOMOLOGACION)", "archivo": "2. Registros de participación en actividades/BASE ASISTENCIA A EVENTOS 2026 - EAFIT_anonimizada.xlsx",
            "tablas_destino": ["fact_asistencia", "dim_evento", "dim_persona"], "antes": antes, "despues": despues, "anomalias": anom, "categorias": cats,
            "nota_columnas": "«Columnas» antes cuenta los nombres de columna distintos entre todas las hojas; los datos personales eliminados por la anonimización no se cuentan en el perfil."}


def _encuestas(res: "Resultado") -> dict[str, Any]:
    cfg = res.cfg
    crudas = {k: pd.read_excel(cfg.ruta_fuente(k), sheet_name="Responses", header=1, dtype=str).dropna(how="all")
              for k in ("enc_presencial", "enc_virtual", "enc_post")}
    antes_df = pd.concat([d.add_prefix(f"{k}__") for k, d in crudas.items()], axis=1)
    filas_antes = sum(len(d) for d in crudas.values())
    cols_antes = sum(d.shape[1] for d in crudas.values())
    celdas = sum(d.size for d in crudas.values())
    nulas = sum(int((d.isna() | d.map(lambda v: isinstance(v, str) and not v.strip())).sum().sum()) for d in crudas.values())
    cent = sum(_celdas(d, lp.es_centinela) for d in crudas.values())
    dup_clave = sum(int(d.iloc[:, 1].duplicated().sum()) for d in crudas.values())
    antes = {
        "filas": filas_antes, "columnas": cols_antes, "celdas": celdas, "celdas_nulas": nulas, "celdas_centinela": cent,
        "pct_sin_dato": round(100 * (nulas + cent) / celdas, 1), "columnas_vacias": sum(int(d.isna().all().sum()) for d in crudas.values()),
        "duplicados_exactos": sum(int(d.astype(str).duplicated().sum()) for d in crudas.values()), "duplicados_clave": dup_clave,
        "columnas_no_snake_case": sum(int(sum(not lp.es_snake_case(c) for c in d.columns)) for d in crudas.values()),
        "libros": 3,
    }
    fe = res.modelo["fact_encuesta"]
    asp, tema = res.modelo["fact_encuesta_aspecto"], res.modelo["fact_encuesta_tema"]
    despues = perfil(fe, "respuesta_id")
    despues.update({"filas_aspecto": len(asp), "filas_tema": len(tema), "libros": 1})
    r = res.respuestas
    ciudades_raw = pd.concat([crudas["enc_presencial"].iloc[:, 14], crudas["enc_virtual"].iloc[:, 14],
                              crudas["enc_post"][[c for c in crudas["enc_post"].columns if c.startswith("6.")][0]]])
    fechas = pd.concat([crudas["enc_presencial"].iloc[:, 3], crudas["enc_virtual"].iloc[:, 3],
                        crudas["enc_post"][[c for c in crudas["enc_post"].columns if c.startswith("Respuesta completada")][0]]])
    post_c = [c for c in crudas["enc_post"].columns if c.startswith("14.")][0]
    anom = [
        _anomalia("tres_estructuras", "Tres libros de encuesta con estructuras de pregunta distintas (4 aspectos, 4 aspectos y 7 aspectos más NPS).", 3, "Se unifican en fact_encuesta y los aspectos pasan a filas (fact_encuesta_aspecto)."),
        _anomalia("fechas_en_texto", "Fechas en texto en español de Zoho Survey («oct. 21, 2026 09:22:34 a. m.»).", int(fechas.notna().sum()), "Se convierten a fecha."),
        _anomalia("escala_con_texto", "Calificaciones NPS escritas con texto («10 (Promoter)»).", int(crudas["enc_post"][post_c].notna().sum()), "Se extrae el número y se clasifica en Promotor, Pasivo o Detractor."),
        _anomalia("variantes_ciudad", "Ciudades escritas a mano con variantes («Bogota», «Bogotá, Bogotá D.C., Colombia»).", _distintos(ciudades_raw), f"Se homologan; quedan {_distintos(fe['ciudad'])} valores distintos."),
        _anomalia("centinelas_en_texto", "Celdas con centinelas («sin dato», «n/a», «-», «ninguno», «no aplica»).", cent, "Pasan a nulo."),
        _anomalia("respuestas_sin_empresa", "Respuestas en las que no se pudo identificar la empresa.", int(r["empresa_id"].isna().sum()), "Se conservan con empresa nula."),
        _anomalia("respuestas_sin_evento", "Respuestas que no se pudieron asignar a un evento 2026 (2025, ambiguas o fuera de ventana).", int(r["evento_id"].isna().sum()), "Se conservan con evento nulo y el método registrado."),
        _anomalia("respuestas_2025", "Respuestas de 2025 (la asistencia solo cubre 2026).", int((r["anio"] == 2025).sum()), "Se conservan para la satisfacción por empresa."),
        _anomalia("encuesta_90_sin_respuestas", "Respuestas en la encuesta de 90 días.", res.encuesta_90_n, "Se documenta que no hay datos para el NPS de la asociación."),
        _anomalia("campos_texto_libre", "Respuestas con temas solicitados en texto libre (no se publican).", int(crudas["enc_presencial"].iloc[:, 10].notna().sum() + crudas["enc_virtual"].iloc[:, 10].notna().sum()), "Se excluyen del modelo por privacidad."),
    ]
    cats = [
        {"columna": "ciudad", "antes": _distintos(ciudades_raw), "despues": _distintos(fe["ciudad"])},
        {"columna": "nivel_cargo (post-evento)", "antes": _distintos(crudas["enc_post"][[c for c in crudas["enc_post"].columns if c.startswith("5.")][0]]), "despues": _distintos(crudas["enc_post"][[c for c in crudas["enc_post"].columns if c.startswith("5.")][0]].map(lp.normalizar_nivel_cargo))},
    ]
    return {"id": "encuestas", "nombre": "Encuestas de eventos (presencial, virtual y post-evento)", "archivo": "3. Encuestas y NPS/ (tres libros)",
            "tablas_destino": ["fact_encuesta", "fact_encuesta_aspecto", "fact_encuesta_tema"], "antes": antes, "despues": despues, "anomalias": anom, "categorias": cats,
            "nota_columnas": "«Antes» suma los tres libros (55 columnas del post-evento incluidas); «después» es fact_encuesta, con los aspectos y los temas en tablas aparte."}


def _informes(res: "Resultado") -> dict[str, Any]:
    """Informes agrupados de Zoho: se cuenta lo que traían (grupos, separadores y totales) frente a los registros recuperados."""
    nombres = {
        "renovaciones": ("Renovaciones de los últimos 2 meses", res.renovaciones, "fact_renovacion"),
        "afiliaciones": ("Afiliaciones de los últimos 2 meses", res.afiliaciones_recientes, "fact_afiliacion_nueva"),
        "nuevos": ("Nuevos afiliados de agosto y septiembre", res.nuevos, "fact_afiliacion_nueva"),
        "oportunidades": ("Estados de oportunidades ganadas por KAM", res.oportunidades, "fact_oportunidad_ganada"),
        "segmento": ("Informe por segmento Elite y Premium", res.segmento, "(control)"),
        "subsectores": ("Informe por subsectores", res.subsectores_informe, "(control)"),
        "membresias": ("Informe de membresías (con subtotales)", res.membresias_informe, "(control)"),
        "base_afiliados": ("Base de datos de afiliados ACTHO", res.base_afiliados, "dim_afiliado.persona_principal_id"),
        "kam": ("Consolidado de asistencia por KAM (bloques repetidos)", res.kam_consolidado, "(control)"),
    }
    out = []
    for clave, (nombre, df, destino) in nombres.items():
        c = res.controles.get(clave, {})
        if c.get("ausente"):
            continue
        out.append({
            "id": clave, "nombre": nombre, "tablas_destino": [destino], "filas_leidas": c.get("filas_leidas"), "filas_vacias": c.get("filas_vacias", 0),
            "filas_total": c.get("filas_total", 0), "filas_encabezado_repetido": c.get("filas_encabezado_repetido", 0), "filas_sin_codigo": c.get("filas_sin_codigo", 0),
            "registros_declarados": c.get("declarados"), "registros_recuperados": c.get("recuperados", len(df)), "coincide_con_declarados": c.get("coincide_con_declarados"),
            "grupos": len(c.get("grupos", [])), "grupos_con_diferencia": len(c.get("grupos_con_diferencia", [])),
            "subtotales_verificados": c.get("subtotales_verificados"), "subtotales_coinciden": c.get("subtotales_coinciden"),
            "columnas_tidy": int(df.shape[1]),
        })
    return {"id": "informes", "nombre": "Informes de Zoho y consolidados de apoyo", "informes": out}


# ---------------------------------------------------------------------------
# Conciliación con los informes de Zoho
# ---------------------------------------------------------------------------

def _chk(codigo: str, descripcion: str, esperado: Any, obtenido: Any, nota: str = "") -> dict[str, Any]:
    return {"codigo": codigo, "descripcion": descripcion, "esperado": esperado, "obtenido": obtenido, "coincide": bool(esperado == obtenido), "nota": nota}


def conciliar(res: "Resultado") -> list[dict[str, Any]]:
    """Contrasta lo limpiado con los informes de Zoho y el consolidado por KAM, como control independiente."""
    out: list[dict[str, Any]] = []
    af = res.modelo["dim_afiliado"].set_index("empresa_id")
    raw = res.crm_completo
    if len(res.membresias_informe):
        activo = raw[raw["Estado"] == "Activo"]
        tipo = activo["Tipo de Membresía"].map(lp.limpiar_texto)
        cat = activo["Categoría de Membresía"].map(lp.limpiar_texto)
        crm_c = pd.DataFrame({"tipo_membresia": tipo, "categoria_membresia": cat.fillna("")}).groupby(["tipo_membresia", "categoria_membresia"]).size()
        inf = res.membresias_informe.assign(tipo_membresia=lambda d: d["tipo_membresia"].map(lp.limpiar_texto)).set_index(["tipo_membresia", "categoria_membresia"])["cantidad"]
        iguales = sum(int(crm_c.get(k, -1) == v) for k, v in inf.items())
        out.append(_chk("membresias_total", "Registros con estado Activo del CRM frente al total del informe de membresías.", int(res.membresias_informe["cantidad"].sum()), int(len(activo)),
                        "El informe se generó el 13 de noviembre; la exportación del CRM es de la misma época."))
        out.append(_chk("membresias_por_tipo_categoria", "Combinaciones tipo y categoría del informe que coinciden con el recuento del CRM.", len(inf), iguales))
    if len(res.segmento):
        s = res.segmento.set_index("empresa_id")
        en = s.index.isin(af.index)
        mismo = [(af.loc[e, "categoria_membresia"] == c) for e, c in zip(s.index[en], s["categoria_membresia"][en])]
        out.append(_chk("segmento_empresas_en_crm", "Empresas del informe Elite y Premium que existen en el CRM.", len(s), int(en.sum())))
        out.append(_chk("segmento_misma_categoria", "Empresas del informe cuya categoría en el CRM coincide con la del informe.", len(s), int(sum(mismo))))
        exp = [pd.Timestamp(af.loc[e, "fecha_expiracion"]) == pd.Timestamp(f) for e, f in zip(s.index[en], s["fecha_expiracion"][en]) if pd.notna(f)]
        out.append(_chk("segmento_misma_expiracion", "Empresas del informe cuya fecha de expiración coincide con la del CRM.", len(exp), int(sum(exp))))
    if len(res.base_afiliados):
        v = set(res.afiliados["empresa_id"])
        b = set(res.base_afiliados["empresa_id"])
        out.append(_chk("base_afiliados_vs_vigentes", "Afiliados de la base de ACTHO (472) frente a los vigentes que puntúa el pipeline.", len(b), len(b & v),
                        f"El pipeline puntúa {len(v)} vigentes; {len(v - b)} no están en la base y {len(b - v)} de la base no son vigentes en el CRM."))
    if len(res.renovaciones):
        r = res.renovaciones
        en = r["empresa_id"].isin(af.index)
        igual = [pd.Timestamp(af.loc[e, "fecha_expiracion"]) == f for e, f in zip(r["empresa_id"][en], r["fecha_expiracion"][en])]
        out.append(_chk("renovaciones_en_crm", "Empresas renovadas que existen en el CRM.", len(r), int(en.sum())))
        out.append(_chk("renovaciones_misma_expiracion", "Renovaciones cuya nueva fecha de expiración ya está reflejada en el CRM.", len(r), int(sum(igual))))
    if len(res.oportunidades):
        o = res.oportunidades
        en = o["empresa_id"].isin(af.index)
        mismo = [af.loc[e, "ejecutiva_id"] == mod_id(n) for e, n in zip(o["empresa_id"][en], o["ejecutiva"][en])]
        out.append(_chk("oportunidades_en_crm", "Oportunidades ganadas cuya empresa existe en el CRM.", len(o), int(en.sum())))
        out.append(_chk("oportunidades_misma_ejecutiva", "Oportunidades cuya ejecutiva coincide con la del CRM.", int(en.sum()), int(sum(mismo)),
                        "Las diferencias suelen ser cuentas reasignadas después de ganar la oportunidad."))
    if len(res.nuevos) or len(res.afiliaciones_recientes):
        n = res.afiliaciones_recientes
        en = n["empresa_id"].isin(af.index)
        out.append(_chk("afiliaciones_en_crm", "Afiliaciones recientes cuya empresa existe en el CRM.", len(n), int(en.sum())))
        nu = res.nuevos
        out.append(_chk("nuevos_en_crm", "Nuevos afiliados de agosto y septiembre que existen en el CRM.", len(nu), int(nu["empresa_id"].isin(af.index).sum()),
                        "Los códigos faltantes indican desfase de captura entre el informe y la exportación del CRM."))
    if len(res.kam_consolidado):
        k = res.kam_consolidado
        a = res.asistencias[res.asistencias["valida"]].groupby("empresa_id").size()
        calc = k["empresa_id"].map(a).fillna(0).astype(int)
        out.append(_chk("kam_bloques", "Bloques del consolidado por KAM cuyo resumen coincide con sus filas.", len(res.controles["kam"]["bloques"]),
                        sum(b["coincide"] for b in res.controles["kam"]["bloques"])))
        out.append(_chk("kam_asistentes_por_empresa", "Empresas del consolidado por KAM cuyo total de asistentes coincide con el recuento del pipeline.", len(k), int((calc == k["total_asistentes"]).sum()),
                        "El consolidado por KAM hereda el subconteo de la hoja GENERAL (rangos truncados): las diferencias son del consolidado, no del pipeline."))
        out.append(_chk("kam_asistentes_total", "Asistentes que suma el consolidado por KAM frente a los que cuenta el pipeline para las mismas empresas.", int(k["total_asistentes"].sum()), int(calc.sum()),
                        "El pipeline recuenta hoja por hoja y por eso supera al consolidado."))
    return out


def mod_id(nombre: str) -> str:
    from .modelo import id_ejecutiva  # noqa: PLC0415
    return id_ejecutiva(nombre)


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------

def auditar(res: "Resultado") -> dict[str, Any]:
    """Ejecuta toda la auditoría y devuelve un diccionario serializable (ver el docstring del módulo)."""
    fuentes = [_crm(res), _asistencia(res), _encuestas(res)]
    cal = {
        "fecha_corte": res.cfg.fecha_corte.isoformat(), "version_homologacion": config.HOMOLOGACION.get("version"),
        "fuentes": fuentes, "informes": _informes(res), "conciliacion": conciliar(res),
        "rechazos": res.rechazos.groupby(["fuente", "motivo"]).size().reset_index(name="filas").to_dict("records") if len(res.rechazos) else [],
        "modelo": {n: {"filas": int(len(d)), "columnas": int(d.shape[1])} for n, d in res.modelo.items()},
    }
    log.info("Auditoría de calidad lista: %d fuentes, %d controles de conciliación", len(fuentes), len(cal["conciliacion"]))
    return cal


def avisos_v2(res: "Resultado") -> list[dict[str, Any]]:
    """Avisos de calidad nuevos de la v2 (se suman a los de ``orquestador.generar_avisos``)."""
    def av(codigo: str, fuente: str, sev: str, desc: str, n: int | float) -> dict[str, Any]:
        return {"codigo": codigo, "fuente": fuente, "severidad": sev, "descripcion": desc, "cantidad": n}
    out: list[dict[str, Any]] = []
    crm = next(f for f in res.calidad["fuentes"] if f["id"] == "crm")
    a_crm = {x["codigo"]: x["cantidad"] for x in crm["anomalias"]}
    out.append(av("crm_estado_inconsistente", "CRM", "media", "Empresas con registro Activo pero membresía cancelada, expirada o inactiva.", a_crm["estado_inconsistente"]))
    out.append(av("crm_categoria_invalida", "CRM", "baja", "Registros cuya categoría de membresía trae un tipo en lugar de una categoría; el nivel se infiere del tipo.", a_crm["categoria_invalida"]))
    n_sin = sum(v["filas_sin_codigo"] for v in res.controles["asistencia"]["lectura"].values())
    out.append(av("asistencia_sin_empresa", "Asistencia", "media", "Inscripciones con persona pero sin código de empresa; se descartan y se listan en control_rechazos.", n_sin))
    hu = res.integridad["huerfanos"]
    fk = hu[(hu["tipo"] == "clave_foranea") & (hu["tabla_padre"] == "dim_afiliado")]
    out.append(av("integridad_empresas_fuera_del_crm", "Integración", "alta", "Filas de hechos (asistencia, encuestas, renovaciones, afiliaciones, oportunidades) cuya empresa no existe en el CRM.", int(fk["filas"].sum())))
    cat = hu[hu["tabla_padre"] == "dim_ciudad"]
    out.append(av("integridad_ciudades_sin_homologar", "Integración", "baja", "Filas con una ciudad que no está en el catálogo de config/homologacion.json.", int(cat["filas"].sum())))
    out.append(av("integridad_errores", "Integración", "alta" if not res.integridad["ok"] else "baja", "Errores de estructura o relaciones rotas del modelo relacional.", res.integridad["resumen"]["errores"]))
    return out
