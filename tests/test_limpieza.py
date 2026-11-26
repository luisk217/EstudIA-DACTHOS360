import pandas as pd

from pipeline import limpieza as lp


def test_reparar_mojibake():
    assert lp.reparar_mojibake("Bogotﾃ｡") == "Bogotá"
    assert lp.reparar_mojibake("Itagﾃｼﾃｭ") == "Itagüí"
    assert lp.reparar_mojibake("Bogotá") == "Bogotá"
    assert lp.reparar_mojibake(None) is None


def test_ciudades():
    assert lp.normalizar_ciudad("BOGOTA") == "Bogotá"
    assert lp.normalizar_ciudad("Bogotá, Bogotá D.C., Colombia") == "Bogotá"
    assert lp.normalizar_ciudad("Medellin") == "Medellín"
    assert lp.normalizar_ciudad("ITAGUI") == "Itagüí"
    assert lp.normalizar_ciudad(float("nan")) is None


def test_niveles():
    assert lp.normalizar_nivel("Estándar") == "Conectar"
    assert lp.normalizar_nivel("Estandar") == "Conectar"
    assert lp.normalizar_nivel("Premium") == "Crecer"
    assert lp.normalizar_nivel("Elite") == "Liderar"
    assert lp.normalizar_nivel("Empresas", "Corporativa Premium") == "Crecer"
    assert lp.normalizar_nivel("Empresas", "Empresa") == "Sin dato"
    assert lp.normalizar_nivel(None) == "Sin dato"


def test_ejecutiva_y_si_no():
    assert lp.normalizar_ejecutiva("0") == "Sin asignar"
    assert lp.normalizar_ejecutiva("Sin asignar (cuenta ACTHO)") == "Sin asignar"
    assert lp.normalizar_ejecutiva("KAM A") == "KAM A"
    assert lp.normalizar_si_no("SÍ, AUTORIZO EL TRATAMIENTO") is True
    assert lp.normalizar_si_no("No") is False
    assert lp.normalizar_si_no("false") is False


def test_id_empresa():
    assert lp.normalizar_id_empresa(" emp-0042 ") == "EMP-0042"
    assert lp.normalizar_id_empresa("ABC") is None
    assert lp.normalizar_id_empresa(None) is None


def test_fechas():
    assert lp.parsear_fecha("2026-12-31") == pd.Timestamp(2026, 12, 31)
    assert lp.parsear_fecha("05/03/2026") == pd.Timestamp(2026, 3, 5)
    assert pd.isna(lp.parsear_fecha("no es fecha"))
    assert lp.parsear_fecha_es("oct. 21, 2026 09:22:34 a.\xa0m.") == pd.Timestamp(2026, 10, 21)
    assert lp.parsear_fecha_es("mar. 27, 2025 09:24:10 a. m.") == pd.Timestamp(2025, 3, 27)
    assert pd.isna(lp.parsear_fecha_es("xxx"))


def test_nps():
    s = pd.Series([10, 10, 9, 8, 7, 6, 0, None])
    r = lp.calcular_nps(s)
    assert (r["promotores"], r["pasivos"], r["detractores"], r["n"]) == (3, 2, 2, 7)
    assert r["nps"] == round(100 * (3 - 2) / 7, 1)
    assert lp.calcular_nps(pd.Series([], dtype=float))["nps"] is None
    assert lp.clasificar_nps(9) == "Promotor" and lp.clasificar_nps(8) == "Pasivo" and lp.clasificar_nps(6) == "Detractor"
    assert lp.extraer_numero("10 (Promoter)") == 10.0
