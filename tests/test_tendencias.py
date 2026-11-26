"""web/data/tendencias.json: forma que lee el frontend (normalizarTendencias) y cuadre con los demás JSON."""
import json
import re

import pytest

from tests.conftest import RAIZ

DIR = RAIZ / "web" / "data"
#: Campos que el frontend reconoce por mes (ver ALIAS en web/js/datos.js); no se pueden quitar ni renombrar.
CAMPOS_FRONTEND = {"mes", "asistentes", "empresas", "satisfaccion", "afiliaciones_vigentes", "afiliaciones", "vencimientos", "salidas"}
CAMPOS_MES = CAMPOS_FRONTEND | {"inicio", "fin", "parcial", "eventos", "personas", "empresas_afiliadas_vigentes", "fechas_eventos",
                                "respuestas", "nps", "n_nps", "renovaciones"}


@pytest.fixture(scope="module")
def t():
    return json.loads((DIR / "tendencias.json").read_text(encoding="utf-8"))


def _j(n):
    return json.loads((DIR / f"{n}.json").read_text(encoding="utf-8"))


def test_forma_que_lee_el_frontend(t):
    assert isinstance(t["meses"], list) and t["meses"]
    for f in t["meses"]:
        assert CAMPOS_MES <= set(f) and re.match(r"^\d{4}-\d{2}$", f["mes"])
    ms = [f["mes"] for f in t["meses"]]
    assert ms == sorted(ms) and len(set(ms)) == len(ms)
    siguiente = {f"{a[:4]}-{int(a[5:]) + 1:02d}" if a[5:] != "12" else f"{int(a[:4]) + 1}-01" for a in ms[:-1]}
    assert siguiente == set(ms[1:])  # meses contiguos, sin saltos


def test_fechas_reales_y_nulos_fuera_de_cobertura(t):
    for f in t["meses"]:
        assert f["inicio"] == f["mes"] + "-01" and f["fin"][:7] == f["mes"] and f["inicio"] <= f["fin"]
        assert all(d[:7] == f["mes"] for d in f["fechas_eventos"])
    por_mes = {f["mes"]: f for f in t["meses"]}
    assert por_mes["2024-06"]["asistentes"] is None and por_mes["2026-01"]["asistentes"] > 0  # la asistencia empieza en enero de 2026
    assert por_mes["2027-06"]["afiliaciones"] is None and por_mes["2026-06"]["renovaciones"] is None  # fuera de cobertura es null, no 0
    assert por_mes["2026-09"]["renovaciones"] is not None
    c = t["cobertura"]["asistencia"]
    assert c["desde"] == "2026-01" and c["hasta"] == "2026-10"


def test_cuadra_con_eventos_resumen_y_afiliados(t):
    ev, res, af = _j("eventos"), _j("resumen"), _j("afiliados")["afiliados"]
    assert sum(f["asistentes"] or 0 for f in t["meses"]) == ev["totales"]["asistentes"] == t["totales"]["asistentes"]
    assert sum(f["eventos"] or 0 for f in t["meses"]) == sum(e["asistentes"] > 0 for e in ev["eventos"])  # el evento sin lista no cuenta
    por_mes = {g["clave"]: g for g in ev["por_mes"]}
    for f in t["meses"]:
        if f["asistentes"]:
            assert por_mes[f["mes"]]["asistentes"] == f["asistentes"] and f["eventos"] <= len(f["fechas_eventos"])
    ant = t["totales"]["antes_de_la_serie"]
    assert sum(f["vencimientos"] for f in t["meses"]) + ant["vencimientos"] == t["totales"]["vencimientos_con_fecha"]
    assert t["totales"]["vencimientos_con_fecha"] + t["totales"]["vencimientos_sin_fecha"] == res["afiliados_vigentes"] == len(af)
    assert sum(1 for a in af if a["expira"]) == t["totales"]["vencimientos_con_fecha"]
    assert sum(d["vencen"] for d in t["vencimientos_por_fecha"]) == t["totales"]["vencimientos_con_fecha"]
    assert sum(f["renovaciones"] or 0 for f in t["meses"]) == t["totales"]["renovaciones"]


def test_rangos_y_consistencia_interna(t):
    for f in t["meses"]:
        assert f["satisfaccion"] is None or 1 <= f["satisfaccion"] <= 5
        if f["asistentes"] is not None:
            assert f["personas"] <= f["asistentes"] and f["empresas_afiliadas_vigentes"] <= f["empresas"] <= f["asistentes"]
        if f["afiliaciones"] is not None:
            assert f["afiliaciones_vigentes"] <= f["afiliaciones"]
        assert (f["satisfaccion"] is None) == (not f["respuestas"])
    assert sum(a["afiliaciones"] for a in t["afiliaciones_por_anio"]) >= sum(f["afiliaciones"] or 0 for f in t["meses"])
    assert [e["fecha"] for e in t["por_evento"]] == sorted(e["fecha"] for e in t["por_evento"])


def test_sin_datos_personales(t):
    txt = json.dumps(t, ensure_ascii=False)
    assert not re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+|https?://|(?<!\d)\d{7,}(?!\d)|<", txt) and "persona_id" not in txt
