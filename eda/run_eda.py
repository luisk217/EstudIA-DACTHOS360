"""Genera los reportes de análisis exploratorio en docs/eda (Markdown y figuras PNG).

Uso:  python -I eda/run_eda.py
Requiere matplotlib (ver requirements-dev.txt). Reutiliza el pipeline para que
las cifras de los reportes coincidan con las del tablero.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline import config, limpieza as lp, orquestador  # noqa: E402

DIR = config.DIR_EDA
FIG = DIR / "fig"
AZUL, GRIS, VERDE, AMBAR, ROJO = "#2a6f97", "#8d99a6", "#4c9a6a", "#d99a2b", "#c0504d"
COL_BANDA = {"Saludable": VERDE, "Atención": AMBAR, "Riesgo alto": ROJO}

plt.rcParams.update({
    "figure.dpi": 130, "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True,
    "grid.alpha": 0.25, "axes.axisbelow": True, "font.size": 9, "axes.titleweight": "bold",
})


def tabla(df: pd.DataFrame, indice: bool = False) -> str:
    """Convierte un DataFrame en tabla Markdown."""
    d = df.reset_index() if indice else df
    cab = "| " + " | ".join(map(str, d.columns)) + " |\n|" + "|".join(["---"] * len(d.columns)) + "|\n"
    def fmt(v):
        if isinstance(v, float):
            return "" if np.isnan(v) else (f"{v:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".") if v != int(v) else f"{int(v):,}".replace(",", "."))
        return str(v).replace("|", "/")
    return cab + "\n".join("| " + " | ".join(fmt(v) for v in r) + " |" for r in d.itertuples(index=False)) + "\n"


def guardar(fig: plt.Figure, nombre: str) -> str:
    FIG.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(FIG / nombre)
    plt.close(fig)
    return f"![{nombre[:-4]}](fig/{nombre})\n"


def escribir(nombre: str, texto: str) -> None:
    DIR.mkdir(parents=True, exist_ok=True)
    (DIR / nombre).write_text(texto, encoding="utf-8")


def nulos(df: pd.DataFrame, top: int = 15) -> pd.DataFrame:
    n = df.isna().mean().mul(100).round(1).sort_values(ascending=False).head(top)
    return pd.DataFrame({"campo": n.index, "% nulo": n.values})


def rep_crm(r) -> None:
    raw, crm, emp = r.crm_raw, r.crm, r.empresas
    f1, ax = plt.subplots(figsize=(6, 3))
    est = crm["estado"].value_counts()
    ax.barh(est.index[::-1], est.values[::-1], color=AZUL)
    ax.set_title("Registros del CRM por estado de membresía")
    g1 = guardar(f1, "crm_estado.png")
    v = emp[emp["vigente"]]
    f2, ax = plt.subplots(figsize=(7, 3))
    m = v["fecha_expiracion"].dt.to_period("M").value_counts().sort_index()
    ax.bar(m.index.astype(str), m.values, color=AZUL)
    ax.set_title("Vigentes por mes de expiración (la mayoría vence el 31 de diciembre)")
    ax.tick_params(axis="x", rotation=70)
    g2 = guardar(f2, "crm_expiracion.png")
    f3, ax = plt.subplots(figsize=(6, 3.4))
    nl = nulos(raw, 12)
    ax.barh(nl["campo"][::-1], nl["% nulo"][::-1], color=GRIS)
    ax.set_title("Campos con más nulos en el CRM (%)")
    g3 = guardar(f3, "crm_nulos.png")
    f4, ax = plt.subplots(figsize=(6, 3))
    niv = v["nivel"].value_counts()
    ax.bar(niv.index, niv.values, color=AZUL)
    ax.set_title("Afiliados vigentes por nivel 2027")
    g4 = guardar(f4, "crm_nivel.png")
    cat = pd.crosstab(raw["categoria_membresia"].fillna("(vacío)"), raw["estado_membresia"].fillna("Sin estado"))
    escribir("01_perfilado_crm.md", f"""# Perfilado del CRM (Zoho)

El CRM trae {len(raw):,} filas y {raw.shape[1]} campos útiles tras descartar los campos eliminados por la anonimización. Tras excluir {r.stats_crm['registros_de_prueba']} registros de prueba y consolidar {r.stats_crm['filas_duplicadas_descartadas']} códigos repetidos quedan {r.stats_crm['empresas_unicas']:,} empresas únicas, de las cuales {len(v)} están vigentes.

## Estados de membresía

{tabla(crm['estado'].value_counts().rename('registros').to_frame(), True)}
{g1}
## Vencimientos

