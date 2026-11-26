"""Score de salud y riesgo de no renovación, transparente y explicable.

Cada señal suma puntos según ``config/pesos_score.json``. El riesgo (0 a 100) es
el total de puntos dividido por el máximo posible; la salud es ``100 - riesgo``.
Cada afiliado conserva la lista de factores con su aporte y un texto en español.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, asdict
from typing import Any, Iterable, Mapping

import numpy as np
import pandas as pd

BANDAS = ("Saludable", "Atención", "Riesgo alto")

ACCIONES: dict[str, str] = {
    "vencimiento": "Contactar para la renovación y presentar el valor recibido durante el año.",
    "sin_asistencia_90d": "Invitar personalmente a la próxima actividad de su línea de interés.",
    "sin_asistencia_anio": "Recordar qué incluye su nivel y proponer una primera experiencia.",
    "una_sola_asistencia": "Proponer que otras personas del equipo participen.",
    "contacto_unico": "Abrir la relación con otras personas y niveles de cargo de la empresa.",
    "satisfaccion": "Llamar para escuchar su experiencia antes de cualquier envío masivo.",
    "detractor": "Llamada de seguimiento de la ejecutiva tras la calificación baja.",
    "antiguedad": "Acompañar el primer ciclo con encuesta de 90 días y plan de uso.",
    "nivel": "Revisar si el nivel responde a sus necesidades.",
    "ejecutiva": "Asignar una ejecutiva de cuenta.",
    "comunidad": "Invitar a una comunidad temática afín.",
}


@dataclass
class Factor:
    """Aporte de una señal al riesgo."""

    codigo: str
    grupo: str
    puntos: float
    texto: str


def _num(v: Any) -> float | None:
    """Convierte a ``float``; devuelve ``None`` para nulos, NaN o valores no numéricos."""
    if v is None:
        return None
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(x) else x


def _coma(x: float, dec: int = 1) -> str:
    """Formatea con coma decimal, como se escribe en español."""
    return f"{x:.{dec}f}".replace(".", ",")


def maximo_posible(pesos: Mapping[str, Any], excluir: Iterable[str] = ()) -> float:
    """Suma de los puntos máximos de cada grupo de factores no excluido."""
    ex = set(excluir)
    p = pesos
    grupos = {
        "vencimiento": max(p["vencimiento"].values()),
        "participacion": p["participacion"]["sin_asistencia_90d"] + p["participacion"]["sin_asistencia_anio"],
        "satisfaccion": p["satisfaccion"]["promedio_bajo"] + p["satisfaccion"]["detractor"],
        "antiguedad": max(p["antiguedad"].values()),
        "nivel": max(p["nivel"].values()),
        "ejecutiva": p["ejecutiva"]["sin_asignar"],
        "comunidad": p["comunidad"]["sin_comunidad"],
    }
    return float(sum(v for k, v in grupos.items() if k not in ex))


def puntuar_afiliado(r: Mapping[str, Any], pesos: Mapping[str, Any], excluir: Iterable[str] = ()) -> list[Factor]:
    """Calcula los factores de riesgo de un afiliado (con puntos mayores a cero)."""
    ex = set(excluir)
    fac: list[Factor] = []
    p = pesos

    dv = _num(r.get("dias_vencimiento"))
    if "vencimiento" not in ex:
        w = p["vencimiento"]
        if dv is None:
            pts, t = w["sin_fecha"], "No tiene fecha de expiración registrada en el CRM"
        elif dv < 0:
            pts, t = w["vencida"], f"La afiliación venció hace {int(-dv)} días y sigue sin renovarse"
        elif dv <= 30:
            pts, t = w["hasta_30"], f"La afiliación vence en {int(dv)} días"
        elif dv <= 60:
            pts, t = w["hasta_60"], f"La afiliación vence en {int(dv)} días"
        elif dv <= 90:
            pts, t = w["hasta_90"], f"La afiliación vence en {int(dv)} días"
        elif dv <= 180:
            pts, t = w["hasta_180"], f"La afiliación vence en {int(dv)} días"
        else:
            pts, t = w["mas_180"], ""
        if pts > 0:
            fac.append(Factor("vencimiento", "vencimiento", float(pts), t))

    w = p["participacion"]
    dias_af = _num(r.get("dias_afiliacion"))
    mult = w["factor_afiliado_nuevo"] if dias_af is not None and dias_af < w["dias_afiliado_nuevo"] else 1.0
    asist, a90 = int(_num(r.get("asistencias")) or 0), int(_num(r.get("asistencias_90d")) or 0)
    pers = int(_num(r.get("personas_distintas")) or 0)
    if a90 == 0:
        fac.append(Factor("sin_asistencia_90d", "participacion", w["sin_asistencia_90d"] * mult,
                          "Ninguna asistencia a eventos en el último trimestre registrado"))
    if asist == 0:
        fac.append(Factor("sin_asistencia_anio", "participacion", w["sin_asistencia_anio"] * mult,
                          "No registra ninguna asistencia a eventos en 2026"))
    elif asist == 1:
        fac.append(Factor("una_sola_asistencia", "participacion", float(w["una_sola_asistencia"]),
                          "Solo una asistencia registrada en el año"))
    if asist >= 2 and pers == 1:
        fac.append(Factor("contacto_unico", "participacion", float(w["contacto_unico"]),
                          "Siempre asiste la misma persona de la empresa"))

    w = p["satisfaccion"]
    sat, nres = _num(r.get("satisfaccion")), int(_num(r.get("n_respuestas")) or 0)
    if "satisfaccion" not in ex and sat is not None and nres > 0:
        if sat < w["umbral_bajo"]:
            fac.append(Factor("satisfaccion", "satisfaccion", float(w["promedio_bajo"]),
                              f"Satisfacción promedio baja: {_coma(sat)} de 5 ({nres} respuestas)"))
        elif sat < w["umbral_medio"]:
            fac.append(Factor("satisfaccion", "satisfaccion", float(w["promedio_medio"]),
                              f"Satisfacción promedio moderada: {_coma(sat)} de 5 ({nres} respuestas)"))
        nmin = _num(r.get("nps_minimo"))
        if nmin is not None and nmin <= 6:
            fac.append(Factor("detractor", "satisfaccion", float(w["detractor"]),
                              f"Calificó con {int(nmin)} la recomendación (detractor)"))

    w = p["antiguedad"]
    ant = _num(r.get("antiguedad_anios"))
    if ant is None:
        fac.append(Factor("antiguedad", "antiguedad", float(w["sin_dato"]), "No hay fecha de afiliación para medir antigüedad"))
    elif ant < 1:
        fac.append(Factor("antiguedad", "antiguedad", float(w["primer_anio"]),
                          f"Primer año de afiliación ({max(int(ant * 12), 0)} meses), aún sin renovación"))
    elif ant < 3:
        fac.append(Factor("antiguedad", "antiguedad", float(w["segundo_a_tercero"]),
                          f"Afiliada hace {_coma(ant)} años, todavía en etapa temprana"))

    nivel = r.get("nivel") or "Sin dato"
    pts = p["nivel"].get(nivel, p["nivel"]["Sin dato"])
    if pts > 0:
        fac.append(Factor("nivel", "nivel", float(pts),
                          f"Nivel {nivel}" if nivel != "Sin dato" else "Nivel de afiliación sin registrar"))

    if "ejecutiva" not in ex and bool(r.get("sin_ejecutiva")):
        fac.append(Factor("ejecutiva", "ejecutiva", float(p["ejecutiva"]["sin_asignar"]), "Sin ejecutiva de cuenta asignada"))

    if "comunidad" not in ex and not bool(r.get("comunidad")):
        fac.append(Factor("comunidad", "comunidad", float(p["comunidad"]["sin_comunidad"]), "No está vinculada a ninguna comunidad"))

    if bool(r.get("renovo_recientemente")):
        fac.append(Factor("renovacion_reciente", "renovacion", -float(p["renovacion_reciente"]["descuento"]),
                          "Renovó en los últimos dos meses (reduce el riesgo)"))
    return [f for f in fac if f.grupo not in ex or f.grupo == "renovacion"]


def asignar_banda(riesgo: float, pesos: Mapping[str, Any]) -> str:
    """Clasifica un riesgo 0-100 en Saludable, Atención o Riesgo alto."""
    b = pesos["bandas"]
    if riesgo >= b["umbral_riesgo_alto"]:
        return "Riesgo alto"
    return "Atención" if riesgo >= b["umbral_atencion"] else "Saludable"


def calcular_score(df: pd.DataFrame, pesos: Mapping[str, Any], excluir: Iterable[str] = ()) -> pd.DataFrame:
    """Aplica el score a todas las filas y añade puntos, riesgo, salud, banda y factores."""
    excluir = tuple(excluir)
    maximo = maximo_posible(pesos, excluir)
    out = df.copy()
    listas = [puntuar_afiliado(r, pesos, excluir) for r in out.to_dict("records")]
    puntos = np.array([max(sum(f.puntos for f in fs), 0.0) for fs in listas])
    out["puntos"] = puntos.round(1)
    out["riesgo"] = np.clip(100 * puntos / maximo, 0, 100).round(1)
    out["salud"] = (100 - out["riesgo"]).round(1)
    out["banda"] = [asignar_banda(x, pesos) for x in out["riesgo"]]
    out["factores"] = [
        [asdict(f) for f in sorted((f for f in fs if f.puntos > 0), key=lambda f: -f.puntos)] for fs in listas
    ]
    out["accion"] = [ACCIONES.get(fs[0]["codigo"], "Mantener el seguimiento habitual.") if fs else
                     "Mantener el seguimiento habitual." for fs in out["factores"]]
    out.attrs["maximo_puntos"] = maximo
    return out


def auc_rango(puntaje: np.ndarray, etiqueta: np.ndarray) -> float:
    """Área bajo la curva ROC por estadístico de rangos (Mann-Whitney), sin dependencias externas."""
    puntaje, etiqueta = np.asarray(puntaje, float), np.asarray(etiqueta, bool)
    pos, neg = puntaje[etiqueta], puntaje[~etiqueta]
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    rangos = pd.Series(np.concatenate([pos, neg])).rank(method="average").to_numpy()
    return float((rangos[: len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))
