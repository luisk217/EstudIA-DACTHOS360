"""Validaciones del pipeline: integridad del modelo relacional y validación retrospectiva del score.

Primera parte: ``verificar_modelo`` comprueba columnas, tipos, claves primarias, nulos, dominios, rangos, reglas de
negocio y claves foráneas del modelo normalizado, y reporta (sin ocultarlos) los valores huérfanos.

Segunda parte: validación retrospectiva del score contra salidas históricas (vigente frente a cancelada).

Limitaciones que condicionan la lectura, y que se informan junto con el resultado:
las empresas que renovaron ya no conservan su fecha de vencimiento anterior, la
asistencia solo existe para 2026 y la fecha de salida real no está registrada
(se usa la fecha de expiración). Por eso la prueba mide asociación, no
capacidad predictiva probada.
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Any, Mapping

import numpy as np
import pandas as pd

from . import config, esquema
from . import limpieza as lp
from .features import calcular_features
from .score import calcular_score, auc_rango

log = logging.getLogger(__name__)

class IntegridadError(RuntimeError):
    """El modelo tiene errores de integridad (columnas, tipos, claves o relaciones rotas)."""


def _tipo_ok(s: pd.Series, tipo: str) -> bool:
    api = pd.api.types
    if tipo == "entero":
        return bool(api.is_integer_dtype(s))
    if tipo == "decimal":
        return bool(api.is_float_dtype(s) or api.is_integer_dtype(s))
    if tipo == "fecha":
        return bool(api.is_datetime64_any_dtype(s))
    if tipo == "booleano":
        return bool(api.is_bool_dtype(s))
    return bool(api.is_string_dtype(s) or api.is_object_dtype(s))


def _problema(codigo: str, tabla: str, columna: str | None, severidad: str, descripcion: str, cantidad: int = 1) -> dict[str, Any]:
    return {"codigo": codigo, "tabla": tabla, "columna": columna, "severidad": severidad, "descripcion": descripcion, "cantidad": int(cantidad)}


def verificar_modelo(modelo: Mapping[str, pd.DataFrame], tablas: Mapping[str, esquema.Tabla] | None = None,
                     homologacion: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Verifica el modelo relacional contra el esquema y devuelve un informe con los huérfanos listados.

    Revisa, por tabla: columnas exactas y en ``snake_case``, tipos, clave primaria (sin nulos ni repetidos), columnas
    obligatorias, valores fuera de lista o de rango y reglas de negocio; y, por cada clave foránea, cuántas filas
    apuntan a un valor que no existe en la tabla padre. Los huérfanos de severidad ``aviso`` son hallazgos esperados
    y explicados (p. ej. empresas que asisten sin estar en el CRM); los de severidad ``error`` rompen el modelo.

    Devuelve ``{"ok", "problemas", "relaciones", "huerfanos", "resumen"}``; ``relaciones`` y ``huerfanos`` son DataFrames.
    """
    tablas = tablas or esquema.ESQUEMA
    h = homologacion or config.HOMOLOGACION
    problemas: list[dict[str, Any]] = []
    relaciones: list[dict[str, Any]] = []
    huerfanos: list[dict[str, Any]] = []

    for nombre, t in tablas.items():
        df = modelo.get(nombre)
        if df is None:
            problemas.append(_problema("tabla_ausente", nombre, None, "error", "La tabla no se construyó."))
            continue
        faltan, sobran = sorted(set(t.nombres()) - set(df.columns)), sorted(set(df.columns) - set(t.nombres()))
        if faltan:
            problemas.append(_problema("columnas_faltantes", nombre, ", ".join(faltan), "error", "Faltan columnas del esquema.", len(faltan)))
        if sobran:
            problemas.append(_problema("columnas_sobrantes", nombre, ", ".join(sobran), "error", "Hay columnas que no están en el esquema.", len(sobran)))
        malas = [c for c in df.columns if not lp.es_snake_case(c)]
        if malas:
            problemas.append(_problema("nombre_no_snake_case", nombre, ", ".join(malas), "error", "Nombres que no están en snake_case sin tildes.", len(malas)))
        for c in t.columnas:
            if c.nombre not in df:
                continue
            s = df[c.nombre]
            if not _tipo_ok(s, c.tipo):
                problemas.append(_problema("tipo_incorrecto", nombre, c.nombre, "error", f"Se esperaba {c.tipo} y la columna es {s.dtype}."))
            nulos = int(s.isna().sum())
            if nulos and (not c.nulo or c.nombre in t.clave):
                problemas.append(_problema("nulos_en_columna_obligatoria", nombre, c.nombre, "error", "Hay nulos en una columna obligatoria.", nulos))
            if c.rango and s.notna().any() and c.tipo in ("entero", "decimal") and pd.api.types.is_numeric_dtype(s):
                fuera = int(((s < c.rango[0]) | (s > c.rango[1])).sum())
                if fuera:
                    problemas.append(_problema("fuera_de_rango", nombre, c.nombre, "error", f"Valores fuera del rango {c.rango[0]:g} a {c.rango[1]:g}.", fuera))
            lista = set(c.valores) if c.valores else (set(config.catalogo(h[c.dominio])) if c.dominio else None)
            if lista is not None:
                con_valor = s.dropna()
                for v, n in con_valor[~con_valor.isin(lista)].value_counts().items():
                    huerfanos.append({"tabla_hijo": nombre, "columna": c.nombre, "tabla_padre": f"catálogo {c.dominio or 'fijo'}", "valor": str(v),
                                      "filas": int(n), "severidad": "aviso", "tipo": "fuera_de_catalogo",
                                      "explicacion": "Valor que no está en el catálogo de config/homologacion.json: agregue la variante a las equivalencias."})
        dup = int(df.duplicated(list(t.clave)).sum()) if all(c in df for c in t.clave) else 0
        if dup:
            problemas.append(_problema("clave_primaria_repetida", nombre, ", ".join(t.clave), "error", "La clave primaria tiene valores repetidos.", dup))

    for nombre, t in tablas.items():
        df = modelo.get(nombre)
        if df is None:
            continue
        for c in t.columnas:
            if not c.fk or c.nombre not in df:
                continue
            padre_t, padre_c = c.fk
            padre = modelo.get(padre_t)
            if padre is None or padre_c not in padre:
                problemas.append(_problema("padre_ausente", nombre, c.nombre, "error", f"No existe {padre_t}.{padre_c}."))
                continue
            s = df[c.nombre]
            con_valor = s.dropna()
            huerf = con_valor[~con_valor.isin(set(padre[padre_c].dropna()))]
            for v, n in huerf.value_counts().items():
                huerfanos.append({"tabla_hijo": nombre, "columna": c.nombre, "tabla_padre": padre_t, "valor": str(v), "filas": int(n),
                                  "severidad": c.fk_severidad, "tipo": "clave_foranea", "explicacion": c.fk_explicacion})
            relaciones.append({
                "tabla_hijo": nombre, "columna": c.nombre, "tabla_padre": padre_t, "columna_padre": padre_c, "filas_hijo": len(df),
                "filas_nulas": int(s.isna().sum()), "filas_con_valor": len(con_valor), "filas_huerfanas": len(huerf),
                "valores_huerfanos": int(huerf.nunique()), "severidad": c.fk_severidad,
                "estado": "ok" if len(huerf) == 0 else ("huérfanos esperados" if c.fk_severidad == "aviso" else "ROTA"),
                "explicacion": c.fk_explicacion,
            })

    problemas += _reglas_de_negocio(modelo)
    rel = pd.DataFrame(relaciones)
    hu = pd.DataFrame(huerfanos, columns=["tabla_hijo", "columna", "tabla_padre", "valor", "filas", "severidad", "tipo", "explicacion"])
    n_err = sum(p["severidad"] == "error" for p in problemas) + int(((hu["severidad"] == "error")).sum())
    fk = hu["tipo"] == "clave_foranea"
    resumen = {
        "tablas": len([n for n in tablas if n in modelo]), "filas_totales": int(sum(len(modelo[n]) for n in tablas if n in modelo)),
        "relaciones_verificadas": len(rel), "relaciones_con_huerfanos": int((rel["filas_huerfanas"] > 0).sum()) if len(rel) else 0,
        "filas_huerfanas_error": int(hu.loc[(hu["severidad"] == "error") & fk, "filas"].sum()),
        "filas_huerfanas_aviso": int(hu.loc[(hu["severidad"] == "aviso") & fk, "filas"].sum()),
        "valores_fuera_de_catalogo": int(hu.loc[hu["tipo"] == "fuera_de_catalogo", "valor"].nunique()),
        "errores": n_err, "avisos": sum(p["severidad"] == "aviso" for p in problemas),
    }
    log.info("Integridad del modelo: %s", resumen)
    return {"ok": n_err == 0, "problemas": problemas, "relaciones": rel, "huerfanos": hu, "resumen": resumen}


