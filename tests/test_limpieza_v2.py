"""Reglas de limpieza nuevas de la v2: texto, centinelas, nombres de columna, fechas, estructura de hojas y CRM ampliado."""
import re
from datetime import date

import pandas as pd
import pytest

from pipeline import integracion as it
from pipeline import limpieza as lp


# ----------------------------------------------------------------------------- texto y centinelas
@pytest.mark.parametrize("v", ["N/A", "n/a", "NA", "-", "--", "—", "sin dato", "Sin Dato", "SIN DATO", "s/d", "ninguno", "null", "None", "#N/A", "#REF!",
                               "#¡VALOR!", "No aplica", "  -  "])
def test_los_centinelas_de_texto_pasan_a_nulo(v):
    assert lp.es_centinela(v) and lp.limpiar_texto(v) is None


@pytest.mark.parametrize("v", ["Bogotá", "Sin comunidad", "0", "No", "Noviembre", "Servicios"])
def test_un_texto_real_no_se_confunde_con_un_centinela(v):
    assert not lp.es_centinela(v) and lp.limpiar_texto(v) == v


def test_limpiar_texto_unifica_espacios_incluido_el_no_separable_y_repara_tildes():
    assert lp.limpiar_texto("  Soluciones   para\xa0RRHH \n") == "Soluciones para RRHH"
    assert lp.limpiar_texto("Bogotﾃ｡") == "Bogotá"
    assert lp.limpiar_texto(5) == 5 and lp.limpiar_texto(None) is None and lp.limpiar_texto("   ") is None


# ----------------------------------------------------------------------------- nombres de columna
@pytest.mark.parametrize("original,esperado", [
    ("Fecha de Expiración Afiliación", "fecha_de_expiracion_afiliacion"), ("Nombre de Empresa [anonimizado]", "nombre_de_empresa"),
    ("ID_EMPRESA (antes Nit)", "id_empresa"), ("Empresa [anonimizado] → ID_EMPRESA", "id_empresa"), ("% de Mujeres en la Compañía", "de_mujeres_en_la_compania"),
    ("15. Califica de 1 a 5", "c_15_califica_de_1_a_5"), ("  Tamaño  de la Empresa ", "tamano_de_la_empresa"), ("Región", "region"), ("###", "columna"),
])
def test_snake_case_sin_tildes_ni_espacios(original, esperado):
    r = lp.snake_case(original)
    assert r == esperado and lp.es_snake_case(r)


@pytest.mark.parametrize("n,ok", [("empresa_id", True), ("fecha_2026", True), ("Empresa", False), ("empresa id", False), ("región", False), ("_x", False), ("x__y", False), ("1x", False)])
def test_es_snake_case(n, ok):
    assert lp.es_snake_case(n) is ok


# ----------------------------------------------------------------------------- tipos
@pytest.mark.parametrize("v,esperado", [("50%", 50.0), ("50", 50.0), (" 7,5 % ", 7.5), ("100%", 100.0), ("0%", 0.0), ("120%", None), ("-5", None), ("abc", None), (None, None), ("N/A", None)])
def test_porcentajes(v, esperado):
    assert lp.normalizar_porcentaje(v) == esperado


@pytest.mark.parametrize("v,esperado", [("1", 1), (1.0, 1), ("3.0", 3), ("2,0", 2), ("1.5", None), ("x", None), (None, None), ("sin dato", None), (float("nan"), None)])
def test_a_entero(v, esperado):
    assert lp.a_entero(v) == esperado


@pytest.mark.parametrize("v,esperado", [("SÍ ", True), ("Sí ", True), ("SI", True), ("SÍ, AUTORIZO EL TRATAMIENTO DE MIS DATOS PERSONALES", True), ("NO, AUTORIZO EL TRATAMIENTO", False),
                                       ("NO", False), ("No aplica", None), ("N/A", None), ("x", True), ("Sin dato", None), (None, None)])
def test_si_no_con_las_variantes_reales_de_las_hojas(v, esperado):
    assert lp.normalizar_si_no(v) is esperado


