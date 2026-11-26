/**
 * Ficha de afiliado: score, factores explicados, acción sugerida y alertas activas.
 */
import { h, decimal, entero, fecha, textoVencimiento } from './util.js';
import { datos } from './datos.js';
import { crearDialogo } from './componentes.js';
import { insigniaBanda, medidorSalud } from './graficos.js';
import { almacen, cumpleRegla } from './reglas.js';

/** Nombres en español de las categorías de factores del score. */
const CATEGORIAS = {
  vencimiento: 'Vencimiento', sin_asistencia_90d: 'Participación reciente', sin_asistencia_anio: 'Participación anual',
  una_sola_asistencia: 'Participación', contacto_unico: 'Un solo contacto', satisfaccion: 'Satisfacción',
  antiguedad: 'Antigüedad', nivel: 'Nivel', ejecutiva: 'Ejecutiva', comunidad: 'Comunidades',
};

/** Abre la ficha del afiliado indicado. */
export function abrirFicha(id) {
  const a = datos.porId.get(id);
  if (!a) return;
  const umbrales = datos.meta.score.umbrales;
  const { dialogo, cuerpo, cerrar } = crearDialogo(`Afiliado ${a.id}`);
  const dato = (t, v) => [h('dt', {}, t), h('dd', {}, v)];
  const activadas = almacen.reglas.filter((r) => r.activa && cumpleRegla(a, r));
  const totalPuntos = a.factores.reduce((s, f) => s + f.p, 0);

  cuerpo.append(
    h('div', { class: 'ficha-score' },
      h('div', {}, h('div', { class: 'ficha-puntaje' }, decimal(a.salud, 1)), h('div', { class: 'nota' }, 'Salud (de 0 a 100)')),
      h('div', {},
        h('div', { style: 'margin-bottom:var(--sp-2)' }, insigniaBanda(a.banda), ` Riesgo ${decimal(a.riesgo, 1)} de 100`),
        medidorSalud(a.salud, umbrales.umbral_atencion, umbrales.umbral_riesgo_alto),
        h('p', { class: 'nota', style: 'margin-top:var(--sp-2)' }, `Zonas de izquierda a derecha: Riesgo alto, Atención, Saludable. La marca indica la posición de este afiliado. Mayor salud significa menor riesgo.`))),
    h('div', { class: 'accion' }, h('strong', {}, 'Acción sugerida: '), a.accion || 'Sin acción específica; mantener el seguimiento habitual.'),
    h('h3', {}, 'Por qué tiene este puntaje'),
    a.factores.length
      ? h('ul', { class: 'factores' }, a.factores.map((f) => h('li', {},
        h('span', { class: 'puntos', title: 'Puntos de riesgo que suma este factor' }, `+${decimal(f.p, 0)} pts`),
        h('span', {}, h('span', { class: 'factor-cat' }, CATEGORIAS[f.c] || f.c), f.t))))
      : h('p', { class: 'suave' }, 'No tiene factores de riesgo registrados.'),
    h('p', { class: 'nota' }, `Total de puntos de riesgo: ${decimal(totalPuntos, 0)} de un máximo de ${datos.meta.score.maximo_puntos}. El riesgo se obtiene al dividir entre el máximo y llevarlo a escala de 0 a 100.`),
    h('h3', {}, 'Datos del afiliado'),
    h('dl', { class: 'datos' },
      dato('Nivel', a.nivel), dato('Tipo', a.tipo), dato('Sector', a.sector), dato('Tamaño', a.tamano), dato('Ciudad', a.ciudad),
      dato('Ejecutiva', a.ejecutiva), dato('Estado de membresía', a.estado),
      dato('Expiración', `${fecha(a.expira)} (${textoVencimiento(a.dias_venc)})`),
      dato('Afiliación', `${fecha(a.afiliacion)} (${decimal(a.antig_anios, 1)} años)`),
      dato('Comunidades', a.comunidad ? 'Pertenece a una comunidad' : 'Sin comunidad'),
      dato('Renovó en los últimos 2 meses', a.renovo_reciente ? 'Sí' : 'No')),
    h('h3', {}, 'Participación y satisfacción'),
    h('dl', { class: 'datos' },
      dato('Asistencias en 2026', entero(a.asist)), dato('Asistencias en el último trimestre registrado', entero(a.asist_90d)),
      dato('Eventos distintos', entero(a.eventos)), dato('Personas distintas', entero(a.personas)),
      dato('Última asistencia', a.ult_asist ? `${fecha(a.ult_asist)} (hace ${entero(a.dias_ult_asist)} días)` : 'Sin asistencias registradas'),
      dato('Satisfacción promedio', a.sat === null ? 'Sin respuestas' : `${decimal(a.sat, 2)} de 5 (${a.n_resp} respuestas)`),
      dato('Recomendación más baja', a.nps_min === null ? 'Sin dato' : `${a.nps_min} de 10`)),
    h('h3', {}, 'Alertas activas'),
    activadas.length
      ? h('ul', {}, activadas.map((r) => h('li', {}, `${r.nombre} (severidad ${r.severidad})`)))
      : h('p', { class: 'suave' }, 'Este afiliado no activa ninguna regla de alerta activa en este navegador.'),
    h('div', { class: 'dialogo-pie' }, h('button', { class: 'btn btn-primario', type: 'button', onclick: cerrar }, 'Cerrar')));
  dialogo.querySelector('button')?.focus();
}

/** Botón con el código del afiliado que abre su ficha (accesible por teclado). */
export function enlaceFicha(id) {
  return h('button', { class: 'btn-enlace', type: 'button', 'aria-label': `Abrir ficha del afiliado ${id}`, onclick: () => abrirFicha(id) }, id);
}
