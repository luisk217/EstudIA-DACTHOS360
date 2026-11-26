"""Consistencia de los JSON publicados en web/data: esquema, rangos, identificadores y privacidad.

Se prueban los archivos tal como los consume el frontend, sin volver a ejecutar el pipeline.
"""
import json
import re
from datetime import date

import pytest

from pipeline import score as sc
from tests.conftest import RAIZ

DIR = RAIZ / "web" / "data"
NOMBRES = ("meta", "resumen", "afiliados", "eventos", "ejecutivas", "encuestas", "segmentos")
BANDAS = ("Saludable", "Atención", "Riesgo alto")
PAT_ID = re.compile(r"^EMP-\d{3,5}$")
CAMPOS_AFILIADO = {
    "id", "nivel", "tipo", "sector", "tamano", "ciudad", "ejecutiva", "estado", "expira", "dias_venc", "afiliacion",
    "antig_anios", "asist", "asist_90d", "eventos", "personas", "ult_asist", "dias_ult_asist", "sat", "n_resp",
    "nps_min", "comunidad", "renovo_reciente", "riesgo", "salud", "banda", "factores", "accion",
}
CODIGOS_FACTOR = set(sc.ACCIONES) | {"renovacion_reciente"}
# Nombres de campo que delatarían texto libre o datos personales de las encuestas.
CLAVES_PROHIBIDAS = {
    "comentario", "comentarios", "observacion", "observaciones", "sugerencia", "sugerencias", "respuesta_abierta",
    "texto_libre", "opinion", "mensaje", "email", "correo", "telefono", "celular", "nombre_persona", "persona_id",
    "cargo", "nit", "documento", "temas_solicitados_texto",
}


def _rechazar_constante(c):
    raise ValueError(f"constante no válida en JSON: {c}")


@pytest.fixture(scope="module")
def d():
    out = {}
    for n in NOMBRES:
        texto = (DIR / f"{n}.json").read_text(encoding="utf-8")
        out[n] = json.loads(texto, parse_constant=_rechazar_constante)  # prohíbe NaN e Infinity
        out[f"_texto_{n}"] = texto
    return out


