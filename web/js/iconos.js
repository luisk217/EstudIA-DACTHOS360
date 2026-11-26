/**
 * Iconografía SVG propia y consistente: cuadrícula de 24 px, trazo de 1,8 px,
 * extremos redondeados y sin relleno. Se dibuja con currentColor, de modo que
 * hereda el color del texto y funciona en tema claro y oscuro.
 */
const NS = 'http://www.w3.org/2000/svg';

/** Trazados por nombre (cada valor es una lista de subtrazados). */
const TRAZOS = {
  resumen: ['M4 4h7v8H4z', 'M13 4h7v5h-7z', 'M13 11h7v9h-7z', 'M4 14h7v6H4z'],
  afiliados: ['M9 11a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7z', 'M2.5 20c0-3.6 2.9-5.5 6.5-5.5s6.5 1.9 6.5 5.5', 'M16 4.4a3.5 3.5 0 0 1 0 6.2', 'M18 14.8c2 .6 3.5 2.2 3.5 5.2'],
  ejecutivas: ['M3.5 8h17v11.5h-17z', 'M8.5 8V5.5h7V8', 'M3.5 13.5h17', 'M10.5 13.5v1.5h3v-1.5'],
  eventos: ['M4 6h16v14H4z', 'M4 10.5h16', 'M8.5 3.5v5', 'M15.5 3.5v5', 'M8 14.5h2.5', 'M13.5 14.5H16', 'M8 17.5h2.5'],
  encuestas: ['M4 5h16v11H10l-5 4v-4H4z', 'M8 9h8', 'M8 12.2h5'],
  alertas: ['M6 17v-5.5a6 6 0 1 1 12 0V17l1.6 2H4.4z', 'M10 21.5h4'],
  metodologia: ['M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z', 'M12 11v5.5', 'M12 7.6v.1'],
  auto: ['M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z', 'M12 3v18', 'M12 7.5a4.5 4.5 0 0 1 0 9'],
  claro: ['M12 16.5a4.5 4.5 0 1 0 0-9 4.5 4.5 0 0 0 0 9z', 'M12 2.5v2.2', 'M12 19.3v2.2', 'M2.5 12h2.2', 'M19.3 12h2.2', 'M5.3 5.3l1.6 1.6', 'M17.1 17.1l1.6 1.6', 'M5.3 18.7l1.6-1.6', 'M17.1 6.9l1.6-1.6'],
  oscuro: ['M20 14.2A8.2 8.2 0 0 1 9.8 4a8.2 8.2 0 1 0 10.2 10.2z'],
  filtro: ['M4 5h16l-6.2 7.3V19l-3.6-1.8v-4.9z'],
  cerrar: ['M6 6l12 12', 'M18 6L6 18'],
  menu: ['M4 7h16', 'M4 12h16', 'M4 17h16'],
  buscar: ['M10.5 17a6.5 6.5 0 1 0 0-13 6.5 6.5 0 0 0 0 13z', 'M15.5 15.5L20 20'],
  descarga: ['M12 4v11', 'M7.5 10.5L12 15l4.5-4.5', 'M5 19.5h14'],
  sube: ['M12 19V6', 'M6.5 11.5L12 6l5.5 5.5'],
  baja: ['M12 5v13', 'M6.5 12.5L12 18l5.5-5.5'],
  igual: ['M5 9h14', 'M5 15h14'],
  chevron: ['M7 10l5 5 5-5'],
  limpiar: ['M5 6.5h14', 'M9.5 6.5V4.5h5v2', 'M7 6.5l.8 13h8.4l.8-13', 'M10 10.5v5.5', 'M14 10.5v5.5'],
  empresa: ['M5 20.5V4.5h9v16', 'M14 9.5h5v11', 'M8 8.5h3', 'M8 12h3', 'M8 15.5h3', 'M3.5 20.5h17'],
  riesgo: ['M12 3l8.5 15.5H3.5z', 'M12 9.5v4.5', 'M12 17v.1'],
  asistencia: ['M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z', 'M8 12.3l2.8 2.8L16.3 9.5'],
  vencimiento: ['M5.5 3.5h13', 'M5.5 20.5h13', 'M7 3.5c0 4.5 5 5 5 8.5s-5 4-5 8.5', 'M17 3.5c0 4.5-5 5-5 8.5s5 4 5 8.5'],
  satisfaccion: ['M12 3.2l2.7 5.6 6.1.8-4.5 4.3 1.1 6.1-5.4-3-5.4 3 1.1-6.1-4.5-4.3 6.1-.8z'],
  nps: ['M3.5 16a8.5 8.5 0 0 1 17 0', 'M12 16l4-5.5', 'M12 16v.1', 'M5 19.5h14'],
  salud: ['M3 12h4l2.2-5 3.6 10 2.2-5H21'],
  personas: ['M12 11.5a3.6 3.6 0 1 0 0-7.2 3.6 3.6 0 0 0 0 7.2z', 'M5 20c0-3.5 3.1-5.5 7-5.5s7 2 7 5.5'],
  calendario: ['M4 6h16v14H4z', 'M4 10.5h16', 'M8.5 3.5v5', 'M15.5 3.5v5'],
  tendencia: ['M3.5 17l5.5-5.5 3.5 3.5 7.5-8', 'M15 7h5.5v5.5'],
  dona: ['M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z', 'M12 15.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7z'],
  barras: ['M5 20V11', 'M10 20V5', 'M15 20v-7', 'M20 20V8'],
  mapa: ['M3.5 3.5h7v7h-7z', 'M13.5 3.5h7v7h-7z', 'M3.5 13.5h7v7h-7z', 'M13.5 13.5h7v7h-7z'],
  dispersion: ['M5 19V4.5', 'M5 19h15', 'M9 14.5v.1', 'M12.5 9v.1', 'M16 13v.1', 'M18 7.5v.1', 'M10 7.5v.1'],
  radar: ['M12 3l8.5 6.2-3.2 10H6.7l-3.2-10z', 'M12 8.5l4.2 3-1.6 5h-5.2l-1.6-5z'],
  enlace: ['M10 14a4 4 0 0 0 5.6 0l3-3a4 4 0 0 0-5.6-5.6l-1 1', 'M14 10a4 4 0 0 0-5.6 0l-3 3a4 4 0 0 0 5.6 5.6l1-1'],
  copiar: ['M8.5 8.5h11v11h-11z', 'M5 15.5V4.5h11'],
  clic: ['M9 3.5v3', 'M4 9h3', 'M5.6 5.6l2.1 2.1', 'M12.5 12l7.5 3-3.3 1.4L15 20z'],
  flecha: ['M5 12h14', 'M13 6l6 6-6 6'],
  info: ['M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z', 'M12 11v5.5', 'M12 7.6v.1'],
  ojo: ['M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z', 'M12 14.8a2.8 2.8 0 1 0 0-5.6 2.8 2.8 0 0 0 0 5.6z'],
  tabla: ['M4 5h16v14H4z', 'M4 10h16', 'M4 14.5h16', 'M10 5v14'],
  check: ['M5 12.5l4.5 4.5L19 7.5'],
  logo: ['M12 21a9 9 0 1 1 9-9', 'M12 16.5a4.5 4.5 0 1 1 4.5-4.5', 'M21 12h-4.5', 'M12 12.2v.1'],
};

/**
 * Devuelve un elemento SVG con el ícono pedido.
 * @param {string} nombre  Clave de TRAZOS.
 * @param {{clase?:string, tam?:number|string}} [opc]
 */
export function icono(nombre, { clase = 'ico', tam } = {}) {
  const svg = document.createElementNS(NS, 'svg');
  svg.setAttribute('viewBox', '0 0 24 24');
  svg.setAttribute('aria-hidden', 'true');
  svg.setAttribute('focusable', 'false');
  svg.setAttribute('class', clase);
  if (tam) { svg.setAttribute('width', tam); svg.setAttribute('height', tam); }
  for (const d of TRAZOS[nombre] || TRAZOS.info) {
    const p = document.createElementNS(NS, 'path');
    p.setAttribute('d', d);
    svg.append(p);
  }
  return svg;
}

export const hayIcono = (nombre) => nombre in TRAZOS;
