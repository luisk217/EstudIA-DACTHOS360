"""Integridad referencial y verificación del modelo: los huérfanos se reportan (no se ocultan) y los errores se detectan."""
import json

import pandas as pd
import pytest

from pipeline import exportacion, modelo
from pipeline.esquema import C, Tabla
from pipeline.validacion import IntegridadError, exigir_integridad, resumen_para_meta, verificar_modelo


def mini(sev="error"):
    """Dos tablas: un catálogo de empresas y un hecho que la referencia."""
    return {
        "dim_a": Tabla("dim_a", "dimension", "Padre.", ("a_id",), (
            C("a_id", "texto", "Clave.", False),
            C("tipo", "texto", "Tipo.", valores=("x", "y")),
        )),
        "fact_b": Tabla("fact_b", "hecho", "Hijo.", ("b_id",), (
            C("b_id", "texto", "Clave.", False),
            C("a_id", "texto", "Referencia.", fk=("dim_a", "a_id"), fk_severidad=sev, fk_explicacion="No afiliada."),
            C("valor", "entero", "Valor.", rango=(0, 10)),
            C("marca", "booleano", "Marca.", False),
        )),
    }


def datos(**cambios):
    m = {
        "dim_a": pd.DataFrame({"a_id": ["A1", "A2"], "tipo": ["x", "y"]}),
        "fact_b": pd.DataFrame({"b_id": ["B1", "B2", "B3"], "a_id": ["A1", "A2", None], "valor": pd.array([1, 5, None], dtype="Int64"),
                                "marca": pd.array([True, False, True], dtype="boolean")}),
    }
    m.update(cambios)
    return m


def problemas(rep, codigo):
    return [p for p in rep["problemas"] if p["codigo"] == codigo]


def test_un_modelo_correcto_pasa_y_los_nulos_de_una_fk_no_son_huerfanos():
    rep = verificar_modelo(datos(), mini())
    assert rep["ok"] and rep["huerfanos"].empty and rep["resumen"]["errores"] == 0
    r = rep["relaciones"].iloc[0]
    assert (r["filas_hijo"], r["filas_nulas"], r["filas_con_valor"], r["filas_huerfanas"], r["estado"]) == (3, 1, 2, 0, "ok")


def test_un_huerfano_de_severidad_error_rompe_el_modelo_y_queda_listado():
    m = datos()
    m["fact_b"].loc[1, "a_id"] = "A9"
    rep = verificar_modelo(m, mini("error"))
    assert not rep["ok"]
    h = rep["huerfanos"].iloc[0]
    assert (h["tabla_hijo"], h["columna"], h["tabla_padre"], h["valor"], h["filas"], h["severidad"]) == ("fact_b", "a_id", "dim_a", "A9", 1, "error")
    assert rep["relaciones"].iloc[0]["estado"] == "ROTA" and rep["resumen"]["filas_huerfanas_error"] == 1
    with pytest.raises(IntegridadError):
        exigir_integridad(rep)


def test_un_huerfano_de_severidad_aviso_se_reporta_pero_no_detiene():
    m = datos()
    m["fact_b"].loc[[0, 1], "a_id"] = ["A9", "A9"]
    rep = verificar_modelo(m, mini("aviso"))
    assert rep["ok"] and rep["resumen"]["filas_huerfanas_aviso"] == 2 and rep["resumen"]["filas_huerfanas_error"] == 0
    h = rep["huerfanos"].iloc[0]
    assert h["valor"] == "A9" and h["filas"] == 2 and h["severidad"] == "aviso" and h["explicacion"] == "No afiliada."
    assert rep["relaciones"].iloc[0]["estado"] == "huérfanos esperados" and rep["relaciones"].iloc[0]["valores_huerfanos"] == 1
    exigir_integridad(rep)  # no lanza


def test_clave_primaria_repetida_o_nula_y_columna_obligatoria_con_nulos():
    m = datos()
    m["fact_b"].loc[1, "b_id"] = "B1"
    m["dim_a"].loc[0, "a_id"] = None
    m["fact_b"].loc[0, "marca"] = pd.NA
    rep = verificar_modelo(m, mini())
    assert problemas(rep, "clave_primaria_repetida") and not rep["ok"]
    nulos = {(p["tabla"], p["columna"]) for p in problemas(rep, "nulos_en_columna_obligatoria")}
    assert nulos == {("dim_a", "a_id"), ("fact_b", "marca")}


def test_columnas_de_mas_de_menos_o_mal_nombradas_y_tipos_incorrectos():
    m = datos()
    m["fact_b"] = m["fact_b"].drop(columns="marca").assign(Extra=1)
    m["dim_a"]["tipo"] = [1, 2]
    rep = verificar_modelo(m, mini())
    assert problemas(rep, "columnas_faltantes")[0]["columna"] == "marca"
    assert problemas(rep, "columnas_sobrantes")[0]["columna"] == "Extra"
    assert problemas(rep, "nombre_no_snake_case")[0]["columna"] == "Extra"
    assert any(p["tabla"] == "dim_a" and p["columna"] == "tipo" for p in problemas(rep, "tipo_incorrecto"))  # enteros en una columna de texto
    m2 = datos()
    m2["fact_b"]["valor"] = ["a", "b", "c"]
    assert any(p["columna"] == "valor" for p in problemas(verificar_modelo(m2, mini()), "tipo_incorrecto"))


