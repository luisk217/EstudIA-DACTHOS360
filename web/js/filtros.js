/**
 * Filtros globales y por vista.
 *
 * Hay un único estado de filtros compartido por todas las vistas. Se refleja en
 * la URL (#/resumen?banda=Riesgo alto&ejecutiva=KAM B) para poder compartir una
 * vista, y cada vista se suscribe para actualizarse en vivo. Cada vista decide
 * qué controles muestra (las demás claves se conservan en la URL).
 */
import { h, reemplazar, entero, normalizar, fecha, alSalir } from './util.js';
import { datos, BANDAS, TRAMOS_VENC } from './datos.js';
import { icono } from './iconos.js';

/** Definición de cada filtro: etiqueta, tipo y cómo obtener sus opciones. */
const unicos = (k) => [...new Set(datos.afiliadosLista.map((a) => a[k]).filter((v) => v !== null && v !== undefined && v !== ''))].sort((x, y) => String(x).localeCompare(String(y), 'es'));
export const DEF = {
  ejecutiva: { etiqueta: 'Ejecutiva', tipo: 'lista', opciones: () => unicos('ejecutiva') },
  nivel: { etiqueta: 'Nivel', tipo: 'lista', opciones: () => unicos('nivel') },
  estado: { etiqueta: 'Estado', tipo: 'lista', opciones: () => unicos('estado') },
  banda: { etiqueta: 'Banda', tipo: 'lista', opciones: () => BANDAS.map((b) => b.nombre) },
  tipo: { etiqueta: 'Tipo', tipo: 'lista', opciones: () => unicos('tipo') },
  sector: { etiqueta: 'Sector', tipo: 'lista', opciones: () => unicos('sector') },
  ciudad: { etiqueta: 'Ciudad', tipo: 'lista', opciones: () => unicos('ciudad') },
  venc: { etiqueta: 'Vencimiento', tipo: 'lista', opciones: () => TRAMOS_VENC.map((t) => ({ valor: t.id, texto: t.etiqueta })) },
  vmin: { etiqueta: 'Vence desde (días)', tipo: 'numero' },
  vmax: { etiqueta: 'Vence hasta (días)', tipo: 'numero' },
  desde: { etiqueta: 'Desde', tipo: 'fecha' },
  hasta: { etiqueta: 'Hasta', tipo: 'fecha' },
  linea: { etiqueta: 'Línea', tipo: 'lista', opciones: () => datos.eventos.por_linea.map((l) => l.clave) },
  modalidad: { etiqueta: 'Modalidad', tipo: 'lista', opciones: () => datos.eventos.por_modalidad.map((l) => l.clave) },
  q: { etiqueta: 'Búsqueda', tipo: 'texto' },
};
export const TODAS = Object.keys(DEF);
/** Filtros que se aplican a la cartera de afiliados. */
export const CARTERA = ['ejecutiva', 'nivel', 'estado', 'banda', 'tipo', 'sector', 'ciudad', 'venc', 'vmin', 'vmax'];

/** Estado actual (todas las claves siempre existen; vacío = sin filtro). */
export const f = Object.fromEntries(TODAS.map((k) => [k, '']));

let vistaId = 'resumen';
const escuchas = new Set();
/** Suscribe una función a los cambios de filtros; devuelve la función para cancelar. */
export function suscribir(fn) { escuchas.add(fn); return () => escuchas.delete(fn); }
const avisar = (origen) => escuchas.forEach((fn) => fn(origen));

export const fijarVista = (id) => { vistaId = id; };

// ---- Validación de valores que llegan por la URL --------------------------------------
function sanear(clave, valor) {
  const v = String(valor ?? '').trim().slice(0, 80);
  const tipo = DEF[clave].tipo;
  if (tipo === 'numero') return /^-?\d{1,5}$/.test(v) ? v : '';
  if (tipo === 'fecha') return /^\d{4}-\d{2}-\d{2}$/.test(v) ? v : '';
  return v;
}

