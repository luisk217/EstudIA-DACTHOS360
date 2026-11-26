/**
 * Utilidades compartidas: creación segura de DOM, formato en español de
 * Colombia, almacenamiento tolerante a fallos y descarga de archivos.
 */

/**
 * Crea un elemento DOM. Los hijos de tipo texto se insertan como nodos de
 * texto (nunca como HTML), lo que evita inyección de contenido.
 * @param {string} etiqueta  Nombre de la etiqueta.
 * @param {Object} [attrs]   Atributos; "class", "on*" y "dataset" tienen trato especial.
 * @param {...any} hijos     Nodos, cadenas, números, arreglos o valores nulos.
 */
export function h(etiqueta, attrs = {}, ...hijos) {
  const el = document.createElement(etiqueta);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k === 'class') el.className = v;
    else if (k === 'dataset') Object.assign(el.dataset, v);
    else if (k.startsWith('on') && typeof v === 'function') el.addEventListener(k.slice(2), v);
    else if (k === 'value' || k === 'checked' || k === 'selected' || k === 'disabled') el[k] = v;
    else el.setAttribute(k, v === true ? '' : v);
  }
  agregar(el, hijos);
  return el;
}

/** Agrega hijos (aplana arreglos, ignora nulos) a un elemento. */
export function agregar(el, hijos) {
  for (const hijo of hijos.flat(Infinity)) {
    if (hijo === null || hijo === undefined || hijo === false) continue;
    el.append(hijo instanceof Node ? hijo : document.createTextNode(String(hijo)));
  }
  return el;
}

/** Vacía un elemento y le agrega los hijos indicados. */
export function reemplazar(el, ...hijos) {
  el.replaceChildren();
  return agregar(el, hijos);
}

// ---- Formato ---------------------------------------------------------------
const fmtEntero = new Intl.NumberFormat('es-CO', { maximumFractionDigits: 0 });
const fmtFecha = new Intl.DateTimeFormat('es-CO', { day: '2-digit', month: 'short', year: 'numeric', timeZone: 'UTC' });
const fmtMes = new Intl.DateTimeFormat('es-CO', { month: 'short', year: '2-digit', timeZone: 'UTC' });

/** Número entero con separador de miles (1.234). */
export const entero = (n) => (n === null || n === undefined ? 'Sin dato' : fmtEntero.format(n));

/** Número con decimales fijos y coma decimal (4,78). */
export function decimal(n, d = 1) {
  if (n === null || n === undefined || Number.isNaN(n)) return 'Sin dato';
  return n.toLocaleString('es-CO', { minimumFractionDigits: d, maximumFractionDigits: d });
}

/** Porcentaje a partir de un número ya en escala 0-100. */
export const pct = (n, d = 1) => (n === null || n === undefined ? 'Sin dato' : `${decimal(n, d)} %`);

/** Fecha AAAA-MM-DD a formato legible (25 nov 2026). */
export function fecha(iso) {
  if (!iso) return 'Sin fecha';
  const d = new Date(`${iso}T00:00:00Z`);
  return Number.isNaN(d.getTime()) ? iso : fmtFecha.format(d).replace(/\./g, '');
}

/** Mes AAAA-MM a texto corto (ene 26). */
export function mesCorto(aaaamm) {
  const d = new Date(`${aaaamm}-01T00:00:00Z`);
  return Number.isNaN(d.getTime()) ? aaaamm : fmtMes.format(d).replace(/\./g, '').replace(' de ', ' ');
}

/** Texto descriptivo de días a vencimiento (negativo = vencida). */
export function textoVencimiento(dias) {
  if (dias === null || dias === undefined) return 'Sin fecha de expiración';
  if (dias < 0) return `Vencida hace ${entero(-dias)} día${dias === -1 ? '' : 's'}`;
  if (dias === 0) return 'Vence hoy';
  return `Vence en ${entero(dias)} día${dias === 1 ? '' : 's'}`;
}

