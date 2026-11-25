<script setup>
import { ref, watch } from 'vue'
import { iniciales } from '../utils/formato.js'
const props = defineProps({ nombre: String, url: String, chico: Boolean })
const fallo = ref(false)
watch(() => props.url, () => { fallo.value = false })
</script>
<template>
  <span class="avatar" :class="{ 'avatar-chico': chico }" aria-hidden="true">
    <img v-if="url && !fallo" :src="url" alt="" loading="lazy" referrerpolicy="no-referrer" @error="fallo = true" style="width:100%;height:100%;object-fit:cover;border-radius:50%" />
    <template v-else>{{ iniciales(nombre) }}</template>
  </span>
</template>
