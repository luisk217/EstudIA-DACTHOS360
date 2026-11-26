"""Carga de las fuentes crudas (Excel) a tablas ``pandas`` sin transformar su contenido de negocio.

Los archivos se tratan como datos no confiables: solo se leen valores, nunca
se evalúa ni ejecuta nada de lo que contienen. Cada lector deja en
``df.attrs["control"]`` un resumen de lo que encontró (filas leídas, vacías,
totales, encabezados repetidos y filas sin código) para que nada se descarte
en silencio, y en ``df.attrs["rechazos"]`` el detalle de las filas descartadas.
"""
from __future__ import annotations

import logging
import re
import warnings
from pathlib import Path
from typing import Any

import openpyxl
import pandas as pd

from . import config
from . import limpieza as lp

log = logging.getLogger(__name__)
warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")

_RE_EMP = re.compile(r"^EMP-\d+$")
_RE_PERSONA = re.compile(r"^P-\d+$")
_RE_ERROR_EXCEL = re.compile(r"^#(REF|VALUE|DIV/0|N/A|NAME|NUM|NULL)", re.IGNORECASE)

COLUMNAS_CRM: dict[str, str] = {
    "ID de registro [anonimizado]": "id_registro",
    "Propietario de Empresa [anonimizado]": "propietario",
    "Nombre de Empresa [anonimizado]": "empresa_id",
    "Tipo de Empresa": "naturaleza",
    "Ciudad de facturación": "ciudad_facturacion",
    "País de facturación": "pais",
    "Departamento": "departamento",
    "Ciudad": "ciudad",
    "Etiqueta": "etiqueta",
    "Región": "region",
    "Tipo de Compañía": "tipo_compania",
    "Estado": "estado_registro",
    "Fecha de Afiliación": "fecha_afiliacion",
    "Independiente": "independiente",
    "Cantidad de Empleados": "empleados",
    "Sector Económico": "sector",
    "Subsector Económico [anonimizado]": "subsector",
    "Tipo de Consultora": "tipo_consultora",
    "% de Mujeres en la Compañía": "pct_mujeres",
    "Tipo de Membresía": "tipo_membresia",
    "Categoría de Membresía": "categoria_membresia",
    "Fecha de Expiración Afiliación": "fecha_expiracion",
    "Estado de la Membresía": "estado_membresia",
    "HR Estratégico": "com_hr_estrategico",
    "Mas que un Salario": "com_mas_que_salario",
    "Talento que Elige": "com_talento_elige",
    "Gente que Crece": "com_gente_crece",
    "Mujeres HR": "com_mujeres_hr",
    "Influenciador": "com_influenciador",
    "Tamaño de la Empresa": "tamano",
    "Miembro Desde el": "miembro_desde",
    "Vinculado a Comunidades": "vinculado_comunidades",
    "Cantidad Miembros": "cantidad_miembros",
}


def _control_filas() -> dict[str, int]:
    return {"filas_leidas": 0, "filas_vacias": 0, "filas_total": 0, "filas_encabezado_repetido": 0, "filas_sin_codigo": 0, "filas_validas": 0}


# ---------------------------------------------------------------------------
# CRM
# ---------------------------------------------------------------------------

def cargar_crm_completo(ruta: Path) -> pd.DataFrame:
    """Lee la exportación de Zoho CRM con todas sus columnas, tal cual (sirve para medir la calidad antes de limpiar)."""
    return pd.read_excel(ruta, dtype=str)


def cargar_crm(ruta: Path, crudo: pd.DataFrame | None = None) -> pd.DataFrame:
    """Lee la exportación de Zoho CRM y conserva solo las columnas útiles, ya renombradas.

    Descarta las filas vacías, los totales y los encabezados repetidos (y los deja registrados en
    ``attrs["control"]`` y ``attrs["rechazos"]``). Las filas con un código de empresa inválido se
    conservan aquí y las excluye ``integracion.consolidar_empresas``, que las cuenta.
    """
    crudo = cargar_crm_completo(ruta) if crudo is None else crudo
    df = crudo[[c for c in COLUMNAS_CRM if c in crudo.columns]].rename(columns=COLUMNAS_CRM)
    ctl, rechazos, mant = _control_filas(), [], []
    patron_emp = re.compile(r"^EMP-\d+$", re.IGNORECASE)
    for i, f in enumerate(df.itertuples(index=False)):
        ctl["filas_leidas"] += 1
        clase = lp.clasificar_fila(f, getattr(f, "empresa_id"), patron_emp, ("Nombre de Empresa", "ID de registro"))
        if clase == "vacia":
            ctl["filas_vacias"] += 1
        elif clase in ("total", "encabezado"):
            ctl["filas_total" if clase == "total" else "filas_encabezado_repetido"] += 1
            rechazos.append({"fuente": "crm", "ubicacion": f"fila {i + 2}", "clave": None, "motivo": "total" if clase == "total" else "encabezado repetido"})
        else:
            ctl["filas_validas" if clase == "valida" else "filas_sin_codigo"] += 1
            mant.append(i)
    out = df.iloc[mant].reset_index(drop=True)
    out.attrs["control"] = {**ctl, "columnas_crudas": int(crudo.shape[1]), "columnas_utiles": int(out.shape[1])}
    out.attrs["rechazos"] = rechazos
    log.info("CRM cargado: %d filas, %d columnas útiles (de %d)", out.shape[0], out.shape[1], crudo.shape[1])
    return out


