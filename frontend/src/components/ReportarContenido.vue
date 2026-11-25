<script setup>
import { ref, watch } from 'vue'
import { apiFetch } from '../services/api.js'
import { usuario, exigirSesion } from '../services/sesion.js'
const props = defineProps({ tipo: {type:String, required:true}, identificador:{type:Number, required:true}, autor:{type:Number, default:0} })
const abierto=ref(false), motivo=ref('spam'), detalle=ref(''), ocupado=ref(false), aviso=ref(''), error=ref('')
let version=0
watch([()=>props.identificador,()=>usuario.value?.id],()=>{version++; abierto.value=false; detalle.value=''; aviso.value=''; error.value=''; ocupado.value=false})
async function enviar(){
  if(ocupado.value || !exigirSesion('Inicia sesión para reportar.')) return
  const actual=version; ocupado.value=true; error.value=''; aviso.value=''
  try{
    await apiFetch('usuarios','/moderacion/reportes',{method:'POST',body:JSON.stringify({tipo:props.tipo,id_objeto:props.identificador,motivo:motivo.value,detalle:detalle.value})})
    if(actual===version){aviso.value='Reporte enviado a administración.'; abierto.value=false; detalle.value=''}
  }catch(e){if(actual===version)error.value=e.message}
  finally{if(actual===version)ocupado.value=false}
}
</script>
<template>
  <div v-if="!usuario || usuario.id !== autor" class="reporte-contenido">
    <button type="button" class="btn-texto" :aria-expanded="abierto" @click="exigirSesion('Inicia sesión para reportar.') && (abierto=!abierto)">{{abierto?'Cancelar reporte':'Reportar'}}</button>
    <form v-if="abierto" class="form-comentario" @submit.prevent="enviar">
      <label>Motivo<select v-model="motivo"><option value="spam">Spam</option><option value="acoso">Acoso</option><option value="contenido_inapropiado">Contenido inapropiado</option><option value="otro">Otro</option></select></label>
      <label>Detalle (opcional)<textarea v-model="detalle" maxlength="500" rows="2"></textarea></label>
      <button type="submit" class="btn-primario btn-ancho-auto" :disabled="ocupado">Enviar reporte</button>
    </form>
    <p v-if="error" class="error" role="alert">{{error}}</p><p v-if="aviso" class="aviso-exito" role="status">{{aviso}}</p>
  </div>
</template>