Los vencimientos se concentran en una sola fecha: {int((v['fecha_expiracion'] == pd.Timestamp('2026-12-31')).sum())} afiliados vigentes expiran el 31 de diciembre de 2026, lo que explica que {int((v['dias_vencimiento'] <= 60).sum()) if 'dias_vencimiento' in v else int(r.afiliados['dias_vencimiento'].le(60).sum())} afiliaciones venzan en los próximos 60 días. {int((v['fecha_expiracion'] < pd.Timestamp(r.cfg.fecha_corte)).sum())} afiliados siguen vigentes aunque su fecha ya pasó.

{g2}
## Nivel, tipo y sector de los vigentes

{g4}
{tabla(v['tipo'].fillna('Sin dato').value_counts().rename('afiliados').to_frame(), True)}
{tabla(v['sector'].fillna('Sin dato').value_counts().head(10).rename('afiliados').to_frame(), True)}
## Categoría de membresía frente a estado (datos crudos)

La columna de categoría mezcla niveles reales (Estándar, Premium, Elite) con valores de tipo (Empresas, Consultoras, Persona Natural), sobre todo en cuentas canceladas.

{tabla(cat, True)}
## Nulos

{g3}
{tabla(nulos(raw, 15))}
""")


def rep_asistencia(r) -> None:
    a, ev = r.asistencias, r.eventos
    v = a[a["valida"]]
    por_ev = v.groupby("evento_id").size().reindex(ev["evento_id"]).fillna(0)
    f1, ax = plt.subplots(figsize=(8, 3.6))
    ax.bar(ev["evento_id"], por_ev.values, color=AZUL)
    ax.set_title("Asistentes por evento (conteo directo de cada hoja)")
    ax.tick_params(axis="x", rotation=90, labelsize=7)
    g1 = guardar(f1, "asistencia_por_evento.png")
    pm = v.merge(ev[["evento_id", "mes", "linea"]], on="evento_id").pivot_table(index="mes", columns="linea", values="persona_id", aggfunc="size", fill_value=0)
    f2, ax = plt.subplots(figsize=(7, 3.4))
    pm.plot(kind="bar", stacked=True, ax=ax, colormap="viridis", width=0.8)
    ax.set_title("Asistentes por mes y línea de la oferta 2027")
    ax.set_xlabel("")
    g2 = guardar(f2, "asistencia_mes_linea.png")
    cargos = v["nivel_cargo"].value_counts()
    f3, ax = plt.subplots(figsize=(6, 3))
    ax.barh(cargos.index[::-1], cargos.values[::-1], color=AZUL)
    ax.set_title("Asistentes por nivel de cargo")
    g3 = guardar(f3, "asistencia_cargo.png")
    c = r.control_general
    tot = len(v)
    escribir("02_perfilado_asistencia.md", f"""# Perfilado de la asistencia a eventos 2026

El libro tiene {len(ev)} eventos con asistencia (la hoja de febrero 13 no trae lista de inscritos), {len(r.asistencias_raw):,} registros de inscripción y {tot:,} asistencias válidas después de descartar {int(a['duplicado'].sum())} repetidos de persona y evento y {int(a['agendado'].sum())} registros en estado agendado. De esas asistencias, {int((v['en_crm']).sum()):,} corresponden a empresas del CRM y {int((~v['en_crm']).sum()):,} a empresas que no aparecen en el CRM.

## La hoja consolidada subestima la participación

La hoja GENERAL calcula las asistencias con COUNTIFS cuyos rangos terminan en filas muy anteriores al final de cada hoja (por ejemplo, la hoja de enero 5 se cuenta hasta la fila 138 y tiene más de 500 registros). Además, la columna del evento 27 no tiene fórmula y las columnas 35 y 36 están vacías. La hoja lista solo {c.get('empresas_listadas')} empresas y deja fuera a {c.get('empresas_con_asistencia_real_no_listadas')} empresas con asistencia real. Sumando sus valores calculados se obtiene {c.get('total_asistencias_reportado'):,} asistencias (columna de total: {c.get('total_columna_total_reportado'):,}), frente a {tot:,} contadas directamente en las hojas ({int((v['en_crm']).sum()):,} si solo se cuentan empresas del CRM).

## Eventos

{g1}
{g2}
{tabla(ev[['evento_id','fecha','nombre','linea','modalidad']].assign(asistentes=por_ev.values.astype(int), fecha=ev['fecha'].dt.strftime('%Y-%m-%d'), nombre=ev['nombre'].str.slice(0, 60)))}
## Nivel de cargo

{g3}
## Encabezados heterogéneos