# ---------------------------------------------------------------------------
# Asistencia a eventos
# ---------------------------------------------------------------------------

def _fila_encabezado(filas: list[tuple], max_busqueda: int = 6) -> int | None:
    """Índice de la fila que contiene el encabezado ``ID_EMPRESA`` (busca en las primeras filas)."""
    for i, fila in enumerate(filas[:max_busqueda]):
        if any(isinstance(c, str) and "ID_EMPRESA" in c.upper() for c in fila):
            return i
    return None


def _titulo_hoja(filas: list[tuple], fila_enc: int) -> str | None:
    """Primer texto no vacío por encima del encabezado (título de la hoja)."""
    for fila in filas[:fila_enc]:
        for c in fila:
            if isinstance(c, str) and c.strip():
                return c.strip()
    return None


def _buscar_col(encabezados: list[str], *patrones: str) -> int | None:
    """Posición de la primera columna cuyo encabezado contiene alguno de los patrones."""
    for i, h in enumerate(encabezados):
        if any(p in h for p in patrones):
            return i
    return None


def _fechas_general(wb: Any) -> dict[int, tuple[pd.Timestamp, pd.Timestamp]]:
    """Fechas (inicio, fin) de cada evento según la hoja GENERAL, que escribe los eventos de varios días como rango."""
    ws = next((w for w in wb.worksheets if w.title.upper().startswith("GENERAL")), None)
    if ws is None:
        return {}
    filas = list(ws.iter_rows(values_only=True))
    i_num = next((i for i, f in enumerate(filas[:8]) if f and f[0] and "ID_EMPRESA" in str(f[0]).upper()), None)
    i_fecha = next((i for i, f in enumerate(filas[:8]) if len(f) > 1 and isinstance(f[1], str) and f[1].strip().upper() == "FECHA"), None)
    if i_num is None or i_fecha is None:
        return {}
    out: dict[int, tuple[pd.Timestamp, pd.Timestamp]] = {}
    for j, n in enumerate(filas[i_num]):
        num = lp.a_entero(n) if j >= 2 else None
        if num is not None and j < len(filas[i_fecha]):
            out[num] = lp.parsear_rango_fechas(filas[i_fecha][j])
    return out


