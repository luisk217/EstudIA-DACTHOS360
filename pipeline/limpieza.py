"""Funciones puras de limpieza y normalización.

Ninguna función ejecuta contenido de los datos: solo transforma texto, fechas
y categorías. Las equivalencias de categorías no están incrustadas: se leen del
diccionario editable ``config/homologacion.json`` (ver ``pipeline/config.py``).
Se prueban con datos sintéticos en ``tests/``.
"""
from __future__ import annotations

import re
import unicodedata
from functools import lru_cache
from datetime import date, datetime
from typing import Any

import pandas as pd

from . import config

# Caracteres de media anchura (U+FF61 a U+FF9F) que aparecen cuando el UTF-8 se decodificó como cp932.
_PAT_MOJIBAKE = re.compile("[｡-ﾟ]")
_PAT_EMPRESA = re.compile(r"^EMP-\d{3,5}$")
_PAT_PERSONA = re.compile(r"^P-\d{3,6}$")
_PAT_FECHA_ES = re.compile(r"^\s*([a-záéíóú]{3})\.?\s+(\d{1,2}),\s+(\d{4})", re.IGNORECASE)
_PAT_SNAKE = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")
_PAT_KAM = re.compile(r"^kam\s*([a-z])$", re.IGNORECASE)
_PAT_TOTAL = re.compile(r"^(grand\s+total|gran\s+total|total(\s+general)?|subtotal|suma|totales)\b", re.IGNORECASE)
#: Años que delatan una fecha centinela (cero de Excel, «fecha infinita» de los sistemas).
_ANIOS_CENTINELA = {1899, 1900, 9999}


def es_nulo(valor: Any) -> bool:
    """Indica si un valor es nulo, NaN o una cadena vacía."""
    if valor is None:
        return True
    if isinstance(valor, float) and valor != valor:
        return True
    if isinstance(valor, str) and not valor.strip():
        return True
    try:
        return bool(pd.isna(valor))
    except (TypeError, ValueError):
        return False


def reparar_mojibake(texto: Any) -> Any:
    """Repara texto UTF-8 mal decodificado como cp932 (p. ej. ``Bogotﾃ｡`` a ``Bogotá``)."""
    if not isinstance(texto, str) or not _PAT_MOJIBAKE.search(texto):
        return texto
    try:
        return texto.encode("cp932").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return texto


def quitar_tildes(texto: str) -> str:
    """Elimina diacríticos de un texto."""
    nfd = unicodedata.normalize("NFD", texto)
    return "".join(c for c in nfd if unicodedata.category(c) != "Mn")


def clave_texto(texto: Any) -> str:
    """Forma canónica para comparar: sin mojibake, sin tildes, minúsculas, espacios colapsados."""
    if es_nulo(texto):
        return ""
    t = quitar_tildes(str(reparar_mojibake(texto)))
    return re.sub(r"\s+", " ", t).strip().lower()


# ---------------------------------------------------------------------------
# Texto genérico, centinelas y nombres de columna
# ---------------------------------------------------------------------------

def _hom() -> dict[str, Any]:
    """Diccionario de homologación vigente (se relee en cada llamada para respetar recargas en caliente)."""
    return config.HOMOLOGACION


@lru_cache(maxsize=8)
def _claves_centinela(centinelas: tuple[str, ...]) -> frozenset[str]:
    return frozenset(clave_texto(c) for c in centinelas)


def es_centinela(valor: Any) -> bool:
    """Indica si el texto es un marcador de dato ausente («N/A», «-», «sin dato», errores de Excel, etc.)."""
    if not isinstance(valor, str):
        return False
    return clave_texto(valor) in _claves_centinela(tuple(_hom()["centinelas_nulos"]))


def limpiar_texto(valor: Any) -> Any:
    """Limpia un texto: repara tildes dañadas, unifica espacios (incluido el no separable) y convierte nulos y centinelas en ``None``.

    Los valores que no son texto (números, fechas) se devuelven sin cambios.
    """
    if es_nulo(valor):
        return None
    if not isinstance(valor, str):
        return valor
    t = unicodedata.normalize("NFC", str(reparar_mojibake(valor))).replace("\xa0", " ")
    t = re.sub(r"\s+", " ", t).strip()
    return None if not t or es_centinela(t) else t


