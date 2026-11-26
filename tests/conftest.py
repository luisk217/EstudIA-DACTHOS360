"""Datos sintéticos pequeños compartidos por las pruebas (no se usan datos reales)."""
import json
from pathlib import Path

import pandas as pd
import pytest

RAIZ = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def pesos():
    with open(RAIZ / "config" / "pesos_score.json", encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture
def crm_sintetico():
    """Seis filas: un duplicado con estados distintos, una prueba y una sin estado."""
    return pd.DataFrame({
        "id_registro": ["R1", "R2", "R3", "R4", "R5", "R6"],
        "empresa_id": ["EMP-0001", "EMP-0001", "EMP-0002", "EMP-0003", "EMP-0004", "EMP-0005"],
        "propietario": ["KAM A", "Sin asignar (cuenta ACTHO)", "0", "KAM B", "KAM B", None],
        "ciudad": ["Bogotﾃ｡", "Bogota", "MEDELLIN", None, "Bogotá", "Cali"],
        "ciudad_facturacion": [None] * 6,
        "etiqueta": [None, None, None, "Prueba", None, None],
        "categoria_membresia": ["Estándar", "Estandar", "Premium", "Elite", "Empresas", None],
        "tipo_membresia": ["Empresa", "Corporativa Estﾃ｡ndar", "Empresa", "Empresa", "Corporativa Premium", None],
        "estado_membresia": ["Activo", "Cancelado", "Cancelado", "Activo", "Periodo de Gracia", None],
        "fecha_afiliacion": ["2020-01-10", "2020-01-10", "2066-12-20", None, "2025-06-01", None],
        "fecha_expiracion": ["2026-12-31", None, None, "2027-03-31", "2026-10-31", None],
        "miembro_desde": [None] * 6,
        "sector": ["Tecnologia", "Tecnología", "Educaciﾃｳn", None, "Servicios", None],
        "empleados": ["1 - 50", "1-50", None, None, None, None],
        "vinculado_comunidades": ["true", "false", "false", "false", "true", "false"],
        "cantidad_miembros": [None] * 6,
        "com_hr_estrategico": [None] * 6, "com_mas_que_salario": [None] * 6, "com_talento_elige": [None] * 6,
        "com_gente_crece": [None] * 6, "com_mujeres_hr": [None] * 6, "com_influenciador": [None] * 6,
    })


@pytest.fixture
def resultado_sintetico(crm_sintetico, pesos):
    """Un ``Resultado`` mínimo armado con las propias funciones del pipeline sobre datos sintéticos (sin leer archivos)."""
    from datetime import date
    from types import SimpleNamespace

    import numpy as np

    from pipeline import integracion as it
    from pipeline.features import calcular_features
    from pipeline.score import calcular_score

    corte = date(2026, 11, 25)
    crm = it.limpiar_crm(crm_sintetico, corte)
    empresas, stats = it.consolidar_empresas(crm)
    ev_raw = pd.DataFrame({
        "evento_n": [1, 2, 3], "hoja": ["A", "B", "C"], "fecha": pd.to_datetime(["2026-03-17", "2026-04-28", "2026-10-27"]),
        "nombre": ["Semana del Talento", "Taller", "Valentía"], "linea": ["Evento grande", "Anticipar", None],
        "experiencia": [None, "Actho Legislativo", None], "modalidad": ["Presencial", "Virtual", "Híbrido"],
        "fecha_fin_general": pd.to_datetime(["2026-03-20", pd.NaT, pd.NaT]),
    })
    eventos = it.limpiar_eventos(ev_raw)
    as_raw = pd.DataFrame({
        "hoja": ["A", "A", "A", "B", "B", "A"], "empresa_id": ["EMP-0001", "EMP-0001", "EMP-0002", "EMP-0004", "EMP-0900", "EMP-0001"],
        "persona_id": ["P-00001", "P-00001", "P-00002", "P-00003", "P-00001", "P-00009"],
        "nivel_cargo": ["Otro", "Otro", "Sin dato", "Dirección / Gerencia", "Otro", "Otro"],
        "costo": ["Con costo", "Con costo", None, "Sin costo", "Sin costo", "Sin costo"],
        "estado_registro": [None, None, None, None, None, "agendado "], "marca_afiliado": [1, 1, None, 1, 1, 1],
        "ciudad": ["BOGOTÁ", None, None, "Medellin", None, None], "autoriza_datos": ["SÍ ", "Si", "NO", "Sí", None, "SI"],
        "registro_ubicacion": ["Si", None, None, None, None, None],
    })
    asist = it.limpiar_asistencias(as_raw, eventos, empresas)
    pres = pd.DataFrame({
        "respuesta_id": ["EP-0001", "EP-0002"], "completada": pd.to_datetime(["2026-03-20", "2025-05-01"]), "colector": "x",
        "lugar_plataforma": [5.0, 4.0], "convocatoria": [5.0, 4.0], "conferencistas": [5.0, 3.0], "relevancia": [4.0, 4.0],
        "persona_id": ["P-00001", None], "empresa_id": ["EMP-0001", None], "ciudad": ["Bogotá", None],
        "metodo_asignacion": ["Correo exacto", "Sin datos de empresa"], "fuente": "encuesta_presencial", "modalidad": "Presencial",
    })
    virt = pres.iloc[:0].assign(fuente="encuesta_virtual", modalidad="Virtual")
    post = pd.DataFrame({
        "respuesta_id": ["PE-0001"], "completada": pd.to_datetime(["2026-10-28"]), "persona_id": ["P-00003"], "empresa_id": ["EMP-0004"],
        "ciudad": ["Medellín"], "afiliado_declarado": [True], "nps_puntaje": [10.0], "satisfaccion_global": [5.0], "asp_expositor": [5.0],
        "asp_contenido": [4.0], "asp_recepcion": [np.nan], "asp_espacio": [5.0], "asp_alimentacion": [np.nan], "asp_tiempo": [4.0],
        "temas_marcados": [["IA", "Nómina"]], "metodo_asignacion": ["Correo exacto"], "fuente": "encuesta_post", "modalidad": "Presencial",
    })
    resp = it.asignar_eventos(it.construir_respuestas(pres, virt, post), eventos)
    vig = empresas[empresas["vigente"]].copy()
    ref = pd.Series(pd.Timestamp(corte), index=vig["empresa_id"])
    afiliados = calcular_score(calcular_features(vig, asist, resp, ref, {"EMP-0001"}), pesos)
    return SimpleNamespace(
        cfg=SimpleNamespace(fecha_corte=corte), empresas=empresas, eventos=eventos, asistencias=asist, respuestas=resp,
        respuestas_raw={"presencial": pres, "virtual": virt, "post": post}, afiliados=afiliados, stats_crm=stats,
        renovaciones=pd.DataFrame({"empresa_id": ["EMP-0001"], "fecha_expiracion": pd.to_datetime(["2027-09-30"]),
                                   "mes_factura": pd.to_datetime(["2026-09-01"]), "ejecutiva": ["KAM A"]}),
        nuevos=pd.DataFrame({"empresa_id": ["EMP-0004", "EMP-1771"], "persona_principal_id": ["P-03265", "P-03266"],
                             "mes": pd.to_datetime(["2026-08-01", "2026-09-01"])}),
        afiliaciones_recientes=pd.DataFrame({"empresa_id": ["EMP-0004"], "fecha_cierre": pd.to_datetime(["2026-08-26"]),
                                             "ejecutiva": ["KAM B"], "categoria_membresia": ["Estándar"]}),
        oportunidades=pd.DataFrame({"empresa_id": ["EMP-0001"], "ejecutiva": ["KAM A"]}),
        base_afiliados=pd.DataFrame({"empresa_id": ["EMP-0001"], "ciudad": ["Bogotá"], "nivel_cargo": ["Otro"], "persona_principal_id": ["P-02901"]}),
    )
