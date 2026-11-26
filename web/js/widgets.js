/**
 * Piezas visuales propias en SVG/HTML: sparklines, medidores (anillo y
 * semicírculo), mapa de calor, tarjetas de gráfico, selector segmentado y
 * esqueletos de carga. Todo se construye con h()/svgEl(): sin innerHTML.
 */
import { h, svgEl, entero, sinMovimiento, acotar, reemplazar } from './util.js';
import { icono } from './iconos.js';

let secuencia = 0;
const idUnico = (p) => `${p}-${(secuencia += 1)}`;

// ---- Sparkline -------------------------------------------------------------------------------
/** Trazado suave (Catmull-Rom a Bézier) por una lista de puntos. */
function trazoSuave(pts) {
  if (pts.length < 2) return '';
  let d = `M${pts[0].x.toFixed(1)},${pts[0].y.toFixed(1)}`;
  for (let i = 0; i < pts.length - 1; i += 1) {
    const p0 = pts[i - 1] || pts[i], p1 = pts[i], p2 = pts[i + 1], p3 = pts[i + 2] || p2, t = 0.18;
    d += ` C${(p1.x + (p2.x - p0.x) * t).toFixed(1)},${(p1.y + (p2.y - p0.y) * t).toFixed(1)} ${(p2.x - (p3.x - p1.x) * t).toFixed(1)},${(p2.y - (p3.y - p1.y) * t).toFixed(1)} ${p2.x.toFixed(1)},${p2.y.toFixed(1)}`;
  }
  return d;
}

/**
 * Mini gráfico de tendencia con área en degradado y punto final.
 * @param {number[]} datos  Valores (los nulos se omiten).
 * @param {{color?:string, descripcion?:string, formato?:Function}} [opc]
 */
export function sparkline(datos, { color = 'var(--serie-1)', descripcion = 'Tendencia', formato = entero } = {}) {
  const v = datos.filter((x) => x !== null && x !== undefined);
  if (v.length < 2) return null;
  const W = 200, H = 44, pad = 4, min = Math.min(...v), max = Math.max(...v), rango = max - min || 1;
  const pts = v.map((y, i) => ({ x: pad + ((W - 2 * pad) * i) / (v.length - 1), y: H - pad - ((H - 2 * pad - 4) * (y - min)) / rango }));
  const d = trazoSuave(pts), id = idUnico('sg');
  const ultimo = pts.at(-1);
  return svgEl('svg', { class: 'spark', viewBox: `0 0 ${W} ${H}`, role: 'img', 'aria-label': `${descripcion}: de ${formato(v[0])} a ${formato(v.at(-1))} en ${v.length} periodos` },
    svgEl('defs', {}, svgEl('linearGradient', { id, x1: 0, y1: 0, x2: 0, y2: 1 },
      svgEl('stop', { offset: '0%', 'stop-color': color, 'stop-opacity': '0.35' }), svgEl('stop', { offset: '100%', 'stop-color': color, 'stop-opacity': '0' }))),
    svgEl('path', { class: 'spark-area', d: `${d} L${ultimo.x},${H} L${pts[0].x},${H} Z`, fill: `url(#${id})` }),
    svgEl('path', { class: 'spark-linea', d, stroke: color, pathLength: '1' }),
    svgEl('circle', { class: 'spark-punto', cx: ultimo.x, cy: ultimo.y, r: 3.4, stroke: color }));
}

// ---- Medidores ------------------------------------------------------------------------------------
/**
 * Medidor en anillo (0 a max) con el valor en el centro.
 * @param {{valor:number, max?:number, color?:string, texto:string, etiqueta?:string, tam?:number}} o
 */