def homologar(valor: Any, seccion: str) -> Any:
    """Lleva un texto a su valor canónico según la sección del diccionario; si no hay equivalencia lo devuelve limpio."""
    t = limpiar_texto(valor)
    if t is None or not isinstance(t, str):
        return t
    return _hom()[seccion]["equivalencias"].get(clave_texto(t), t)


def fuera_de_catalogo(valores: Any, seccion: str) -> list[str]:
    """Valores distintos (no nulos) que no están en el catálogo de la sección; sirven para ampliar el diccionario."""
    cat = set(config.catalogo(_hom()[seccion]))
    return sorted({str(v) for v in pd.Series(valores).dropna().unique() if str(v) not in cat})


def snake_case(nombre: Any) -> str:
    """Convierte un encabezado a ``snake_case`` sin tildes ni espacios (``Fecha de Expiración [x]`` da ``fecha_de_expiracion``).

    Descarta las etiquetas entre corchetes de la anonimización y, si el encabezado trae una flecha
    (``Empresa [anonimizado] → ID_EMPRESA``), usa el nombre de destino.
    """
    t = str(nombre)
    if "→" in t:
        t = t.split("→")[-1]
    t = re.sub(r"\[[^\]]*\]|\([^)]*\)", " ", t)
    t = re.sub(r"[^a-z0-9]+", "_", quitar_tildes(t).lower()).strip("_")
    if not t:
        return "columna"
    return t if not t[0].isdigit() else f"c_{t}"


def es_snake_case(nombre: Any) -> bool:
    """Indica si un nombre de columna ya está en ``snake_case`` ASCII (minúsculas, dígitos y guiones bajos)."""
    return bool(_PAT_SNAKE.match(str(nombre)))


# ---------------------------------------------------------------------------
# Estructura de las hojas: totales, encabezados repetidos y grupos de Zoho
# ---------------------------------------------------------------------------

def quitar_conteo_grupo(valor: Any) -> tuple[str | None, int | None]:
    """Separa el texto de un grupo de Zoho de su conteo: ``KAM D ( 1 )`` da ``("KAM D", 1)``."""
    if es_nulo(valor):
        return None, None
    t = str(valor).strip()
    m = re.match(r"^(.*?)\s*\(\s*(\d+)\s*\)\s*$", t)
    return ((m[1].strip() or None), int(m[2])) if m else (t, None)


def es_fila_total(celdas: Any) -> bool:
    """Indica si una fila es un total o subtotal mezclado con los datos (una celda de texto empieza por «Total», «Subtotal», etc.)."""
    return any(isinstance(c, str) and _PAT_TOTAL.match(quitar_tildes(c.strip())) for c in celdas)


def es_encabezado_repetido(celdas: Any, patrones: tuple[str, ...]) -> bool:
    """Indica si una fila repite el encabezado de la tabla (una celda contiene uno de los patrones, sin distinguir mayúsculas)."""
    claves = [clave_texto(p) for p in patrones]
    return any(k in clave_texto(c) for c in celdas if isinstance(c, str) for k in claves)


def clasificar_fila(celdas: Any, clave: Any, patron_clave: re.Pattern[str], patrones_encabezado: tuple[str, ...] = ()) -> str:
    """Clasifica una fila: ``vacia``, ``total``, ``encabezado``, ``sin_clave`` (tiene contenido pero no código válido) o ``valida``."""
    celdas = tuple(celdas)
    if all(es_nulo(c) for c in celdas):
        return "vacia"
    if es_fila_total(celdas):
        return "total"
    if patrones_encabezado and es_encabezado_repetido(celdas, patrones_encabezado):
        return "encabezado"
    if isinstance(clave, str) and patron_clave.match(clave.strip()):
        return "valida"
    return "sin_clave"


# ---------------------------------------------------------------------------
# Categorías homologadas con el diccionario config/homologacion.json
# ---------------------------------------------------------------------------

def normalizar_ciudad(valor: Any) -> str | None:
    """Unifica ciudades (tildes, mayúsculas, errores comunes, sufijos de país o de «D.C.») según el diccionario."""
    t = limpiar_texto(valor)
    if t is None:
        return None
    base = str(t).split(",")[0].strip()
    clave = clave_texto(base)
    eq = _hom()["ciudades"]["equivalencias"]
    if clave in eq:
        return eq[clave]
    return base.title() if base.isupper() else base


def normalizar_sector(valor: Any) -> str | None:
    """Unifica sectores económicos escritos con y sin tildes, con errores de digitación o con espacios dobles."""
    return homologar(valor, "sectores")


