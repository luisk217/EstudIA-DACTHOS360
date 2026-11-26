"""Esquema del modelo relacional normalizado de DACTHO 360.

Es la única fuente de verdad del modelo: de aquí salen la verificación de tipos, claves y
relaciones (``validacion.verificar_modelo``), la escritura de las tablas (``exportacion``) y el
diccionario de datos (``docs/DICCIONARIO_DATOS.md``, generado por ``eda/generar_documentos.py``).

Convenciones: una entidad por tabla, columnas en ``snake_case`` sin tildes, una fila por hecho
(formato tidy), claves naturales legibles (``EMP-0001``, ``EV01``) y catálogos pequeños
(``dim_nivel``, ``dim_ciudad``...) con la lista editable de ``config/homologacion.json``.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

TIPOS = ("texto", "entero", "decimal", "fecha", "booleano")


@dataclass(frozen=True)
class Columna:
    """Una columna del modelo."""

    nombre: str
    tipo: str
    descripcion: str
    nulo: bool = True
    #: Clave foránea ``(tabla_padre, columna_padre)``.
    fk: tuple[str, str] | None = None
    #: ``error`` rompe la integridad; ``aviso`` es un hallazgo esperado y explicado (p. ej. empresas no afiliadas).
    fk_severidad: str = "error"
    fk_explicacion: str = ""
    #: Sección de ``homologacion.json`` cuyo catálogo define los valores válidos.
    dominio: str | None = None
    #: Lista cerrada de valores válidos (cuando no hay sección en el diccionario).
    valores: tuple[str, ...] | None = None
    rango: tuple[float, float] | None = None


@dataclass(frozen=True)
class Tabla:
    """Una tabla del modelo."""

    nombre: str
    clase: str  # catalogo | dimension | hecho
    descripcion: str
    clave: tuple[str, ...]
    columnas: tuple[Columna, ...]
    grano: str = ""
    fuente: str = ""

    def nombres(self) -> list[str]:
        return [c.nombre for c in self.columnas]


def C(nombre: str, tipo: str, desc: str, nulo: bool = True, **kw: Any) -> Columna:
    """Atajo para declarar columnas."""
    return Columna(nombre, tipo, desc, nulo, **kw)


_NO_AFILIADA = ("Empresas que asisten, responden o aparecen en informes sin tener registro en el CRM: no afiliadas, o afiliadas "
                "cuyo alta aún no se cargó. Es un hallazgo de cobertura, no un error de captura.")

TABLAS: tuple[Tabla, ...] = (
    # ------------------------------------------------------------------ catálogos
    Tabla("dim_nivel", "catalogo", "Niveles de la oferta 2027 y su equivalente en las categorías de Zoho.", ("nivel",), (
        C("nivel", "texto", "Nivel 2027 (Conectar, Crecer o Liderar).", False),
        C("categoria_zoho", "texto", "Categoría que usa Zoho CRM para ese nivel.", False),
        C("orden", "entero", "Orden de menor a mayor nivel.", False),
        C("descripcion", "texto", "Descripción del nivel.", False),
    ), grano="un nivel", fuente="config/homologacion.json (niveles)"),
    Tabla("dim_estado_membresia", "catalogo", "Estados de la membresía en Zoho y si cuentan como afiliación vigente.", ("estado_membresia",), (
        C("estado_membresia", "texto", "Estado de la membresía.", False),
        C("es_vigente", "booleano", "Verdadero si el estado cuenta como afiliado vigente (Activo, Periodo de Gracia, Pronto a Expirar).", False),
        C("orden", "entero", "Orden de presentación.", False),
    ), grano="un estado", fuente="config/homologacion.json (estados_membresia)"),
    Tabla("dim_tipo_membresia", "catalogo", "Tipos de afiliado (Empresa, Consultora, Persona natural, Universidad, Estudiante).", ("tipo_membresia",), (
        C("tipo_membresia", "texto", "Tipo de afiliado homologado.", False),
    ), grano="un tipo", fuente="config/homologacion.json (tipos_membresia)"),
    Tabla("dim_sector", "catalogo", "Sectores económicos homologados.", ("sector",), (
        C("sector", "texto", "Sector económico homologado.", False),
    ), grano="un sector", fuente="config/homologacion.json (sectores)"),
    Tabla("dim_ciudad", "catalogo", "Ciudades homologadas (sin tildes dañadas ni variantes de escritura).", ("ciudad",), (
        C("ciudad", "texto", "Nombre canónico de la ciudad.", False),
    ), grano="una ciudad", fuente="config/homologacion.json (ciudades)"),
    Tabla("dim_modalidad", "catalogo", "Modalidades de los eventos.", ("modalidad",), (
        C("modalidad", "texto", "Presencial, Virtual o Híbrido.", False),
    ), grano="una modalidad", fuente="config/homologacion.json (modalidades)"),
    Tabla("dim_linea_evento", "catalogo", "Líneas de la oferta 2027 y formatos transversales a los que se homologan los eventos.", ("linea",), (
        C("linea", "texto", "Línea o formato.", False),
        C("tipo", "texto", "«linea» o «formato transversal».", False, valores=("linea", "formato transversal")),
        C("descripcion", "texto", "Descripción.", False),
    ), grano="una línea o formato", fuente="config/homologacion.json (lineas_evento)"),
    Tabla("dim_nivel_cargo", "catalogo", "Niveles de cargo de las personas que asisten.", ("nivel_cargo",), (
        C("nivel_cargo", "texto", "Nivel de cargo homologado.", False),
        C("orden", "entero", "Orden de mayor a menor jerarquía.", False),
    ), grano="un nivel de cargo", fuente="config/homologacion.json (niveles_cargo)"),
    # ------------------------------------------------------------------ dimensiones
    Tabla("dim_ejecutiva", "dimension", "Ejecutivas de cuenta (KAM) anonimizadas, más la etiqueta «Sin asignar».", ("ejecutiva_id",), (
        C("ejecutiva_id", "texto", "Identificador (EJ-A, EJ-B... o EJ-SIN_ASIGNAR).", False),
        C("ejecutiva", "texto", "Etiqueta anonimizada de la ejecutiva (KAM A...).", False),
        C("es_asignada", "booleano", "Falso para «Sin asignar» (cuentas sin ejecutiva o canceladas que se reasignaron).", False),
    ), grano="una ejecutiva", fuente="CRM, informes de renovaciones, afiliaciones y oportunidades"),
    Tabla("dim_afiliado", "dimension", "Empresas del CRM de Zoho, una fila por código de empresa, ya consolidadas y homologadas.", ("empresa_id",), (
        C("empresa_id", "texto", "Código anonimizado de la empresa (EMP-0000); reemplaza al NIT.", False),
        C("id_registro_crm", "texto", "Identificador del registro en la exportación del CRM."),
        C("ejecutiva_id", "texto", "Ejecutiva propietaria de la cuenta.", False, fk=("dim_ejecutiva", "ejecutiva_id")),
        C("naturaleza", "texto", "Tipo de empresa (nacional privada, multinacional...).", dominio="naturaleza_empresa"),
        C("tipo_compania", "texto", "Tipo de compañía en Zoho (Asociado, Cliente...)."),
        C("tipo_membresia", "texto", "Tipo de afiliado homologado.", fk=("dim_tipo_membresia", "tipo_membresia")),
        C("tipo_membresia_zoho", "texto", "Tipo de membresía tal como aparece en Zoho (limpio, sin homologar)."),
        C("categoria_membresia", "texto", "Categoría de Zoho (Estándar, Premium, Elite...) cuando la columna trae una categoría válida.", dominio="categorias_membresia"),
        C("nivel", "texto", "Nivel 2027 (Conectar, Crecer, Liderar); nulo si no se puede inferir.", fk=("dim_nivel", "nivel")),
        C("estado_membresia", "texto", "Estado de la membresía; nulo si el CRM no lo trae.", fk=("dim_estado_membresia", "estado_membresia")),
        C("estado_registro", "texto", "Estado del registro en el CRM (Activo o Inactivo).", dominio="estados_registro_crm"),
        C("sector", "texto", "Sector económico homologado.", fk=("dim_sector", "sector"), fk_severidad="aviso",
          fk_explicacion="Sector que aún no está en el catálogo de config/homologacion.json."),
        C("subsector", "texto", "Subsector económico homologado."),
        C("tipo_consultora", "texto", "Tipo de consultora (solo afiliados consultoras)."),
        C("ciudad", "texto", "Ciudad (la del registro o, si falta, la de facturación) homologada.", fk=("dim_ciudad", "ciudad"), fk_severidad="aviso",
          fk_explicacion="Ciudad que aún no está en el catálogo de config/homologacion.json: agréguela o añada su variante a las equivalencias."),
        C("ciudad_facturacion", "texto", "Ciudad de facturación homologada.", fk=("dim_ciudad", "ciudad"), fk_severidad="aviso",
          fk_explicacion="Ciudad que aún no está en el catálogo de config/homologacion.json."),
        C("departamento", "texto", "Departamento homologado.", dominio="departamentos"),
        C("region", "texto", "Región comercial homologada.", dominio="regiones"),
        C("pais", "texto", "País de facturación homologado.", dominio="paises"),
        C("tamano", "texto", "Tamaño de la empresa (Micro, Pequeña, Mediana, Grande).", dominio="tamanos"),
        C("rango_empleados", "texto", "Rango de empleados con formato único (1-50, 51-200...).", dominio="rangos_empleados"),
        C("es_independiente", "booleano", "Verdadero si el afiliado es independiente."),
        C("pct_mujeres", "decimal", "Porcentaje de mujeres en la compañía (0 a 100).", rango=(0, 100)),
        C("fecha_afiliacion", "fecha", "Fecha de afiliación; nula si venía vacía o con una fecha imposible."),
        C("fecha_expiracion", "fecha", "Fecha de expiración de la afiliación."),
        C("miembro_desde", "fecha", "Fecha «Miembro desde» del CRM."),
        C("vinculado_comunidades", "booleano", "Verdadero si el CRM marca vinculación a comunidades o hay miembros en alguna.", False),
        C("cantidad_miembros", "entero", "Cantidad de miembros declarados.", rango=(0, 100000)),
        C("persona_principal_id", "texto", "Persona de contacto principal del afiliado (anonimizada).", fk=("dim_persona", "persona_id")),
        C("fecha_afiliacion_invalida", "booleano", "Bandera: la fecha de afiliación original era posterior al corte y se descartó.", False),
        C("fechas_incoherentes", "booleano", "Bandera: la expiración es anterior a la afiliación.", False),
        C("estado_inconsistente", "booleano", "Bandera: el registro figura Activo pero la membresía está cancelada, expirada o inactiva.", False),
        C("categoria_invalida", "booleano", "Bandera: la columna de categoría traía un tipo («Empresas», «Consultoras»...) en lugar de una categoría.", False),
    ), grano="una empresa del CRM", fuente="1. Base de datos de afiliados (Zoho CRM) y 5. Base de datos afiliados ACTHO"),
    Tabla("dim_persona", "dimension", "Personas anonimizadas que aparecen en asistencia, encuestas o como contacto principal.", ("persona_id",), (
        C("persona_id", "texto", "Código anonimizado de la persona (P-00000).", False),
        C("fuentes", "texto", "Fuentes donde aparece, separadas por «;» (asistencia, encuesta, afiliado_principal).", False),
        C("n_empresas_asociadas", "entero", "Cantidad de empresas distintas con las que figura en asistencia o encuestas.", False, rango=(0, 100)),
        C("multiples_empresas", "booleano", "Verdadero si figura con más de una empresa (cambio de empresa o código reutilizado).", False),
    ), grano="una persona", fuente="asistencia, encuestas, base de afiliados y nuevos afiliados"),
    Tabla("dim_evento", "dimension", "Catálogo de eventos 2026 homologado con la oferta 2027.", ("evento_id",), (
        C("evento_id", "texto", "Identificador del evento (EV01...).", False),
        C("evento_n", "entero", "Número del evento en la hoja GENERAL y en la homologación.", False),
        C("hoja_origen", "texto", "Hoja del libro de asistencia de la que sale la lista de asistentes.", False),
        C("nombre", "texto", "Nombre del evento.", False),
        C("fecha_inicio", "fecha", "Primer día del evento.", False),
        C("fecha_fin", "fecha", "Último día del evento (igual al primero en eventos de un día).", False),
        C("mes", "texto", "Mes de inicio en formato AAAA-MM.", False),
        C("linea", "texto", "Línea o formato de la oferta 2027; nulo si no está clasificado.", fk=("dim_linea_evento", "linea")),
        C("experiencia", "texto", "Experiencia o detalle dentro de la línea."),
        C("modalidad", "texto", "Modalidad (Presencial, Virtual, Híbrido).", fk=("dim_modalidad", "modalidad")),
        C("tiene_asistentes", "booleano", "Falso si la hoja del evento no trae lista de asistentes.", False),
    ), grano="un evento", fuente="2. Registros de participación (hoja HOMOLOGACION y GENERAL)"),
    # ------------------------------------------------------------------ hechos
    Tabla("fact_asistencia", "hecho", "Un registro por inscripción de una persona a un evento, con marcas de validez.", ("asistencia_id",), (
        C("asistencia_id", "texto", "Identificador de la fila (AS-00001...), asignado en el orden de las hojas.", False),
        C("evento_id", "texto", "Evento al que corresponde la hoja.", False, fk=("dim_evento", "evento_id")),
        C("persona_id", "texto", "Persona inscrita.", fk=("dim_persona", "persona_id")),
        C("empresa_id", "texto", "Empresa de la persona.", False, fk=("dim_afiliado", "empresa_id"), fk_severidad="aviso", fk_explicacion=_NO_AFILIADA),
        C("nivel_cargo", "texto", "Nivel de cargo; nulo cuando la fuente dice «Sin dato».", fk=("dim_nivel_cargo", "nivel_cargo")),
        C("ciudad", "texto", "Ciudad declarada (solo algunas hojas la traen).", fk=("dim_ciudad", "ciudad"), fk_severidad="aviso",
          fk_explicacion="Ciudad de las hojas de asistencia que aún no está en el catálogo."),
        C("con_costo", "booleano", "Verdadero si el cupo fue con costo."),
        C("autoriza_datos", "booleano", "Verdadero si autorizó el tratamiento de datos."),
        C("registro_ubicacion", "booleano", "Estado de registro de ubicación principal (Sí o No), cuando la hoja lo trae."),
        C("marca_fuente", "entero", "Marca numérica de la primera columna de la hoja («Tipo de asistente» o «Afiliado»); su significado no está documentado en la fuente."),
        C("es_agendado", "booleano", "Verdadero si el registro está solo agendado; no cuenta como asistencia.", False),
        C("es_duplicado", "booleano", "Verdadero si repite a la misma persona en el mismo evento.", False),
        C("es_valida", "booleano", "Verdadero si cuenta como asistencia (no agendada ni duplicada).", False),
    ), grano="una inscripción de una persona a un evento", fuente="2. Registros de participación (una hoja por evento)"),
    Tabla("fact_encuesta", "hecho", "Una fila por respuesta de las tres encuestas de eventos, con satisfacción 1 a 5 y NPS.", ("respuesta_id",), (
        C("respuesta_id", "texto", "Identificador de la respuesta (EP-0001, EV-0001, PE-0001).", False),
        C("fuente", "texto", "Encuesta de origen.", False, dominio="origenes_encuesta"),
        C("modalidad", "texto", "Modalidad del evento que se evalúa.", fk=("dim_modalidad", "modalidad")),
        C("fecha_respuesta", "fecha", "Fecha en que se completó la respuesta.", False),
        C("persona_id", "texto", "Persona que responde.", fk=("dim_persona", "persona_id")),
        C("empresa_id", "texto", "Empresa de quien responde; nula si no se pudo identificar.", fk=("dim_afiliado", "empresa_id"), fk_severidad="aviso", fk_explicacion=_NO_AFILIADA),
        C("ciudad", "texto", "Ciudad declarada.", fk=("dim_ciudad", "ciudad"), fk_severidad="aviso", fk_explicacion="Ciudad escrita a mano que aún no está en el catálogo."),
        C("evento_id", "texto", "Evento 2026 inferido por fecha y modalidad; nulo si no hay uno compatible.", fk=("dim_evento", "evento_id")),
        C("metodo_evento", "texto", "Cómo se asignó (o por qué no se asignó) el evento.", False),
        C("metodo_asignacion_empresa", "texto", "Cómo se identificó la empresa en la encuesta."),
        C("afiliado_declarado", "booleano", "Verdadero si la persona dice ser afiliada (solo la encuesta post-evento lo pregunta)."),
        C("satisfaccion", "decimal", "Satisfacción media de 1 a 5 de los aspectos calificados.", rango=(1, 5)),
        C("nps_puntaje", "entero", "Recomendación de 0 a 10 (solo la encuesta post-evento).", rango=(0, 10)),
        C("nps_categoria", "texto", "Promotor, Pasivo o Detractor.", valores=("Promotor", "Pasivo", "Detractor")),
    ), grano="una respuesta de encuesta", fuente="3. Encuestas y NPS (presencial, virtual y post-evento)"),
    Tabla("fact_encuesta_aspecto", "hecho", "Calificaciones de 1 a 5 por aspecto de cada respuesta (columnas pasadas a filas).", ("respuesta_id", "aspecto"), (
        C("respuesta_id", "texto", "Respuesta calificada.", False, fk=("fact_encuesta", "respuesta_id")),
        C("aspecto", "texto", "Aspecto calificado.", False, dominio="aspectos_encuesta"),
        C("calificacion", "entero", "Calificación de 1 a 5.", False, rango=(1, 5)),
    ), grano="un aspecto de una respuesta", fuente="3. Encuestas y NPS"),
    Tabla("fact_encuesta_tema", "hecho", "Temas de interés marcados en la encuesta post-evento (opciones cerradas, sin texto libre).", ("respuesta_id", "tema"), (
        C("respuesta_id", "texto", "Respuesta que marcó el tema.", False, fk=("fact_encuesta", "respuesta_id")),
        C("tema", "texto", "Tema marcado.", False),
    ), grano="un tema marcado en una respuesta", fuente="3. Encuestas y NPS (post-evento, pregunta 18)"),
    Tabla("fact_comunidad_afiliado", "hecho", "Miembros de cada empresa en cada comunidad de ACTHO (columnas pasadas a filas).", ("empresa_id", "comunidad"), (
        C("empresa_id", "texto", "Empresa afiliada.", False, fk=("dim_afiliado", "empresa_id")),
        C("comunidad", "texto", "Comunidad (HR Estratégico, Mujeres HR...).", False),
        C("miembros", "entero", "Cantidad de miembros de la empresa en la comunidad.", False, rango=(1, 1000)),
    ), grano="una empresa en una comunidad", fuente="1. Base de datos de afiliados"),
    Tabla("fact_renovacion", "hecho", "Renovaciones facturadas en los últimos dos meses del informe de Zoho.", ("renovacion_id",), (
        C("renovacion_id", "texto", "Identificador (RN-001...).", False),
        C("empresa_id", "texto", "Empresa que renovó.", False, fk=("dim_afiliado", "empresa_id"), fk_severidad="aviso", fk_explicacion=_NO_AFILIADA),
        C("ejecutiva_id", "texto", "Ejecutiva de la cuenta.", False, fk=("dim_ejecutiva", "ejecutiva_id")),
        C("mes_factura", "fecha", "Primer día del mes de la factura de renovación."),
        C("fecha_expiracion_nueva", "fecha", "Nueva fecha de expiración tras renovar."),
    ), grano="una renovación", fuente="5. Informe Renovaciones - Últimos 2 meses"),
    Tabla("fact_afiliacion_nueva", "hecho", "Afiliaciones nuevas de agosto a octubre: negocios ganados y lista de nuevos afiliados, unidos por empresa.", ("afiliacion_id",), (
        C("afiliacion_id", "texto", "Identificador (AF-001...).", False),
        C("empresa_id", "texto", "Empresa nueva.", False, fk=("dim_afiliado", "empresa_id"), fk_severidad="aviso",
          fk_explicacion="Empresa en el informe de nuevos afiliados que no aparece en la exportación del CRM: desfase de captura entre ambos reportes."),
        C("ejecutiva_id", "texto", "Ejecutiva que cerró el negocio; nula si la empresa solo figura en la lista de nuevos.", fk=("dim_ejecutiva", "ejecutiva_id")),
        C("fecha_cierre", "fecha", "Fecha de cierre del negocio."),
        C("categoria_membresia", "texto", "Categoría de membresía del negocio, tal como la digitó el CRM."),
        C("nivel", "texto", "Nivel 2027 inferido de la categoría.", fk=("dim_nivel", "nivel")),
        C("mes_lista_nuevos", "fecha", "Primer día del mes en que figura en la lista de nuevos afiliados."),
        C("persona_principal_id", "texto", "Afiliado principal de la lista de nuevos.", fk=("dim_persona", "persona_id")),
        C("en_informe_afiliaciones", "booleano", "Verdadero si figura en el informe de afiliaciones de los últimos dos meses.", False),
        C("en_lista_nuevos", "booleano", "Verdadero si figura en la lista de nuevos afiliados de agosto y septiembre.", False),
    ), grano="una afiliación nueva", fuente="5. Afiliaciones - Últimos 2 meses y Nuevos Afiliados AGO-SEP"),
    Tabla("fact_oportunidad_ganada", "hecho", "Oportunidades ganadas por ejecutiva según el informe de Zoho.", ("oportunidad_id",), (
        C("oportunidad_id", "texto", "Identificador (OP-001...).", False),
        C("empresa_id", "texto", "Empresa de la oportunidad.", False, fk=("dim_afiliado", "empresa_id"), fk_severidad="aviso", fk_explicacion=_NO_AFILIADA),
        C("ejecutiva_id", "texto", "Ejecutiva propietaria del trato.", False, fk=("dim_ejecutiva", "ejecutiva_id")),
    ), grano="una oportunidad ganada", fuente="5. Estados oportunidades ganadas por KAM"),
    Tabla("fact_score_afiliado", "hecho", "Variables, puntos, riesgo y banda del score de cada afiliado vigente a la fecha de corte.", ("empresa_id",), (
        C("empresa_id", "texto", "Afiliado vigente puntuado.", False, fk=("dim_afiliado", "empresa_id")),
        C("fecha_corte", "fecha", "Fecha de corte del cálculo.", False),
        C("dias_vencimiento", "entero", "Días entre el corte y la expiración (negativo si ya venció)."),
        C("dias_afiliacion", "entero", "Días desde la afiliación hasta el corte."),
        C("antiguedad_anios", "decimal", "Antigüedad en años.", rango=(0, 100)),
        C("asistencias", "entero", "Asistencias válidas de 2026 hasta el corte.", False, rango=(0, 100000)),
        C("asistencias_90d", "entero", "Asistencias en los 90 días previos al último evento registrado.", False, rango=(0, 100000)),
        C("eventos_distintos", "entero", "Eventos distintos con asistencia.", False, rango=(0, 100)),
        C("personas_distintas", "entero", "Personas distintas que asistieron.", False, rango=(0, 100000)),
        C("ultima_asistencia", "fecha", "Fecha de la última asistencia."),
        C("dias_ultima_asistencia", "entero", "Días desde la última asistencia."),
        C("n_respuestas", "entero", "Respuestas de encuesta en los últimos 12 meses.", False, rango=(0, 100000)),
        C("satisfaccion", "decimal", "Satisfacción media de 1 a 5 en los últimos 12 meses.", rango=(1, 5)),
        C("nps_minimo", "entero", "Calificación mínima de recomendación en los últimos 12 meses.", rango=(0, 10)),
        C("detractor", "booleano", "Verdadero si alguna calificación de recomendación fue de 0 a 6.", False),
        C("renovo_recientemente", "booleano", "Verdadero si renovó en los últimos dos meses.", False),
        C("puntos", "decimal", "Puntos de riesgo acumulados.", False, rango=(0, 1000)),
        C("riesgo", "decimal", "Riesgo de 0 a 100.", False, rango=(0, 100)),
        C("salud", "decimal", "Salud de 0 a 100 (100 menos el riesgo).", False, rango=(0, 100)),
        C("banda", "texto", "Saludable, Atención o Riesgo alto.", False, valores=("Saludable", "Atención", "Riesgo alto")),
        C("accion", "texto", "Acción sugerida derivada del factor principal.", False),
    ), grano="un afiliado vigente", fuente="Resultado del score (pipeline/score.py)"),
    Tabla("fact_score_factor", "hecho", "Factores que explican el score de cada afiliado, ordenados por puntos.", ("empresa_id", "orden"), (
        C("empresa_id", "texto", "Afiliado puntuado.", False, fk=("fact_score_afiliado", "empresa_id")),
        C("orden", "entero", "Posición del factor (1 es el que más pesa).", False, rango=(1, 50)),
        C("codigo", "texto", "Código del factor.", False),
        C("puntos", "decimal", "Puntos que aporta al riesgo (negativos si lo reducen).", False),
        C("texto", "texto", "Explicación en español.", False),
    ), grano="un factor de un afiliado", fuente="Resultado del score (pipeline/score.py)"),
)

#: Tablas por nombre.
ESQUEMA: dict[str, Tabla] = {t.nombre: t for t in TABLAS}

#: Tablas de control que acompañan al modelo (bitácoras, no entidades).
CONTROLES: dict[str, str] = {
    "control_rechazos": "Filas de las fuentes que se descartaron, con su ubicación y motivo (pruebas, duplicados del CRM, filas sin código de empresa).",
    "control_huerfanos": "Valores de clave foránea que no existen en la tabla padre, con la cantidad de filas afectadas y su severidad.",
    "control_integridad": "Una fila por relación entre tablas: filas del hijo, nulos, huérfanas y severidad.",
    "control_calidad": "Métricas antes y después de la limpieza por fuente: filas, columnas, nulos, duplicados y anomalías corregidas.",
}


def orden_de_carga() -> list[str]:
    """Orden topológico: los padres antes que los hijos (catálogos, dimensiones y hechos)."""
    pendientes = {t.nombre: {c.fk[0] for c in t.columnas if c.fk and c.fk[0] != t.nombre} for t in TABLAS}
    orden: list[str] = []
    while pendientes:
        listos = sorted(n for n, deps in pendientes.items() if not (deps - set(orden)))
        if not listos:  # ciclo: dim_afiliado y dim_persona se referencian en un solo sentido, así que no debería ocurrir
            orden += sorted(pendientes)
            break
        orden += listos
        for n in listos:
            del pendientes[n]
    return orden


def a_markdown() -> str:
    """Diccionario de datos del modelo en Markdown (lo usa ``eda/generar_documentos.py``)."""
    from . import config  # noqa: PLC0415 (evita el ciclo al importar)

    h = config.HOMOLOGACION
    out: list[str] = []
    for t in TABLAS:
        pk = ", ".join(f"`{c}`" for c in t.clave)
        out.append(f"### `{t.nombre}`\n")
        out.append(f"{t.descripcion} Grano: {t.grano}. Clave primaria: {pk}. Fuente: {t.fuente}.\n")
        out.append("| Columna | Tipo | Nulos | Descripción | Relación o dominio |")
        out.append("|---|---|---|---|---|")
        for c in t.columnas:
            rel = ""
            if c.fk:
                rel = f"Clave foránea a `{c.fk[0]}.{c.fk[1]}`" + (" (aviso si no existe)" if c.fk_severidad == "aviso" else "")
            elif c.dominio:
                n = len(config.catalogo(h[c.dominio]))
                rel = f"Catálogo `{c.dominio}` ({n} valores)"
            elif c.valores:
                rel = "Valores: " + ", ".join(c.valores)
            elif c.rango:
                rel = f"Rango {c.rango[0]:g} a {c.rango[1]:g}"
            nulo = "no" if (not c.nulo or c.nombre in t.clave) else "sí"
            out.append(f"| `{c.nombre}` | {c.tipo} | {nulo} | {c.descripcion} | {rel} |")
        out.append("")
    return "\n".join(out)
