"""Casos límite de la limpieza: nulos, fechas inválidas, variantes de texto y NPS fuera de escala."""
from datetime import date, datetime

import numpy as np
import pandas as pd
import pytest

from pipeline import limpieza as lp


@pytest.mark.parametrize("v", [None, float("nan"), np.nan, pd.NA, pd.NaT, "", "   ", "\t\n"])
def test_es_nulo_detecta_nulos(v):
    assert lp.es_nulo(v)


@pytest.mark.parametrize("v", [0, 0.0, "0", False, "x", [1, 2]])
def test_es_nulo_no_confunde_ceros_ni_listas(v):
    assert not lp.es_nulo(v)


@pytest.mark.parametrize("v,esperado", [
    ("Sí", True), ("SI", True), ("SÍ, AUTORIZO EL TRATAMIENTO", True), ("true", True), ("1", True),
    ("No", False), ("NO, gracias", False), ("false", False), ("0", False),
    ("Sin dato", None), ("Sin comunidad", None), ("Noviembre", None), ("Tal vez", None), ("", None), (None, None),
])
def test_si_no_exige_palabra_completa(v, esperado):
    assert lp.normalizar_si_no(v) is esperado


def test_fechas_invalidas_dan_nat():
    for v in ("31/02/2026", "2026-13-40", "00/00/0000", "ayer", 45000, None, ""):
        assert pd.isna(lp.parsear_fecha(v)), v
    assert pd.isna(lp.parsear_fecha_es("feb. 31, 2026 09:00:00 a. m."))
    assert pd.isna(lp.parsear_fecha_es("zzz. 10, 2026"))
    assert pd.isna(lp.parsear_fecha_es(None))


def test_fechas_validas_en_varios_tipos():
    assert lp.parsear_fecha(datetime(2026, 3, 5, 14, 30)) == pd.Timestamp(2026, 3, 5)
    assert lp.parsear_fecha(date(2026, 3, 5)) == pd.Timestamp(2026, 3, 5)
    assert lp.parsear_fecha("2026-03-05 10:11:12") == pd.Timestamp(2026, 3, 5)
    assert lp.parsear_fecha("5/3/2026") == pd.Timestamp(2026, 3, 5)  # día/mes/año
    assert lp.parsear_fecha_es("sep. 3, 2026 10:00:00 a. m.") == pd.Timestamp(2026, 9, 3)


def test_nps_ignora_valores_fuera_de_escala_y_no_numericos():
    s = pd.Series([10, 9, 8, 6, 11, -1, "abc", None])
    r = lp.calcular_nps(s)
    assert (r["n"], r["promotores"], r["pasivos"], r["detractores"]) == (4, 2, 1, 1)
    assert r["nps"] == 25.0
    assert lp.calcular_nps(pd.Series([11, -3]))["nps"] is None


@pytest.mark.parametrize("p,c", [(10, "Promotor"), (9, "Promotor"), (8.9, "Pasivo"), (7, "Pasivo"), (6.9, "Detractor"), (0, "Detractor")])
def test_clasificar_nps_en_los_bordes(p, c):
    assert lp.clasificar_nps(p) == c


@pytest.mark.parametrize("p", [11, -1, "texto", None, float("nan")])
def test_clasificar_nps_invalido_es_none(p):
    assert lp.clasificar_nps(p) is None


def test_extraer_numero_variantes():
    assert lp.extraer_numero("4,5") == 4.5 and lp.extraer_numero("Calificación: 7") == 7.0
    assert lp.extraer_numero("sin número") is None and lp.extraer_numero(None) is None


def test_ciudad_y_sector_con_nulos_y_variantes():
    assert lp.normalizar_ciudad("  ") is None and lp.normalizar_sector(None) is None
    assert lp.normalizar_ciudad("cali") == "cali"  # no se inventa una ciudad canónica
    assert lp.normalizar_sector("BANCA Y FINANZAS") == "Finanzas"
    assert lp.normalizar_empleados("1 - 50") == "1-50" and lp.normalizar_empleados("Más de 10.000") == "10.001 o más"


def test_id_empresa_rechaza_formatos_dudosos():
    for v in ("EMP-1", "EMP-123456", "EMP0001", "EMP-00A1", "emp-0001; DROP", "1234"):
        assert lp.normalizar_id_empresa(v) is None, v
    assert lp.normalizar_id_empresa("EMP-123") == "EMP-123" and lp.normalizar_id_empresa("emp-12345") == "EMP-12345"


def test_mojibake_no_toca_texto_normal_ni_no_texto():
    assert lp.reparar_mojibake("Ñandú, año") == "Ñandú, año"
    assert lp.reparar_mojibake(123) == 123
    assert lp.clave_texto("  ÁRBOL   Grande ") == "arbol grande" and lp.clave_texto(None) == ""
