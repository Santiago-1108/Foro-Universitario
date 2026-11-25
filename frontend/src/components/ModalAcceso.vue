<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { cerrarModalAcceso, modalAcceso } from '../services/sesion.js'

const route = useRoute()
const titulo = ref(null)
const dialogo = ref(null)
let focoAnterior = null

const consulta = computed(() => {
  const camino = route.fullPath
  if (camino.startsWith('/login') || camino.startsWith('/registro')) return {}
  return { redirect: camino }
})

watch(
  () => modalAcceso.value.abierto,
  async (abierto) => {
    if (abierto) {
      focoAnterior = document.activeElement
      await nextTick()
      if (modalAcceso.value.abierto) titulo.value?.focus()
    } else {
      const anterior = focoAnterior
      focoAnterior = null
      await nextTick()
      if (!modalAcceso.value.abierto && anterior?.isConnected) anterior.focus()
    }
  },
)

function alTecla(evento) {
  if (!modalAcceso.value.abierto) return
  if (evento.key === 'Escape') { evento.preventDefault(); cerrarModalAcceso(); return }
  if (evento.key !== 'Tab' || !dialogo.value) return
  const controles = [...dialogo.value.querySelectorAll('a[href], button:not([disabled])')]
  if (!controles.length) { evento.preventDefault(); return }
  const primero = controles[0], ultimo = controles[controles.length - 1]
  const actual = document.activeElement
  if (!controles.includes(actual) || (evento.shiftKey && actual === primero) || (!evento.shiftKey && actual === ultimo)) {
    evento.preventDefault()
    ;(evento.shiftKey ? ultimo : primero).focus()
  }
}

onMounted(() => window.addEventListener('keydown', alTecla))
onUnmounted(() => window.removeEventListener('keydown', alTecla))
</script>

<template>
  <Teleport to="body">
  <div
    v-if="modalAcceso.abierto"
    class="modal-fondo"
    @click.self="cerrarModalAcceso"
  >
    <div
      class="modal-tarjeta"
      ref="dialogo"
      role="dialog"
      aria-modal="true"
      aria-labelledby="titulo-modal-acceso"
    >
      <h2 id="titulo-modal-acceso" ref="titulo" tabindex="-1">Inicia sesión para participar</h2>
      <p>{{ modalAcceso.mensaje }}</p>
      <div class="modal-acciones">
        <router-link
          class="btn-primario btn-ancho-auto"
          :to="{ path: '/login', query: consulta }"
          @click="cerrarModalAcceso"
        >
          Iniciar sesión
        </router-link>
        <router-link
          class="btn-secundario"
          :to="{ path: '/registro', query: consulta }"
          @click="cerrarModalAcceso"
        >
          Crear cuenta
        </router-link>
        <button type="button" class="btn-texto" @click="cerrarModalAcceso">Seguir leyendo</button>
      </div>
    </div>
  </div>
  </Teleport>
</template>
