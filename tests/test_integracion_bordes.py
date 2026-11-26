"""Casos límite de integración: duplicados, agendados, vacíos, fechas futuras y cálculo de variables."""
from datetime import date

import pandas as pd

from pipeline import features as ft
from pipeline import integracion as it


def _asistencia(raw):
    emp = pd.DataFrame({"empresa_id": ["EMP-0001"], "estado": ["Activo"], "vigente": [True]})
    ev = pd.DataFrame({"hoja": ["A", "B"], "evento_id": ["EV01", "EV02"], "fecha": pd.to_datetime(["2026-03-01", "2026-04-01"])})
    return it.limpiar_asistencias(raw, ev, emp)


def _raw(filas):
    d = pd.DataFrame(filas, columns=["hoja", "empresa_id", "persona_id", "estado_registro"])
    return d.assign(nivel_cargo=None, costo="Sin costo", marca_afiliado=1)


def test_agendado_previo_no_anula_la_asistencia_real():
    a = _asistencia(_raw([("A", "EMP-0001", "P1", "agendado "), ("A", "EMP-0001", "P1", None)]))
    assert a["valida"].tolist() == [False, True]
    assert a["duplicado"].tolist() == [False, False]


def test_misma_persona_en_dos_eventos_cuenta_dos_veces():
    a = _asistencia(_raw([("A", "EMP-0001", "P1", None), ("B", "EMP-0001", "P1", None), ("B", "EMP-0001", "P1", None)]))
    assert a["valida"].tolist() == [True, True, False]


def test_persona_sin_id_no_se_deduplica():
    a = _asistencia(_raw([("A", "EMP-0001", None, None), ("A", "EMP-0001", None, None)]))
    assert a["valida"].all()


def test_asistencia_vacia_no_rompe_el_cruce():
    emp = pd.DataFrame({"empresa_id": ["EMP-0001"], "vigente": [True]})
    vacio = pd.DataFrame({"empresa_id": [], "valida": []}, dtype=object)
    resp = pd.DataFrame({"empresa_id": [], "nps_puntaje": []}, dtype=object)
    t = it.tasas_de_cruce(emp, vacio, resp)
    assert t["pct_sin_ninguna"] == 100.0 and t["con_asistencia"] == 0
    assert it.tasas_de_cruce(emp.iloc[0:0], vacio, resp)["pct_con_asistencia"] == 0.0  # sin vigentes: no divide entre cero


def test_consolidar_sin_codigo_valido_y_con_estado_vacio(crm_sintetico):
    crm_sintetico.loc[3, "empresa_id"] = "no es un id"
    crm = it.limpiar_crm(crm_sintetico, date(2026, 11, 25))
    emp, stats = it.consolidar_empresas(crm)
    assert stats["sin_codigo_valido"] == 1 and emp["empresa_id"].notna().all()
    assert emp["empresa_id"].is_unique


def test_consolidar_es_determinista_ante_el_orden_de_entrada(crm_sintetico):
    crm = it.limpiar_crm(crm_sintetico, date(2026, 11, 25))
    a, _ = it.consolidar_empresas(crm)
    b, _ = it.consolidar_empresas(crm.sample(frac=1, random_state=3))
    cols = ["empresa_id", "estado", "ejecutiva"]
    pd.testing.assert_frame_equal(a.sort_values("empresa_id")[cols].reset_index(drop=True),
                                  b.sort_values("empresa_id")[cols].reset_index(drop=True))


def test_fecha_de_afiliacion_futura_se_descarta_pero_se_marca(crm_sintetico):
    crm = it.limpiar_crm(crm_sintetico, date(2026, 11, 25))
    assert crm["fecha_afiliacion_invalida"].sum() == 1 and crm["fecha_afiliacion"].isna().sum() >= 1
    # El día del corte es válido; el día siguiente no.
    c2 = crm_sintetico.copy()
    c2.loc[0, "fecha_afiliacion"] = "2026-11-25"
    c2.loc[1, "fecha_afiliacion"] = "2026-11-26"
    r = it.limpiar_crm(c2, date(2026, 11, 25))
    assert not r.loc[0, "fecha_afiliacion_invalida"] and r.loc[1, "fecha_afiliacion_invalida"]


