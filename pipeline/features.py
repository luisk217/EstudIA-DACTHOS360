"""Cálculo de variables por afiliado a una fecha de referencia.

La fecha de referencia puede ser distinta por empresa, lo que permite reutilizar
las mismas funciones en la validación retrospectiva (referencia = fecha de
expiración de quienes ya salieron).
"""
from __future__ import annotations

import pandas as pd

from . import config


def calcular_features(
    base: pd.DataFrame,
    asistencias: pd.DataFrame,
    respuestas: pd.DataFrame,
    referencia: pd.Series,
    renovaron: set[str] | None = None,
    cobertura_inicio: pd.Timestamp = pd.Timestamp(config.INICIO_COBERTURA_ASISTENCIA),
    ventana_reciente: int = config.VENTANA_RECIENTE_DIAS,
    ventana_satisfaccion: int = config.VENTANA_SATISFACCION_DIAS,
) -> pd.DataFrame:
    """Devuelve una fila por empresa de ``base`` con las variables que alimentan el score.

    ``referencia`` es una serie indexada por ``empresa_id`` con la fecha a la
    que se mide cada empresa; solo se usan eventos y respuestas hasta esa fecha.
    """
    f = base.set_index("empresa_id").copy()
    ref = referencia.reindex(f.index)
    f["fecha_referencia"] = ref
    f["dias_vencimiento"] = (f["fecha_expiracion"] - ref).dt.days
    inicio = f["fecha_afiliacion"].where(f["fecha_afiliacion"].notna(), f["miembro_desde"])
    f["dias_afiliacion"] = (ref - inicio).dt.days
    f["antiguedad_anios"] = (f["dias_afiliacion"] / 365.25).round(2)

    a = asistencias[asistencias["valida"]].copy()
    a = a[a["empresa_id"].isin(f.index)]
    a["ref"] = a["empresa_id"].map(ref)
    a = a[(a["fecha"] <= a["ref"]) & (a["fecha"] >= cobertura_inicio)]
    # La ventana reciente termina en el último evento registrado: el libro no trae asistencia posterior.
    fin_cob = asistencias.loc[asistencias["valida"], "fecha"].max()
    fin = a["ref"].where(a["ref"] < fin_cob, fin_cob)
    a["reciente"] = a["fecha"] > fin - pd.Timedelta(days=ventana_reciente)
    f.attrs["fin_cobertura_asistencia"] = fin_cob
    g = a.groupby("empresa_id")
    f["asistencias"] = g.size()
    f["asistencias_90d"] = a[a["reciente"]].groupby("empresa_id").size()
    f["eventos_distintos"] = g["evento_id"].nunique()
    f["personas_distintas"] = g["persona_id"].nunique()
    f["ultima_asistencia"] = g["fecha"].max()
    for c in ("asistencias", "asistencias_90d", "eventos_distintos", "personas_distintas"):
        f[c] = f[c].fillna(0).astype(int)
    f["dias_ultima_asistencia"] = (ref - f["ultima_asistencia"]).dt.days

    r = respuestas[respuestas["empresa_id"].isin(f.index) & respuestas["completada"].notna()].copy()
    r["ref"] = r["empresa_id"].map(ref)
    r = r[(r["completada"] <= r["ref"]) & (r["completada"] > r["ref"] - pd.Timedelta(days=ventana_satisfaccion))]
    gr = r.groupby("empresa_id")
    f["n_respuestas"] = gr.size()
    f["satisfaccion"] = gr["satisfaccion"].mean().round(2)
    f["nps_minimo"] = gr["nps_puntaje"].min()
    f["n_respuestas"] = f["n_respuestas"].fillna(0).astype(int)
    f["detractor"] = f["nps_minimo"].le(6).fillna(False)
    f["renovo_recientemente"] = f.index.isin(renovaron or set())
    f["sin_ejecutiva"] = f["ejecutiva"].eq("Sin asignar")
    return f.reset_index()
