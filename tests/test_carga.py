"""Carga de fuentes con estructuras desordenadas: se construyen libros de Excel sintéticos con openpyxl (no se usan datos reales)."""
from datetime import datetime

import openpyxl
import pandas as pd
import pytest

from pipeline import carga


def _libro(tmp_path, nombre, hojas):
    """``hojas`` es una lista de (titulo, filas); cada fila es una lista que se escribe desde la columna A."""
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for titulo, filas in hojas:
        ws = wb.create_sheet(titulo)
        for r, fila in enumerate(filas, start=1):
            for c, v in enumerate(fila, start=1):
                if v is not None:
                    ws.cell(r, c, v)
    ruta = tmp_path / nombre
    wb.save(ruta)
    return ruta


# ----------------------------------------------------------------------------- informes agrupados de Zoho
RENOVACIONES = [
    [None] * 5, ["  Informe Renovaciones - Ultimos 2 Meses"], ["    Generado desde Zoho CRM el 13 de noviembre de 2026"], [None], ["    Cantidad de registros : 5"], [None],
    ["Fecha Factura Renovacion", "Propietario de Empresa [anonimizado]", "Nombre de Empresa [anonimizado]", "Fecha de Expiración Afiliación", "Valor [eliminado]"],
    ["Septiembre 2026 ( 4 )", "KAM D ( 1 )", "EMP-0454", datetime(2027, 9, 30), None],
    [None] * 5,
    [None, "KAM E ( 3 )", "EMP-0250", datetime(2027, 9, 30), None],
    [None, None, "EMP-0559", datetime(2027, 9, 30), None],
    [None, None, "EMP-0551", datetime(2027, 8, 31), None],
    [None] * 5,
    ["Octubre 2026 ( 1 )", "Sin asignar (cuenta ACTHO) ( 1 )", "EMP-0240", datetime(2026, 12, 31), None],
    [None] * 5,
    ["Grand Total"],
]


def test_informe_agrupado_se_vuelve_tidy_con_grupos_repetidos_y_sin_conteos(tmp_path):
    df = carga.cargar_renovaciones(_libro(tmp_path, "ren.xlsx", [("Sheet0", RENOVACIONES)]))
    assert df["empresa_id"].tolist() == ["EMP-0454", "EMP-0250", "EMP-0559", "EMP-0551", "EMP-0240"]
    assert df["ejecutiva"].tolist() == ["KAM D", "KAM E", "KAM E", "KAM E", "Sin asignar"]  # el grupo se repite hacia abajo y pierde « ( n )»
    assert df["mes_factura"].tolist() == [pd.Timestamp(2026, 9, 1)] * 4 + [pd.Timestamp(2026, 10, 1)]
    assert df["fecha_expiracion"].iloc[3] == pd.Timestamp(2027, 8, 31)


def test_informe_agrupado_cuadra_con_lo_declarado_y_cuenta_lo_que_descarta(tmp_path):
    ctl = carga.cargar_renovaciones(_libro(tmp_path, "ren.xlsx", [("Sheet0", RENOVACIONES)])).attrs["control"]
    assert ctl["declarados"] == 5 and ctl["recuperados"] == 5 and ctl["coincide_con_declarados"]
    assert ctl["filas_total"] == 1 and ctl["filas_vacias"] == 3 and ctl["filas_sin_codigo"] == 0
    assert ctl["generado"] == pd.Timestamp(2026, 11, 13)
    assert ctl["grupos_con_diferencia"] == [] and [g["declarado"] for g in ctl["grupos"]] == [4, 1]


def test_informe_agrupado_detecta_que_faltan_registros(tmp_path):
    filas = [list(f) for f in RENOVACIONES]
    filas[4] = ["    Cantidad de registros : 7"]  # el encabezado declara más de lo que hay
    filas[7][0] = "Septiembre 2026 ( 6 )"
    ctl = carga.cargar_renovaciones(_libro(tmp_path, "ren.xlsx", [("Sheet0", filas)])).attrs["control"]
    assert not ctl["coincide_con_declarados"] and ctl["declarados"] == 7 and ctl["recuperados"] == 5
    assert ctl["grupos_con_diferencia"] == [{"grupo": "Septiembre 2026", "declarado": 6, "recuperado": 4}]


