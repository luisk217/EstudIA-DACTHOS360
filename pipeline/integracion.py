"""Limpieza por fuente e integración en un modelo por afiliado.

Clave de unión: ``empresa_id`` (formato ``EMP-0000``), el código anonimizado que
ACTHO asignó en lugar del NIT. Aparece en el CRM (``Nombre de Empresa``), en
cada hoja de asistencia (``ID_EMPRESA``) y en las encuestas (``ID_EMPRESA``).
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from . import config
from . import limpieza as lp

log = logging.getLogger(__name__)

COLS_COMUNIDAD = [
    "com_hr_estrategico", "com_mas_que_salario", "com_talento_elige",
    "com_gente_crece", "com_mujeres_hr", "com_influenciador",
]


def limpiar_crm(raw: pd.DataFrame, corte: date) -> pd.DataFrame:
    """Normaliza el CRM: texto, fechas, categorías homologadas, niveles, ejecutiva y estado; marca registros de prueba y anomalías.

    Además de lo que usa el score, deja homologadas las columnas geográficas (país, departamento, región), el tamaño,
    el rango de empleados, la naturaleza de la empresa, el subsector y los booleanos, y añade banderas de anomalía
    (``fecha_afiliacion_invalida``, ``estado_inconsistente``, ``fechas_incoherentes``, ``categoria_invalida``) para que
    ninguna corrección quede oculta.
    """
    df = raw.copy()
    for c in df.columns:
        df[c] = df[c].map(lp.limpiar_texto)
    df["empresa_id"] = df["empresa_id"].map(lp.normalizar_id_empresa)
    df["es_prueba"] = df["etiqueta"].map(lambda v: "prueba" in lp.clave_texto(v))
    df["ciudad"] = df["ciudad"].where(df["ciudad"].notna(), df["ciudad_facturacion"]).map(lp.normalizar_ciudad)
    if "ciudad_facturacion" in df:
        df["ciudad_facturacion"] = df["ciudad_facturacion"].map(lp.normalizar_ciudad)
    df["sector"] = df["sector"].map(lp.normalizar_sector)
    if "subsector" in df:
        df["subsector"] = df["subsector"].map(lp.normalizar_subsector)
    df["empleados"] = df["empleados"].map(lp.normalizar_empleados)
    df["tipo"] = df["tipo_membresia"].map(lp.normalizar_tipo_membresia)
    df["nivel"] = [lp.normalizar_nivel(c, t) for c, t in zip(df["categoria_membresia"], df["tipo_membresia"])]
    df["categoria_invalida"] = df["categoria_membresia"].notna() & df["categoria_membresia"].map(lp.normalizar_categoria_membresia).isna()
    df["categoria_membresia"] = df["categoria_membresia"].map(lp.normalizar_categoria_membresia)
    df["ejecutiva"] = df["propietario"].map(lp.normalizar_ejecutiva)
    for c, f in (("pais", lp.normalizar_pais), ("departamento", lp.normalizar_departamento), ("region", lp.normalizar_region),
                 ("tamano", lp.normalizar_tamano), ("naturaleza", lp.normalizar_naturaleza), ("estado_registro", lp.normalizar_estado_registro)):
        if c in df:
            df[c] = df[c].map(f)
    if "independiente" in df:
        df["independiente"] = df["independiente"].map(lp.normalizar_si_no).astype("boolean")
    if "pct_mujeres" in df:
        df["pct_mujeres"] = df["pct_mujeres"].map(lp.normalizar_porcentaje)
    for c in ("fecha_afiliacion", "fecha_expiracion", "miembro_desde"):
        df[c] = df[c].map(lp.parsear_fecha)
    ts_corte = pd.Timestamp(corte)
    df["fecha_afiliacion_invalida"] = df["fecha_afiliacion"] > ts_corte
    df.loc[df["fecha_afiliacion_invalida"], "fecha_afiliacion"] = pd.NaT
    df["fechas_incoherentes"] = df["fecha_expiracion"] < df["fecha_afiliacion"]
    df["estado"] = df["estado_membresia"].map(lp.normalizar_estado_membresia).fillna("Sin estado")
    df["vigente"] = df["estado"].isin(config.ESTADOS_VIGENTES)
    df["no_vigente"] = df["estado"].isin(config.ESTADOS_NO_VIGENTES)
    if "estado_registro" in df:
        df["estado_inconsistente"] = (df["estado_registro"] == "Activo") & df["no_vigente"]
    else:
        df["estado_inconsistente"] = False
    for c in COLS_COMUNIDAD:
        df[c] = df[c].map(lp.a_entero).astype("Int64")
    df["n_comunidades"] = df[COLS_COMUNIDAD].notna().sum(axis=1)
    df["comunidad"] = df["vinculado_comunidades"].map(lp.normalizar_si_no).fillna(False) | (df["n_comunidades"] > 0)
    df["cantidad_miembros"] = df["cantidad_miembros"].map(lp.a_entero).astype("Int64")
    return df


def consolidar_empresas(crm: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    """Deja una fila por ``empresa_id``.

    Prioridad: registro vigente, luego con estado, luego con fecha de
    expiración, luego con más campos completos. Se excluyen registros de prueba
    y los sin código válido.
    """
    base = crm[~crm["es_prueba"] & crm["empresa_id"].notna()].copy()
    base["_p1"] = (~base["vigente"]).astype(int)
    base["_p2"] = (base["estado"] == "Sin estado").astype(int)
    base["_p3"] = base["fecha_expiracion"].isna().astype(int)
    base["_p4"] = -base.notna().sum(axis=1)
    base = base.sort_values(["empresa_id", "_p1", "_p2", "_p3", "_p4"])
    duplicados = int(base["empresa_id"].duplicated().sum())
    uno = base.drop_duplicates("empresa_id", keep="first").drop(columns=["_p1", "_p2", "_p3", "_p4"])
    conflicto = int(base[base["empresa_id"].duplicated(keep=False)].groupby("empresa_id")["estado"].nunique().gt(1).sum())
    stats = {
        "filas_originales": len(crm), "registros_de_prueba": int(crm["es_prueba"].sum()),
        "sin_codigo_valido": int(crm["empresa_id"].isna().sum()), "filas_duplicadas_descartadas": duplicados,
        "empresas_con_duplicado_y_estados_distintos": conflicto, "empresas_unicas": len(uno),
    }
    log.info("CRM consolidado: %s", stats)
    return uno.reset_index(drop=True), stats


def limpiar_eventos(eventos: pd.DataFrame) -> pd.DataFrame:
    """Completa fin de evento, mes, línea y modalidad del catálogo de eventos.

    El fin de un evento de varios días se toma del rango que escribe la hoja GENERAL
    (``fecha_fin_general``) y, si falta, del diccionario ``fin_evento_multidia``.
    """
    ev = eventos.copy()
    ev["evento_id"] = ev["evento_n"].map(lambda n: f"EV{n:02d}")
    fin_general = ev["fecha_fin_general"] if "fecha_fin_general" in ev else pd.Series(pd.NaT, index=ev.index)
    fines = []
    for n, f, g in zip(ev["evento_n"], ev["fecha"], fin_general):
        if pd.notna(g) and g >= f:
            fines.append(pd.Timestamp(g))
        else:
            fines.append(pd.Timestamp(config.FIN_EVENTO_MULTIDIA.get(n, f.date())))
    ev["fecha_fin"] = fines
    ev["mes"] = ev["fecha"].dt.strftime("%Y-%m")
    ev["linea"] = ev["linea"].map(lp.normalizar_linea).fillna("Sin clasificar")
    ev["experiencia"] = ev["experiencia"].map(lp.limpiar_texto).astype(object).where(ev["experiencia"].notna(), None)
    ev["modalidad"] = ev["modalidad"].map(lp.normalizar_modalidad).fillna("Sin dato")
    ev["nombre"] = ev["nombre"].map(lambda t: " ".join(str(lp.reparar_mojibake(t)).split()))
    return ev


def limpiar_asistencias(raw: pd.DataFrame, eventos: pd.DataFrame, empresas: pd.DataFrame) -> pd.DataFrame:
    """Une las hojas, deduplica persona-evento, descarta ``agendado`` y marca el estado de afiliación."""
    df = raw.merge(eventos[["hoja", "evento_id", "fecha"]], on="hoja", how="left")
    df["agendado"] = df["estado_registro"].map(lambda v: "agendado" in lp.clave_texto(v))
    df["nivel_cargo"] = df["nivel_cargo"].map(lambda v: lp.normalizar_nivel_cargo(v) or "Sin dato")
    df["persona_id"] = df["persona_id"].map(lp.limpiar_texto)
    df["persona_id_invalido"] = df["persona_id"].notna() & df["persona_id"].map(lp.normalizar_id_persona).isna()
    if "ciudad" in df:
        df["ciudad"] = df["ciudad"].map(lp.normalizar_ciudad)
    for c in ("autoriza_datos", "registro_ubicacion"):
        df[c] = df[c].map(lp.normalizar_si_no).astype("boolean") if c in df else pd.array([None] * len(df), dtype="boolean")
    df["con_costo"] = df["costo"].map(lambda v: None if lp.es_nulo(v) else lp.clave_texto(v).startswith("con"))
    # La deduplicación ignora los registros «agendado»: si no, un agendado previo anularía la asistencia real.
    efectivos = df[~df["agendado"] & df["persona_id"].notna()]
    df["duplicado"] = df.index.isin(efectivos.index[efectivos.duplicated(["evento_id", "persona_id"], keep="first")])
    df["valida"] = ~df["agendado"] & ~df["duplicado"]
    estado = empresas.set_index("empresa_id")[["estado", "vigente"]]
    df = df.join(estado, on="empresa_id")
    df["en_crm"] = df["estado"].notna()
    df["vigente"] = df["vigente"].fillna(False).astype(bool)
    df["estado"] = df["estado"].fillna("No está en el CRM")
    return df.drop(columns=["costo", "estado_registro"])


def construir_respuestas(presencial: pd.DataFrame, virtual: pd.DataFrame, post: pd.DataFrame) -> pd.DataFrame:
    """Unifica las tres encuestas en una tabla larga con satisfacción 1-5 por respuesta."""
    pres = presencial.assign(afiliado_declarado=None, nps_puntaje=np.nan)
    virt = virtual.assign(afiliado_declarado=None, nps_puntaje=np.nan)
    for d in (pres, virt):
        d["satisfaccion"] = d[["lugar_plataforma", "convocatoria", "conferencistas", "relevancia"]].mean(axis=1)
    p = post.copy()
    asp = ["satisfaccion_global", "asp_expositor", "asp_contenido", "asp_recepcion", "asp_espacio", "asp_alimentacion", "asp_tiempo"]
    p["satisfaccion"] = p[asp].mean(axis=1)
    cols = ["respuesta_id", "fuente", "modalidad", "completada", "persona_id", "empresa_id", "ciudad",
            "metodo_asignacion", "afiliado_declarado", "satisfaccion", "nps_puntaje"]
    out = pd.concat([pres.reindex(columns=cols), virt.reindex(columns=cols), p.reindex(columns=cols)], ignore_index=True)
    out["modalidad"] = out["modalidad"].map(lp.normalizar_modalidad)
    out["nps_categoria"] = out["nps_puntaje"].map(lp.clasificar_nps)
    out["anio"] = out["completada"].dt.year
    return out


def asignar_eventos(resp: pd.DataFrame, eventos: pd.DataFrame, ventana: int = config.VENTANA_ENCUESTA_DIAS) -> pd.DataFrame:
    """Asigna cada respuesta al evento 2026 más cercano anterior a la fecha (misma modalidad).

    Las encuestas no traen el evento; se infiere por la fecha de respuesta, con
    una ventana de ``ventana`` días tras el cierre del evento. Si dos eventos
    compatibles quedan a la misma distancia, la respuesta se marca como ambigua.
    """
    r = resp.copy()
    ids: list[str | None] = []
    metodos: list[str] = []
    for fecha, mod in zip(r["completada"], r["modalidad"]):
        if pd.isna(fecha) or fecha.year < 2026:
            ids.append(None); metodos.append("fuera de 2026" if not pd.isna(fecha) else "sin fecha"); continue
        compat = eventos[eventos["modalidad"].isin(_modalidades_compatibles(mod))]
        delta = (fecha - compat["fecha_fin"]).dt.days
        cand = compat[(delta >= 0) & (delta <= ventana) & (fecha >= compat["fecha"])]
        if cand.empty:
            ids.append(None); metodos.append("sin evento en la ventana"); continue
        d = (fecha - cand["fecha_fin"]).dt.days
        mejores = cand[d == d.min()]
        if len(mejores) == 1:
            ids.append(mejores["evento_id"].iloc[0]); metodos.append("fecha")
        else:
            ids.append(None); metodos.append("ambiguo (varios eventos el mismo día)")
    r["evento_id"] = ids
    r["metodo_evento"] = metodos
    return r


def _modalidades_compatibles(modalidad: Any) -> list[str]:
    """Modalidades de evento con las que puede coincidir una respuesta (los híbridos aceptan ambas)."""
    m = lp.clave_texto(modalidad)
    if m.startswith("pres"):
        return ["Presencial", "Híbrido"]
    if m.startswith("virt"):
        return ["Virtual", "Híbrido"]
    return ["Presencial", "Virtual", "Híbrido"]


def tasas_de_cruce(vigentes: pd.DataFrame, asistencias: pd.DataFrame, respuestas: pd.DataFrame) -> dict[str, Any]:
    """Mide qué porcentaje de afiliados vigentes se cruza con asistencia y con encuestas."""
    v = set(vigentes["empresa_id"])
    con_as = v & set(asistencias.loc[asistencias["valida"], "empresa_id"])
    con_en = v & set(respuestas["empresa_id"].dropna())
    con_nps = v & set(respuestas.loc[respuestas["nps_puntaje"].notna(), "empresa_id"])
    n = len(v)
    pct = lambda k: round(100 * k / n, 1) if n else 0.0  # noqa: E731
    return {
        "afiliados_vigentes": n,
        "con_asistencia": len(con_as), "pct_con_asistencia": pct(len(con_as)), "pct_sin_asistencia": pct(n - len(con_as)),
        "con_encuesta": len(con_en), "pct_con_encuesta": pct(len(con_en)), "pct_sin_encuesta": pct(n - len(con_en)),
        "con_nps": len(con_nps), "pct_con_nps": pct(len(con_nps)),
        "con_asistencia_o_encuesta": len(con_as | con_en), "pct_con_alguna": pct(len(con_as | con_en)),
        "sin_ninguna": n - len(con_as | con_en), "pct_sin_ninguna": pct(n - len(con_as | con_en)),
    }
