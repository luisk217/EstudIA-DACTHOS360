/**
 * Vista 6: Alertas (módulo central).
 * Crear, editar, activar, duplicar y eliminar reglas; evaluarlas sobre los
 * afiliados en el navegador; exportar listas a CSV y reglas a JSON.
 */
import { h, entero, decimal, fecha, descargarCsv, descargarTexto, reemplazar, contar } from '../util.js';
import { datos } from '../datos.js';
import { cabecera, kpi, aviso, tablaPaginada, crearDialogo, confirmar, campoSelect } from '../componentes.js';
import { barrasH, insigniaBanda } from '../graficos.js';
import { grafico, paleta, modeloBarras, modeloDona, PATRON_BANDA } from '../charts.js';
import { tarjetaGrafico } from '../widgets.js';
import { BANDAS } from '../datos.js';
import { enlaceFicha } from '../ficha.js';
import {
  almacen, campos, OPERADORES, SEVERIDADES, PLANTILLAS, evaluar, describirRegla, validarRegla, reglaDesdePlantilla,
  guardarRegla, eliminarRegla, duplicarRegla, guardarReglas, exportarReglasJson, importarReglasJson, reglasPorAfiliado,
} from '../reglas.js';

const etiquetaSeveridad = (id) => SEVERIDADES.find((s) => s.id === id)?.etiqueta ?? id;
const simboloSev = { alta: '◆', media: '▲', baja: '●' };
const insigniaSeveridad = (id) => h('span', { class: `insignia s-${id}` }, `${simboloSev[id]} ${etiquetaSeveridad(id)}`);
const slug = (t) => t.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 50) || 'regla';

