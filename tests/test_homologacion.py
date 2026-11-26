"""Diccionario de homologación editable (config/homologacion.json): estructura, consistencia y efecto de editarlo."""
import json

import pytest

from pipeline import config
from pipeline import limpieza as lp


@pytest.fixture
def diccionario_temporal(tmp_path):
    """Copia editable del diccionario; al terminar se restaura el original."""
    original = config.RUTA_HOMOLOGACION
    ruta = tmp_path / "homologacion.json"
    ruta.write_text(original.read_text(encoding="utf-8"), encoding="utf-8")
    yield ruta
    config.recargar_homologacion(original)


def _editar(ruta, f):
    d = json.loads(ruta.read_text(encoding="utf-8"))
    f(d)
    ruta.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")


def test_el_diccionario_entregado_es_valido():
    assert config.validar_homologacion(config.HOMOLOGACION) == []
    for s in config.SECCIONES_HOMOLOGACION:
        assert s in config.HOMOLOGACION


def test_los_mapeos_ya_no_estan_incrustados_en_el_codigo():
    texto = (config.RAIZ / "pipeline" / "config.py").read_text(encoding="utf-8")
    assert "Medellín" not in texto and "Itagüí" not in texto and "Conectar" not in texto  # viven en el JSON
    assert config.CIUDADES_CANONICAS == config.HOMOLOGACION["ciudades"]["equivalencias"]
    assert config.NIVEL_POR_CATEGORIA == config.HOMOLOGACION["niveles"]["por_categoria"]
    assert config.NIVELES == ("Conectar", "Crecer", "Liderar")


def test_todas_las_equivalencias_apuntan_a_valores_del_catalogo_y_sus_claves_estan_normalizadas():
    for nombre, sec in config.HOMOLOGACION.items():
        if not (isinstance(sec, dict) and "equivalencias" in sec):
            continue
        cat = set(config.catalogo(sec))
        for k, v in sec["equivalencias"].items():
            assert k == lp.clave_texto(k), (nombre, k)
            assert not cat or v in cat, (nombre, k, v)
        assert len(cat) == len(config.catalogo(sec)), f"catálogo con repetidos en {nombre}"


def test_los_estados_vigentes_y_no_vigentes_cubren_el_catalogo_sin_solaparse():
    e = config.HOMOLOGACION["estados_membresia"]
    assert set(e["vigentes"]) | set(e["no_vigentes"]) == set(e["catalogo"]) and not set(e["vigentes"]) & set(e["no_vigentes"])
    assert config.ESTADOS_VIGENTES == tuple(e["vigentes"])


def test_validar_detecta_secciones_ausentes_claves_mal_escritas_y_destinos_invalidos():
    h = json.loads(json.dumps(config.HOMOLOGACION))
    del h["sectores"]
    h["ciudades"]["equivalencias"]["MEDELLÍN "] = "Medellín"
    h["ciudades"]["equivalencias"]["xyz"] = "Ciudad inventada"
    p = config.validar_homologacion(h)
    assert any("sectores" in x for x in p) and any("MEDELLÍN" in x for x in p) and any("Ciudad inventada" in x for x in p)


def test_editar_el_json_cambia_la_limpieza_sin_tocar_codigo(diccionario_temporal):
    assert lp.normalizar_ciudad("Chiquinquirá") == "Chiquinquirá"
    assert lp.normalizar_ciudad("Chiqui") == "Chiqui"
    _editar(diccionario_temporal, lambda d: (d["ciudades"]["catalogo"].append("Chiquinquirá"),
                                             d["ciudades"]["equivalencias"].update({"chiqui": "Chiquinquirá"})))
    config.recargar_homologacion(diccionario_temporal)
    assert lp.normalizar_ciudad("Chiqui") == "Chiquinquirá" and "Chiquinquirá" in config.catalogo(config.HOMOLOGACION["ciudades"])
    _editar(diccionario_temporal, lambda d: d["niveles"]["por_categoria"].update({"platino": "Liderar"}))
    config.recargar_homologacion(diccionario_temporal)
    assert lp.normalizar_nivel("Platino") == "Liderar"
    _editar(diccionario_temporal, lambda d: d["centinelas_nulos"].append("pendiente de dato"))
    config.recargar_homologacion(diccionario_temporal)
    assert lp.es_centinela("Pendiente de dato") and lp.limpiar_texto("Pendiente de dato") is None