def _reglas_de_negocio(modelo: Mapping[str, pd.DataFrame]) -> list[dict[str, Any]]:
    """Reglas que no se expresan en el esquema: coherencia entre columnas de una misma tabla."""
    out: list[dict[str, Any]] = []
    a = modelo.get("fact_asistencia")
    if a is not None and len(a):
        valida = a["es_valida"].fillna(False).astype(bool)
        coherente = valida == (~a["es_agendado"].fillna(False).astype(bool) & ~a["es_duplicado"].fillna(False).astype(bool))
        if not coherente.all():
            out.append(_problema("regla_valida_incoherente", "fact_asistencia", "es_valida", "error",
                                 "es_valida no coincide con «no agendada y no duplicada».", int((~coherente).sum())))
        v = a[valida & a["persona_id"].notna()]
        n = int(v.duplicated(["evento_id", "persona_id"]).sum())
        if n:
            out.append(_problema("regla_persona_evento_repetida", "fact_asistencia", "persona_id", "error",
                                 "Una persona cuenta más de una vez como asistencia válida en el mismo evento.", n))
    ev = modelo.get("dim_evento")
    if ev is not None and len(ev):
        n = int((ev["fecha_fin"] < ev["fecha_inicio"]).sum())
        if n:
            out.append(_problema("regla_evento_fechas", "dim_evento", "fecha_fin", "error", "Eventos que terminan antes de empezar.", n))
        n = int((ev["mes"] != ev["fecha_inicio"].dt.strftime("%Y-%m")).sum())
        if n:
            out.append(_problema("regla_evento_mes", "dim_evento", "mes", "error", "El mes no coincide con la fecha de inicio.", n))
    af = modelo.get("dim_afiliado")
    if af is not None and len(af):
        incoh = af["fecha_expiracion"] < af["fecha_afiliacion"]
        sin_marca = int((incoh & ~af["fechas_incoherentes"].fillna(False).astype(bool)).sum())
        if sin_marca:
            out.append(_problema("regla_fechas_afiliado", "dim_afiliado", "fecha_expiracion", "error", "Expiración anterior a la afiliación sin bandera.", sin_marca))
    e = modelo.get("fact_encuesta")
    if e is not None and len(e):
        esperado = e["nps_puntaje"].map(lambda p: None if pd.isna(p) else lp.clasificar_nps(p))
        n = int((esperado.fillna("-") != e["nps_categoria"].fillna("-")).sum())
        if n:
            out.append(_problema("regla_nps_categoria", "fact_encuesta", "nps_categoria", "error", "La categoría NPS no corresponde al puntaje.", n))
    return out