export function vistaAlertas() {
  let seleccionada = almacen.reglas[0]?.id ?? null;
  const mensaje = h('div', { role: 'status', 'aria-live': 'polite' });
  const contKpi = h('div', { class: 'rejilla c3' });
  const contLista = h('div', {});
  const contDetalle = h('div', {});
  const tReglas = tarjetaGrafico({ titulo: 'Afiliados por regla', subtitulo: 'Clic en una barra para ver su detalle', icono: 'alertas', id: 'al-reglas' });
  const gReglas = grafico(tReglas.cuerpo, { alto: 250, clic: (i) => { const r = almacen.reglas[i]; if (r) { seleccionada = r.id; pintar(`[data-sel="${r.id}"]`); } } });
  const tBandas = tarjetaGrafico({ titulo: 'Afiliados con alerta por banda', subtitulo: 'Afiliados únicos con alguna regla activa', icono: 'dona', id: 'al-bandas' });
  const gBandas = grafico(tBandas.cuerpo, { alto: 250 });
  const tabla = tablaPaginada({
    etiqueta: 'Afiliados que activan la regla seleccionada', tamano: 15, orden: { clave: 'riesgo', dir: 'desc' },
    vacio: 'Ningún afiliado activa esta regla con los datos actuales.',
    columnas: [
      { clave: 'id', titulo: 'Afiliado', valor: (a) => a.id, render: (a) => enlaceFicha(a.id) },
      { clave: 'banda', titulo: 'Banda', valor: (a) => a.riesgo, render: (a) => insigniaBanda(a.banda) },
      { clave: 'riesgo', titulo: 'Riesgo', valor: (a) => a.riesgo, render: (a) => decimal(a.riesgo, 1), num: true },
      { clave: 'ejecutiva', titulo: 'Ejecutiva', valor: (a) => a.ejecutiva },
      { clave: 'nivel', titulo: 'Nivel', valor: (a) => a.nivel },
      { clave: 'dias_venc', titulo: 'Vencimiento', valor: (a) => a.dias_venc, render: (a) => (a.expira ? `${fecha(a.expira)} (${a.dias_venc} d)` : 'Sin fecha') },
      { clave: 'asist', titulo: 'Asist. 2026', valor: (a) => a.asist, render: (a) => entero(a.asist), num: true },
    ],
  });

  /** Avisa por la región en vivo (y la deja visible como aviso). */
  const decir = (tipo, texto) => reemplazar(mensaje, aviso(tipo, texto));

  // ---- Exportaciones ---------------------------------------------------------
  const filaCsv = (a, r) => [a.id, a.banda, a.riesgo, a.salud, a.nivel, a.tipo, a.sector, a.ejecutiva, a.estado, a.expira, a.dias_venc, a.asist, a.asist_90d, a.sat, a.accion, r.nombre, etiquetaSeveridad(r.severidad)];
  const ENCAB = ['afiliado', 'banda', 'riesgo', 'salud', 'nivel', 'tipo', 'sector', 'ejecutiva', 'estado', 'expira', 'dias_a_vencimiento', 'asistencias_2026', 'asistencias_90d', 'satisfaccion', 'accion_sugerida', 'regla', 'severidad'];
  const exportarRegla = (r) => { const lista = evaluar(r); descargarCsv(`alerta-${slug(r.nombre)}.csv`, ENCAB, lista.map((a) => filaCsv(a, r))); decir('ok', `Se exportaron ${entero(lista.length)} afiliados de la regla «${r.nombre}».`); };
  const exportarTodas = () => {
    const filas = almacen.reglas.filter((r) => r.activa).flatMap((r) => evaluar(r).map((a) => filaCsv(a, r)));
    descargarCsv('alertas-activas.csv', ENCAB, filas);
    decir('ok', `Se exportaron ${entero(filas.length)} alertas de las reglas activas.`);
  };

  // ---- Pintado -----------------------------------------------------------------
  function pintar(enfocar) {
    const resultados = new Map(almacen.reglas.map((r) => [r.id, evaluar(r)]));
    const activas = almacen.reglas.filter((r) => r.activa);
    const afectados = reglasPorAfiliado();
    const altas = new Set(activas.filter((r) => r.severidad === 'alta').flatMap((r) => resultados.get(r.id).map((a) => a.id)));
    reemplazar(contKpi,
      kpi('Reglas activas', `${activas.length} de ${almacen.reglas.length}`, 'Las desactivadas no se cuentan en los totales', { icono: 'alertas' }),
      kpi('Afiliados con alguna alerta', entero(afectados.size), `${decimal((afectados.size / datos.afiliadosLista.length) * 100, 1)} % de la cartera, sin duplicar`, { icono: 'afiliados', tono: 'aviso' }),
      kpi('Con alerta de severidad alta', entero(altas.size), 'Afiliados únicos', { icono: 'riesgo', tono: 'riesgo' }));

    if (!almacen.reglas.some((r) => r.id === seleccionada)) seleccionada = almacen.reglas[0]?.id ?? null;
    const idxSel = almacen.reglas.findIndex((r) => r.id === seleccionada);
    gReglas.poner(() => {
      const P = paleta(), col = { alta: P.riesgo, media: P.aviso, baja: P.ok }, pat = { alta: 4, media: 1, baja: 0 };
      return modeloBarras({ etiquetas: almacen.reglas.map((r) => r.nombre), horizontal: true, leyenda: false, ejeCat: 'Regla', maxRotulo: 40, seleccion: idxSel < 0 ? null : idxSel,
        series: [{ nombre: 'Afiliados', datos: almacen.reglas.map((r) => resultados.get(r.id).length), colores: almacen.reglas.map((r) => col[r.severidad] || P.primario), patrones: almacen.reglas.map((r) => pat[r.severidad] ?? 0) }] });
    });
    const porBandaAl = Object.fromEntries(BANDAS.map((b) => [b.nombre, 0]));
    for (const id of afectados.keys()) porBandaAl[datos.porId.get(id).banda] += 1;
    gBandas.poner(() => { const P = paleta(); return modeloDona({ etiquetas: BANDAS.map((b) => b.nombre), valores: BANDAS.map((b) => porBandaAl[b.nombre]), colores: BANDAS.map((b) => P.banda[b.nombre]), patrones: BANDAS.map((b) => PATRON_BANDA[b.nombre]), centro: { valor: entero(afectados.size), texto: 'afiliados' }, nombre: 'Afiliados', ejeCat: 'Banda', posicion: 'right' }); });
    reemplazar(contLista, almacen.reglas.length
      ? h('ul', { class: 'lista-reglas', 'aria-label': 'Reglas de alerta' }, almacen.reglas.map((r) => itemRegla(r, resultados.get(r.id).length)))
      : h('div', { class: 'vacio' }, h('p', {}, 'Aún no hay reglas. Cree una nueva o parta de una plantilla.')));
    pintarDetalle(resultados);
    if (enfocar) document.querySelector(enfocar)?.focus();
  }

  function itemRegla(r, n) {
    return h('li', { class: `regla-item ${r.id === seleccionada ? 'sel' : ''} ${r.activa ? '' : 'inactiva'}` },
      h('div', { class: 'regla-cab' },
        h('button', { class: 'regla-nombre', type: 'button', 'aria-pressed': String(r.id === seleccionada), 'data-sel': r.id, onclick: () => { seleccionada = r.id; pintar(`[data-sel="${r.id}"]`); } }, r.nombre),
        h('span', { class: 'regla-cuenta', 'aria-label': `${n} afiliados activan esta regla` }, entero(n))),
      h('div', { class: 'regla-meta' }, insigniaSeveridad(r.severidad), r.ambito ? h('span', {}, `Ejecutiva: ${r.ambito}`) : h('span', {}, 'Toda la cartera'), h('span', {}, r.activa ? 'Activa' : 'Desactivada')),
      h('div', { class: 'fila-botones' },
        h('label', { class: 'interruptor' },
          h('input', { type: 'checkbox', role: 'switch', checked: r.activa, 'data-sw': r.id, 'aria-label': `Activar la regla ${r.nombre}`, onchange: (e) => { r.activa = e.target.checked; aviso_persistencia(guardarReglas()); pintar(`[data-sw="${r.id}"]`); } }),
          'Activa'),
        h('button', { class: 'btn btn-chico', type: 'button', 'data-ed': r.id, 'aria-label': `Editar la regla ${r.nombre}`, onclick: () => editor(structuredClone(r), false) }, 'Editar'),
        h('button', { class: 'btn btn-chico', type: 'button', 'aria-label': `Duplicar la regla ${r.nombre}`, onclick: () => { const c = duplicarRegla(r.id); seleccionada = c.id; decir('ok', `Regla duplicada como «${c.nombre}».`); pintar(`[data-sel="${c.id}"]`); } }, 'Duplicar'),
        h('button', { class: 'btn btn-chico btn-peligro', type: 'button', 'aria-label': `Eliminar la regla ${r.nombre}`, onclick: async () => {
          if (await confirmar('Eliminar regla', `Se eliminará la regla «${r.nombre}» de este navegador. Esta acción no se puede deshacer, salvo que la haya exportado.`, 'Eliminar', true)) { aviso_persistencia(eliminarRegla(r.id)); decir('ok', `Regla «${r.nombre}» eliminada.`); pintar(); }
        } }, 'Eliminar')));
  }

  function pintarDetalle(resultados) {
    const r = almacen.reglas.find((x) => x.id === seleccionada);
    if (!r) { reemplazar(contDetalle, h('div', { class: 'vacio' }, 'Seleccione una regla para ver los afiliados que la activan.')); return; }
    const lista = resultados.get(r.id);
    const porEjec = [...contar(lista, (a) => a.ejecutiva)].map(([k, n]) => ({ etiqueta: k, valor: n, texto: entero(n) })).sort((a, b) => b.valor - a.valor);
    reemplazar(contDetalle, h('section', { class: 'tarjeta', 'aria-labelledby': 'det-titulo' },
      h('h2', { id: 'det-titulo' }, r.nombre),
      r.descripcion ? h('p', { class: 'suave' }, r.descripcion) : null,
      h('p', { class: 'resumen-regla' }, h('strong', {}, 'Condición: '), describirRegla(r)),
      r.activa ? null : aviso('info', 'Esta regla está desactivada: se muestra su resultado, pero no cuenta en los totales.'),
      h('p', {}, h('strong', {}, entero(lista.length)), ` afiliados activan esta regla (${decimal((lista.length / datos.afiliadosLista.length) * 100, 1)} % de la cartera).`),
      lista.length && !r.ambito ? h('div', { style: 'margin-bottom:var(--sp-4)' }, h('h3', { style: 'font-size:var(--fs-md)' }, 'Por ejecutiva'), barrasH(porEjec)) : null,
      h('div', { class: 'fila-botones', style: 'margin-bottom:var(--sp-3)' },
        h('button', { class: 'btn btn-primario', type: 'button', disabled: !lista.length, onclick: () => exportarRegla(r) }, 'Exportar lista a CSV'))));
    contDetalle.firstChild.append(tabla.elemento);
    tabla.actualizar(lista);
  }

  /** Avisa si el guardado local falló (sin almacenamiento disponible). */
  function aviso_persistencia(ok) {
    if (!ok) decir('aviso', 'No fue posible guardar en este navegador (almacenamiento bloqueado o lleno). Los cambios valen solo mientras esta página esté abierta; exporte las reglas a JSON para conservarlas.');
  }

  // ---- Editor de regla -----------------------------------------------------------
  function editor(regla, esNueva) {
    const catalogo = campos();
    const { cuerpo, cerrar } = crearDialogo(esNueva ? 'Nueva regla de alerta' : 'Editar regla de alerta', { ancho: '58rem' });
    const errores = h('div', { role: 'alert' });
    const previa = h('p', { class: 'resumen-regla', 'aria-live': 'polite' });
    const filas = h('div', {});

    const actualizarPrevia = () => {
      const errs = validarRegla(regla);
      previa.textContent = errs.length ? 'Complete la regla para ver cuántos afiliados la activarían.' : `Con los datos actuales, esta regla activaría a ${entero(evaluar(regla).length)} afiliados.`;
    };

    function inputValor(c, campo, op) {
      const etiq = `Valor de la condición`;
      if (!op || op.valor === 0) return h('span', { class: 'conector-vacio' }, 'Sin valor');
      if (op.valor === 2) {
        const par = Array.isArray(c.valor) ? c.valor : ['', ''];
        const num = (i, t) => h('input', { type: 'number', step: 'any', value: par[i], 'aria-label': t, placeholder: t, oninput: (e) => { const p = Array.isArray(c.valor) ? [...c.valor] : ['', '']; p[i] = e.target.value === '' ? '' : Number(e.target.value); c.valor = p; actualizarPrevia(); } });
        return h('div', { style: 'display:grid;grid-template-columns:1fr 1fr;gap:var(--sp-1)' }, num(0, 'Mínimo'), num(1, 'Máximo'));
      }
      if (campo.tipo === 'num') {
        return h('input', { type: 'number', step: 'any', value: c.valor ?? '', 'aria-label': etiq, oninput: (e) => { c.valor = e.target.value === '' ? '' : Number(e.target.value); actualizarPrevia(); } });
      }
      if (op.valor === 'multi') {
        const marcados = Array.isArray(c.valor) ? c.valor : [];
        return h('div', {}, h('select', { multiple: true, 'aria-label': `${etiq} (puede elegir varias opciones)`, onchange: (e) => { c.valor = [...e.target.selectedOptions].map((o) => o.value); actualizarPrevia(); } },
          campo.opciones.map((o) => h('option', { value: o, selected: marcados.includes(o) }, o))), h('span', { class: 'ayuda' }, 'Ctrl o Mayús para varias.'));
      }
      return h('select', { 'aria-label': etiq, onchange: (e) => { c.valor = e.target.value; actualizarPrevia(); } },
        [h('option', { value: '' }, 'Elija...'), ...campo.opciones.map((o) => h('option', { value: o, selected: c.valor === o }, o))]);
    }

    function pintarFilas() {
      reemplazar(filas, regla.condiciones.map((c, i) => {
        const campo = catalogo.find((x) => x.id === c.campo) || catalogo[0];
        const op = OPERADORES[campo.tipo].find((o) => o.id === c.op);
        return h('div', { class: 'cond-fila', role: 'group', 'aria-label': `Condición ${i + 1}` },
          i === 0 ? h('span', { class: 'conector-vacio' }, 'Cuando')
            : h('select', { 'aria-label': `Conector de la condición ${i + 1}`, onchange: (e) => { c.conector = e.target.value; actualizarPrevia(); } },
              ['Y', 'O'].map((v) => h('option', { value: v, selected: (c.conector || 'Y') === v }, v))),
          h('select', { 'aria-label': `Campo de la condición ${i + 1}`, onchange: (e) => { c.campo = e.target.value; const nuevo = catalogo.find((x) => x.id === c.campo); c.op = OPERADORES[nuevo.tipo][0].id; c.valor = nuevo.tipo === 'enum' ? '' : (nuevo.tipo === 'num' ? '' : ''); pintarFilas(); actualizarPrevia(); } },
            catalogo.map((x) => h('option', { value: x.id, selected: x.id === campo.id }, x.etiqueta))),
          h('select', { 'aria-label': `Operador de la condición ${i + 1}`, onchange: (e) => { c.op = e.target.value; c.valor = c.op === 'entre' ? ['', ''] : (['uno', 'ninguno'].includes(c.op) ? [] : (campo.tipo === 'enum' ? '' : '')); pintarFilas(); actualizarPrevia(); } },
            OPERADORES[campo.tipo].map((o) => h('option', { value: o.id, selected: o.id === c.op }, o.etiqueta))),
          inputValor(c, campo, op),
          h('button', { class: 'btn btn-chico btn-peligro', type: 'button', disabled: regla.condiciones.length === 1, 'aria-label': `Quitar la condición ${i + 1}`, onclick: () => { regla.condiciones.splice(i, 1); pintarFilas(); actualizarPrevia(); } }, 'Quitar'));
      }));
    }

    const nombre = h('input', { id: 'r-nombre', type: 'text', value: regla.nombre, maxlength: 120, required: true, oninput: (e) => { regla.nombre = e.target.value; } });
    const desc = h('textarea', { id: 'r-desc', maxlength: 500, oninput: (e) => { regla.descripcion = e.target.value; } }, regla.descripcion);
    cuerpo.append(
      h('form', { novalidate: true, onsubmit: (e) => {
        e.preventDefault();
        const errs = validarRegla(regla);
        if (errs.length) { reemplazar(errores, aviso('error', h('ul', { style: 'margin:0;padding-left:1.1rem' }, errs.map((t) => h('li', {}, t))))); return; }
        aviso_persistencia(guardarRegla({ ...regla, nombre: regla.nombre.trim() }));
        seleccionada = regla.id; cerrar();
        decir('ok', `Regla «${regla.nombre.trim()}» guardada.`); pintar();
      } },
      h('div', { class: 'campo', style: 'margin-bottom:var(--sp-3)' }, h('label', { for: 'r-nombre' }, 'Nombre de la regla'), nombre),
      h('div', { class: 'campo', style: 'margin-bottom:var(--sp-3)' }, h('label', { for: 'r-desc' }, 'Descripción (opcional)'), desc),
      h('div', { class: 'rejilla c2' },
        campoSelect({ id: 'r-sev', etiqueta: 'Severidad', todas: null, opciones: SEVERIDADES.map((s) => ({ valor: s.id, texto: s.etiqueta })), valor: regla.severidad, onchange: (e) => { regla.severidad = e.target.value; } }),
        campoSelect({ id: 'r-ambito', etiqueta: 'Ámbito (opcional)', todas: 'Toda la cartera', opciones: datos.nombresEjecutivas, valor: regla.ambito || '', onchange: (e) => { regla.ambito = e.target.value || null; actualizarPrevia(); } })),
      h('p', { class: 'ayuda', style: 'margin-top:-0.5rem' }, 'El ámbito limita la regla a la cartera de una ejecutiva.'),
      h('label', { class: 'interruptor', style: 'margin-bottom:var(--sp-3)' }, h('input', { type: 'checkbox', role: 'switch', checked: regla.activa, onchange: (e) => { regla.activa = e.target.checked; } }), 'Regla activa'),
      h('fieldset', { style: 'border:1px solid var(--borde);border-radius:var(--radio-sm);padding:var(--sp-3) var(--sp-4);margin:0 0 var(--sp-3)' },
        h('legend', { style: 'font-weight:700;padding:0 var(--sp-2)' }, 'Condiciones'),
        h('p', { class: 'ayuda', style: 'margin-top:0' }, 'Una a una se combinan con Y u O. La Y se evalúa antes que la O: «A Y B O C» significa «(A y B) o C». Si un afiliado no tiene dato en un campo numérico, esa comparación no se cumple.'),
        filas,
        h('button', { class: 'btn btn-chico', type: 'button', onclick: () => { regla.condiciones.push({ conector: 'Y', campo: 'banda', op: 'es', valor: '' }); pintarFilas(); actualizarPrevia(); } }, 'Agregar condición')),
      previa, errores,
      h('div', { class: 'dialogo-pie' },
        h('button', { class: 'btn', type: 'button', onclick: cerrar }, 'Cancelar'),
        h('button', { class: 'btn btn-primario', type: 'submit' }, 'Guardar regla'))));
    pintarFilas(); actualizarPrevia(); nombre.focus();
  }

  // ---- Importar ------------------------------------------------------------------
  const archivo = h('input', { type: 'file', accept: 'application/json,.json', class: 'solo-lectores', tabindex: '-1', 'aria-hidden': 'true', onchange: async (e) => {
    const f = e.target.files[0];
    e.target.value = '';
    if (!f) return;
    if (f.size > 1_000_000) { decir('error', 'El archivo supera 1 MB y no parece un archivo de reglas.'); return; }
    try {
      const { importadas, descartadas } = importarReglasJson(await f.text());
      decir(importadas ? 'ok' : 'aviso', `Se importaron ${importadas} reglas${descartadas ? ` y se descartaron ${descartadas} por no ser válidas` : ''}.`);
      pintar();
    } catch (err) { decir('error', err.message); }
  } });

  const plantillas = h('div', { class: 'plantillas' }, PLANTILLAS.map((p) => h('div', { class: 'plantilla' },
    h('strong', {}, p.nombre), insigniaSeveridad(p.severidad), h('p', {}, p.descripcion),
    h('button', { class: 'btn btn-chico', type: 'button', 'aria-label': `Usar la plantilla ${p.nombre}`, onclick: () => editor(reglaDesdePlantilla(p), true) }, 'Usar plantilla'))));

  const raiz = h('div', {},
    cabecera('Alertas', 'Defina reglas sobre los campos de los afiliados, vea quiénes las activan y exporte las listas para el trabajo comercial.', { icono: 'alertas' }),
    aviso('info', h('strong', {}, 'Las reglas viven en este navegador. '), 'Este tablero no tiene servidor ni base de datos: las reglas se guardan en el almacenamiento local de este navegador y de este equipo. No se comparten con otras personas ni se sincronizan entre dispositivos, y se pierden si se borran los datos del sitio. Use «Exportar reglas» para respaldarlas o llevarlas a otro navegador, e «Importar reglas» para recuperarlas.'),
    almacen.persistente ? null : aviso('aviso', 'El almacenamiento local no está disponible en este navegador (por ejemplo, navegación privada o bloqueo de datos del sitio). Las reglas funcionan, pero se perderán al cerrar o recargar la página.'),
    almacen.ultimoError ? aviso('aviso', almacen.ultimoError) : null,
    contKpi,
    h('div', { class: 'fila-botones', style: 'margin-bottom:var(--sp-4)' },
      h('button', { class: 'btn btn-primario', type: 'button', onclick: () => editor(reglaDesdePlantilla(null), true) }, 'Nueva regla'),
      h('button', { class: 'btn', type: 'button', onclick: exportarTodas }, 'Exportar alertas activas a CSV'),
      h('button', { class: 'btn', type: 'button', onclick: () => { descargarTexto('dactho360-reglas.json', exportarReglasJson(), 'application/json'); decir('ok', 'Reglas exportadas a dactho360-reglas.json.'); } }, 'Exportar reglas (JSON)'),
      h('button', { class: 'btn', type: 'button', onclick: () => archivo.click() }, 'Importar reglas (JSON)'), archivo),
    mensaje,
    h('div', { class: 'rejilla c2' }, tReglas.elemento, tBandas.elemento),
    h('div', { class: 'alertas-diseno' }, h('div', {}, h('h2', { class: 'titulo-seccion' }, 'Reglas'), contLista), contDetalle),
    h('section', { class: 'seccion', style: 'margin-top:var(--sp-6)', 'aria-labelledby': 'h-plantillas' },
      h('h2', { id: 'h-plantillas' }, 'Plantillas'),
      h('p', { class: 'suave' }, 'Punto de partida para reglas habituales. Al usarlas se abre el editor para que pueda ajustarlas, por ejemplo limitarlas a una ejecutiva.'), plantillas));
  pintar();
  return raiz;
}
