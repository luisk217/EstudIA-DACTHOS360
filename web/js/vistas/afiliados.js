/** Vista 2: Afiliados (dispersión riesgo y vencimiento, filtros en vivo, tabla con orden y paginación; ficha al abrir). */
import { h, entero, decimal, pct, fecha, alSalir, descargarCsv, textoVencimiento } from '../util.js';
import { datos, BANDAS } from '../datos.js';
import { cabecera, kpi, tablaPaginada } from '../componentes.js';
import { insigniaBanda } from '../graficos.js';
import { enlaceFicha, abrirFicha } from '../ficha.js';
import { grafico, paleta, modeloDona, modeloBarras, modeloDispersion, PATRON_BANDA } from '../charts.js';
import { tarjetaGrafico, medidorAnillo } from '../widgets.js';
import { resumir, ranking } from '../analitica.js';
import { f, barraFiltros, filtrarAfiliados, alternar, suscribir, textoConteo, CARTERA } from '../filtros.js';
import { reemplazar } from '../util.js';

const FORMAS_BANDA = { Saludable: 'circle', Atención: 'triangle', 'Riesgo alto': 'rectRot' };

export function vistaAfiliados() {
  const TODOS = datos.afiliadosLista, U = datos.meta.score.umbrales;
  const barra = barraFiltros({ claves: CARTERA, busqueda: true });
  const kpis = h('div', { class: 'rejilla c4' });
  let gruposDisp = [], etiquetasEstado = [];

  const tDisp = tarjetaGrafico({ titulo: 'Riesgo frente a días a vencimiento', subtitulo: 'Cada punto es un afiliado. Clic en un punto para abrir su ficha', icono: 'dispersion', clase: 'ancha', id: 'g-disp' });
  const gDisp = grafico(tDisp.cuerpo, { alto: 470, clic: (i, d) => { const p = gruposDisp[d]?.puntos[i]; if (p) abrirFicha(p.id); } });
  const notaDisp = h('p', { class: 'nota' });
  tDisp.cuerpo.append(notaDisp);
  const tBanda = tarjetaGrafico({ titulo: 'Bandas de riesgo', subtitulo: 'Clic para filtrar', icono: 'dona', id: 'g-banda2' });
  const gBanda = grafico(tBanda.cuerpo, { alto: 250, clic: (i) => alternar('banda', BANDAS[i].nombre) });
  const tEstado = tarjetaGrafico({ titulo: 'Estado en el CRM', subtitulo: 'Clic para filtrar', icono: 'barras', id: 'g-estado' });
  const gEstado = grafico(tEstado.cuerpo, { alto: 190, clic: (i) => { if (etiquetasEstado[i]) alternar('estado', etiquetasEstado[i]); } });

  const columnas = [
    { clave: 'id', titulo: 'Afiliado', valor: (a) => a.id, render: (a) => enlaceFicha(a.id) },
    { clave: 'banda', titulo: 'Banda', valor: (a) => a.riesgo, render: (a) => insigniaBanda(a.banda) },
    { clave: 'riesgo', titulo: 'Riesgo', valor: (a) => a.riesgo, render: (a) => decimal(a.riesgo, 1), num: true },
    { clave: 'nivel', titulo: 'Nivel', valor: (a) => a.nivel },
    { clave: 'ejecutiva', titulo: 'Ejecutiva', valor: (a) => a.ejecutiva },
    { clave: 'estado', titulo: 'Estado', valor: (a) => a.estado },
    { clave: 'dias_venc', titulo: 'Vencimiento', valor: (a) => a.dias_venc,
      render: (a) => (a.expira ? `${fecha(a.expira)} (${a.dias_venc < 0 ? `hace ${entero(-a.dias_venc)} d` : `en ${entero(a.dias_venc)} d`})` : 'Sin fecha') },
    { clave: 'asist', titulo: 'Asist. 2026', valor: (a) => a.asist, render: (a) => entero(a.asist), num: true },
    { clave: 'sat', titulo: 'Satisf.', valor: (a) => a.sat, render: (a) => (a.sat === null ? 'Sin dato' : decimal(a.sat, 2)), num: true },
  ];
  const tabla = tablaPaginada({ etiqueta: 'Afiliados vigentes', columnas, tamano: 20, orden: { clave: 'riesgo', dir: 'desc' } });
  const conteo = h('p', { 'aria-live': 'polite', class: 'suave conteo-tabla' });
  let filtrada = [];
  const exportar = h('button', { class: 'btn btn-chico', type: 'button', onclick: () => {
    descargarCsv('afiliados-filtrados.csv', ['afiliado', 'banda', 'riesgo', 'nivel', 'estado', 'ejecutiva', 'sector', 'ciudad', 'expira', 'dias_a_vencimiento', 'asistencias_2026', 'satisfaccion'],
      filtrada.map((a) => [a.id, a.banda, a.riesgo, a.nivel, a.estado, a.ejecutiva, a.sector, a.ciudad, a.expira, a.dias_venc, a.asist, a.sat]));
  } }, 'Exportar selección (CSV)');

  function pintar() {
    filtrada = filtrarAfiliados(TODOS);
    const S = resumir(filtrada);
    barra.contador(textoConteo(S.n, TODOS.length));
    conteo.textContent = `${entero(S.n)} de ${entero(TODOS.length)} afiliados cumplen los filtros.`;
    reemplazar(kpis,
      kpi('Afiliados en la selección', entero(S.n), `${pct(TODOS.length ? (S.n / TODOS.length) * 100 : 0)} de la cartera`, { icono: 'afiliados', numero: { id: 'a-n', valor: S.n } }),
      kpi('Riesgo promedio', S.riesgoMedio === null ? 'Sin dato' : decimal(S.riesgoMedio, 1), S.saludMedia === null ? '' : `Salud promedio ${decimal(S.saludMedia, 1)}`, { icono: 'salud', medidor: S.riesgoMedio === null ? null : medidorAnillo({ valor: S.riesgoMedio, max: 100, color: 'var(--aviso-barra)', texto: decimal(S.riesgoMedio, 0), etiqueta: 'Riesgo promedio' }) }),
      kpi('En riesgo alto', entero(S.porBanda['Riesgo alto']), `${pct(S.pctRiesgo)} de la selección`, { icono: 'riesgo', tono: 'riesgo', numero: { id: 'a-r', valor: S.porBanda['Riesgo alto'] } }),
      kpi('Vencen en 90 días o menos', entero(S.venc90), `${entero(S.vencidas)} ya vencidas aparte`, { icono: 'vencimiento', tono: 'aviso', numero: { id: 'a-v', valor: S.venc90 } }));

    const conFecha = filtrada.filter((a) => a.dias_venc !== null);
    gruposDisp = BANDAS.map((b) => ({ nombre: b.nombre, forma: FORMAS_BANDA[b.nombre], color: '', puntos: conFecha.filter((a) => a.banda === b.nombre).map((a) => ({ x: a.dias_venc, y: a.riesgo, id: a.id,
      info: [`Riesgo ${decimal(a.riesgo, 1)} · ${textoVencimiento(a.dias_venc)}`, `${a.nivel} · ${a.ejecutiva}`, a.sector ?? 'Sin sector'] })) }));
    gDisp.poner(() => {
      const P = paleta(); gruposDisp.forEach((g) => { g.color = P.banda[g.nombre]; });
      return modeloDispersion({ grupos: gruposDisp, tituloX: 'Días a vencimiento (negativo: ya vencida)', tituloY: 'Riesgo (0 a 100)', minX: -360, maxX: 420,
        referencias: { x: [{ valor: 0, etiqueta: 'Fecha de corte', color: P.texto }], y: [{ valor: U.umbral_atencion, etiqueta: `Atención ${U.umbral_atencion}`, color: P.aviso }, { valor: U.umbral_riesgo_alto, etiqueta: `Riesgo alto ${U.umbral_riesgo_alto}`, color: P.riesgo }],
          zonas: [{ desde: 0, hasta: U.umbral_atencion, color: P.ok, alfa: 0.05 }, { desde: U.umbral_atencion, hasta: U.umbral_riesgo_alto, color: P.aviso, alfa: 0.06 }, { desde: U.umbral_riesgo_alto, hasta: 100, color: P.riesgo, alfa: 0.07 }] } });
    });
    const sinFecha = filtrada.length - conFecha.length;
    notaDisp.textContent = `${entero(conFecha.length)} afiliados con fecha de expiración${sinFecha ? `; ${entero(sinFecha)} sin fecha no se dibujan` : ''}. Las bandas se distinguen por color y por forma del punto (círculo, triángulo y rombo).`;

    const listaB = filtrarAfiliados(TODOS, ['banda']), SB = resumir(listaB), selB = BANDAS.findIndex((b) => b.nombre === f.banda);
    gBanda.poner(() => { const P = paleta(); return modeloDona({ etiquetas: BANDAS.map((b) => b.nombre), valores: BANDAS.map((b) => SB.porBanda[b.nombre]), colores: BANDAS.map((b) => P.banda[b.nombre]), patrones: BANDAS.map((b) => PATRON_BANDA[b.nombre]), seleccion: selB < 0 ? null : selB, centro: { valor: entero(SB.n), texto: 'afiliados' }, nombre: 'Afiliados', ejeCat: 'Banda', posicion: 'right' }); });
    const pares = ranking(filtrarAfiliados(TODOS, ['estado']), (a) => a.estado);
    etiquetasEstado = pares.map((p) => p[0]);
    const selE = etiquetasEstado.indexOf(f.estado);
    gEstado.poner(() => modeloBarras({ etiquetas: etiquetasEstado, series: [{ nombre: 'Afiliados', datos: pares.map((p) => p[1]) }], horizontal: true, seleccion: selE < 0 ? null : selE, ejeCat: 'Estado' }));
    tabla.actualizar(filtrada);
  }

  const raiz = h('div', { class: 'vista-afiliados' },
    cabecera('Afiliados', 'Busque, filtre y ordene la cartera. Abra un afiliado para ver su score, los factores que lo explican y la acción sugerida.', { icono: 'afiliados' }),
    barra.elemento, kpis,
    h('div', { class: 'rejilla c-2-1' }, tDisp.elemento, h('div', { class: 'col-pila' }, tBanda.elemento, tEstado.elemento)),
    h('section', { class: 'tarjeta', 'aria-labelledby': 'h-lista' },
      h('header', { class: 'tarjeta-cab' }, h('div', { class: 'tarjeta-titulos' }, h('h2', { id: 'h-lista' }, 'Lista de afiliados'), conteo), h('div', { class: 'tarjeta-acciones' }, exportar)),
      tabla.elemento));
  alSalir(suscribir(pintar));
  pintar();
  return raiz;
}
