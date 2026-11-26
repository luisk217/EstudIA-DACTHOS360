"""Casos límite del score: umbrales de bandas, tramos de vencimiento, nulos y topes."""
import math

import numpy as np
import pandas as pd
import pytest

from pipeline import score as sc
from tests.test_score import base


def _pts(pesos, **kw):
    return sum(f.puntos for f in sc.puntuar_afiliado(base(**kw), pesos) if f.grupo == "vencimiento")


@pytest.mark.parametrize("riesgo,esperada", [
    (0, "Saludable"), (34.9, "Saludable"), (35, "Atención"), (54.9, "Atención"), (55, "Riesgo alto"), (100, "Riesgo alto"),
])
def test_bandas_en_los_umbrales(pesos, riesgo, esperada):
    assert sc.asignar_banda(riesgo, pesos) == esperada


@pytest.mark.parametrize("dias,clave", [
    (-1, "vencida"), (0, "hasta_30"), (30, "hasta_30"), (31, "hasta_60"), (60, "hasta_60"),
    (61, "hasta_90"), (90, "hasta_90"), (91, "hasta_180"), (180, "hasta_180"), (181, "mas_180"),
])
def test_tramos_de_vencimiento_en_los_bordes(pesos, dias, clave):
    assert _pts(pesos, dias_vencimiento=dias) == pesos["vencimiento"][clave]


def test_fecha_vencida_explica_los_dias(pesos):
    # El texto debe decir hace cuántos días venció (sin signos negativos).
    f = sc.puntuar_afiliado(base(dias_vencimiento=-12), pesos)[0]
    assert f.codigo == "vencimiento" and "hace 12 días" in f.texto and "-" not in f.texto


def test_nulos_y_nan_no_rompen_ni_penalizan_de_mas(pesos):
    vacio = dict(dias_vencimiento=float("nan"), dias_afiliacion=None, antiguedad_anios=float("nan"), asistencias=None,
                 asistencias_90d=float("nan"), personas_distintas=None, satisfaccion=float("nan"), n_respuestas=None,
                 nps_minimo=None, nivel=None, sin_ejecutiva=None, comunidad=None, renovo_recientemente=None)
    c = {f.codigo for f in sc.puntuar_afiliado(vacio, pesos)}
    assert {"vencimiento", "antiguedad", "nivel", "sin_asistencia_90d", "sin_asistencia_anio", "comunidad"} <= c
    assert "satisfaccion" not in c and "detractor" not in c and "ejecutiva" not in c
    assert sc.puntuar_afiliado({}, pesos)  # un registro totalmente vacío tampoco falla


def test_peor_caso_llega_a_cien_y_nunca_pasa(pesos):
    peor = base(dias_vencimiento=-1, asistencias=0, asistencias_90d=0, personas_distintas=0, satisfaccion=1.0,
                n_respuestas=3, nps_minimo=0, antiguedad_anios=0.5, dias_afiliacion=200, nivel="Conectar",
                sin_ejecutiva=True, comunidad=False)
    out = sc.calcular_score(pd.DataFrame([peor]), pesos)
    assert out.loc[0, "puntos"] == sc.maximo_posible(pesos) == out.attrs["maximo_puntos"]
    assert out.loc[0, "riesgo"] == 100 and out.loc[0, "salud"] == 0 and out.loc[0, "banda"] == "Riesgo alto"


def test_mejor_caso_con_descuento_no_baja_de_cero(pesos):
    mejor = base(renovo_recientemente=True)  # sin factores: el descuento no puede dar riesgo negativo
    out = sc.calcular_score(pd.DataFrame([mejor]), pesos)
    assert out.loc[0, "riesgo"] == 0 and out.loc[0, "salud"] == 100 and out.loc[0, "factores"] == []


def test_riesgo_y_salud_suman_cien_en_barrido(pesos):
    rng = np.random.default_rng(7)
    filas = [base(dias_vencimiento=int(rng.integers(-200, 400)), asistencias=int(rng.integers(0, 6)),
                  asistencias_90d=int(rng.integers(0, 3)), personas_distintas=int(rng.integers(0, 4)),
                  satisfaccion=float(rng.uniform(1, 5)), nps_minimo=int(rng.integers(0, 11)),
                  antiguedad_anios=float(rng.uniform(0, 6)), sin_ejecutiva=bool(rng.integers(0, 2)),
                  comunidad=bool(rng.integers(0, 2)), renovo_recientemente=bool(rng.integers(0, 2)),
                  nivel=str(rng.choice(["Conectar", "Crecer", "Liderar", "Sin dato"]))) for _ in range(300)]
    out = sc.calcular_score(pd.DataFrame(filas), pesos)
    assert out["riesgo"].between(0, 100).all() and out["salud"].between(0, 100).all()
    assert ((out["riesgo"] + out["salud"]) - 100).abs().max() < 0.051
    assert set(out["banda"]) <= set(sc.BANDAS)


def test_satisfaccion_en_los_umbrales(pesos):
    def pts(sat):
        return sum(f.puntos for f in sc.puntuar_afiliado(base(satisfaccion=sat), pesos) if f.codigo == "satisfaccion")
    s = pesos["satisfaccion"]
    assert pts(s["umbral_bajo"] - 0.01) == s["promedio_bajo"]
    assert pts(s["umbral_bajo"]) == s["promedio_medio"]
    assert pts(s["umbral_medio"] - 0.01) == s["promedio_medio"]
    assert pts(s["umbral_medio"]) == 0


def test_detractor_en_el_borde(pesos):
    assert "detractor" in {f.codigo for f in sc.puntuar_afiliado(base(nps_minimo=6), pesos)}
    assert "detractor" not in {f.codigo for f in sc.puntuar_afiliado(base(nps_minimo=7), pesos)}


def test_afiliado_nuevo_en_el_borde_de_dias(pesos):
    sin = dict(asistencias=0, asistencias_90d=0, personas_distintas=0)
    n = pesos["participacion"]["dias_afiliado_nuevo"]

    def part(d):
        return sum(f.puntos for f in sc.puntuar_afiliado(base(**sin, dias_afiliacion=d), pesos) if f.grupo == "participacion")
    assert part(n - 1) < part(n) == part(n + 500)


def test_antiguedad_en_los_bordes(pesos):
    def pts(a):
        return sum(f.puntos for f in sc.puntuar_afiliado(base(antiguedad_anios=a), pesos) if f.codigo == "antiguedad")
    assert pts(0.99) == pesos["antiguedad"]["primer_anio"]
    assert pts(1.0) == pesos["antiguedad"]["segundo_a_tercero"]
    assert pts(2.99) == pesos["antiguedad"]["segundo_a_tercero"]
    assert pts(3.0) == 0
    assert pts(None) == pesos["antiguedad"]["sin_dato"]


def test_calcular_score_no_muta_la_entrada_y_conserva_el_orden(pesos):
    df = pd.DataFrame([base(dias_vencimiento=d) for d in (400, -3, 20)])
    antes = df.copy(deep=True)
    out = sc.calcular_score(df, pesos)
    pd.testing.assert_frame_equal(df, antes)
    assert out["riesgo"].iloc[1] > out["riesgo"].iloc[2] > out["riesgo"].iloc[0]


def test_auc_sin_una_clase_devuelve_nan():
    assert math.isnan(sc.auc_rango(np.array([1.0, 2.0]), np.array([True, True])))
    assert math.isnan(sc.auc_rango(np.array([1.0, 2.0]), np.array([False, False])))
