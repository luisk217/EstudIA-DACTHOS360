import numpy as np
import pandas as pd

from pipeline import score as sc


def base(**kw):
    r = dict(dias_vencimiento=200, dias_afiliacion=2000, antiguedad_anios=5.0, asistencias=5, asistencias_90d=2,
             personas_distintas=3, satisfaccion=4.8, n_respuestas=2, nps_minimo=10, nivel="Liderar",
             sin_ejecutiva=False, comunidad=True, renovo_recientemente=False)
    r.update(kw)
    return r


def codigos(r, pesos, **kw):
    return {f.codigo for f in sc.puntuar_afiliado(r, pesos, **kw)}


def test_afiliado_sano_sin_factores(pesos):
    assert sc.puntuar_afiliado(base(), pesos) == []


def test_vencimiento_por_tramos(pesos):
    def pts(d):
        return sum(f.puntos for f in sc.puntuar_afiliado(base(dias_vencimiento=d), pesos))
    assert pts(-5) == pesos["vencimiento"]["vencida"]
    assert pts(20) == pesos["vencimiento"]["hasta_30"]
    assert pts(45) == pesos["vencimiento"]["hasta_60"]
    assert pts(80) == pesos["vencimiento"]["hasta_90"]
    assert pts(120) == pesos["vencimiento"]["hasta_180"]
    assert pts(300) == 0
    assert pts(None) == pesos["vencimiento"]["sin_fecha"]


def test_participacion(pesos):
    c = codigos(base(asistencias=0, asistencias_90d=0, personas_distintas=0), pesos)
    assert {"sin_asistencia_90d", "sin_asistencia_anio"} <= c
    assert "una_sola_asistencia" in codigos(base(asistencias=1, personas_distintas=1), pesos)
    assert "contacto_unico" in codigos(base(asistencias=3, personas_distintas=1), pesos)
    assert "contacto_unico" not in codigos(base(asistencias=3, personas_distintas=2), pesos)


def test_afiliado_nuevo_atenua_participacion(pesos):
    sin = dict(asistencias=0, asistencias_90d=0, personas_distintas=0)

    def part(**kw):
        return sum(f.puntos for f in sc.puntuar_afiliado(base(**sin, **kw), pesos) if f.grupo == "participacion")
    assert part(dias_afiliacion=30) == part() * pesos["participacion"]["factor_afiliado_nuevo"]


def test_satisfaccion_y_detractor(pesos):
    fs = {f.codigo: f for f in sc.puntuar_afiliado(base(satisfaccion=3.5, nps_minimo=4), pesos)}
    assert fs["satisfaccion"].puntos == pesos["satisfaccion"]["promedio_bajo"]
    assert "detractor" in fs and "3,5" in fs["satisfaccion"].texto
    assert "satisfaccion" not in codigos(base(satisfaccion=None, n_respuestas=0), pesos)  # sin dato no penaliza


def test_exclusiones_y_maximo(pesos):
    c = codigos(base(sin_ejecutiva=True, comunidad=False), pesos, excluir=("ejecutiva", "comunidad"))
    assert "ejecutiva" not in c and "comunidad" not in c
    assert sc.maximo_posible(pesos, ("vencimiento",)) == sc.maximo_posible(pesos) - max(pesos["vencimiento"].values())


def test_calcular_score_bandas_y_texto(pesos):
    df = pd.DataFrame([
        base(),
        base(dias_vencimiento=-10, asistencias=0, asistencias_90d=0, personas_distintas=0, sin_ejecutiva=True,
             comunidad=False, nivel="Conectar", satisfaccion=3.0, nps_minimo=5),
    ])
    out = sc.calcular_score(df, pesos)
    assert out["banda"].tolist() == ["Saludable", "Riesgo alto"]
    assert (out["riesgo"] + out["salud"]).round(1).eq(100).all()
    assert out["riesgo"].between(0, 100).all()
    top = out.loc[1, "factores"][0]
    assert top["codigo"] == "vencimiento" and "venció" in top["texto"]
    assert out.loc[0, "factores"] == []


def test_renovacion_reciente_reduce_riesgo(pesos):
    a = sc.calcular_score(pd.DataFrame([base(dias_vencimiento=20)]), pesos)["riesgo"].iloc[0]
    b = sc.calcular_score(pd.DataFrame([base(dias_vencimiento=20, renovo_recientemente=True)]), pesos)["riesgo"].iloc[0]
    assert b < a


def test_auc():
    assert sc.auc_rango(np.array([1, 2, 3, 4]), np.array([0, 0, 1, 1])) == 1.0
    assert sc.auc_rango(np.array([4, 3, 2, 1]), np.array([0, 0, 1, 1])) == 0.0
    assert sc.auc_rango(np.array([1, 1, 1, 1]), np.array([0, 1, 0, 1])) == 0.5
