/**
 * Componentes de interfaz reutilizables: KPI, avisos, diálogos, confirmación
 * y tabla con ordenamiento y paginación.
 */
import { h, entero, reemplazar, fechaLarga } from './util.js';
import { datos } from './datos.js';
import { icono } from './iconos.js';
import { sparkline, animarNumero, esqueletoVista } from './widgets.js';

/** Último valor mostrado por indicador (para animar el cambio al filtrar). */
const valoresPrevios = new Map();

/**
 * Tarjeta de indicador (KPI) con ícono, variación, sparkline y medidor opcionales.
 * @param {string} etiqueta
 * @param {string} valor    Texto del valor principal.
 * @param {string} [detalle]
 * @param {Object} [o]
 * @param {string} [o.icono]  Nombre de ícono (iconos.js).
 * @param {'ok'|'aviso'|'riesgo'|'info'} [o.tono]
 * @param {{datos:number[], color?:string, descripcion?:string, formato?:Function}} [o.spark]
 * @param {{texto:string, direccion:'sube'|'baja'|'igual', bueno?:boolean|null, titulo?:string}} [o.delta]
 * @param {Node} [o.medidor]  Medidor SVG a la derecha del valor.
 * @param {{id:string, valor:number, formato?:Function}} [o.numero]  Anima el valor desde el anterior.
 * @param {string} [o.enlace]  Hash al que lleva la tarjeta.
 */
export function kpi(etiqueta, valor, detalle, o = {}) {
  const { icono: ico, tono, spark, delta, medidor, numero, enlace } = o;
  const elValor = h('span', { class: 'kpi-valor' }, valor);
  if (numero) {
    const previo = valoresPrevios.get(numero.id) ?? 0;
    valoresPrevios.set(numero.id, numero.valor);
    const fmt = numero.formato || entero;
    animarNumero(elValor, previo, numero.valor, fmt);
  }
  const grafico = spark ? sparkline(spark.datos, { color: spark.color, descripcion: spark.descripcion || `Tendencia de ${etiqueta}`, formato: spark.formato }) : null;
  const cuerpo = [
    h('div', { class: 'kpi-cab' }, ico ? h('span', { class: 'kpi-icono' }, icono(ico)) : null, h('span', { class: 'kpi-etiqueta' }, etiqueta)),
    h('div', { class: 'kpi-cuerpo' },
      h('div', { class: 'kpi-principal' }, elValor,
        delta ? h('span', { class: `kpi-delta ${delta.direccion} ${delta.bueno === true ? 'bueno' : delta.bueno === false ? 'malo' : 'neutro'}`, title: delta.titulo || null }, icono(delta.direccion || 'igual', { clase: 'ico' }), delta.texto) : null),
      medidor ? h('div', { class: 'kpi-medidor' }, medidor) : null),
    detalle ? h('span', { class: 'kpi-detalle' }, detalle) : null,
    grafico ? h('div', { class: 'kpi-spark' }, grafico, spark.pie ? h('span', { class: 'kpi-spark-pie' }, spark.pie) : null) : null,
  ];
  const clase = `tarjeta kpi${tono ? ` tono-${tono}` : ''}${grafico ? ' con-spark' : ''}`;
  return enlace ? h('a', { class: `${clase} kpi-enlace`, href: enlace }, cuerpo) : h('div', { class: clase }, cuerpo);
}

/** Aviso con rol adecuado. tipo: info | aviso | error | ok. */
export function aviso(tipo, ...contenido) {
  const marca = { info: 'Nota', aviso: 'Atención', error: 'Error', ok: 'Listo' }[tipo];
  return h('div', { class: `aviso aviso-${tipo}`, role: tipo === 'error' ? 'alert' : 'note' },
    h('span', {}, `${marca}:`), h('div', {}, ...contenido));
}

/** Tarjeta con título opcional. */
export function tarjeta(titulo, ...contenido) {
  return h('section', { class: 'tarjeta' }, titulo ? h('h2', { class: 'tarjeta-titulo' }, titulo) : null, ...contenido);
}

/**
 * Cabecera de vista: ícono, título (recibe el foco al navegar), descripción y
 * la fecha de corte leída de data/meta.json.
 */
