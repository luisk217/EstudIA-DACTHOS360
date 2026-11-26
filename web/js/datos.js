/**
 * Carga de datos. Solo se leen los JSON locales generados por el pipeline
 * (carpeta data/); no hay ninguna llamada a servicios externos.
 */

const ARCHIVOS = ['meta', 'resumen', 'afiliados', 'eventos', 'ejecutivas', 'encuestas', 'segmentos'];

/** Almacén de datos, llenado por cargarDatos(). */
export const datos = {};

/** Bandas del score, en orden de menor a mayor riesgo, con su presentación. */
export const BANDAS = [
  { nombre: 'Saludable', clase: 'b-saludable', seg: 'seg-ok', barra: 'ok', simbolo: 'circulo' },
  { nombre: 'Atención', clase: 'b-atencion', seg: 'seg-aviso', barra: 'aviso', simbolo: 'triangulo' },
  { nombre: 'Riesgo alto', clase: 'b-riesgo', seg: 'seg-riesgo', barra: 'riesgo', simbolo: 'rombo' },
];
export const bandaInfo = (nombre) => BANDAS.find((b) => b.nombre === nombre) || BANDAS[0];

/** Tramos de vencimiento usados en filtros y gráficos. */
export const TRAMOS_VENC = [
  { id: 'vencida', etiqueta: 'Ya vencida', prueba: (d) => d !== null && d < 0 },
  { id: '0-30', etiqueta: 'Vence en 0 a 30 días', prueba: (d) => d !== null && d >= 0 && d <= 30 },
  { id: '31-60', etiqueta: 'Vence en 31 a 60 días', prueba: (d) => d !== null && d > 30 && d <= 60 },
  { id: '61-90', etiqueta: 'Vence en 61 a 90 días', prueba: (d) => d !== null && d > 60 && d <= 90 },
  { id: '90+', etiqueta: 'Vence en más de 90 días', prueba: (d) => d !== null && d > 90 },
  { id: 'sin-fecha', etiqueta: 'Sin fecha de expiración', prueba: (d) => d === null },
];
export const tramoDe = (dias) => TRAMOS_VENC.find((t) => t.prueba(dias ?? null));

/** Lee un JSON y falla con un mensaje claro si la respuesta no es válida. */
async function leerJson(nombre) {
  const resp = await fetch(`data/${nombre}.json`, { cache: 'no-cache' });
  if (!resp.ok) throw new Error(`No se pudo leer data/${nombre}.json (código ${resp.status}).`);
  return resp.json();
}

/** Lee un JSON opcional: devuelve null si no existe o no es válido (sin interrumpir la carga). */
async function leerJsonOpcional(nombre) {
  try {
    const resp = await fetch(`data/${nombre}.json`, { cache: 'no-cache' });
    return resp.ok ? await resp.json() : null;
  } catch {
    return null;
  }
}

// ---- Series mensuales (tendencias) ----------------------------------------------------
const ALIAS = {
  asistentes: ['asistentes', 'asistencias', 'asistencias_validas'],
  empresas: ['empresas_unicas', 'empresas', 'empresas_distintas'],
  satisfaccion: ['satisfaccion', 'satisfaccion_media', 'satisfaccion_1a5'],
  afiliaciones: ['afiliaciones_vigentes', 'afiliaciones', 'nuevas_afiliaciones', 'afiliados_nuevos', 'altas'],
  vencimientos: ['vencimientos', 'vencen', 'expiraciones'],
  salidas: ['salidas', 'bajas'],
};
const MES = /^\d{4}-\d{2}/;
const numero = (v) => (typeof v === 'number' && Number.isFinite(v) ? v : null);

/**
 * Convierte distintas formas razonables de data/tendencias.json a
 * {meses, asistentes, empresas, satisfaccion, afiliaciones, vencimientos}.
 * Devuelve null si no reconoce el contenido (se usarán series calculadas).
 */