export function medidorAnillo({ valor, max = 100, color = 'var(--primario)', texto, etiqueta = 'Medidor', tam = 64 }) {
  const r = 26, c = 2 * Math.PI * r, frac = acotar(valor / max, 0, 1);
  const arco = svgEl('circle', { class: 'anillo-valor', cx: 32, cy: 32, r, stroke: color, 'stroke-dasharray': `${c.toFixed(2)}`, 'stroke-dashoffset': sinMovimiento() ? (c * (1 - frac)).toFixed(2) : c.toFixed(2), transform: 'rotate(-90 32 32)' });
  if (!sinMovimiento()) requestAnimationFrame(() => requestAnimationFrame(() => arco.setAttribute('stroke-dashoffset', (c * (1 - frac)).toFixed(2))));
  return svgEl('svg', { class: 'anillo', viewBox: '0 0 64 64', width: tam, height: tam, role: 'img', 'aria-label': `${etiqueta}: ${texto}` },
    svgEl('circle', { class: 'anillo-pista', cx: 32, cy: 32, r }), arco,
    svgEl('text', { x: 32, y: 36.5, 'text-anchor': 'middle', class: 'anillo-texto' }, texto));
}

/**
 * Medidor semicircular con zonas de color y aguja (p. ej. NPS de -100 a 100).
 * @param {{valor:number, min:number, max:number, zonas:Array<{hasta:number,color:string}>, texto:string, etiqueta?:string}} o
 */
export function medidorSemi({ valor, min = -100, max = 100, zonas, texto, etiqueta = 'Medidor', ancho = 150 }) {
  const cx = 80, cy = 78, R = 62, ancla = (v) => Math.PI * (1 - (v - min) / (max - min));
  const punto = (v, r = R) => [cx + r * Math.cos(ancla(v)), cy - r * Math.sin(ancla(v))];
  let desde = min;
  const arcos = zonas.map((z) => {
    const [x0, y0] = punto(desde), [x1, y1] = punto(z.hasta);
    const d = `M${x0.toFixed(1)},${y0.toFixed(1)} A${R},${R} 0 0 1 ${x1.toFixed(1)},${y1.toFixed(1)}`;
    desde = z.hasta;
    return svgEl('path', { d, class: 'semi-zona', stroke: z.color });
  });
  const [ax, ay] = punto(acotar(valor, min, max), R - 12);
  return svgEl('svg', { class: 'semi', viewBox: '0 0 160 96', width: ancho, role: 'img', 'aria-label': `${etiqueta}: ${texto}` },
    ...arcos,
    svgEl('line', { class: 'semi-aguja', x1: cx, y1: cy, x2: ax.toFixed(1), y2: ay.toFixed(1) }),
    svgEl('circle', { class: 'semi-eje', cx, cy, r: 5 }),
    svgEl('text', { x: 14, y: 92, class: 'semi-extremo' }, String(min)), svgEl('text', { x: 146, y: 92, class: 'semi-extremo', 'text-anchor': 'end' }, `+${max}`),
    svgEl('title', {}, `${etiqueta}: ${texto}`));
}

// ---- Mapa de calor --------------------------------------------------------------------------------
/**
 * Mapa de calor como tabla (accesible): filas × columnas, intensidad por valor.
 * @param {{filas:Array<{clave:string, etiqueta:string, valores:number[]}>, columnas:string[], formato?:Function, unidad?:string, onClic?:(fila:string, columna:number)=>void, seleccion?:string|null, tituloFila?:string}} o
 */
export function mapaCalor({ filas, columnas, claves = [], formato = entero, unidad = 'asistentes', onClic, seleccion = null, tituloFila = 'Línea' }) {
  const todos = filas.flatMap((f) => f.valores);
  const max = Math.max(1, ...todos);
  const celda = (f, v, j) => {
    const i = v / max, tip = `${f.etiqueta} · ${columnas[j]}: ${formato(v)} ${unidad}`;
    const contenido = [h('span', { class: 'celda-valor' }, v ? formato(v) : '·')];
    const props = { class: `celda${i > 0.5 ? ' intensa' : ''}${seleccion === f.clave ? ' sel' : ''}`, style: `--i:${(v ? 0.1 + 0.9 * i : 0).toFixed(3)}`, 'data-tip': tip, 'aria-label': tip };
    return h('td', {}, onClic ? h('button', { ...props, type: 'button', onclick: () => onClic(f.clave, j) }, contenido) : h('span', { ...props }, contenido));
  };
  return h('div', { class: 'mapa-calor-envoltura' },
    h('div', { class: 'scroll-x' }, h('table', { class: 'mapa-calor' },
      h('caption', { class: 'solo-lectores' }, `Mapa de calor de ${unidad} por ${tituloFila.toLowerCase()} y mes`),
      h('thead', {}, h('tr', {}, h('th', { scope: 'col' }, tituloFila), columnas.map((c) => h('th', { scope: 'col' }, c)), h('th', { scope: 'col', class: 'num' }, 'Total'))),
      h('tbody', {}, filas.map((f) => h('tr', {}, h('th', { scope: 'row' }, f.etiqueta), f.valores.map((v, j) => celda(f, v, j)), h('td', { class: 'num total' }, formato(f.valores.reduce((s, x) => s + x, 0)))))))),
    h('div', { class: 'mapa-escala', 'aria-hidden': 'true' }, h('span', {}, 'Menos'), h('span', { class: 'mapa-degradado' }), h('span', {}, `Más (hasta ${formato(max)})`)));
}

