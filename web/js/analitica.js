/**
 * Cálculos sobre los datos: resúmenes de cartera, series mensuales, regresión
 * lineal, media móvil y variaciones. Funciones puras (sin DOM).
 */
import { BANDAS, TRAMOS_VENC } from './datos.js';
import { sumarMeses, rangoMeses } from './util.js';

/** Cuenta por clave y devuelve [[clave, n]] ordenado de mayor a menor. */
export function ranking(lista, fn, { vacio = 'Sin dato' } = {}) {
  const m = new Map();
  for (const x of lista) { const k = fn(x) ?? vacio; m.set(k, (m.get(k) || 0) + 1); }
  return [...m].sort((a, b) => b[1] - a[1] || String(a[0]).localeCompare(String(b[0]), 'es'));
}

/** Agrupa los pares restantes en «Otros» tras los primeros n. */
export function topConOtros(pares, n, etiquetaOtros = 'Otros') {
  if (pares.length <= n) return pares;
  const resto = pares.slice(n).reduce((s, [, v]) => s + v, 0);
  return [...pares.slice(0, n), [etiquetaOtros, resto]];
}

const media = (arr) => (arr.length ? arr.reduce((s, x) => s + x, 0) / arr.length : null);

/** Resumen de una lista (ya filtrada) de afiliados. */
export function resumir(lista) {
  const n = lista.length;
  const porBanda = Object.fromEntries(BANDAS.map((b) => [b.nombre, 0]));
  const tramos = Object.fromEntries(TRAMOS_VENC.map((t) => [t.id, 0]));
  let conAsist = 0, conAsist90 = 0, unSolo = 0, sumResp = 0, sumSat = 0, conResp = 0, nuevos = 0;
  for (const a of lista) {
    porBanda[a.banda] = (porBanda[a.banda] || 0) + 1;
    const t = TRAMOS_VENC.find((x) => x.prueba(a.dias_venc ?? null));
    if (t) tramos[t.id] += 1;
    if (a.asist > 0) conAsist += 1;
    if (a.asist_90d > 0) conAsist90 += 1;
    if (a.asist > 1 && a.personas === 1) unSolo += 1;
    if (a.n_resp > 0 && a.sat !== null) { sumResp += a.n_resp; sumSat += a.sat * a.n_resp; conResp += 1; }
    if (a.antig_anios !== null && a.antig_anios < 0.25) nuevos += 1;
  }
  const pct = (x) => (n ? (x / n) * 100 : 0);
  return {
    n, porBanda, tramos,
    riesgoMedio: media(lista.map((a) => a.riesgo)), saludMedia: media(lista.map((a) => a.salud)),
    conAsist, sinAsist: n - conAsist, pctAsist: pct(conAsist), conAsist90, pctAsist90: pct(conAsist90), unSolo, nuevos,
    pctRiesgo: pct(porBanda['Riesgo alto'] || 0),
    venc90: tramos['0-30'] + tramos['31-60'] + tramos['61-90'], vencidas: tramos.vencida,
    sat: { media: sumResp ? sumSat / sumResp : null, respuestas: sumResp, afiliados: conResp },
  };
}

// ---- Series --------------------------------------------------------------------------
/** Cuenta por mes (AAAA-MM) de un campo de fecha, opcionalmente separado por banda. */
export function porMes(lista, campo, { rango, porBanda = false } = {}) {
  const m = new Map();
  for (const a of lista) {
    const v = a[campo];
    if (!v) continue;
    const mes = v.slice(0, 7);
    if (!m.has(mes)) m.set(mes, Object.fromEntries([['total', 0], ...BANDAS.map((b) => [b.nombre, 0])]));
    const c = m.get(mes); c.total += 1; if (porBanda) c[a.banda] += 1;
  }
  const meses = rango ?? (m.size ? rangoMeses([...m.keys()].sort()[0], [...m.keys()].sort().at(-1)) : []);
  return { meses, filas: meses.map((x) => m.get(x) ?? Object.fromEntries([['total', 0], ...BANDAS.map((b) => [b.nombre, 0])])) };
}

/**
 * Regresión lineal por mínimos cuadrados sobre los valores no nulos (x = posición).
 * @returns {{pendiente:number, intercepto:number, r2:number, valores:(number|null)[]}|null}
 */
export function regresionLineal(ys) {
  const pts = ys.map((y, x) => ({ x, y })).filter((p) => p.y !== null && p.y !== undefined);
  if (pts.length < 3) return null;
  const n = pts.length, sx = pts.reduce((s, p) => s + p.x, 0), sy = pts.reduce((s, p) => s + p.y, 0);
  const sxx = pts.reduce((s, p) => s + p.x * p.x, 0), sxy = pts.reduce((s, p) => s + p.x * p.y, 0);
  const den = n * sxx - sx * sx;
  if (!den) return null;
  const pendiente = (n * sxy - sx * sy) / den, intercepto = (sy - pendiente * sx) / n;
  const ym = sy / n;
  const ssTot = pts.reduce((s, p) => s + (p.y - ym) ** 2, 0), ssRes = pts.reduce((s, p) => s + (p.y - (intercepto + pendiente * p.x)) ** 2, 0);
  const x0 = pts[0].x, x1 = pts.at(-1).x;
  return { pendiente, intercepto, r2: ssTot ? 1 - ssRes / ssTot : 0, valores: ys.map((_, x) => (x >= x0 && x <= x1 ? intercepto + pendiente * x : null)) };
}

/** Media móvil simple de ventana k sobre valores no nulos (nulo si no hay datos en la ventana). */
export function mediaMovil(ys, k = 3) {
  return ys.map((y, i) => {
    if (y === null || y === undefined) return null;
    const ventana = ys.slice(Math.max(0, i - k + 1), i + 1).filter((v) => v !== null && v !== undefined);
    return ventana.length >= Math.min(k, 2) ? media(ventana) : null;
  });
}

/** Variación entre los dos últimos valores no nulos: {actual, previo, delta, pct}. */
export function variacion(ys) {
  const idx = ys.map((v, i) => (v === null || v === undefined ? -1 : i)).filter((i) => i >= 0);
  if (idx.length < 2) return null;
  const actual = ys[idx.at(-1)], previo = ys[idx.at(-2)];
  return { actual, previo, delta: actual - previo, pct: previo ? ((actual - previo) / Math.abs(previo)) * 100 : null };
}

/** Recorta una serie mensual a una ventana de meses (los meses fuera de la ventana desaparecen). */
export function ventana(meses, series, desde, hasta) {
  const idx = meses.map((m, i) => i).filter((i) => (!desde || meses[i] >= desde) && (!hasta || meses[i] <= hasta));
  return { meses: idx.map((i) => meses[i]), series: Object.fromEntries(Object.entries(series).map(([k, v]) => [k, idx.map((i) => v[i])])) };
}

/** Quita ceros/nulos iniciales y finales de una serie (para sparklines más limpios). */
export function recortarExtremos(ys, esVacio = (v) => v === null || v === undefined) {
  let a = 0, b = ys.length;
  while (a < b && esVacio(ys[a])) a += 1;
  while (b > a && esVacio(ys[b - 1])) b -= 1;
  return ys.slice(a, b);
}

export { sumarMeses };
