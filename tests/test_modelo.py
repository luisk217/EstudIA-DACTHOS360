"""Modelo relacional normalizado: estructura, tipos, claves, formato tidy y centinelas, sobre datos sintéticos."""
import pandas as pd
import pytest

from pipeline import esquema, modelo
from pipeline import limpieza as lp
from pipeline.validacion import verificar_modelo


@pytest.fixture
def m(resultado_sintetico):
    return modelo.construir_modelo(resultado_sintetico)


def test_el_modelo_tiene_todas_las_tablas_del_esquema_y_en_orden_de_carga(m):
    assert list(m) == esquema.orden_de_carga() and set(m) == set(esquema.ESQUEMA)
    vistas: set[str] = set()
    for n in m:  # los padres siempre van antes que los hijos
        for c in esquema.ESQUEMA[n].columnas:
            if c.fk and c.fk[0] != n:
                assert c.fk[0] in vistas, (n, c.nombre)
        vistas.add(n)


def test_cada_tabla_coincide_con_su_esquema_y_usa_snake_case(m):
    for n, df in m.items():
        assert list(df.columns) == esquema.ESQUEMA[n].nombres(), n
        assert all(lp.es_snake_case(c) for c in df.columns), n


def test_el_modelo_sintetico_pasa_la_verificacion_de_integridad(m):
    rep = verificar_modelo(m)
    assert rep["ok"], rep["problemas"]
    assert rep["resumen"]["errores"] == 0


def test_los_centinelas_internos_pasan_a_nulos_reales(m, resultado_sintetico):
    asist = resultado_sintetico.asistencias
    assert (asist["nivel_cargo"] == "Sin dato").any()  # el pipeline interno conserva «Sin dato» para el tablero
    assert m["fact_asistencia"]["nivel_cargo"].isna().any() and not (m["fact_asistencia"]["nivel_cargo"] == "Sin dato").any()
    af = m["dim_afiliado"].set_index("empresa_id")
    assert pd.isna(af.loc["EMP-0005", "estado_membresia"]) and pd.isna(af.loc["EMP-0005", "nivel"])
    assert m["dim_evento"]["linea"].isna().sum() == 1  # el evento sin línea no queda como «Sin clasificar»


def test_los_booleanos_las_fechas_y_los_enteros_tienen_su_tipo(m):
    a, af = m["fact_asistencia"], m["dim_afiliado"]
    assert str(a["autoriza_datos"].dtype) == "boolean" and str(a["marca_fuente"].dtype) == "Int64"
    assert pd.api.types.is_datetime64_any_dtype(af["fecha_expiracion"]) and str(af["cantidad_miembros"].dtype) == "Int64"
    assert a["autoriza_datos"].dropna().isin([True, False]).all()  # SI, Sí, SÍ y NO ya son booleanos
    assert a.loc[a["persona_id"] == "P-00002", "autoriza_datos"].iloc[0] == False  # noqa: E712


def test_fact_asistencia_conserva_las_marcas_en_vez_de_borrar_filas(m, resultado_sintetico):
    a = m["fact_asistencia"]
    assert len(a) == len(resultado_sintetico.asistencias)
    assert a["es_duplicado"].sum() == 1 and a["es_agendado"].sum() == 1
    assert a["es_valida"].sum() == len(a) - 2
    assert a["asistencia_id"].is_unique and a["asistencia_id"].iloc[0] == "AS-00001"


def test_dim_ejecutiva_incluye_sin_asignar_y_las_de_los_informes(m):
    e = m["dim_ejecutiva"].set_index("ejecutiva_id")
    assert not e.loc["EJ-SIN_ASIGNAR", "es_asignada"]
    assert {"EJ-A", "EJ-B"} <= set(e.index) and e["ejecutiva"].is_unique
    assert modelo.id_ejecutiva("KAM C") == "EJ-C" and modelo.id_ejecutiva("Sin asignar") == "EJ-SIN_ASIGNAR"


def test_aspectos_y_temas_estan_en_formato_largo(m):
    asp = m["fact_encuesta_aspecto"]
    assert set(asp.columns) == {"respuesta_id", "aspecto", "calificacion"}
    assert not asp.duplicated(["respuesta_id", "aspecto"]).any() and asp["calificacion"].between(1, 5).all()
    post = asp[asp["respuesta_id"] == "PE-0001"]
    assert set(post["aspecto"]) == {"satisfaccion_global", "expositor", "contenido", "espacio", "manejo_tiempo"}  # los nulos no generan fila
    assert set(m["fact_encuesta_tema"]["tema"]) == {"IA", "Nómina"}


def test_dim_persona_marca_a_quien_figura_con_varias_empresas(m):
    p = m["dim_persona"].set_index("persona_id")
    assert p.loc["P-00001", "multiples_empresas"] and p.loc["P-00001", "n_empresas_asociadas"] == 2  # EMP-0001 y EMP-0900
    assert not p.loc["P-00003", "multiples_empresas"]
    assert "afiliado_principal" in p.loc["P-02901", "fuentes"]
    assert p.index.is_unique


def test_afiliacion_nueva_une_informe_y_lista_por_empresa(m):
    f = m["fact_afiliacion_nueva"].set_index("empresa_id")
    assert f.loc["EMP-0004", "en_informe_afiliaciones"] and f.loc["EMP-0004", "en_lista_nuevos"]
    assert not f.loc["EMP-1771", "en_informe_afiliaciones"] and f.loc["EMP-1771", "en_lista_nuevos"] and pd.isna(f.loc["EMP-1771", "ejecutiva_id"])
    assert f["afiliacion_id"].is_unique


def test_el_score_y_sus_factores_quedan_relacionados(m):
    s, f = m["fact_score_afiliado"], m["fact_score_factor"]
    assert s["empresa_id"].is_unique and set(f["empresa_id"]) <= set(s["empresa_id"])
    assert not f.duplicated(["empresa_id", "orden"]).any() and (s["riesgo"] + s["salud"]).round(1).eq(100).all()


def test_coaccionar_acepta_columnas_ausentes_y_tipos_mezclados():
    t = esquema.ESQUEMA["dim_nivel"]
    out = modelo.coaccionar(pd.DataFrame({"nivel": ["Conectar"], "orden": ["1"]}), t)
    assert list(out.columns) == t.nombres() and str(out["orden"].dtype) == "Int64" and out["descripcion"].isna().all()
