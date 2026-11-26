/** Vista 5: Encuestas y NPS (tendencia de satisfacción, composición del NPS, radar y aspectos). */
import { h, entero, decimal, mesCorto, reemplazar, alSalir, rangoMeses, fechaLarga } from '../util.js';
import { datos } from '../datos.js';
import { cabecera, kpi, aviso, tablaPaginada } from '../componentes.js';
import { grafico, paleta, modeloDona, modeloBarras, modeloLinea, modeloRadar } from '../charts.js';
import { tarjetaGrafico, medidorSemi, medidorAnillo, segmentado } from '../widgets.js';
import { barraFiltros, suscribir, mesEnPeriodo } from '../filtros.js';

const ASPECTOS = {
  lugar_plataforma: 'Lugar o plataforma', convocatoria: 'Convocatoria', conferencistas: 'Conferencistas', relevancia: 'Relevancia del contenido',
  satisfaccion_global: 'Satisfacción global', asp_expositor: 'Expositor', asp_contenido: 'Contenido', asp_recepcion: 'Recepción', asp_espacio: 'Espacio', asp_alimentacion: 'Alimentación', asp_tiempo: 'Manejo del tiempo',
};
const FUENTES = { encuesta_post: 'Encuesta posterior al evento', encuesta_presencial: 'Encuesta presencial', encuesta_virtual: 'Encuesta virtual' };
const ZONAS_NPS = [{ hasta: 0, color: 'var(--riesgo-barra)' }, { hasta: 50, color: 'var(--aviso-barra)' }, { hasta: 100, color: 'var(--ok-barra)' }];

