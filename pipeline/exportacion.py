"""Exportación: modelo relacional y tablas de control (CSV) y JSON estáticos para el frontend (``web/data``)."""
from __future__ import annotations

import json
import logging
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from . import __version__, config, esquema, limpieza as lp
from .orquestador import Resultado
from .validacion import resumen_para_meta

log = logging.getLogger(__name__)

ASPECTOS = ["lugar_plataforma", "convocatoria", "conferencistas", "relevancia"]


def _limpio(x: Any) -> Any:
    """Convierte recursivamente tipos de pandas/numpy a tipos JSON (NaN y NaT a ``null``)."""
    if isinstance(x, dict):
        return {str(k): _limpio(v) for k, v in x.items()}
    if isinstance(x, (list, tuple, set)):
        return [_limpio(v) for v in x]
    if isinstance(x, (pd.Timestamp, datetime)):
        return None if pd.isna(x) else x.strftime("%Y-%m-%d")
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.floating, float)):
        if math.isnan(x) or math.isinf(x):
            return None
        return int(x) if float(x).is_integer() else round(float(x), 3)
    if isinstance(x, (np.bool_,)):
        return bool(x)
    if x is pd.NaT or x is pd.NA:
        return None
    return x


def escribir_json(obj: Any, ruta: Path) -> None:
    """Escribe un JSON compacto en UTF-8."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as fh:
        json.dump(_limpio(obj), fh, ensure_ascii=False, separators=(",", ":"))
    log.info("Escrito %s (%.1f KB)", ruta.name, ruta.stat().st_size / 1024)


def _iso(ts: Any) -> str | None:
    """Fecha en formato AAAA-MM-DD, o ``None`` si es nula."""
    return None if pd.isna(ts) else pd.Timestamp(ts).strftime("%Y-%m-%d")


def json_afiliados(res: Resultado) -> dict[str, Any]:
    """Una fila por afiliado vigente con score y factores."""
    filas = []
    for r in res.afiliados.sort_values(["riesgo", "dias_vencimiento"], ascending=[False, True]).to_dict("records"):
        filas.append({
            "id": r["empresa_id"], "nivel": r["nivel"], "tipo": r["tipo"], "sector": r["sector"], "tamano": r["tamano"],
            "ciudad": r["ciudad"], "ejecutiva": r["ejecutiva"], "estado": r["estado"],
            "expira": _iso(r["fecha_expiracion"]), "dias_venc": r["dias_vencimiento"],
            "afiliacion": _iso(r["fecha_afiliacion"]), "antig_anios": r["antiguedad_anios"],
            "asist": r["asistencias"], "asist_90d": r["asistencias_90d"], "eventos": r["eventos_distintos"],
            "personas": r["personas_distintas"], "ult_asist": _iso(r["ultima_asistencia"]),
            "dias_ult_asist": r["dias_ultima_asistencia"], "sat": r["satisfaccion"], "n_resp": r["n_respuestas"],
            "nps_min": r["nps_minimo"], "comunidad": bool(r["comunidad"]), "renovo_reciente": bool(r["renovo_recientemente"]),
            "riesgo": r["riesgo"], "salud": r["salud"], "banda": r["banda"],
            "factores": [{"c": f["codigo"], "p": round(f["puntos"], 1), "t": f["texto"]} for f in r["factores"][:5]],
            "accion": r["accion"],
        })
    return {"afiliados": filas}


def _stats_encuesta(df: pd.DataFrame) -> dict[str, Any]:
    nps = lp.calcular_nps(df["nps_puntaje"])
    return {"n": len(df), "satisfaccion": df["satisfaccion"].mean(), "n_nps": nps["n"], "nps": nps["nps"]}


def json_eventos(res: Resultado) -> dict[str, Any]:
    """Catálogo de eventos con asistencia y satisfacción, más agregados por línea, mes, modalidad y cargo."""
    a = res.asistencias[res.asistencias["valida"]]
    r = res.respuestas
    out = []
    for e in res.eventos.to_dict("records"):
        ae = a[a["evento_id"] == e["evento_id"]]
        re_ = r[r["evento_id"] == e["evento_id"]]
        emp = set(ae["empresa_id"])
        out.append({
            "id": e["evento_id"], "nombre": e["nombre"], "fecha": _iso(e["fecha"]), "fecha_fin": _iso(e["fecha_fin"]),
            "mes": e["mes"], "linea": e["linea"], "experiencia": e["experiencia"], "modalidad": e["modalidad"],
            "asistentes": len(ae), "personas": ae["persona_id"].nunique(), "empresas": len(emp),
            "empresas_vigentes": int(ae.loc[ae["vigente"], "empresa_id"].nunique()),
            "empresas_no_crm": int(ae.loc[~ae["en_crm"], "empresa_id"].nunique()),
            "n_respuestas": len(re_), "satisfaccion": re_["satisfaccion"].mean() if len(re_) else None,
        })
    ev = pd.DataFrame(out)
    def agrupa(col: str) -> list[dict[str, Any]]:
        g = ev.groupby(col).agg(eventos=("id", "size"), asistentes=("asistentes", "sum"), empresas_max=("empresas", "max")).reset_index()
        ae = a.merge(res.eventos[["evento_id", col]], on="evento_id")
        g["empresas"] = g[col].map(ae.groupby(col)["empresa_id"].nunique())
        g["empresas_vigentes"] = g[col].map(ae[ae["vigente"]].groupby(col)["empresa_id"].nunique())
        g["promedio_asistentes"] = (g["asistentes"] / g["eventos"]).round(1)
        return g.drop(columns="empresas_max").rename(columns={col: "clave"}).to_dict("records")
    cargos = a.groupby("nivel_cargo").size().sort_values(ascending=False)
    return {
        "eventos": out, "por_linea": agrupa("linea"), "por_modalidad": agrupa("modalidad"), "por_mes": agrupa("mes"),
        "por_nivel_cargo": [{"clave": k, "asistentes": int(v)} for k, v in cargos.items()],
        "totales": {"eventos": len(out), "asistentes": len(a), "personas": a["persona_id"].nunique(),
                    "empresas": a["empresa_id"].nunique(), "empresas_vigentes": int(a.loc[a["vigente"], "empresa_id"].nunique())},
    }


def json_ejecutivas(res: Resultado) -> dict[str, Any]:
    """Resumen de cartera por ejecutiva (sin repetir la lista completa de afiliados)."""
    a = res.afiliados
    out = []
    for nombre, g in a.groupby("ejecutiva"):
        g = g.sort_values(["riesgo", "dias_vencimiento"], ascending=[False, True])
        out.append({
            "nombre": nombre, "cartera": len(g),
            "por_banda": {b: int((g["banda"] == b).sum()) for b in ("Saludable", "Atención", "Riesgo alto")},
            "vencen_30": int((g["dias_vencimiento"] <= 30).sum()), "vencen_60": int((g["dias_vencimiento"] <= 60).sum()),
            "vencen_90": int((g["dias_vencimiento"] <= 90).sum()),
            "sin_asistencia_90d": int((g["asistencias_90d"] == 0).sum()), "sin_asistencia_anio": int((g["asistencias"] == 0).sum()),
            "riesgo_medio": g["riesgo"].mean().round(1), "salud_media": g["salud"].mean().round(1),
            "por_nivel": g["nivel"].value_counts().to_dict(),
            "prioritarios": g["empresa_id"].head(10).tolist(),
        })
    out.sort(key=lambda d: (d["nombre"] == "Sin asignar", -d["cartera"]))
    return {"ejecutivas": out}


def json_encuestas(res: Resultado) -> dict[str, Any]:
    """Agregados de satisfacción y NPS por segmento, tipo de evento, modalidad y mes (las encuestas no identifican evento)."""
    r = res.respuestas
    ev = res.eventos.set_index("evento_id")
    r = r.assign(linea=r["evento_id"].map(ev["linea"]), mes=r["completada"].dt.strftime("%Y-%m"))
    def por(col: str) -> list[dict[str, Any]]:
        return [{"clave": k, **_stats_encuesta(g)} for k, g in r.groupby(col, dropna=True)]
    pres, virt, post = (res.respuestas_raw[k] for k in ("presencial", "virtual", "post"))
    aspectos = {
        "presencial": {a: pres[a].mean() for a in ASPECTOS}, "virtual": {a: virt[a].mean() for a in ASPECTOS},
        "post_evento": {a: post[a].mean() for a in ("satisfaccion_global", "asp_expositor", "asp_contenido", "asp_recepcion", "asp_espacio", "asp_alimentacion", "asp_tiempo")},
    }
    nps_post = lp.calcular_nps(post["nps_puntaje"])
    nps_afil = {k: lp.calcular_nps(g["nps_puntaje"]) for k, g in post.groupby("afiliado_declarado", dropna=True)}
    temas = pd.Series([t for lst in post["temas_marcados"] for t in lst]).value_counts()
    return {
        "resumen": {"respuestas": len(r), "con_empresa": int(r["empresa_id"].notna().sum()),
                    "con_evento_2026": int(r["evento_id"].notna().sum()), "anio_2025": int((r["anio"] == 2025).sum()),
                    "satisfaccion_media": r["satisfaccion"].mean(), "encuesta_90_dias_respuestas": res.encuesta_90_n},
        "por_fuente": por("fuente"), "por_modalidad": por("modalidad"), "por_linea": por("linea"),
        "por_mes": por("mes"), "por_nivel_afiliado": por("nivel_afiliado"),
        "por_asignacion_empresa": por("metodo_asignacion"),
        "aspectos": aspectos,
        "nps_post_evento": {**nps_post, "advertencia": "Muestra pequeña; no equivale al NPS de la asociación (encuesta de 90 días sin respuestas)."},
        "nps_post_afiliado_declarado": {("afiliado" if k else "no_afiliado"): v for k, v in nps_afil.items()},
        "temas_solicitados": [{"tema": k, "n": int(v)} for k, v in temas.items()],
        "interes_afiliarse_no_afiliados": post.loc[post["afiliado_declarado"] == False, "interes_afiliarse"].value_counts().to_dict(),  # noqa: E712
    }


def json_segmentos(res: Resultado) -> dict[str, Any]:
    """Listas de empresas por segmento para comunicaciones, más asistentes no afiliados."""
    a = res.afiliados
    a_ord = a.sort_values(["riesgo", "dias_vencimiento"], ascending=[False, True])
    nuevo = a["dias_afiliacion"] < 90
    ids = lambda m: a_ord.loc[a_ord["empresa_id"].isin(a.loc[m, "empresa_id"]), "empresa_id"].tolist()  # noqa: E731
    seg = {
        "no_participan": ids(a["asistencias_90d"] == 0),
        "vencen_90": ids(a["dias_vencimiento"] <= 90),
        "detractores": ids(a["detractor"]),
        "promotores": ids(res.afiliados["nps_minimo"].ge(9) & (res.afiliados["n_respuestas"] > 0)),
        "un_solo_contacto": ids((a["asistencias"] >= 2) & (a["personas_distintas"] == 1)),
        "nuevos_90d": ids(nuevo),
        "riesgo_alto": ids(a["banda"] == "Riesgo alto"),
    }
    v = res.asistencias[res.asistencias["valida"] & ~res.asistencias["vigente"]]
    g = v.groupby("empresa_id").agg(asistentes=("persona_id", "size"), personas=("persona_id", "nunique"),
                                   eventos=("evento_id", "nunique"), estado=("estado", "first"),
                                   ultima=("fecha", "max")).reset_index().sort_values(["eventos", "asistentes"], ascending=False)
    return {
        "definiciones": {
            "no_participan": "Afiliados vigentes sin asistencia en el último trimestre registrado (hasta el último evento del libro)",
            "vencen_90": "Afiliados vigentes que vencen en 90 días o menos (incluye vencidos), ordenados por riesgo",
            "detractores": "Afiliados con alguna calificación de recomendación de 0 a 6 en los últimos 12 meses",
            "promotores": "Afiliados con calificación mínima de 9 o 10 en sus encuestas",
            "un_solo_contacto": "Afiliados con dos o más asistencias, siempre de la misma persona",
            "nuevos_90d": "Afiliados con menos de 90 días de afiliación",
            "riesgo_alto": "Afiliados en banda Riesgo alto",
        },
        "conteos": {k: len(x) for k, x in seg.items()},
        "listas": seg,
        "asistentes_no_afiliados": {
            "empresas_total": int(len(g)), "asistentes_total": int(g["asistentes"].sum()),
            "top": [{"id": r["empresa_id"], "estado_crm": r["estado"], "asistentes": int(r["asistentes"]),
                     "eventos": int(r["eventos"]), "ultima": _iso(r["ultima"])} for r in g.head(60).to_dict("records")],
        },
    }


def json_resumen(res: Resultado) -> dict[str, Any]:
    """KPIs globales para la vista de Dirección."""
    a, e = res.afiliados, res.empresas
    n = len(a)
    nps = lp.calcular_nps(res.respuestas_raw["post"]["nps_puntaje"])
    dist = lambda col, top=8: [{"clave": k, "n": int(v)} for k, v in a[col].fillna("Sin dato").value_counts().head(top).items()]  # noqa: E731
    no_vig = e[e["no_vigente"]]
    return {
        "afiliados_vigentes": n,
        "por_estado": a["estado"].value_counts().to_dict(),
        "por_nivel": a["nivel"].value_counts().to_dict(),
        "por_banda": {b: int((a["banda"] == b).sum()) for b in ("Saludable", "Atención", "Riesgo alto")},
        "vencimientos": {"vencidas": int((a["dias_vencimiento"] < 0).sum()), "hasta_30": int((a["dias_vencimiento"] <= 30).sum()),
                         "hasta_60": int((a["dias_vencimiento"] <= 60).sum()), "hasta_90": int((a["dias_vencimiento"] <= 90).sum()),
                         "sin_fecha": int(a["dias_vencimiento"].isna().sum())},
        "participacion": {
            "pct_con_asistencia_90d": round(100 * float((a["asistencias_90d"] > 0).mean()), 1),
            "pct_con_asistencia_anio": round(100 * float((a["asistencias"] > 0).mean()), 1),
            "sin_asistencia_anio": int((a["asistencias"] == 0).sum()),
            "un_solo_contacto": int(((a["asistencias"] >= 2) & (a["personas_distintas"] == 1)).sum()),
            "asistencias_2026": int(res.asistencias["valida"].sum()),
            "asistencias_afiliados": int((res.asistencias["valida"] & res.asistencias["en_crm"]).sum()),
        },
        "satisfaccion": {"media_1a5": res.respuestas["satisfaccion"].mean(), "respuestas": len(res.respuestas),
                         "afiliados_con_respuesta": int((a["n_respuestas"] > 0).sum())},
        "nps_post_evento": {**nps, "advertencia": "Muestra pequeña (octubre a noviembre de 2026)."},
        "base_historica": {"canceladas": int((e["estado"] == "Cancelado").sum()), "expiradas": int((e["estado"] == "Expirado").sum()),
                           "sin_estado": int((e["estado"] == "Sin estado").sum()), "no_vigentes_total": len(no_vig)},
        "renovaron_ultimos_2_meses": int(a["renovo_recientemente"].sum()),
        "distribuciones": {"sector": dist("sector"), "tamano": dist("tamano"), "ciudad": dist("ciudad"), "tipo": dist("tipo", 6)},
        "riesgo_medio": a["riesgo"].mean().round(1), "salud_media": a["salud"].mean().round(1),
    }


def _control_general_meta(c: dict[str, Any]) -> dict[str, Any]:
    """Control de la hoja GENERAL sin el detalle fila por fila (que va a control_rechazos.csv)."""
    return {k: v for k, v in c.items() if k not in ("lectura", "filas_rechazadas")}


def _calidad_meta(cal: dict[str, Any]) -> dict[str, Any]:
    """Resumen de la auditoría de calidad para ``meta.json`` (el detalle completo está en control_calidad.csv y docs/LIMPIEZA.md)."""
    llaves = ("filas", "columnas", "celdas_nulas", "celdas_centinela", "pct_sin_dato", "columnas_vacias", "duplicados_exactos", "duplicados_clave", "columnas_no_snake_case")
    return {
        "fuentes": [{"id": f["id"], "nombre": f["nombre"], "tablas_destino": f["tablas_destino"],
                     "antes": {k: f["antes"].get(k) for k in llaves}, "despues": {k: f["despues"].get(k) for k in llaves},
                     "anomalias": [{"codigo": a["codigo"], "descripcion": a["descripcion"], "cantidad": a["cantidad"]} for a in f["anomalias"]],
                     "categorias": f["categorias"]} for f in cal["fuentes"]],
        "informes": [{k: i[k] for k in ("id", "nombre", "registros_declarados", "registros_recuperados", "coincide_con_declarados", "filas_vacias", "filas_total")}
                     for i in cal["informes"]["informes"]],
        "conciliacion": cal["conciliacion"], "rechazos": cal["rechazos"],
    }


def _mes_fin(mes: pd.Period) -> str:
    return mes.end_time.strftime("%Y-%m-%d")


def json_tendencias(res: Resultado) -> dict[str, Any]:
    """Series mensuales con fechas reales: asistencia, satisfacción, afiliaciones, vencimientos, salidas y renovaciones.

    Cada mes trae todas las métricas; ``null`` significa «fuera de la cobertura de esa fuente» (por ejemplo, no hay
    asistencia antes de enero de 2026) y ``0`` significa «cubierto y sin registros». La cobertura de cada serie se
    declara en ``cobertura``.
    """
    corte = pd.Timestamp(res.cfg.fecha_corte)
    desde = pd.Period(config.TENDENCIAS_DESDE, "M")
    e, a = res.empresas, res.asistencias[res.asistencias["valida"]]
    ev = res.eventos.set_index("evento_id")
    a = a.assign(mes=a["evento_id"].map(ev["mes"]))
    r = res.respuestas.dropna(subset=["completada"]).assign(mes=lambda d: d["completada"].dt.strftime("%Y-%m"))
    vig = e[e["vigente"]]
    sal = e[e["no_vigente"]]
    meses_exp = pd.concat([vig["fecha_expiracion"], sal["fecha_expiracion"]]).dropna()
    hasta = max(meses_exp.max().to_period("M") if len(meses_exp) else corte.to_period("M"), corte.to_period("M"))
    rango = pd.period_range(desde, hasta, freq="M")

    def por_mes(fechas: pd.Series) -> pd.Series:
        return fechas.dropna().dt.to_period("M").astype(str).value_counts()

    af_mes, afv_mes = por_mes(e["fecha_afiliacion"]), por_mes(vig["fecha_afiliacion"])
    venc_mes, sal_mes = por_mes(vig["fecha_expiracion"]), por_mes(sal["fecha_expiracion"])
    ren = res.renovaciones.dropna(subset=["mes_factura"]) if len(res.renovaciones) else res.renovaciones
    ren_mes = por_mes(ren["mes_factura"]) if len(ren) else pd.Series(dtype=int)
    g_as = a.groupby("mes")
    asist = pd.DataFrame({
        "eventos": g_as["evento_id"].nunique(), "asistentes": g_as.size(), "personas": g_as["persona_id"].nunique(),
        "empresas": g_as["empresa_id"].nunique(), "empresas_afiliadas_vigentes": a[a["vigente"]].groupby("mes")["empresa_id"].nunique(),
    }).fillna(0).astype(int)
    fechas_ev = {m: sorted(_iso(x) for x in res.eventos.loc[res.eventos["mes"] == m, "fecha"]) for m in res.eventos["mes"].unique()}
    g_r = r.groupby("mes")
    enc = pd.DataFrame({"respuestas": g_r.size(), "satisfaccion": g_r["satisfaccion"].mean().round(3)})
    nps_mes = {m: lp.calcular_nps(g["nps_puntaje"]) for m, g in g_r}
    cob_as = (pd.Period(a["mes"].min(), "M"), pd.Period(a["mes"].max(), "M")) if len(a) else (None, None)
    cob_en = (pd.Period(r["mes"].min(), "M"), pd.Period(r["mes"].max(), "M")) if len(r) else (None, None)
    cob_ren = (ren["mes_factura"].min().to_period("M"), ren["mes_factura"].max().to_period("M")) if len(ren) else (None, None)
    cob_af = (e["fecha_afiliacion"].min().to_period("M"), corte.to_period("M"))

    def en(p: pd.Period, cob: tuple[Any, Any]) -> bool:
        return cob[0] is not None and cob[0] <= p <= cob[1]

    meses = []
    for p in rango:
        m = str(p)
        fila: dict[str, Any] = {"mes": m, "inicio": p.start_time.strftime("%Y-%m-%d"), "fin": _mes_fin(p), "parcial": bool(p == corte.to_period("M"))}
        if en(p, cob_as):
            s = asist.loc[m] if m in asist.index else None
            fila.update({k: (int(s[k]) if s is not None else 0) for k in asist.columns})
            fila["fechas_eventos"] = fechas_ev.get(m, [])
        else:
            fila.update({k: None for k in asist.columns})
            fila["fechas_eventos"] = []
        if en(p, cob_en):
            tiene = m in enc.index
            nps = nps_mes.get(m, {"n": 0, "nps": None})
            fila.update({"respuestas": int(enc.loc[m, "respuestas"]) if tiene else 0, "satisfaccion": float(enc.loc[m, "satisfaccion"]) if tiene else None,
                         "nps": nps["nps"], "n_nps": nps["n"]})
        else:
            fila.update({"respuestas": None, "satisfaccion": None, "nps": None, "n_nps": None})
        fila["afiliaciones"] = int(af_mes.get(m, 0)) if en(p, cob_af) else None
        fila["afiliaciones_vigentes"] = int(afv_mes.get(m, 0)) if en(p, cob_af) else None
        fila["vencimientos"] = int(venc_mes.get(m, 0))
        fila["salidas"] = int(sal_mes.get(m, 0))
        fila["renovaciones"] = int(ren_mes.get(m, 0)) if en(p, cob_ren) else None
        meses.append(fila)

    def cob(c: tuple[Any, Any], extra: str = "") -> dict[str, Any]:
        return {"desde": str(c[0]) if c[0] is not None else None, "hasta": str(c[1]) if c[1] is not None else None, "nota": extra}

    por_anio = e["fecha_afiliacion"].dropna().dt.year.value_counts().sort_index()
    por_anio_v = vig["fecha_afiliacion"].dropna().dt.year.value_counts()
    ev_serie = []
    for x in res.eventos.sort_values(["fecha", "evento_id"]).to_dict("records"):
        ae = a[a["evento_id"] == x["evento_id"]]
        re_ = res.respuestas[res.respuestas["evento_id"] == x["evento_id"]]
        ev_serie.append({"id": x["evento_id"], "fecha": _iso(x["fecha"]), "fecha_fin": _iso(x["fecha_fin"]), "asistentes": len(ae), "personas": int(ae["persona_id"].nunique()),
                         "empresas": int(ae["empresa_id"].nunique()), "n_respuestas": len(re_), "satisfaccion": re_["satisfaccion"].mean() if len(re_) else None})
    venc_dia = vig["fecha_expiracion"].dropna().dt.strftime("%Y-%m-%d").value_counts().sort_index()
    return {
        "fecha_corte": res.cfg.fecha_corte.isoformat(),
        "generado_en": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "definiciones": {
            "meses": "Un registro por mes calendario entre %s y el último mes con vencimientos; todas las series comparten el mismo eje." % config.TENDENCIAS_DESDE,
            "valores_nulos": "null significa fuera de la cobertura de la fuente (no hay dato); 0 significa mes cubierto sin registros.",
            "asistentes": "Asistencias válidas (sin duplicados ni agendados) de los eventos que empiezan en el mes.",
            "personas_y_empresas": "Personas y empresas distintas con asistencia válida en el mes; empresas_afiliadas_vigentes cuenta solo las que hoy son afiliadas vigentes.",
            "satisfaccion": "Media de satisfacción de 1 a 5 de las respuestas completadas en el mes (todas las encuestas, incluidas las de 2025); nps es el NPS post-evento del mes.",
            "afiliaciones": "Empresas del CRM por mes de su fecha de afiliación (incluye las que luego salieron); afiliaciones_vigentes cuenta las que siguen vigentes.",
            "vencimientos": "Afiliados vigentes por mes de su fecha de expiración (los de meses anteriores al corte son vigentes con fecha vencida).",
            "salidas": "Empresas canceladas, expiradas o inactivas por mes de su fecha de expiración (la fecha real de salida no está registrada).",
            "renovaciones": "Renovaciones facturadas por mes, del informe de Zoho de los últimos dos meses.",
        },
        "cobertura": {
            "asistencia": cob(cob_as, "El libro de asistencia cubre del 5 de enero al 27 de octubre de 2026."),
            "satisfaccion": cob(cob_en, "Incluye respuestas de 2025 de las encuestas presencial y virtual."),
            "afiliaciones": cob(cob_af, "El mes del corte está incompleto."),
            "vencimientos": cob((rango[0], rango[-1])),
            "renovaciones": cob(cob_ren, "El informe cubre solo las renovaciones facturadas en septiembre y octubre de 2026."),
        },
        "meses": meses,
        "por_evento": ev_serie,
        "afiliaciones_por_anio": [{"anio": int(y), "afiliaciones": int(n), "afiliaciones_vigentes": int(por_anio_v.get(y, 0))} for y, n in por_anio.items()],
        "vencimientos_por_fecha": [{"fecha": d, "vencen": int(n)} for d, n in venc_dia.items()],
        "totales": {
            "asistentes": int(len(a)), "eventos": int(len(res.eventos)), "afiliados_vigentes": int(len(vig)),
            "vencimientos_con_fecha": int(vig["fecha_expiracion"].notna().sum()), "vencimientos_sin_fecha": int(vig["fecha_expiracion"].isna().sum()),
            "renovaciones": int(len(res.renovaciones)), "respuestas": int(len(r)),
            "antes_de_la_serie": {
                "afiliaciones": int((e["fecha_afiliacion"] < desde.start_time).sum()), "vencimientos": int((vig["fecha_expiracion"] < desde.start_time).sum()),
                "salidas": int((sal["fecha_expiracion"] < desde.start_time).sum()),
            },
        },
    }


def json_meta(res: Resultado) -> dict[str, Any]:
    """Metadatos: fecha de generación, fuentes, tasa de cruce, definiciones del score y avisos de calidad."""
    p = res.cfg.pesos
    return {
        "generado_en": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "fecha_corte": res.cfg.fecha_corte.isoformat(), "version_pipeline": __version__, "version_pesos": p.get("version"),
        "fuentes": {
            "crm_filas": res.stats_crm["filas_originales"], "crm_empresas_unicas": res.stats_crm["empresas_unicas"],
            "eventos": len(res.eventos), "registros_asistencia": len(res.asistencias_raw),
            "asistencias_validas": int(res.asistencias["valida"].sum()),
            "respuestas_encuesta": len(res.respuestas),
        },
        "cruce": res.cruce,
        "score": {
            "descripcion": p.get("descripcion"), "umbrales": p["bandas"], "maximo_puntos": res.afiliados.attrs.get("maximo_puntos"),
            "bandas": {"Saludable": "Riesgo menor a %s" % p["bandas"]["umbral_atencion"],
                       "Atención": "Riesgo desde %s y menor a %s" % (p["bandas"]["umbral_atencion"], p["bandas"]["umbral_riesgo_alto"]),
                       "Riesgo alto": "Riesgo desde %s" % p["bandas"]["umbral_riesgo_alto"]},
            "pesos": p, "validacion": res.validacion,
        },
        "control_hoja_general": _control_general_meta(res.control_general),
        "avisos_calidad": res.avisos,
        "homologacion": {"version": config.HOMOLOGACION.get("version"), "archivo": "config/homologacion.json",
                         "secciones": sorted(k for k, v in config.HOMOLOGACION.items() if isinstance(v, dict) and "equivalencias" in v)},
        "modelo": {n: {"filas": int(len(d)), "columnas": int(d.shape[1]), "clase": esquema.ESQUEMA[n].clase} for n, d in res.modelo.items()},
        "integridad": resumen_para_meta(res.integridad),
        "calidad": _calidad_meta(res.calidad),
        "supuestos": [
            "La clave de unión es el código de empresa (EMP-0000); el NIT fue eliminado en la anonimización.",
            "Afiliado vigente: estado de membresía Activo, Periodo de Gracia o Pronto a Expirar.",
            "Asistencia: un registro por persona y evento; se descartan repetidos y registros en estado agendado.",
            "Las encuestas se asignan a un evento 2026 por fecha de respuesta y modalidad; las demás no tienen evento.",
            "La asistencia solo cubre 2026; la satisfacción usa respuestas de los últimos 12 meses.",
            "Niveles 2027: Estándar es Conectar, Premium es Crecer y Elite es Liderar.",
        ],
    }


LEGADO = ("empresas", "eventos", "asistencias", "respuestas", "afiliados_score")


def _csv(df: pd.DataFrame, ruta: Path) -> None:
    df.to_csv(ruta, index=False, encoding="utf-8-sig", date_format="%Y-%m-%d")


def tabla_control_calidad(cal: dict[str, Any]) -> pd.DataFrame:
    """Aplana la auditoría de calidad en una tabla larga: métricas, anomalías, categorías y conciliación."""
    llaves = ("filas", "columnas", "celdas_nulas", "celdas_centinela", "pct_sin_dato", "columnas_vacias", "duplicados_exactos", "duplicados_clave", "columnas_no_snake_case")
    filas: list[dict[str, Any]] = []
    for f in cal["fuentes"]:
        for k in llaves:
            filas.append({"fuente": f["id"], "tipo": "metrica", "concepto": k, "antes": f["antes"].get(k), "despues": f["despues"].get(k), "detalle": None})
        for a in f["anomalias"]:
            filas.append({"fuente": f["id"], "tipo": "anomalia", "concepto": a["codigo"], "antes": a["cantidad"], "despues": None, "detalle": f"{a['descripcion']} {a['tratamiento']}"})
        for c in f["categorias"]:
            filas.append({"fuente": f["id"], "tipo": "categoria", "concepto": c["columna"], "antes": c["antes"], "despues": c["despues"], "detalle": "valores distintos"})
    for i in cal["informes"]["informes"]:
        filas.append({"fuente": i["id"], "tipo": "informe", "concepto": "registros", "antes": i["registros_declarados"], "despues": i["registros_recuperados"],
                      "detalle": f"filas vacías {i['filas_vacias']}, totales {i['filas_total']}, encabezados repetidos {i['filas_encabezado_repetido']}"})
    for c in cal["conciliacion"]:
        filas.append({"fuente": "conciliacion", "tipo": "conciliacion", "concepto": c["codigo"], "antes": c["esperado"], "despues": c["obtenido"],
                      "detalle": f"{'coincide' if c['coincide'] else 'difiere'}. {c['descripcion']} {c['nota']}".strip()})
    df = pd.DataFrame(filas, columns=["fuente", "tipo", "concepto", "antes", "despues", "detalle"]).astype({"antes": object, "despues": object})
    ent = lambda v: int(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and v == v and float(v).is_integer() else v  # noqa: E731
    df["antes"], df["despues"] = df["antes"].map(ent), df["despues"].map(ent)
    return df


def exportar_tablas(res: Resultado) -> None:
    """Guarda en ``data/processed`` el modelo normalizado, las tablas de control y las tablas anchas intermedias.

    El modelo (``dim_*`` y ``fact_*``) y los controles (``control_*``) quedan en la raíz; las tablas anchas de la v1
    (una fila por empresa o por evento con todo mezclado) quedan en ``intermedias/`` por compatibilidad. Ninguna se versiona.
    """
    d = res.cfg.dir_procesados
    d.mkdir(parents=True, exist_ok=True)
    for viejo in LEGADO:  # la v1 las escribía en la raíz
        (d / f"{viejo}.csv").unlink(missing_ok=True)
    for n, df in res.modelo.items():
        _csv(df, d / f"{n}.csv")
    _csv(res.rechazos, d / "control_rechazos.csv")
    _csv(res.integridad["huerfanos"], d / "control_huerfanos.csv")
    _csv(res.integridad["relaciones"], d / "control_integridad.csv")
    _csv(tabla_control_calidad(res.calidad), d / "control_calidad.csv")
    i = d / "intermedias"
    i.mkdir(exist_ok=True)
    res.empresas.to_csv(i / "empresas.csv", index=False, encoding="utf-8-sig")
    res.eventos.to_csv(i / "eventos.csv", index=False, encoding="utf-8-sig")
    res.asistencias.to_csv(i / "asistencias.csv", index=False, encoding="utf-8-sig")
    res.respuestas.to_csv(i / "respuestas.csv", index=False, encoding="utf-8-sig")
    af = res.afiliados.drop(columns=["factores"]).assign(
        factores=res.afiliados["factores"].map(lambda fs: " | ".join(f["texto"] for f in fs)))
    af.to_csv(i / "afiliados_score.csv", index=False, encoding="utf-8-sig")


def exportar_todo(res: Resultado) -> None:
    """Escribe tablas intermedias y todos los JSON del frontend."""
    exportar_tablas(res)
    w = res.cfg.dir_web
    escribir_json(json_meta(res), w / "meta.json")
    escribir_json(json_resumen(res), w / "resumen.json")
    escribir_json(json_afiliados(res), w / "afiliados.json")
    escribir_json(json_eventos(res), w / "eventos.json")
    escribir_json(json_ejecutivas(res), w / "ejecutivas.json")
    escribir_json(json_encuestas(res), w / "encuestas.json")
    escribir_json(json_segmentos(res), w / "segmentos.json")
    escribir_json(json_tendencias(res), w / "tendencias.json")
