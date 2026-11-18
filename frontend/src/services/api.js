/**
 * Cliente HTTP simple con fetch.
 * servicio: 'usuarios' | 'foro' | 'interacciones'
 * ruta: camino del backend, por ejemplo '/auth/login'
 */

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

  const respuesta = await fetch(url, { ...opciones, headers })

  // El backend envía JSON con { error: '...' } cuando algo falla.
  let datos = {}
  try {
    datos = await respuesta.json()
  } catch {
    datos = {}
  }

  // Un 401 con token guardado es sesión vencida. No redirigimos: la
  // pantalla pública sigue visible y la vista pide iniciar sesión.
  if (respuesta.status === 401 && token) {
    localStorage.removeItem('token')
    localStorage.removeItem('usuario')
    window.dispatchEvent(new Event('sesion-expirada'))
  }

  if (!respuesta.ok) {
    const error = new Error(datos.error || 'Error en la petición')
    error.status = respuesta.status
    throw error
  }

  return datos
}
