/**
 * Cliente HTTP simple con fetch.
 * servicio: 'usuarios' | 'foro' | 'interacciones'
 * ruta: camino del backend, por ejemplo '/auth/login'
 */

export const REVISION_API = 'comunidades-multimedia-1'

const prefijos = {
  usuarios: '/api/usuarios',
  foro: '/api/foro',
  interacciones: '/api/interacciones',
}

export async function apiFetch(servicio, ruta, opciones = {}) {
  const prefijo = prefijos[servicio]
  if (!prefijo) {
    throw new Error('Servicio desconocido')
  }

  // Asegura una sola barra entre prefijo y ruta.
  const camino = ruta.startsWith('/') ? ruta : `/${ruta}`
  const url = `${prefijo}${camino}`

  const headers = {
    'Content-Type': 'application/json',
    ...(opciones.headers || {}),
  }

  const token = localStorage.getItem('token')
  if (token) {
    headers.Authorization = `Bearer ${token}`
  }

  let respuesta
  try {
    respuesta = await fetch(url, { ...opciones, headers })
  } catch (causa) {
    if (causa.name === 'AbortError') throw causa
    const error = new Error(`No se pudo conectar con el servicio ${servicio}. Comprueba que esté iniciado.`)
    error.cause = causa
    throw error
  }

  // El backend envía JSON con { error: '...' } cuando algo falla.
  let datos = null, jsonValido = true
  try {
    datos = await respuesta.json()
  } catch {
    jsonValido = false
  }

  // Nunca entregar datos privados a una sesión distinta de la que inició la petición.
  if (localStorage.getItem('token') !== token) {
    const error = new Error('La sesión cambió durante la petición')
    error.name = 'AbortError'
    throw error
  }

  // Un 401 con token guardado es sesión vencida. No redirigimos: la
  // pantalla pública sigue visible y la vista pide iniciar sesión.
  if (respuesta.status === 401 && token && localStorage.getItem('token') === token) {
    localStorage.removeItem('token')
    localStorage.removeItem('usuario')
    window.dispatchEvent(new Event('sesion-expirada'))
  }

  if (!respuesta.ok) {
    const mensajes = {400:'Parámetros inválidos',401:'Inicia sesión nuevamente',403:'No tienes permisos',404:'Ruta o recurso no encontrado',405:'Método HTTP no permitido',422:'Datos no válidos',500:'Error interno del servidor',502:'Servicio no disponible',503:'Servicio temporalmente no disponible',504:'El servicio no respondió a tiempo'}
    const revision = respuesta.headers?.get?.('X-Foro-Revision')
    const mensaje = typeof datos?.error === 'string' ? datos.error : (mensajes[respuesta.status] || 'Error en la petición')
    const detalle = typeof datos?.detalle === 'string' ? ` — ${datos.detalle}` : ''
    const rutaNueva = servicio === 'foro' && (/\borden=para_ti\b|\bvista=historial\b/.test(ruta) || /\/preguntas\/(historial|\d+\/visita)/.test(ruta)) || servicio === 'usuarios' && ruta.startsWith('/usuarios/perfil/votos')
    const desactualizado = rutaNueva && [400,404,405,500].includes(respuesta.status) && revision !== REVISION_API
    const error = new Error(`${mensaje}${detalle} (HTTP ${respuesta.status})${desactualizado ? `. Comprueba que el servicio ${servicio} esté actualizado y reiniciado.` : ''}`)
    error.status = respuesta.status
    error.revision = revision
    throw error
  }

  if (!jsonValido) {
    const error = new Error(`Respuesta no válida del servicio ${servicio}: se esperaba JSON. Revisa el servidor y el proxy.`)
    error.status = respuesta.status
    throw error
  }
  return datos
}