def test_id_de_persona():
    assert lp.normalizar_id_persona(" p-02560 ") == "P-02560" and lp.normalizar_id_persona("P1") is None and lp.normalizar_id_persona(None) is None


@pytest.mark.parametrize("v,esperado", [("kam  b", "KAM B"), ("KAMc", "KAM C"), ("KAM A", "KAM A"), ("0", "Sin asignar"), ("Sin asignar (cuenta ACTHO)", "Sin asignar"), (None, "Sin asignar"), ("N/A", "Sin asignar")])
def test_ejecutiva(v, esperado):
    assert lp.normalizar_ejecutiva(v) == esperado


# ----------------------------------------------------------------------------- fechas
@pytest.mark.parametrize("v", ["1900-01-01", "1899-12-30", "9999-12-31", "01/01/1900", "31/12/9999", "N/A", "-"])
def test_las_fechas_centinela_dan_nat(v):
    assert pd.isna(lp.parsear_fecha(v))


def test_fechas_con_otros_separadores_y_rangos():
    assert lp.parsear_fecha("05-03-2026") == pd.Timestamp(2026, 3, 5) and lp.parsear_fecha("05.03.2026") == pd.Timestamp(2026, 3, 5)
    assert lp.parsear_fecha("17-20/03/2026") == pd.Timestamp(2026, 3, 17)
    assert lp.parsear_rango_fechas("17-20/03/2026") == (pd.Timestamp(2026, 3, 17), pd.Timestamp(2026, 3, 20))
    assert lp.parsear_rango_fechas("28/07/2026-29/07/2026") == (pd.Timestamp(2026, 7, 28), pd.Timestamp(2026, 7, 29))
    ini, fin = lp.parsear_rango_fechas(pd.Timestamp(2026, 1, 5))
    assert ini == fin == pd.Timestamp(2026, 1, 5)
    assert all(pd.isna(x) for x in lp.parsear_rango_fechas("sin fecha"))


def test_fechas_de_los_informes_de_zoho():
    assert lp.parsear_fecha_es("ago 26, 2026 ( 1 )") == pd.Timestamp(2026, 8, 26) and lp.parsear_fecha_es("sep 1, 2026") == pd.Timestamp(2026, 9, 1)
    assert lp.parsear_mes_anio("Septiembre 2026 ( 10 )") == pd.Timestamp(2026, 9, 1) and pd.isna(lp.parsear_mes_anio("KAM D ( 1 )"))
    assert lp.numero_mes("Agosto") == 8 and lp.numero_mes("Setiembre") == 9 and lp.numero_mes("KAM A") is None


# ----------------------------------------------------------------------------- estructura de hojas
@pytest.mark.parametrize("v,esperado", [("KAM D ( 1 )", ("KAM D", 1)), ("Septiembre 2026 ( 10 )", ("Septiembre 2026", 10)), ("Sin asignar (cuenta ACTHO) ( 1 )", ("Sin asignar (cuenta ACTHO)", 1)),
                                       ("KAM A", ("KAM A", None)), (None, (None, None))])
def test_quitar_conteo_de_grupo(v, esperado):
    assert lp.quitar_conteo_grupo(v) == esperado


@pytest.mark.parametrize("fila,total", [(("Grand Total", None), True), (("Total general", 5), True), ((None, "Subtotal", 3), True), (("EMP-0001", "Totalmente"), False), (("Totales", 1), True), ((1, 2, None), False)])
def test_detecta_filas_de_total(fila, total):
    assert lp.es_fila_total(fila) is total


def test_clasifica_las_filas_de_una_hoja():
    pat = re.compile(r"^EMP-\d+$")
    c = lambda fila, clave: lp.clasificar_fila(fila, clave, pat, ("ID_EMPRESA",))  # noqa: E731
    assert c((None, None), None) == "vacia" and c(("EMP-0001", "P-1"), "EMP-0001") == "valida"
    assert c(("TOTAL", 10), None) == "total" and c(("ID_EMPRESA", "ID_PERSONA"), "ID_EMPRESA") == "encabezado"
    assert c((None, "P-02302"), None) == "sin_clave" and c(("emp-12", 1), "emp-12") == "sin_clave"


