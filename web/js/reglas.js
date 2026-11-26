/**
 * Motor de reglas de alerta: catálogo de campos y operadores, evaluación sobre
 * afiliados, plantillas, persistencia en localStorage e importación/exportación.
 *
 * Modelo de una regla:
 *   { id, nombre, descripcion, activa, severidad: 'alta'|'media'|'baja',
 *     ambito: null | 'KAM B' (ejecutiva), condiciones: [{ conector, campo, op, valor }] }
 * "conector" ('Y' | 'O') une cada condición con la anterior (se ignora en la
 * primera). La Y tiene precedencia sobre la O, como en lógica booleana.
 */
import { datos, BANDAS } from './datos.js';
import { nuevoId, leerAlmacen, escribirAlmacen, migrarClave, CLAVES, CLAVES_ANTIGUAS } from './util.js';

const CLAVE = CLAVES.reglas;
/** Nombre del formato de exportación; se sigue aceptando el antiguo («dacho360-reglas»). */
export const FORMATO = 'dactho360-reglas';
const FORMATOS_ACEPTADOS = [FORMATO, 'dacho360-reglas'];
export const SEVERIDADES = [
  { id: 'alta', etiqueta: 'Alta' },
  { id: 'media', etiqueta: 'Media' },
  { id: 'baja', etiqueta: 'Baja' },
];

// ---- Operadores por tipo de campo ---------------------------------------------
export const OPERADORES = {
  num: [
    { id: 'eq', etiqueta: 'es igual a', valor: 1 }, { id: 'ne', etiqueta: 'es distinto de', valor: 1 },
    { id: 'lt', etiqueta: 'es menor que', valor: 1 }, { id: 'le', etiqueta: 'es menor o igual que', valor: 1 },
    { id: 'gt', etiqueta: 'es mayor que', valor: 1 }, { id: 'ge', etiqueta: 'es mayor o igual que', valor: 1 },
    { id: 'entre', etiqueta: 'está entre', valor: 2 },
    { id: 'vacio', etiqueta: 'no tiene dato', valor: 0 }, { id: 'novacio', etiqueta: 'tiene dato', valor: 0 },
  ],
  enum: [
    { id: 'es', etiqueta: 'es', valor: 1 }, { id: 'noes', etiqueta: 'no es', valor: 1 },
    { id: 'uno', etiqueta: 'es uno de', valor: 'multi' }, { id: 'ninguno', etiqueta: 'no es ninguno de', valor: 'multi' },
  ],
  bool: [
    { id: 'verdadero', etiqueta: 'es sí', valor: 0 }, { id: 'falso', etiqueta: 'es no', valor: 0 },
  ],
};

let memoCampos = { lista: null, largo: -1, campos: null };

/** Campos disponibles. Las opciones de los campos de lista salen de los datos cargados (se memorizan por lista). */
export function campos() {
  const A = datos.afiliadosLista ?? [];
  if (memoCampos.lista === A && memoCampos.largo === A.length) return memoCampos.campos;
  const unicos = (k) => [...new Set(A.map((a) => a[k]).filter((v) => v !== null && v !== undefined))].sort((x, y) => String(x).localeCompare(String(y), 'es'));
  const lista = [
    { id: 'banda', etiqueta: 'Banda de riesgo', tipo: 'enum', opciones: BANDAS.map((b) => b.nombre) },
    { id: 'riesgo', etiqueta: 'Riesgo (0 a 100)', tipo: 'num' },
    { id: 'salud', etiqueta: 'Salud (0 a 100)', tipo: 'num' },
    { id: 'dias_venc', etiqueta: 'Días a vencimiento (negativo si ya venció)', tipo: 'num' },
    { id: 'estado', etiqueta: 'Estado de membresía', tipo: 'enum', opciones: unicos('estado') },
    { id: 'nivel', etiqueta: 'Nivel', tipo: 'enum', opciones: unicos('nivel') },
    { id: 'ejecutiva', etiqueta: 'Ejecutiva', tipo: 'enum', opciones: unicos('ejecutiva') },
    { id: 'tipo', etiqueta: 'Tipo de afiliado', tipo: 'enum', opciones: unicos('tipo') },
    { id: 'sector', etiqueta: 'Sector', tipo: 'enum', opciones: unicos('sector') },
    { id: 'tamano', etiqueta: 'Tamaño de empresa', tipo: 'enum', opciones: unicos('tamano') },
    { id: 'ciudad', etiqueta: 'Ciudad', tipo: 'enum', opciones: unicos('ciudad') },
    { id: 'asist', etiqueta: 'Asistencias en 2026', tipo: 'num' },
    { id: 'asist_90d', etiqueta: 'Asistencias en el último trimestre registrado', tipo: 'num' },
    { id: 'eventos', etiqueta: 'Eventos distintos con asistencia', tipo: 'num' },
    { id: 'personas', etiqueta: 'Personas distintas que asistieron', tipo: 'num' },
    { id: 'dias_ult_asist', etiqueta: 'Días desde la última asistencia', tipo: 'num' },
    { id: 'sat', etiqueta: 'Satisfacción promedio (1 a 5)', tipo: 'num' },
    { id: 'n_resp', etiqueta: 'Número de respuestas de encuesta', tipo: 'num' },
    { id: 'nps_min', etiqueta: 'Calificación de recomendación más baja (0 a 10)', tipo: 'num' },
    { id: 'antig_anios', etiqueta: 'Antigüedad (años)', tipo: 'num' },
    { id: 'comunidad', etiqueta: 'Pertenece a una comunidad', tipo: 'bool' },
    { id: 'renovo_reciente', etiqueta: 'Renovó en los últimos 2 meses', tipo: 'bool' },
  ];
  memoCampos = { lista: A, largo: A.length, campos: lista };
  return lista;
}
const campoPor = (id) => campos().find((c) => c.id === id);
const operadorPor = (tipo, id) => OPERADORES[tipo].find((o) => o.id === id);