def normalizar_subsector(valor: Any) -> str | None:
    """Unifica subsectores (mayúsculas distintas, tildes y errores de digitación)."""
    return homologar(valor, "subsectores")


def normalizar_categoria_membresia(valor: Any) -> str | None:
    """Devuelve la categoría de Zoho (Estándar, Estándar Colaborador, Premium, Elite) o ``None``.

    La columna mezcla categorías con valores de tipo mal digitados («Empresas», «Consultoras», «Plus»):
    esos valores no son categorías y dan ``None`` (el nivel se infiere entonces del tipo de membresía).
    """
    t = homologar(valor, "categorias_membresia")
    return t if t in config.catalogo(_hom()["categorias_membresia"]) else None


def normalizar_tipo_membresia(valor: Any) -> str | None:
    """Agrupa los tipos de membresía de Zoho en Empresa, Consultora, Persona natural, etc."""
    return homologar(valor, "tipos_membresia")


def normalizar_empleados(valor: Any) -> str | None:
    """Homogeneiza rangos de empleados (``1 - 50`` y ``1-50``; «más de 10.000» pasa a «10.001 o más»)."""
    t = limpiar_texto(valor)
    if t is None:
        return None
    t = re.sub(r"\s*-\s*", "-", str(t))
    if clave_texto(t).startswith("mas de 10"):
        return "10.001 o más"
    return _hom()["rangos_empleados"]["equivalencias"].get(clave_texto(t), t)


def normalizar_estado_membresia(valor: Any) -> str | None:
    """Lleva el estado de la membresía a uno de los seis estados de Zoho (Activo, Periodo de Gracia, etc.)."""
    return homologar(valor, "estados_membresia")


def normalizar_estado_registro(valor: Any) -> str | None:
    """Lleva el estado del registro del CRM a Activo o Inactivo."""
    return homologar(valor, "estados_registro_crm")


def normalizar_pais(valor: Any) -> str | None:
    """Unifica el país (``COLOMBIA`` y el error ``Colomba`` pasan a ``Colombia``)."""
    return homologar(valor, "paises")


def normalizar_departamento(valor: Any) -> str | None:
    """Unifica el departamento (``DC`` y ``Bogotá, D.C.`` pasan a ``Bogotá D.C.``; restituye tildes)."""
    return homologar(valor, "departamentos")


def normalizar_region(valor: Any) -> str | None:
    """Unifica la región comercial (``Bogota``, ``Medellin`` y ``Otro`` pasan a su forma canónica)."""
    return homologar(valor, "regiones")


def normalizar_tamano(valor: Any) -> str | None:
    """Unifica el tamaño de la empresa (Micro, Pequeña, Mediana, Grande)."""
    return homologar(valor, "tamanos")


def normalizar_naturaleza(valor: Any) -> str | None:
    """Limpia el tipo de empresa (Nacional Privada, Multinacional, etc.)."""
    return homologar(valor, "naturaleza_empresa")


def normalizar_modalidad(valor: Any) -> str | None:
    """Unifica la modalidad del evento o de la encuesta (Presencial, Virtual, Híbrido)."""
    return homologar(valor, "modalidades")


def normalizar_linea(valor: Any) -> str | None:
    """Unifica la línea o el formato de la oferta 2027 de un evento."""
    return homologar(valor, "lineas_evento")


def normalizar_nivel_cargo(valor: Any) -> str | None:
    """Unifica el nivel de cargo; «Sin dato» y similares pasan a ``None``."""
    return homologar(valor, "niveles_cargo")


def normalizar_nivel(categoria: Any, tipo_membresia: Any = None) -> str:
    """Devuelve el nivel 2027 (Conectar, Crecer, Liderar) o ``Sin dato``.

    Usa la categoría de Zoho y, si esta contiene un valor de tipo mal
    digitado (``Empresas``, ``Consultoras``), intenta inferirlo del tipo de
    membresía (``Corporativa Premium``).
    """
    n = _hom()["niveles"]
    clave = clave_texto(categoria)
    if clave in n["por_categoria"]:
        return n["por_categoria"][clave]
    clave_tipo = clave_texto(tipo_membresia)
    for palabra, nivel in n["por_palabra_en_tipo"]:
        if palabra in clave_tipo:
            return nivel
    return "Sin dato"