# ----------------------------------------------------------------------------- CRM ampliado
@pytest.fixture
def crm_ampliado(crm_sintetico):
    c = crm_sintetico.copy()
    c["pais"] = ["COLOMBIA", "Colomba", "Colombia", None, "Guatemala", "N/A"]
    c["departamento"] = ["DC", "Bogotá, D.C.", "Atlantico", None, "Bolivar", "-"]
    c["region"] = ["Bogota", "Medellin", "Otro", None, "Bogotá", None]
    c["tamano"] = ["Pequeña", "grande", None, None, "Mediana", "sin dato"]
    c["naturaleza"] = ["Nacional Privada"] * 6
    c["estado_registro"] = ["Activo", "Inactivo", "Activo", None, "Activo", None]
    c["independiente"] = ["Si", "No", None, None, "SI", None]
    c["pct_mujeres"] = ["50%", "100%", None, None, "30%", "N/A"]
    c["subsector"] = ["Servivios Legales", None, "Centros De Formación", None, "Bancos", None]
    c["com_hr_estrategico"] = ["1", None, "2", None, None, None]
    c["cantidad_miembros"] = ["3", None, None, None, "1", None]
    return c


def test_limpiar_crm_homologa_geografia_tamano_y_tipos(crm_ampliado):
    crm = it.limpiar_crm(crm_ampliado, date(2026, 11, 25))
    assert crm["pais"].tolist()[:3] == ["Colombia", "Colombia", "Colombia"] and crm["pais"].isna().sum() == 2
    assert crm["departamento"].tolist()[:3] == ["Bogotá D.C.", "Bogotá D.C.", "Atlántico"] and crm["departamento"].iloc[4] == "Bolívar"
    assert crm["region"].tolist()[:3] == ["Bogotá", "Antioquia", "Otra"]
    assert crm["tamano"].tolist()[:2] == ["Pequeña", "Grande"] and pd.isna(crm["tamano"].iloc[5])
    assert crm["independiente"].tolist()[:2] == [True, False] and str(crm["independiente"].dtype) == "boolean"
    assert crm["pct_mujeres"].iloc[:2].tolist() == [50.0, 100.0] and pd.isna(crm["pct_mujeres"].iloc[5])
    assert crm["subsector"].iloc[0] == "Servicios legales" and crm["subsector"].iloc[2] == "Centros de formación"
    assert str(crm["com_hr_estrategico"].dtype) == "Int64" and crm["com_hr_estrategico"].iloc[0] == 1 and crm["cantidad_miembros"].iloc[0] == 3
    assert crm["n_comunidades"].iloc[0] == 1 and bool(crm["comunidad"].iloc[0])


def test_limpiar_crm_marca_anomalias_sin_ocultarlas(crm_ampliado):
    crm = it.limpiar_crm(crm_ampliado, date(2026, 11, 25))
    # «Empresas» no es una categoría: se anula, se marca y el nivel se infiere del tipo de membresía.
    assert bool(crm["categoria_invalida"].iloc[4]) and pd.isna(crm["categoria_membresia"].iloc[4]) and crm["nivel"].iloc[4] == "Crecer"
    assert crm["categoria_membresia"].iloc[1] == "Estándar" and not crm["categoria_invalida"].iloc[1]
    # Registro Activo con membresía cancelada.
    assert crm["estado_inconsistente"].tolist() == [False, False, True, False, False, False]
    assert bool(crm["fecha_afiliacion_invalida"].iloc[2])