export function vistaEncuestas() {
  const { encuestas: E } = datos, tm = datos.tendencias;
  const N = E.nps_post_evento, ND = E.nps_post_afiliado_declarado;
  const barra = barraFiltros({ claves: ['desde', 'hasta'] });
  const kpis = h('div', { class: 'rejilla c4' });
  const mesesE = rangoMeses(E.por_mes[0].clave, E.por_mes.at(-1).clave);
  const porMes = new Map(E.por_mes.map((m) => [m.clave, m]));
  let seg = 'fuente';

  const tSat = tarjetaGrafico({ titulo: 'Satisfacción promedio por mes', subtitulo: 'Curva suavizada con tendencia lineal y media móvil de 3 meses (escala de 4 a 5)', icono: 'tendencia', clase: 'ancha', id: 'en-sat' });
  const gSat = grafico(tSat.cuerpo, { alto: 320 });
  const notaSat = h('p', { class: 'nota' }); tSat.cuerpo.append(notaSat);
  const tNps = tarjetaGrafico({ titulo: 'Composición del NPS post-evento', subtitulo: 'Promotores 9 o 10, pasivos 7 u 8, detractores 0 a 6', icono: 'dona', id: 'en-nps' });
  const gNps = grafico(tNps.cuerpo, { alto: 290 });
  const tResp = tarjetaGrafico({ titulo: 'Respuestas y satisfacción por mes', subtitulo: 'Barras: número de respuestas. Línea: satisfacción (eje derecho)', icono: 'barras', clase: 'ancha', id: 'en-resp' });
  const gResp = grafico(tResp.cuerpo, { alto: 300 });
  const tDecl = tarjetaGrafico({ titulo: 'NPS según se declare afiliado o no', subtitulo: 'Barras apiladas con las respuestas por categoría', icono: 'barras', id: 'en-decl' });
  const gDecl = grafico(tDecl.cuerpo, { alto: 260 });
  const tRadar = tarjetaGrafico({ titulo: 'Aspectos evaluados: presencial y virtual', subtitulo: 'Radar de la calificación media (1 a 5) en los cuatro aspectos comunes', icono: 'radar', id: 'en-radar' });
  const gRadar = grafico(tRadar.cuerpo, { alto: 320 });
  const tPost = tarjetaGrafico({ titulo: 'Aspectos de la encuesta posterior', subtitulo: 'Calificación media de 1 a 5', icono: 'barras', id: 'en-post' });
  const gPost = grafico(tPost.cuerpo, { alto: 320 });
  const tTemas = tarjetaGrafico({ titulo: 'Temas que se solicitan', subtitulo: 'Los diez más mencionados', icono: 'info', id: 'en-temas' });
  const gTemas = grafico(tTemas.cuerpo, { alto: 330 });
  const tInteres = tarjetaGrafico({ titulo: 'Interés de afiliarse (no afiliados)', subtitulo: 'Posibles candidatos para el equipo comercial', icono: 'afiliados', id: 'en-int' });
  const gInteres = grafico(tInteres.cuerpo, { alto: 330 });

  // Tabla de segmentos (una sola, con selector)
  const segmentos = {
    fuente: { titulo: 'Fuente de encuesta', filas: E.por_fuente, nombres: FUENTES }, modalidad: { titulo: 'Modalidad', filas: E.por_modalidad }, linea: { titulo: 'Línea', filas: E.por_linea },
    nivel: { titulo: 'Nivel de afiliado', filas: E.por_nivel_afiliado }, asignacion: { titulo: 'Método de asignación de empresa', filas: E.por_asignacion_empresa },
  };
  const tablaSeg = tablaPaginada({ etiqueta: 'Detalle por segmento', tamano: 50, columnas: [
    { clave: 'clave', titulo: 'Segmento', valor: (x) => x.nombre },
    { clave: 'n', titulo: 'Respuestas', valor: (x) => x.n, render: (x) => entero(x.n), num: true },
    { clave: 'sat', titulo: 'Satisfacción (1 a 5)', valor: (x) => x.satisfaccion, render: (x) => decimal(x.satisfaccion, 2), num: true },
    { clave: 'nn', titulo: 'Respuestas con NPS', valor: (x) => x.n_nps, render: (x) => entero(x.n_nps), num: true },
    { clave: 'nps', titulo: 'NPS', valor: (x) => x.nps, render: (x) => (x.nps === null ? 'Sin dato' : decimal(x.nps, 1)), num: true },
  ] });
  const tituloSeg = h('h3', { class: 'sub' });
  const pintarSeg = () => { const s = segmentos[seg]; tituloSeg.textContent = `Por ${s.titulo.toLowerCase()}`; tablaSeg.actualizar(s.filas.map((x) => ({ ...x, nombre: s.nombres?.[x.clave] || x.clave }))); };

  function pintar() {
    const sel = mesesE.filter(mesEnPeriodo);
    const filasMes = sel.map((m) => porMes.get(m) ?? null);
    const resp = filasMes.reduce((s, x) => s + (x?.n ?? 0), 0);
    const sat = resp ? filasMes.reduce((s, x) => s + (x ? x.satisfaccion * x.n : 0), 0) / resp : null;
    // Satisfacción mensual: de tendencias.json (o calculada) restringida al periodo
    const satMes = sel.map((m) => { const i = tm.meses.indexOf(m); return i < 0 ? (porMes.get(m)?.satisfaccion ?? null) : tm.satisfaccion[i]; });
    reemplazar(kpis,
      kpi('Respuestas de encuesta', entero(resp), `${entero(E.resumen.con_empresa)} con empresa identificada en total`, { icono: 'encuestas', numero: { id: 'en-r', valor: resp }, spark: { datos: filasMes.map((x) => x?.n ?? 0), descripcion: 'Respuestas por mes', pie: 'Respuestas por mes' } }),
      kpi('Satisfacción media', sat === null ? 'Sin dato' : `${decimal(sat, 2)} / 5`, 'Promedio ponderado del periodo', { icono: 'satisfaccion', tono: 'ok', medidor: sat === null ? null : medidorAnillo({ valor: sat, max: 5, color: 'var(--ok-barra)', texto: decimal(sat, 1), etiqueta: 'Satisfacción sobre 5' }), spark: { datos: satMes, color: 'var(--ok-barra)', descripcion: 'Satisfacción mensual', formato: (v) => decimal(v, 2), pie: 'Satisfacción por mes' } }),
      kpi('NPS post-evento', decimal(N.nps, 1), `Muestra pequeña: ${N.n} respuestas (no depende del periodo)`, { icono: 'nps', tono: 'info', medidor: medidorSemi({ valor: N.nps, min: -100, max: 100, zonas: ZONAS_NPS, texto: decimal(N.nps, 0), etiqueta: 'NPS post-evento', ancho: 120 }) }),
      kpi('NPS de 90 días', 'Sin datos', `${E.resumen.encuesta_90_dias_respuestas} respuestas: la encuesta aún no se aplica`, { icono: 'info' }));

    gSat.poner(() => { const P = paleta(); return modeloLinea({ etiquetas: sel.map(mesCorto), series: [{ nombre: 'Satisfacción', datos: satMes, color: P.cat[0], area: true, tendencia: 'ambas', formato: (v) => decimal(v, 2) }], min: 4, max: 5, formato: (v) => decimal(v, 2), tituloY: 'Satisfacción (1 a 5)' }); });
    notaSat.textContent = 'La escala parte de 4 para distinguir variaciones pequeñas; todos los valores son altos. Los meses con pocas respuestas (por ejemplo, los últimos) son poco estables.';

    gNps.poner(() => { const P = paleta(); return modeloDona({ etiquetas: ['Promotores', 'Pasivos', 'Detractores'], valores: [N.promotores, N.pasivos, N.detractores], colores: [P.ok, P.aviso, P.riesgo], patrones: [0, 1, 4], centro: { valor: decimal(N.nps, 0), texto: 'NPS' }, nombre: 'Respuestas' , ejeCat: 'Categoría' }); });
    gResp.poner(() => { const P = paleta(); return modeloBarras({ etiquetas: sel.map(mesCorto), series: [{ nombre: 'Respuestas', datos: filasMes.map((x) => x?.n ?? 0), color: P.cat[0] }],
      lineas: [{ nombre: 'Satisfacción', datos: satMes, color: P.cat[2], formato: (v) => decimal(v, 2) }], tituloY2: 'Satisfacción', formatoY2: (v) => decimal(v, 1), minY2: 4, maxY2: 5, ejeCat: 'Mes', etiquetasDatos: false }); });
    gDecl.poner(() => { const P = paleta(); const filas = [['Post-evento', N], ['No afiliados', ND.no_afiliado], ['Afiliados', ND.afiliado]]; return modeloBarras({ etiquetas: filas.map((x) => x[0]), horizontal: true, apilado: true,
      series: [{ nombre: 'Promotores', color: P.ok, patron: 0, datos: filas.map((x) => x[1].promotores) }, { nombre: 'Pasivos', color: P.aviso, patron: 1, datos: filas.map((x) => x[1].pasivos) }, { nombre: 'Detractores', color: P.riesgo, patron: 4, datos: filas.map((x) => x[1].detractores) }], ejeCat: 'Grupo' }); });

    const comunes = ['lugar_plataforma', 'convocatoria', 'conferencistas', 'relevancia'];
    gRadar.poner(() => { const P = paleta(); const m = modeloRadar({ ejes: comunes.map((k) => ASPECTOS[k]), series: [{ nombre: 'Presencial', datos: comunes.map((k) => E.aspectos.presencial[k]), color: P.cat[0] }, { nombre: 'Virtual', datos: comunes.map((k) => E.aspectos.virtual[k]), color: P.cat[2] }], max: 5, formato: (v) => decimal(v, 2) });
      m.cfg.options.scales.r.min = 4; m.cfg.options.scales.r.ticks.stepSize = 0.25; m.cfg.options.scales.r.ticks.callback = (v) => decimal(v, 2); return m; });
    const post = Object.entries(E.aspectos.post_evento);
    gPost.poner(() => modeloBarras({ etiquetas: post.map(([k]) => ASPECTOS[k] || k), series: [{ nombre: 'Calificación media', datos: post.map(([, v]) => v) }], horizontal: true, formato: (v) => decimal(v, 2), minValor: 1, ejeCat: 'Aspecto', leyenda: false }));
    const temas = E.temas_solicitados.slice(0, 10);
    gTemas.poner(() => modeloBarras({ etiquetas: temas.map((t) => t.tema), series: [{ nombre: 'Menciones', datos: temas.map((t) => t.n) }], horizontal: true, ejeCat: 'Tema', leyenda: false, maxRotulo: 34 }));
    const interes = Object.entries(E.interes_afiliarse_no_afiliados);
    gInteres.poner(() => modeloDona({ etiquetas: interes.map(([k]) => k), valores: interes.map(([, v]) => v), nombre: 'Respuestas', ejeCat: 'Interés', centro: { valor: entero(interes.reduce((s, [, v]) => s + v, 0)), texto: 'respuestas' } }));
  }

  const raiz = h('div', { class: 'vista-encuestas' },
    cabecera('Encuestas y NPS', 'Satisfacción y recomendación según las encuestas de eventos. Las cifras de segmentos pequeños son indicativas.', { icono: 'encuestas' }),
    barra.elemento,
    aviso('aviso', h('strong', {}, 'Advertencia de muestra. '), N.advertencia, ` Solo ${entero(N.n)} respuestas traen calificación de recomendación y no hay detractores, por lo que el NPS de ${decimal(N.nps, 1)} debe leerse con cautela.`),
    kpis,
    h('div', { class: 'rejilla c-2-1' }, h('div', { class: 'col-pila' }, tSat.elemento), tNps.elemento),
    h('div', { class: 'rejilla c-2-1' }, tResp.elemento, tDecl.elemento),
    h('div', { class: 'rejilla c2' }, tRadar.elemento, tPost.elemento),
    h('div', { class: 'rejilla c2' }, tTemas.elemento, tInteres.elemento),
    h('section', { class: 'seccion', 'aria-labelledby': 'h-seg-enc' },
      h('div', { class: 'seccion-cab' }, h('h2', { id: 'h-seg-enc', class: 'titulo-seccion' }, 'Detalle por segmento'),
        segmentado({ etiqueta: 'Segmento de la tabla', opciones: Object.entries(segmentos).map(([valor, s]) => ({ valor, texto: s.titulo })), valor: seg, alCambiar: (v) => { seg = v; pintarSeg(); } })),
      tituloSeg, tablaSeg.elemento,
      h('p', { class: 'nota' }, `De ${entero(E.resumen.respuestas)} respuestas, ${entero(E.resumen.con_evento_2026)} se asignaron a un evento de 2026 y ${entero(E.resumen.anio_2025)} son de 2025. Ninguna encuesta trae el evento, por lo que la satisfacción se informa por segmento.`)));
  alSalir(suscribir(pintar));
  pintar(); pintarSeg();
  return raiz;
}