// ---- Evaluación ---------------------------------------------------------------
/** Convierte el valor de una condición a número; vacío o ausente da NaN (Number('') sería 0 y daría falsos positivos). */
const aNumero = (x) => (x === null || x === undefined || (typeof x === 'string' && !x.trim()) ? NaN : Number(x));

/** Evalúa una condición sobre un afiliado. Los datos ausentes nunca cumplen comparaciones numéricas. */
export function cumpleCondicion(af, c) {
  const v = af[c.campo];
  const nulo = v === null || v === undefined;
  const n = aNumero(c.valor);
  switch (c.op) {
    case 'vacio': return nulo;
    case 'novacio': return !nulo;
    case 'eq': return !nulo && v === n;
    case 'ne': return !nulo && !Number.isNaN(n) && v !== n;
    case 'lt': return !nulo && v < n;
    case 'le': return !nulo && v <= n;
    case 'gt': return !nulo && v > n;
    case 'ge': return !nulo && v >= n;
    case 'entre': return !nulo && Array.isArray(c.valor) && v >= aNumero(c.valor[0]) && v <= aNumero(c.valor[1]);
    case 'es': return v === c.valor;
    case 'noes': return v !== c.valor;
    case 'uno': return Array.isArray(c.valor) && c.valor.includes(v);
    case 'ninguno': return Array.isArray(c.valor) && !c.valor.includes(v);
    case 'verdadero': return v === true;
    case 'falso': return v !== true;
    default: return false;
  }
}

/** Evalúa una regla completa (ámbito + condiciones con Y/O) sobre un afiliado. */
export function cumpleRegla(af, regla) {
  if (regla.ambito && af.ejecutiva !== regla.ambito) return false;
  if (!regla.condiciones?.length) return false;
  // Se agrupa en bloques separados por O; dentro de cada bloque todo debe cumplirse (Y).
  const bloques = [[]];
  regla.condiciones.forEach((c, i) => {
    if (i > 0 && c.conector === 'O') bloques.push([]);
    bloques[bloques.length - 1].push(c);
  });
  return bloques.some((b) => b.every((c) => cumpleCondicion(af, c)));
}

/** Devuelve los afiliados que activan la regla. */
export const evaluar = (regla, afiliados = datos.afiliadosLista) => afiliados.filter((a) => cumpleRegla(a, regla));

// ---- Descripción legible ------------------------------------------------------
function textoValor(c) {
  if (c.op === 'vacio' || c.op === 'novacio' || c.op === 'verdadero' || c.op === 'falso') return '';
  if (c.op === 'entre') return Array.isArray(c.valor) ? `${c.valor[0]} y ${c.valor[1]}` : '';
  if (Array.isArray(c.valor)) return c.valor.join(', ');
  return String(c.valor ?? '');
}

/** Redacta una condición en español, p. ej. «Banda de riesgo es Riesgo alto». */
export function describirCondicion(c) {
  const campo = campoPor(c.campo);
  if (!campo) return 'Condición desconocida';
  const op = operadorPor(campo.tipo, c.op);
  return `${campo.etiqueta} ${op ? op.etiqueta : c.op} ${textoValor(c)}`.trim();
}

/** Redacta la regla completa. */
export function describirRegla(r) {
  const partes = r.condiciones.map((c, i) => `${i > 0 ? (c.conector === 'O' ? ' O ' : ' Y ') : ''}${describirCondicion(c)}`).join('');
  return `${r.ambito ? `Ejecutiva ${r.ambito}: ` : ''}${partes || 'Sin condiciones'}`;
}