/** Carga el estado desde los parámetros de la URL (al entrar a una vista). */
export function cargarDeParams(params) {
  for (const k of TODAS) f[k] = sanear(k, params.get(k));
}

/** Parámetros de URL del estado actual (solo los no vacíos). */
export function aParams({ sinBusqueda = false } = {}) {
  const p = new URLSearchParams();
  for (const k of TODAS) if (f[k] !== '' && !(sinBusqueda && k === 'q')) p.set(k, f[k]);
  return p;
}

/** Enlace (hash) a una vista conservando los filtros actuales. */
export function hashVista(id, { sinBusqueda = true, extra = {} } = {}) {
  const p = aParams({ sinBusqueda });
  for (const [k, v] of Object.entries(extra)) { if (v === '' || v === null || v === undefined) p.delete(k); else p.set(k, v); }
  const q = p.toString();
  return `#/${id}${q ? `?${q}` : ''}`;
}

function sincronizarUrl() {
  const destino = hashVista(vistaId, { sinBusqueda: false });
  if (location.hash !== destino) { try { history.replaceState(null, '', destino); } catch { /* sin efecto */ } }
}

// ---- Cambios de estado --------------------------------------------------------------
/** Fija un filtro (o varios con un objeto) y notifica. */
export function fijar(clave, valor, origen) {
  const cambios = typeof clave === 'object' ? clave : { [clave]: valor };
  let hubo = false;
  for (const [k, v] of Object.entries(cambios)) {
    const nuevo = sanear(k, v);
    if (f[k] !== nuevo) { f[k] = nuevo; hubo = true; }
  }
  if (!hubo) return;
  sincronizarUrl();
  avisar(origen);
}
/** Activa un filtro, o lo quita si ya estaba con ese valor (interacción cruzada). */
export function alternar(clave, valor) { fijar(clave, f[clave] === String(valor) ? '' : String(valor)); }
/** Alterna varios a la vez: si todos coinciden los quita, si no los fija. */
export function alternarVarios(cambios) {
  const todos = Object.entries(cambios).every(([k, v]) => f[k] === String(v));
  fijar(Object.fromEntries(Object.entries(cambios).map(([k, v]) => [k, todos ? '' : String(v)])));
}
export function limpiar(claves = TODAS) {
  fijar(Object.fromEntries(claves.map((k) => [k, ''])));
}

// ---- Aplicación de filtros a los datos --------------------------------------------------
/** ¿Un afiliado cumple los filtros de cartera? "excepto" omite algunas claves (para resaltar la selección). */
export function cumple(a, excepto = []) {
  const on = (k) => f[k] !== '' && !excepto.includes(k);
  if (on('ejecutiva') && a.ejecutiva !== f.ejecutiva) return false;
  if (on('nivel') && a.nivel !== f.nivel) return false;
  if (on('estado') && a.estado !== f.estado) return false;
  if (on('banda') && a.banda !== f.banda) return false;
  if (on('tipo') && a.tipo !== f.tipo) return false;
  if (on('sector') && a.sector !== f.sector) return false;
  if (on('ciudad') && a.ciudad !== f.ciudad) return false;
  if (on('venc')) { const t = TRAMOS_VENC.find((x) => x.id === f.venc); if (t && !t.prueba(a.dias_venc ?? null)) return false; }
  if (on('vmin') && (a.dias_venc === null || a.dias_venc < Number(f.vmin))) return false;
  if (on('vmax') && (a.dias_venc === null || a.dias_venc > Number(f.vmax))) return false;
  if (on('q')) {
    const texto = normalizar([a.id, a.sector, a.ciudad, a.tipo, a.ejecutiva].filter(Boolean).join(' '));
    if (!texto.includes(normalizar(f.q))) return false;
  }
  return true;
}
export const filtrarAfiliados = (lista = datos.afiliadosLista, excepto = []) => lista.filter((a) => cumple(a, excepto));

/** ¿Hay algún filtro de cartera activo? */
export const hayFiltrosCartera = () => CARTERA.some((k) => f[k] !== '');