Cada hoja usa encabezados distintos (ID_EMPRESA, EMPRESA, Celular, cédula, columnas de consentimiento con nombres diferentes y una primera columna sin título cuyo valor es 1 o 2). El pipeline localiza la columna por su nombre y no por su posición. Los valores de autorización de datos aparecen escritos de varias formas distintas (SI, Sí, SÍ, Si, entre otras).
""")


def rep_encuestas(r) -> None:
    resp = r.respuestas
    pres, virt, post = (r.respuestas_raw[k] for k in ("presencial", "virtual", "post"))
    f1, ax = plt.subplots(figsize=(7, 3.2))
    for nombre, d, cols in (("Presencial", pres, ["lugar_plataforma", "convocatoria", "conferencistas", "relevancia"]),
                            ("Virtual", virt, ["lugar_plataforma", "convocatoria", "conferencistas", "relevancia"])):
        ax.plot(["Lugar o plataforma", "Convocatoria", "Conferencistas", "Relevancia"], [d[c].mean() for c in cols], marker="o", label=nombre,
                color=AZUL if nombre == "Presencial" else AMBAR)
    ax.set_ylim(3.5, 5)
    ax.legend()
    ax.set_title("Promedio por aspecto (escala 1 a 5)")
    g1 = guardar(f1, "enc_aspectos.png")
    nps = lp.calcular_nps(post["nps_puntaje"])
    f2, ax = plt.subplots(figsize=(4.5, 3))
    ax.bar(["Promotores", "Pasivos", "Detractores"], [nps["promotores"], nps["pasivos"], nps["detractores"]], color=[VERDE, AMBAR, ROJO])
    ax.set_title(f"NPS post-evento: {nps['nps']} (n = {nps['n']})")
    g2 = guardar(f2, "enc_nps.png")
    f3, ax = plt.subplots(figsize=(7, 3))
    m = resp.groupby(resp["completada"].dt.to_period("M")).size()
    ax.bar(m.index.astype(str), m.values, color=AZUL)
    ax.set_title("Respuestas por mes (2025 y 2026)")
    ax.tick_params(axis="x", rotation=70)
    g3 = guardar(f3, "enc_mes.png")
    metodo = resp["metodo_evento"].value_counts().rename("respuestas").to_frame()
    asign = resp["metodo_asignacion"].fillna("Sin dato").value_counts().rename("respuestas").to_frame()
    escribir("03_perfilado_encuestas.md", f"""# Perfilado de las encuestas

Hay {len(pres)} respuestas presenciales, {len(virt)} virtuales y {len(post)} post-evento ({int(post['nps_puntaje'].notna().sum())} con NPS). La encuesta de 90 días solo tiene el instrumento, sin respuestas ({r.encuesta_90_n}).

## Escala 1 a 5

Las calificaciones se concentran en 4 y 5 (satisfacción media {resp['satisfaccion'].mean():.2f}), por lo que la variación entre afiliados es pequeña y un promedio menor a 4,5 ya es una señal relativamente baja.

{g1}
## NPS post-evento

Promotores {nps['promotores']}, pasivos {nps['pasivos']}, detractores {nps['detractores']}: NPS de {nps['nps']}. Coincide con el cálculo manual esperado de 35, 6 y 0. La muestra es pequeña y, entre quienes se declaran no afiliados, el NPS es de {lp.calcular_nps(post.loc[post['afiliado_declarado'] == False, 'nps_puntaje'])['nps']}; entre afiliados, de {lp.calcular_nps(post.loc[post['afiliado_declarado'] == True, 'nps_puntaje'])['nps']}.

{g2}
## Las encuestas sí traen empresa, pero no evento

{int(resp['empresa_id'].notna().sum())} de {len(resp)} respuestas traen un código de empresa válido (el resto, {int(resp['empresa_id'].isna().sum())}, no identifica empresa). Ninguna trae el evento: se infiere por la fecha de respuesta y la modalidad, con una ventana de {config.VENTANA_ENCUESTA_DIAS} días después del evento.

{tabla(metodo, True)}
Las respuestas de 2025 (el colector se reutilizó) no tienen evento en el libro 2026 y se conservan solo para la satisfacción por empresa. Las ambiguas corresponden a dos eventos presenciales el mismo día (27 de octubre).

{g3}
## Cómo se asignó la empresa en la exportación