def test_informe_agrupado_lista_las_filas_sin_codigo_en_vez_de_perderlas(tmp_path):
    filas = [list(f) for f in RENOVACIONES]
    filas[10][2] = "sin código"
    df = carga.cargar_renovaciones(_libro(tmp_path, "ren.xlsx", [("Sheet0", filas)]))
    assert len(df) == 4 and df.attrs["control"]["filas_sin_codigo"] == 1
    assert df.attrs["rechazos"] and df.attrs["rechazos"][0]["motivo"] == "sin código de empresa"


def test_afiliaciones_con_tres_niveles_de_grupo(tmp_path):
    filas = [
        [None], ["  Afiliaciones"], ["    Generado desde Zoho CRM el 13 de noviembre de 2026"], [None], ["    Cantidad de registros : 3"], [None],
        ["Fecha del cierre", "Propietario de Trato", "Fecha del cierre", "Nombre de Trato", "Categoría de Membresía", "Importe"],
        ["Agosto 2026 ( 2 )", "KAM C ( 1 )", "ago 26, 2026 ( 1 )", "EMP-0994", "Estándar", None],
        [None] * 6,
        [None, "KAM A ( 1 )", "ago 12, 2026 ( 1 )", "EMP-0992", "Premium", None],
        [None] * 6,
        ["Septiembre 2026 ( 1 )", "KAM B ( 1 )", "sep 21, 2026 ( 1 )", "EMP-1014", "Personal", None],
        ["Grand Total"],
    ]
    df = carga.cargar_afiliaciones_recientes(_libro(tmp_path, "af.xlsx", [("Sheet0", filas)]))
    assert df["empresa_id"].tolist() == ["EMP-0994", "EMP-0992", "EMP-1014"]
    assert df["fecha_cierre"].tolist() == [pd.Timestamp(2026, 8, 26), pd.Timestamp(2026, 8, 12), pd.Timestamp(2026, 9, 21)]
    assert df["ejecutiva"].tolist() == ["KAM C", "KAM A", "KAM B"] and df.attrs["control"]["coincide_con_declarados"]


def test_nuevos_afiliados_con_titulos_combinados_y_encabezado_repetido(tmp_path):
    filas = [
        ["Nuevos afiliados"], ["Agosto"], ["NOMBRE EMPRESA [anonimizado]", "AFILIADO PRINCIPAL [anonimizado]", "CORREO [eliminado]", "CONTACTO [eliminado]"],
        ["EMP-0986", "P-03265", None, None], ["EMP-0991", "P-03266"], [None], [None],
        ["Nuevos afiliados"], ["Septiembre"], ["NOMBRE EMPRESA [anonimizado]", "AFILIADO PRINCIPAL [anonimizado]", "CORREO [eliminado]", "CONTACTO [eliminado]"],
        ["EMP-1012", "P-03277"], ["EMP-0986", "P-03265"],
    ]
    ruta = _libro(tmp_path, "nuevos.xlsx", [("Hoja1", filas)])
    wb = openpyxl.load_workbook(ruta)
    wb["Hoja1"].merge_cells("A1:D1")
    wb.save(ruta)
    df = carga.cargar_nuevos(ruta, anio=2026)
    assert df["empresa_id"].tolist() == ["EMP-0986", "EMP-0991", "EMP-1012"]  # EMP-0986 repetida en septiembre: se conserva la primera
    assert df["mes"].tolist() == [pd.Timestamp(2026, 8, 1), pd.Timestamp(2026, 8, 1), pd.Timestamp(2026, 9, 1)]
    assert df.attrs["control"]["filas_encabezado_repetido"] == 2 and df["persona_principal_id"].iloc[0] == "P-03265"


