import { computed, ref } from 'vue'

function leerUsuario() {
  try {
    const datos = JSON.parse(localStorage.getItem('usuario') || 'null')
    return datos && typeof datos === 'object' ? datos : null
  } catch {
    return null
  }
}

export const usuario = ref(localStorage.getItem('token') ? leerUsuario() : null)
export const autenticado = computed(() => Boolean(localStorage.getItem('token') && usuario.value))
export const esAdministrador = computed(() => usuario.value?.rol === 'admin')

export const modalAcceso = ref({
  abierto: false,
  mensaje: '',
})

export function pedirSesion(mensaje) {
  modalAcceso.value = {
    abierto: true,
    mensaje: mensaje || 'Inicia sesión para participar.',
  }
}

export function cerrarModalAcceso() {
  modalAcceso.value = { abierto: false, mensaje: '' }
}

export function exigirSesion(mensaje) {
  if (localStorage.getItem('token') && usuario.value) return true
  pedirSesion(mensaje)
  return false
}

export function guardarSesion(token, datosUsuario) {
  localStorage.setItem('token', token)
  localStorage.setItem('usuario', JSON.stringify(datosUsuario))
  usuario.value = datosUsuario
}

export function cerrarSesionLocal() {
  localStorage.removeItem('token')
  localStorage.removeItem('usuario')
  usuario.value = null
}

export function destinoSeguro(valor) {
  if (typeof valor === 'string' && valor.startsWith('/') && !valor.startsWith('//') && !/[\\\x00-\x20]/.test(valor)) {
    return valor
  }
  return '/'
}

function sincronizarSesion() {
  const token = localStorage.getItem('token')
  usuario.value = token ? leerUsuario() : null
}

window.addEventListener('sesion-expirada', sincronizarSesion)

// Borra o sincroniza la sesión cuando otra pestaña cambia de cuenta.
window.addEventListener('storage', e => { if (e.key === 'token' || e.key === 'usuario' || e.key === null) sincronizarSesion() })