/** Normaliza texto para búsqueda sin tildes ni mayúsculas. */
export const normalizar = (s) => String(s ?? '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();

// ---- Almacenamiento tolerante a fallos --------------------------------------
/** Lee de localStorage; devuelve el valor por defecto si no está disponible. */
export function leerAlmacen(clave, defecto = null) {
  try {
    const v = window.localStorage.getItem(clave);
    return v === null ? defecto : v;
  } catch {
    return defecto;
  }
}

/** Quita una clave de localStorage; devuelve true si tuvo éxito. */
export function borrarAlmacen(clave) {
  try {
    window.localStorage.removeItem(clave);
    return true;
  } catch {
    return false;
  }
}

/**
 * Migra una vez el contenido de una clave antigua a la nueva: solo si la nueva
 * no existe y la antigua sí. Tras copiar, la antigua se elimina.
 * @returns {boolean} true si se migró algo.
 */
export function migrarClave(antigua, nueva) {
  const previo = leerAlmacen(antigua, null);
  if (previo === null) return false;
  if (leerAlmacen(nueva, null) === null && !escribirAlmacen(nueva, previo)) return false;
  borrarAlmacen(antigua);
  return true;
}

/** Claves de almacenamiento local del tablero (prefijo "dactho360"). */
export const CLAVES = { tema: 'dactho360.tema', reglas: 'dactho360.reglas.v1', filtrosAbiertos: 'dactho360.filtros' };
/** Claves heredadas de versiones anteriores (escritas "dacho360"), que se migran una vez. */
export const CLAVES_ANTIGUAS = { tema: 'dacho360.tema', reglas: 'dacho360.reglas.v1' };

/** Escribe en localStorage; devuelve true si tuvo éxito. */
export function escribirAlmacen(clave, valor) {
  try {
    window.localStorage.setItem(clave, valor);
    return true;
  } catch {
    return false;
  }
}

// ---- Descargas --------------------------------------------------------------
/** Descarga un texto como archivo en el navegador (sin servidor). */
export function descargarTexto(nombre, contenido, tipo) {
  const url = URL.createObjectURL(new Blob([contenido], { type: tipo }));
  const a = h('a', { href: url, download: nombre });
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** Escapa una celda CSV; neutraliza fórmulas (=, +, -, @) para hojas de cálculo. */
function celdaCsv(v) {
  let s = v === null || v === undefined ? '' : String(v);
  if (/^[=+\-@\t\r]/.test(s) && Number.isNaN(Number(s))) s = `'${s}`;
  return /[",\n\r;]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

/** Descarga filas (arreglo de arreglos) como CSV UTF-8 con BOM para Excel. */
export function descargarCsv(nombre, encabezados, filas) {
  const lineas = [encabezados, ...filas].map((f) => f.map(celdaCsv).join(','));
  descargarTexto(nombre, `﻿${lineas.join('\r\n')}\r\n`, 'text/csv;charset=utf-8');
}

/** Identificador corto único para reglas (la secuencia evita choques al crear muchos en el mismo milisegundo). */
let secuenciaId = 0;
export const nuevoId = () => `r${Date.now().toString(36)}${(secuenciaId++).toString(36)}${Math.random().toString(36).slice(2, 6)}`;

/** Cuenta ocurrencias de una clave sobre un arreglo. */
export function contar(arr, fn) {
  const m = new Map();
  for (const x of arr) m.set(fn(x), (m.get(fn(x)) || 0) + 1);
  return m;
}

/** Construye un enlace interno a una vista con parámetros: href('afiliados', {banda: 'Riesgo alto'}). */
export function href(vista, params = {}) {
  const q = new URLSearchParams(Object.entries(params).filter(([, v]) => v !== '' && v !== null && v !== undefined)).toString();
  return `#/${vista}${q ? `?${q}` : ''}`;
}


// ---- Ciclo de vida de las vistas --------------------------------------------
const salidas = [];
/** Registra una función que se ejecuta al abandonar la vista (destruir gráficos, quitar escuchas). */
export const alSalir = (fn) => { salidas.push(fn); };
/** Ejecuta y vacía las funciones registradas con alSalir. */
export function ejecutarSalidas() {
  while (salidas.length) { try { salidas.pop()(); } catch (e) { console.error(e); } }
}

/** Crea un elemento SVG (los hijos y atributos se asignan de forma segura). */
export function svgEl(etiqueta, attrs = {}, ...hijos) {
  const el = document.createElementNS('http://www.w3.org/2000/svg', etiqueta);
  for (const [k, v] of Object.entries(attrs)) if (v !== null && v !== undefined && v !== false) el.setAttribute(k, v);
  for (const hijo of hijos.flat()) if (hijo !== null && hijo !== undefined && hijo !== false) el.append(hijo instanceof Node ? hijo : document.createTextNode(String(hijo)));
  return el;
}

/** ¿El usuario pidió reducir el movimiento? */
export const sinMovimiento = () => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false;

/** Limita un número a un rango. */
export const acotar = (v, min, max) => Math.min(max, Math.max(min, v));

/** Suma de un arreglo de números. */
export const suma = (arr) => arr.reduce((s, x) => s + (x || 0), 0);

/** Fecha corta con mes (nov 2026) a partir de AAAA-MM-DD. */
export function fechaMes(iso) {
  return iso ? mesCorto(iso.slice(0, 7)) : 'Sin fecha';
}

/** Fecha larga (25 de noviembre de 2026) a partir de AAAA-MM-DD. */
export function fechaLarga(iso) {
  const d = new Date(`${iso}T00:00:00Z`);
  return Number.isNaN(d.getTime()) ? String(iso) : new Intl.DateTimeFormat('es-CO', { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' }).format(d);
}

/** Días entre dos fechas AAAA-MM-DD (b - a). */
export const diasEntre = (a, b) => Math.round((new Date(`${b}T00:00:00Z`) - new Date(`${a}T00:00:00Z`)) / 86400000);

/** Suma meses a un mes AAAA-MM. */
export function sumarMeses(aaaamm, n) {
  const [a, m] = aaaamm.split('-').map(Number);
  const t = a * 12 + (m - 1) + n;
  return `${Math.floor(t / 12)}-${String((t % 12) + 1).padStart(2, '0')}`;
}

/** Lista de meses AAAA-MM entre dos extremos, ambos incluidos. */
export function rangoMeses(desde, hasta) {
  const r = [];
  for (let m = desde; m <= hasta && r.length < 600; m = sumarMeses(m, 1)) r.push(m);
  return r;
}

/** Nombres de meses en texto: ['2026-10','2026-11'] -> «octubre y noviembre de 2026». */
export function mesesEnTexto(meses) {
  if (!meses.length) return '';
  const nombre = (m) => new Intl.DateTimeFormat('es-CO', { month: 'long', timeZone: 'UTC' }).format(new Date(`${m}-01T00:00:00Z`));
  const anios = [...new Set(meses.map((m) => m.slice(0, 4)))];
  const partes = meses.map((m, i) => (anios.length > 1 && (i === meses.length - 1 || meses[i + 1].slice(0, 4) !== m.slice(0, 4)) ? `${nombre(m)} de ${m.slice(0, 4)}` : nombre(m)));
  const unidos = partes.length > 1 ? `${partes.slice(0, -1).join(', ')} y ${partes.at(-1)}` : partes[0];
  return anios.length > 1 ? unidos : `${unidos} de ${anios[0]}`;
}

/** Último día (AAAA-MM-DD) de un mes AAAA-MM. */
export function ultimoDiaMes(aaaamm) {
  const [a, m] = aaaamm.split('-').map(Number);
  return `${aaaamm}-${String(new Date(Date.UTC(a, m, 0)).getUTCDate()).padStart(2, '0')}`;
}
