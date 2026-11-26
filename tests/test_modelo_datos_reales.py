"""Modelo generado por el pipeline en data/processed (se omite si aún no se ejecutó) y su reflejo en meta.json."""
import json

import pandas as pd
import pytest

from pipeline import esquema
from pipeline import limpieza as lp
from tests.conftest import RAIZ

DIR = RAIZ / "data" / "processed"
pytestmark = pytest.mark.skipif(not (DIR / "dim_afiliado.csv").exists(), reason="ejecute python -I run_pipeline.py para generar data/processed")


@pytest.fixture(scope="module")
def m():
    return {n: pd.read_csv(DIR / f"{n}.csv", dtype=str, keep_default_na=False, na_values=[""]) for n in esquema.ESQUEMA}


def test_columnas_exactas_y_snake_case(m):
    for n, t in esquema.ESQUEMA.items():
        assert list(m[n].columns) == t.nombres() and all(lp.es_snake_case(c) for c in m[n].columns), n


def test_claves_primarias_y_foraneas_sin_errores(m):
    for n, t in esquema.ESQUEMA.items():
        assert not m[n].duplicated(list(t.clave)).any() and m[n][list(t.clave)].notna().all().all(), n
        for c in t.columnas:
            if c.fk and c.fk_severidad == "error":
                assert set(m[n][c.nombre].dropna()) <= set(m[c.fk[0]][c.fk[1]]), (n, c.nombre)


def test_los_huerfanos_estan_reportados_y_coinciden_con_meta(m):
    meta = json.loads((RAIZ / "web" / "data" / "meta.json").read_text(encoding="utf-8"))["integridad"]
    hu = pd.read_csv(DIR / "control_huerfanos.csv")
    fk = hu[(hu["tipo"] == "clave_foranea") & (hu["tabla_padre"] == "dim_afiliado")]
    real = ~m["fact_asistencia"]["empresa_id"].isin(set(m["dim_afiliado"]["empresa_id"]))
    assert int(real.sum()) == int(fk.loc[fk["tabla_hijo"] == "fact_asistencia", "filas"].sum())
    assert meta["ok"] and meta["errores"] == 0 and meta["filas_huerfanas_error"] == 0
    assert meta["filas_huerfanas_aviso"] == int(hu.loc[hu["tipo"] == "clave_foranea", "filas"].sum())


def test_cuadra_con_los_json_del_tablero(m):
    ev = json.loads((DIR.parents[1] / "web" / "data" / "eventos.json").read_text(encoding="utf-8"))
    res = json.loads((DIR.parents[1] / "web" / "data" / "resumen.json").read_text(encoding="utf-8"))
    assert int((m["fact_asistencia"]["es_valida"] == "True").sum()) == ev["totales"]["asistentes"]
    assert len(m["fact_score_afiliado"]) == res["afiliados_vigentes"]
    vig = set(m["dim_estado_membresia"].query("es_vigente == 'True'")["estado_membresia"])
    assert int(m["dim_afiliado"]["estado_membresia"].isin(vig).sum()) == res["afiliados_vigentes"]


def test_categorias_homologadas_y_sin_centinelas(m):
    af = m["dim_afiliado"]
    for col in ("ciudad", "sector", "region", "pais", "tamano", "rango_empleados"):
        assert not af[col].dropna().map(lp.es_centinela).any(), col
    assert not af["ciudad"].dropna().str.contains("D.C", regex=False).any() and not af["sector"].dropna().str.contains("  ").any()
    assert set(af["nivel"].dropna()) <= {"Conectar", "Crecer", "Liderar"}
    assert not (m["fact_asistencia"]["nivel_cargo"] == "Sin dato").any()
