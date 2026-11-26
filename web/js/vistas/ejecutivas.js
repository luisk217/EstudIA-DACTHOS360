/** Vista 3: Cartera por ejecutiva (barras apiladas y agrupadas, radar, tarjetas y tabla con interacción cruzada). */
import { h, entero, decimal, pct, reemplazar, alSalir } from '../util.js';
import { datos, BANDAS } from '../datos.js';
import { cabecera, aviso, kpi, tablaPaginada } from '../componentes.js';
import { apiladaBandas, insigniaBanda } from '../graficos.js';
import { enlaceFicha } from '../ficha.js';
import { grafico, paleta, modeloBarras, modeloRadar } from '../charts.js';
import { tarjetaGrafico, medidorAnillo } from '../widgets.js';
import { resumir } from '../analitica.js';
import { f, barraFiltros, filtrarAfiliados, alternar, suscribir, textoConteo, CARTERA, hashVista } from '../filtros.js';

export function vistaEjecutivas() {
  const TODOS = datos.afiliadosLista;
  const nombres = datos.ejecutivas.ejecutivas.map((e) => e.nombre);
  const barra = barraFiltros({ claves: CARTERA });
  const kpis = h('div', { class: 'rejilla c4' });
  const contTarjetas = h('div', { class: 'rejilla c-auto' });

  const clicEj = (i) => { if (nombres[i]) alternar('ejecutiva', nombres[i]); };
  const tBandas = tarjetaGrafico({ titulo: 'Bandas de riesgo por ejecutiva', subtitulo: 'Barras apiladas; clic para filtrar por ejecutiva', icono: 'barras', id: 'e-bandas' });
  const gBandas = grafico(tBandas.cuerpo, { alto: 330, clic: clicEj });
  const tVenc = tarjetaGrafico({ titulo: 'Vencimientos por ejecutiva', subtitulo: 'Barras agrupadas por tramo de días a vencimiento', icono: 'vencimiento', id: 'e-venc' });
  const gVenc = grafico(tVenc.cuerpo, { alto: 330, clic: clicEj });
  const tRadar = tarjetaGrafico({ titulo: 'Perfil de riesgo', subtitulo: 'Radar comparativo; use la leyenda para mostrar u ocultar ejecutivas', icono: 'radar', id: 'e-radar' });
  const gRadar = grafico(tRadar.cuerpo, { alto: 360 });
  const tTam = tarjetaGrafico({ titulo: 'Riesgo alto como porcentaje de la cartera', subtitulo: 'Clic en una barra para filtrar', icono: 'riesgo', id: 'e-pct' });
  const gTam = grafico(tTam.cuerpo, { alto: 360, clic: clicEj });

  const tabla = tablaPaginada({
    etiqueta: 'Resumen por ejecutiva', tamano: 10, orden: { clave: 'cartera', dir: 'desc' },
    columnas: [
      { clave: 'nombre', titulo: 'Ejecutiva', valor: (r) => r.nombre, render: (r) => h('button', { class: 'btn-enlace', type: 'button', 'aria-pressed': String(f.ejecutiva === r.nombre), title: 'Filtrar por esta ejecutiva', onclick: () => alternar('ejecutiva', r.nombre) }, r.nombre) },
      { clave: 'cartera', titulo: 'Cartera', valor: (r) => r.S.n, render: (r) => entero(r.S.n), num: true },
      { clave: 'riesgo', titulo: 'Riesgo alto', valor: (r) => r.S.porBanda['Riesgo alto'], render: (r) => `${entero(r.S.porBanda['Riesgo alto'])} (${decimal(r.S.pctRiesgo, 1)} %)`, num: true },
      { clave: 'venc', titulo: 'Vencen en 90 d o menos', valor: (r) => r.S.venc90, render: (r) => entero(r.S.venc90), num: true },
      { clave: 'vencidas', titulo: 'Ya vencidas', valor: (r) => r.S.vencidas, render: (r) => entero(r.S.vencidas), num: true },
      { clave: 'sinasist', titulo: 'Sin asistencia en el año', valor: (r) => r.S.sinAsist, render: (r) => entero(r.S.sinAsist), num: true },
      { clave: 'medio', titulo: 'Riesgo promedio', valor: (r) => r.S.riesgoMedio, render: (r) => (r.S.riesgoMedio === null ? 'Sin dato' : decimal(r.S.riesgoMedio, 1)), num: true },
    ],
  });

  function pintar() {
    const lista = filtrarAfiliados(TODOS), S = resumir(lista);
    barra.contador(textoConteo(S.n, TODOS.length));
    // Los gráficos muestran todas las ejecutivas (resaltando la elegida); las tarjetas respetan el filtro.
    const baseG = filtrarAfiliados(TODOS, ['ejecutiva']);
    const filas = nombres.map((nombre) => ({ nombre, lista: baseG.filter((a) => a.ejecutiva === nombre) })).map((r) => ({ ...r, S: resumir(r.lista) }));
    const sel = nombres.indexOf(f.ejecutiva);
    const activas = filas.filter((r) => r.S.n > 0);

    const peor = [...activas].sort((a, b) => b.S.pctRiesgo - a.S.pctRiesgo)[0];
    reemplazar(kpis,
      kpi('Ejecutivas con cartera', entero(activas.length), `${entero(S.n)} afiliados en la selección`, { icono: 'ejecutivas', numero: { id: 'e-n', valor: activas.length } }),
      kpi('Riesgo alto en la selección', entero(S.porBanda['Riesgo alto']), `${pct(S.pctRiesgo)} de la cartera filtrada`, { icono: 'riesgo', tono: 'riesgo', numero: { id: 'e-r', valor: S.porBanda['Riesgo alto'] }, medidor: medidorAnillo({ valor: S.pctRiesgo, max: 100, color: 'var(--riesgo-barra)', texto: `${decimal(S.pctRiesgo, 0)} %`, etiqueta: 'Porcentaje en riesgo alto' }) }),
      kpi('Mayor proporción en riesgo alto', peor ? peor.nombre : 'Sin dato', peor ? `${decimal(peor.S.pctRiesgo, 1)} % de su cartera (${entero(peor.S.porBanda['Riesgo alto'])} afiliados)` : '', { icono: 'alertas', tono: 'aviso' }),
      kpi('Vencen en 90 días o menos', entero(S.venc90), `${entero(S.vencidas)} ya vencidas aparte`, { icono: 'vencimiento', tono: 'aviso', numero: { id: 'e-v', valor: S.venc90 } }));

    gBandas.poner(() => { const P = paleta(); return modeloBarras({ etiquetas: nombres, series: BANDAS.map((b) => ({ nombre: b.nombre, color: P.banda[b.nombre], datos: filas.map((r) => r.S.porBanda[b.nombre]) })), apilado: true, bandas: true, horizontal: true, seleccion: sel < 0 ? null : sel, ejeCat: 'Ejecutiva' }); });
    const TR = [['vencida', 'Ya vencidas'], ['0-30', '0 a 30 días'], ['31-60', '31 a 60 días'], ['61-90', '61 a 90 días']];
    gVenc.poner(() => modeloBarras({ etiquetas: nombres, series: TR.map(([id, nombre]) => ({ nombre, datos: filas.map((r) => r.S.tramos[id]) })), seleccion: sel < 0 ? null : sel, etiquetasDatos: false, ejeCat: 'Ejecutiva' }));
    gTam.poner(() => { const P = paleta(); return modeloBarras({ etiquetas: nombres, series: [{ nombre: '% en riesgo alto', datos: filas.map((r) => Number(decimal(r.S.pctRiesgo, 1).replace(',', '.'))), color: P.riesgo, patron: 4 }], horizontal: true, formato: (v) => `${decimal(v, 1)} %`, seleccion: sel < 0 ? null : sel, max: 60, ejeCat: 'Ejecutiva', leyenda: false }); });

    const ejes = ['% en riesgo alto', '% vence en 90 d o menos', '% sin asistencia en el año', '% sin asistencia reciente', 'Riesgo promedio'];
    const perfil = (Sx) => [Sx.pctRiesgo, Sx.n ? (Sx.venc90 / Sx.n) * 100 : 0, 100 - Sx.pctAsist, 100 - Sx.pctAsist90, Sx.riesgoMedio ?? 0];
    const orden = [...activas].sort((a, b) => b.S.riesgoMedio - a.S.riesgoMedio);
    const visibles = new Set(orden.slice(0, 3).map((r) => r.nombre));
    gRadar.poner(() => {
      const P = paleta();
      const m = modeloRadar({ ejes, series: [...activas.map((r, i) => ({ nombre: r.nombre, datos: perfil(r.S), color: P.cat[i % P.cat.length] })), { nombre: 'Cartera filtrada', datos: perfil(S), color: P.suave }], max: 100, sufijo: '' });
      m.cfg.data.datasets.forEach((d) => { d.hidden = d.label !== 'Cartera filtrada' && !visibles.has(d.label) && d.label !== f.ejecutiva; });
      return m;
    });

    reemplazar(contTarjetas, (f.ejecutiva ? filas.filter((r) => r.nombre === f.ejecutiva) : filas).filter((r) => r.S.n > 0).map((r) => {
      const id = `ej-${r.nombre.replace(/\s/g, '')}`;
      const prioritarios = [...r.lista].sort((a, b) => b.riesgo - a.riesgo || (a.dias_venc ?? 9999) - (b.dias_venc ?? 9999)).slice(0, 8);
      return h('article', { class: 'tarjeta tarjeta-ej', 'aria-labelledby': id },
        h('h2', { id }, `${r.nombre} · ${entero(r.S.n)} afiliados`),
        apiladaBandas(r.S.porBanda, `Bandas de ${r.nombre}`),
        h('dl', { class: 'datos' },
          ...[['Ya vencidas', r.S.tramos.vencida], ['Vencen en 0 a 30 días', r.S.tramos['0-30']], ['Vencen en 31 a 60 días', r.S.tramos['31-60']], ['Vencen en 61 a 90 días', r.S.tramos['61-90']],
            ['Sin asistencia en 2026', r.S.sinAsist], ['Sin asistencia reciente', r.S.n - r.S.conAsist90]].flatMap(([t, v]) => [h('dt', {}, t), h('dd', {}, entero(v))]),
          h('dt', {}, 'Riesgo promedio'), h('dd', {}, decimal(r.S.riesgoMedio, 1))),
        h('h3', { class: 'sub' }, 'Afiliados prioritarios'),
        h('ul', { class: 'leyenda' }, prioritarios.map((a) => h('li', {}, enlaceFicha(a.id), insigniaBanda(a.banda)))),
        h('p', { class: 'nota' }, 'Prioridad: mayor riesgo y cercanía del vencimiento.'),
        h('a', { href: hashVista('afiliados', { extra: { ejecutiva: r.nombre } }) }, `Ver cartera de ${r.nombre} en Afiliados`));
    }));
    tabla.actualizar(activas);
  }

  const raiz = h('div', { class: 'vista-ejecutivas' },
    cabecera('Ejecutivas', 'Cartera, bandas de riesgo, vencimientos y afiliados prioritarios de cada ejecutiva comercial. Los filtros actualizan todo en vivo.', { icono: 'ejecutivas' }),
    barra.elemento,
    aviso('info', 'Los nombres de las ejecutivas están anonimizados (KAM A a KAM F). «Sin asignar» agrupa cuentas sin responsable.'),
    kpis,
    h('div', { class: 'rejilla c2' }, tBandas.elemento, tVenc.elemento),
    h('div', { class: 'rejilla c2' }, tRadar.elemento, tTam.elemento),
    h('section', { class: 'tarjeta', 'aria-labelledby': 'h-res-ej' },
      h('header', { class: 'tarjeta-cab' }, h('div', { class: 'tarjeta-titulos' }, h('h2', { id: 'h-res-ej' }, 'Resumen por ejecutiva'), h('p', { class: 'tarjeta-sub' }, 'Ordene por cualquier columna; el nombre filtra la vista'))),
      tabla.elemento),
    h('h2', { class: 'titulo-seccion' }, 'Detalle de cada cartera'),
    contTarjetas);
  alSalir(suscribir(pintar));
  pintar();
  return raiz;
}
