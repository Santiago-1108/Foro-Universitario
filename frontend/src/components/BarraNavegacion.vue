<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { NOTIFICACIONES_DEMO } from '../datos/demostracion.js'
import {
  autenticado,
  cerrarSesionLocal,
  esAdministrador,
  pedirSesion,
  plan,
  usuario,
} from '../services/sesion.js'
import { iniciales } from '../utils/formato.js'

const router = useRouter()
const contenedorAvisos = ref(null)
const panelAbierto = ref(false)
const vistas = ref(sessionStorage.getItem('notificaciones_vistas') === '1')

const pendientes = computed(() => (vistas.value ? 0 : NOTIFICACIONES_DEMO.length))

function alPulsarNotificaciones() {
  if (!autenticado.value) {
    pedirSesion('Inicia sesión para ver tus notificaciones.')
    return
  }
  panelAbierto.value = !panelAbierto.value
  if (panelAbierto.value) {
    vistas.value = true
    sessionStorage.setItem('notificaciones_vistas', '1')
  }
}

function clicFuera(evento) {
  if (!panelAbierto.value || !contenedorAvisos.value) return
  if (!contenedorAvisos.value.contains(evento.target)) {
    panelAbierto.value = false
  }
}

function alTecla(evento) {
  if (evento.key === 'Escape') panelAbierto.value = false
}

function salir() {
  cerrarSesionLocal()
  panelAbierto.value = false
  router.push('/')
}

onMounted(() => {
  document.addEventListener('click', clicFuera)
  window.addEventListener('keydown', alTecla)
})

onUnmounted(() => {
  document.removeEventListener('click', clicFuera)
  window.removeEventListener('keydown', alTecla)
})
</script>

<template>
  <header class="barra">
    <div class="barra-interior">
      <router-link to="/" class="foro-marca">Foro universitario</router-link>

      <nav class="barra-nav" aria-label="Principal">
        <router-link to="/" class="barra-enlace" exact-active-class="barra-enlace-activo">
          Inicio
        </router-link>
        <router-link
          v-if="esAdministrador"
          to="/admin"
          class="barra-enlace"
          active-class="barra-enlace-activo"
        >
          Administración
        </router-link>
      </nav>

      <div class="barra-acciones">
        <div ref="contenedorAvisos" class="aviso-campana">
          <button
            type="button"
            class="btn-icono"
            :aria-expanded="panelAbierto"
            aria-label="Notificaciones"
            @click="alPulsarNotificaciones"
          >
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M6 9a6 6 0 1 1 12 0c0 7 3 7 3 9H3c0-2 3-2 3-9Z" />
              <path d="M10 20a2 2 0 0 0 4 0" />
            </svg>
            <span v-if="autenticado && pendientes > 0" class="punto-aviso">{{ pendientes }}</span>
          </button>

          <section v-if="panelAbierto" class="panel-notificaciones" aria-label="Notificaciones">
            <p class="nota-demo">Demostración. El servidor aún no envía notificaciones.</p>
            <ul>
              <li v-for="aviso in NOTIFICACIONES_DEMO" :key="aviso.id">
                <p>{{ aviso.texto }}</p>
                <time>{{ aviso.cuando }}</time>
              </li>
            </ul>
          </section>
        </div>

        <div v-if="autenticado" class="sesion-activa">
          <span v-if="plan === 'premium'" class="insignia insignia-premium">Premium</span>
          <span class="avatar" aria-hidden="true">{{ iniciales(usuario.nombre_apellido) }}</span>
          <span class="sesion-datos">
            <span class="foro-nombre">{{ usuario.nombre_apellido }}</span>
            <span class="insignia">{{ usuario.rol }}</span>
          </span>
          <button type="button" class="btn-secundario btn-salir" @click="salir">Cerrar sesión</button>
        </div>
        <template v-else>
          <router-link to="/registro" class="btn-texto">Crear cuenta</router-link>
          <router-link to="/login" class="btn-primario btn-ancho-auto">Iniciar sesión</router-link>
        </template>
      </div>
    </div>
  </header>
</template>