def test_un_diccionario_roto_no_se_carga(diccionario_temporal):
    _editar(diccionario_temporal, lambda d: d["sectores"]["equivalencias"].update({"x": "Sector que no existe"}))
    with pytest.raises(ValueError, match="homologacion.json inválido"):
        config.cargar_homologacion(diccionario_temporal)


def test_fuera_de_catalogo_lista_lo_que_falta_agregar():
    assert lp.fuera_de_catalogo(["Bogotá", "Medellín", "Narnia", None], "ciudades") == ["Narnia"]
    assert lp.fuera_de_catalogo(["Presencial", "Hibrido"], "modalidades") == ["Hibrido"]


@pytest.mark.parametrize("fn,entrada,esperado", [
    (lp.normalizar_ciudad, "Bogotá D.C.", "Bogotá"), (lp.normalizar_ciudad, "BOGOTÁ D.C.", "Bogotá"), (lp.normalizar_ciudad, "Bigotá", "Bogotá"),
    (lp.normalizar_ciudad, "Medelon", "Medellín"), (lp.normalizar_ciudad, "Barra", "Barranquilla"), (lp.normalizar_ciudad, "Floridablanca Girón", "Floridablanca"),
    (lp.normalizar_ciudad, "Bogota (Bogota)", "Bogotá"), (lp.normalizar_ciudad, "Gachancipa", "Gachancipá"),
    (lp.normalizar_sector, "ONG", "Entidades sin ánimo de lucro"), (lp.normalizar_sector, "Entidades Sin Animo de Lucro", "Entidades sin ánimo de lucro"),
    (lp.normalizar_sector, "Soluciones y Productos para  RRHH", "Soluciones y Productos para RRHH"),
    (lp.normalizar_subsector, "Servivios Legales", "Servicios legales"), (lp.normalizar_subsector, "Centros De Formación", "Centros de formación"),
    (lp.normalizar_pais, "COLOMBIA", "Colombia"), (lp.normalizar_pais, "Colomba", "Colombia"),
    (lp.normalizar_departamento, "DC", "Bogotá D.C."), (lp.normalizar_departamento, "Bogotá, D.C.", "Bogotá D.C."),
    (lp.normalizar_departamento, "Atlantico", "Atlántico"), (lp.normalizar_region, "Medellin", "Antioquia"), (lp.normalizar_region, "Otro", "Otra"),
    (lp.normalizar_tamano, "Pequeña", "Pequeña"), (lp.normalizar_tamano, "PEQUENA", "Pequeña"),
    (lp.normalizar_estado_membresia, "periodo de gracia", "Periodo de Gracia"), (lp.normalizar_estado_registro, "INACTIVO", "Inactivo"),
    (lp.normalizar_modalidad, "hibrido", "Híbrido"), (lp.normalizar_linea, "FORO", "Foro"),
    (lp.normalizar_nivel_cargo, "Sin dato", None), (lp.normalizar_nivel_cargo, "Alta dirección", "Alta dirección (C-level / VP)"),
    (lp.normalizar_categoria_membresia, "Estandar", "Estándar"), (lp.normalizar_categoria_membresia, "Empresas", None),
    (lp.normalizar_categoria_membresia, "Plus", None), (lp.normalizar_tipo_membresia, "Jóvenes Talentos / Estudiantes", "Estudiante"),
])
def test_equivalencias_del_diccionario_en_los_normalizadores(fn, entrada, esperado):
    assert fn(entrada) == esperado