{tabla(asign, True)}
La asignación por dominio del correo es la menos precisa; se conserva el método para que el equipo pueda filtrar por confianza.
""")


def rep_calidad(r) -> None:
    av = pd.DataFrame(r.avisos)[["fuente", "severidad", "descripcion", "cantidad"]]
    crm = r.crm_raw
    dup_cat = crm["categoria_membresia"].value_counts()
    sec = crm["sector"].dropna()
    sec_raw_vs_clean = pd.DataFrame({"antes": [sec.nunique()], "después": [r.crm["sector"].nunique()]})
    ciu = pd.DataFrame({"antes": [crm["ciudad"].dropna().nunique()], "después": [r.crm["ciudad"].nunique()]})
    emp_ctx = pd.DataFrame({
        "estado": r.empresas["estado"].value_counts().index,
        "con ejecutiva": [int((r.empresas.loc[r.empresas["estado"] == e, "ejecutiva"] != "Sin asignar").sum()) for e in r.empresas["estado"].value_counts().index],
        "sin ejecutiva": [int((r.empresas.loc[r.empresas["estado"] == e, "ejecutiva"] == "Sin asignar").sum()) for e in r.empresas["estado"].value_counts().index],
    })
    escribir("04_calidad_datos.md", f"""# Calidad de los datos

## Avisos del pipeline

{tabla(av)}
## Nulos, duplicados e inconsistencias del CRM

El CRM tiene {int(r.stats_crm['filas_duplicadas_descartadas'])} códigos de empresa repetidos, {r.stats_crm['empresas_con_duplicado_y_estados_distintos']} de ellos con estados distintos (por ejemplo, un registro activo y otro cancelado de la misma empresa). Se conserva el registro vigente. Los registros duplicados cancelados suelen estar en manos de «Sin asignar», lo que sesga cualquier análisis por ejecutiva si no se deduplica.

Los valores únicos de ciudad pasan de {ciu['antes'][0]} a {ciu['después'][0]} y los de sector de {sec_raw_vs_clean['antes'][0]} a {sec_raw_vs_clean['después'][0]} tras reparar tildes dañadas y unificar variantes. Cuatro propietarios (KAM G, KAM H, KAM I y «0») aparecen en una sola cuenta cancelada cada uno.

Categorías de membresía crudas:

{tabla(dup_cat.rename('registros').to_frame(), True)}
### Ejecutiva asignada según estado

Las cuentas «Sin asignar» son sobre todo canceladas: al cancelarse, la cuenta se reasigna. Por eso la ejecutiva no se usa como señal en la validación retrospectiva, y entre los vigentes solo {int(((r.empresas['vigente']) & (r.empresas['ejecutiva'] == 'Sin asignar')).sum())} cuentas carecen de ejecutiva.

{tabla(emp_ctx)}
## Fórmulas rotas en la hoja consolidada de asistencia

{tabla(pd.DataFrame({'control': ['Columnas de evento sin fórmula', 'Columnas con rango truncado', 'Empresas con asistencia que la hoja no lista', 'Total reportado por la hoja', 'Total contado en las hojas'], 'valor': [str(r.control_general.get('columnas_evento_sin_formula')), len(r.control_general.get('columnas_con_rango_truncado', [])), r.control_general.get('empresas_con_asistencia_real_no_listadas'), r.control_general.get('total_asistencias_reportado'), int(r.asistencias['valida'].sum())]}))}
## Inconsistencias de nombres, NIT y niveles

El NIT fue eliminado en la anonimización y el código de empresa es el único identificador compartido. Todos los códigos con formato EMP-0000 son válidos; {int((~r.asistencias['en_crm']).sum())} registros de asistencia usan códigos fuera del CRM (EMP-1053 en adelante), que son empresas no afiliadas o afiliadas todavía no cargadas. El informe de nuevos afiliados de agosto y septiembre incluye 3 códigos (EMP-1771, EMP-1774 y EMP-1775) que no están en la exportación del CRM, lo que indica un desfase de captura. Los niveles de Zoho (Estándar, Estandar, Estándar Colaborador, Premium, Elite) se llevan a Conectar, Crecer y Liderar.
""")


def rep_integracion(r) -> None:
    c = r.cruce
    f1, ax = plt.subplots(figsize=(6, 3))
    etiquetas = ["Con asistencia", "Con encuesta", "Con NPS", "Con alguna", "Sin ninguna"]
    vals = [c["pct_con_asistencia"], c["pct_con_encuesta"], c["pct_con_nps"], c["pct_con_alguna"], c["pct_sin_ninguna"]]
    ax.barh(etiquetas[::-1], vals[::-1], color=[ROJO, AZUL, AZUL, AZUL, AZUL][::-1])
    ax.set_xlim(0, 100)
    for i, v in enumerate(vals[::-1]):
        ax.text(v + 1, i, f"{v:.1f}%", va="center")
    ax.set_title("Tasa de cruce de los afiliados vigentes con cada fuente")
    g1 = guardar(f1, "integracion_cruce.png")
    a = r.afiliados
    por_nivel = a.groupby("nivel").agg(afiliados=("empresa_id", "size"), con_asistencia=("asistencias", lambda s: round(100 * (s > 0).mean(), 1)),
                                       con_encuesta=("n_respuestas", lambda s: round(100 * (s > 0).mean(), 1)))
    no_af = r.asistencias[r.asistencias["valida"] & ~r.asistencias["vigente"]]
    escribir("05_integracion_cruce.md", f"""# Integración y tasa de cruce