def _base_features():
    return pd.DataFrame({
        "empresa_id": ["EMP-0001", "EMP-0002", "EMP-0003"],
        "fecha_expiracion": pd.to_datetime(["2026-12-05", "2026-11-01", None]),
        "fecha_afiliacion": pd.to_datetime(["2020-01-01", None, "2026-10-01"]),
        "miembro_desde": pd.to_datetime([None, "2019-05-05", None]),
        "ejecutiva": ["KAM A", "Sin asignar", "KAM B"],
    })


def test_features_fechas_vencidas_nulos_y_ventanas():
    base = _base_features()
    asist = pd.DataFrame({
        "empresa_id": ["EMP-0001", "EMP-0001", "EMP-0001", "EMP-0002", "EMP-0001"],
        "persona_id": ["P1", "P1", "P2", "P9", "P1"], "evento_id": ["E1", "E2", "E2", "E3", "E4"],
        "fecha": pd.to_datetime(["2026-02-01", "2026-10-20", "2026-10-20", "2025-12-31", "2026-12-30"]),
        "valida": [True, True, True, True, True],
    })
    resp = pd.DataFrame({
        "empresa_id": ["EMP-0001", "EMP-0001", "EMP-0002"], "completada": pd.to_datetime(["2026-10-21", "2025-01-01", "2026-11-02"]),
        "satisfaccion": [4.0, 1.0, 3.0], "nps_puntaje": [10.0, 2.0, 5.0],
    })
    ref = pd.Series(pd.Timestamp("2026-11-25"), index=base["empresa_id"])
    f = ft.calcular_features(base, asist, resp, ref, renovaron={"EMP-0003"}).set_index("empresa_id")
    assert f.loc["EMP-0001", "dias_vencimiento"] == 10 and f.loc["EMP-0002", "dias_vencimiento"] == -24
    assert pd.isna(f.loc["EMP-0003", "dias_vencimiento"])
    # Asistencia: la de 2025 (antes de la cobertura) y la posterior a la referencia no cuentan.
    assert f.loc["EMP-0001", "asistencias"] == 3 and f.loc["EMP-0002", "asistencias"] == 0 and f.loc["EMP-0003", "asistencias"] == 0
    assert f.loc["EMP-0001", "eventos_distintos"] == 2 and f.loc["EMP-0001", "personas_distintas"] == 2
    assert f.loc["EMP-0001", "asistencias_90d"] == 2
    assert pd.isna(f.loc["EMP-0003", "dias_ultima_asistencia"])
    # Encuestas: solo cuenta el último año; el detractor sale de la nota mínima de esa ventana.
    assert f.loc["EMP-0001", "n_respuestas"] == 1 and f.loc["EMP-0001", "satisfaccion"] == 4.0 and not f.loc["EMP-0001", "detractor"]
    assert f.loc["EMP-0002", "detractor"] and f.loc["EMP-0003", "n_respuestas"] == 0 and not f.loc["EMP-0003", "detractor"]
    # Antigüedad: usa «miembro desde» si falta la afiliación.
    assert f.loc["EMP-0002", "antiguedad_anios"] > 7 and f.loc["EMP-0003", "antiguedad_anios"] < 0.2
    assert f.loc["EMP-0003", "renovo_recientemente"] and f.loc["EMP-0002", "sin_ejecutiva"] and not f.loc["EMP-0001", "sin_ejecutiva"]


def test_features_sin_asistencias_ni_respuestas():
    base = _base_features()
    asist = pd.DataFrame({"empresa_id": [], "persona_id": [], "evento_id": [], "fecha": pd.to_datetime([]), "valida": pd.Series([], dtype=bool)})
    resp = pd.DataFrame({"empresa_id": [], "completada": pd.to_datetime([]), "satisfaccion": [], "nps_puntaje": []})
    ref = pd.Series(pd.Timestamp("2026-11-25"), index=base["empresa_id"])
    f = ft.calcular_features(base, asist, resp, ref)
    assert (f["asistencias"] == 0).all() and (f["n_respuestas"] == 0).all() and len(f) == 3
