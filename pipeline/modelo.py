"""Construcción del modelo relacional normalizado a partir de las tablas limpias del pipeline.

Cada función arma una tabla del ``esquema`` (una entidad por tabla, formato tidy, claves foráneas
consistentes). Los centinelas internos del pipeline («Sin dato», «Sin estado», «Sin clasificar»)
pasan a nulos reales; el JSON del tablero los vuelve a mostrar como «Sin dato» al exportar.
"""
from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pandas as pd

from . import config, esquema
from . import limpieza as lp

if TYPE_CHECKING:  # pragma: no cover
    from .orquestador import Resultado

ASPECTOS_PRESENCIAL_VIRTUAL = ("lugar_plataforma", "convocatoria", "conferencistas", "relevancia")
ASPECTOS_POST = {
    "satisfaccion_global": "satisfaccion_global", "asp_expositor": "expositor", "asp_contenido": "contenido",
    "asp_recepcion": "recepcion", "asp_espacio": "espacio", "asp_alimentacion": "alimentacion", "asp_tiempo": "manejo_tiempo",
}


def id_ejecutiva(nombre: str) -> str:
    """Identificador estable de una ejecutiva: ``KAM B`` da ``EJ-B`` y ``Sin asignar`` da ``EJ-SIN_ASIGNAR``."""
    m = re.match(r"^KAM ([A-Z])$", nombre)
    if m:
        return f"EJ-{m[1]}"
    return "EJ-" + re.sub(r"[^A-Z0-9]+", "_", lp.quitar_tildes(nombre).upper()).strip("_")


def coaccionar(df: pd.DataFrame, tabla: esquema.Tabla) -> pd.DataFrame:
    """Ajusta columnas, orden y tipos de un DataFrame a la definición de la tabla."""
    out = pd.DataFrame(index=df.index)
    for c in tabla.columnas:
        s = df[c.nombre] if c.nombre in df else pd.Series([None] * len(df), index=df.index)
        if c.tipo == "entero":
            out[c.nombre] = pd.to_numeric(s, errors="coerce").round().astype("Int64")
        elif c.tipo == "decimal":
            out[c.nombre] = pd.to_numeric(s, errors="coerce").astype("float64")
        elif c.tipo == "fecha":
            out[c.nombre] = pd.to_datetime(s, errors="coerce").astype("datetime64[ns]")
        elif c.tipo == "booleano":
            out[c.nombre] = s.map(lambda v: pd.NA if lp.es_nulo(v) else bool(v)).astype("boolean")
        else:
            out[c.nombre] = s.astype("object").where(s.notna(), None)
    return out.reset_index(drop=True)


def _o_nulo(serie: pd.Series, *centinelas: str) -> pd.Series:
    """Convierte en nulo los centinelas internos del pipeline."""
    return serie.where(~serie.isin(centinelas), None)


# ---------------------------------------------------------------------------
# Catálogos
# ---------------------------------------------------------------------------

def catalogos() -> dict[str, pd.DataFrame]:
    """Tablas de catálogo leídas del diccionario de homologación."""
    h = config.HOMOLOGACION
    niveles = pd.DataFrame(h["niveles"]["catalogo"])[["nivel", "categoria_zoho", "orden", "descripcion"]]
    vig = set(h["estados_membresia"]["vigentes"])
    estados = pd.DataFrame({"estado_membresia": config.catalogo(h["estados_membresia"])})
    estados["es_vigente"] = estados["estado_membresia"].isin(vig)
    estados["orden"] = range(1, len(estados) + 1)
    lineas = pd.DataFrame(h["lineas_evento"]["catalogo"])[["linea", "tipo", "descripcion"]]
    cargos = pd.DataFrame({"nivel_cargo": config.catalogo(h["niveles_cargo"])})
    cargos["orden"] = range(1, len(cargos) + 1)
    out = {
        "dim_nivel": niveles, "dim_estado_membresia": estados,
        "dim_tipo_membresia": pd.DataFrame({"tipo_membresia": config.catalogo(h["tipos_membresia"])}),
        "dim_sector": pd.DataFrame({"sector": config.catalogo(h["sectores"])}),
        "dim_ciudad": pd.DataFrame({"ciudad": config.catalogo(h["ciudades"])}),
        "dim_modalidad": pd.DataFrame({"modalidad": config.catalogo(h["modalidades"])}),
        "dim_linea_evento": lineas, "dim_nivel_cargo": cargos,
    }
    return {k: coaccionar(v, esquema.ESQUEMA[k]) for k, v in out.items()}


