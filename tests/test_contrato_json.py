"""Contrato de los siete JSON del tablero: la v2 solo puede añadir campos o archivos, nunca quitar ni renombrar.

``baseline_contrato_web.json`` guarda las rutas de campos que tenían los siete archivos en la v1 (25 de noviembre de 2026).
Las claves de diccionarios cuyo contenido depende de los datos (estados, niveles, respuestas abiertas) no se comparan.
"""
import json

import pytest

from tests.conftest import RAIZ

DIR = RAIZ / "web" / "data"
BASE = RAIZ / "tests" / "baseline_contrato_web.json"
NOMBRES = ("meta", "resumen", "afiliados", "eventos", "ejecutivas", "encuestas", "segmentos")
#: Diccionarios cuyas claves son valores de los datos (p. ej. «Activo», «Conectar») y no campos del contrato.
CLAVES_DE_DATOS = {"por_estado", "por_nivel", "interes_afiliarse_no_afiliados"}


def rutas(obj, prefijo=""):
    """Rutas de todos los campos; en las listas se unen los campos de todos los elementos (``[]``)."""
    out = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.add(f"{prefijo}/{k}")
            if k not in CLAVES_DE_DATOS:
                out |= rutas(v, f"{prefijo}/{k}")
    elif isinstance(obj, list):
        for v in obj:
            out |= rutas(v, prefijo + "[]")
    return out


@pytest.fixture(scope="module")
def baseline():
    return json.loads(BASE.read_text(encoding="utf-8"))


def test_el_baseline_cubre_los_siete_archivos(baseline):
    assert set(baseline) == set(NOMBRES) and all(len(v) > 3 for v in baseline.values())


@pytest.mark.parametrize("nombre", NOMBRES)
def test_los_siete_json_conservan_todos_sus_campos(nombre, baseline):
    actual = rutas(json.loads((DIR / f"{nombre}.json").read_text(encoding="utf-8")))
    perdidos = sorted(set(baseline[nombre]) - actual)
    assert not perdidos, f"{nombre}.json perdió campos: {perdidos[:10]}"


def test_afiliados_conserva_los_28_campos_por_afiliado(baseline):
    por_afiliado = {r for r in baseline["afiliados"] if r.startswith("/afiliados[]/") and r.count("/") == 2}
    assert len(por_afiliado) == 28
    primero = json.loads((DIR / "afiliados.json").read_text(encoding="utf-8"))["afiliados"][0]
    assert {f"/afiliados[]/{k}" for k in primero} >= por_afiliado


def test_los_tipos_de_los_campos_clave_no_cambian():
    res = json.loads((DIR / "resumen.json").read_text(encoding="utf-8"))
    assert isinstance(res["afiliados_vigentes"], int) and isinstance(res["por_banda"], dict) and isinstance(res["distribuciones"]["ciudad"], list)
    ev = json.loads((DIR / "eventos.json").read_text(encoding="utf-8"))
    assert isinstance(ev["eventos"], list) and {"id", "fecha", "asistentes", "empresas", "satisfaccion"} <= set(ev["eventos"][0])
    meta = json.loads((DIR / "meta.json").read_text(encoding="utf-8"))
    assert isinstance(meta["avisos_calidad"], list) and isinstance(meta["score"]["pesos"], dict) and isinstance(meta["cruce"]["afiliados_vigentes"], int)


def test_los_campos_nuevos_son_solo_adiciones():
    meta = json.loads((DIR / "meta.json").read_text(encoding="utf-8"))
    assert {"homologacion", "modelo", "integridad", "calidad"} <= set(meta)
    assert (DIR / "tendencias.json").exists()  # archivo nuevo: no forma parte de los siete originales
