<script setup>
import {ref} from 'vue'
import {apiFetch} from '../services/api.js'
const ocupado=ref(false),aviso=ref(''),error=ref('')
async function limpiar(){if(ocupado.value)return;ocupado.value=true;aviso.value='';error.value='';try{const r=await apiFetch('foro','/multimedia/limpiar',{method:'POST',body:'{}'});aviso.value=r.eliminados?`${r.eliminados} archivos retirados.`:'No hay archivos vencidos disponibles para retirar.'}catch(e){error.value=e.message}finally{ocupado.value=false}}
</script>
<template><section class="ajuste-almacenamiento"><h3>Almacenamiento personal</h3><p>Libera espacio de cargas propias que ya vencieron y no están en uso. Los archivos recientes se conservan.</p><button class="btn-secundario" type="button" :disabled="ocupado" @click="limpiar">{{ocupado?'Revisando…':'Liberar espacio'}}</button><p v-if="aviso" role="status">{{aviso}}</p><p v-if="error" class="error" role="alert">{{error}}</p></section></template>