def cargar_asistencia(ruta: Path) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """Lee el libro de asistencia 2026 (una hoja por evento, con estructuras distintas entre hojas).

    Devuelve ``(eventos, asistencias_crudas, control_general)``. Las hojas
    ``GENERAL`` y ``HOMOLOGACION`` no se tratan como eventos; la primera solo se
    usa para auditar sus fórmulas y para leer las fechas de los eventos de varios
    días, y la segunda para catalogar eventos. Las columnas se ubican por el texto
    del encabezado (no por posición), de modo que las 33 hojas con listas de campos
    distintas se unifican en una sola tabla. Las filas vacías, los totales, los
    encabezados repetidos y las filas sin código de empresa se cuentan en
    ``control_general["lectura"]`` y las descartadas se listan en
    ``control_general["filas_rechazadas"]``.
    """
    wb = openpyxl.load_workbook(ruta, data_only=True)
    hoja_hom = next(ws for ws in wb.worksheets if ws.title.upper().startswith("HOMOLOG"))
    filas_h = list(hoja_hom.iter_rows(values_only=True))
    ini = next(i for i, f in enumerate(filas_h) if f and f[0] and "evento" in str(f[0]).lower() and i > 0)
    fechas_gen = _fechas_general(wb)
    eventos = []
    for f in filas_h[ini + 1:]:
        if f[0] is None or not str(f[0]).strip().isdigit():
            continue
        n = int(f[0])
        ini_g, fin_g = fechas_gen.get(n, (pd.NaT, pd.NaT))
        eventos.append({
            "evento_n": n, "hoja": str(f[1]).strip(), "fecha": lp.parsear_fecha(f[2]),
            "nombre": str(f[3]).strip(), "linea": lp.limpiar_texto(f[4]), "experiencia": lp.limpiar_texto(f[5]),
            "modalidad": lp.limpiar_texto(f[6]), "fecha_fin_general": fin_g,
        })
    df_ev = pd.DataFrame(eventos)

    registros: list[dict[str, Any]] = []
    rechazadas: list[dict[str, Any]] = []
    lectura: dict[str, dict[str, int]] = {}
    hojas_sin_encabezado: list[str] = []
    hojas_evento = {r.hoja for r in df_ev.itertuples()}
    for ws in wb.worksheets:
        if ws.title not in hojas_evento:
            continue
        filas = list(ws.iter_rows(values_only=True))
        enc = _fila_encabezado(filas)
        if enc is None:
            log.warning("Hoja sin encabezado ID_EMPRESA: %s", ws.title)
            hojas_sin_encabezado.append(ws.title)
            continue
        h = [str(c).strip().lower() if c is not None else "" for c in filas[enc]]
        i_emp = _buscar_col(h, "id_empresa")
        i_per = _buscar_col(h, "id_persona")
        i_car = _buscar_col(h, "nivel de cargo")
        i_cos = _buscar_col(h, "costo")
        i_ciu = _buscar_col(h, "ciudad")
        i_aut = _buscar_col(h, "autorizaci", "tratamiento", "protecci")
        i_ubi = _buscar_col(h, "estado de registro")
        i_est = h.index("estado") if "estado" in h else None
        ctl = _control_filas()
        for k, f in enumerate(filas[enc + 1:], start=enc + 2):
            ctl["filas_leidas"] += 1
            get = lambda i: f[i] if i is not None and i < len(f) else None  # noqa: E731
            clase = lp.clasificar_fila(f, get(i_emp), _RE_EMP, ("ID_EMPRESA", "ID_PERSONA"))
            if clase == "vacia":
                ctl["filas_vacias"] += 1
                continue
            if clase != "valida":
                ctl[{"total": "filas_total", "encabezado": "filas_encabezado_repetido", "sin_clave": "filas_sin_codigo"}[clase]] += 1
                rechazadas.append({"fuente": "asistencia", "ubicacion": f"{ws.title}, fila {k + 1}", "clave": get(i_per),
                                   "motivo": {"total": "total mezclado con datos", "encabezado": "encabezado repetido", "sin_clave": "sin código de empresa"}[clase]})
                continue
            ctl["filas_validas"] += 1
            registros.append({
                "hoja": ws.title, "empresa_id": f[i_emp].strip(), "persona_id": get(i_per),
                "nivel_cargo": get(i_car), "costo": get(i_cos), "estado_registro": get(i_est),
                "marca_afiliado": f[0] if f and isinstance(f[0], (int, float)) else None,
                "ciudad": get(i_ciu), "autoriza_datos": get(i_aut), "registro_ubicacion": get(i_ubi),
            })
        ctl["columnas"] = [c for c in h if c]
        ctl["celdas_combinadas"] = len(ws.merged_cells.ranges)
        lectura[ws.title] = ctl
    df_as = pd.DataFrame(registros)
    log.info("Asistencia cargada: %d eventos, %d registros, %d filas rechazadas", len(df_ev), len(df_as), len(rechazadas))
    control = _auditar_general(ruta, wb, df_as)
    control["lectura"] = lectura
    control["filas_rechazadas"] = rechazadas
    control["hojas_sin_encabezado"] = hojas_sin_encabezado
    control["hojas_sin_homologar"] = sorted(
        w.title for w in wb.worksheets if not w.title.upper().startswith(("GENERAL", "HOMOLOG")) and w.title not in hojas_evento)
    control["eventos_sin_hoja"] = sorted(hojas_evento - {w.title for w in wb.worksheets})
    return df_ev, df_as, control


def _auditar_general(ruta: Path, wb_valores: Any, df_as: pd.DataFrame) -> dict[str, Any]:
    """Audita la hoja consolidada GENERAL: fórmulas ausentes, rangos truncados, fila de totales y celdas con error."""
    nombre = next((ws.title for ws in wb_valores.worksheets if ws.title.upper().startswith("GENERAL")), None)
    if nombre is None:
        return {}
    wb_f = openpyxl.load_workbook(ruta, data_only=False)
    ws_f, ws_v = wb_f[nombre], wb_valores[nombre]
    filas_f = list(ws_f.iter_rows(values_only=True))
    filas_v = list(ws_v.iter_rows(values_only=True))
    fila_n = next(i for i, f in enumerate(filas_f) if f and f[0] and "ID_EMPRESA" in str(f[0]).upper())
    datos = [(f, v) for f, v in zip(filas_f[fila_n + 1:], filas_v[fila_n + 1:])
             if f[0] and _RE_EMP.match(str(f[0]).strip())]
    cols_evento = range(2, 38)
    total_cache = 0
    total_columna = 0
    sin_formula: dict[int, int] = {}
    truncadas: dict[int, int] = {}
    for f, v in datos:
        if len(v) > 41 and isinstance(v[41], (int, float)):
            total_columna += v[41]
        for j in cols_evento:
            val = v[j] if j < len(v) else None
            if isinstance(val, (int, float)):
                total_cache += val
            formula = f[j] if j < len(f) else None
            if formula is None and any(isinstance(x, str) and x.startswith("=") for x in f[2:38]):
                sin_formula[j - 1] = sin_formula.get(j - 1, 0) + 1
    # Rangos truncados: se compara el fin del rango con el tamaño real de cada hoja.
    muestra = datos[0][0] if datos else ()
    for j in cols_evento:
        formula = muestra[j] if j < len(muestra) else None
        if isinstance(formula, str):
            m = re.search(r"'([^']+)'!\$B\$(\d+):\$B\$(\d+)", formula)
            if m and m[1] in wb_valores.sheetnames:
                if df_as[df_as["hoja"] == m[1]].shape[0] > int(m[3]) - 2:
                    truncadas[j - 1] = int(m[3])
    empresas = {str(f[0]).strip() for f, _ in datos}
    # Fila de totales mezclada con los datos: sus SUM() deberían cubrir todas las empresas listadas.
    ultima_fila_datos = fila_n + 1 + max((i for i, (f, _) in enumerate(zip(filas_f[fila_n + 1:], filas_v[fila_n + 1:]))
                                         if f[0] and _RE_EMP.match(str(f[0]).strip())), default=0) + 1
    fila_total, sumas_truncadas, sumas_total = None, 0, 0
    for i, f in enumerate(filas_f[fila_n + 1:], start=fila_n + 2):
        formulas = [c for c in f[2:38] if isinstance(c, str) and re.match(r"^=\+?SUM\(", c)]
        if len(formulas) >= 10 and not (f[0] and _RE_EMP.match(str(f[0]).strip())):
            fila_total = i
            for c in formulas:
                m = re.search(r"SUM\(\$?[A-Z]+\$?(\d+):\$?[A-Z]+\$?(\d+)\)", c)
                if m:
                    sumas_total += 1
                    if int(m[2]) < ultima_fila_datos:
                        sumas_truncadas += 1
            break
    n_formulas = sum(1 for f in filas_f for c in f if isinstance(c, str) and c.startswith("="))
    n_error = sum(1 for f in filas_v for c in f if isinstance(c, str) and _RE_ERROR_EXCEL.match(c.strip()))
    return {
        "hoja": nombre,
        "empresas_listadas": len(empresas),
        "total_asistencias_reportado": int(total_cache),
        "total_columna_total_reportado": int(total_columna),
        "columnas_evento_sin_formula": sorted(sin_formula),
        "columnas_con_rango_truncado": sorted(truncadas),
        "empresas_con_asistencia_real_no_listadas": int(
            df_as["empresa_id"].nunique() - len(set(df_as["empresa_id"]) & empresas)
        ) if len(df_as) else 0,
        "formulas_totales": n_formulas,
        "celdas_con_error_excel": n_error,
        "fila_de_totales": fila_total,
        "sumas_en_fila_de_totales": sumas_total,
        "sumas_con_rango_truncado": sumas_truncadas,
    }