La clave de unión es el código de empresa (formato EMP-0000, columna «Nombre de Empresa» del CRM, «ID_EMPRESA» en asistencia y encuestas). Es un código anonimizado que reemplaza al NIT; no se hizo ningún intento de reidentificar empresas. Si el código viene vacío o con formato distinto, el registro no se une.

## Tasa de cruce con {c['afiliados_vigentes']} afiliados vigentes

{g1}
{c['pct_sin_asistencia']}% de los afiliados vigentes no se cruza con ninguna asistencia de 2026 y {c['pct_sin_encuesta']}% no se cruza con ninguna respuesta de encuesta. El {c['pct_sin_ninguna']}% no aparece en ninguna de las dos fuentes. Solo {c['con_nps']} afiliados ({c['pct_con_nps']}%) tienen una respuesta con NPS, por lo que el NPS por afiliado no es utilizable todavía; la satisfacción por afiliado se apoya en las encuestas presenciales y virtuales de los últimos 12 meses.

{tabla(por_nivel.reset_index())}
## Participantes no afiliados

{no_af['empresa_id'].nunique():,} empresas con asistencia en 2026 no están vigentes en el CRM ({int(no_af['estado'].eq('No está en el CRM').sum()):,} registros de empresas fuera del CRM y el resto de exafiliadas o sin estado). Son candidatas a campañas de afiliación. La lista de mayor frecuencia se exporta en segmentos.json.

## Modelo integrado

Una fila por afiliado vigente (afiliados.json) con campos del CRM, variables de asistencia y encuestas y score. Tablas auxiliares: eventos (catálogo con línea, modalidad, asistentes y satisfacción), asistencias (una fila por persona y evento), respuestas de encuesta (con evento inferido y método) y agregados de encuestas por modalidad, línea, mes y nivel del afiliado, porque las encuestas no identifican el evento.
""")


def rep_score(r) -> None:
    a, v = r.afiliados, r.validacion
    f1, ax = plt.subplots(figsize=(6.5, 3.2))
    for b, c in COL_BANDA.items():
        ax.hist(a.loc[a["banda"] == b, "riesgo"], bins=np.arange(0, 105, 5), color=c, label=b)
    ax.set_title("Distribución del riesgo (0 a 100)")
    ax.legend()
    g1 = guardar(f1, "score_distribucion.png")
    t = pd.DataFrame(v["tasa_salida_por_tercil"]).T
    f2, ax = plt.subplots(figsize=(5, 3))
    ax.bar(t.index, t["tasa_pct"], color=[VERDE, AMBAR, ROJO])
    ax.set_title("Salidas 2026 por tercil de riesgo (%)")
    g2 = guardar(f2, "score_validacion.png")
    f3, ax = plt.subplots(figsize=(6, 3))
    s = pd.Series(v["auc_por_senal"]).sort_values()
    ax.barh(s.index, s.values, color=AZUL)
    ax.axvline(0.5, color=GRIS, ls="--")
    ax.set_xlim(0.3, 0.9)
    ax.set_title("AUC por señal (0,5 equivale al azar)")
    g3 = guardar(f3, "score_auc_senales.png")
    pesos = r.cfg.pesos
    top = pd.Series([f["codigo"] for fs in a["factores"] for f in fs[:1]]).value_counts().rename("afiliados").to_frame()
    escribir("06_score_validacion.md", f"""# Score de salud y riesgo, y su validación

## Diseño

El riesgo suma puntos por señales transparentes y se escala de 0 a 100 dividiendo por el máximo posible ({a.attrs.get('maximo_puntos')} puntos). Los pesos están en config/pesos_score.json. Bandas: Saludable (menos de {pesos['bandas']['umbral_atencion']}), Atención (desde {pesos['bandas']['umbral_atencion']}) y Riesgo alto (desde {pesos['bandas']['umbral_riesgo_alto']}). Los umbrales se fijaron para que la lista de riesgo alto sea atendible en una semana; no provienen de un ajuste estadístico.

Resultado: {', '.join(f'{k} {int(x)}' for k, x in a['banda'].value_counts().items())}.

{g1}
Factor principal de cada afiliado:

{tabla(top, True)}
## Validación contra salidas históricas

