/** Vista 7: Acerca de y metodología. */
import { h, entero, decimal, fecha, fechaLarga } from '../util.js';
import { datos } from '../datos.js';
import { cabecera, tarjeta, aviso, tablaPaginada } from '../componentes.js';
import { grafico, paleta, modeloBarras, modeloDona } from '../charts.js';
import { tarjetaGrafico } from '../widgets.js';

const SEVERIDAD = { alta: 's-alta', media: 's-media', baja: 's-baja' };
const NOMBRE_SENAL = {
  sin_asistencia_90d: 'Sin asistencia reciente', sin_asistencia_anio: 'Sin asistencia en el año', menos_asistencias: 'Pocas asistencias',
  menos_personas: 'Pocas personas distintas', menor_antiguedad: 'Menor antigüedad', nivel_conectar: 'Nivel Conectar',
};

export function vistaMetodologia() {
  const M = datos.meta, S = M.score, V = S.validacion, P = S.pesos;
  const terciles = Object.entries(V.tasa_salida_por_tercil);

  const tablaAvisos = tablaPaginada({ etiqueta: 'Avisos de calidad de datos', tamano: 30, orden: { clave: 'sev', dir: 'asc' }, columnas: [
    { clave: 'sev', titulo: 'Severidad', valor: (a) => ({ alta: 0, media: 1, baja: 2 })[a.severidad], render: (a) => h('span', { class: `insignia ${SEVERIDAD[a.severidad]}` }, { alta: '◆ Alta', media: '▲ Media', baja: '● Baja' }[a.severidad]) },
    { clave: 'fuente', titulo: 'Fuente', valor: (a) => a.fuente },
    { clave: 'desc', titulo: 'Aviso', valor: (a) => a.descripcion },
    { clave: 'cant', titulo: 'Cantidad', valor: (a) => a.cantidad, render: (a) => (a.codigo.startsWith('cruce_') ? `${decimal(a.cantidad, 1)} %` : entero(a.cantidad)), num: true },
  ] });
  tablaAvisos.actualizar(M.avisos_calidad);

  const lista = (items) => h('ul', {}, items.map((t) => h('li', {}, t)));
  const ultimo = fechaLarga(datos.ultimoEvento);
  const tTer = tarjetaGrafico({ titulo: 'Tasa de salida por tercil de riesgo', subtitulo: 'Porcentaje de empresas que salieron en cada tercil', icono: 'barras', id: 'm-ter' });
  grafico(tTer.cuerpo, { alto: 250 }).poner(() => { const P = paleta(); return modeloBarras({ etiquetas: terciles.map(([k, v]) => `${k} (${v.n})`), series: [{ nombre: 'Tasa de salida', datos: terciles.map(([, v]) => v.tasa_pct), colores: [P.ok, P.aviso, P.riesgo], patrones: [0, 1, 4] }], formato: (v) => `${decimal(v, 1)} %`, ejeCat: 'Tercil', leyenda: false, max: 20 }); });
  tTer.cuerpo.append(h('p', { class: 'nota' }, 'Pocos casos de salida: las diferencias entre terciles medio y bajo no son concluyentes.'));
  const tAuc = tarjetaGrafico({ titulo: 'AUC por señal (0,5 es azar)', subtitulo: 'Capacidad de cada señal para separar a quienes salieron', icono: 'dispersion', id: 'm-auc' });
  const senales = Object.entries(V.auc_por_senal);
  grafico(tAuc.cuerpo, { alto: 250 }).poner(() => modeloBarras({ etiquetas: senales.map(([k]) => NOMBRE_SENAL[k] || k), series: [{ nombre: 'AUC', datos: senales.map(([, v]) => v) }], horizontal: true, formato: (v) => decimal(v, 2), minValor: 0.4, max: 0.9, ejeCat: 'Señal', leyenda: false }));
  tAuc.cuerpo.append(h('p', { class: 'nota' }, `La participación es la señal más informativa: el ${decimal(V.pct_con_asistencia_salieron, 0)} % de quienes salieron tenía alguna asistencia, frente al ${decimal(V.pct_con_asistencia_vigentes, 0)} % de los vigentes. El nivel Conectar no discrimina.`));
  const tCruce = tarjetaGrafico({ titulo: 'Cobertura de la información', subtitulo: 'Afiliados vigentes según las fuentes con registros', icono: 'dona', id: 'm-cruce' });
  const cr = M.cruce;
  grafico(tCruce.cuerpo, { alto: 250 }).poner(() => { const P = paleta(); return modeloDona({ etiquetas: ['Con asistencia o encuesta', 'Sin ninguna'], valores: [cr.con_asistencia_o_encuesta, cr.sin_ninguna], colores: [P.cat[0], P.otros], patrones: [0, 2], nombre: 'Afiliados', ejeCat: 'Cobertura', centro: { valor: `${decimal(cr.pct_con_alguna, 0)} %`, texto: 'con datos' }, posicion: 'bottom' }); });
  return h('div', { class: 'prosa' },
    cabecera('Acerca de y metodología', 'Cómo se construye el tablero, cómo se calcula el score y qué tan lejos puede llevar la interpretación.', { icono: 'metodologia' }),
    h('div', { class: 'rejilla c3' },
      tarjeta('Corte de datos', h('p', {}, h('strong', {}, fecha(M.fecha_corte)), ` · pipeline v${M.version_pipeline}, pesos v${M.version_pesos}`), h('p', { class: 'nota' }, `Generado el ${fecha(M.generado_en.slice(0, 10))}. Los archivos se leen como datos y no se ejecuta su contenido.`)),
      tarjeta('Fuentes', lista([`CRM: ${entero(M.fuentes.crm_filas)} filas, ${entero(M.fuentes.crm_empresas_unicas)} empresas`, `Asistencia: ${entero(M.fuentes.asistencias_validas)} válidas de ${entero(M.fuentes.registros_asistencia)} registros en ${M.fuentes.eventos} eventos`, `Encuestas: ${entero(M.fuentes.respuestas_encuesta)} respuestas`])),
      tarjeta('Privacidad', h('p', {}, 'Los datos están anonimizados: solo códigos de empresa (EMP-xxxx) y nombres genéricos de ejecutivas. No se intenta reidentificar a nadie ni se usan datos de otras fuentes.'))),

    h('section', { class: 'seccion' }, h('h2', {}, 'Cómo se calcula el score'),
      h('p', {}, `Cada afiliado vigente suma puntos de riesgo por señales transparentes. La suma se divide entre el máximo posible (${S.maximo_puntos} puntos con los pesos actuales) para quedar entre 0 y 100. La salud es 100 menos el riesgo. Cada afiliado conserva la lista de factores con sus puntos y una acción sugerida derivada del factor principal.`),
      h('div', { class: 'rejilla c2' },
        tarjeta('Bandas', h('ul', {}, [
          h('li', {}, h('strong', {}, 'Saludable: '), `riesgo menor a ${S.umbrales.umbral_atencion}`),
          h('li', {}, h('strong', {}, 'Atención: '), `riesgo desde ${S.umbrales.umbral_atencion} y menor a ${S.umbrales.umbral_riesgo_alto}`),
          h('li', {}, h('strong', {}, 'Riesgo alto: '), `riesgo desde ${S.umbrales.umbral_riesgo_alto}`)]),
        h('p', { class: 'nota' }, 'Los umbrales se fijaron para que la lista de riesgo alto sea atendible en una semana; no provienen de un ajuste estadístico y se pueden cambiar en config/pesos_score.json.')),
        tarjeta('Puntos por grupo de señales',
          h('ul', {}, [
            h('li', {}, `Vencimiento: hasta ${P.vencimiento.vencida} puntos (vencida ${P.vencimiento.vencida}, hasta 30 días ${P.vencimiento.hasta_30}, hasta 60 ${P.vencimiento.hasta_60}, hasta 90 ${P.vencimiento.hasta_90}, hasta 180 ${P.vencimiento.hasta_180}, sin fecha ${P.vencimiento.sin_fecha})`),
            h('li', {}, `Participación: sin asistencia reciente ${P.participacion.sin_asistencia_90d}, sin asistencia en el año ${P.participacion.sin_asistencia_anio}, una sola asistencia ${P.participacion.una_sola_asistencia}, un solo contacto ${P.participacion.contacto_unico}`),
            h('li', {}, `Satisfacción y NPS: promedio bajo ${P.satisfaccion.promedio_bajo}, promedio medio ${P.satisfaccion.promedio_medio}, detractor ${P.satisfaccion.detractor}`),
            h('li', {}, `Antigüedad: primer año ${P.antiguedad.primer_anio}, segundo a tercero ${P.antiguedad.segundo_a_tercero}`),
            h('li', {}, `Nivel: Conectar ${P.nivel.Conectar}, Crecer ${P.nivel.Crecer}, Liderar ${P.nivel.Liderar}`),
            h('li', {}, `Ejecutiva sin asignar ${P.ejecutiva.sin_asignar}; sin comunidad ${P.comunidad.sin_comunidad}; renovación reciente resta ${P.renovacion_reciente.descuento}`)])),
      ),
      h('p', {}, `La falta de datos de satisfacción no suma puntos, para no penalizar a quien simplemente no fue encuestado. Los afiliados con menos de 90 días ven reducidas a la mitad las señales de ausencia de participación. La ventana reciente termina en el último evento del libro (${ultimo}) y no en la fecha de corte.`)),

    h('section', { class: 'seccion' }, h('h2', {}, 'Validación: una asociación, no una predicción probada'),
      aviso('aviso', h('strong', {}, `AUC de ${decimal(V.auc, 2)} `), `(intervalo de 95 %: ${decimal(V.auc_ic95[0], 2)} a ${decimal(V.auc_ic95[1], 2)}). `, 'Indica que el score se asocia con la salida histórica en esta muestra. No demuestra capacidad predictiva ni debe usarse para automatizar decisiones sobre afiliados.'),
      h('p', {}, `Se aplicó el score, sin las señales de vencimiento, ejecutiva y comunidad, a ${V.n_salieron} empresas que salieron entre abril y noviembre de 2026 y a los ${V.n_vigentes} vigentes. ${V.lectura}`),
      h('div', { class: 'rejilla c3' }, tTer.elemento, tAuc.elemento, tCruce.elemento),
      h('h3', {}, 'Limitaciones de la validación'), lista(V.limitaciones)),

    h('section', { class: 'seccion' }, h('h2', {}, 'Supuestos'), lista(M.supuestos)),
    h('section', { class: 'seccion' }, h('h2', {}, 'Limitaciones del tablero'),
      lista([
        `Solo se mide la asistencia desde enero de 2026 y hasta el ${ultimo}; la participación reciente puede estar subestimada.`,
        `El NPS post-evento (${datos.resumen.nps_post_evento.n} respuestas) no es el NPS de la asociación; la encuesta de 90 días no tiene respuestas.`,
        `Solo el ${decimal(M.cruce.pct_con_encuesta, 1)} % de los afiliados tiene alguna respuesta de encuesta, por lo que la satisfacción por afiliado es parcial.`,
        'La hoja consolidada de asistencia del origen está incompleta; el pipeline recalcula la asistencia desde las hojas por evento.',
        'Las reglas de alerta se evalúan en este navegador sobre los datos del corte; no se actualizan solas ni se comparten entre usuarios.'])),
    h('section', { class: 'seccion' }, h('h2', {}, 'Avisos de calidad de datos'), tablaAvisos.elemento));
}
