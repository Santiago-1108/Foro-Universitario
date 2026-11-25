<script setup>
import { onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { apiFetch } from '../services/api.js'
import {
  autenticado,
  cerrarSesionLocal,
  esAdministrador,
  pedirSesion,
  usuario,
} from '../services/sesion.js'
import IconoForo from './IconoForo.vue'
import AvatarUsuario from './AvatarUsuario.vue'
import { iniciales, formatearFecha } from '../utils/formato.js'

const router = useRouter(), route = useRoute()
const barraRef = ref(null)
let observadorBarra
function medirBarra(){
  if (barraRef.value) document.documentElement.style.setProperty('--alto-barra', `${Math.ceil(barraRef.value.getBoundingClientRect().height)}px`)
}
defineProps({menuAbierto:Boolean})
defineEmits(['alternar-menu'])
const consulta=ref(''), menuUsuario=ref(false), contenedorUsuario=ref(null), botonUsuario=ref(null)
const oscuro=ref(localStorage.getItem('foro-tema')==='oscuro')
function aplicarTema(){document.documentElement.dataset.tema=oscuro.value?'oscuro':'claro';localStorage.setItem('foro-tema',oscuro.value?'oscuro':'claro')}
function buscarGlobal(){if(consulta.value.trim()) router.push({path:'/buscar',query:{q:consulta.value.trim()}})}
function cerrarMenu(){menuUsuario.value=false;botonUsuario.value?.focus()}
watch(()=>route.fullPath,()=>{menuUsuario.value=false;consulta.value=route.path==='/buscar'?String(route.query.q||''):''},{immediate:true})
const contenedorAvisos = ref(null)
const botonAvisos = ref(null)
const panelAbierto = ref(false)
const avisos = ref([])
const pendientes = ref(0)
const siguiente = ref(null)
const cargando = ref(false)
const modificando = ref(false)
const errorAvisos = ref('')
let generacion = 0
let controlador = null
let intervalo = null
const mensajesPendientes = ref(0)
let consultaMensajes = null
async function cargarConteoMensajes() {
  if (!autenticado.value || document.visibilityState !== 'visible') return
  consultaMensajes?.abort()
  const ctrl = new AbortController(); consultaMensajes = ctrl
  const version = generacion, token = localStorage.getItem('token')
  try {
    const datos = await apiFetch('usuarios', '/mensajes?solo_conteo=1', {signal:ctrl.signal})
    if (sesionActual(version) && consultaMensajes === ctrl && token === localStorage.getItem('token')) mensajesPendientes.value=datos.pendientes
  } catch(error) { if(consultaMensajes===ctrl && sesionActual(version) && error.name!=='AbortError') mensajesPendientes.value=0 }
  finally { if(consultaMensajes===ctrl) consultaMensajes=null }
}

function sesionActual(version) {
  return version === generacion && autenticado.value
}

async function cargarAvisos({ completa = panelAbierto.value, mas = false, forzar = false } = {}) {
  if (!autenticado.value || modificando.value || (mas && !siguiente.value)) return
  if (cargando.value && !forzar) return
  controlador?.abort()
  const actual = new AbortController()
  controlador = actual
  const version = generacion
  cargando.value = true
  errorAvisos.value = ''
  try {
    const ruta = !completa ? '/notificaciones?solo_conteo=1' :
      `/notificaciones?limite=20${mas ? `&antes=${encodeURIComponent(siguiente.value)}` : ''}`
    const datos = await apiFetch('usuarios', ruta, { signal: actual.signal })
    if (!sesionActual(version) || controlador !== actual) return
    pendientes.value = datos.pendientes
    if (completa) {
      const nuevos = datos.notificaciones
      avisos.value = mas ? [...avisos.value, ...nuevos.filter(n => !avisos.value.some(a => a.id === n.id))] : nuevos
      siguiente.value = datos.siguiente
    }
  } catch (error) {
    if (sesionActual(version) && controlador === actual && error.name !== 'AbortError') {
      errorAvisos.value = error.message
    }
  } finally {
    if (controlador === actual) { cargando.value = false; controlador = null }
  }
}

function alPulsarNotificaciones() {
  if (!autenticado.value) {
    pedirSesion('Inicia sesión para ver tus notificaciones.')
    return
  }
  menuUsuario.value=false
  panelAbierto.value = !panelAbierto.value
  if (panelAbierto.value) cargarAvisos({ completa: true, forzar: true })
}

async function marcarLectura(aviso = null, abrir = false) {
  if (!autenticado.value || modificando.value) return
  const version = generacion
  controlador?.abort()
  controlador = null
  cargando.value = false
  modificando.value = true
  errorAvisos.value = ''
  let correcto = false
  try {
    if (!aviso || !aviso.leida) {
      const ruta = aviso ? `/notificaciones/${encodeURIComponent(aviso.id)}/leer` : '/notificaciones/leer-todas'
      await apiFetch('usuarios', ruta, { method: 'PUT', body: '{}' })
    }
    if (!sesionActual(version)) return
    correcto = true
    if (aviso) avisos.value = avisos.value.map(a => a.id === aviso.id ? { ...a, leida: true } : a)
    else avisos.value = avisos.value.map(a => ({ ...a, leida: true }))
    if (abrir && aviso) {
      panelAbierto.value = false
      await router.push(aviso.id_pregunta ? `/preguntas/${aviso.id_pregunta}` : `/usuarios/${aviso.id_actor}`)
    }
  } catch (error) {
    if (sesionActual(version)) errorAvisos.value = error.message
  } finally {
    if (sesionActual(version)) {
      modificando.value = false
      // Conserva las páginas cargadas al marcar una notificación; sincroniza el contador.
      if (correcto) await cargarAvisos({ completa: false })
    }
  }
}

function refrescarEnPrimerPlano() {
  if (document.visibilityState === 'visible') { cargarAvisos({ completa: panelAbierto.value && avisos.value.length <= 20 }); cargarConteoMensajes() }
}

watch(() => usuario.value, () => {
  menuUsuario.value=false
  generacion++
  consultaMensajes?.abort(); consultaMensajes=null; mensajesPendientes.value=0
  controlador?.abort()
  controlador = null
  avisos.value = []; pendientes.value = 0; siguiente.value = null
  errorAvisos.value = ''; cargando.value = false; modificando.value = false; panelAbierto.value = false
  if (autenticado.value) refrescarEnPrimerPlano()
})

function clicFuera(evento) {
  if (menuUsuario.value && !contenedorUsuario.value?.contains(evento.target)) menuUsuario.value=false
  if (!panelAbierto.value || !contenedorAvisos.value) return
  if (!contenedorAvisos.value.contains(evento.target)) {
    panelAbierto.value = false
  }
}

function cerrarAvisos() {
  panelAbierto.value = false
  botonAvisos.value?.focus()
}

function alTecla(evento) {
  if(evento.key==='Escape' && menuUsuario.value) cerrarMenu()
  if (evento.key === 'Escape' && panelAbierto.value) cerrarAvisos()
}

function salir() {
  menuUsuario.value=false
  cerrarSesionLocal()
  panelAbierto.value = false
  router.push('/')
}

onMounted(() => {
  medirBarra()
  if (typeof ResizeObserver !== 'undefined') { observadorBarra = new ResizeObserver(medirBarra); observadorBarra.observe(barraRef.value) }
  window.addEventListener('resize', medirBarra)
  aplicarTema()
  document.addEventListener('click', clicFuera)
  window.addEventListener('keydown', alTecla)
  document.addEventListener('visibilitychange', refrescarEnPrimerPlano)
  window.addEventListener('mensajes-actualizados', cargarConteoMensajes)
  refrescarEnPrimerPlano()
  intervalo = window.setInterval(refrescarEnPrimerPlano, 120000)
})

onUnmounted(() => {
  observadorBarra?.disconnect()
  window.removeEventListener('resize', medirBarra)
  document.documentElement.style.removeProperty('--alto-barra')
  document.removeEventListener('click', clicFuera)
  window.removeEventListener('keydown', alTecla)
  document.removeEventListener('visibilitychange', refrescarEnPrimerPlano)
  window.removeEventListener('mensajes-actualizados', cargarConteoMensajes)
  consultaMensajes?.abort()
  window.clearInterval(intervalo)
  generacion++
  controlador?.abort()
})
</script>

<template>
  <header class="barra" ref="barraRef">
    <div class="barra-interior">
      <button type="button" class="btn-icono" title="Mostrar u ocultar navegación" aria-label="Mostrar u ocultar navegación" :aria-expanded="menuAbierto" @click="$emit('alternar-menu')"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 6h16M4 12h16M4 18h16"/></svg></button>
      <router-link to="/" class="foro-marca">Foro universitario</router-link>

      <form class="busqueda-global" role="search" @submit.prevent="buscarGlobal"><input v-model="consulta" type="search" maxlength="120" aria-label="Buscar en todo el foro" placeholder="Buscar en el foro universitario" required/><button class="btn-icono" type="submit" title="Buscar" aria-label="Buscar"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="10" cy="10" r="6"/><path d="m15 15 6 6"/></svg></button></form>
      <div class="barra-acciones">
        <router-link :to="{path:'/',query:{crear:'1',...(route.path==='/'&&route.query.categoria?{categoria:route.query.categoria}:{}),...(route.path==='/'&&route.query.vista?{vista:route.query.vista}:{}),...(route.path==='/'&&route.query.comunidad?{comunidad:route.query.comunidad,slug:route.query.slug}:{})}}" class="btn-secundario nav-crear" title="Crear publicación">+ Crear</router-link>
        <router-link v-if="autenticado" to="/mensajes" class="btn-icono" :aria-label="`Mensajes privados: ${mensajesPendientes} sin leer`">
          <svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 6 9 7 9-7"/></svg>
          <span v-if="mensajesPendientes > 0" class="punto-aviso">{{mensajesPendientes}}</span>
        </router-link>
        <div ref="contenedorAvisos" class="aviso-campana">
          <button
            type="button"
            class="btn-icono"
            ref="botonAvisos"
            :aria-expanded="panelAbierto"
             :aria-label="`Notificaciones: ${pendientes} sin leer`"
            @click="alPulsarNotificaciones"
          >
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M6 9a6 6 0 1 1 12 0c0 7 3 7 3 9H3c0-2 3-2 3-9Z" />
              <path d="M10 20a2 2 0 0 0 4 0" />
            </svg>
            <span v-if="autenticado && pendientes > 0" class="punto-aviso">{{ pendientes }}</span>
          </button>

          <section v-if="panelAbierto" class="panel-notificaciones" aria-label="Notificaciones">
            <div class="notificaciones-cabecera"><h2>Notificaciones</h2><button type="button" class="btn-texto" @click="cerrarAvisos">Cerrar</button></div>
            <div class="tarjeta-acciones">
              <button type="button" class="btn-texto" :disabled="modificando" @click="cargarAvisos({ completa: true, forzar: true })">Actualizar</button>
              <button type="button" class="btn-texto" :disabled="modificando || !pendientes" @click="marcarLectura()">Marcar todas como leídas</button>
            </div>
            <p v-if="errorAvisos" role="alert" class="foro-estado">{{ errorAvisos }}</p>
            <p v-if="cargando" role="status">Cargando notificaciones…</p>
            <p v-else-if="!avisos.length && !errorAvisos">No tienes notificaciones.</p>
            <ul v-if="avisos.length">
              <li v-for="aviso in avisos" :key="aviso.id" :class="{'notificacion-nueva':!aviso.leida}">
                <span v-if="!aviso.leida" class="insignia">Nueva</span>
                <p><button type="button" class="btn-texto" :disabled="modificando" @click="marcarLectura(aviso, true)">{{ aviso.texto }}</button></p>
                <time :datetime="aviso.fecha_creacion">{{ formatearFecha(aviso.fecha_creacion) }}</time>
                <button v-if="!aviso.leida" type="button" class="btn-texto" :disabled="modificando" @click="marcarLectura(aviso)">Marcar como leída</button>
              </li>
            </ul>
            <button v-if="siguiente" type="button" class="btn-secundario" :disabled="cargando || modificando" @click="cargarAvisos({ completa: true, mas: true })">Cargar más</button>
          </section>
        </div>

        <div v-if="autenticado" ref="contenedorUsuario" class="menu-usuario-contenedor">
          <button ref="botonUsuario" type="button" class="btn-icono menu-avatar" :aria-expanded="menuUsuario" aria-label="Abrir menú de usuario" @click="menuUsuario=!menuUsuario;panelAbierto=false"><AvatarUsuario :nombre="usuario.nombre_apellido" :url="usuario.avatar_url" /></button>
          <section v-if="menuUsuario" class="menu-usuario" aria-label="Opciones de cuenta">
            <p class="menu-identidad"><strong>{{usuario.nombre_apellido}}</strong><span class="insignia">{{usuario.rol}}</span></p>
            <router-link :to="`/usuarios/${usuario.id}`"><IconoForo nombre="perfil"/> Ver perfil</router-link>
            <router-link :to="`/usuarios/${usuario.id}?editar=perfil`"><IconoForo nombre="editar"/> Editar perfil</router-link>
            <router-link :to="`/usuarios/${usuario.id}?editar=avatar`"><IconoForo nombre="imagen"/> Editar avatar</router-link>
            <router-link to="/?crear=1&borrador=1"><IconoForo nombre="publicaciones"/> Borradores</router-link>
            <router-link :to="`/usuarios/${usuario.id}?tab=guardadas`"><IconoForo nombre="guardados"/> Publicaciones guardadas</router-link>
            <router-link :to="`/usuarios/${usuario.id}?tab=logros`"><IconoForo nombre="logros"/> Logros</router-link>
            <router-link :to="`/usuarios/${usuario.id}?tab=configuracion`"><IconoForo nombre="configuracion"/> Configuración</router-link>
            <button type="button" @click="oscuro=!oscuro;aplicarTema()" :aria-pressed="oscuro"><IconoForo nombre="tema"/> {{oscuro?'Modo claro':'Modo oscuro'}}</button>
            <button type="button" class="menu-salir" @click="salir"><IconoForo nombre="salir"/> Cerrar sesión</button>
          </section>
        </div>
        <template v-else>
          <router-link to="/registro" class="btn-texto">Crear cuenta</router-link>
          <router-link to="/login" class="btn-primario btn-ancho-auto">Iniciar sesión</router-link>
        </template>
      </div>
    </div>
  </header>
</template>
