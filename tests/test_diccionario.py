"""El diccionario de datos documentado coincide con el esquema del modelo."""
from pipeline import esquema
from tests.conftest import RAIZ

DOC = (RAIZ / "docs" / "DICCIONARIO_DATOS.md").read_text(encoding="utf-8")


def test_el_bloque_generado_coincide_con_el_esquema():
    ini, fin = "<!-- inicio:esquema -->", "<!-- fin:esquema -->"
    bloque = DOC.split(ini)[1].split(fin)[0].strip()
    assert bloque == esquema.a_markdown().strip()


def test_todas_las_tablas_y_columnas_estan_documentadas():
    for t in esquema.TABLAS:
        assert f"### `{t.nombre}`" in DOC
        assert all(f"`{c.nombre}`" in DOC for c in t.columnas)
    assert all(f"`{c}`" in DOC for c in esquema.CONTROLES)
