/**
 * Gráficos interactivos con Chart.js 4.5.1, servido localmente (vendor/chartjs).
 *
 * - Paleta leída de las variables CSS (claro/oscuro); se reconstruye al cambiar el tema.
 * - Codificación redundante: patrones de relleno, formas de punto, trazos distintos,
 *   etiquetas con valores y porcentajes y una tabla de datos equivalente.
 * - Animaciones sutiles de entrada que respetan prefers-reduced-motion.
 * - Cada gráfico se describe con un "modelo" ({cfg, tabla, descripcion}) que se
 *   puede reaplicar en vivo cuando cambian los filtros.
 */
import { h, entero, decimal, sinMovimiento, alSalir, reemplazar } from './util.js';
import { regresionLineal, mediaMovil, variacion } from './analitica.js';

const Chart = window.Chart;
if (!Chart) throw new Error('No se cargó la biblioteca de gráficos (vendor/chartjs/chart.umd.min.js).');

// ---- Color --------------------------------------------------------------------------
export const css = (nombre) => getComputedStyle(document.documentElement).getPropertyValue(nombre).trim();

/** Aplica transparencia a un color hexadecimal (#rrggbb). Otros formatos se devuelven igual. */
export function conAlfa(color, a) {
  const m = /^#([0-9a-f]{6})$/i.exec(String(color).trim());
  if (!m) return color;
  const n = parseInt(m[1], 16);
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${a})`;
}
const luminancia = (color) => {
  const m = /^#([0-9a-f]{6})$/i.exec(String(color).trim());
  if (!m) return 0.4;
  const n = parseInt(m[1], 16);
  return (0.2126 * ((n >> 16) & 255) + 0.7152 * ((n >> 8) & 255) + 0.0722 * (n & 255)) / 255;
};

/** Colores vigentes (se leen de las variables CSS en cada construcción). */
export function paleta() {
  return {
    texto: css('--texto'), suave: css('--texto-suave'), borde: css('--borde'), bordeFuerte: css('--borde-fuerte'),
    superficie: css('--superficie'), superficie2: css('--superficie-2'), primario: css('--serie-1'), pista: css('--pista'),
    cat: [1, 2, 3, 4, 5, 6].map((i) => css(`--cat-${i}`)), otros: css('--cat-otros'),
    banda: { Saludable: css('--ok-barra'), Atención: css('--aviso-barra'), 'Riesgo alto': css('--riesgo-barra') },
    ok: css('--ok-barra'), aviso: css('--aviso-barra'), riesgo: css('--riesgo-barra'),
    fuente: css('--font-texto') || 'system-ui', fuenteTitulo: css('--font-titulo') || 'serif',
  };
}

// ---- Patrones de relleno (redundancia al color) ---------------------------------------------
const cachePatrones = new Map();
/**
 * Patrón de relleno: 0 sólido, 1 diagonal /, 2 puntos, 3 líneas horizontales, 4 diagonal \, 5 cuadrícula.
 * @param {number} tipo
 * @param {string} color  Color base (#rrggbb).
 * @param {number} [alfa=1]
 */
export function patron(tipo, color, alfa = 1) {
  if (tipo === 0) return alfa === 1 ? color : conAlfa(color, alfa);
  const dpr = Math.max(1, Math.round(window.devicePixelRatio || 1));
  const clave = `${tipo}|${color}|${alfa}|${dpr}`;
  if (cachePatrones.has(clave)) return cachePatrones.get(clave);
  const T = 10, c = document.createElement('canvas');
  c.width = c.height = T * dpr;
  const x = c.getContext('2d');
  x.scale(dpr, dpr);
  x.fillStyle = conAlfa(color, alfa); x.fillRect(0, 0, T, T);
  const marca = luminancia(color) > 0.52 ? `rgba(0,0,0,${0.3 * alfa})` : `rgba(255,255,255,${0.5 * alfa})`;
  x.strokeStyle = marca; x.fillStyle = marca; x.lineWidth = 1.6; x.lineCap = 'square';
  x.beginPath();
  if (tipo === 1) { x.moveTo(-1, T + 1); x.lineTo(T + 1, -1); x.moveTo(-1, 1); x.lineTo(1, -1); x.moveTo(T - 1, T + 1); x.lineTo(T + 1, T - 1); }
  if (tipo === 4) { x.moveTo(-1, -1); x.lineTo(T + 1, T + 1); x.moveTo(T - 1, -1); x.lineTo(T + 1, 1); x.moveTo(-1, T - 1); x.lineTo(1, T + 1); }
  if (tipo === 3) { x.moveTo(0, T / 2); x.lineTo(T, T / 2); }
  if (tipo === 5) { x.moveTo(T / 2, 0); x.lineTo(T / 2, T); x.moveTo(0, T / 2); x.lineTo(T, T / 2); }
  if (tipo === 2) { x.arc(T / 2, T / 2, 1.7, 0, Math.PI * 2); x.fill(); }
  else x.stroke();
  const p = x.createPattern(c, 'repeat');
  try { p.setTransform(new DOMMatrix().scale(1 / dpr)); } catch { /* navegadores sin setTransform */ }
  cachePatrones.set(clave, p);
  return p;
}
/** Patrón asignado a cada banda: Saludable sólido, Atención rayas /, Riesgo alto rayas \. */
export const PATRON_BANDA = { Saludable: 0, Atención: 1, 'Riesgo alto': 4 };
/** Formas de punto para series de línea (redundancia al color). */
const FORMAS = ['circle', 'triangle', 'rect', 'rectRot', 'crossRot', 'star'];
const TRAZOS_LINEA = [[], [7, 4], [2, 3], [10, 3, 2, 3]];

// ---- Formato ---------------------------------------------------------------------------------
const pctTxt = (v, d = 0) => `${decimal(v, d)} %`;
const redondeoRect = (ctx, x, y, w, hgt, r) => {
  if (ctx.roundRect) { ctx.beginPath(); ctx.roundRect(x, y, w, hgt, r); } else { ctx.beginPath(); ctx.rect(x, y, w, hgt); }
};

/** Dibuja un texto sobre una pastilla legible (superficie semitransparente). */
function pastilla(ctx, texto, x, y, P, { alinear = 'center', fuente } = {}) {
  ctx.font = fuente || `600 11.5px ${P.fuente}`;
  const w = ctx.measureText(texto).width + 9, hgt = 18;
  const x0 = alinear === 'left' ? x : alinear === 'right' ? x - w : x - w / 2;
  ctx.save();
  ctx.fillStyle = conAlfa(P.superficie, 0.9); ctx.strokeStyle = conAlfa(P.bordeFuerte, 0.45); ctx.lineWidth = 1;
  redondeoRect(ctx, x0, y - hgt / 2, w, hgt, 5); ctx.fill(); ctx.stroke();
  ctx.fillStyle = P.texto; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
  ctx.fillText(texto, x0 + w / 2, y + 0.5);
  ctx.restore();
  return w;
}

// ---- Complementos (plugins) propios ----------------------------------------------------------
const dxEtiquetas = {
  id: 'dxEtiquetas',
  defaults: { activo: false },
  afterDatasetsDraw(chart, _args, o) {
    if (!o?.activo) return;
    const P = paleta(), { ctx } = chart;
    const fmt = o.formato || ((v) => entero(v));
    chart.data.datasets.forEach((ds, di) => {
      const meta = chart.getDatasetMeta(di);
      if (meta.hidden) return;
      const tipo = meta.type;
      if (tipo !== 'doughnut' && tipo !== 'pie' && tipo !== 'bar') return;
      meta.data.forEach((el, i) => {
        const v = ds.data[i];
        if (v === null || v === undefined || Number.isNaN(v)) return;
        if (tipo === 'doughnut' || tipo === 'pie') {
          if (!chart.getDataVisibility(i)) return;
          const a = el.getProps(['startAngle', 'endAngle', 'innerRadius', 'outerRadius', 'x', 'y'], true);
          const frac = (a.endAngle - a.startAngle) / (Math.PI * 2);
          if (frac < (o.minimo ?? 0.05)) return;
          const mid = (a.startAngle + a.endAngle) / 2, r = (a.innerRadius + a.outerRadius) / 2;
          pastilla(ctx, pctTxt(frac * 100, frac < 0.1 ? 1 : 0), a.x + Math.cos(mid) * r, a.y + Math.sin(mid) * r, P);
          return;
        }
        if (!v) return;
        const p = el.getProps(['x', 'y', 'base', 'width', 'height'], true);
        const horiz = chart.options.indexAxis === 'y';
        const texto = fmt(v, i, di);
        if (o.apilado) {
          const largo = horiz ? Math.abs(p.x - p.base) : Math.abs(p.base - p.y);
          if (largo < (horiz ? 34 : 22)) return;
          pastilla(ctx, texto, horiz ? (p.x + p.base) / 2 : p.x, horiz ? p.y : (p.y + p.base) / 2, P, { fuente: `600 11px ${P.fuente}` });
        } else if (horiz) {
          ctx.save(); ctx.font = `600 12px ${P.fuente}`; ctx.fillStyle = P.texto; ctx.textAlign = 'left'; ctx.textBaseline = 'middle';
          ctx.fillText(texto, Math.max(p.x, p.base) + 7, p.y); ctx.restore();
        } else {
          ctx.save(); ctx.font = `600 12px ${P.fuente}`; ctx.fillStyle = P.texto; ctx.textAlign = 'center'; ctx.textBaseline = 'bottom';
          ctx.fillText(texto, p.x, Math.min(p.y, p.base) - 5); ctx.restore();
        }
      });
    });
  },
};

const dxCentro = {
  id: 'dxCentro',
  defaults: { activo: false },
  afterDraw(chart, _args, o) {
    if (!o?.activo || !['doughnut'].includes(chart.config.type)) return;
    const P = paleta(), { ctx } = chart, el = chart.getDatasetMeta(0).data[0];
    if (!el) return;
    const a = el.getProps(['x', 'y', 'innerRadius'], true);
    const tam = Math.max(16, Math.min(34, a.innerRadius * 0.46));
    ctx.save(); ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.fillStyle = P.texto; ctx.font = `700 ${tam}px ${P.fuenteTitulo}`;
    ctx.fillText(o.valor, a.x, a.y - (o.texto ? tam * 0.2 : 0));
    if (o.texto && a.innerRadius > 38) { ctx.fillStyle = P.suave; ctx.font = `600 ${Math.max(11, tam * 0.4)}px ${P.fuente}`; ctx.fillText(o.texto, a.x, a.y + tam * 0.62); }
    ctx.restore();
  },
};

const dxCruz = {
  id: 'dxCruz',
  defaults: { activo: false },
  afterDatasetsDraw(chart, _args, o) {
    if (!o?.activo) return;
    const act = chart.getActiveElements();
    if (!act.length) return;
    const P = paleta(), { ctx, chartArea: a } = chart, x = act[0].element.x;
    ctx.save(); ctx.strokeStyle = conAlfa(P.suave, 0.45); ctx.setLineDash([4, 4]); ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(x, a.top); ctx.lineTo(x, a.bottom); ctx.stroke(); ctx.restore();
  },
};

const dxReferencias = {
  id: 'dxReferencias',
  defaults: { activo: false },
  beforeDatasetsDraw(chart, _args, o) {
    if (!o?.activo) return;
    const P = paleta(), { ctx, chartArea: a, scales } = chart;
    ctx.save();
    for (const z of o.zonas || []) { // zonas sombreadas en Y
      const y0 = scales.y.getPixelForValue(z.hasta), y1 = scales.y.getPixelForValue(z.desde);
      ctx.fillStyle = conAlfa(z.color, z.alfa ?? 0.07); ctx.fillRect(a.left, Math.max(a.top, y0), a.right - a.left, Math.min(a.bottom, y1) - Math.max(a.top, y0));
    }
    ctx.setLineDash([5, 4]); ctx.lineWidth = 1.3;
    for (const r of o.y || []) {
      const y = scales.y.getPixelForValue(r.valor);
      if (y < a.top || y > a.bottom) continue;
      ctx.strokeStyle = conAlfa(r.color || P.suave, 0.8); ctx.beginPath(); ctx.moveTo(a.left, y); ctx.lineTo(a.right, y); ctx.stroke();
      if (r.etiqueta) pastilla(ctx, r.etiqueta, a.right - 4, y - 11, P, { alinear: 'right', fuente: `600 11px ${P.fuente}` });
    }
    for (const r of o.x || []) {
      const x = scales.x.getPixelForValue(r.valor);
      if (x < a.left || x > a.right) continue;
      ctx.strokeStyle = conAlfa(r.color || P.suave, 0.85); ctx.beginPath(); ctx.moveTo(x, a.top); ctx.lineTo(x, a.bottom); ctx.stroke();
      if (r.etiqueta) pastilla(ctx, r.etiqueta, x + 4, a.top + 11, P, { alinear: 'left', fuente: `600 11px ${P.fuente}` });
    }
    ctx.restore();
  },
};
Chart.register(dxEtiquetas, dxCentro, dxCruz, dxReferencias);

// ---- Opciones comunes ---------------------------------------------------------------------------
function defaultsGlobales() {
  const P = paleta();
  Chart.defaults.font.family = P.fuente;
  Chart.defaults.font.size = 12.5;
  Chart.defaults.color = P.suave;
  Chart.defaults.borderColor = P.borde;
}

function animacion(entrada = true) {
  if (sinMovimiento()) return false;
  return { duration: entrada ? 760 : 420, easing: 'easeOutQuart' };
}

function opcionesBase(P, { leyenda = true, posicion = 'bottom', cruz = false } = {}) {
  return {
    responsive: true, maintainAspectRatio: false, animation: animacion(),
    layout: { padding: { top: 6, right: 8, bottom: 2, left: 2 } },
    interaction: { mode: 'nearest', intersect: true },
    plugins: {
      legend: { display: leyenda, position: posicion, labels: { color: P.texto, usePointStyle: true, boxWidth: 9, boxHeight: 9, padding: 14, font: { size: 12.5, family: P.fuente } } },
      tooltip: {
        backgroundColor: conAlfa(P.superficie, 0.97), titleColor: P.texto, bodyColor: P.texto, footerColor: P.suave, borderColor: P.bordeFuerte, borderWidth: 1,
        padding: 11, cornerRadius: 9, boxPadding: 5, usePointStyle: true, caretSize: 6,
        titleFont: { weight: '700', size: 13, family: P.fuente }, bodyFont: { size: 12.5, family: P.fuente }, footerFont: { size: 11.5, weight: '600', family: P.fuente },
      },
      dxCruz: { activo: cruz },
    },
  };
}
const ejeCategoria = (P, extra = {}) => ({ grid: { display: false }, border: { color: P.bordeFuerte }, ticks: { color: P.suave, font: { size: 12 }, maxRotation: 0, autoSkipPadding: 10 }, ...extra });
const ejeValor = (P, extra = {}) => ({ grid: { color: conAlfa(P.borde, 0.75), borderDash: [3, 4] }, border: { display: false }, ticks: { color: P.suave, font: { size: 12 }, maxTicksLimit: 6 }, beginAtZero: true, ...extra });
const tituloEje = (P, texto) => (texto ? { display: true, text: texto, color: P.suave, font: { size: 11.5, weight: '600' } } : { display: false });

// ---- Modelo: líneas y áreas con tendencia ---------------------------------------------------------
/**
 * Líneas suavizadas (curvas) con áreas en degradado y líneas de tendencia rotuladas.
 * @param {Object} o
 * @param {string[]} o.etiquetas
 * @param {Array<{nombre:string, datos:(number|null)[], color?:string, area?:boolean, eje?:'y'|'y2', tendencia?:'lineal'|'movil'|'ambas'|null, formato?:Function}>} o.series
 */
export function modeloLinea({ etiquetas, series, formato = entero, min, max, tituloY, tituloY2, formatoY2, variacionPie = true, unidadMes = 'mes' }) {
  const P = paleta();
  const datasets = [];
  const tabla = { encabezados: ['Mes', ...series.map((s) => s.nombre)], filas: etiquetas.map((e, i) => [e, ...series.map((s) => ((s.formato || formato)(s.datos[i])))]) };
  series.forEach((s, i) => {
    const color = s.color || P.cat[i % P.cat.length];
    const yAxisID = s.eje || 'y';
    datasets.push({
      type: 'line', label: s.nombre, data: s.datos, yAxisID, borderColor: color, borderWidth: 2.7, tension: 0.38, spanGaps: true, order: 1,
      fill: !!s.area, backgroundColor: s.area ? (ctx) => {
        const a = ctx.chart.chartArea;
        if (!a) return conAlfa(color, 0.16);
        const g = ctx.chart.ctx.createLinearGradient(0, a.top, 0, a.bottom);
        g.addColorStop(0, conAlfa(color, 0.42)); g.addColorStop(0.7, conAlfa(color, 0.08)); g.addColorStop(1, conAlfa(color, 0));
        return g;
      } : color,
      pointStyle: FORMAS[i % FORMAS.length], pointRadius: 4, pointHoverRadius: 7, pointBackgroundColor: P.superficie, pointBorderColor: color, pointBorderWidth: 2.2,
      borderDash: TRAZOS_LINEA[0], esSerie: true, formatoSerie: s.formato || formato,
    });
    const fm = s.formato || formato;
    if (s.tendencia === 'lineal' || s.tendencia === 'ambas') {
      const reg = regresionLineal(s.datos);
      if (reg) {
        const signo = reg.pendiente >= 0 ? '+' : '−';
        datasets.push({ type: 'line', label: `Tendencia lineal de ${s.nombre} (${signo}${fm(Math.abs(reg.pendiente))} por ${unidadMes})`, data: reg.valores, yAxisID, borderColor: color, borderWidth: 1.9, borderDash: [8, 5], pointRadius: 0, pointHoverRadius: 0, pointStyle: 'line', fill: false, tension: 0, order: 3, esTendencia: true, formatoSerie: fm });
        tabla.encabezados.push(`Tendencia lineal: ${s.nombre}`); tabla.filas.forEach((f, k) => f.push(reg.valores[k] === null ? 'Sin dato' : fm(reg.valores[k])));
      }
    }
    if (s.tendencia === 'movil' || s.tendencia === 'ambas') {
      const mm = mediaMovil(s.datos, 3);
      datasets.push({ type: 'line', label: `Media móvil de 3 ${unidadMes}es de ${s.nombre}`, data: mm, yAxisID, borderColor: conAlfa(color, 0.9), borderWidth: 2.2, borderDash: [2, 4], pointRadius: 0, pointHoverRadius: 0, pointStyle: 'line', fill: false, tension: 0.4, order: 2, spanGaps: true, esTendencia: true, formatoSerie: fm });
      tabla.encabezados.push(`Media móvil: ${s.nombre}`); tabla.filas.forEach((f, k) => f.push(mm[k] === null ? 'Sin dato' : fm(mm[k])));
    }
  });
  const usaY2 = series.some((s) => s.eje === 'y2');
  const opciones = opcionesBase(P, { cruz: true });
  opciones.interaction = { mode: 'index', intersect: false };
  opciones.plugins.tooltip.callbacks = {
    label: (c) => `${c.dataset.label.length > 38 ? c.dataset.label.slice(0, 36) + '…' : c.dataset.label}: ${c.raw === null || c.raw === undefined ? 'Sin dato' : c.dataset.formatoSerie(c.raw)}`,
    footer: (items) => {
      if (!variacionPie) return '';
      const it = items.find((x) => x.dataset.esSerie);
      if (!it || it.dataIndex === 0) return '';
      const previo = it.dataset.data[it.dataIndex - 1];
      if (previo === null || previo === undefined || it.raw === null || !previo) return '';
      const d = ((it.raw - previo) / Math.abs(previo)) * 100;
      return `Variación frente al ${unidadMes} anterior: ${d >= 0 ? '+' : '−'}${decimal(Math.abs(d), 1)} %`;
    },
  };
  opciones.plugins.legend.labels.generateLabels = (chart) => chart.data.datasets.map((ds, i) => ({
    fontColor: P.texto, text: ds.label, fillStyle: ds.borderColor, strokeStyle: ds.borderColor, lineWidth: 2, lineDash: ds.borderDash, hidden: !chart.isDatasetVisible(i), datasetIndex: i, pointStyle: ds.esTendencia ? 'line' : ds.pointStyle,
  }));
  opciones.scales = {
    x: ejeCategoria(P),
    y: ejeValor(P, { min, max, title: tituloEje(P, tituloY), ticks: { color: P.suave, font: { size: 12 }, maxTicksLimit: 6, callback: (v) => formato(v) } }),
    ...(usaY2 ? { y2: ejeValor(P, { position: 'right', grid: { drawOnChartArea: false }, title: tituloEje(P, tituloY2), ticks: { color: P.suave, font: { size: 12 }, maxTicksLimit: 6, callback: (v) => (formatoY2 || formato)(v) } }) } : {}),
  };
  const principal = series[0];
  const regP = principal ? regresionLineal(principal.datos) : null;
  const descripcion = `Gráfico de líneas: ${series.map((s) => s.nombre).join(', ')} de ${etiquetas[0] ?? ''} a ${etiquetas.at(-1) ?? ''}. ${principal ? `Último valor de ${principal.nombre}: ${formato([...principal.datos].reverse().find((v) => v !== null) ?? 0)}.${regP ? ` La tendencia lineal es ${regP.pendiente >= 0 ? 'creciente' : 'decreciente'}.` : ''}` : ''}`;
  return { cfg: { type: 'line', data: { labels: etiquetas, datasets }, options: opciones }, tabla, descripcion };
}

// ---- Modelo: barras (simples, agrupadas, apiladas) -----------------------------------------------------
/**
 * @param {Object} o
 * @param {string[]} o.etiquetas
 * @param {Array<{nombre:string, datos:number[], color?:string, colores?:string[], patrones?:number[], patron?:number}>} o.series
 * @param {boolean} [o.apilado]  Barras apiladas.
 * @param {boolean} [o.horizontal]
 * @param {number|null} [o.seleccion]  Índice resaltado (el resto se atenúa).
 */
export function modeloBarras({ etiquetas, series, apilado = false, horizontal = false, formato = entero, seleccion = null, etiquetasDatos = true, max, tituloValor, leyenda, ejeCat = 'Categoría', maxRotulo = 28, bandas = false, lineas = [], tituloY2, formatoY2, minValor, minY2, maxY2 }) {
  const P = paleta();
  const datasets = series.map((s, si) => {
    const base = s.color || P.cat[si % P.cat.length];
    const colorDe = (i) => s.colores?.[i] || base;
    const patronDe = (i) => (s.patrones ? s.patrones[i] : s.patron ?? (series.length > 1 || bandas ? (bandas ? PATRON_BANDA[s.nombre] ?? si : si) : 0));
    const dim = (i) => (seleccion !== null && seleccion !== undefined && seleccion !== i ? 0.32 : 1);
    return {
      label: s.nombre, data: s.datos, borderRadius: apilado ? 3 : 7, borderSkipped: apilado ? false : 'start',
      backgroundColor: s.datos.map((_, i) => patron(patronDe(i) ?? 0, colorDe(i), dim(i))),
      borderColor: s.datos.map((_, i) => (seleccion === i ? P.texto : apilado ? P.superficie : conAlfa(colorDe(i), 0))), borderWidth: s.datos.map((_, i) => (seleccion === i ? 2 : apilado ? 1.5 : 0)),
      hoverBorderColor: P.texto, hoverBorderWidth: 2, maxBarThickness: horizontal ? 26 : 44, barPercentage: apilado ? 0.82 : series.length > 1 ? 0.88 : 0.74, categoryPercentage: 0.84,
      leyendaColor: base, leyendaPatron: patronDe(0) ?? 0,
    };
  });
  lineas.forEach((l, k) => {
    const color = l.color || P.cat[(series.length + k) % P.cat.length];
    datasets.push({ type: 'line', label: l.nombre, data: l.datos, yAxisID: 'y2', borderColor: color, backgroundColor: color, borderWidth: 2.7, tension: 0.38, spanGaps: true, order: 0,
      pointStyle: FORMAS[(k + 1) % FORMAS.length], pointRadius: 4, pointHoverRadius: 7, pointBackgroundColor: P.superficie, pointBorderColor: color, pointBorderWidth: 2.2, esSerie: true, formatoSerie: l.formato || formato, leyendaColor: color, leyendaLinea: true });
  });
  const opciones = opcionesBase(P, { leyenda: leyenda ?? (series.length + lineas.length) > 1 });
  opciones.indexAxis = horizontal ? 'y' : 'x';
  opciones.interaction = { mode: apilado ? 'index' : 'nearest', intersect: !apilado, axis: horizontal ? 'y' : 'x' };
  const cat = ejeCategoria(P, { stacked: apilado, ticks: { color: P.suave, font: { size: 12 }, maxRotation: 0, autoSkip: etiquetas.length > 14, autoSkipPadding: 6, callback(v) { const t = this.getLabelForValue(v); return t.length > maxRotulo ? `${t.slice(0, maxRotulo - 1)}…` : t; } } });
  const val = ejeValor(P, { stacked: apilado, max, min: minValor, beginAtZero: minValor === undefined, title: tituloEje(P, tituloValor), ticks: { color: P.suave, font: { size: 12 }, maxTicksLimit: 6, callback: (v) => formato(v) }, grace: horizontal ? '14%' : '10%' });
  if (horizontal) { cat.grid = { display: false }; val.grid = { color: conAlfa(P.borde, 0.75), borderDash: [3, 4] }; }
  opciones.scales = horizontal ? { y: cat, x: val } : { x: cat, y: val };
  if (lineas.length) opciones.scales.y2 = ejeValor(P, { position: 'right', min: minY2, max: maxY2, beginAtZero: minY2 === undefined, grid: { drawOnChartArea: false }, title: tituloEje(P, tituloY2), ticks: { color: P.suave, font: { size: 12 }, maxTicksLimit: 6, callback: (v) => (formatoY2 || formato)(v) } });
  opciones.plugins.dxEtiquetas = { activo: etiquetasDatos, formato, apilado };
  opciones.plugins.tooltip.callbacks = {
    title: (it) => it[0]?.label ?? '',
    label: (c) => {
      if (c.dataset.type === 'line') return `${c.dataset.label}: ${c.raw === null ? 'Sin dato' : c.dataset.formatoSerie(c.raw)}`;
      const total = apilado ? series.reduce((s, x) => s + (x.datos[c.dataIndex] || 0), 0) : 0;
      return `${c.dataset.label}: ${formato(c.raw)}${apilado && total ? ` (${pctTxt((c.raw / total) * 100, 0)} del total)` : ''}`;
    },
    footer: (items) => (apilado ? `Total: ${formato(series.reduce((s, x) => s + (x.datos[items[0].dataIndex] || 0), 0))}` : ''),
  };
  // Leyenda con el patrón/color de cada serie
  opciones.plugins.legend.labels.generateLabels = (chart) => chart.data.datasets.map((ds, i) => ({
    fontColor: P.texto, text: ds.label, fillStyle: ds.leyendaLinea ? ds.leyendaColor : patron(ds.leyendaPatron ?? 0, ds.leyendaColor, 1), strokeStyle: ds.leyendaColor, lineWidth: 1, hidden: !chart.isDatasetVisible(i), datasetIndex: i, pointStyle: ds.leyendaLinea ? ds.pointStyle : 'rectRounded',
  }));
  const tabla = { encabezados: [ejeCat, ...series.map((s) => s.nombre), ...lineas.map((l) => l.nombre)], filas: etiquetas.map((e, i) => [e, ...series.map((s) => formato(s.datos[i])), ...lineas.map((l) => (l.formato || formato)(l.datos[i]))]), clicable: true };
  return {
    cfg: { type: 'bar', data: { labels: etiquetas, datasets }, options: opciones }, tabla,
    descripcion: `Gráfico de barras${apilado ? ' apiladas' : series.length > 1 ? ' agrupadas' : ''}: ${etiquetas.map((e, i) => `${e} ${series.map((s) => `${series.length > 1 ? `${s.nombre} ` : ''}${formato(s.datos[i])}`).join(' y ')}`).join('; ')}.`,
  };
}

// ---- Modelo: dona y torta ----------------------------------------------------------------------------------
/**
 * @param {Object} o
 * @param {string[]} o.etiquetas
 * @param {number[]} o.valores
 * @param {string[]} [o.colores]
 * @param {number[]} [o.patrones]  Un tipo de patrón por segmento.
 * @param {'doughnut'|'pie'} [o.tipo]
 */
export function modeloDona({ etiquetas, valores, colores, patrones, tipo = 'doughnut', seleccion = null, centro, nombre = 'Cantidad', formato = entero, posicion = 'bottom', ejeCat = 'Categoría' }) {
  const P = paleta();
  const total = valores.reduce((s, v) => s + v, 0) || 1;
  const col = etiquetas.map((e, i) => colores?.[i] ?? (e === 'Otros' || e === 'Sin dato' ? P.otros : P.cat[i % P.cat.length]));
  const pat = etiquetas.map((e, i) => patrones?.[i] ?? (e === 'Otros' ? 2 : i % 6));
  const dim = (i) => (seleccion !== null && seleccion !== undefined && seleccion !== i ? 0.3 : 1);
  const opciones = opcionesBase(P, { posicion });
  opciones.interaction = { mode: 'nearest', intersect: true };
  opciones.cutout = tipo === 'pie' ? 0 : '62%';
  opciones.animation = sinMovimiento() ? false : { duration: 820, easing: 'easeOutQuart', animateRotate: true, animateScale: true };
  opciones.plugins.dxEtiquetas = { activo: true };
  opciones.plugins.dxCentro = { activo: tipo === 'doughnut' && !!centro, valor: centro?.valor ?? '', texto: centro?.texto ?? '' };
  opciones.plugins.legend.labels.generateLabels = (chart) => etiquetas.map((e, i) => ({
    fontColor: P.texto, text: `${e} · ${pctTxt((valores[i] / total) * 100, valores[i] / total < 0.1 ? 1 : 0)}`, fillStyle: patron(pat[i], col[i], 1), strokeStyle: col[i], lineWidth: 1, hidden: !chart.getDataVisibility(i), index: i, pointStyle: 'rectRounded',
  }));
  opciones.plugins.tooltip.callbacks = {
    label: (c) => `${c.label}: ${formato(c.raw)} (${pctTxt((c.raw / total) * 100, 1)})`,
  };
  const datasets = [{
    label: nombre, data: valores, backgroundColor: valores.map((_, i) => patron(pat[i], col[i], dim(i))),
    borderColor: valores.map((_, i) => (seleccion === i ? P.texto : P.superficie)), borderWidth: valores.map((_, i) => (seleccion === i ? 2.5 : 2)),
    hoverBorderColor: P.texto, spacing: tipo === 'pie' ? 1 : 2, borderRadius: tipo === 'pie' ? 3 : 6, hoverOffset: 9, offset: valores.map((_, i) => (seleccion === i ? 10 : 0)),
  }];
  const tabla = { encabezados: [ejeCat, nombre, 'Porcentaje'], filas: etiquetas.map((e, i) => [e, formato(valores[i]), pctTxt((valores[i] / total) * 100, 1)]), clicable: true };
  return {
    cfg: { type: tipo, data: { labels: etiquetas, datasets }, options: opciones }, tabla,
    descripcion: `Gráfico de ${tipo === 'pie' ? 'torta' : 'dona'}: ${etiquetas.map((e, i) => `${e} ${formato(valores[i])} (${pctTxt((valores[i] / total) * 100, 1)})`).join('; ')}.`,
  };
}

// ---- Modelo: radar ------------------------------------------------------------------------------------------
export function modeloRadar({ ejes, series, max = 100, formato = (v) => decimal(v, 1), sufijo = '' }) {
  const P = paleta();
  const opciones = opcionesBase(P);
  opciones.interaction = { mode: 'nearest', intersect: true };
  opciones.scales = { r: {
    min: 0, max, ticks: { display: true, backdropColor: 'transparent', color: P.suave, font: { size: 10.5 }, maxTicksLimit: 4, callback: (v) => `${v}${sufijo}` },
    grid: { color: conAlfa(P.borde, 0.9) }, angleLines: { color: conAlfa(P.borde, 0.9) }, pointLabels: { color: P.texto, font: { size: 12, weight: '600' } },
  } };
  opciones.plugins.tooltip.callbacks = { label: (c) => `${c.dataset.label}: ${formato(c.raw)}${sufijo}` };
  const datasets = series.map((s, i) => {
    const color = s.color || P.cat[i % P.cat.length];
    return { label: s.nombre, data: s.datos, borderColor: color, backgroundColor: conAlfa(color, 0.14), borderWidth: 2.4, borderDash: TRAZOS_LINEA[i % TRAZOS_LINEA.length], pointStyle: FORMAS[i % FORMAS.length], pointRadius: 4, pointHoverRadius: 7, pointBackgroundColor: P.superficie, pointBorderColor: color, pointBorderWidth: 2, fill: true };
  });
  return {
    cfg: { type: 'radar', data: { labels: ejes, datasets }, options: opciones },
    tabla: { encabezados: ['Indicador', ...series.map((s) => s.nombre)], filas: ejes.map((e, i) => [e, ...series.map((s) => `${formato(s.datos[i])}${sufijo}`)]) },
    descripcion: `Gráfico de radar con ${ejes.length} indicadores (${ejes.join(', ')}) para ${series.map((s) => s.nombre).join(', ')}.`,
  };
}

// ---- Modelo: dispersión ------------------------------------------------------------------------------------------------
/**
 * @param {Object} o
 * @param {Array<{nombre:string, color:string, forma:string, patron?:number, puntos:Array<{x:number,y:number,info?:string[],id?:string}>}>} o.grupos
 */
export function modeloDispersion({ grupos, tituloX, tituloY, referencias = {}, minX, maxX }) {
  const P = paleta();
  const opciones = opcionesBase(P);
  opciones.interaction = { mode: 'nearest', intersect: true };
  opciones.scales = {
    x: { type: 'linear', min: minX, max: maxX, grid: { color: conAlfa(P.borde, 0.5), borderDash: [3, 4] }, border: { color: P.bordeFuerte }, title: tituloEje(P, tituloX), ticks: { color: P.suave, font: { size: 12 }, maxTicksLimit: 9 } },
    y: { min: 0, max: 100, grid: { color: conAlfa(P.borde, 0.75), borderDash: [3, 4] }, border: { display: false }, title: tituloEje(P, tituloY), ticks: { color: P.suave, font: { size: 12 }, stepSize: 20 } },
  };
  opciones.plugins.dxReferencias = { activo: true, ...referencias };
  opciones.plugins.tooltip.callbacks = {
    title: (it) => it[0]?.raw?.id ?? '',
    label: (c) => [`${c.dataset.label}`, ...(c.raw.info || [])],
  };
  opciones.plugins.legend.labels.generateLabels = (chart) => chart.data.datasets.map((ds, i) => ({
    fontColor: P.texto, text: ds.label, fillStyle: ds.borderColor, strokeStyle: ds.borderColor, lineWidth: 1, hidden: !chart.isDatasetVisible(i), datasetIndex: i, pointStyle: ds.pointStyle,
  }));
  const datasets = grupos.map((g) => ({
    label: g.nombre, data: g.puntos, backgroundColor: conAlfa(g.color, 0.62), borderColor: g.color, borderWidth: 1.4, pointStyle: g.forma, pointRadius: 5, pointHoverRadius: 8, pointHoverBorderWidth: 2.4, pointHoverBorderColor: P.texto,
  }));
  const total = grupos.reduce((s, g) => s + g.puntos.length, 0);
  return {
    cfg: { type: 'scatter', data: { datasets }, options: opciones },
    tabla: { encabezados: ['Afiliado', 'Banda', tituloX, tituloY], filas: grupos.flatMap((g) => g.puntos.slice(0, 60).map((p) => [p.id, g.nombre, String(p.x), String(p.y)])), nota: total > 60 * grupos.length ? 'Se muestran hasta 60 afiliados por banda.' : '' },
    descripcion: `Gráfico de dispersión de ${total} afiliados: riesgo (0 a 100) frente a días a vencimiento. ${grupos.map((g) => `${g.nombre}: ${g.puntos.length}`).join('; ')}.`,
  };
}

// ---- Contenedor de gráfico: ciclo de vida, accesibilidad y tema ----------------------------------------------------------------
const vivos = new Set();

/** Reconstruye todos los gráficos vivos (cambio de tema o de movimiento reducido). */
export function reconstruirGraficos() {
  defaultsGlobales();
  vivos.forEach((g) => g.rehacer());
}
window.addEventListener('dactho:tema', reconstruirGraficos);
window.matchMedia?.('(prefers-color-scheme: dark)').addEventListener?.('change', () => setTimeout(reconstruirGraficos, 30));

/**
 * Crea un gráfico dentro de un contenedor.
 * @param {HTMLElement} contenedor
 * @param {{alto?:number|string, clic?:(indice:number, serie:number)=>void, etiquetaClic?:string}} [cfg]
 * @returns {{poner:(fn:()=>Object)=>void, elemento:HTMLElement, destruir:()=>void}}
 */
export function grafico(contenedor, { alto = 290, clic = null } = {}) {
  defaultsGlobales();
  const canvas = h('canvas', { role: 'img', 'aria-label': 'Gráfico' });
  const lienzo = h('div', { class: 'grafico-lienzo', style: `height:${typeof alto === 'number' ? `${alto}px` : alto}` }, canvas);
  const tablaCont = h('div', { class: 'grafico-tabla' });
  const detalles = h('details', { class: 'grafico-datos' },
    h('summary', {}, 'Ver los datos en una tabla'), tablaCont);
  const elemento = h('figure', { class: 'grafico' }, lienzo, detalles);
  contenedor.append(elemento);
  let chart = null, ultimo = null;

  function pintarTabla(t) {
    if (!t) { reemplazar(tablaCont); return; }
    reemplazar(tablaCont,
      clic && t.clicable ? h('p', { class: 'nota' }, 'Active un nombre de la primera columna para filtrar por él.') : null,
      h('div', { class: 'tabla-envoltura' }, h('table', {},
        h('thead', {}, h('tr', {}, t.encabezados.map((e) => h('th', { scope: 'col' }, e)))),
        h('tbody', {}, t.filas.map((f, i) => h('tr', {}, f.map((c, j) => (j === 0
          ? h('th', { scope: 'row' }, clic && t.clicable ? h('button', { class: 'btn-enlace', type: 'button', onclick: () => clic(i, 0) }, c) : c)
          : h('td', { class: 'num' }, c)))))))),
      t.nota ? h('p', { class: 'nota' }, t.nota) : null);
  }

  function aplicar(modelo) {
    const cfg = modelo.cfg;
    if (clic) {
      cfg.options.onClick = (_e, els) => { if (els.length) clic(els[0].index, els[0].datasetIndex); };
      cfg.options.onHover = (_e, els) => { canvas.style.cursor = els.length ? 'pointer' : 'default'; };
    }
    if (!chart) chart = new Chart(canvas, cfg);
    else { chart.data = cfg.data; chart.options = cfg.options; chart.update(); }
    canvas.setAttribute('aria-label', modelo.descripcion || 'Gráfico');
    pintarTabla(modelo.tabla);
  }

  const handle = {
    elemento,
    chart: () => chart,
    /** Aplica (o reaplica) un modelo; la función se guarda para reconstruir al cambiar el tema. */
    poner(fn) { ultimo = fn; aplicar(fn()); },
    rehacer() { if (ultimo) { if (chart) { chart.destroy(); chart = null; } aplicar(ultimo()); } },
    destruir() { vivos.delete(handle); chart?.destroy(); chart = null; },
  };
  vivos.add(handle);
  alSalir(() => handle.destruir());
  return handle;
}

export { variacion };