# ---------------------------------------------------------------------------
# Encuestas
# ---------------------------------------------------------------------------

def _leer_respuestas(ruta: Path) -> tuple[pd.DataFrame, dict[str, int]]:
    """Lee la hoja ``Responses`` (encabezado en la fila 2) y descarta las filas totalmente vacías."""
    df = pd.read_excel(ruta, sheet_name="Responses", header=1, dtype=str)
    n0 = len(df)
    df = df.dropna(how="all").reset_index(drop=True)
    return df, {"filas_leidas": n0, "filas_vacias": n0 - len(df), "filas_validas": len(df), "columnas_crudas": int(df.shape[1])}


def cargar_encuesta_evento(ruta: Path, modalidad: str) -> pd.DataFrame:
    """Lee la hoja ``Responses`` de las encuestas presenciales o virtuales."""
    df, ctl = _leer_respuestas(ruta)
    cols = list(df.columns)
    out = pd.DataFrame({
        "respuesta_id": df[cols[1]], "completada": df[cols[3]].map(lp.parsear_fecha_es),
        "colector": df[cols[5]].map(lp.limpiar_texto),
        "lugar_plataforma": pd.to_numeric(df[cols[6]], errors="coerce"),
        "convocatoria": pd.to_numeric(df[cols[7]], errors="coerce"),
        "conferencistas": pd.to_numeric(df[cols[8]], errors="coerce"),
        "relevancia": pd.to_numeric(df[cols[9]], errors="coerce"),
        "temas_solicitados": df[cols[10]], "persona_id": df[cols[12]].map(lp.limpiar_texto),
        "empresa_id": df[cols[13]].map(lp.normalizar_id_empresa), "ciudad": df[cols[14]].map(lp.normalizar_ciudad),
        "empresa_en_crm_fuente": df[cols[17]].map(lp.normalizar_si_no), "metodo_asignacion": df[cols[18]].map(lp.limpiar_texto),
    })
    out["fuente"] = f"encuesta_{modalidad.lower()}"
    out["modalidad"] = modalidad
    out.attrs["control"] = ctl
    log.info("Encuesta %s: %d respuestas", modalidad, len(out))
    return out


