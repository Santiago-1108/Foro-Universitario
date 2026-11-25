<script setup>
import { ref, onBeforeUnmount } from 'vue'
import IconoForo from './IconoForo.vue'
import { apiFetch } from '../services/api.js'
const props=defineProps({tipo:{type:String,required:true},uso:{type:String,default:'publicacion'},bloqueado:Boolean}),emit=defineEmits(['cambio'])
const archivos=ref([]),error=ref(''),cargando=ref(false),selector=ref(null),arrastrando=ref(false)
const mimes=['image/jpeg','image/png','image/webp']
const tope=()=>props.uso==='icono'?500000:props.uso==='portada'?1000000:props.tipo==='video'?10000000:2000000
const cantidadMax=()=>props.uso!=='publicacion'||props.tipo==='video'?1:3
function quitar(i){URL.revokeObjectURL(archivos.value[i].preview);archivos.value.splice(i,1);emit('cambio',archivos.value.length,archivos.value[0]?.preview||'')}
const preparando=ref(false)
async function comprimir(f){
  if(f.size<=tope())return f
  if(f.size>12000000||typeof createImageBitmap!=='function')throw new Error('Reduce la imagen antes de subirla')
  const bitmap=await createImageBitmap(f)
  try{if(bitmap.width*bitmap.height>25000000)throw new Error('Resolución excesiva');const canvas=document.createElement('canvas'),escala=Math.min(1,(props.uso==='icono'?512:1600)/Math.max(bitmap.width,bitmap.height));canvas.width=Math.max(1,Math.round(bitmap.width*escala));canvas.height=Math.max(1,Math.round(bitmap.height*escala));canvas.getContext('2d').drawImage(bitmap,0,0,canvas.width,canvas.height);for(const calidad of [.85,.65,.45]){const blob=await new Promise(ok=>canvas.toBlob(ok,'image/webp',calidad));if(blob&&mimes.includes(blob.type)&&blob.size>0&&blob.size<=tope())return new File([blob],f.name.replace(/\.[^.]+$/,'')+(blob.type==='image/webp'?'.webp':'.png'),{type:blob.type})}throw new Error('No fue posible reducir la imagen al límite permitido')}finally{bitmap.close()}
}
async function agregar(files){if(preparando.value||cargando.value||props.bloqueado)return;preparando.value=true;error.value='';try{for(let f of Array.from(files)){const video=props.tipo==='video';if(archivos.value.length>=cantidadMax()||!(video?f.type==='video/mp4':mimes.includes(f.type))||f.size<=0){error.value='Archivo no admitido o límite superado.';continue}try{if(!video)f=await comprimir(f);if(f.size>tope())throw new Error('Tamaño máximo superado');archivos.value.push({file:f,preview:URL.createObjectURL(f),progreso:0,id:null,verificado:false})}catch(e){error.value=e.message}}emit('cambio',archivos.value.length,archivos.value[0]?.preview||'')}finally{preparando.value=false}}
function soltar(e){arrastrando.value=false;if(!props.bloqueado&&!cargando.value)agregar(e.dataTransfer.files)}
function subir(a,url){return new Promise((ok,no)=>{const xhr=new XMLHttpRequest();xhr.open('PUT',url);xhr.setRequestHeader('Content-Type',a.file.type);xhr.upload.onprogress=e=>{if(e.lengthComputable)a.progreso=Math.round(100*e.loaded/e.total)};xhr.timeout=120000;xhr.onload=()=>xhr.status>=200&&xhr.status<300?ok():no(new Error(`Storage rechazó el archivo (HTTP ${xhr.status})`));xhr.onerror=xhr.ontimeout=()=>no(new Error('No se pudo subir el archivo'));xhr.send(a.file)})}
async function preparar(){if(preparando.value)throw new Error('Espera a que termine la preparación de imágenes');if(!archivos.value.length)throw new Error('Selecciona al menos un archivo');cargando.value=true;error.value='';try{for(const a of archivos.value){if(a.verificado)continue;if(!a.id){const r=await apiFetch('foro','/multimedia/reservar',{method:'POST',body:JSON.stringify({mime:a.file.type,bytes:a.file.size,uso:props.uso})});a.id=r.id;try{await subir(a,r.url)}catch(e){try{await apiFetch('foro',`/multimedia/${a.id}`,{method:'DELETE'})}catch{}a.id=null;throw e}}await apiFetch('foro',`/multimedia/${a.id}/verificar`,{method:'PUT',body:'{}'});a.verificado=true;a.progreso=100}return archivos.value.map(a=>a.id)}catch(e){error.value=e.message;throw e}finally{cargando.value=false}}
async function eliminar(i){const a=archivos.value[i];if(a.id)try{await apiFetch('foro',`/multimedia/${a.id}`,{method:'DELETE'})}catch(e){error.value=e.message;return}quitar(i)}
onBeforeUnmount(()=>archivos.value.forEach(a=>URL.revokeObjectURL(a.preview)))
defineExpose({preparar})
</script>
<template>
  <div class="carga-multimedia" :class="{'carga-activa':arrastrando}" @dragover.prevent="arrastrando=true" @dragleave.self="arrastrando=false" @drop.prevent="soltar">
    <input ref="selector" class="selector-archivo-nativo" type="file" tabindex="-1" aria-hidden="true" :multiple="uso==='publicacion'&&tipo!=='video'" :accept="tipo==='video'?'video/mp4':'image/jpeg,image/png,image/webp'" :disabled="bloqueado||cargando||preparando" @change="agregar($event.target.files);$event.target.value=''" />
    <div class="carga-zona">
      <span class="carga-icono"><IconoForo :nombre="tipo==='video'?'video':'imagen'"/></span>
      <strong>{{archivos.length?'Archivos seleccionados':'Arrastra y suelta aquí'}}</strong>
      <button type="button" class="btn-secundario btn-ancho-auto" :disabled="bloqueado||cargando||preparando||archivos.length>=cantidadMax()" @click="selector?.click()">{{archivos.length?'Añadir archivo':'Seleccionar archivo'+(cantidadMax()>1?'s':'')}}</button>
      <small>{{uso==='icono'?'JPG, PNG o WebP · hasta 500 KB':uso==='portada'?'JPG, PNG o WebP · hasta 1 MB':tipo==='video'?'MP4 · hasta 10 MB · recomendado: 60 s':'Hasta 3 imágenes JPG, PNG o WebP · 2 MB cada una'}}</small>
    </div>
    <p v-if="preparando" role="status" class="nota-demo">Preparando imágenes…</p>
    <article v-for="(a,i) in archivos" :key="a.preview" class="archivo-previo">
      <img v-if="tipo!=='video'" :src="a.preview" alt="Vista previa"><video v-else :src="a.preview" controls preload="metadata" playsinline/>
      <div><strong class="archivo-nombre">{{a.file.name}}</strong><small>{{a.file.size>=1000000?(a.file.size/1000000).toFixed(2)+' MB':Math.ceil(a.file.size/1000)+' KB'}}</small>
        <div v-if="cargando||a.progreso>0" class="archivo-progreso"><progress :value="a.progreso" max="100" aria-label="Progreso de carga"></progress><small>{{a.progreso}}%</small></div>
        <small v-if="a.verificado">Listo para publicar</small>
      </div>
      <button type="button" class="btn-icono" :aria-label="'Quitar '+a.file.name" title="Quitar archivo" :disabled="bloqueado||cargando||preparando" @click="eliminar(i)"><IconoForo nombre="cerrar"/></button>
    </article>
    <p v-if="error" class="error" role="alert">{{error}}</p>
  </div>
</template>
