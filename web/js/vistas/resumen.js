/** Vista 1: Resumen ejecutivo de retención, participación y NPS (interactivo, con filtros en vivo). */
import { h, entero, decimal, pct, reemplazar, alSalir, fechaLarga, mesCorto, mesesEnTexto, diasEntre, sumarMeses, rangoMeses, ultimoDiaMes, textoVencimiento } from '../util.js';
import { datos, TRAMOS_VENC, BANDAS } from '../datos.js';
import { kpi, aviso, cabecera, tablaPaginada } from '../componentes.js';
import { insigniaBanda } from '../graficos.js';
import { enlaceFicha } from '../ficha.js';
import { grafico, paleta, modeloDona, modeloBarras, modeloLinea, PATRON_BANDA } from '../charts.js';
import { tarjetaGrafico, medidorAnillo, medidorSemi } from '../widgets.js';
import { resumir, ranking, topConOtros, porMes, variacion } from '../analitica.js';
import { f, barraFiltros, filtrarAfiliados, hayFiltrosCartera, alternar, alternarVarios, suscribir, textoConteo, CARTERA, rangoPeriodo, mesEnPeriodo, hashVista } from '../filtros.js';

const CORTO = { vencida: 'Ya vencida', '0-30': '0 a 30 días', '31-60': '31 a 60 días', '61-90': '61 a 90 días', '90+': 'Más de 90 días', 'sin-fecha': 'Sin fecha' };
const SEGMENTOS = [
  ['no_participan', 'sin asistencia en el último trimestre registrado'], ['vencen_90', 'vencen en 90 días o menos (incluye vencidas)'],
  ['un_solo_contacto', 'con un solo contacto en la organización'], ['nuevos_90d', 'afiliados nuevos (menos de 90 días)'], ['promotores', 'promotores (recomendación de 9 o 10)'],
];

/** Último mes completo respecto de la fecha de corte (si el corte no es fin de mes, el mes anterior). */
function ultimoMesCompleto() {
  const corte = datos.fechaCorte, mes = corte.slice(0, 7);
  return corte === ultimoDiaMes(mes) ? mes : sumarMeses(mes, -1);
}

/** Variación porcentual como indicador de KPI. */
function deltaDe(serie, meses, { buenoSube = true, unidad = '%', sufijo = '' } = {}) {
  const idx = serie.map((v, i) => (v === null || v === undefined ? -1 : i)).filter((i) => i >= 0);
  const v = variacion(serie);
  if (!v) return undefined;
  const dir = v.delta > 0 ? 'sube' : v.delta < 0 ? 'baja' : 'igual';
  const texto = v.pct === null || unidad === 'abs' ? `${v.delta > 0 ? '+' : v.delta < 0 ? '−' : ''}${entero(Math.abs(v.delta))}` : `${v.delta > 0 ? '+' : v.delta < 0 ? '−' : ''}${decimal(Math.abs(v.pct), 1)} %`;
  return { texto: sufijo ? `${texto} ${sufijo}` : texto, direccion: dir, bueno: dir === 'igual' ? null : (dir === 'sube') === buenoSube,
    titulo: `${mesCorto(meses[idx.at(-1)])}: ${decimal(v.actual, v.actual % 1 ? 2 : 0)} frente a ${mesCorto(meses[idx.at(-2)])}: ${decimal(v.previo, v.previo % 1 ? 2 : 0)}` };
}