def resumen_para_meta(rep: Mapping[str, Any], max_huerfanos: int = 25) -> dict[str, Any]:
    """Versión compacta del informe de integridad para ``meta.json`` (solo códigos anonimizados, sin datos personales)."""
    hu = rep["huerfanos"]
    if len(hu):
        por_rel = hu.groupby(["tabla_hijo", "columna", "tipo", "severidad"]).agg(valores=("valor", "nunique"), filas=("filas", "sum")).reset_index()
        muestra = hu[hu["tipo"] == "clave_foranea"].sort_values("filas", ascending=False).head(max_huerfanos)
    else:
        por_rel, muestra = hu, hu
    rel = rep["relaciones"]
    return {
        "ok": rep["ok"], **rep["resumen"],
        "relaciones_con_huerfanos_detalle": rel[rel["filas_huerfanas"] > 0].drop(columns=["explicacion"]).to_dict("records") if len(rel) else [],
        "huerfanos_por_relacion": por_rel.to_dict("records"),
        "problemas": list(rep["problemas"]),
        "muestra_huerfanos": muestra[["tabla_hijo", "columna", "valor", "filas", "severidad"]].to_dict("records"),
    }


def exigir_integridad(rep: Mapping[str, Any]) -> None:
    """Lanza ``IntegridadError`` si el informe tiene errores (los avisos no la detienen)."""
    if not rep["ok"]:
        errores = [p for p in rep["problemas"] if p["severidad"] == "error"]
        rotas = rep["huerfanos"][rep["huerfanos"]["severidad"] == "error"]
        raise IntegridadError(f"{len(errores)} problemas de estructura y {len(rotas)} valores huérfanos de severidad error: "
                              + "; ".join(f"{p['tabla']}.{p['columna']}: {p['descripcion']}" for p in errores[:5]))


#: Factores que se excluyen porque reflejan el desenlace (ejecutiva reasignada, comunidad actual) o es circular (vencimiento).
EXCLUIDOS = ("vencimiento", "ejecutiva", "comunidad")