// ---- Validación y saneamiento ------------------------------------------------
/** Revisa una regla y devuelve la lista de problemas en español (vacía si es válida). */
export function validarRegla(r) {
  const errores = [];
  if (!r.nombre || !r.nombre.trim()) errores.push('Escriba un nombre para la regla.');
  if (!r.condiciones || !r.condiciones.length) errores.push('Agregue al menos una condición.');
  (r.condiciones || []).forEach((c, i) => {
    const n = i + 1, campo = campoPor(c.campo);
    if (!campo) { errores.push(`Condición ${n}: el campo no es válido.`); return; }
    const op = operadorPor(campo.tipo, c.op);
    if (!op) { errores.push(`Condición ${n}: el operador no es válido para ese campo.`); return; }
    if (op.valor === 1 && (c.valor === '' || c.valor === null || c.valor === undefined || (campo.tipo === 'num' && Number.isNaN(Number(c.valor))))) errores.push(`Condición ${n}: indique un valor.`);
    if (op.valor === 2 && (!Array.isArray(c.valor) || c.valor.some((x) => x === '' || Number.isNaN(Number(x))))) errores.push(`Condición ${n}: indique los dos límites del rango.`);
    if (op.valor === 'multi' && (!Array.isArray(c.valor) || !c.valor.length)) errores.push(`Condición ${n}: elija al menos una opción.`);
  });
  return errores;
}

/** Copia solo los campos conocidos de un objeto externo (importación) y valida su forma. */
export function sanearRegla(x) {
  if (!x || typeof x !== 'object') return null;
  const conds = Array.isArray(x.condiciones) ? x.condiciones.slice(0, 20).map((c) => ({
    conector: c && c.conector === 'O' ? 'O' : 'Y',
    campo: String(c?.campo ?? ''), op: String(c?.op ?? ''),
    valor: Array.isArray(c?.valor) ? c.valor.slice(0, 50).map((v) => (typeof v === 'number' ? v : String(v))) : (typeof c?.valor === 'number' ? c.valor : String(c?.valor ?? '')),
  })) : [];
  const regla = {
    id: nuevoId(),
    nombre: String(x.nombre ?? '').slice(0, 120),
    descripcion: String(x.descripcion ?? '').slice(0, 500),
    activa: x.activa !== false,
    severidad: SEVERIDADES.some((s) => s.id === x.severidad) ? x.severidad : 'media',
    ambito: typeof x.ambito === 'string' && x.ambito ? x.ambito.slice(0, 60) : null,
    condiciones: conds,
  };
  return validarRegla(regla).length ? null : regla;
}

// ---- Plantillas -----------------------------------------------------------------
const cond = (campo, op, valor, conector = 'Y') => ({ conector, campo, op, valor });
export const PLANTILLAS = [
  { nombre: 'Riesgo alto con vencimiento en menos de 60 días', descripcion: 'Cuentas críticas que requieren contacto inmediato. Puede limitarse a una ejecutiva.', severidad: 'alta', ambito: null,
    condiciones: [cond('banda', 'es', 'Riesgo alto'), cond('dias_venc', 'lt', 60)] },
  { nombre: 'Sin asistencia en el último año', descripcion: 'Afiliados vigentes sin ninguna asistencia a eventos en 2026.', severidad: 'media', ambito: null,
    condiciones: [cond('asist', 'eq', 0)] },
  { nombre: 'Vigente con fecha de expiración vencida', descripcion: 'Estado vigente en el CRM, pero con fecha de expiración ya pasada: revisar o regularizar.', severidad: 'alta', ambito: null,
    condiciones: [cond('dias_venc', 'lt', 0), cond('estado', 'uno', ['Activo', 'Periodo de Gracia', 'Pronto a Expirar'])] },
  { nombre: 'Vence en 30 días y sin asistencia reciente', descripcion: 'Renovación próxima sin participación en el último trimestre registrado.', severidad: 'alta', ambito: null,
    condiciones: [cond('dias_venc', 'entre', [0, 30]), cond('asist_90d', 'eq', 0)] },
  { nombre: 'Satisfacción baja', descripcion: 'Promedio de satisfacción inferior a 4,2 sobre 5 o alguna calificación de recomendación de 6 o menos.', severidad: 'media', ambito: null,
    condiciones: [cond('sat', 'lt', 4.2), cond('nps_min', 'le', 6, 'O')] },
  { nombre: 'Afiliación nueva sin participación', descripcion: 'Menos de 3 meses de antigüedad y ninguna asistencia: oportunidad de bienvenida.', severidad: 'baja', ambito: null,
    condiciones: [cond('antig_anios', 'lt', 0.25), cond('asist', 'eq', 0)] },
  { nombre: 'Sin ejecutiva asignada', descripcion: 'Cuentas vigentes sin responsable comercial.', severidad: 'media', ambito: null,
    condiciones: [cond('ejecutiva', 'es', 'Sin asignar')] },
];

