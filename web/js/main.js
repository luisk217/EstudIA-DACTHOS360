/**
 * Punto de entrada: tema, navegación, enrutador por hash y estados de carga.
 * Rutas relativas (sirve en subcarpetas como GitHub Pages): #/resumen, #/afiliados?banda=Riesgo alto, ...
 */
import { h, reemplazar, leerAlmacen, escribirAlmacen, migrarClave, CLAVES, CLAVES_ANTIGUAS, ejecutarSalidas, fechaLarga } from './util.js';
import { cargarDatos, datos } from './datos.js';
import { cargarReglas } from './reglas.js';
import { cargando, errorCarga } from './componentes.js';
import { icono } from './iconos.js';
import { cargarDeParams, fijarVista, hashVista, suscribir } from './filtros.js';
import { vistaResumen } from './vistas/resumen.js';
import { vistaAfiliados } from './vistas/afiliados.js';
import { vistaEjecutivas } from './vistas/ejecutivas.js';
import { vistaEventos } from './vistas/eventos.js';
import { vistaEncuestas } from './vistas/encuestas.js';
import { vistaAlertas } from './vistas/alertas.js';
import { vistaMetodologia } from './vistas/metodologia.js';

/** Rutas de la aplicación; "icono" es el nombre en iconos.js. */
const VISTAS = [
  { id: 'resumen', titulo: 'Resumen ejecutivo', vista: vistaResumen, icono: 'resumen' },
  { id: 'afiliados', titulo: 'Afiliados', vista: vistaAfiliados, icono: 'afiliados' },
  { id: 'ejecutivas', titulo: 'Ejecutivas', vista: vistaEjecutivas, icono: 'ejecutivas' },
  { id: 'eventos', titulo: 'Eventos y participación', vista: vistaEventos, icono: 'eventos' },
  { id: 'encuestas', titulo: 'Encuestas y NPS', vista: vistaEncuestas, icono: 'encuestas' },
  { id: 'alertas', titulo: 'Alertas', vista: vistaAlertas, icono: 'alertas' },
  { id: 'metodologia', titulo: 'Metodología', vista: vistaMetodologia, icono: 'metodologia' },
];

const principal = document.getElementById('principal');
const nav = document.getElementById('nav-lateral');
let listo = false;

// ---- Tema (automático, claro u oscuro) --------------------------------------------
// Claves «dactho360.*»; si existen las antiguas («dacho360.*») se migran una sola vez.
migrarClave(CLAVES_ANTIGUAS.tema, CLAVES.tema);
const TEMAS = [{ id: 'auto', texto: 'Tema automático', icono: 'auto' }, { id: 'claro', texto: 'Tema claro', icono: 'claro' }, { id: 'oscuro', texto: 'Tema oscuro', icono: 'oscuro' }];
let tema = leerAlmacen(CLAVES.tema, 'auto');
// Parámetro opcional ?tema=claro|oscuro (útil para capturas); no se guarda.
const temaUrl = new URLSearchParams(location.search).get('tema');
if (TEMAS.some((t) => t.id === temaUrl)) tema = temaUrl;
if (!TEMAS.some((t) => t.id === tema)) tema = 'auto';
const etiquetaTema = h('span', { class: 'btn-tema-texto' });
const botonTema = h('button', { class: 'btn btn-chico btn-tema', type: 'button', onclick: () => {
  tema = TEMAS[(TEMAS.findIndex((t) => t.id === tema) + 1) % TEMAS.length].id;
  escribirAlmacen(CLAVES.tema, tema); aplicarTema();
} });
const botonTemaMovil = h('button', { class: 'btn btn-chico btn-icono', type: 'button', onclick: () => botonTema.click() });
function aplicarTema() {
  if (tema === 'auto') document.documentElement.removeAttribute('data-tema'); else document.documentElement.setAttribute('data-tema', tema);
  const t = TEMAS.find((x) => x.id === tema);
  botonTema.setAttribute('aria-label', `Cambiar tema de color. Actual: ${t.texto.toLowerCase()}`);
  botonTemaMovil.setAttribute('aria-label', `Cambiar tema de color. Actual: ${t.texto.toLowerCase()}`);
  reemplazar(botonTema, icono(t.icono), h('span', {}, t.texto));
  reemplazar(botonTemaMovil, icono(t.icono));
  window.dispatchEvent(new Event('dactho:tema'));
}

