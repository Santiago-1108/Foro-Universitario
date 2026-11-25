<script setup>
import { ref } from 'vue'
const props=defineProps({modelValue:{type:String,default:''},etiqueta:{type:String,required:true},bloqueado:Boolean})
const emit=defineEmits(['update:modelValue'])
const campo=ref(null),aviso=ref('')
function actualizar(v){aviso.value='';emit('update:modelValue',v)}
function pegarEvento(e){const texto=e.clipboardData?.getData('text/plain');if(!texto)return;e.preventDefault();actualizar(texto.trim())}
async function pegar(){campo.value?.focus();try{if(!navigator.clipboard?.readText)throw new Error();const texto=await navigator.clipboard.readText();if(!texto.trim()){aviso.value='No hay texto en el portapapeles.';return}actualizar(texto.trim())}catch{aviso.value='Pulsa Ctrl + V en el campo o utiliza el menú Pegar del navegador.'}}
</script>
<template>
  <div class="campo-url-imagen">
    <label>{{etiqueta}}<input ref="campo" type="url" inputmode="url" autocomplete="off" spellcheck="false" maxlength="2048" placeholder="https://ejemplo.com/imagen.png" :value="modelValue" :disabled="bloqueado" @input="actualizar($event.target.value)" @paste.stop="pegarEvento" /></label>
    <button type="button" class="btn-secundario" :disabled="bloqueado" @click="pegar">Pegar URL</button>
    <small v-if="aviso" role="status">{{aviso}}</small>
    <small>Usa un enlace HTTPS directo a una imagen. Opcional.</small>
  </div>
</template>