/** Rango de meses (AAAA-MM) del periodo seleccionado; extremos vacíos si no hay filtro. */
export const rangoPeriodo = () => ({ desde: f.desde ? f.desde.slice(0, 7) : '', hasta: f.hasta ? f.hasta.slice(0, 7) : '' });
export function mesEnPeriodo(mes) {
  const r = rangoPeriodo();
  return (!r.desde || mes >= r.desde) && (!r.hasta || mes <= r.hasta);
}

/** Eventos que cumplen periodo, línea y modalidad (con "excepto" opcional). */
export function filtrarEventos(lista = datos.eventos.eventos, excepto = []) {
  const on = (k) => f[k] !== '' && !excepto.includes(k);
  return lista.filter((e) => {
    const fin = e.fecha_fin || e.fecha;
    if (on('desde') && fin < f.desde) return false;
    if (on('hasta') && e.fecha > f.hasta) return false;
    if (on('linea') && e.linea !== f.linea) return false;
    if (on('modalidad') && e.modalidad !== f.modalidad) return false;
    return true;
  });
}

// ---- Descripción de filtros activos ---------------------------------------------------
function textoFiltro(k) {
  const v = f[k];
  switch (k) {
    case 'venc': return `Vencimiento: ${TRAMOS_VENC.find((t) => t.id === v)?.etiqueta ?? v}`;
    case 'vmin': return `Vence desde ${v} días`;
    case 'vmax': return `Vence hasta ${v} días`;
    case 'desde': return `Desde ${fecha(v)}`;
    case 'hasta': return `Hasta ${fecha(v)}`;
    case 'q': return `Búsqueda: «${v}»`;
    default: return `${DEF[k].etiqueta}: ${v}`;
  }
}
/** Lista de filtros activos entre las claves indicadas. */
export const activos = (claves) => claves.filter((k) => f[k] !== '').map((k) => ({ clave: k, texto: textoFiltro(k) }));

// ---- Interfaz: barra de filtros ----------------------------------------------------------
const GRUPOS = [
  { titulo: 'Cartera', claves: ['ejecutiva', 'nivel', 'estado', 'banda', 'tipo', 'sector', 'ciudad'] },
  { titulo: 'Vencimiento', claves: ['venc', 'vmin', 'vmax'] },
  { titulo: 'Periodo de actividad', claves: ['desde', 'hasta'] },
  { titulo: 'Eventos', claves: ['linea', 'modalidad'] },
];

/**
 * Barra de filtros de una vista: panel plegable con controles, chips de filtros
 * activos, botón de limpiar y botón para copiar el enlace.
 * @param {{claves:string[], busqueda?:boolean, id?:string}} cfg  Claves que aplican a la vista.
 * @returns {{elemento:HTMLElement, contador:(texto:string)=>void}}
 */