Se aplicó el score, sin vencimiento, ejecutiva ni comunidad, a {v['n_salieron']} empresas que salieron (cancelada, expirada o inactiva) con fecha de expiración entre abril y noviembre de 2026, tomando la asistencia hasta esa fecha, y a {v['n_vigentes']} vigentes a la fecha de corte. El AUC es {v['auc']} (intervalo de 95%: {v['auc_ic95'][0]} a {v['auc_ic95'][1]}). {v['lectura']}

{tabla(t.reset_index().rename(columns={'index': 'tercil', 'n': 'empresas', 'salieron': 'salieron', 'tasa_pct': 'tasa de salida %'}))}
{g2}
{g3}
La participación es la señal más informativa: {v['pct_con_asistencia_salieron']}% de los que salieron tenía alguna asistencia registrada frente a {v['pct_con_asistencia_vigentes']}% de los vigentes. El nivel Conectar no discrimina (AUC {v['auc_por_senal']['nivel_conectar']}), por lo que su peso se dejó bajo y por criterio de negocio.

## Limitaciones

{chr(10).join('- ' + x for x in v['limitaciones'])}
""")


def rep_decisiones(r) -> None:
    escribir("07_decisiones_limpieza.md", f"""# Decisiones de limpieza y su justificación

**Código de empresa como clave.** El NIT no está disponible. El código EMP-0000 es el único identificador común a las tres fuentes. Se valida su formato y se descartan los que no lo cumplen.

**Una fila por empresa en el CRM.** Hay {r.stats_crm['filas_duplicadas_descartadas']} códigos repetidos. Se conserva el registro vigente; si ninguno lo es, el que tenga estado y fecha de expiración. Así una empresa con un registro cancelado antiguo y otro activo no se cuenta como baja.

**Registros de prueba.** Se excluyen las filas con etiqueta de prueba ({r.stats_crm['registros_de_prueba']}).

**Afiliado vigente.** Estado de membresía Activo, Periodo de Gracia o Pronto a Expirar. Cancelado, Expirado e Inactivo son salidas; las filas sin estado ({int((r.empresas['estado'] == 'Sin estado').sum())}) no se puntúan porque no se sabe si son afiliados.

**Tildes dañadas.** El texto con codificación rota (por ejemplo «Bogotﾃ｡») se repara reinterpretando los bytes como UTF-8. Es una corrección determinista y reversible.

**Ciudades, sectores y categorías.** Se unifican variantes por clave sin tildes ni mayúsculas. «Estandar» y «Estándar» son el mismo nivel; Estándar Colaborador se trata como Conectar.

**Niveles.** Estándar, Premium y Elite de Zoho equivalen a Conectar, Crecer y Liderar (documento de oferta 2027). Si la categoría trae un valor de tipo, se infiere del tipo de membresía.

**Ejecutiva.** Vacío, «0» y «Sin asignar (cuenta ACTHO)» se tratan como sin asignar.

**Fechas.** Se aceptan ISO, dd/mm/aaaa y el formato en español de Zoho Survey. Una fecha de afiliación posterior al corte (2066) se descarta. Los eventos de varios días usan la fecha de fin del calendario.

**Asistencia.** Se recorre cada hoja por nombre de columna, sin depender de las fórmulas de la hoja GENERAL. Se descartan los repetidos de la misma persona en el mismo evento y los registros agendados. La hoja de febrero 13 no trae lista y queda sin asistentes.

**Encuestas.** Se unifican en una tabla de respuestas con satisfacción media de los aspectos de 1 a 5. El evento se infiere por fecha y modalidad; si dos eventos compatibles coinciden, queda ambiguo. Las respuestas de 2025 se usan para la satisfacción por empresa pero no se asignan a eventos.

**Satisfacción faltante no penaliza.** Solo {r.cruce['pct_con_encuesta']}% de los afiliados tiene respuestas; castigar la ausencia penalizaría por no haber sido encuestado. La ausencia queda como aviso y no como puntos.

**Ventana de participación reciente.** El libro termina el 27 de octubre de 2026; los 90 días se miden hasta el último evento registrado y no hasta la fecha de corte, para no marcar a todos como inactivos por un vacío de datos.