// ---- Menú ---------------------------------------------------------------------------
const telon = h('div', { class: 'telon', hidden: true, onclick: () => alternarMenu(false) });
const botonMenu = h('button', { class: 'btn btn-chico btn-icono', type: 'button', 'aria-expanded': 'false', 'aria-controls': 'nav-lateral', 'aria-label': 'Abrir el menú', onclick: () => alternarMenu() }, icono('menu'));
function alternarMenu(abrir) {
  const abierto = abrir ?? !nav.classList.contains('abierto');
  nav.classList.toggle('abierto', abierto);
  telon.hidden = !abierto;
  document.body.classList.toggle('menu-abierto', abierto);
  botonMenu.setAttribute('aria-expanded', String(abierto));
  botonMenu.setAttribute('aria-label', abierto ? 'Cerrar el menú' : 'Abrir el menú');
}
document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && nav.classList.contains('abierto')) { alternarMenu(false); botonMenu.focus(); } });

const notaCorte = h('p', { class: 'nota' }, 'Datos anonimizados.');
reemplazar(nav,
  h('a', { class: 'marca', href: '#/resumen' },
    h('span', { class: 'marca-logo' }, icono('logo', { clase: 'ico' })),
    h('span', { class: 'marca-textos' }, h('span', { class: 'marca-nombre' }, 'DACTHO 360'), h('span', { class: 'marca-sub' }, 'Tablero Integral de Gestión de Afiliados · ACTHO'))),
  h('nav', { 'aria-label': 'Secciones' }, h('ul', { class: 'menu' }, VISTAS.map((v) => h('li', {}, h('a', { href: `#/${v.id}`, 'data-vista': v.id }, icono(v.icono), h('span', {}, v.titulo)))))),
  h('div', { class: 'nav-pie' }, botonTema, notaCorte));
document.getElementById('barra-movil').append(
  h('a', { class: 'marca-movil', href: '#/resumen' }, h('span', { class: 'marca-logo' }, icono('logo', { clase: 'ico' })), h('span', { class: 'marca-nombre' }, 'DACTHO 360')),
  h('div', { class: 'barra-acciones' }, botonTemaMovil, botonMenu));
document.body.append(telon);
aplicarTema();

/** Los enlaces del menú conservan los filtros activos al cambiar de vista. */
function actualizarEnlaces() {
  nav.querySelectorAll('a[data-vista]').forEach((a) => a.setAttribute('href', hashVista(a.dataset.vista)));
}
suscribir(actualizarEnlaces);

// ---- Enrutador ------------------------------------------------------------------------
function rutaActual() {
  const [ruta, consulta = ''] = location.hash.replace(/^#\/?/, '').split('?');
  return { vista: VISTAS.find((v) => v.id === ruta) || VISTAS[0], params: new URLSearchParams(consulta) };
}

function mostrar() {
  if (!listo) return;
  const { vista, params } = rutaActual();
  ejecutarSalidas(); // destruye los gráficos y las suscripciones de la vista anterior
  cargarDeParams(params);
  fijarVista(vista.id);
  actualizarEnlaces();
  nav.querySelectorAll('[data-vista]').forEach((a) => (a.dataset.vista === vista.id ? a.setAttribute('aria-current', 'page') : a.removeAttribute('aria-current')));
  document.title = `${vista.titulo} · DACTHO 360`;
  alternarMenu(false);
  principal.setAttribute('aria-busy', 'true');
  principal.classList.remove('entrando');
  try {
    reemplazar(principal, vista.vista(params));
  } catch (err) {
    console.error(err);
    reemplazar(principal, errorCarga(`Ocurrió un problema al mostrar esta sección: ${err.message}`, mostrar));
  }
  void principal.offsetWidth; // reinicia la animación de entrada
  principal.classList.add('entrando');
  principal.removeAttribute('aria-busy');
  window.scrollTo(0, 0);
  document.getElementById('titulo-vista')?.focus({ preventScroll: true });
}

async function iniciar() {
  reemplazar(principal, cargando());
  principal.setAttribute('aria-busy', 'true');
  try {
    if (location.protocol === 'file:') throw new Error('Abra el tablero desde un servidor local (por ejemplo, python -m http.server dentro de la carpeta web), porque el navegador bloquea la lectura de archivos de datos desde file://.');
    await cargarDatos();
    cargarReglas();
    notaCorte.textContent = `Datos anonimizados. Corte: ${fechaLarga(datos.fechaCorte)}.`;
    listo = true;
    mostrar();
  } catch (err) {
    console.error(err);
    reemplazar(principal, errorCarga(err.message, iniciar));
    principal.removeAttribute('aria-busy');
  }
}

window.addEventListener('hashchange', mostrar);
iniciar();