def _claves(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield str(k)
            yield from _claves(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _claves(v)


def _en_rango(v, lo, hi):
    return v is None or (isinstance(v, (int, float)) and not isinstance(v, bool) and lo <= v <= hi)


def test_los_siete_archivos_existen_y_son_objetos(d):
    for n in NOMBRES:
        assert isinstance(d[n], dict) and d[n], n


def test_afiliados_esquema_e_identificadores(d):
    lista = d["afiliados"]["afiliados"]
    assert len(lista) > 0
    ids = [a["id"] for a in lista]
    assert len(ids) == len(set(ids)), "ids duplicados"
    for a in lista:
        assert set(a) == CAMPOS_AFILIADO, a["id"]
        assert PAT_ID.match(a["id"]), a["id"]
        assert isinstance(a["comunidad"], bool) and isinstance(a["renovo_reciente"], bool)
        assert a["banda"] in BANDAS


def test_afiliados_rangos_y_coherencia_interna(d):
    meta = d["meta"]
    um = meta["score"]["umbrales"]
    corte = date.fromisoformat(meta["fecha_corte"])
    vigentes = {"Activo", "Periodo de Gracia", "Pronto a Expirar"}
    for a in d["afiliados"]["afiliados"]:
        i = a["id"]
        assert 0 <= a["riesgo"] <= 100 and 0 <= a["salud"] <= 100, i
        assert abs(a["riesgo"] + a["salud"] - 100) < 0.051, f"riesgo + salud != 100 en {i}"
        esperada = sc.asignar_banda(a["riesgo"], {"bandas": um})
        assert a["banda"] == esperada, f"banda incoherente en {i}"
        assert a["estado"] in vigentes, i
        assert a["nivel"] in {"Conectar", "Crecer", "Liderar", "Sin dato"}, i
        assert a["ejecutiva"], i
        # Contadores de participación.
        for k in ("asist", "asist_90d", "eventos", "personas", "n_resp"):
            assert isinstance(a[k], int) and a[k] >= 0, (i, k)
        assert a["asist_90d"] <= a["asist"] and a["eventos"] <= a["asist"] and a["personas"] <= a["asist"], i
        assert (a["asist"] == 0) == (a["ult_asist"] is None) == (a["dias_ult_asist"] is None), i
        assert _en_rango(a["sat"], 1, 5) and _en_rango(a["nps_min"], 0, 10), i
        assert a["n_resp"] > 0 or (a["sat"] is None and a["nps_min"] is None), i
        assert _en_rango(a["antig_anios"], 0, 100), i
        # Fechas y días a vencimiento.
        assert (a["expira"] is None) == (a["dias_venc"] is None), i
        if a["expira"]:
            assert (date.fromisoformat(a["expira"]) - corte).days == a["dias_venc"], f"dias_venc incoherente en {i}"
        if a["afiliacion"]:
            assert date.fromisoformat(a["afiliacion"]) <= corte, i
        # Factores: ordenados, con puntos positivos y códigos conocidos.
        f = a["factores"]
        assert len(f) <= 5, i
        assert all(x["c"] in CODIGOS_FACTOR and x["p"] > 0 and x["t"] for x in f), i
        assert [x["p"] for x in f] == sorted((x["p"] for x in f), reverse=True), i
        assert a["accion"], i
        assert a["banda"] == "Saludable" or f, f"sin factores en afiliado no saludable {i}"


def test_resumen_cuadra_con_afiliados(d):
    lista, r = d["afiliados"]["afiliados"], d["resumen"]
    n = len(lista)
    assert r["afiliados_vigentes"] == n
    assert sum(r["por_estado"].values()) == n and sum(r["por_nivel"].values()) == n and sum(r["por_banda"].values()) == n
    for b in BANDAS:
        assert r["por_banda"][b] == sum(a["banda"] == b for a in lista)
    assert r["vencimientos"]["vencidas"] == sum(a["dias_venc"] is not None and a["dias_venc"] < 0 for a in lista)
    assert r["vencimientos"]["sin_fecha"] == sum(a["dias_venc"] is None for a in lista)
    assert r["participacion"]["sin_asistencia_anio"] == sum(a["asist"] == 0 for a in lista)
    assert abs(r["riesgo_medio"] + r["salud_media"] - 100) < 0.11
    assert _en_rango(r["satisfaccion"]["media_1a5"], 1, 5)


def test_ejecutivas_suman_la_cartera(d):
    lista, ej = d["afiliados"]["afiliados"], d["ejecutivas"]["ejecutivas"]
    nombres = [e["nombre"] for e in ej]
    assert len(nombres) == len(set(nombres))
    assert sum(e["cartera"] for e in ej) == len(lista)
    por_id = {a["id"]: a for a in lista}
    for e in ej:
        propios = [a for a in lista if a["ejecutiva"] == e["nombre"]]
        assert e["cartera"] == len(propios) and sum(e["por_banda"].values()) == e["cartera"], e["nombre"]
        assert 1 <= len(e["prioritarios"]) <= 10
        assert all(i in por_id and por_id[i]["ejecutiva"] == e["nombre"] for i in e["prioritarios"]), e["nombre"]
        assert _en_rango(e["riesgo_medio"], 0, 100)


def test_segmentos_apuntan_a_afiliados_reales(d):
    ids = {a["id"] for a in d["afiliados"]["afiliados"]}
    s = d["segmentos"]
    assert set(s["conteos"]) == set(s["listas"]) == set(s["definiciones"])
    for k, lst in s["listas"].items():
        assert s["conteos"][k] == len(lst) == len(set(lst)), k
        assert set(lst) <= ids, k
    assert s["conteos"]["riesgo_alto"] == d["resumen"]["por_banda"]["Riesgo alto"]
    top = s["asistentes_no_afiliados"]["top"]
    assert len(top) <= 60 and all(PAT_ID.match(x["id"]) and x["id"] not in ids for x in top)
    assert [(x["eventos"], x["asistentes"]) for x in top] == sorted(((x["eventos"], x["asistentes"]) for x in top), reverse=True)


def test_eventos_cuadran(d):
    e = d["eventos"]
    ids = [x["id"] for x in e["eventos"]]
    assert len(ids) == len(set(ids)) == e["totales"]["eventos"]
    assert sum(x["asistentes"] for x in e["eventos"]) == e["totales"]["asistentes"]
    for x in e["eventos"]:
        assert x["fecha"] <= x["fecha_fin"] and x["mes"] == x["fecha"][:7], x["id"]
        assert x["personas"] <= x["asistentes"] and x["empresas_vigentes"] <= x["empresas"], x["id"]
        assert _en_rango(x["satisfaccion"], 1, 5) and (x["satisfaccion"] is None) == (x["n_respuestas"] == 0), x["id"]
    for agrupado in ("por_linea", "por_modalidad", "por_mes"):
        assert sum(g["asistentes"] for g in e[agrupado]) == e["totales"]["asistentes"], agrupado
        assert sum(g["eventos"] for g in e[agrupado]) == e["totales"]["eventos"], agrupado
    assert sum(g["asistentes"] for g in e["por_nivel_cargo"]) == e["totales"]["asistentes"]
    assert e["totales"]["empresas_vigentes"] <= len(d["afiliados"]["afiliados"])


def test_encuestas_rangos_y_nps(d):
    e = d["encuestas"]
    for nps in [e["nps_post_evento"], *e["nps_post_afiliado_declarado"].values()]:
        assert nps["promotores"] + nps["pasivos"] + nps["detractores"] == nps["n"]
        esperado = round(100 * (nps["promotores"] - nps["detractores"]) / nps["n"], 1)
        assert nps["nps"] == esperado and -100 <= nps["nps"] <= 100
    assert sum(v["n"] for v in e["nps_post_afiliado_declarado"].values()) == e["nps_post_evento"]["n"]
    for tabla in ("por_fuente", "por_modalidad", "por_linea", "por_mes", "por_nivel_afiliado", "por_asignacion_empresa"):
        for fila in e[tabla]:
            assert fila["n"] > 0 and _en_rango(fila["satisfaccion"], 1, 5) and _en_rango(fila["nps"], -100, 100), (tabla, fila)
            assert fila["n_nps"] <= fila["n"], (tabla, fila)
    for grupo in e["aspectos"].values():
        assert all(_en_rango(v, 1, 5) for v in grupo.values())
    assert _en_rango(e["resumen"]["satisfaccion_media"], 1, 5)
    assert e["resumen"]["con_evento_2026"] <= e["resumen"]["respuestas"]


def test_encuestas_sin_texto_libre(d):
    e = d["encuestas"]
    # Los únicos textos permitidos son etiquetas de opciones cerradas: temas (casillas) e interés de afiliación.
    assert 0 < len(e["temas_solicitados"]) <= 20
    for t in e["temas_solicitados"]:
        assert set(t) == {"tema", "n"} and len(t["tema"]) <= 80 and t["n"] > 0
    assert len(e["interes_afiliarse_no_afiliados"]) <= 6
    assert all(len(k) <= 40 for k in e["interes_afiliarse_no_afiliados"])
    for n in NOMBRES:
        assert not (set(map(str.lower, _claves(d[n]))) & CLAVES_PROHIBIDAS), f"campo prohibido en {n}.json"


def test_sin_datos_personales_en_ningun_json(d):
    for n in NOMBRES:
        t = d[f"_texto_{n}"]
        assert not re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", t), f"correo electrónico en {n}.json"
        assert not re.search(r"https?://", t), f"enlace externo en {n}.json"
        assert not re.search(r"(?<!\d)\d{7,}(?!\d)", t), f"número largo (posible documento o teléfono) en {n}.json"
        assert "<" not in t.replace("\\u003c", ""), f"marcado HTML en {n}.json"


def test_meta_coincide_con_la_configuracion(d):
    meta = d["meta"]
    pesos = json.loads((RAIZ / "config" / "pesos_score.json").read_text(encoding="utf-8"))
    assert meta["score"]["pesos"] == pesos and meta["score"]["umbrales"] == pesos["bandas"]
    assert meta["version_pesos"] == pesos["version"]
    assert meta["score"]["maximo_puntos"] == sc.maximo_posible(pesos)
    assert re.match(r"^\d{4}-\d{2}-\d{2}$", meta["fecha_corte"]) and meta["generado_en"].endswith("Z")
    c = meta["cruce"]
    assert c["afiliados_vigentes"] == len(d["afiliados"]["afiliados"])
    assert abs(c["pct_con_asistencia"] + c["pct_sin_asistencia"] - 100) < 0.11
    assert abs(c["pct_con_encuesta"] + c["pct_sin_encuesta"] - 100) < 0.11
    for av in meta["avisos_calidad"]:
        assert {"codigo", "fuente", "severidad", "descripcion", "cantidad"} <= set(av) and av["severidad"] in {"alta", "media", "baja"}
    assert len({av["codigo"] for av in meta["avisos_calidad"]}) == len(meta["avisos_calidad"])
    v = meta["score"]["validacion"]
    assert 0 <= v["auc"] <= 1 and v["auc_ic95"][0] <= v["auc"] <= v["auc_ic95"][1]
    assert sum(t["n"] for t in v["tasa_salida_por_tercil"].values()) == v["n_salieron"] + v["n_vigentes"]