def cargar_encuesta_post(ruta: Path) -> pd.DataFrame:
    """Lee la encuesta post-evento (con NPS) y la deja con columnas legibles."""
    df, ctl = _leer_respuestas(ruta)
    cols = list(df.columns)

    def col(prefijo: str) -> pd.Series:
        for c in cols:
            if c.startswith(prefijo):
                return df[c]
        return pd.Series([None] * len(df))

    def aspectos(texto: str) -> pd.Series:
        for c in cols:
            if texto in c and c.startswith("15."):
                return pd.to_numeric(df[c], errors="coerce")
        return pd.Series([float("nan")] * len(df))

    temas = [c for c in cols if c.startswith("18.") and "[" in c]
    nombres_tema = {c: re.search(r"\[(.+)\]", c)[1] for c in temas}
    out = pd.DataFrame({
        "respuesta_id": col("ID de respuesta"), "completada": col("Respuesta completada").map(lp.parsear_fecha_es),
        "colector": col("Nombre del recopilador").map(lp.limpiar_texto), "persona_id": col("1.").map(lp.limpiar_texto),
        "empresa_id": col("4.").map(lp.normalizar_id_empresa), "cargo": col("5.").map(lp.normalizar_nivel_cargo),
        "ciudad": col("6.").map(lp.normalizar_ciudad), "afiliado_declarado": col("7.").map(
            lambda v: None if lp.es_nulo(v) else not lp.clave_texto(v).startswith("no")),
        "interes_afiliarse": col("8.").map(lp.limpiar_texto), "como_participo": col("12.").map(lp.normalizar_modalidad),
        "satisfaccion_global": pd.to_numeric(col("13."), errors="coerce"),
        "nps_puntaje": col("14.").map(lp.extraer_numero),
        "asp_expositor": aspectos("Expositor"), "asp_contenido": aspectos("Contenido"),
        "asp_recepcion": aspectos("Recepci"), "asp_espacio": aspectos("Espacio"),
        "asp_alimentacion": aspectos("Alimentaci"), "asp_tiempo": aspectos("Manejo del tiempo"),
        "empresa_en_crm_fuente": col("EMPRESA_EN_CRM").map(lp.normalizar_si_no), "metodo_asignacion": col("METODO_ASIGNACION").map(lp.limpiar_texto),
    })
    # Los temas marcados se guardan como texto de la opción elegida.
    out["temas_marcados"] = df[temas].notna().apply(
        lambda r: [nombres_tema[c] for c in temas if r[c]], axis=1) if temas else [[] for _ in range(len(df))]
    out["fuente"] = "encuesta_post"
    out["modalidad"] = out["como_participo"]
    out.attrs["control"] = ctl
    log.info("Encuesta post-evento: %d respuestas, %d con NPS", len(out), out["nps_puntaje"].notna().sum())
    return out


def cargar_encuesta_90(ruta: Path) -> pd.DataFrame:
    """Lee la encuesta de 90 días (instrumento; hoy sin respuestas)."""
    df, ctl = _leer_respuestas(ruta)
    df.attrs["control"] = ctl
    return df


# ---------------------------------------------------------------------------
# Informes de Zoho CRM (formato agrupado, con subtotales y «Grand Total»)
# ---------------------------------------------------------------------------

def _leer_hoja(ruta: Path) -> list[tuple]:
    wb = openpyxl.load_workbook(ruta, data_only=True)
    return [tuple(r) for r in wb.worksheets[0].iter_rows(values_only=True)]


def leer_informe_zoho(ruta: Path, columnas: list[str], grupos: list[str], clave: str = "empresa_id",
                      patron_clave: re.Pattern[str] = _RE_EMP) -> pd.DataFrame:
    """Lee un informe agrupado de Zoho CRM y lo deja en formato tidy, una fila por registro.

    Los informes de Zoho escriben cada grupo (mes, propietario, fecha) solo en su primera
    fila y añaden entre paréntesis la cantidad de registros («KAM D ( 1 )»), dejan filas en
    blanco entre grupos y cierran con «Grand Total». Este lector localiza el encabezado
    después de «Cantidad de registros», repite hacia abajo el valor de cada columna de grupo,
    le quita el conteo, descarta separadores y totales, y verifica que los registros
    recuperados coincidan con la cantidad declarada y con el conteo de cada grupo superior.
    El resumen queda en ``attrs["control"]``.
    """
    filas = _leer_hoja(ruta)
    declarados, generado, i_enc = None, None, None
    for i, f in enumerate(filas[:15]):
        a = f[0] if f else None
        if not isinstance(a, str):
            continue
        k = lp.clave_texto(a)
        if "cantidad de registros" in k:
            declarados = lp.a_entero(a.split(":")[-1])
        elif k.startswith("generado desde"):
            m = re.search(r"(\d{1,2}) de ([a-z]+) de (\d{4})", k)
            if m and lp.numero_mes(m[2]):
                generado = pd.Timestamp(int(m[3]), lp.numero_mes(m[2]), int(m[1]))
        elif declarados is not None and i_enc is None:
            i_enc = i
    if i_enc is None:  # sin línea de cantidad: el encabezado es la primera fila con texto en la primera columna
        i_enc = next(i for i, f in enumerate(filas) if f and isinstance(f[0], str) and not f[0].strip().lower().startswith(("generado", "informe")))
    ctl = _control_filas()
    ctl.update({"declarados": declarados, "generado": generado, "encabezado_en_fila": i_enc + 1})
    actual: dict[str, Any] = {g: None for g in grupos}
    ocurrencias: list[dict[str, Any]] = []  # una por cada aparición del grupo de nivel superior
    registros, rechazos = [], []
    for k, f in enumerate(filas[i_enc + 1:], start=i_enc + 2):
        ctl["filas_leidas"] += 1
        celdas = dict(zip(columnas, list(f) + [None] * (len(columnas) - len(f))))
        if lp.es_fila_total(f):
            ctl["filas_total"] += 1
            continue
        if all(lp.es_nulo(c) for c in f):
            ctl["filas_vacias"] += 1
            continue
        for g in grupos:
            if not lp.es_nulo(celdas.get(g)):
                texto, n = lp.quitar_conteo_grupo(celdas[g])
                actual[g] = texto
                if g == grupos[0] and n is not None:
                    ocurrencias.append({"grupo": texto, "declarado": n, "recuperado": 0})
        if isinstance(celdas.get(clave), str) and patron_clave.match(celdas[clave].strip()):
            ctl["filas_validas"] += 1
            if ocurrencias:
                ocurrencias[-1]["recuperado"] += 1
            registros.append({c: (actual[c] if c in grupos else celdas[c]) for c in columnas})
        else:
            ctl["filas_sin_codigo"] += 1
            rechazos.append({"fuente": ruta.stem, "ubicacion": f"fila {k}", "clave": None, "motivo": "sin código de empresa"})
    df = pd.DataFrame(registros, columns=columnas)
    ctl["recuperados"] = len(df)
    ctl["coincide_con_declarados"] = declarados is None or declarados == len(df)
    ctl["grupos"] = ocurrencias
    ctl["grupos_con_diferencia"] = [o for o in ocurrencias if o["declarado"] != o["recuperado"]]
    df.attrs["control"] = ctl
    df.attrs["rechazos"] = rechazos
    log.info("Informe %s: %d registros (declarados %s)", ruta.stem[:40], len(df), declarados)
    return df