# ---------------------------------------------------------------------------
# Dimensiones
# ---------------------------------------------------------------------------

def dim_ejecutiva(res: "Resultado") -> pd.DataFrame:
    """Ejecutivas que aparecen en el CRM y en los informes de Zoho."""
    nombres = set(res.empresas["ejecutiva"])
    for t in (res.renovaciones, res.afiliaciones_recientes, res.oportunidades):
        if len(t) and "ejecutiva" in t:
            nombres |= set(t["ejecutiva"].dropna())
    sin = config.HOMOLOGACION["ejecutivas"]["etiqueta_sin_asignar"]
    ordenadas = sorted(nombres - {sin}) + ([sin] if sin in nombres else [])
    df = pd.DataFrame({"ejecutiva": ordenadas})
    df["ejecutiva_id"] = df["ejecutiva"].map(id_ejecutiva)
    df["es_asignada"] = df["ejecutiva"] != sin
    return coaccionar(df, esquema.ESQUEMA["dim_ejecutiva"])


def dim_afiliado(res: "Resultado") -> pd.DataFrame:
    """Una fila por empresa del CRM con sus atributos homologados."""
    e = res.empresas.copy()
    principal = pd.concat([
        res.base_afiliados[["empresa_id", "persona_principal_id"]] if len(res.base_afiliados) else None,
        res.nuevos[["empresa_id", "persona_principal_id"]] if len(res.nuevos) else None,
    ], ignore_index=True).dropna(subset=["persona_principal_id"]).drop_duplicates("empresa_id")
    e = e.merge(principal, on="empresa_id", how="left")
    df = pd.DataFrame({
        "empresa_id": e["empresa_id"], "id_registro_crm": e["id_registro"],
        "ejecutiva_id": e["ejecutiva"].map(id_ejecutiva),
        "naturaleza": e.get("naturaleza"), "tipo_compania": e.get("tipo_compania"),
        "tipo_membresia": e["tipo"], "tipo_membresia_zoho": e["tipo_membresia"],
        "categoria_membresia": e["categoria_membresia"], "nivel": _o_nulo(e["nivel"], "Sin dato"),
        "estado_membresia": _o_nulo(e["estado"], "Sin estado"), "estado_registro": e.get("estado_registro"),
        "sector": e["sector"], "subsector": e.get("subsector"), "tipo_consultora": e.get("tipo_consultora"),
        "ciudad": e["ciudad"], "ciudad_facturacion": e.get("ciudad_facturacion"), "departamento": e.get("departamento"),
        "region": e.get("region"), "pais": e.get("pais"), "tamano": e.get("tamano"), "rango_empleados": e["empleados"],
        "es_independiente": e.get("independiente"), "pct_mujeres": e.get("pct_mujeres"),
        "fecha_afiliacion": e["fecha_afiliacion"], "fecha_expiracion": e["fecha_expiracion"], "miembro_desde": e["miembro_desde"],
        "vinculado_comunidades": e["comunidad"], "cantidad_miembros": e["cantidad_miembros"],
        "persona_principal_id": e["persona_principal_id"],
        "fecha_afiliacion_invalida": e["fecha_afiliacion_invalida"], "fechas_incoherentes": e["fechas_incoherentes"],
        "estado_inconsistente": e["estado_inconsistente"], "categoria_invalida": e["categoria_invalida"],
    })
    return coaccionar(df, esquema.ESQUEMA["dim_afiliado"])