export function barraFiltros({ claves, busqueda = false }) {
  const aplicables = busqueda ? [...claves, 'q'] : claves;
  const controles = new Map(); // clave -> elemento de formulario
  const contadorEl = h('span', { class: 'filtros-contador', 'aria-live': 'polite' });
  const insignia = h('span', { class: 'filtros-insignia', hidden: true });
  const chips = h('div', { class: 'chips', 'aria-live': 'polite' });
  const aviso = h('span', { class: 'solo-lectores', role: 'status' });

  const crearControl = (k) => {
    const d = DEF[k], id = `flt-${k}`;
    let el;
    if (d.tipo === 'lista') {
      const opts = d.opciones().map((o) => (typeof o === 'string' ? { valor: o, texto: o } : o));
      el = h('select', { id, onchange: (e) => fijar(k, e.target.value, 'control') },
        h('option', { value: '' }, 'Todas'), opts.map((o) => h('option', { value: o.valor }, o.texto)));
    } else if (d.tipo === 'numero') {
      let t = null;
      el = h('input', { id, type: 'number', inputmode: 'numeric', step: '1', min: '-9999', max: '9999', placeholder: 'Sin límite',
        oninput: (e) => { clearTimeout(t); t = setTimeout(() => fijar(k, e.target.value, 'control'), 250); } });
    } else if (d.tipo === 'fecha') {
      el = h('input', { id, type: 'date', min: '2025-01-01', max: '2027-12-31', onchange: (e) => fijar(k, e.target.value, 'control') });
    } else {
      let t = null;
      el = h('input', { id, type: 'search', autocomplete: 'off', placeholder: 'Código, sector, ciudad…',
        oninput: (e) => { clearTimeout(t); t = setTimeout(() => fijar(k, e.target.value, 'control'), 160); } });
    }
    controles.set(k, el);
    return h('div', { class: `campo${k === 'q' ? ' buscar' : ''}` }, h('label', { for: id }, d.etiqueta), el);
  };

  const grupos = [];
  if (busqueda) grupos.push(h('div', { class: 'grupo-busqueda' }, crearControl('q')));
  const orden = GRUPOS.flatMap((g) => g.claves).filter((k) => aplicables.includes(k) && k !== 'q');
  grupos.push(h('div', { class: 'grupo-campos' }, orden.map(crearControl)));

  /** Copia al portapapeles el enlace de la vista actual. */
  async function copiarEnlace(e) {
    const url = location.href;
    let ok = false;
    try { await navigator.clipboard.writeText(url); ok = true; } catch {
      const t = h('textarea', { style: 'position:fixed;opacity:0' }, url); document.body.append(t); t.select();
      try { ok = document.execCommand('copy'); } catch { ok = false; } t.remove();
    }
    aviso.textContent = ok ? 'Enlace copiado.' : 'No fue posible copiar; copie la dirección del navegador.';
    const b = e.currentTarget; b.classList.toggle('ok', ok); setTimeout(() => b.classList.remove('ok'), 1600);
  }

  const abierto = window.matchMedia('(min-width: 1000px)').matches || activos(aplicables).length > 0;
  const limpiarBtn = h('button', { class: 'btn btn-chico btn-limpiar', type: 'button', onclick: () => limpiar(aplicables) }, icono('limpiar'), 'Limpiar filtros');
  const detalles = h('details', { class: 'filtros-panel', open: abierto },
    h('summary', {}, icono('filtro'), h('span', { class: 'filtros-titulo' }, 'Filtros'), insignia, contadorEl, icono('chevron', { clase: 'ico chev' })),
    h('form', { class: 'filtros-cuerpo', 'aria-label': 'Filtros de la vista', onsubmit: (e) => e.preventDefault() }, grupos));
  const elemento = h('section', { class: 'filtros tarjeta-vidrio', 'aria-label': 'Filtros' },
    detalles,
    h('div', { class: 'filtros-pie' }, chips,
      h('div', { class: 'filtros-acciones' }, limpiarBtn,
        h('button', { class: 'btn btn-chico', type: 'button', onclick: copiarEnlace, title: 'Copia el enlace de esta vista con los filtros aplicados' }, icono('enlace'), 'Copiar enlace')),
      aviso));

  function refrescar() {
    for (const [k, el] of controles) { if (el !== document.activeElement || DEF[k].tipo === 'lista') el.value = f[k]; }
    const act = activos(aplicables);
    reemplazar(chips, act.length ? act.map((c) => h('button', { class: 'chip', type: 'button', 'aria-label': `Quitar filtro: ${c.texto}`, onclick: () => fijar(c.clave, '') }, c.texto, icono('cerrar', { clase: 'ico chip-x' })))
      : h('span', { class: 'chips-vacio' }, 'Sin filtros activos: se muestra toda la información.'));
    insignia.hidden = act.length === 0; insignia.textContent = String(act.length);
    limpiarBtn.disabled = act.length === 0;
    elemento.classList.toggle('con-filtros', act.length > 0);
  }
  refrescar();
  alSalir(suscribir(refrescar));
  return { elemento, contador: (texto) => { contadorEl.textContent = texto; } };
}

/** Texto estándar "N de M afiliados". */
export const textoConteo = (n, total, noun = 'afiliados') => `${entero(n)} de ${entero(total)} ${noun}`;
