/**
 * El servidor no guarda ranking, estrellas, notificaciones ni planes.
 * Estos datos solo ilustran la interfaz y deben verse etiquetados como demostración.
 */

export const RANKING_DEMO = [
  { id: 'demo-1', nombre: 'Ana Ríos', puntos: 128, estrellas: 5 },
  { id: 'demo-2', nombre: 'Luis Cárdenas', puntos: 96, estrellas: 4 },
  { id: 'demo-3', nombre: 'Mateo Gil', puntos: 74, estrellas: 4 },
  { id: 'demo-4', nombre: 'Sofía Pardo', puntos: 51, estrellas: 3 },
]

export const NOTIFICACIONES_DEMO = [
  { id: 'n1', texto: 'Alguien votó tu pregunta sobre normalización.', cuando: 'Hace 12 min' },
  { id: 'n2', texto: 'Camila respondió tu pregunta de rutas en Flask.', cuando: 'Hace 1 h' },
  { id: 'n3', texto: 'Hay un comentario nuevo en tu respuesta.', cuando: 'Hace 3 h' },
  { id: 'n4', texto: 'Sumaste una estrella por votos positivos.', cuando: 'Ayer' },
  { id: 'n5', texto: 'Subiste al puesto 4 del ranking de participación.', cuando: 'Ayer' },
]