def _ejecutiva_de_grupo(serie: pd.Series) -> pd.Series:
    return serie.map(lp.normalizar_ejecutiva)


def cargar_renovaciones(ruta: Path) -> pd.DataFrame:
    """Lee el informe de renovaciones de los últimos dos meses (formato agrupado de Zoho).

    Devuelve ``empresa_id``, ``fecha_expiracion`` (la nueva fecha tras renovar), ``mes_factura`` (primer día del
    mes de la factura de renovación) y ``ejecutiva``.
    """
    df = leer_informe_zoho(ruta, ["fecha_factura", "propietario", "empresa_id", "fecha_expiracion", "valor"], ["fecha_factura", "propietario"])
    ctl, rech = df.attrs["control"], df.attrs["rechazos"]
    out = pd.DataFrame({
        "empresa_id": df["empresa_id"].map(lp.normalizar_id_empresa),
        "fecha_expiracion": df["fecha_expiracion"].map(lp.parsear_fecha),
        "mes_factura": df["fecha_factura"].map(lp.parsear_mes_anio),
        "ejecutiva": _ejecutiva_de_grupo(df["propietario"]),
    }).dropna(subset=["empresa_id"]).reset_index(drop=True)
    out.attrs["control"], out.attrs["rechazos"] = ctl, rech
    return out


def cargar_afiliaciones_recientes(ruta: Path) -> pd.DataFrame:
    """Lee el informe de afiliaciones (negocios ganados) de los últimos dos meses."""
    df = leer_informe_zoho(ruta, ["mes_cierre", "propietario", "fecha_cierre", "empresa_id", "categoria_membresia", "importe"],
                           ["mes_cierre", "propietario", "fecha_cierre"])
    ctl, rech = df.attrs["control"], df.attrs["rechazos"]
    out = pd.DataFrame({
        "empresa_id": df["empresa_id"].map(lp.normalizar_id_empresa),
        "fecha_cierre": df["fecha_cierre"].map(lp.parsear_fecha_es),
        "ejecutiva": _ejecutiva_de_grupo(df["propietario"]),
        "categoria_membresia": df["categoria_membresia"].map(lp.limpiar_texto),
    }).dropna(subset=["empresa_id"]).reset_index(drop=True)
    out.attrs["control"], out.attrs["rechazos"] = ctl, rech
    return out


def cargar_oportunidades_ganadas(ruta: Path) -> pd.DataFrame:
    """Lee el informe de estados de oportunidades ganadas por KAM."""
    df = leer_informe_zoho(ruta, ["propietario", "empresa_id", "importe"], ["propietario"])
    ctl, rech = df.attrs["control"], df.attrs["rechazos"]
    out = pd.DataFrame({
        "empresa_id": df["empresa_id"].map(lp.normalizar_id_empresa), "ejecutiva": _ejecutiva_de_grupo(df["propietario"]),
    }).dropna(subset=["empresa_id"]).reset_index(drop=True)
    out.attrs["control"], out.attrs["rechazos"] = ctl, rech
    return out


def cargar_segmento_elite_premium(ruta: Path) -> pd.DataFrame:
    """Lee el informe por segmento Elite y Premium (categoría, ejecutiva, empresa y vencimiento)."""
    df = leer_informe_zoho(ruta, ["categoria_membresia", "propietario", "empresa_id", "fecha_expiracion"], ["categoria_membresia", "propietario"])
    ctl, rech = df.attrs["control"], df.attrs["rechazos"]
    out = pd.DataFrame({
        "empresa_id": df["empresa_id"].map(lp.normalizar_id_empresa), "categoria_membresia": df["categoria_membresia"].map(lp.limpiar_texto),
        "ejecutiva": _ejecutiva_de_grupo(df["propietario"]), "fecha_expiracion": df["fecha_expiracion"].map(lp.parsear_fecha),
    }).dropna(subset=["empresa_id"]).reset_index(drop=True)
    out.attrs["control"], out.attrs["rechazos"] = ctl, rech
    return out


