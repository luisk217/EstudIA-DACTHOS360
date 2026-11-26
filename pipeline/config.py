"""Configuración central del pipeline DACTHO 360.

Reúne rutas y constantes de negocio. Los pesos del score viven en
``config/pesos_score.json`` y el diccionario de homologación de categorías
(ciudades, sectores, niveles, estados, modalidades, líneas de evento y demás)
vive en ``config/homologacion.json``; ambos los puede editar el equipo de
ACTHO sin tocar código.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Iterable

RAIZ: Path = Path(__file__).resolve().parents[1]

#: Carpeta con las exportaciones crudas (se puede sobrescribir con ACTHO_DATA_DIR).
DIR_DATOS: Path = Path(
    os.environ.get("ACTHO_DATA_DIR", RAIZ / "Material & Recursos" / "Recursos ACTHO")
)

RUTA_PESOS: Path = RAIZ / "config" / "pesos_score.json"
#: Diccionario editable de homologación de categorías (se puede sobrescribir con ACTHO_HOMOLOGACION).
RUTA_HOMOLOGACION: Path = Path(os.environ.get("ACTHO_HOMOLOGACION", RAIZ / "config" / "homologacion.json"))
DIR_PROCESADOS: Path = RAIZ / "data" / "processed"
DIR_WEB: Path = RAIZ / "web" / "data"
DIR_EDA: Path = RAIZ / "docs" / "eda"

#: Fecha de corte del análisis (la de los informes de Zoho entregados).
FECHA_CORTE_DEFECTO: date = date(2026, 11, 25)

#: Inicio de cobertura del libro de asistencia (primer evento de 2026).
INICIO_COBERTURA_ASISTENCIA: date = date(2026, 1, 1)

# Rutas relativas de cada fuente dentro de DIR_DATOS.
FUENTES: dict[str, str] = {
    "crm": "1. Base de datos de afiliados/Base de datos Hackaton_anonimizada.xlsx",
    "asistencia": "2. Registros de participación en actividades/BASE ASISTENCIA A EVENTOS 2026 - EAFIT_anonimizada.xlsx",
    "kam": "2. Registros de participación en actividades/Consolidados de asistencia por KAM 2026_anonimizado.xlsx",
    "enc_presencial": "3. Encuestas y NPS/Eventos Presenciales 2026_anonimizada.xlsx",
    "enc_virtual": "3. Encuestas y NPS/Eventos Virtuales ACRIP 2026_anonimizada.xlsx",
    "enc_post": "3. Encuestas y NPS/ENCUESTA-POST-EVENTOS (PRESENCIAL Y VIRTUAL)_anonimizada.xlsx",
    "enc_90": "3. Encuestas y NPS/90 días - NPS_sin respuestas (instrumento).xlsx",
    "renovaciones": "5. Indicadores y reportes actuales/Informe Renovaciones - Ultimos 2 Meses_anonimizado.xlsx",
    "nuevos": "5. Indicadores y reportes actuales/Nuevos Afiliados AGO-SEP_anonimizado.xlsx",
    "afiliaciones": "5. Indicadores y reportes actuales/Afiliaciones - Ultimos 2 Meses_anonimizado.xlsx",
    "oportunidades": "5. Indicadores y reportes actuales/Estados oportunidades ganadas por KAM_anonimizado.xlsx",
    "segmento": "5. Indicadores y reportes actuales/Informe por segmento Elite y Premium_anonimizado.xlsx",
    "subsectores": "5. Indicadores y reportes actuales/Informe por subsectores_anonimizado.xlsx",
    "membresias": "5. Indicadores y reportes actuales/Informe de membresías.xlsx",
    "base_afiliados": "5. Indicadores y reportes actuales/Base de datos afiliados ACTHO_anonimizada.xlsx",
}

#: Fuentes que el pipeline necesita para producir el tablero; las demás son informes de apoyo (opcionales).
FUENTES_OBLIGATORIAS: tuple[str, ...] = ("crm", "asistencia", "enc_presencial", "enc_virtual", "enc_post", "enc_90", "renovaciones")

SECCIONES_HOMOLOGACION: tuple[str, ...] = (
    "centinelas_nulos", "si_no", "estados_membresia", "estados_registro_crm", "niveles", "categorias_membresia", "tipos_membresia", "sectores",
    "subsectores", "ciudades", "departamentos", "regiones", "paises", "tamanos", "rangos_empleados", "naturaleza_empresa",
    "ejecutivas", "modalidades", "lineas_evento", "niveles_cargo", "fin_evento_multidia", "meses_es", "meses_es_completos",
)


def catalogo(seccion: dict[str, Any]) -> list[str]:
    """Valores canónicos de una sección (si el catálogo trae diccionarios, toma el primer campo)."""
    out: list[str] = []
    for v in seccion.get("catalogo", []):
        out.append(next(iter(v.values())) if isinstance(v, dict) else v)
    return out


def _clave(texto: str) -> str:
    import re
    import unicodedata
    nfd = unicodedata.normalize("NFD", texto)
    t = "".join(c for c in nfd if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", t).strip().lower()


def validar_homologacion(h: dict[str, Any]) -> list[str]:
    """Revisa la estructura del diccionario y devuelve la lista de problemas (vacía si es correcto).

    Detecta secciones ausentes, claves de equivalencia mal escritas (con mayúsculas, tildes o espacios
    sobrantes) y equivalencias que apuntan a un valor que no está en el catálogo de la sección.
    """
    problemas: list[str] = []
    for s in SECCIONES_HOMOLOGACION:
        if s not in h:
            problemas.append(f"falta la sección «{s}»")
    for nombre, sec in h.items():
        if not isinstance(sec, dict) or "equivalencias" not in sec:
            continue
        cat = set(catalogo(sec))
        for k, v in sec["equivalencias"].items():
            if k != _clave(k):
                problemas.append(f"{nombre}: la clave «{k}» debe escribirse en minúsculas, sin tildes y sin espacios sobrantes (use «{_clave(k)}»)")
            if cat and v not in cat:
                problemas.append(f"{nombre}: la equivalencia «{k}» apunta a «{v}», que no está en el catálogo")
    return problemas


def cargar_homologacion(ruta: Path | None = None) -> dict[str, Any]:
    """Lee y valida ``config/homologacion.json``; lanza ``ValueError`` si tiene errores de estructura."""
    ruta = Path(ruta) if ruta else RUTA_HOMOLOGACION
    with open(ruta, encoding="utf-8") as fh:
        h = json.load(fh)
    problemas = validar_homologacion(h)
    if problemas:
        raise ValueError(f"homologacion.json inválido ({ruta}): " + "; ".join(problemas))
    return h


#: Diccionario vigente. Se puede reemplazar en caliente con ``recargar_homologacion`` (las pruebas lo hacen).
HOMOLOGACION: dict[str, Any] = cargar_homologacion()


def recargar_homologacion(ruta: Path | None = None) -> dict[str, Any]:
    """Recarga el diccionario desde disco (o desde ``ruta``) y actualiza las constantes derivadas."""
    global HOMOLOGACION
    HOMOLOGACION = cargar_homologacion(ruta)
    _derivar()
    return HOMOLOGACION


def _derivar() -> None:
    """Calcula las constantes de conveniencia que antes estaban incrustadas en este módulo."""
    h = HOMOLOGACION
    g = globals()
    g["ESTADOS_VIGENTES"] = tuple(h["estados_membresia"]["vigentes"])
    g["ESTADOS_NO_VIGENTES"] = tuple(h["estados_membresia"]["no_vigentes"])
    g["NIVEL_POR_CATEGORIA"] = dict(h["niveles"]["por_categoria"])
    g["NIVELES"] = tuple(v["nivel"] for v in sorted(h["niveles"]["catalogo"], key=lambda v: v["orden"]))
    g["FIN_EVENTO_MULTIDIA"] = {int(k): date.fromisoformat(v) for k, v in h["fin_evento_multidia"].items()}
    g["MESES_ES"] = dict(h["meses_es"])
    g["CIUDADES_CANONICAS"] = dict(h["ciudades"]["equivalencias"])
    g["SECTORES_CANONICOS"] = dict(h["sectores"]["equivalencias"])
    g["TIPOS_MEMBRESIA_CANONICOS"] = dict(h["tipos_membresia"]["equivalencias"])


# Constantes derivadas del diccionario (se declaran aquí para que los analizadores estáticos las vean).
ESTADOS_VIGENTES: tuple[str, ...] = ()
ESTADOS_NO_VIGENTES: tuple[str, ...] = ()
NIVEL_POR_CATEGORIA: dict[str, str] = {}
NIVELES: tuple[str, ...] = ()
FIN_EVENTO_MULTIDIA: dict[int, date] = {}
MESES_ES: dict[str, int] = {}
CIUDADES_CANONICAS: dict[str, str] = {}
SECTORES_CANONICOS: dict[str, str] = {}
TIPOS_MEMBRESIA_CANONICOS: dict[str, str] = {}
_derivar()

# Ventana (días tras el evento) para asignar una respuesta de encuesta a un evento.
VENTANA_ENCUESTA_DIAS: int = 2

# Ventanas de análisis (días).
VENTANA_RECIENTE_DIAS: int = 90
VENTANA_SATISFACCION_DIAS: int = 365

#: Primer mes de las series de tendencias (web/data/tendencias.json).
TENDENCIAS_DESDE: str = "2024-01"

#: Año de los informes de Zoho que solo traen el mes (p. ej. «Agosto», «Septiembre»).
ANIO_INFORMES: int = FECHA_CORTE_DEFECTO.year


@dataclass
class Configuracion:
    """Parámetros de una ejecución del pipeline."""

    dir_datos: Path = DIR_DATOS
    fecha_corte: date = FECHA_CORTE_DEFECTO
    ruta_pesos: Path = RUTA_PESOS
    dir_procesados: Path = DIR_PROCESADOS
    dir_web: Path = DIR_WEB
    semilla: int = 2026
    pesos: dict[str, Any] = field(default_factory=dict)

    def ruta_fuente(self, clave: str) -> Path:
        """Devuelve la ruta absoluta de una fuente declarada en ``FUENTES``."""
        return self.dir_datos / FUENTES[clave]

    def cargar_pesos(self) -> dict[str, Any]:
        """Lee el archivo JSON de pesos y lo deja en ``self.pesos``."""
        with open(self.ruta_pesos, encoding="utf-8") as fh:
            self.pesos = json.load(fh)
        return self.pesos