def test_informe_de_membresias_separa_subtotales_y_total_de_los_datos(tmp_path):
    filas = [
        [None], ["  Informe de membresías"], ["    Generado desde Zoho CRM el 13 de noviembre de 2026"], [None], ["    Cantidad de registros : 14"], [None],
        ["Tipo de Membresía", "Categoría de Membresía", "Cantidad de registros"],
        ["Empresa", "Elite", "5"], [None, "Premium", "4"], [None, None, "9"],
        ["Consultoras", "Estándar", "3"], [None, "Estandar", "2"], [None, None, "5"],
        [None, None, "14"],
    ]
    df = carga.cargar_informe_membresias(_libro(tmp_path, "mem.xlsx", [("Sheet0", filas)]))
    assert df["cantidad"].sum() == 14 and len(df) == 4 and df["tipo_membresia"].tolist() == ["Empresa", "Empresa", "Consultoras", "Consultoras"]
    ctl = df.attrs["control"]
    assert ctl["subtotales_verificados"] == 3 and ctl["subtotales_coinciden"] == 3 and ctl["coincide_con_declarados"]
    filas[9][2] = "10"  # un subtotal que no suma
    ctl = carga.cargar_informe_membresias(_libro(tmp_path, "mem2.xlsx", [("Sheet0", filas)])).attrs["control"]
    assert ctl["subtotales_coinciden"] < ctl["subtotales_verificados"]


def test_consolidado_por_kam_unifica_bloques_repetidos(tmp_path):
    enc = [None, "Empresa [anonimizado]", "NIT [eliminado]", "Estado de Asistencia", "Eventos Asistidos", "Total Asistentes"]
    filas = [
        [None, "RESUMEN CONSOLIDADO DE ASISTENCIAS - BD KAM A"], [None, "Total Empresas BD", "Empresas con Asistencia", "Empresas sin Asistencia", "Total Asistentes Registrados"],
        [None, 2, 1, 1, 3], [None], [None, "CONSOLIDADO GENERAL POR EMPRESA (BD PERSONA)"], enc,
        [None, "EMP-0019", None, "Asistió", 2, 3], [None, "EMP-0022", None, "No Asistió", 0, 0], [None], [None],
        [None, "RESUMEN CONSOLIDADO DE ASISTENCIAS - BD KAM D"], [None, "Total Empresas BD", "Empresas con Asistencia", "Empresas sin Asistencia", "Total Asistentes Registrados"],
        [None, 1, 1, 0, 4], [None], [None, "CONSOLIDADO GENERAL POR EMPRESA (BD OTRA)"], enc, [None, "EMP-0013", None, "Asistió", 1, 4],
    ]
    df = carga.cargar_kam_consolidado(_libro(tmp_path, "kam.xlsx", [("Hoja 1", filas)]))
    assert df["ejecutiva"].tolist() == ["KAM A", "KAM A", "KAM D"] and df["total_asistentes"].tolist() == [3, 0, 4]
    assert df.attrs["control"]["coincide_con_declarados"] and len(df.attrs["control"]["bloques"]) == 2
    assert "PERSONA" not in " ".join(map(str, df.to_numpy().ravel()))  # los nombres de los títulos no llegan a los datos