def dim_persona(res: "Resultado") -> pd.DataFrame:
    """Personas que aparecen en asistencia, encuestas o como contacto principal."""
    a = res.asistencias[["persona_id", "empresa_id"]].assign(fuente="asistencia")
    r = res.respuestas[["persona_id", "empresa_id"]].assign(fuente="encuesta")
    principal = pd.concat([t[["persona_principal_id"]].rename(columns={"persona_principal_id": "persona_id"})
                           for t in (res.base_afiliados, res.nuevos) if len(t)], ignore_index=True).assign(empresa_id=None, fuente="afiliado_principal")
    todo = pd.concat([a, r, principal], ignore_index=True).dropna(subset=["persona_id"])
    fuentes = todo.groupby("persona_id")["fuente"].agg(lambda s: ";".join(sorted(set(s))))
    n_emp = todo.dropna(subset=["empresa_id"]).groupby("persona_id")["empresa_id"].nunique()
    df = pd.DataFrame({"persona_id": fuentes.index, "fuentes": fuentes.to_numpy()})
    df["n_empresas_asociadas"] = df["persona_id"].map(n_emp).fillna(0).astype(int)
    df["multiples_empresas"] = df["n_empresas_asociadas"] > 1
    return coaccionar(df.sort_values("persona_id"), esquema.ESQUEMA["dim_persona"])


def dim_evento(res: "Resultado") -> pd.DataFrame:
    """Catálogo de eventos."""
    ev = res.eventos
    con_lista = set(res.asistencias["evento_id"].dropna())
    df = pd.DataFrame({
        "evento_id": ev["evento_id"], "evento_n": ev["evento_n"], "hoja_origen": ev["hoja"], "nombre": ev["nombre"],
        "fecha_inicio": ev["fecha"], "fecha_fin": ev["fecha_fin"], "mes": ev["mes"],
        "linea": _o_nulo(ev["linea"], "Sin clasificar"), "experiencia": ev["experiencia"],
        "modalidad": _o_nulo(ev["modalidad"], "Sin dato"), "tiene_asistentes": ev["evento_id"].isin(con_lista),
    })
    return coaccionar(df, esquema.ESQUEMA["dim_evento"])


# ---------------------------------------------------------------------------
# Hechos
# ---------------------------------------------------------------------------

def fact_asistencia(res: "Resultado") -> pd.DataFrame:
    """Todas las inscripciones, con las marcas de validez (agendado, duplicado, válida)."""
    a = res.asistencias.reset_index(drop=True)
    df = pd.DataFrame({
        "asistencia_id": [f"AS-{i + 1:05d}" for i in range(len(a))], "evento_id": a["evento_id"], "persona_id": a["persona_id"],
        "empresa_id": a["empresa_id"], "nivel_cargo": _o_nulo(a["nivel_cargo"], "Sin dato"), "ciudad": a.get("ciudad"),
        "con_costo": a["con_costo"], "autoriza_datos": a.get("autoriza_datos"), "registro_ubicacion": a.get("registro_ubicacion"),
        "marca_fuente": a["marca_afiliado"], "es_agendado": a["agendado"], "es_duplicado": a["duplicado"], "es_valida": a["valida"],
    })
    return coaccionar(df, esquema.ESQUEMA["fact_asistencia"])


def fact_encuesta(res: "Resultado") -> pd.DataFrame:
    """Una fila por respuesta de las tres encuestas."""
    r = res.respuestas.reset_index(drop=True)
    df = pd.DataFrame({
        "respuesta_id": r["respuesta_id"], "fuente": r["fuente"], "modalidad": r["modalidad"], "fecha_respuesta": r["completada"],
        "persona_id": r["persona_id"], "empresa_id": r["empresa_id"], "ciudad": r["ciudad"], "evento_id": r["evento_id"],
        "metodo_evento": r["metodo_evento"], "metodo_asignacion_empresa": r["metodo_asignacion"],
        "afiliado_declarado": r["afiliado_declarado"], "satisfaccion": r["satisfaccion"].round(3),
        "nps_puntaje": r["nps_puntaje"], "nps_categoria": r["nps_categoria"],
    })
    return coaccionar(df, esquema.ESQUEMA["fact_encuesta"])