// ---- Tarjeta de gráfico y controles --------------------------------------------------------------------
/**
 * Tarjeta con encabezado (ícono, título, subtítulo y acciones) y un cuerpo.
 * @returns {{elemento:HTMLElement, cuerpo:HTMLElement}}
 */
export function tarjetaGrafico({ titulo, subtitulo, icono: ico, acciones, clase = '', id }) {
  const idTitulo = id ? `${id}-t` : idUnico('tg');
  const cuerpo = h('div', { class: 'tarjeta-cuerpo' });
  const elemento = h('section', { class: `tarjeta tarjeta-grafico ${clase}`, 'aria-labelledby': idTitulo },
    h('header', { class: 'tarjeta-cab' },
      ico ? h('span', { class: 'tarjeta-icono' }, icono(ico)) : null,
      h('div', { class: 'tarjeta-titulos' }, h('h2', { id: idTitulo }, titulo), subtitulo ? h('p', { class: 'tarjeta-sub' }, subtitulo) : null),
      acciones ? h('div', { class: 'tarjeta-acciones' }, acciones) : null),
    cuerpo);
  return { elemento, cuerpo };
}

/** Selector segmentado (grupo de botones con aria-pressed). */
export function segmentado({ etiqueta, opciones, valor, alCambiar }) {
  let actual = valor;
  const botones = opciones.map((o) => h('button', { type: 'button', class: 'seg-btn', 'aria-pressed': String(o.valor === actual), onclick: () => {
    if (actual === o.valor) return;
    actual = o.valor; botones.forEach((b, i) => b.setAttribute('aria-pressed', String(opciones[i].valor === actual))); alCambiar(actual);
  } }, o.texto));
  return h('div', { class: 'segmentado', role: 'group', 'aria-label': etiqueta }, botones);
}

// ---- Esqueletos de carga ---------------------------------------------------------------------------------
const bloque = (clase) => h('div', { class: `esqueleto ${clase}`, 'aria-hidden': 'true' });
/** Esqueleto de una vista (cabecera, indicadores y dos gráficos) mientras cargan los datos. */
export function esqueletoVista() {
  const kpis = h('div', { class: 'rejilla c4' }, [0, 1, 2, 3].map(() => h('div', { class: 'tarjeta' }, bloque('esq-linea corta'), bloque('esq-valor'), bloque('esq-linea'), bloque('esq-spark'))));
  const graficos = h('div', { class: 'rejilla c2' }, [0, 1].map(() => h('div', { class: 'tarjeta' }, bloque('esq-linea media'), bloque('esq-grafico'))));
  return h('div', { class: 'esqueleto-vista', role: 'status', 'aria-live': 'polite' },
    h('span', { class: 'solo-lectores' }, 'Cargando datos…'),
    bloque('esq-titulo'), bloque('esq-linea larga'), kpis, graficos);
}

/** Anima un número desde su valor previo hasta el nuevo (respeta prefers-reduced-motion). */
export function animarNumero(el, desde, hasta, formato = entero, ms = 700) {
  if (sinMovimiento() || desde === hasta || !Number.isFinite(hasta)) { el.textContent = formato(hasta); return; }
  const t0 = performance.now();
  const paso = (t) => {
    const p = Math.min(1, (t - t0) / ms), e = 1 - (1 - p) ** 3;
    el.textContent = formato(desde + (hasta - desde) * e);
    if (p < 1 && el.isConnected) requestAnimationFrame(paso); else el.textContent = formato(hasta);
  };
  requestAnimationFrame(paso);
}

export { reemplazar };
