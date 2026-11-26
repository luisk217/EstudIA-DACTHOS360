from datetime import date

import pandas as pd

from pipeline import integracion as it


def test_limpiar_y_consolidar_crm(crm_sintetico):
    crm = it.limpiar_crm(crm_sintetico, date(2026, 11, 25))
    assert crm.loc[0, "ciudad"] == "Bogotá"
    assert crm.loc[0, "nivel"] == "Conectar" and crm.loc[2, "nivel"] == "Crecer"
    assert bool(crm["fecha_afiliacion_invalida"].iloc[2])
    assert pd.isna(crm.loc[2, "fecha_afiliacion"])
    emp, stats = it.consolidar_empresas(crm)
    assert stats["registros_de_prueba"] == 1 and stats["filas_duplicadas_descartadas"] == 1
    assert emp["empresa_id"].is_unique and "EMP-0003" not in set(emp["empresa_id"])
    # El duplicado EMP-0001 conserva el registro vigente, con su ejecutiva.
    fila = emp.set_index("empresa_id").loc["EMP-0001"]
    assert fila["estado"] == "Activo" and fila["ejecutiva"] == "KAM A"
    assert emp.set_index("empresa_id").loc["EMP-0005", "estado"] == "Sin estado"
    assert not emp.set_index("empresa_id").loc["EMP-0005", "vigente"]


def _eventos():
    return pd.DataFrame({
        "evento_id": ["EV01", "EV02", "EV03"],
        "fecha": pd.to_datetime(["2026-04-28", "2026-04-30", "2026-05-05"]),
        "fecha_fin": pd.to_datetime(["2026-04-28", "2026-04-30", "2026-05-05"]),
        "modalidad": ["Presencial", "Presencial", "Virtual"],
    })


def test_asignar_eventos_por_fecha():
    resp = pd.DataFrame({
        "completada": pd.to_datetime(["2026-04-30", "2026-05-05", "2025-04-30", "2026-06-30", "2026-04-29"]),
        "modalidad": ["Presencial", "Virtual", "Presencial", "Presencial", "Presencial"],
    })
    r = it.asignar_eventos(resp, _eventos())
    assert r["evento_id"].fillna("-").tolist() == ["EV02", "EV03", "-", "-", "EV01"]
    assert r["metodo_evento"].iloc[2] == "fuera de 2026"


def test_asignar_eventos_ambiguo():
    ev = _eventos()
    ev.loc[0, ["fecha", "fecha_fin"]] = pd.Timestamp("2026-04-30")
    r = it.asignar_eventos(pd.DataFrame({"completada": pd.to_datetime(["2026-04-30"]), "modalidad": ["Presencial"]}), ev)
    assert pd.isna(r["evento_id"].iloc[0]) and "ambiguo" in r["metodo_evento"].iloc[0]


def test_asistencias_dedup_y_tasa_cruce():
    emp = pd.DataFrame({"empresa_id": ["EMP-0001", "EMP-0002"], "estado": ["Activo", "Cancelado"], "vigente": [True, False]})
    ev = pd.DataFrame({"hoja": ["A"], "evento_id": ["EV01"], "fecha": pd.to_datetime(["2026-03-01"])})
    raw = pd.DataFrame({
        "hoja": ["A"] * 5, "empresa_id": ["EMP-0001", "EMP-0001", "EMP-0002", "EMP-0900", "EMP-0001"],
        "persona_id": ["P1", "P1", "P2", "P3", "P4"], "nivel_cargo": [None] * 5, "costo": ["Sin costo"] * 5,
        "estado_registro": [None, None, None, None, "agendado"], "marca_afiliado": [1] * 5,
    })
    a = it.limpiar_asistencias(raw, ev, emp)
    assert a["valida"].sum() == 3  # un duplicado y un agendado quedan fuera
    assert not a.loc[a["empresa_id"] == "EMP-0900", "en_crm"].iloc[0]
    vig = emp[emp["vigente"]]
    resp = pd.DataFrame({"empresa_id": [None, "EMP-0002"], "nps_puntaje": [None, None]})
    t = it.tasas_de_cruce(vig, a, resp)
    assert t["afiliados_vigentes"] == 1 and t["pct_con_asistencia"] == 100.0
    assert t["pct_sin_encuesta"] == 100.0