export function cabecera(titulo, descripcion, { icono: ico = 'resumen', acciones } = {}) {
  return h('header', { class: 'cabecera-vista' },
    h('div', { class: 'cabecera-texto' },
      h('p', { class: 'cabecera-ojo' }, icono(ico), h('span', {}, 'DACTHO 360 · Gestión de afiliados')),
      h('h1', { id: 'titulo-vista', tabindex: '-1' }, titulo),
      descripcion ? h('p', { class: 'cabecera-desc' }, descripcion) : null),
    h('div', { class: 'cabecera-lado' },
      datos.fechaCorte ? h('span', { class: 'pildora-corte', title: 'Fecha de corte de los datos (data/meta.json)' }, icono('calendario'), `Corte: ${fechaLarga(datos.fechaCorte)}`) : null,
      acciones || null));
}

/** Estado de carga accesible: esqueleto de la vista con anuncio para lectores de pantalla. */
export function cargando() { return esqueletoVista(); }

/** Estado de error con botón para reintentar. */
export function errorCarga(mensaje, reintentar) {
  return h('div', { class: 'estado', role: 'alert' },
    h('h2', {}, 'No fue posible cargar la información'),
    h('p', { class: 'suave' }, mensaje),
    reintentar ? h('button', { class: 'btn btn-primario', type: 'button', onclick: reintentar }, 'Reintentar') : null);
}

/**
 * Crea un diálogo modal nativo (<dialog>): trampa de foco, Escape y retorno
 * de foco al elemento que lo abrió los gestiona el navegador.
 * @returns {{dialogo: HTMLDialogElement, cuerpo: HTMLElement, cerrar: Function}}
 */
export function crearDialogo(titulo, { ancho } = {}) {
  const lanzador = document.activeElement;
  const idTitulo = `dlg-${Math.random().toString(36).slice(2, 8)}`;
  const cuerpo = h('div', { class: 'dialogo-cuerpo' });
  const cerrar = () => dialogo.close();
  const dialogo = h('dialog', { 'aria-labelledby': idTitulo, style: ancho ? `width:min(${ancho},calc(100vw - 1.5rem))` : null },
    h('div', { class: 'dialogo-cab' },
      h('h2', { id: idTitulo }, titulo),
      h('button', { class: 'btn btn-chico', type: 'button', 'aria-label': 'Cerrar', onclick: cerrar }, 'Cerrar')),
    cuerpo);
  dialogo.addEventListener('close', () => { dialogo.remove(); if (lanzador && lanzador.isConnected) lanzador.focus(); });
  dialogo.addEventListener('click', (e) => { if (e.target === dialogo) cerrar(); });
  document.body.append(dialogo);
  dialogo.showModal();
  return { dialogo, cuerpo, cerrar };
}

/** Confirmación modal. Devuelve una promesa con true o false. */
export function confirmar(titulo, mensaje, textoAceptar = 'Aceptar', peligro = false) {
  return new Promise((resolver) => {
    const { dialogo, cuerpo, cerrar } = crearDialogo(titulo, { ancho: '28rem' });
    let resultado = false;
    dialogo.addEventListener('close', () => resolver(resultado));
    cuerpo.append(h('p', {}, mensaje),
      h('div', { class: 'dialogo-pie' },
        h('button', { class: 'btn', type: 'button', onclick: cerrar }, 'Cancelar'),
        h('button', { class: `btn ${peligro ? 'btn-peligro-solido' : 'btn-primario'}`, type: 'button', onclick: () => { resultado = true; cerrar(); } }, textoAceptar)));
  });
}

/**
 * Tabla con ordenamiento por columna y paginación.
 * @param {Object} cfg
 * @param {string} cfg.etiqueta  Texto accesible de la tabla (caption oculto).
 * @param {Array<{clave:string,titulo:string,valor:(f:any)=>any,render?:(f:any)=>Node|string,num?:boolean}>} cfg.columnas
 * @param {number} [cfg.tamano=20]  Filas por página.
 * @param {{clave:string,dir:'asc'|'desc'}} [cfg.orden]
 * @param {string} [cfg.vacio]  Mensaje cuando no hay filas.
 * @returns {{elemento: HTMLElement, actualizar: (filas:any[], reiniciarPagina?:boolean)=>void}}
 */