def validar_score(
    empresas: pd.DataFrame, asistencias: pd.DataFrame, respuestas: pd.DataFrame, pesos: Mapping[str, Any],
    corte: date, semilla: int = 2026, min_dias_cobertura: int = 90, n_bootstrap: int = 1000,
) -> dict[str, Any]:
    """Compara el score de quienes salieron en 2026 con el de los afiliados vigentes."""
    corte_ts = pd.Timestamp(corte)
    inicio_valido = pd.Timestamp(config.INICIO_COBERTURA_ASISTENCIA) + pd.Timedelta(days=min_dias_cobertura)
    salieron = empresas[
        empresas["no_vigente"] & empresas["fecha_expiracion"].notna()
        & (empresas["fecha_expiracion"] >= inicio_valido) & (empresas["fecha_expiracion"] < corte_ts)
    ]
    vigentes = empresas[empresas["vigente"]]
    pob = pd.concat([salieron.assign(salio=1), vigentes.assign(salio=0)], ignore_index=True)
    ref = pd.Series(
        np.where(pob["salio"] == 1, pob["fecha_expiracion"], corte_ts), index=pob["empresa_id"], dtype="datetime64[ns]"
    )
    feats = calcular_features(pob, asistencias, respuestas, ref)
    feats["salio"] = pob.set_index("empresa_id").loc[feats["empresa_id"], "salio"].to_numpy()
    sc = calcular_score(feats, pesos, excluir=EXCLUIDOS)

    y, s = sc["salio"].to_numpy().astype(bool), sc["riesgo"].to_numpy()
    auc = auc_rango(s, y)
    rng = np.random.default_rng(semilla)
    boots = []
    idx_pos, idx_neg = np.where(y)[0], np.where(~y)[0]
    for _ in range(n_bootstrap):
        i = np.concatenate([rng.choice(idx_pos, len(idx_pos)), rng.choice(idx_neg, len(idx_neg))])
        boots.append(auc_rango(s[i], y[i]))
    ic = (float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5)))

    # Tasa de salida por tercil de riesgo (los umbrales de banda del score completo no aplican al score reducido).
    sc["tercil"] = pd.qcut(sc["riesgo"].rank(method="first"), 3, labels=["Riesgo bajo", "Riesgo medio", "Riesgo alto"])
    por_tercil = sc.groupby("tercil", observed=True)["salio"].agg(["size", "sum"]).assign(
        tasa=lambda d: (100 * d["sum"] / d["size"]).round(1))
    univ = {
        "sin_asistencia_90d": auc_rango((sc["asistencias_90d"] == 0).astype(float), y),
        "sin_asistencia_anio": auc_rango((sc["asistencias"] == 0).astype(float), y),
        "menos_asistencias": auc_rango(-sc["asistencias"].astype(float), y),
        "menos_personas": auc_rango(-sc["personas_distintas"].astype(float), y),
        "menor_antiguedad": auc_rango(-sc["antiguedad_anios"].fillna(sc["antiguedad_anios"].median()), y),
        "nivel_conectar": auc_rango((sc["nivel"] == "Conectar").astype(float), y),
    }
    res = {
        "n_salieron": int(y.sum()), "n_vigentes": int((~y).sum()),
        "auc": round(auc, 3), "auc_ic95": [round(ic[0], 3), round(ic[1], 3)],
        "tasa_salida_por_tercil": {str(k): {"n": int(v["size"]), "salieron": int(v["sum"]), "tasa_pct": float(v["tasa"])}
                                   for k, v in por_tercil.iterrows()},
        "auc_por_senal": {k: round(float(v), 3) for k, v in univ.items()},
        "pct_con_asistencia_salieron": round(100 * float((sc.loc[y, "asistencias"] > 0).mean()), 1),
        "pct_con_asistencia_vigentes": round(100 * float((sc.loc[~y, "asistencias"] > 0).mean()), 1),
        "factores_excluidos": list(EXCLUIDOS),
        "lectura": _lectura(auc, ic),
        "limitaciones": [
            "Los afiliados que renovaron pierden su fecha de vencimiento anterior, por lo que no se pueden usar como casos negativos del mismo momento.",
            "La asistencia solo existe desde enero de 2026; se excluyen salidas anteriores a abril de 2026 por cobertura insuficiente.",
            "No se conoce la fecha real de cancelación; se usa la fecha de expiración como referencia.",
            "Los salientes son pocos, por lo que el resultado es una señal de asociación y no una garantía de predicción.",
            "Se excluyeron vencimiento, ejecutiva y comunidad: el primero es circular y los otros dos se reasignan tras la cancelación.",
        ],
    }
    log.info("Validación: AUC=%.3f IC95=%s (salieron=%d, vigentes=%d)", auc, res["auc_ic95"], res["n_salieron"], res["n_vigentes"])
    return res


def _lectura(auc: float, ic: tuple[float, float]) -> str:
    """Redacta en español la interpretación prudente del AUC y su intervalo de confianza."""
    if np.isnan(auc):
        return "No hubo casos suficientes para evaluar."
    if ic[0] <= 0.5:
        return "El score separa débilmente a quienes salieron de quienes siguen; el intervalo incluye el azar. Úselo como orientación, no como predicción."
    if auc < 0.65:
        return "El score muestra una asociación modesta con la salida; sirve para priorizar la atención, no para predecir con certeza."
    if auc < 0.75:
        return "El score muestra una asociación moderada con la salida histórica; es útil para priorizar, con las limitaciones indicadas."
    return "El score muestra una asociación clara con la salida histórica en esta muestra; conviene reconfirmarla con más historia antes de automatizar decisiones."