def normalizar_ejecutiva(valor: Any) -> str:
    """Normaliza el propietario de la cuenta; vacío, ``0`` o ``Sin asignar`` pasan a ``Sin asignar`` y ``kam  b`` a ``KAM B``."""
    e = _hom()["ejecutivas"]
    t = limpiar_texto(valor)
    if t is None:
        return e["etiqueta_sin_asignar"]
    t = str(t)
    k = t.lower()
    if k in e["valores_sin_asignar"] or any(k.startswith(p) for p in e["prefijos_sin_asignar"]):
        return e["etiqueta_sin_asignar"]
    m = _PAT_KAM.match(t)
    return f"KAM {m[1].upper()}" if m else t


def normalizar_si_no(valor: Any) -> bool | None:
    """Convierte variantes de Sí/No (``SI``, ``Sí``, ``SÍ, AUTORIZO...``) a booleano.

    Se exige límite de palabra: «Sin dato» o «Noviembre» no deben leerse como Sí ni No,
    y los centinelas («N/A», «no aplica») dan ``None``.
    """
    if es_nulo(valor) or es_centinela(valor):
        return None
    clave = clave_texto(valor)
    sn = _hom()["si_no"]
    primera = re.match(r"^[a-z]+", clave)
    palabra = primera[0] if primera else ""
    if clave in sn["verdaderos"] or (len(palabra) > 1 and palabra in sn["verdaderos"]):
        return True
    if clave in sn["falsos"] or (len(palabra) > 1 and palabra in sn["falsos"]):
        return False
    return None


def normalizar_porcentaje(valor: Any) -> float | None:
    """Convierte ``50%`` o ``50`` en un porcentaje de 0 a 100; ``None`` si es nulo, centinela o no es válido."""
    if es_nulo(valor) or es_centinela(valor):
        return None
    t = str(valor).strip().replace(",", ".")
    try:
        x = float(t.rstrip("%").strip())
    except ValueError:
        return None
    return round(x, 1) if 0 <= x <= 100 else None


def a_entero(valor: Any) -> int | None:
    """Convierte ``1``, ``1.0`` o ``'3'`` en entero; ``None`` si es nulo, centinela o no entero."""
    if es_nulo(valor) or es_centinela(valor):
        return None
    try:
        x = float(str(valor).replace(",", ".").strip())
    except ValueError:
        return None
    return int(x) if x.is_integer() else None


def normalizar_id_persona(valor: Any) -> str | None:
    """Devuelve el ID de persona en formato ``P-00000`` o ``None`` si no es válido."""
    if es_nulo(valor):
        return None
    t = str(valor).strip().upper()
    return t if _PAT_PERSONA.match(t) else None


def normalizar_id_empresa(valor: Any) -> str | None:
    """Devuelve el ID de empresa en formato ``EMP-0000`` o ``None`` si no es válido."""
    if es_nulo(valor):
        return None
    t = str(valor).strip().upper()
    return t if _PAT_EMPRESA.match(t) else None


# ---------------------------------------------------------------------------
# Fechas
# ---------------------------------------------------------------------------

def _valida(ts: pd.Timestamp) -> pd.Timestamp:
    """Descarta las fechas centinela (1899, 1900, 9999) y las que no son fechas."""
    return pd.NaT if pd.isna(ts) or ts.year in _ANIOS_CENTINELA else ts


def parsear_fecha(valor: Any) -> pd.Timestamp:
    """Convierte fechas ISO, ``dd/mm/aaaa`` (también con ``-`` o ``.``) o datetime a ``Timestamp`` (``NaT`` si falla).

    Un rango como ``17-20/03/2026`` devuelve su primer día. Las fechas centinela (1900, 9999) dan ``NaT``.
    """
    if es_nulo(valor) or es_centinela(valor):
        return pd.NaT
    if isinstance(valor, (datetime, date, pd.Timestamp)):
        return _valida(pd.Timestamp(valor).normalize())
    t = str(valor).strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}", t):
        return _valida(pd.to_datetime(t[:10], errors="coerce"))
    m = re.match(r"^(\d{1,2})\s*-\s*\d{1,2}/(\d{1,2})/(\d{4})", t)  # rango 17-20/03/2026
    if not m:
        m = re.match(r"^(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{4})", t)
    if m:
        return _valida(pd.to_datetime(f"{m[3]}-{int(m[2]):02d}-{int(m[1]):02d}", errors="coerce"))
    return pd.NaT