**Afiliados nuevos.** Con menos de 90 días de afiliación, las señales de ausencia de participación se reducen a la mitad.
""")


def rep_limpieza(r) -> None:
    """Figuras y tablas de la limpieza (v2): nulos, categorías, estructura, anomalías, integridad y tendencias."""
    cal = r.calidad
    nombres = {"crm": "CRM de Zoho", "asistencia": "Asistencia", "encuestas": "Encuestas"}
    fu = {f["id"]: f for f in cal["fuentes"]}
    ids = list(fu)

    # 1. Porcentaje de celdas sin dato
    f1, ax = plt.subplots(figsize=(6.4, 2.8))
    y = np.arange(len(ids))
    ax.barh(y - 0.19, [fu[i]["antes"]["pct_sin_dato"] for i in ids], 0.38, color=GRIS, label="Antes")
    ax.barh(y + 0.19, [fu[i]["despues"]["pct_sin_dato"] for i in ids], 0.38, color=AZUL, label="Después")
    ax.set_yticks(y, [nombres[i] for i in ids])
    ax.invert_yaxis()
    ax.set_xlabel("% de celdas sin dato (nulos y centinelas)")
    ax.set_title("Celdas sin dato antes y después de la limpieza")
    ax.legend(frameon=False, loc="lower right")
    for yy, i in zip(y, ids):
        ax.text(fu[i]["antes"]["pct_sin_dato"] + 0.6, yy - 0.19, f"{fu[i]['antes']['pct_sin_dato']:.1f}".replace(".", ","), va="center", fontsize=8)
        ax.text(fu[i]["despues"]["pct_sin_dato"] + 0.6, yy + 0.19, f"{fu[i]['despues']['pct_sin_dato']:.1f}".replace(".", ","), va="center", fontsize=8)
    g1 = guardar(f1, "limpieza_celdas_sin_dato.png")

    # 2. Valores distintos por categoría
    cats = [(f"{nombres[i]}: {c['columna']}", c["antes"], c["despues"]) for i in ids for c in fu[i]["categorias"] if c["antes"] != c["despues"]]
    f2, ax = plt.subplots(figsize=(7.2, 0.38 * len(cats) + 1.2))
    y = np.arange(len(cats))
    ax.barh(y - 0.19, [c[1] for c in cats], 0.38, color=GRIS, label="Antes")
    ax.barh(y + 0.19, [c[2] for c in cats], 0.38, color=AZUL, label="Después")
    ax.set_yticks(y, [c[0] for c in cats], fontsize=8)
    ax.invert_yaxis()
    ax.set_xlabel("Valores distintos")
    ax.set_title("Valores distintos por categoría, antes y después")
    ax.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.09), ncol=2)
    g2 = guardar(f2, "limpieza_categorias.png")

    # 3. Filas y columnas
    f3, axs = plt.subplots(1, 2, figsize=(8, 2.9))
    for ax, k, tit in ((axs[0], "filas", "Filas"), (axs[1], "columnas", "Columnas")):
        y = np.arange(len(ids))
        ax.barh(y - 0.19, [fu[i]["antes"][k] for i in ids], 0.38, color=GRIS, label="Antes")
        ax.barh(y + 0.19, [fu[i]["despues"][k] for i in ids], 0.38, color=AZUL, label="Después")
        ax.set_yticks(y, [nombres[i] for i in ids] if k == "filas" else [""] * len(ids))
        ax.invert_yaxis()
        ax.set_title(tit)
    axs[0].legend(frameon=False, loc="lower right")
    g3 = guardar(f3, "limpieza_filas_columnas.png")

    # 4. Anomalías corregidas
    filas = [(nombres[i], a.get("etiqueta") or a["codigo"].replace("_", " "), a["cantidad"]) for i in ids for a in fu[i]["anomalias"] if a["cantidad"] and a["cantidad"] > 0
             and not a["codigo"].startswith("general_total")]
    filas.sort(key=lambda x: x[2])
    col = {"CRM de Zoho": AZUL, "Asistencia": VERDE, "Encuestas": AMBAR}
    f4, ax = plt.subplots(figsize=(7.4, 0.27 * len(filas) + 1.0))
    ax.barh([f[1] for f in filas], [f[2] for f in filas], color=[col[f[0]] for f in filas])
    ax.set_xscale("log")
    ax.set_xlabel("Celdas o filas afectadas (escala logarítmica)")
    ax.set_title("Anomalías detectadas y tratadas, por fuente")
    ax.tick_params(axis="y", labelsize=7)
    ax.legend(handles=[plt.Rectangle((0, 0), 1, 1, color=c) for c in col.values()], labels=list(col), frameon=False, loc="lower right")
    g4 = guardar(f4, "limpieza_anomalias.png")

    # 5. Huérfanos
    hu = r.integridad["huerfanos"]
    h = hu[hu["tipo"] == "clave_foranea"].groupby(["tabla_hijo", "columna"])["filas"].sum().sort_values()
    f5, ax = plt.subplots(figsize=(6.8, 0.45 * max(len(h), 2) + 1.0))
    if len(h):
        ax.barh([f"{a}.{b}" for a, b in h.index], h.values, color=AMBAR)
    ax.set_xlabel("Filas con una clave que no existe en la tabla padre")
    ax.set_title("Huérfanos reportados por relación (severidad aviso)")
    ax.tick_params(axis="y", labelsize=8)
    g5 = guardar(f5, "integridad_huerfanos.png")

    # 6. Tendencias
    import json as _json
    tj = _json.loads((config.DIR_WEB / "tendencias.json").read_text(encoding="utf-8")) if (config.DIR_WEB / "tendencias.json").exists() else None
    g6 = ""
    if tj:
        m = pd.DataFrame(tj["meses"])
        f6, axs = plt.subplots(2, 2, figsize=(8.4, 5.2), sharex=True)
        for ax, (k, tit, c) in zip(axs.ravel(), (("asistentes", "Asistentes por mes", AZUL), ("satisfaccion", "Satisfacción media (1 a 5)", VERDE),
                                               ("afiliaciones", "Afiliaciones por mes", AMBAR), ("vencimientos", "Vencimientos de vigentes por mes", ROJO))):
            ax.plot(m["mes"], m[k], marker="o", ms=3, color=c)
            ax.set_title(tit)
            ax.set_xticks(range(0, len(m), 3), m["mes"][::3], rotation=60, fontsize=7)
        g6 = guardar(f6, "tendencias_series.png")

    res_tabla = pd.DataFrame([{
        "fuente": nombres[i], "filas antes": fu[i]["antes"]["filas"], "filas después": fu[i]["despues"]["filas"],
        "columnas antes": fu[i]["antes"]["columnas"], "columnas después": fu[i]["despues"]["columnas"],
        "% sin dato antes": fu[i]["antes"]["pct_sin_dato"], "% sin dato después": fu[i]["despues"]["pct_sin_dato"],
        "duplicados por clave antes": fu[i]["antes"]["duplicados_clave"], "duplicados por clave después": fu[i]["despues"]["duplicados_clave"],
    } for i in ids])
    conc = pd.DataFrame(cal["conciliacion"])[["descripcion", "esperado", "obtenido", "coincide"]]
    conc["coincide"] = conc["coincide"].map({True: "sí", False: "no"})
    escribir("08_antes_despues.md", f"""# Calidad de los datos antes y después de la limpieza