export function tablaPaginada({ etiqueta, columnas, tamano = 20, orden = null, vacio = 'No hay registros que coincidan con los filtros.' }) {
  let filas = [], pagina = 0, ord = orden;
  const caption = h('caption', { class: 'solo-lectores' }, etiqueta);
  const thead = h('thead'), tbody = h('tbody');
  const info = h('span', { 'aria-live': 'polite' });
  const ant = h('button', { class: 'btn btn-chico', type: 'button', onclick: () => { pagina -= 1; pintar(); } }, 'Anterior');
  const sig = h('button', { class: 'btn btn-chico', type: 'button', onclick: () => { pagina += 1; pintar(); } }, 'Siguiente');
  const pos = h('span', {});
  const tabla = h('table', {}, caption, thead, tbody);
  const elemento = h('div', {}, h('div', { class: 'tabla-envoltura' }, tabla), h('div', { class: 'paginacion' }, info, h('div', { class: 'acciones' }, ant, pos, sig)));

  /** Compara con valores nulos siempre al final. */
  function comparar(a, b, col) {
    const va = col.valor(a), vb = col.valor(b);
    if (va === null || va === undefined) return (vb === null || vb === undefined) ? 0 : 1;
    if (vb === null || vb === undefined) return -1;
    const r = typeof va === 'number' && typeof vb === 'number' ? va - vb : String(va).localeCompare(String(vb), 'es');
    return ord.dir === 'asc' ? r : -r;
  }

  function pintarCabecera() {
    reemplazar(thead, h('tr', {}, columnas.map((c) => {
      const activa = ord && ord.clave === c.clave;
      const th = h('th', { scope: 'col', class: c.num ? 'num' : '', 'aria-sort': activa ? (ord.dir === 'asc' ? 'ascending' : 'descending') : 'none' },
        h('button', { class: 'th-orden', type: 'button', onclick: () => {
          ord = { clave: c.clave, dir: activa && ord.dir === 'asc' ? 'desc' : 'asc' };
          pagina = 0; pintar(); },
        'aria-label': `Ordenar por ${c.titulo}` }, c.titulo, h('span', { class: 'flecha', 'aria-hidden': 'true' }, activa ? (ord.dir === 'asc' ? '▲' : '▼') : '')));
      return th;
    })));
  }

  function pintar() {
    const col = ord && columnas.find((c) => c.clave === ord.clave);
    const ordenadas = col ? [...filas].sort((a, b) => comparar(a, b, col)) : filas;
    const paginas = Math.max(1, Math.ceil(ordenadas.length / tamano));
    pagina = Math.min(Math.max(0, pagina), paginas - 1);
    const visibles = ordenadas.slice(pagina * tamano, (pagina + 1) * tamano);
    pintarCabecera();
    reemplazar(tbody, visibles.length ? visibles.map((f) => h('tr', {}, columnas.map((c) => h('td', { class: c.num ? 'num' : '' }, c.render ? c.render(f) : c.valor(f) ?? '')))) :
      h('tr', {}, h('td', { colspan: columnas.length, class: 'suave' }, vacio)));
    const desde = ordenadas.length ? pagina * tamano + 1 : 0;
    info.textContent = `Mostrando ${entero(desde)} a ${entero(Math.min((pagina + 1) * tamano, ordenadas.length))} de ${entero(ordenadas.length)}`;
    pos.textContent = `Página ${pagina + 1} de ${paginas}`;
    ant.disabled = pagina === 0;
    sig.disabled = pagina >= paginas - 1;
  }

  return { elemento, actualizar(nuevas, reiniciar = true) { filas = nuevas; if (reiniciar) pagina = 0; pintar(); } };
}

/**
 * Campo de selección con etiqueta visible.
 * @param {{id:string, etiqueta:string, opciones:Array<string|{valor:string,texto:string}>, valor?:string, onchange?:Function, todas?:string}} cfg
 */
export function campoSelect({ id, etiqueta, opciones, valor = '', onchange, todas = 'Todas' }) {
  const opts = [...(todas === null ? [] : [{ valor: '', texto: todas }]), ...opciones.map((o) => (typeof o === 'string' ? { valor: o, texto: o } : o))];
  const sel = h('select', { id, onchange }, opts.map((o) => h('option', { value: o.valor, selected: o.valor === valor }, o.texto)));
  return h('div', { class: 'campo' }, h('label', { for: id }, etiqueta), sel);
}