def parsear_rango_fechas(valor: Any) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Devuelve ``(inicio, fin)`` de una fecha o de un rango (``17-20/03/2026`` o ``28/07/2026-29/07/2026``); ``NaT`` si no se puede leer."""
    t = "" if es_nulo(valor) else str(valor).strip()
    m = re.match(r"^(\d{1,2})\s*-\s*(\d{1,2})/(\d{1,2})/(\d{4})", t)
    if m:
        ini = _valida(pd.to_datetime(f"{m[4]}-{int(m[3]):02d}-{int(m[1]):02d}", errors="coerce"))
        fin = _valida(pd.to_datetime(f"{m[4]}-{int(m[3]):02d}-{int(m[2]):02d}", errors="coerce"))
        return ini, fin
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})\s*-\s*(\d{1,2})/(\d{1,2})/(\d{4})", t)  # 28/07/2026-29/07/2026
    if m:
        ini = _valida(pd.to_datetime(f"{m[3]}-{int(m[2]):02d}-{int(m[1]):02d}", errors="coerce"))
        fin = _valida(pd.to_datetime(f"{m[6]}-{int(m[5]):02d}-{int(m[4]):02d}", errors="coerce"))
        return ini, fin
    f = parsear_fecha(valor)
    return f, f


def parsear_fecha_es(valor: Any) -> pd.Timestamp:
    """Interpreta fechas de Zoho Survey como ``mar. 27, 2025 09:24:10 a. m.`` y de Zoho CRM como ``ago 26, 2026 ( 1 )``."""
    if es_nulo(valor):
        return pd.NaT
    meses = _hom()["meses_es"]
    m = _PAT_FECHA_ES.match(quitar_tildes(str(valor)))
    if not m or m[1].lower() not in meses:
        return pd.NaT
    try:
        return pd.Timestamp(int(m[3]), meses[m[1].lower()], int(m[2]))
    except ValueError:  # día inexistente, p. ej. «feb. 31, 2026»
        return pd.NaT


def parsear_mes_anio(valor: Any) -> pd.Timestamp:
    """Interpreta ``Septiembre 2026 ( 10 )`` como el primer día de ese mes; ``NaT`` si no es un mes con año."""
    texto, _ = quitar_conteo_grupo(valor)
    m = re.match(r"^([a-z]+)\s+(\d{4})$", quitar_tildes(texto or "").lower())
    meses = _hom()["meses_es_completos"]
    if not m or m[1] not in meses:
        return pd.NaT
    return pd.Timestamp(int(m[2]), meses[m[1]], 1)


def numero_mes(nombre: Any) -> int | None:
    """Número del mes (1 a 12) de un nombre completo en español, como ``Agosto``; ``None`` si no lo es."""
    texto, _ = quitar_conteo_grupo(nombre)
    return _hom()["meses_es_completos"].get(clave_texto(texto))


# ---------------------------------------------------------------------------
# NPS y números
# ---------------------------------------------------------------------------

def clasificar_nps(puntaje: Any) -> str | None:
    """Clasifica un puntaje 0-10 en Promotor (9-10), Pasivo (7-8) o Detractor (0-6).

    Devuelve ``None`` si el valor es nulo, no numérico o está fuera de la escala.
    """
    if es_nulo(puntaje):
        return None
    try:
        p = float(puntaje)
    except (TypeError, ValueError):
        return None
    if not 0 <= p <= 10:
        return None
    if p >= 9:
        return "Promotor"
    return "Pasivo" if p >= 7 else "Detractor"


def calcular_nps(puntajes: pd.Series) -> dict[str, float | int | None]:
    """Calcula NPS = %promotores - %detractores sobre una serie de puntajes 0-10.

    Se ignoran los valores no numéricos y los que están fuera de la escala 0-10.
    """
    p = pd.to_numeric(puntajes, errors="coerce").dropna()
    p = p[(p >= 0) & (p <= 10)]
    n = len(p)
    if n == 0:
        return {"n": 0, "promotores": 0, "pasivos": 0, "detractores": 0, "nps": None}
    prom, det = int((p >= 9).sum()), int((p <= 6).sum())
    return {
        "n": n, "promotores": prom, "pasivos": n - prom - det, "detractores": det,
        "nps": round(100 * (prom - det) / n, 1),
    }


def extraer_numero(valor: Any) -> float | None:
    """Extrae el primer número de un texto como ``10 (Promoter)`` o ``5.0``."""
    if es_nulo(valor):
        return None
    m = re.search(r"\d+(?:[.,]\d+)?", str(valor))
    return float(m[0].replace(",", ".")) if m else None
