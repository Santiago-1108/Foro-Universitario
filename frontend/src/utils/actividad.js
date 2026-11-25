// Defensa adicional frente a resultados de una sección distinta. El servidor filtra antes de paginar.
export function actividadDeTipo(items, tipo) {
  return tipo === 'general' ? items : items.filter(item => item.tipo === tipo)
}
