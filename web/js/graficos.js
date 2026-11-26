/**
 * Gráficos ligeros sin dependencias (HTML, CSS y SVG).
 * Todos muestran el valor numérico como texto, de modo que el color nunca es
 * el único portador de significado, y son legibles por lectores de pantalla.
 */
import { h } from './util.js';
import { bandaInfo, BANDAS } from './datos.js';

const NS = 'http://www.w3.org/2000/svg';
const svg = (tag, attrs = {}, ...hijos) => {
  const el = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
  for (const hijo of hijos) if (hijo) el.append(hijo);
  return el;
};

/** Símbolo propio de cada banda (círculo, triángulo, rombo) para no depender del color. */
export function simboloBanda(nombre) {
  const tipo = bandaInfo(nombre).simbolo;
  const forma = {
    circulo: () => svg('circle', { cx: 5, cy: 5, r: 4.5 }),
    triangulo: () => svg('polygon', { points: '5,0.5 9.8,9.5 0.2,9.5' }),
    rombo: () => svg('polygon', { points: '5,0 10,5 5,10 0,5' }),
  }[tipo]();
  return svg('svg', { viewBox: '0 0 10 10', 'aria-hidden': 'true', focusable: 'false' }, forma);
}

/** Insignia de banda: símbolo + nombre. */
export function insigniaBanda(nombre) {
  return h('span', { class: `insignia ${bandaInfo(nombre).clase}` }, simboloBanda(nombre), nombre);
}

/**
 * Barras horizontales como lista.
 * @param {Array<{etiqueta:string, valor:number, texto?:string, variante?:string}>} items
 * @param {{max?:number}} [opc]
 */
export function barrasH(items, opc = {}) {
  const max = opc.max ?? Math.max(1, ...items.map((i) => i.valor || 0));
  return h('ul', { class: 'barras' }, items.map((i) => h('li', { class: 'barra-fila' },
    h('span', { class: 'etq' }, i.etiqueta),
    h('span', { class: 'barra-pista', 'aria-hidden': 'true' },
      h('span', { class: `barra-relleno ${i.variante || ''}`, style: `width:${Math.max(0, ((i.valor || 0) / max) * 100)}%` })),
    h('span', { class: 'val' }, i.texto ?? String(i.valor)))));
}

/**
 * Barra apilada con leyenda numérica.
 * @param {Array<{etiqueta:string, valor:number, seg:string}>} segmentos  seg = clase CSS (seg-ok, ...)
 */
export function apilada(segmentos, descripcion) {
  const total = segmentos.reduce((s, x) => s + x.valor, 0) || 1;
  return h('div', {},
    h('div', { class: 'apilada', role: 'img', 'aria-label': descripcion },
      segmentos.filter((s) => s.valor > 0).map((s) => h('span', { class: s.seg, style: `width:${(s.valor / total) * 100}%`, title: `${s.etiqueta}: ${s.valor}` }))),
    h('ul', { class: 'leyenda' }, segmentos.map((s) => h('li', {},
      h('span', { class: `muestra ${s.seg}` }), `${s.etiqueta}: `, h('strong', {}, `${s.valor}`),
      ` (${((s.valor / total) * 100).toLocaleString('es-CO', { maximumFractionDigits: 1 })} %)`))));
}

/** Atajo: barra apilada por bandas a partir de un objeto {banda: n}. */
export function apiladaBandas(porBanda, descripcion) {
  return apilada(BANDAS.map((b) => ({ etiqueta: b.nombre, valor: porBanda[b.nombre] || 0, seg: b.seg })), descripcion);
}

/**
 * Columnas verticales en SVG con etiquetas de valor sobre cada columna.
 * @param {Array<{etiqueta:string, valor:number}>} items
 */