def test_estado_inconsistente_solo_si_el_registro_activo_contradice_la_membresia():
    raw = pd.DataFrame({
        "id_registro": ["a", "b", "c", "d"], "empresa_id": ["EMP-0001", "EMP-0002", "EMP-0003", "EMP-0004"],
        "estado_registro": ["Activo", "Activo", "Inactivo", None], "estado_membresia": ["Expirado", "Activo", "Expirado", "Activo"],
    })
    base = pd.DataFrame({c: [None] * 4 for c in (
        "propietario", "ciudad", "ciudad_facturacion", "etiqueta", "categoria_membresia", "tipo_membresia", "fecha_afiliacion", "fecha_expiracion",
        "miembro_desde", "sector", "empleados", "vinculado_comunidades", "cantidad_miembros", "com_hr_estrategico", "com_mas_que_salario",
        "com_talento_elige", "com_gente_crece", "com_mujeres_hr", "com_influenciador")})
    crm = it.limpiar_crm(pd.concat([raw, base], axis=1), date(2026, 11, 25))
    assert crm["estado_inconsistente"].tolist() == [True, False, False, False]


def test_limpiar_eventos_toma_el_fin_del_rango_de_general_y_cae_al_diccionario():
    ev = pd.DataFrame({
        "evento_n": [7, 24, 5, 3], "hoja": list("ABCD"), "fecha": pd.to_datetime(["2026-03-17", "2026-07-28", "2026-02-12", "2026-02-04"]),
        "nombre": ["  Semana   del Talento  ", "Julio", "Bogota", "Foro"], "linea": ["EVENTO GRANDE", "anticipar", None, "Foro"],
        "experiencia": [None, "Actho", None, None], "modalidad": ["presencial", "Presencial", None, "hibrido"],
        "fecha_fin_general": pd.to_datetime(["2026-03-20", pd.NaT, pd.NaT, pd.NaT]),
    })
    r = it.limpiar_eventos(ev).set_index("evento_n")
    assert r.loc[7, "fecha_fin"] == pd.Timestamp("2026-03-20")  # del rango de GENERAL
    assert r.loc[24, "fecha_fin"] == pd.Timestamp("2026-07-29")  # del diccionario fin_evento_multidia
    assert r.loc[5, "fecha_fin"] == r.loc[5, "fecha"] and r.loc[3, "fecha_fin"] == r.loc[3, "fecha"]
    assert r.loc[7, "nombre"] == "Semana del Talento" and r.loc[7, "linea"] == "Evento grande" and r.loc[24, "linea"] == "Anticipar"
    assert r.loc[5, "linea"] == "Sin clasificar" and r.loc[5, "modalidad"] == "Sin dato" and r.loc[3, "modalidad"] == "Híbrido"


def test_limpiar_asistencias_homologa_ciudad_autorizacion_y_nivel_de_cargo():
    emp = pd.DataFrame({"empresa_id": ["EMP-0001"], "estado": ["Activo"], "vigente": [True]})
    ev = pd.DataFrame({"hoja": ["A"], "evento_id": ["EV01"], "fecha": pd.to_datetime(["2026-03-01"])})
    raw = pd.DataFrame({
        "hoja": ["A"] * 3, "empresa_id": ["EMP-0001"] * 3, "persona_id": ["P-00001", "P-00002", "x1"], "nivel_cargo": ["Sin dato", "Alta dirección", None],
        "costo": [None, "Con costo", "Sin costo"], "estado_registro": [None] * 3, "marca_afiliado": [1] * 3,
        "ciudad": ["BOGOTÁ D.C.", "Bigotá", "NEIVA"], "autoriza_datos": ["SÍ ", "no", "N/A"], "registro_ubicacion": [None] * 3,
    })
    a = it.limpiar_asistencias(raw, ev, emp)
    assert a["ciudad"].tolist() == ["Bogotá", "Bogotá", "Neiva"]
    assert a["autoriza_datos"].tolist()[:2] == [True, False] and pd.isna(a["autoriza_datos"].iloc[2])
    assert a["nivel_cargo"].tolist() == ["Sin dato", "Alta dirección (C-level / VP)", "Sin dato"]
    assert a["persona_id_invalido"].tolist() == [False, False, True]
    assert a["con_costo"].tolist()[1:] == [True, False] and a["con_costo"].iloc[0] is None