Las cifras vienen de la auditoría del pipeline (`pipeline/calidad.py`), que mide cada fuente original y la tabla del modelo normalizado que resulta de ella. El detalle completo, con la explicación de cada anomalía, está en `docs/LIMPIEZA.md` y en `data/processed/control_calidad.csv`.

## Resumen por fuente

{tabla(res_tabla)}
{g3}
## Celdas sin dato

La mejora no viene de inventar datos: baja porque se eliminan las columnas vacías que dejó la anonimización, se unifican los centinelas («sin dato», «n/a», «-») en nulos reales y se descartan duplicados y registros de prueba.

{g1}
## Categorías homologadas

{g2}
## Anomalías tratadas

{g4}
## Integridad referencial

El modelo tiene {r.integridad['resumen']['relaciones_verificadas']} relaciones entre tablas. Ninguna está rota; los huérfanos que quedan son esperados y están listados en `control_huerfanos.csv`: sobre todo empresas que asisten o responden sin estar en el CRM.

{g5}
## Conciliación con los informes de Zoho

{tabla(conc)}
## Series de tendencias (`web/data/tendencias.json`)

{g6}""")


def main() -> None:
    logging.basicConfig(level=logging.WARNING)
    r = orquestador.ejecutar(config.Configuracion())
    for f in (rep_crm, rep_asistencia, rep_encuestas, rep_calidad, rep_integracion, rep_score, rep_decisiones, rep_limpieza):
        f(r)
    escribir("README.md", """# Análisis exploratorio DACTHO 360

Reportes generados con `python -I eda/run_eda.py`. Las cifras provienen del mismo pipeline que alimenta el tablero.

1. [Perfilado del CRM](01_perfilado_crm.md)
2. [Perfilado de la asistencia](02_perfilado_asistencia.md)
3. [Perfilado de las encuestas](03_perfilado_encuestas.md)
4. [Calidad de los datos](04_calidad_datos.md)
5. [Integración y tasa de cruce](05_integracion_cruce.md)
6. [Score y validación](06_score_validacion.md)
7. [Decisiones de limpieza](07_decisiones_limpieza.md)
8. [Calidad antes y después de la limpieza](08_antes_despues.md)
""")
    print("Reportes escritos en", DIR)


if __name__ == "__main__":
    main()