export function vistaResumen() {
  const { resumen: R, encuestas: E } = datos;
  const TODOS = datos.afiliadosLista, tm = datos.tendencias, corte = datos.fechaCorte;
  const barra = barraFiltros({ claves: [...CARTERA, 'desde', 'hasta'] });
  const base = (excepto) => filtrarAfiliados(TODOS, excepto);

  const nps = R.nps_post_evento;
  const mesesNps = E.por_mes.filter((m) => m.n_nps > 0).map((m) => m.clave);
  const kpis1 = h('div', { class: 'rejilla c4' }), kpis2 = h('div', { class: 'rejilla c4' });

  // ---- Tarjetas de gráficos ----------------------------------------------------------------
  const crear = (cfg, alto, clic) => { const t = tarjetaGrafico(cfg); const g = grafico(t.cuerpo, { alto, clic }); return { ...t, g }; };
  const cBanda = crear({ titulo: 'Distribución por banda de riesgo', subtitulo: 'Haga clic en un segmento para filtrar todo el resumen', icono: 'dona', id: 'g-banda' }, 300,
    (i) => alternar('banda', BANDAS[i].nombre));
  const cVenc = crear({ titulo: 'Vencimientos de membresía', subtitulo: 'Afiliados por tramo de días a vencimiento', icono: 'vencimiento', id: 'g-venc' }, 300,
    (i) => alternar('venc', TRAMOS_VENC[i].id));
  const cTend = crear({ titulo: 'Asistencia mensual a eventos', subtitulo: 'Asistentes y empresas únicas por mes, con tendencia lineal y media móvil de 3 meses', icono: 'tendencia', clase: 'ancha', id: 'g-tend' }, 330,
    (i) => { const m = mesesTend[i]; if (m) alternarVarios({ desde: `${m}-01`, hasta: ultimoDiaMes(m) }); });
  const cSector = crear({ titulo: 'Sectores principales', subtitulo: 'Participación de cada sector en la cartera', icono: 'empresa', id: 'g-sector' }, 330,
    (i) => { const e = etiquetasSector[i]; if (e && e !== 'Otros') alternar('sector', e); });
  const cCal = crear({ titulo: 'Calendario de vencimientos', subtitulo: 'Afiliados que vencen cada mes, apilados por banda. Clic en un mes para filtrar por ese rango', icono: 'calendario', clase: 'ancha', id: 'g-cal' }, 320,
    (i) => { const m = mesesCal[i]; if (m) alternarVarios({ vmin: diasEntre(corte, `${m}-01`), vmax: diasEntre(corte, ultimoDiaMes(m)) }); });
  const cTipo = crear({ titulo: 'Tipo de afiliado', subtitulo: 'Empresas, consultoras, universidades y personas', icono: 'afiliados', id: 'g-tipo' }, 320,
    (i) => { if (etiquetasTipo[i]) alternar('tipo', etiquetasTipo[i]); });
  const cNivel = crear({ titulo: 'Nivel de afiliación y banda', subtitulo: 'Barras apiladas por nivel; clic para filtrar nivel y banda', icono: 'barras', id: 'g-nivel' }, 300,
    (i, d) => { if (nivelesCh[i]) alternarVarios({ nivel: nivelesCh[i], banda: BANDAS[d]?.nombre ?? '' }); });
  const cCiudad = crear({ titulo: 'Ciudades principales', subtitulo: 'Afiliados por ciudad', icono: 'mapa', id: 'g-ciudad' }, 300,
    (i) => { if (etiquetasCiudad[i]) alternar('ciudad', etiquetasCiudad[i]); });
  const hayAltas = tm.salidas?.some((v) => v !== null);
  const cAltas = hayAltas ? crear({ titulo: 'Altas y salidas por mes', subtitulo: 'Afiliaciones frente a empresas que salieron (cancelaron o expiraron); datos de todo el CRM', icono: 'tendencia', clase: 'ancha', id: 'g-altas' }, 290) : null;
  let mesesTend = [], etiquetasSector = [], mesesCal = [], etiquetasTipo = [], nivelesCh = [], etiquetasCiudad = [];

  // ---- Tabla de prioridades -------------------------------------------------------------------
  const tabla = tablaPaginada({
    etiqueta: 'Afiliados de mayor riesgo según los filtros', tamano: 8, orden: { clave: 'riesgo', dir: 'desc' },
    columnas: [
      { clave: 'id', titulo: 'Afiliado', valor: (a) => a.id, render: (a) => enlaceFicha(a.id) },
      { clave: 'banda', titulo: 'Banda', valor: (a) => a.riesgo, render: (a) => insigniaBanda(a.banda) },
      { clave: 'riesgo', titulo: 'Riesgo', valor: (a) => a.riesgo, render: (a) => decimal(a.riesgo, 1), num: true },
      { clave: 'ejecutiva', titulo: 'Ejecutiva', valor: (a) => a.ejecutiva },
      { clave: 'venc', titulo: 'Vencimiento', valor: (a) => a.dias_venc, render: (a) => textoVencimiento(a.dias_venc) },
      { clave: 'factor', titulo: 'Factor principal', valor: (a) => a.factores[0]?.t ?? '', render: (a) => a.factores[0]?.t ?? 'Sin factores' },
    ],
  });
  const enlaceTabla = h('a', { class: 'btn btn-chico', href: '#/afiliados' }, 'Abrir en Afiliados');
  const listaSegmentos = h('ul', { class: 'segmentos' });
  const notaTendencia = h('p', { class: 'nota' });

  // ---- Pintado (se ejecuta al cargar y cada vez que cambian los filtros) ---------------------------------
  function pintar() {
    const lista = filtrarAfiliados(TODOS), S = resumir(lista), n = S.n;
    barra.contador(textoConteo(n, TODOS.length));
    enlaceTabla.setAttribute('href', hashVista('afiliados'));
    const sinDatos = n === 0;

    // Series mensuales (de tendencias.json o calculadas)
    const completo = ultimoMesCompleto();
    const meses13 = rangoMeses(sumarMeses(completo, -12), completo);
    const tv = (serie, m) => { const i = tm.meses.indexOf(m); return i < 0 ? null : tm[serie][i]; };
    const nuevas = hayFiltrosCartera() ? porMes(lista, 'afiliacion', { rango: meses13 }).filas.map((x) => x.total) : meses13.map((m) => tv('afiliaciones', m) ?? 0);
    const mesesVenc = rangoMeses(sumarMeses(corte.slice(0, 7), -1), sumarMeses(corte.slice(0, 7), 8));
    const vencMes = hayFiltrosCartera() ? porMes(lista, 'expira', { rango: mesesVenc }).filas.map((x) => x.total) : mesesVenc.map((m) => tv('vencimientos', m) ?? 0);
    const idxAsist = tm.meses.map((m, i) => (tm.asistentes[i] !== null && mesEnPeriodo(m) ? i : -1)).filter((i) => i >= 0);
    mesesTend = idxAsist.map((i) => tm.meses[i]);
    const asistMes = idxAsist.map((i) => tm.asistentes[i]), empMes = idxAsist.map((i) => tm.empresas[i]);
    const idxSat = tm.meses.map((m, i) => (tm.satisfaccion[i] !== null ? i : -1)).filter((i) => i >= 0).slice(-12);
    const satMes = idxSat.map((i) => tm.satisfaccion[i]), mesesSat = idxSat.map((i) => tm.meses[i]);

    // ---- Indicadores ------------------------------------------------------------------------------
    const estados = Object.fromEntries(ranking(lista, (a) => a.estado));
    reemplazar(kpis1,
      kpi('Afiliados vigentes', entero(n), sinDatos ? 'Ningún afiliado cumple los filtros' : `${entero(estados.Activo || 0)} activos, ${entero(estados['Periodo de Gracia'] || 0)} en periodo de gracia, ${entero(estados['Pronto a Expirar'] || 0)} pronto a expirar`,
        { icono: 'afiliados', numero: { id: 'r-vig', valor: n }, spark: { datos: nuevas, descripcion: 'Nuevas afiliaciones por mes', formato: entero, pie: `Nuevas afiliaciones por mes (${mesCorto(meses13[0])} a ${mesCorto(completo)})` }, delta: deltaDe(nuevas, meses13, { sufijo: 'nuevas' }) }),
      kpi('En riesgo alto', entero(S.porBanda['Riesgo alto']), `${pct(S.pctRiesgo)} de la cartera filtrada`,
        { icono: 'riesgo', tono: 'riesgo', numero: { id: 'r-riesgo', valor: S.porBanda['Riesgo alto'] }, medidor: medidorAnillo({ valor: S.pctRiesgo, max: 100, color: 'var(--riesgo-barra)', texto: `${decimal(S.pctRiesgo, 0)} %`, etiqueta: 'Porcentaje en riesgo alto' }), enlace: hashVista('afiliados', { extra: { banda: 'Riesgo alto' } }) }),
      kpi('Vencen en 90 días o menos', entero(S.venc90), `${entero(S.vencidas)} ya vencidas aparte, ${entero(S.tramos['0-30'])} vencen en 30 días`,
        { icono: 'vencimiento', tono: 'aviso', numero: { id: 'r-v90', valor: S.venc90 }, spark: { datos: vencMes, color: 'var(--aviso-barra)', descripcion: 'Vencimientos por mes', formato: entero, pie: `Vencimientos por mes (${mesCorto(mesesVenc[0])} a ${mesCorto(mesesVenc.at(-1))})` } }),
      kpi('NPS post-evento', decimal(nps.nps, 1), `Muestra pequeña: ${nps.n} respuestas (no depende de los filtros)`,
        { icono: 'nps', tono: 'info', medidor: medidorSemi({ valor: nps.nps, min: -100, max: 100, zonas: [{ hasta: 0, color: 'var(--riesgo-barra)' }, { hasta: 50, color: 'var(--aviso-barra)' }, { hasta: 100, color: 'var(--ok-barra)' }], texto: decimal(nps.nps, 0), etiqueta: 'NPS post-evento', ancho: 120 }) }));

    reemplazar(kpis2,
      kpi('Satisfacción promedio', S.sat.media === null ? 'Sin dato' : `${decimal(S.sat.media, 2)} / 5`, `${entero(S.sat.respuestas)} respuestas de ${entero(S.sat.afiliados)} afiliados de esta selección`,
        { icono: 'satisfaccion', tono: 'ok', medidor: S.sat.media === null ? null : medidorAnillo({ valor: S.sat.media, max: 5, color: 'var(--ok-barra)', texto: decimal(S.sat.media, 1), etiqueta: 'Satisfacción sobre 5' }),
          spark: { datos: satMes, color: 'var(--ok-barra)', descripcion: 'Satisfacción mensual', formato: (v) => decimal(v, 2), pie: `Satisfacción mensual global (${mesCorto(mesesSat[0])} a ${mesCorto(mesesSat.at(-1))})` }, delta: deltaDe(satMes, mesesSat) }),
      kpi('Con asistencia en el año', pct(S.pctAsist), `${entero(S.sinAsist)} afiliados sin ninguna asistencia`,
        { icono: 'asistencia', numero: { id: 'r-asist', valor: S.pctAsist, formato: (v) => pct(v) }, medidor: medidorAnillo({ valor: S.pctAsist, max: 100, color: 'var(--primario)', texto: `${decimal(S.pctAsist, 0)} %`, etiqueta: 'Con asistencia' }),
          spark: { datos: asistMes, descripcion: 'Asistentes por mes', formato: entero, pie: 'Asistentes por mes (todos los eventos)' }, delta: deltaDe(asistMes, mesesTend, { sufijo: 'asist.' }) }),
      kpi('Con asistencia reciente', pct(S.pctAsist90), `Último trimestre registrado (hasta el ${fechaLarga(datos.ultimoEvento)})`,
        { icono: 'eventos', numero: { id: 'r-asist90', valor: S.pctAsist90, formato: (v) => pct(v) }, medidor: medidorAnillo({ valor: S.pctAsist90, max: 100, color: 'var(--cat-3)', texto: `${decimal(S.pctAsist90, 0)} %`, etiqueta: 'Con asistencia reciente' }) }),
      kpi('Salud promedio', S.saludMedia === null ? 'Sin dato' : decimal(S.saludMedia, 1), S.riesgoMedio === null ? '' : `Sobre 100 · riesgo promedio ${decimal(S.riesgoMedio, 1)}`,
        { icono: 'salud', tono: 'ok', medidor: S.saludMedia === null ? null : medidorAnillo({ valor: S.saludMedia, max: 100, color: 'var(--ok-barra)', texto: decimal(S.saludMedia, 0), etiqueta: 'Salud promedio' }) }));

    // ---- Gráficos ------------------------------------------------------------------------------------
    const listaB = base(['banda']), SB = resumir(listaB);
    const selBanda = BANDAS.findIndex((b) => b.nombre === f.banda);
    cBanda.g.poner(() => { const P = paleta(); return modeloDona({ etiquetas: BANDAS.map((b) => b.nombre), valores: BANDAS.map((b) => SB.porBanda[b.nombre]), colores: BANDAS.map((b) => P.banda[b.nombre]), patrones: BANDAS.map((b) => PATRON_BANDA[b.nombre]), seleccion: selBanda < 0 ? null : selBanda, centro: { valor: entero(SB.n), texto: 'afiliados' }, nombre: 'Afiliados', ejeCat: 'Banda' }); });

    const listaV = base(['venc']), SV = resumir(listaV);
    const selVenc = TRAMOS_VENC.findIndex((t) => t.id === f.venc);
    cVenc.g.poner(() => { const P = paleta(); return modeloBarras({ etiquetas: TRAMOS_VENC.map((t) => CORTO[t.id]), series: [{ nombre: 'Afiliados', datos: TRAMOS_VENC.map((t) => SV.tramos[t.id]),
      colores: TRAMOS_VENC.map((t) => (t.id === 'vencida' ? P.riesgo : t.id === '0-30' ? P.aviso : t.id === 'sin-fecha' ? P.otros : P.cat[0])), patrones: TRAMOS_VENC.map((t) => (t.id === 'vencida' ? 4 : t.id === '0-30' ? 1 : t.id === 'sin-fecha' ? 2 : 0)) }],
      horizontal: true, seleccion: selVenc < 0 ? null : selVenc, ejeCat: 'Tramo de vencimiento' }); });

    cTend.g.poner(() => { const P = paleta(); return modeloLinea({ etiquetas: mesesTend.map(mesCorto), series: [
      { nombre: 'Asistentes', datos: asistMes, color: P.cat[0], area: true, tendencia: 'ambas' }, { nombre: 'Empresas únicas', datos: empMes, color: P.cat[2] }], tituloY: 'Personas / empresas' }); });
    reemplazar(notaTendencia, `Asistencia registrada hasta el ${fechaLarga(datos.ultimoEvento)}. Fuente de la serie: ${datos.tendenciasCalculadas ? 'calculada en el navegador a partir de los eventos' : tm.fuente}. `,
      rangoPeriodo().desde || rangoPeriodo().hasta ? 'Hay un periodo seleccionado: use «Limpiar filtros» para ver todos los meses.' : 'Haga clic en un mes para limitar el periodo.');

    if (cAltas) {
      const fin = ultimoMesCompleto(), mesesA = rangoMeses(sumarMeses(fin, -17), fin).filter(mesEnPeriodo);
      const col = (serie) => mesesA.map((m) => { const i = tm.meses.indexOf(m); return i < 0 ? 0 : (tm[serie][i] ?? 0); });
      const altas = col('afiliaciones'), salidas = col('salidas');
      cAltas.g.poner(() => { const P = paleta(); return modeloBarras({ etiquetas: mesesA.map(mesCorto), series: [{ nombre: 'Altas', datos: altas, color: P.cat[0], patron: 0 }, { nombre: 'Salidas', datos: salidas, color: P.riesgo, patron: 4 }], etiquetasDatos: false, ejeCat: 'Mes' }); });
    }

    const listaS = base(['sector']);
    const paresSector = topConOtros(ranking(listaS, (a) => a.sector), 7);
    etiquetasSector = paresSector.map((p) => p[0]);
    const selSector = etiquetasSector.indexOf(f.sector);
    cSector.g.poner(() => modeloDona({ etiquetas: etiquetasSector, valores: paresSector.map((p) => p[1]), seleccion: selSector < 0 ? null : selSector, centro: { valor: entero(listaS.length), texto: 'afiliados' }, nombre: 'Afiliados', posicion: 'bottom', ejeCat: 'Sector' }));

    const listaC = base(['vmin', 'vmax', 'venc']);
    const filasCal = porMes(listaC, 'expira', { porBanda: true, rango: rangoMeses(datos.afiliadosLista.map((a) => a.expira).filter(Boolean).sort()[0].slice(0, 7), datos.afiliadosLista.map((a) => a.expira).filter(Boolean).sort().at(-1).slice(0, 7)) });
    mesesCal = filasCal.meses;
    cCal.g.poner(() => { const P = paleta(); return modeloBarras({ etiquetas: mesesCal.map(mesCorto), series: BANDAS.map((b) => ({ nombre: b.nombre, datos: filasCal.filas.map((x) => x[b.nombre]), color: P.banda[b.nombre] })), apilado: true, bandas: true, etiquetasDatos: false, ejeCat: 'Mes de vencimiento' }); });

    const listaT = base(['tipo']);
    const paresTipo = ranking(listaT, (a) => a.tipo);
    etiquetasTipo = paresTipo.map((p) => p[0]);
    const selTipo = etiquetasTipo.indexOf(f.tipo);
    cTipo.g.poner(() => modeloDona({ etiquetas: etiquetasTipo, valores: paresTipo.map((p) => p[1]), tipo: 'pie', seleccion: selTipo < 0 ? null : selTipo, nombre: 'Afiliados', ejeCat: 'Tipo' }));

    const listaN = base(['nivel']);
    nivelesCh = ranking(TODOS, (a) => a.nivel).map((p) => p[0]);
    const selNivel = nivelesCh.indexOf(f.nivel);
    cNivel.g.poner(() => { const P = paleta(); return modeloBarras({ etiquetas: nivelesCh, series: BANDAS.map((b) => ({ nombre: b.nombre, color: P.banda[b.nombre], datos: nivelesCh.map((nv) => listaN.filter((a) => a.nivel === nv && a.banda === b.nombre).length) })), apilado: true, bandas: true, seleccion: selNivel < 0 ? null : selNivel, ejeCat: 'Nivel' }); });

    const listaCi = base(['ciudad']);
    const paresCiudad = ranking(listaCi, (a) => a.ciudad).slice(0, 8);
    etiquetasCiudad = paresCiudad.map((p) => p[0]);
    const selCiudad = etiquetasCiudad.indexOf(f.ciudad);
    cCiudad.g.poner(() => modeloBarras({ etiquetas: etiquetasCiudad, series: [{ nombre: 'Afiliados', datos: paresCiudad.map((p) => p[1]) }], horizontal: true, seleccion: selCiudad < 0 ? null : selCiudad, ejeCat: 'Ciudad' }));

    // ---- Tabla y segmentos -------------------------------------------------------------------------------
    tabla.actualizar(lista);
    const ids = new Set(lista.map((a) => a.id));
    reemplazar(listaSegmentos, SEGMENTOS.map(([k, t]) => {
      const total = datos.segmentos.listas[k]?.length ?? datos.segmentos.conteos[k], cuenta = (datos.segmentos.listas[k] || []).filter((id) => ids.has(id)).length;
      return h('li', {}, h('strong', {}, entero(cuenta)), h('span', { class: 'suave' }, hayFiltrosCartera() ? ` de ${entero(total)}` : ''), ` ${t}`);
    }));
  }

  const fila = (clase, ...hijos) => h('div', { class: `rejilla ${clase}` }, ...hijos.map((c) => c.elemento || c));
  const raiz = h('div', { class: 'vista-resumen' },
    cabecera('Resumen ejecutivo', `Estado de la cartera de afiliados vigentes con corte al ${fechaLarga(datos.fechaCorte)}. Los datos están anonimizados; todos los indicadores y gráficos responden a los filtros.`, { icono: 'resumen' }),
    barra.elemento,
    aviso('aviso', h('strong', {}, 'El NPS post-evento se basa en una muestra pequeña. '),
      `Son ${nps.n} respuestas de ${mesesEnTexto(mesesNps)}; no equivale al NPS de la asociación, que se medirá con la encuesta de 90 días (hoy ${entero(E.resumen.encuesta_90_dias_respuestas)} respuestas).`),
    kpis1, kpis2,
    fila('c2', cBanda, cVenc),
    fila('c-2-1', h('div', { class: 'col-pila' }, cTend.elemento, notaTendencia), cSector),
    fila('c-2-1', cCal, cTipo),
    cAltas ? h('div', { class: 'rejilla' }, cAltas.elemento) : null,
    fila('c2', cNivel, cCiudad),
    h('section', { class: 'tarjeta', 'aria-labelledby': 'h-prio' },
      h('header', { class: 'tarjeta-cab' }, h('div', { class: 'tarjeta-titulos' }, h('h2', { id: 'h-prio' }, 'Afiliados que requieren atención'), h('p', { class: 'tarjeta-sub' }, 'Mayor riesgo dentro de la selección actual')), h('div', { class: 'tarjeta-acciones' }, enlaceTabla)),
      tabla.elemento),
    h('section', { class: 'tarjeta', 'aria-labelledby': 'h-seg' },
      h('header', { class: 'tarjeta-cab' }, h('div', { class: 'tarjeta-titulos' }, h('h2', { id: 'h-seg' }, 'Segmentos de acción'), h('p', { class: 'tarjeta-sub' }, 'Listas ya calculadas por el pipeline para priorizar el trabajo comercial'))),
      listaSegmentos));
  alSalir(suscribir(pintar));
  pintar();
  return raiz;
}