def fact_encuesta_aspecto(res: "Resultado") -> pd.DataFrame:
    """Calificaciones por aspecto en formato largo."""
    pres, virt, post = (res.respuestas_raw[k] for k in ("presencial", "virtual", "post"))
    partes = []
    for d in (pres, virt):
        partes.append(d.melt(id_vars="respuesta_id", value_vars=list(ASPECTOS_PRESENCIAL_VIRTUAL), var_name="aspecto", value_name="calificacion"))
    p = post.rename(columns=ASPECTOS_POST)
    partes.append(p.melt(id_vars="respuesta_id", value_vars=list(ASPECTOS_POST.values()), var_name="aspecto", value_name="calificacion"))
    df = pd.concat(partes, ignore_index=True).dropna(subset=["calificacion"])
    df = df.sort_values(["respuesta_id", "aspecto"]).reset_index(drop=True)
    return coaccionar(df, esquema.ESQUEMA["fact_encuesta_aspecto"])


def fact_encuesta_tema(res: "Resultado") -> pd.DataFrame:
    """Temas marcados en la encuesta post-evento."""
    post = res.respuestas_raw["post"]
    filas = [{"respuesta_id": rid, "tema": t} for rid, ts in zip(post["respuesta_id"], post["temas_marcados"]) for t in ts]
    df = pd.DataFrame(filas, columns=["respuesta_id", "tema"]).drop_duplicates()
    return coaccionar(df.sort_values(["respuesta_id", "tema"]), esquema.ESQUEMA["fact_encuesta_tema"])


def fact_comunidad_afiliado(res: "Resultado") -> pd.DataFrame:
    """Miembros por empresa y comunidad (las seis columnas del CRM pasadas a filas)."""
    etiquetas = config.HOMOLOGACION["comunidades"]
    e = res.empresas
    df = e.melt(id_vars="empresa_id", value_vars=[c for c in etiquetas if c in e], var_name="comunidad", value_name="miembros")
    df = df.dropna(subset=["miembros"]).assign(comunidad=lambda d: d["comunidad"].map(etiquetas))
    return coaccionar(df.sort_values(["empresa_id", "comunidad"]), esquema.ESQUEMA["fact_comunidad_afiliado"])


def _numerar(prefijo: str, n: int, ancho: int = 3) -> list[str]:
    return [f"{prefijo}-{i + 1:0{ancho}d}" for i in range(n)]


def fact_renovacion(res: "Resultado") -> pd.DataFrame:
    """Renovaciones del informe de Zoho."""
    r = res.renovaciones
    df = pd.DataFrame({
        "renovacion_id": _numerar("RN", len(r)), "empresa_id": r["empresa_id"], "ejecutiva_id": r["ejecutiva"].map(id_ejecutiva),
        "mes_factura": r["mes_factura"], "fecha_expiracion_nueva": r["fecha_expiracion"],
    }) if len(r) else pd.DataFrame(columns=esquema.ESQUEMA["fact_renovacion"].nombres())
    return coaccionar(df, esquema.ESQUEMA["fact_renovacion"])


