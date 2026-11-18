<script setup>
import { useRoute } from 'vue-router'
import BarraNavegacion from './components/BarraNavegacion.vue'
import ModalAcceso from './components/ModalAcceso.vue'

const route = useRoute()
</script>

<template>
  <BarraNavegacion v-if="route.meta.barra !== false" />
  <router-view />
  <ModalAcceso />
</template>