def test_valores_fuera_de_rango_y_fuera_de_lista():
    m = datos()
    m["fact_b"].loc[0, "valor"] = 99
    m["dim_a"].loc[1, "tipo"] = "z"
    rep = verificar_modelo(m, mini())
    assert problemas(rep, "fuera_de_rango")[0]["cantidad"] == 1 and not rep["ok"]
    h = rep["huerfanos"]
    assert h.loc[h["tipo"] == "fuera_de_catalogo", "valor"].tolist() == ["z"] and h.loc[h["tipo"] == "fuera_de_catalogo", "severidad"].iloc[0] == "aviso"
    assert rep["resumen"]["valores_fuera_de_catalogo"] == 1


def test_tabla_o_padre_ausente():
    rep = verificar_modelo({"fact_b": datos()["fact_b"]}, mini())
    assert problemas(rep, "tabla_ausente") and problemas(rep, "padre_ausente") and not rep["ok"]


# ----------------------------------------------------------------------------- con el modelo completo (datos sintéticos)
@pytest.fixture
def m(resultado_sintetico):
    return modelo.construir_modelo(resultado_sintetico)


def test_las_empresas_fuera_del_crm_se_listan_como_aviso_y_no_se_ocultan(m):
    rep = verificar_modelo(m)
    h = rep["huerfanos"]
    h = h[(h["tabla_hijo"] == "fact_asistencia") & (h["columna"] == "empresa_id")]
    assert h["valor"].tolist() == ["EMP-0900"] and h["filas"].iloc[0] == 1 and h["severidad"].iloc[0] == "aviso"
    nuevas = rep["huerfanos"].query("tabla_hijo == 'fact_afiliacion_nueva'")
    assert nuevas["valor"].tolist() == ["EMP-1771"]  # el desfase de captura entre el informe de nuevos y el CRM
    assert rep["ok"]


def test_romper_una_clave_foranea_del_modelo_completo_se_detecta(m):
    m["fact_asistencia"].loc[0, "evento_id"] = "EV99"
    rep = verificar_modelo(m)
    assert not rep["ok"]
    h = rep["huerfanos"].query("severidad == 'error'")
    assert h["valor"].tolist() == ["EV99"] and h["tabla_hijo"].iloc[0] == "fact_asistencia"


def test_las_ciudades_sin_homologar_quedan_a_la_vista(m):
    m["fact_asistencia"].loc[0, "ciudad"] = "Narnia"
    rep = verificar_modelo(m)
    h = rep["huerfanos"].query("columna == 'ciudad' and valor == 'Narnia'")
    assert len(h) == 1 and h["severidad"].iloc[0] == "aviso" and rep["ok"]


def _valida_falsa(m):
    a = m["fact_asistencia"]
    a["es_valida"] = pd.array([False] * len(a), dtype="boolean")


def _evento_termina_antes(m):
    e = m["dim_evento"]
    e["fecha_fin"] = e["fecha_inicio"] - pd.Timedelta(days=1)


def _mes_incorrecto(m):
    m["dim_evento"]["mes"] = "2020-01"


def _nps_incorrecto(m):
    m["fact_encuesta"]["nps_categoria"] = "Pasivo"


@pytest.mark.parametrize("cambio,codigo", [
    (_valida_falsa, "regla_valida_incoherente"), (_evento_termina_antes, "regla_evento_fechas"),
    (_mes_incorrecto, "regla_evento_mes"), (_nps_incorrecto, "regla_nps_categoria"),
])
def test_reglas_de_negocio_del_modelo(m, cambio, codigo):
    cambio(m)
    rep = verificar_modelo(m)
    assert problemas(rep, codigo) and not rep["ok"]


def test_dos_asistencias_validas_de_la_misma_persona_en_el_mismo_evento_se_detectan(m):
    a = m["fact_asistencia"]
    i = a.index[a["es_duplicado"]][0]
    a.loc[i, ["es_duplicado", "es_valida"]] = [False, True]
    assert problemas(verificar_modelo(m), "regla_persona_evento_repetida")


def test_el_resumen_para_meta_es_json_y_no_trae_la_tabla_completa(m):
    rep = verificar_modelo(m)
    s = resumen_para_meta(rep, max_huerfanos=1)
    txt = json.dumps(exportacion._limpio(s), ensure_ascii=False)
    assert s["ok"] and len(s["muestra_huerfanos"]) == 1 and "relaciones_con_huerfanos_detalle" in s
    assert "@" not in txt and "http" not in txt
    sin = resumen_para_meta(verificar_modelo(datos(), mini()))
    assert sin["muestra_huerfanos"] == [] and sin["huerfanos_por_relacion"] == []