# ----------------------------------------------------------------------------- CRM
def test_crm_descarta_vacias_totales_y_encabezados_repetidos_y_lo_cuenta(tmp_path):
    enc = ["ID de registro [anonimizado]", "Nombre de Empresa [anonimizado]", "Estado de la Membresía", "Columna eliminada"]
    filas = [enc, ["R-1", "EMP-0001", "Activo", None], [None] * 4, ["R-2", "EMP-0002", "Cancelado", None], list(enc), ["Total", None, "2", None], ["R-3", "sin código", "Activo", None]]
    df = carga.cargar_crm(_libro(tmp_path, "crm.xlsx", [("Sheet0", filas)]))
    assert list(df.columns) == ["id_registro", "empresa_id", "estado_membresia"]  # renombradas a snake_case y sin la columna ajena
    assert df["empresa_id"].tolist() == ["EMP-0001", "EMP-0002", "sin código"]
    ctl = df.attrs["control"]
    assert ctl["filas_vacias"] == 1 and ctl["filas_total"] == 1 and ctl["filas_encabezado_repetido"] == 1 and ctl["filas_sin_codigo"] == 1 and ctl["filas_validas"] == 2
    assert {r["motivo"] for r in df.attrs["rechazos"]} == {"total", "encabezado repetido"}


# ----------------------------------------------------------------------------- libro de asistencia con hojas de estructura distinta
def _libro_asistencia(tmp_path):
    enc_a = [None, "ID_EMPRESA (antes Nit)", "Empresa [eliminado]", "ID_PERSONA [anonimizado]", "Nivel de cargo [anonimizado]", "cedula [eliminado]", "E-mail [eliminado]",
             None, "Costo [anonimizado]", "Autorización datos ", "Estado de registro de ubicación principal"]
    hoja_a = [["Taller de prueba"], enc_a,
              [1, "EMP-0001", None, "P-00001", "Dirección / Gerencia", None, None, 1, "Con costo", "SÍ ", "Si"],
              [1, "EMP-0002", None, "P-00002", "Sin dato", None, None, 1, "Sin costo", "No", "Sí"],
              [None] * 11,
              [None, "TOTAL", None, None, None, None, None, None, None, None, None],
              [None, "ID_EMPRESA (antes Nit)", None, "ID_PERSONA [anonimizado]"],
              [1, None, None, "P-00003", "Otro", None, None, 1, "Sin costo", "SI", "Si"],
              [None] * 11, [None] * 11]
    enc_b = ["Columna 1", "ID_EMPRESA (antes Nit)", "Empresa [eliminado]", "ID_PERSONA [anonimizado]", "Número de celular [eliminado]", "Email [eliminado]",
             "Nivel de cargo [anonimizado]", "Tratamiento de datos personales", "Estado "]
    hoja_b = [[None, "Foro de prueba"], enc_b, [1, "EMP-0001", None, "P-00001", None, None, "Otro", "SÍ, AUTORIZO EL TRATAMIENTO", "agendado "],
              [1, "EMP-0001", None, "P-00001", None, None, "Otro", "SÍ, AUTORIZO EL TRATAMIENTO", None]]
    homologacion = [["Homologación de los eventos"], [None], ["N° evento (columna en GENERAL)", "Hoja de origen", "Fecha", "Nombre del evento", "Línea oferta 2027", "Experiencia / detalle", "Modalidad (inferida)"],
                    [1, "ENERO 5", "2026-01-05", "Taller de prueba", "Anticipar", "Actho Legislativo", "Virtual"],
                    [2, "MARZO 17", "2026-03-17", "Semana del Talento", "Evento grande", None, "Presencial"],
                    [3, "FEBRERO 13", "2026-02-13", "Live sin lista", "Anticipar", None, "Virtual"], [None]]
    sumas = [None, None] + [f"=+SUM({c}7:{c}7)" for c in ["C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N"]]
    general = [
        [None], [None, "MES "], ["ID_EMPRESA [anonimizado]", "NUMERO DE EVENTOS ", 1, 2, 3], [None, "FECHA ", datetime(2026, 1, 5), "17-20/03/2026", datetime(2026, 2, 13)],
        [None, "NOMBRE DE LA ACTIVIDAD "], [None, "ID_EMPRESA (antes NIT)", "ASISTENCIA 1", "ASISTENCIA 2", "ASISTENCIA 3"],
        ["EMP-0001", "EMP-0001", "=+COUNTIFS('ENERO 5'!$B$3:$B$3,'GENERAL (2)'!B7)", "=+COUNTIFS('MARZO 17'!$B$3:$B$3,'GENERAL (2)'!B7)"],
        ["EMP-0002", "EMP-0002", "=+COUNTIFS('ENERO 5'!$B$3:$B$3,'GENERAL (2)'!B8)"],
        sumas,
    ]
    return _libro(tmp_path, "asistencia.xlsx", [("GENERAL (2)", general), ("MARZO 17", hoja_b), ("ENERO 5", hoja_a), ("FEBRERO 13", [[None] * 5] * 3),
                                                ("HOMOLOGACION OFERTA 2027", homologacion)])