export function columnas(items, { descripcion, formato = (v) => String(v), alto = 220 } = {}) {
  const w = Math.max(320, items.length * 54), pad = { l: 8, r: 8, t: 22, b: 30 };
  const max = Math.max(1, ...items.map((i) => i.valor));
  const paso = (w - pad.l - pad.r) / items.length, ancho = Math.min(36, paso * 0.62);
  const raiz = svg('svg', { class: 'col-svg', viewBox: `0 0 ${w} ${alto}`, role: 'img', 'aria-label': descripcion, style: `min-width:${Math.min(w, 520)}px` });
  raiz.append(svg('line', { class: 'eje', x1: pad.l, x2: w - pad.r, y1: alto - pad.b, y2: alto - pad.b }));
  items.forEach((it, i) => {
    const hgt = ((alto - pad.t - pad.b) * it.valor) / max, x = pad.l + paso * i + (paso - ancho) / 2, y = alto - pad.b - hgt;
    raiz.append(svg('rect', { class: 'col', x, y, width: ancho, height: Math.max(hgt, 1), rx: 3 }));
    const v = svg('text', { class: 'val', x: x + ancho / 2, y: y - 5, 'text-anchor': 'middle' }); v.textContent = formato(it.valor);
    const e = svg('text', { x: x + ancho / 2, y: alto - pad.b + 15, 'text-anchor': 'middle' }); e.textContent = it.etiqueta;
    raiz.append(v, e);
  });
  return h('div', { class: 'scroll-x' }, raiz);
}

/**
 * Línea con puntos en SVG (p. ej. satisfacción por mes). Los valores nulos se omiten.
 * @param {Array<{etiqueta:string, valor:number|null}>} items
 */
export function linea(items, { descripcion, min, max, formato = (v) => String(v), alto = 220 } = {}) {
  const w = Math.max(360, items.length * 48), pad = { l: 36, r: 12, t: 20, b: 30 };
  const raiz = svg('svg', { class: 'col-svg', viewBox: `0 0 ${w} ${alto}`, role: 'img', 'aria-label': descripcion, style: 'min-width:420px' });
  const paso = (w - pad.l - pad.r) / Math.max(1, items.length - 1);
  const yDe = (v) => pad.t + (alto - pad.t - pad.b) * (1 - (v - min) / (max - min));
  for (let k = 0; k <= 4; k += 1) {
    const v = min + ((max - min) * k) / 4, y = yDe(v);
    raiz.append(svg('line', { class: 'rejilla-h', x1: pad.l, x2: w - pad.r, y1: y, y2: y }));
    const t = svg('text', { x: pad.l - 6, y: y + 4, 'text-anchor': 'end' }); t.textContent = formato(v); raiz.append(t);
  }
  const pts = items.map((it, i) => ({ ...it, x: pad.l + paso * i, y: it.valor === null ? null : yDe(it.valor) }));
  const validos = pts.filter((p) => p.y !== null);
  raiz.append(svg('polyline', { class: 'lin', points: validos.map((p) => `${p.x},${p.y}`).join(' ') }));
  pts.forEach((p, i) => {
    if (p.y !== null) {
      raiz.append(svg('circle', { class: 'pto', cx: p.x, cy: p.y, r: 4 }));
      const v = svg('text', { class: 'val', x: p.x, y: p.y - 9, 'text-anchor': 'middle' }); v.textContent = formato(p.valor); raiz.append(v);
    }
    if (items.length <= 14 || i % 2 === 0) {
      const e = svg('text', { x: p.x, y: alto - pad.b + 15, 'text-anchor': 'middle' }); e.textContent = p.etiqueta; raiz.append(e);
    }
  });
  return h('div', { class: 'scroll-x' }, raiz);
}

/** Medidor 0 a 100 de salud con las tres zonas de banda y una marca de posición. */
export function medidorSalud(salud, umbralAtencion, umbralRiesgo) {
  // Salud = 100 - riesgo. Riesgo alto: salud <= 100 - umbralRiesgo.
  const zonaRiesgo = 100 - umbralRiesgo, zonaAtencion = umbralRiesgo - umbralAtencion, zonaOk = umbralAtencion;
  return h('div', { class: 'medidor', role: 'img', 'aria-label': `Salud ${salud} de 100` },
    h('span', { class: 'seg-riesgo', style: `width:${zonaRiesgo}%` }),
    h('span', { class: 'seg-aviso', style: `width:${zonaAtencion}%` }),
    h('span', { class: 'seg-ok', style: `width:${zonaOk}%` }),
    h('span', { class: 'medidor-marca', style: `left:${Math.min(100, Math.max(0, salud))}%` }));
}