def fact_afiliacion_nueva(res: "Resultado") -> pd.DataFrame:
    """Une el informe de afiliaciones (negocios ganados) con la lista de nuevos afiliados."""
    d = res.afiliaciones_recientes.sort_values("fecha_cierre").drop_duplicates("empresa_id") if len(res.afiliaciones_recientes) else \
        pd.DataFrame(columns=["empresa_id", "fecha_cierre", "ejecutiva", "categoria_membresia"])
    n = res.nuevos.rename(columns={"mes": "mes_lista_nuevos"}) if len(res.nuevos) else \
        pd.DataFrame(columns=["empresa_id", "persona_principal_id", "mes_lista_nuevos"])
    m = d.merge(n, on="empresa_id", how="outer", indicator=True)
    tipos = res.empresas.set_index("empresa_id")["tipo_membresia"]
    m["nivel"] = [None if (lp.es_nulo(c) or (x := lp.normalizar_nivel(c, tipos.get(e))) == "Sin dato") else x
                  for e, c in zip(m["empresa_id"], m["categoria_membresia"])]
    m = m.sort_values(["fecha_cierre", "empresa_id"], na_position="last").reset_index(drop=True)
    df = pd.DataFrame({
        "afiliacion_id": _numerar("AF", len(m)), "empresa_id": m["empresa_id"],
        "ejecutiva_id": m["ejecutiva"].map(lambda v: None if lp.es_nulo(v) else id_ejecutiva(v)),
        "fecha_cierre": m["fecha_cierre"], "categoria_membresia": m["categoria_membresia"], "nivel": m["nivel"],
        "mes_lista_nuevos": m["mes_lista_nuevos"], "persona_principal_id": m["persona_principal_id"],
        "en_informe_afiliaciones": m["_merge"].isin(["both", "left_only"]), "en_lista_nuevos": m["_merge"].isin(["both", "right_only"]),
    })
    return coaccionar(df, esquema.ESQUEMA["fact_afiliacion_nueva"])


def fact_oportunidad_ganada(res: "Resultado") -> pd.DataFrame:
    """Oportunidades ganadas por ejecutiva."""
    o = res.oportunidades
    df = pd.DataFrame({"oportunidad_id": _numerar("OP", len(o)), "empresa_id": o["empresa_id"], "ejecutiva_id": o["ejecutiva"].map(id_ejecutiva)}) \
        if len(o) else pd.DataFrame(columns=esquema.ESQUEMA["fact_oportunidad_ganada"].nombres())
    return coaccionar(df, esquema.ESQUEMA["fact_oportunidad_ganada"])


def fact_score(res: "Resultado") -> tuple[pd.DataFrame, pd.DataFrame]:
    """Score por afiliado vigente y sus factores explicativos."""
    a = res.afiliados.reset_index(drop=True)
    df = a.assign(fecha_corte=pd.Timestamp(res.cfg.fecha_corte))
    sc = coaccionar(df, esquema.ESQUEMA["fact_score_afiliado"])
    filas = [{"empresa_id": e, "orden": i + 1, "codigo": f["codigo"], "puntos": f["puntos"], "texto": f["texto"]}
             for e, fs in zip(a["empresa_id"], a["factores"]) for i, f in enumerate(fs)]
    fa = pd.DataFrame(filas, columns=["empresa_id", "orden", "codigo", "puntos", "texto"])
    return sc, coaccionar(fa, esquema.ESQUEMA["fact_score_factor"])


def construir_modelo(res: "Resultado") -> dict[str, pd.DataFrame]:
    """Arma todas las tablas del modelo, en el orden de carga (padres antes que hijos)."""
    modelo = catalogos()
    modelo["dim_ejecutiva"] = dim_ejecutiva(res)
    modelo["dim_afiliado"] = dim_afiliado(res)
    modelo["dim_persona"] = dim_persona(res)
    modelo["dim_evento"] = dim_evento(res)
    modelo["fact_asistencia"] = fact_asistencia(res)
    modelo["fact_encuesta"] = fact_encuesta(res)
    modelo["fact_encuesta_aspecto"] = fact_encuesta_aspecto(res)
    modelo["fact_encuesta_tema"] = fact_encuesta_tema(res)
    modelo["fact_comunidad_afiliado"] = fact_comunidad_afiliado(res)
    modelo["fact_renovacion"] = fact_renovacion(res)
    modelo["fact_afiliacion_nueva"] = fact_afiliacion_nueva(res)
    modelo["fact_oportunidad_ganada"] = fact_oportunidad_ganada(res)
    modelo["fact_score_afiliado"], modelo["fact_score_factor"] = fact_score(res)
    return {n: modelo[n] for n in esquema.orden_de_carga()}