/** Crea una regla nueva a partir de una plantilla (o en blanco). */
export function reglaDesdePlantilla(p) {
  return { id: nuevoId(), nombre: p?.nombre ?? '', descripcion: p?.descripcion ?? '', activa: true, severidad: p?.severidad ?? 'media', ambito: p?.ambito ?? null,
    condiciones: (p?.condiciones ?? [cond('banda', 'es', 'Riesgo alto')]).map((c) => structuredClone(c)) };
}

// ---- Persistencia -----------------------------------------------------------------
/** Estado de las reglas: se guarda en localStorage cuando está disponible. */
export const almacen = { reglas: [], persistente: true, ultimoError: null };
const escuchas = new Set();
export const alCambiar = (fn) => { escuchas.add(fn); return () => escuchas.delete(fn); };

/** Carga las reglas guardadas; la primera vez siembra tres plantillas activas. */
export function cargarReglas() {
  // Migración única desde la clave antigua («dacho360.reglas.v1») a «dactho360.reglas.v1».
  migrarClave(CLAVES_ANTIGUAS.reglas, CLAVE);
  const crudo = leerAlmacen(CLAVE, null);
  if (crudo === null) {
    // Sin dato guardado (o almacenamiento no disponible): se siembran ejemplos.
    almacen.reglas = PLANTILLAS.slice(0, 3).map(reglaDesdePlantilla);
    almacen.persistente = guardarReglas();
    return;
  }
  try {
    const datosGuardados = JSON.parse(crudo);
    // Se vuelve a sanear lo guardado: el almacenamiento local también es una entrada no confiable.
    almacen.reglas = (Array.isArray(datosGuardados) ? datosGuardados : []).map((r) => {
      const limpia = sanearRegla(r);
      return limpia ? { ...limpia, id: typeof r.id === 'string' && r.id ? r.id.slice(0, 40) : limpia.id } : null;
    }).filter(Boolean);
    almacen.persistente = true;
  } catch {
    almacen.reglas = [];
    almacen.ultimoError = 'Las reglas guardadas estaban dañadas y se descartaron.';
  }
}

/** Guarda en localStorage y avisa a los suscriptores. Devuelve true si persistió. */
export function guardarReglas() {
  const ok = escribirAlmacen(CLAVE, JSON.stringify(almacen.reglas));
  almacen.persistente = ok;
  escuchas.forEach((fn) => fn());
  return ok;
}

export function guardarRegla(regla) {
  const i = almacen.reglas.findIndex((r) => r.id === regla.id);
  if (i >= 0) almacen.reglas[i] = regla; else almacen.reglas.push(regla);
  return guardarReglas();
}
export function eliminarRegla(id) { almacen.reglas = almacen.reglas.filter((r) => r.id !== id); return guardarReglas(); }
export function duplicarRegla(id) {
  const o = almacen.reglas.find((r) => r.id === id);
  if (!o) return null;
  const copia = { ...structuredClone(o), id: nuevoId(), nombre: `${o.nombre} (copia)` };
  almacen.reglas.push(copia);
  guardarReglas();
  return copia;
}

// ---- Exportación e importación JSON ------------------------------------------------
export function exportarReglasJson() {
  return JSON.stringify({ formato: FORMATO, version: 1, exportado: new Date().toISOString(), reglas: almacen.reglas.map(({ id, ...resto }) => resto) }, null, 2);
}

/** Importa reglas desde texto JSON. Devuelve {importadas, descartadas} o lanza Error con mensaje en español. */
export function importarReglasJson(texto) {
  let obj;
  try { obj = JSON.parse(texto); } catch { throw new Error('El archivo no es un JSON válido.'); }
  const lista = Array.isArray(obj) ? obj : obj && FORMATOS_ACEPTADOS.includes(obj.formato) ? obj.reglas : null;
  if (!Array.isArray(lista)) throw new Error('El archivo no tiene el formato de reglas de DACTHO 360.');
  const validas = lista.slice(0, 200).map(sanearRegla).filter(Boolean);
  almacen.reglas.push(...validas);
  guardarReglas();
  return { importadas: validas.length, descartadas: lista.length - validas.length };
}

// ---- Resumen para vistas -------------------------------------------------------------
/** Evalúa todas las reglas activas y devuelve id de afiliado -> reglas que activa. */
export function reglasPorAfiliado(afiliados = datos.afiliadosLista) {
  const mapa = new Map();
  for (const r of almacen.reglas.filter((x) => x.activa)) {
    for (const a of evaluar(r, afiliados)) {
      if (!mapa.has(a.id)) mapa.set(a.id, []);
      mapa.get(a.id).push(r);
    }
  }
  return mapa;
}
