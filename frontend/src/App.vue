<script setup>
import { useRoute, useRouter } from 'vue-router'
import { watch, ref } from 'vue'
import { usuario } from './services/sesion.js'
import BarraNavegacion from './components/BarraNavegacion.vue'
import MenuLateral from './components/MenuLateral.vue'
import ModalAcceso from './components/ModalAcceso.vue'

document.documentElement.dataset.tema=localStorage.getItem('foro-tema')==='oscuro'?'oscuro':'claro'
const route = useRoute()
const router = useRouter()
const menuAbierto = ref(window.innerWidth > 1000)
watch(() => route.fullPath, () => { if (window.innerWidth <= 1000) menuAbierto.value = false })
watch(usuario, (actual, anterior) => {
  if (route.meta.requiereAdmin && (actual?.rol !== 'admin' || actual?.id !== anterior?.id)) router.replace('/')
  else if (route.meta.requiereSesion && !actual) router.replace('/login')
})
</script>

<template>
  <BarraNavegacion v-if="route.meta.barra !== false" :menu-abierto="menuAbierto" @alternar-menu="menuAbierto = !menuAbierto" />
  <div v-if="route.meta.barra !== false" class="foro-shell" :class="{'menu-visible':menuAbierto}">
    <button v-if="menuAbierto" class="menu-fondo" aria-label="Cerrar navegación" @click="menuAbierto=false"></button>
    <MenuLateral v-if="menuAbierto" />
    <div class="shell-contenido"><router-view /></div>
  </div>
  <router-view v-else />
  <ModalAcceso />
</template>