def cargar_subsectores(ruta: Path) -> pd.DataFrame:
    """Lee el informe por subsectores (empresa y subsector económico)."""
    df = leer_informe_zoho(ruta, ["empresa_id", "subsector"], [])
    ctl, rech = df.attrs["control"], df.attrs["rechazos"]
    out = pd.DataFrame({"empresa_id": df["empresa_id"].map(lp.normalizar_id_empresa), "subsector": df["subsector"].map(lp.normalizar_subsector)})
    out = out.dropna(subset=["empresa_id"]).reset_index(drop=True)
    out.attrs["control"], out.attrs["rechazos"] = ctl, rech
    return out


def cargar_base_afiliados(ruta: Path) -> pd.DataFrame:
    """Lee la base de afiliados de ACTHO (empresa, ciudad, cargo y persona del afiliado principal)."""
    filas = _leer_hoja(ruta)
    ctl = _control_filas()
    reg, rech = [], []
    for k, f in enumerate(filas[1:], start=2):
        ctl["filas_leidas"] += 1
        clase = lp.clasificar_fila(f, f[0], _RE_EMP, ("Nombre de Empresa",))
        if clase == "vacia":
            ctl["filas_vacias"] += 1
        elif clase != "valida":
            ctl["filas_sin_codigo" if clase == "sin_clave" else "filas_total"] += 1
            rech.append({"fuente": "base_afiliados", "ubicacion": f"fila {k}", "clave": None, "motivo": clase})
        else:
            ctl["filas_validas"] += 1
            p = lp.limpiar_texto(f[3])
            reg.append({"empresa_id": lp.normalizar_id_empresa(f[0]), "ciudad": lp.normalizar_ciudad(f[1]),
                        "nivel_cargo": lp.normalizar_nivel_cargo(f[2]),
                        "persona_principal_id": p if isinstance(p, str) and _RE_PERSONA.match(p) else None})
    out = pd.DataFrame(reg, columns=["empresa_id", "ciudad", "nivel_cargo", "persona_principal_id"])
    out.attrs["control"], out.attrs["rechazos"] = {**ctl, "declarados": None, "recuperados": len(out), "coincide_con_declarados": True}, rech
    return out


def cargar_nuevos(ruta: Path, anio: int | None = None) -> pd.DataFrame:
    """Lee la lista de nuevos afiliados (celdas combinadas por mes y encabezado repetido en cada mes).

    Cada mes aparece como un título («Agosto»), un encabezado repetido y las empresas. Devuelve
    ``empresa_id``, ``persona_principal_id`` y ``mes`` (primer día del mes; el libro no trae el año,
    por lo que se toma ``anio`` o el año de los informes).
    """
    anio = anio or config.ANIO_INFORMES
    filas = _leer_hoja(ruta)
    ctl = _control_filas()
    reg, rech = [], []
    mes: int | None = None
    for k, f in enumerate(filas, start=1):
        ctl["filas_leidas"] += 1
        if all(lp.es_nulo(c) for c in f):
            ctl["filas_vacias"] += 1
            continue
        a = f[0]
        if isinstance(a, str) and lp.numero_mes(a) and all(lp.es_nulo(c) for c in f[1:]):
            mes = lp.numero_mes(a)
            continue
        if lp.es_encabezado_repetido(f, ("NOMBRE EMPRESA",)):
            ctl["filas_encabezado_repetido"] += 1
            continue
        if isinstance(a, str) and lp.clave_texto(a) == "nuevos afiliados":
            continue
        emp = lp.normalizar_id_empresa(a)
        if emp is None:
            ctl["filas_sin_codigo"] += 1
            rech.append({"fuente": "nuevos_afiliados", "ubicacion": f"fila {k}", "clave": None, "motivo": "sin código de empresa"})
            continue
        ctl["filas_validas"] += 1
        p = lp.limpiar_texto(f[1])
        reg.append({"empresa_id": emp, "persona_principal_id": p if isinstance(p, str) and _RE_PERSONA.match(p) else None,
                    "mes": pd.Timestamp(anio, mes, 1) if mes else pd.NaT})
    out = pd.DataFrame(reg, columns=["empresa_id", "persona_principal_id", "mes"]).drop_duplicates("empresa_id").reset_index(drop=True)
    out.attrs["control"], out.attrs["rechazos"] = {**ctl, "declarados": None, "recuperados": len(out), "coincide_con_declarados": True}, rech
    return out