export function normalizarTendencias(crudo) {
  if (!crudo || typeof crudo !== 'object') return null;
  const filas = new Map(); // mes -> { serie: valor }
  const poner = (mes, serie, valor) => {
    if (typeof mes !== 'string' || !MES.test(mes)) return;
    const m = mes.slice(0, 7);
    if (!filas.has(m)) filas.set(m, {});
    filas.get(m)[serie] = numero(valor);
  };
  const claveSerie = (k) => Object.keys(ALIAS).find((s) => ALIAS[s].includes(k));
  const mesDe = (f) => f.mes ?? f.clave ?? f.periodo ?? f.fecha;
  const filasMeses = Array.isArray(crudo.meses) && crudo.meses.length && typeof crudo.meses[0] === 'object' ? crudo.meses : null;
  const fuente = filasMeses ?? crudo.series ?? crudo.mensual ?? crudo.meses_series ?? crudo;

  if (Array.isArray(fuente)) { // filas por mes
    for (const f of fuente) {
      if (!f || typeof f !== 'object') continue;
      for (const [k, v] of Object.entries(f)) {
        const s = claveSerie(k);
        // Si hay «afiliaciones_vigentes», se prefiere sobre «afiliaciones» (que incluye a quienes salieron).
        if (s && !(k === 'afiliaciones' && 'afiliaciones_vigentes' in f)) poner(mesDe(f), s, v);
      }
    }
  } else if (fuente && typeof fuente === 'object') {
    const meses = Array.isArray(crudo.meses) ? crudo.meses : Array.isArray(fuente.meses) ? fuente.meses : null;
    for (const [k, v] of Object.entries(fuente)) {
      const s = claveSerie(k);
      if (!s) continue;
      if (Array.isArray(v) && meses && v.every((x) => x === null || typeof x === 'number')) {
        v.forEach((x, i) => poner(meses[i], s, x)); // arreglos paralelos
      } else if (Array.isArray(v)) {
        for (const f of v) { if (f && typeof f === 'object') poner(mesDe(f), s, f.valor ?? f.n ?? f[k]); } // [{mes, valor}]
      } else if (v && typeof v === 'object') {
        for (const [m, x] of Object.entries(v)) poner(m, s, x); // {mes: valor}
      }
    }
  }
  if (!filas.size) return null;
  const meses = [...filas.keys()].sort();
  const salida = { meses, fuente: 'data/tendencias.json' };
  for (const s of Object.keys(ALIAS)) salida[s] = meses.map((m) => filas.get(m)[s] ?? null);
  return salida;
}

/** Series mensuales calculadas a partir de afiliados, eventos y encuestas (si no hay tendencias.json). */
function calcularTendencias() {
  const E = datos.eventos.por_mes, S = datos.encuestas.por_mes, A = datos.afiliadosLista;
  const cuentaMes = (campo) => { const m = new Map(); for (const a of A) if (a[campo]) m.set(a[campo].slice(0, 7), (m.get(a[campo].slice(0, 7)) || 0) + 1); return m; };
  const alta = cuentaMes('afiliacion'), venc = cuentaMes('expira');
  const todos = new Set([...E.map((x) => x.clave), ...S.map((x) => x.clave), ...alta.keys(), ...venc.keys()]);
  const ordenados = [...todos].sort();
  // Meses continuos entre el primero y el último con datos
  const meses = [];
  if (ordenados.length) {
    let [a, m] = ordenados[0].split('-').map(Number);
    const fin = ordenados.at(-1);
    for (let i = 0; i < 600; i += 1) {
      const clave = `${a}-${String(m).padStart(2, '0')}`;
      meses.push(clave);
      if (clave >= fin) break;
      m += 1; if (m > 12) { m = 1; a += 1; }
    }
  }
  const eMap = new Map(E.map((x) => [x.clave, x])), sMap = new Map(S.map((x) => [x.clave, x]));
  return {
    meses, fuente: 'calculada en el navegador',
    asistentes: meses.map((m) => eMap.get(m)?.asistentes ?? null),
    empresas: meses.map((m) => eMap.get(m)?.empresas ?? null),
    satisfaccion: meses.map((m) => sMap.get(m)?.satisfaccion ?? null),
    afiliaciones: meses.map((m) => alta.get(m) ?? 0),
    vencimientos: meses.map((m) => venc.get(m) ?? 0),
    salidas: meses.map(() => null),
  };
}

/** Carga todos los archivos en paralelo y arma índices auxiliares. */
export async function cargarDatos() {
  const [lista, tendencias] = await Promise.all([Promise.all(ARCHIVOS.map(leerJson)), leerJsonOpcional('tendencias')]);
  ARCHIVOS.forEach((n, i) => { datos[n] = lista[i]; });
  datos.afiliadosLista = datos.afiliados.afiliados;
  datos.porId = new Map(datos.afiliadosLista.map((a) => [a.id, a]));
  datos.nombresEjecutivas = [...new Set(datos.afiliadosLista.map((a) => a.ejecutiva))].sort();
  // Fechas de referencia leídas de los datos (no escritas a mano en las vistas)
  datos.fechaCorte = datos.meta.fecha_corte;
  datos.ultimoEvento = datos.eventos.eventos.filter((e) => e.asistentes > 0).map((e) => e.fecha_fin || e.fecha).sort().at(-1) ?? null;
  const calculadas = calcularTendencias();
  const leidas = normalizarTendencias(tendencias);
  if (leidas) { // series ausentes en el archivo se completan con las calculadas
    for (const serie of Object.keys(ALIAS)) {
      if (leidas[serie].some((v) => v !== null)) continue;
      leidas[serie] = leidas.meses.map((m) => { const i = calculadas.meses.indexOf(m); return i < 0 ? null : calculadas[serie][i]; });
    }
  }
  datos.tendencias = leidas ?? calculadas;
  datos.tendenciasCalculadas = !leidas;
  return datos;
}
