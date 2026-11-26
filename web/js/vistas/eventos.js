/** Vista 4: Eventos y participación (áreas con tendencia, apilados, dona, mapa de calor) y no afiliados que asisten. */
import { h, entero, decimal, pct, fecha, mesCorto, reemplazar, alSalir, fechaLarga, rangoMeses, ultimoDiaMes } from '../util.js';
import { datos } from '../datos.js';
import { kpi, aviso, cabecera, tablaPaginada } from '../componentes.js';
import { grafico, paleta, modeloDona, modeloBarras, modeloLinea } from '../charts.js';
import { tarjetaGrafico, mapaCalor, segmentado, medidorAnillo } from '../widgets.js';
import { f, barraFiltros, filtrarEventos, alternar, alternarVarios, suscribir, textoConteo, mesEnPeriodo } from '../filtros.js';

export function vistaEventos() {
  const { eventos: E, segmentos: S } = datos;
  const T = E.totales, NA = S.asistentes_no_afiliados, tm = datos.tendencias;
  const TODOS = E.eventos;
  const barra = barraFiltros({ claves: ['desde', 'hasta', 'linea', 'modalidad'] });
  const kpis = h('div', { class: 'rejilla c4' }), kpisGlobales = h('div', { class: 'rejilla c4' });
  const meses = rangoMeses(TODOS.map((e) => e.mes).sort()[0], TODOS.map((e) => e.mes).sort().at(-1));
  const lineas = E.por_linea.map((l) => l.clave), modalidades = E.por_modalidad.map((m) => m.clave);
  let mesesVis = [], modoCalor = 'linea';

  const tablaEv = tablaPaginada({
    etiqueta: 'Eventos de 2026', tamano: 12, orden: { clave: 'fecha', dir: 'desc' },
    vacio: 'Ningún evento cumple los filtros.',
    columnas: [
      { clave: 'fecha', titulo: 'Fecha', valor: (e) => e.fecha_fin || e.fecha, render: (e) => fecha(e.fecha_fin || e.fecha) },
      { clave: 'nombre', titulo: 'Evento', valor: (e) => e.nombre },
      { clave: 'linea', titulo: 'Línea', valor: (e) => e.linea },
      { clave: 'modalidad', titulo: 'Modalidad', valor: (e) => e.modalidad },
      { clave: 'asistentes', titulo: 'Asistentes', valor: (e) => e.asistentes, render: (e) => entero(e.asistentes), num: true },
      { clave: 'vigentes', titulo: 'Empresas afiliadas', valor: (e) => e.empresas_vigentes, render: (e) => entero(e.empresas_vigentes), num: true },
      { clave: 'sat', titulo: 'Satisfacción', valor: (e) => e.satisfaccion, render: (e) => (e.satisfaccion === null ? 'Sin dato' : `${decimal(e.satisfaccion, 2)} (${e.n_respuestas})`), num: true },
    ],
  });
  const tablaNa = tablaPaginada({
    etiqueta: 'Empresas no afiliadas vigentes que asisten', tamano: 10, orden: { clave: 'asistentes', dir: 'desc' },
    columnas: [
      { clave: 'id', titulo: 'Empresa', valor: (x) => x.id },
      { clave: 'estado', titulo: 'Estado en el CRM', valor: (x) => x.estado_crm, render: (x) => x.estado_crm || 'No figura en el CRM' },
      { clave: 'asistentes', titulo: 'Asistentes', valor: (x) => x.asistentes, render: (x) => entero(x.asistentes), num: true },
      { clave: 'eventos', titulo: 'Eventos', valor: (x) => x.eventos, render: (x) => entero(x.eventos), num: true },
      { clave: 'ultima', titulo: 'Última asistencia', valor: (x) => x.ultima, render: (x) => fecha(x.ultima) },
    ],
  });
  tablaNa.actualizar(NA.top);

  const clicMes = (i) => { const m = mesesVis[i]; if (m) alternarVarios({ desde: `${m}-01`, hasta: ultimoDiaMes(m) }); };
  const tTend = tarjetaGrafico({ titulo: 'Asistentes por mes', subtitulo: 'Área con tendencia lineal y media móvil de 3 meses. Clic en un mes para limitar el periodo', icono: 'tendencia', clase: 'ancha', id: 'ev-tend' });
  const gTend = grafico(tTend.cuerpo, { alto: 330, clic: clicMes });
  const notaTend = h('p', { class: 'nota' }); tTend.cuerpo.append(notaTend);
  const tLineaDona = tarjetaGrafico({ titulo: 'Por línea', subtitulo: 'Clic para filtrar', icono: 'dona', id: 'ev-linea' });
  const gLinea = grafico(tLineaDona.cuerpo, { alto: 330, clic: (i) => alternar('linea', lineas[i]) });
  const tApil = tarjetaGrafico({ titulo: 'Asistentes por mes y línea', subtitulo: 'Barras apiladas; clic en un segmento para filtrar la línea', icono: 'barras', clase: 'ancha', id: 'ev-apil' });
  const gApil = grafico(tApil.cuerpo, { alto: 320, clic: (_i, d) => alternar('linea', lineas[d]) });
  const tMod = tarjetaGrafico({ titulo: 'Por modalidad', subtitulo: 'Clic para filtrar', icono: 'dona', id: 'ev-mod' });
  const gMod = grafico(tMod.cuerpo, { alto: 320, clic: (i) => alternar('modalidad', modalidades[i]) });
  const calorCont = h('div', {});
  const tCalor = tarjetaGrafico({ titulo: 'Mapa de calor de asistencia', subtitulo: 'Asistentes por mes; la intensidad indica el volumen. Clic en una celda para filtrar', icono: 'mapa', clase: 'ancha', id: 'ev-calor',
    acciones: segmentado({ etiqueta: 'Agrupar mapa de calor por', opciones: [{ valor: 'linea', texto: 'Por línea' }, { valor: 'modalidad', texto: 'Por modalidad' }], valor: modoCalor, alCambiar: (v) => { modoCalor = v; pintar(); } }) });
  tCalor.cuerpo.append(calorCont);
  const tPromedio = tarjetaGrafico({ titulo: 'Promedio de asistentes por evento', subtitulo: 'Por línea, según los filtros', icono: 'barras', id: 'ev-prom' });
  const gProm = grafico(tPromedio.cuerpo, { alto: 260, clic: (i) => alternar('linea', lineas[i]) });
  const tCargo = tarjetaGrafico({ titulo: 'Nivel de cargo de los asistentes', subtitulo: 'Todo el año (no cambia con los filtros)', icono: 'personas', id: 'ev-cargo' });
  const gCargo = grafico(tCargo.cuerpo, { alto: 260 });

  function pintar() {
    const evs = filtrarEventos(TODOS);
    barra.contador(textoConteo(evs.length, TODOS.length, 'eventos'));
    mesesVis = meses.filter(mesEnPeriodo);
    const sumaMes = (lista, fn) => mesesVis.map((m) => lista.filter((e) => e.mes === m).reduce((s, e) => s + fn(e), 0));
    const asistMes = sumaMes(evs, (e) => e.asistentes), evMes = sumaMes(evs, () => 1);
    const totalAsist = asistMes.reduce((s, x) => s + x, 0);
    const conAsist = evs.filter((e) => e.asistentes > 0);
    const conSat = evs.filter((e) => e.satisfaccion !== null && e.n_respuestas > 0);
    const respTot = conSat.reduce((s, e) => s + e.n_respuestas, 0), sat = respTot ? conSat.reduce((s, e) => s + e.satisfaccion * e.n_respuestas, 0) / respTot : null;
    const mayor = [...evs].sort((a, b) => b.asistentes - a.asistentes)[0];
    const delta = (serie, buenoSube = true) => {
      const idx = serie.map((v, i) => (v ? i : -1)).filter((i) => i >= 0);
      if (idx.length < 2) return undefined;
      const a = serie[idx.at(-1)], b = serie[idx.at(-2)], d = ((a - b) / b) * 100;
      return { texto: `${d >= 0 ? '+' : '−'}${decimal(Math.abs(d), 1)} %`, direccion: d > 0 ? 'sube' : d < 0 ? 'baja' : 'igual', bueno: d === 0 ? null : (d > 0) === buenoSube, titulo: `${mesCorto(mesesVis[idx.at(-1)])}: ${entero(a)} frente a ${mesCorto(mesesVis[idx.at(-2)])}: ${entero(b)}` };
    };
    reemplazar(kpis,
      kpi('Eventos', entero(evs.length), `${entero(conAsist.length)} con asistencia registrada`, { icono: 'eventos', numero: { id: 'ev-n', valor: evs.length }, spark: { datos: evMes, descripcion: 'Eventos por mes', pie: 'Eventos por mes' } }),
      kpi('Asistencias válidas', entero(totalAsist), 'Registros por persona y evento', { icono: 'asistencia', numero: { id: 'ev-a', valor: totalAsist }, spark: { datos: asistMes, descripcion: 'Asistentes por mes', pie: 'Asistentes por mes' }, delta: delta(asistMes) }),
      kpi('Promedio por evento', conAsist.length ? entero(totalAsist / conAsist.length) : 'Sin dato', mayor ? `Mayor: ${mayor.nombre.slice(0, 48)}${mayor.nombre.length > 48 ? '…' : ''} (${entero(mayor.asistentes)})` : 'Sin eventos', { icono: 'personas' }),
      kpi('Satisfacción de eventos', sat === null ? 'Sin dato' : `${decimal(sat, 2)} / 5`, `${entero(respTot)} respuestas en ${entero(conSat.length)} eventos con encuesta`, { icono: 'satisfaccion', tono: 'ok', medidor: sat === null ? null : medidorAnillo({ valor: sat, max: 5, color: 'var(--ok-barra)', texto: decimal(sat, 1), etiqueta: 'Satisfacción de eventos' }) }));
    reemplazar(kpisGlobales,
      kpi('Personas distintas', entero(T.personas), 'Todo el año; no cambia con los filtros', { icono: 'personas' }),
      kpi('Empresas participantes', entero(T.empresas), 'Afiliadas o no', { icono: 'empresa' }),
      kpi('Empresas afiliadas vigentes', entero(T.empresas_vigentes), `${decimal((T.empresas_vigentes / datos.resumen.afiliados_vigentes) * 100, 1)} % de la cartera`, { icono: 'afiliados', tono: 'info', medidor: medidorAnillo({ valor: (T.empresas_vigentes / datos.resumen.afiliados_vigentes) * 100, max: 100, color: 'var(--primario)', texto: `${decimal((T.empresas_vigentes / datos.resumen.afiliados_vigentes) * 100, 0)} %`, etiqueta: 'Cartera con participación' }) }),
      kpi('No afiliadas con asistencia', entero(NA.empresas_total), `${entero(NA.asistentes_total)} asistencias: candidatas a afiliación`, { icono: 'alertas', tono: 'aviso' }));

    // Tendencia mensual (con empresas únicas de tendencias.json cuando no hay filtros de línea o modalidad)
    const sinCorte = !f.linea && !f.modalidad;
    const empMes = sinCorte ? mesesVis.map((m) => { const i = tm.meses.indexOf(m); return i < 0 ? null : tm.empresas[i]; }) : null;
    gTend.poner(() => { const P = paleta(); return modeloLinea({ etiquetas: mesesVis.map(mesCorto), series: [{ nombre: 'Asistentes', datos: asistMes, color: P.cat[0], area: true, tendencia: 'ambas' },
      ...(empMes && empMes.some((v) => v !== null) ? [{ nombre: 'Empresas únicas', datos: empMes, color: P.cat[2] }] : [])], tituloY: 'Asistentes' }); });
    notaTend.textContent = `Asistencia registrada hasta el ${fechaLarga(datos.ultimoEvento)}: el último mes puede estar incompleto. ${sinCorte ? '' : 'Con filtros de línea o modalidad no se muestran las empresas únicas.'}`;

    // Línea y modalidad (dona/pie) sin su propio filtro, para resaltar la selección
    const evL = filtrarEventos(TODOS, ['linea']);
    const valL = lineas.map((l) => evL.filter((e) => e.linea === l).reduce((s, e) => s + e.asistentes, 0));
    const selL = lineas.indexOf(f.linea);
    gLinea.poner(() => modeloDona({ etiquetas: lineas, valores: valL, seleccion: selL < 0 ? null : selL, centro: { valor: entero(valL.reduce((s, x) => s + x, 0)), texto: 'asistentes' }, nombre: 'Asistentes', ejeCat: 'Línea' }));
    const evM = filtrarEventos(TODOS, ['modalidad']);
    const valM = modalidades.map((m) => evM.filter((e) => e.modalidad === m).reduce((s, e) => s + e.asistentes, 0));
    const selM = modalidades.indexOf(f.modalidad);
    gMod.poner(() => modeloDona({ etiquetas: modalidades, valores: valM, tipo: 'pie', seleccion: selM < 0 ? null : selM, nombre: 'Asistentes', ejeCat: 'Modalidad' }));

    gApil.poner(() => modeloBarras({ etiquetas: mesesVis.map(mesCorto), series: lineas.map((l) => ({ nombre: l, datos: mesesVis.map((m) => evL.filter((e) => e.mes === m && e.linea === l).reduce((s, e) => s + e.asistentes, 0)) })), apilado: true, etiquetasDatos: false, ejeCat: 'Mes' }));

    // Mapa de calor
    const dim = modoCalor === 'linea' ? 'linea' : 'modalidad', claves = modoCalor === 'linea' ? lineas : modalidades;
    const evC = filtrarEventos(TODOS, [dim]);
    reemplazar(calorCont, mapaCalor({
      filas: claves.map((c) => ({ clave: c, etiqueta: c, valores: mesesVis.map((m) => evC.filter((e) => e.mes === m && e[dim] === c).reduce((s, e) => s + e.asistentes, 0)) })),
      columnas: mesesVis.map(mesCorto), tituloFila: modoCalor === 'linea' ? 'Línea' : 'Modalidad', unidad: 'asistentes', seleccion: f[dim] || null,
      onClic: (clave, j) => alternarVarios({ [dim]: clave, desde: `${mesesVis[j]}-01`, hasta: ultimoDiaMes(mesesVis[j]) }) }));

    const prom = lineas.map((l) => { const x = evL.filter((e) => e.linea === l && e.asistentes > 0); return x.length ? x.reduce((s, e) => s + e.asistentes, 0) / x.length : 0; });
    gProm.poner(() => modeloBarras({ etiquetas: lineas, series: [{ nombre: 'Promedio de asistentes', datos: prom.map((v) => Math.round(v)) }], horizontal: true, seleccion: selL < 0 ? null : selL, ejeCat: 'Línea', leyenda: false }));
    gCargo.poner(() => modeloBarras({ etiquetas: E.por_nivel_cargo.map((c) => c.clave), series: [{ nombre: 'Asistentes', datos: E.por_nivel_cargo.map((c) => c.asistentes) }], horizontal: true, ejeCat: 'Nivel de cargo', leyenda: false, maxRotulo: 24 }));
    tablaEv.actualizar(evs);
  }

  const raiz = h('div', { class: 'vista-eventos' },
    cabecera('Eventos y participación', 'Asistencia a los eventos de 2026 por mes, línea y modalidad, y empresas no afiliadas que participan.', { icono: 'eventos' }),
    barra.elemento,
    aviso('aviso', `El libro de asistencia llega hasta el ${fechaLarga(datos.ultimoEvento)}: no incluye eventos posteriores, lo que limita la lectura de la participación reciente.`),
    kpis, kpisGlobales,
    h('div', { class: 'rejilla c-2-1' }, tTend.elemento, tLineaDona.elemento),
    h('div', { class: 'rejilla c-2-1' }, tApil.elemento, tMod.elemento),
    h('div', { class: 'rejilla' }, tCalor.elemento),
    h('div', { class: 'rejilla c2' }, tPromedio.elemento, tCargo.elemento),
    h('section', { class: 'seccion', 'aria-labelledby': 'h-eventos' }, h('h2', { id: 'h-eventos', class: 'titulo-seccion' }, 'Eventos de 2026'), tablaEv.elemento),
    h('section', { class: 'seccion', 'aria-labelledby': 'h-na' },
      h('h2', { id: 'h-na', class: 'titulo-seccion' }, 'Asistentes no afiliados: candidatos a afiliación'),
      h('p', { class: 'suave' }, `${entero(NA.empresas_total)} empresas sin afiliación vigente reunieron ${entero(NA.asistentes_total)} asistencias. Se listan las 60 con mayor participación; las que figuran como canceladas o expiradas pueden ser candidatas a reafiliación y las que no figuran en el CRM, a primera afiliación.`),
      tablaNa.elemento));
  alSalir(suscribir(pintar));
  pintar();
  return raiz;
}
