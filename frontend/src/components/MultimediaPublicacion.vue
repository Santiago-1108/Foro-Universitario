<script setup>
import { ref, watch, onMounted, onBeforeUnmount } from 'vue'
import { apiFetch } from '../services/api.js'
import { usuario } from '../services/sesion.js'
const props=defineProps({id:{type:[Number,String],required:true}}),elemento=ref(null),archivos=ref([]),indice=ref(0),error=ref(''),cargando=ref(false)
let version=0,observer,visible=false
async function cargar(){const v=++version;error.value='';cargando.value=true;archivos.value=[];indice.value=0;try{const r=await apiFetch('foro',`/multimedia/publicaciones/${props.id}`);if(v===version)archivos.value=r}catch(e){if(v===version)error.value=e.message}finally{if(v===version)cargando.value=false}}
onMounted(()=>{if(!('IntersectionObserver'in window)){visible=true;cargar();return}observer=new IntersectionObserver(e=>{if(e.some(x=>x.isIntersecting)){visible=true;observer.disconnect();cargar()}},{rootMargin:'100px'});observer.observe(elemento.value)})
watch([()=>props.id,()=>usuario.value?.id],()=>{version++;archivos.value=[];if(visible)cargar()})
onBeforeUnmount(()=>{version++;observer?.disconnect()})
</script>
<template><div ref="elemento" class="multimedia-publicacion"><p v-if="cargando" role="status">Cargando archivos…</p><p v-if="error" class="error" role="alert">{{error}} <button class="btn-texto" @click="cargar">Reintentar</button></p><template v-if="archivos.length"><video v-if="archivos[indice].mime==='video/mp4'" :key="archivos[indice].id" :src="archivos[indice].url" controls preload="none" playsinline @error="error='No se pudo reproducir el video. Intenta recargarlo.'"></video><img v-else :src="archivos[indice].url" alt="Imagen adjunta a la publicación" loading="lazy" referrerpolicy="no-referrer" @error="error='No se pudo cargar la imagen. Intenta recargarla.'"><div v-if="archivos.length>1" class="tarjeta-acciones"><button class="btn-texto" :disabled="indice===0" @click="indice--">Anterior</button><span>{{indice+1}} / {{archivos.length}}</span><button class="btn-texto" :disabled="indice===archivos.length-1" @click="indice++">Siguiente</button></div><button type="button" class="btn-texto" @click="cargar">Recargar multimedia</button></template></div></template>