@pytest.fixture
def asistencia(tmp_path):
    return carga.cargar_asistencia(_libro_asistencia(tmp_path))


def test_asistencia_une_hojas_de_estructura_distinta_ubicando_las_columnas_por_su_texto(asistencia):
    ev, a, _ = asistencia
    assert len(ev) == 3 and ev["fecha"].iloc[1] == pd.Timestamp(2026, 3, 17)
    assert len(a) == 4 and set(a["hoja"]) == {"ENERO 5", "MARZO 17"}
    assert a.loc[a["hoja"] == "MARZO 17", "autoriza_datos"].iloc[0].startswith("SÍ")  # columna con otro nombre y otra posición
    assert a.loc[(a["hoja"] == "MARZO 17") & a["estado_registro"].notna(), "estado_registro"].iloc[0].strip() == "agendado"
    assert a.loc[a["hoja"] == "ENERO 5", "registro_ubicacion"].tolist() == ["Si", "Sí"]
    assert a["nivel_cargo"].tolist().count("Otro") == 2


def test_asistencia_cuenta_y_lista_lo_que_descarta(asistencia):
    _, _, c = asistencia
    ene = c["lectura"]["ENERO 5"]
    assert ene["filas_validas"] == 2 and ene["filas_total"] == 1 and ene["filas_encabezado_repetido"] == 1 and ene["filas_sin_codigo"] == 1 and ene["filas_vacias"] == 1
    assert c["lectura"]["MARZO 17"]["filas_validas"] == 2 and c["hojas_sin_encabezado"] == ["FEBRERO 13"]
    motivos = sorted(r["motivo"] for r in c["filas_rechazadas"])
    assert motivos == ["encabezado repetido", "sin código de empresa", "total mezclado con datos"]
    assert any(r["clave"] == "P-00003" and r["ubicacion"].startswith("ENERO 5") for r in c["filas_rechazadas"])
    assert c["hojas_sin_homologar"] == [] and c["eventos_sin_hoja"] == []


def test_asistencia_lee_las_fechas_de_fin_de_la_hoja_general(asistencia):
    ev, _, _ = asistencia
    assert ev["fecha_fin_general"].iloc[1] == pd.Timestamp(2026, 3, 20)  # «17-20/03/2026»
    assert ev["fecha_fin_general"].iloc[0] == pd.Timestamp(2026, 1, 5)


def test_asistencia_audita_las_formulas_rotas_de_general(asistencia):
    _, _, c = asistencia
    assert c["columnas_con_rango_truncado"] == [1, 2]  # los COUNTIFS cubren hasta la fila 3 y las hojas tienen más filas
    assert c["fila_de_totales"] == 9 and c["sumas_en_fila_de_totales"] == 12 and c["sumas_con_rango_truncado"] == 12
    assert c["empresas_listadas"] == 2 and c["empresas_con_asistencia_real_no_listadas"] == 0 and c["celdas_con_error_excel"] == 0


def test_un_libro_sin_la_hoja_general_no_rompe_la_carga(tmp_path):
    ruta = _libro_asistencia(tmp_path)
    wb = openpyxl.load_workbook(ruta)
    del wb["GENERAL (2)"]
    wb.save(ruta)
    ev, a, c = carga.cargar_asistencia(ruta)
    assert len(a) == 4 and ev["fecha_fin_general"].isna().all() and "fila_de_totales" not in c
