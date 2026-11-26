"""Orquestación de todo el pipeline: carga, limpieza, integración, modelo relacional, score y validación."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from . import calidad, carga, config, integracion, limpieza as lp, modelo as mod
from .features import calcular_features
from .score import calcular_score
from .validacion import exigir_integridad, validar_score, verificar_modelo

log = logging.getLogger(__name__)


@dataclass
class Resultado:
    """Todas las tablas y métricas que produce una ejecución."""

    cfg: config.Configuracion
    crm_raw: pd.DataFrame
    crm: pd.DataFrame
    empresas: pd.DataFrame
    stats_crm: dict[str, int]
    eventos: pd.DataFrame
    asistencias_raw: pd.DataFrame
    asistencias: pd.DataFrame
    control_general: dict[str, Any]
    respuestas: pd.DataFrame
    respuestas_raw: dict[str, pd.DataFrame]
    afiliados: pd.DataFrame
    cruce: dict[str, Any]
    validacion: dict[str, Any]
    avisos: list[dict[str, Any]] = field(default_factory=list)
    encuesta_90_n: int = 0
    # Informes de apoyo de Zoho y control de la limpieza (v2).
    renovaciones: pd.DataFrame = field(default_factory=pd.DataFrame)
    nuevos: pd.DataFrame = field(default_factory=pd.DataFrame)
    afiliaciones_recientes: pd.DataFrame = field(default_factory=pd.DataFrame)
    oportunidades: pd.DataFrame = field(default_factory=pd.DataFrame)
    base_afiliados: pd.DataFrame = field(default_factory=pd.DataFrame)
    segmento: pd.DataFrame = field(default_factory=pd.DataFrame)
    subsectores_informe: pd.DataFrame = field(default_factory=pd.DataFrame)
    membresias_informe: pd.DataFrame = field(default_factory=pd.DataFrame)
    kam_consolidado: pd.DataFrame = field(default_factory=pd.DataFrame)
    crm_completo: pd.DataFrame = field(default_factory=pd.DataFrame)
    controles: dict[str, dict[str, Any]] = field(default_factory=dict)
    rechazos: pd.DataFrame = field(default_factory=pd.DataFrame)
    modelo: dict[str, pd.DataFrame] = field(default_factory=dict)
    integridad: dict[str, Any] = field(default_factory=dict)
    calidad: dict[str, Any] = field(default_factory=dict)


def _aviso(codigo: str, fuente: str, severidad: str, descripcion: str, cantidad: int | float | None = None) -> dict[str, Any]:
    return {"codigo": codigo, "fuente": fuente, "severidad": severidad, "descripcion": descripcion, "cantidad": cantidad}


def generar_avisos(r_crm_raw: pd.DataFrame, crm: pd.DataFrame, empresas: pd.DataFrame, stats: dict[str, int],
                   asist: pd.DataFrame, control: dict[str, Any], resp: pd.DataFrame, cruce: dict[str, Any],
                   n90: int, corte: pd.Timestamp) -> list[dict[str, Any]]:
    """Construye la lista de avisos de calidad que viaja en los metadatos."""
    av: list[dict[str, Any]] = []
    moj = int(sum(r_crm_raw[c].astype(str).str.contains(r"[｡-ﾟ]", regex=True).sum() for c in r_crm_raw.columns))
    if moj:
        av.append(_aviso("crm_tildes_danadas", "CRM", "media", "Celdas con tildes dañadas (codificación) que se repararon al cargar.", moj))
    if stats["registros_de_prueba"]:
        av.append(_aviso("crm_pruebas", "CRM", "baja", "Registros de prueba excluidos.", stats["registros_de_prueba"]))
    if stats["filas_duplicadas_descartadas"]:
        av.append(_aviso("crm_duplicados", "CRM", "media", "Códigos de empresa repetidos; se conservó un registro por empresa.", stats["filas_duplicadas_descartadas"]))
    sin_estado = int((empresas["estado"] == "Sin estado").sum())
    av.append(_aviso("crm_sin_estado", "CRM", "media", "Empresas sin estado de membresía; no se puntúan.", sin_estado))
    v = empresas[empresas["vigente"]]
    n = int((v["ejecutiva"] == "Sin asignar").sum())
    av.append(_aviso("crm_sin_ejecutiva", "CRM", "alta", "Afiliados vigentes sin ejecutiva asignada.", n))
    n = int((v["fecha_expiracion"] < corte).sum())
    av.append(_aviso("crm_vigente_vencida", "CRM", "alta", "Afiliados con estado vigente cuya fecha de expiración ya pasó.", n))
    av.append(_aviso("crm_sin_fecha_exp", "CRM", "media", "Afiliados vigentes sin fecha de expiración.", int(v["fecha_expiracion"].isna().sum())))
    av.append(_aviso("crm_nivel_sin_dato", "CRM", "media", "Afiliados vigentes sin nivel interpretable (Conectar, Crecer, Liderar).", int((v["nivel"] == "Sin dato").sum())))
    av.append(_aviso("crm_categoria_duplicada", "CRM", "baja", "Variantes de categoría como «Estándar» y «Estandar» unificadas.", int((r_crm_raw["categoria_membresia"] == "Estandar").sum())))
    inval = int(crm["fecha_afiliacion_invalida"].sum())
    if inval:
        av.append(_aviso("crm_fecha_futura", "CRM", "baja", "Fechas de afiliación posteriores al corte, descartadas.", inval))
    if control:
        av.append(_aviso("asistencia_general_formulas", "Asistencia", "alta",
                         "La hoja consolidada tiene rangos truncados y columnas sin fórmula; subestima las asistencias reales.",
                         len(control.get("columnas_con_rango_truncado", [])) + len(control.get("columnas_evento_sin_formula", []))))
    av.append(_aviso("asistencia_duplicados", "Asistencia", "baja", "Registros repetidos de la misma persona en el mismo evento, descartados.", int(asist["duplicado"].sum())))
    av.append(_aviso("asistencia_agendado", "Asistencia", "baja", "Registros en estado «agendado», que no se cuentan como asistencia.", int(asist["agendado"].sum())))
    av.append(_aviso("asistencia_no_crm", "Asistencia", "media", "Empresas con asistencia que no están en el CRM (posibles no afiliadas).", int(asist.loc[~asist["en_crm"], "empresa_id"].nunique())))
    av.append(_aviso("encuestas_sin_empresa", "Encuestas", "alta", "Respuestas sin empresa identificada.", int(resp["empresa_id"].isna().sum())))
    av.append(_aviso("encuestas_sin_evento", "Encuestas", "alta", "Respuestas que no se pudieron asignar a un evento 2026 por fecha.", int(resp["evento_id"].isna().sum())))
    av.append(_aviso("nps_muestra_pequena", "Encuestas", "alta", "El NPS post-evento se basa en muestra pequeña; no es un NPS de la asociación.", int(resp["nps_puntaje"].notna().sum())))
    av.append(_aviso("nps_90_sin_respuestas", "Encuestas", "alta", "La encuesta de 90 días no tiene respuestas todavía.", n90))
    av.append(_aviso("cruce_sin_asistencia", "Integración", "alta", "Porcentaje de afiliados vigentes sin ninguna asistencia registrada.", cruce["pct_sin_asistencia"]))
    av.append(_aviso("cruce_sin_encuesta", "Integración", "alta", "Porcentaje de afiliados vigentes sin ninguna respuesta de encuesta.", cruce["pct_sin_encuesta"]))
    return av


def _opcional(cfg: config.Configuracion, clave: str, lector: Any, columnas: list[str]) -> pd.DataFrame:
    """Carga un informe de apoyo; si el archivo no está, avisa y sigue con una tabla vacía."""
    ruta = cfg.ruta_fuente(clave)
    if not ruta.exists():
        log.warning("Informe de apoyo ausente (%s): se omite", ruta.name)
        df = pd.DataFrame(columns=columnas)
        df.attrs["control"] = {"ausente": True}
        df.attrs["rechazos"] = []
        return df
    return lector(ruta)


def _tabla_rechazos(crm: pd.DataFrame, empresas: pd.DataFrame, controles: dict[str, dict[str, Any]], partes: list[pd.DataFrame]) -> pd.DataFrame:
    """Reúne en una sola tabla todas las filas que las fuentes aportaron y el pipeline descartó, con su motivo."""
    excl = crm[~crm["id_registro"].isin(empresas["id_registro"])]
    filas: list[dict[str, Any]] = []
    for r in excl.itertuples():
        motivo = ("registro de prueba" if r.es_prueba else "código de empresa inválido" if pd.isna(r.empresa_id)
                  else "código repetido: se conservó otro registro de la misma empresa")
        filas.append({"fuente": "crm", "ubicacion": r.id_registro, "clave": r.empresa_id, "motivo": motivo,
                      "detalle": f"estado de membresía {r.estado}" if isinstance(r.estado, str) else None})
    for r in controles.get("asistencia", {}).get("filas_rechazadas", []):
        filas.append({"fuente": r["fuente"], "ubicacion": r["ubicacion"], "clave": r["clave"], "motivo": r["motivo"], "detalle": None})
    for df in partes:
        for r in df.attrs.get("rechazos", []):
            filas.append({"fuente": r["fuente"], "ubicacion": r["ubicacion"], "clave": r["clave"], "motivo": r["motivo"], "detalle": None})
    return pd.DataFrame(filas, columns=["fuente", "ubicacion", "clave", "motivo", "detalle"])


def ejecutar(cfg: config.Configuracion, estricto: bool = False) -> Resultado:
    """Corre el pipeline completo y devuelve todas las tablas intermedias y finales.

    Con ``estricto=True`` se detiene si el modelo relacional tiene errores de integridad; los huérfanos de
    severidad aviso (empresas fuera del CRM, ciudades sin homologar) se reportan pero no detienen la ejecución.
    """
    if not cfg.pesos:
        cfg.cargar_pesos()
    corte = pd.Timestamp(cfg.fecha_corte)
    controles: dict[str, dict[str, Any]] = {}

    crm_completo = carga.cargar_crm_completo(cfg.ruta_fuente("crm"))
    crm_raw = carga.cargar_crm(cfg.ruta_fuente("crm"), crudo=crm_completo)
    controles["crm"] = crm_raw.attrs["control"]
    crm = integracion.limpiar_crm(crm_raw, cfg.fecha_corte)
    empresas, stats = integracion.consolidar_empresas(crm)

    ev_raw, as_raw, control = carga.cargar_asistencia(cfg.ruta_fuente("asistencia"))
    controles["asistencia"] = control
    eventos = integracion.limpiar_eventos(ev_raw)
    asist = integracion.limpiar_asistencias(as_raw, eventos, empresas)

    pres = carga.cargar_encuesta_evento(cfg.ruta_fuente("enc_presencial"), "Presencial")
    virt = carga.cargar_encuesta_evento(cfg.ruta_fuente("enc_virtual"), "Virtual")
    post = carga.cargar_encuesta_post(cfg.ruta_fuente("enc_post"))
    enc90 = carga.cargar_encuesta_90(cfg.ruta_fuente("enc_90"))
    n90 = len(enc90)
    for k, d in (("enc_presencial", pres), ("enc_virtual", virt), ("enc_post", post), ("enc_90", enc90)):
        controles[k] = d.attrs.get("control", {})
    resp = integracion.asignar_eventos(integracion.construir_respuestas(pres, virt, post), eventos)
    resp = resp.join(empresas.set_index("empresa_id")[["nivel", "estado"]].rename(columns={"nivel": "nivel_afiliado", "estado": "estado_crm"}),
                     on="empresa_id")

    renov = carga.cargar_renovaciones(cfg.ruta_fuente("renovaciones"))
    renovaron = set(renov["empresa_id"])
    apoyo = {
        "nuevos": _opcional(cfg, "nuevos", carga.cargar_nuevos, ["empresa_id", "persona_principal_id", "mes"]),
        "afiliaciones": _opcional(cfg, "afiliaciones", carga.cargar_afiliaciones_recientes, ["empresa_id", "fecha_cierre", "ejecutiva", "categoria_membresia"]),
        "oportunidades": _opcional(cfg, "oportunidades", carga.cargar_oportunidades_ganadas, ["empresa_id", "ejecutiva"]),
        "segmento": _opcional(cfg, "segmento", carga.cargar_segmento_elite_premium, ["empresa_id", "categoria_membresia", "ejecutiva", "fecha_expiracion"]),
        "subsectores": _opcional(cfg, "subsectores", carga.cargar_subsectores, ["empresa_id", "subsector"]),
        "membresias": _opcional(cfg, "membresias", carga.cargar_informe_membresias, ["tipo_membresia", "categoria_membresia", "cantidad"]),
        "base_afiliados": _opcional(cfg, "base_afiliados", carga.cargar_base_afiliados, ["empresa_id", "ciudad", "nivel_cargo", "persona_principal_id"]),
        "kam": _opcional(cfg, "kam", carga.cargar_kam_consolidado, ["ejecutiva", "empresa_id", "estado_asistencia", "eventos_asistidos", "total_asistentes"]),
    }
    controles["renovaciones"] = renov.attrs["control"]
    for k, d in apoyo.items():
        controles[k] = d.attrs.get("control", {})

    vigentes = empresas[empresas["vigente"]].copy()
    cruce = integracion.tasas_de_cruce(vigentes, asist, resp)
    ref = pd.Series(corte, index=vigentes["empresa_id"])
    feats = calcular_features(vigentes, asist, resp, ref, renovaron)
    afiliados = calcular_score(feats, cfg.pesos)

    validacion = validar_score(empresas, asist, resp, cfg.pesos, cfg.fecha_corte, cfg.semilla)
    avisos = generar_avisos(crm_raw, crm, empresas, stats, asist, control, resp, cruce, n90, corte)
    res = Resultado(cfg, crm_raw, crm, empresas, stats, eventos, as_raw, asist, control, resp,
                    {"presencial": pres, "virtual": virt, "post": post}, afiliados, cruce, validacion, avisos, n90,
                    renovaciones=renov, nuevos=apoyo["nuevos"], afiliaciones_recientes=apoyo["afiliaciones"],
                    oportunidades=apoyo["oportunidades"], base_afiliados=apoyo["base_afiliados"], segmento=apoyo["segmento"],
                    subsectores_informe=apoyo["subsectores"], membresias_informe=apoyo["membresias"], kam_consolidado=apoyo["kam"],
                    crm_completo=crm_completo, controles=controles)
    res.rechazos = _tabla_rechazos(crm, empresas, controles, [renov, *apoyo.values()])
    res.modelo = mod.construir_modelo(res)
    res.integridad = verificar_modelo(res.modelo)
    res.calidad = calidad.auditar(res)
    res.avisos += calidad.avisos_v2(res)
    if estricto:
        exigir_integridad(res.integridad)
    log.info("Pipeline completo: %d afiliados vigentes puntuados; modelo con %d tablas (%s)", len(afiliados),
             len(res.modelo), "integridad correcta" if res.integridad["ok"] else "CON ERRORES DE INTEGRIDAD")
    return res