def cargar_informe_membresias(ruta: Path) -> pd.DataFrame:
    """Lee el informe de membresías: un resumen con subtotales por tipo y un total general mezclados con los datos.

    Devuelve ``tipo_membresia``, ``categoria_membresia`` y ``cantidad`` de cada combinación, sin los subtotales ni
    el total. Comprueba que cada subtotal sea la suma de su grupo y que el total sea la suma de todo
    (``attrs["control"]["subtotales_coinciden"]``).
    """
    filas = _leer_hoja(ruta)
    declarados = None
    i_enc = None
    for i, f in enumerate(filas[:12]):
        if isinstance(f[0], str) and "cantidad de registros" in lp.clave_texto(f[0]):
            declarados = lp.a_entero(f[0].split(":")[-1])
            i_enc = i
    i_enc = (i_enc or 4) + 1
    while i_enc < len(filas) and all(lp.es_nulo(c) for c in filas[i_enc]):
        i_enc += 1
    reg, tipo = [], None
    sub_ok, sub_total, suma_tipo, suma_total, detalle_sub, prev_sub = 0, 0, 0, 0, [], False
    ctl = _control_filas()
    for f in filas[i_enc + 1:]:
        ctl["filas_leidas"] += 1
        if all(lp.es_nulo(c) for c in f):
            ctl["filas_vacias"] += 1
            continue
        et_tipo, cat, cant = lp.limpiar_texto(f[0]), lp.limpiar_texto(f[1]), lp.a_entero(f[2])
        if cant is None:
            continue
        if et_tipo is None and cat is None:
            # Fila sin etiquetas: el subtotal de un tipo o, si va justo después de otro subtotal, el total general.
            ctl["filas_total"] += 1
            sub_total += 1
            if prev_sub:
                sub_ok += int(cant == suma_total)
                detalle_sub.append({"tipo": "total general", "subtotal": cant, "suma": suma_total})
            else:
                sub_ok += int(cant == suma_tipo)
                detalle_sub.append({"tipo": tipo, "subtotal": cant, "suma": suma_tipo})
                suma_total += suma_tipo
            prev_sub = True
            continue
        prev_sub = False
        if et_tipo is not None:
            tipo, suma_tipo = et_tipo, 0
        ctl["filas_validas"] += 1
        suma_tipo += cant
        reg.append({"tipo_membresia": tipo, "categoria_membresia": cat, "cantidad": cant})
    out = pd.DataFrame(reg, columns=["tipo_membresia", "categoria_membresia", "cantidad"])
    out.attrs["control"] = {**ctl, "declarados": declarados, "recuperados": int(out["cantidad"].sum()),
                            "coincide_con_declarados": declarados is None or declarados == int(out["cantidad"].sum()),
                            "subtotales_verificados": sub_total, "subtotales_coinciden": sub_ok, "detalle_subtotales": detalle_sub}
    out.attrs["rechazos"] = []
    return out


def cargar_kam_consolidado(ruta: Path) -> pd.DataFrame:
    """Lee el consolidado de asistencia por KAM, cuya hoja repite un bloque (resumen más tabla por empresa) por cada ejecutiva.

    Unifica los bloques en una sola tabla con ``ejecutiva``, ``empresa_id``, ``estado_asistencia``,
    ``eventos_asistidos`` y ``total_asistentes``. El título de cada bloque puede incluir un nombre de
    persona entre paréntesis; solo se conserva la etiqueta anonimizada «KAM X».
    """
    filas = _leer_hoja(ruta)
    reg, bloques = [], []
    actual: dict[str, Any] | None = None
    ctl = _control_filas()
    for f in filas:
        ctl["filas_leidas"] += 1
        textos = [c for c in f if isinstance(c, str)]
        titulo = next((t for t in textos if lp.clave_texto(t).startswith("resumen consolidado")), None)
        if titulo:
            m = re.search(r"\bKAM\s+([A-Za-z])\b", titulo)
            actual = {"ejecutiva": f"KAM {m[1].upper()}" if m else "Sin asignar", "resumen": None, "filas": 0}
            bloques.append(actual)
            continue
        if actual is None:
            continue
        if actual["resumen"] is None and len(f) > 4 and all(isinstance(x, (int, float)) for x in f[1:5]):
            actual["resumen"] = {"total_empresas": int(f[1]), "con_asistencia": int(f[2]), "sin_asistencia": int(f[3]), "total_asistentes": int(f[4])}
            continue
        emp = lp.normalizar_id_empresa(f[1]) if len(f) > 1 else None
        if emp and len(f) > 5 and lp.limpiar_texto(f[3]):
            reg.append({"ejecutiva": actual["ejecutiva"], "empresa_id": emp, "estado_asistencia": lp.limpiar_texto(f[3]),
                        "eventos_asistidos": lp.a_entero(f[4]) or 0, "total_asistentes": lp.a_entero(f[5]) or 0})
            actual["filas"] += 1
            ctl["filas_validas"] += 1
        elif all(lp.es_nulo(c) for c in f):
            ctl["filas_vacias"] += 1
    out = pd.DataFrame(reg, columns=["ejecutiva", "empresa_id", "estado_asistencia", "eventos_asistidos", "total_asistentes"])
    detalle = []
    for b in bloques:
        g = out[out["ejecutiva"] == b["ejecutiva"]]
        r = b["resumen"] or {}
        detalle.append({"ejecutiva": b["ejecutiva"], **r, "filas_recuperadas": len(g),
                        "asistentes_recuperados": int(g["total_asistentes"].sum()),
                        "coincide": bool(r) and r.get("total_empresas") == len(g) and r.get("total_asistentes") == int(g["total_asistentes"].sum())})
    out.attrs["control"] = {**ctl, "bloques": detalle, "declarados": sum(d.get("total_empresas", 0) for d in detalle), "recuperados": len(out),
                            "coincide_con_declarados": all(d["coincide"] for d in detalle)}
    out.attrs["rechazos"] = []
    return out
