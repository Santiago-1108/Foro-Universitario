<script setup>
import IconoForo from './IconoForo.vue'
import CrearComunidad from './CrearComunidad.vue'
import { ref, watch, onMounted, onUnmounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import { apiFetch } from '../services/api.js'
import { usuario, esAdministrador, exigirSesion } from '../services/sesion.js'
const route=useRoute(), categorias=ref([]), error=ref('')
const modalComunidad=ref(false), nuevasComunidades=ref([]), errorNuevas=ref('')
let versionComunidades=0
async function cargarComunidades(){const v=++versionComunidades;nuevasComunidades.value=[];errorNuevas.value='';if(!usuario.value)return;try{const r=await apiFetch('foro','/comunidades?mias=1');if(v===versionComunidades)nuevasComunidades.value=r.slice(0,20)}catch(e){if(v===versionComunidades)errorNuevas.value=e.message}}
function abrirComunidad(){if(exigirSesion('Inicia sesión para crear una comunidad.'))modalComunidad.value=true}
watch(()=>usuario.value?.id,()=>{modalComunidad.value=false;cargarComunidades()})
onMounted(()=>{cargarComunidades();window.addEventListener('comunidades-actualizadas',cargarComunidades)})
onUnmounted(()=>{versionComunidades++;window.removeEventListener('comunidades-actualizadas',cargarComunidades)})
let version=0
async function cargar(){const v=++version; error.value=''; categorias.value=[]; try {const r=await apiFetch('foro','/categorias'); if(v===version) categorias.value=r} catch(e){if(v===version)error.value=e.message}}
watch(()=>usuario.value?.id,cargar)
onMounted(()=>{cargar();window.addEventListener('categorias-actualizadas',cargar)})
onUnmounted(()=>{version++;window.removeEventListener('categorias-actualizadas',cargar)})
const links=computed(()=>[{n:'Inicio',icon:'inicio',to:'/'},{n:'Popular',icon:'popular',to:'/?orden=popular'},{n:'Explorar',icon:'explorar',to:'/?explorar=1'},...(usuario.value?[{n:'Siguiendo',icon:'siguiendo',to:'/?vista=personalizado'},{n:'Guardados',icon:'guardados',to:`/usuarios/${usuario.value.id}?tab=guardadas`},{n:'Ocultos',icon:'guardados',to:`/usuarios/${usuario.value.id}?tab=ocultas`},{n:'Historial',icon:'historial',to:`/usuarios/${usuario.value.id}?tab=historial`},{n:'Mis publicaciones',icon:'publicaciones',to:`/usuarios/${usuario.value.id}?tab=publicacion`}]:[]),...(esAdministrador.value?[{n:'Administración',icon:'configuracion',to:'/admin'}]:[])])
</script>
<template>
  <aside class="menu-lateral" aria-label="Navegación lateral">
    <nav><router-link v-for="l in links" :key="l.n" :to="l.to" :class="{'lateral-activo':route.fullPath===l.to}" :aria-current="route.fullPath===l.to?'page':undefined"><IconoForo :nombre="l.icon"/>{{l.n}}</router-link></nav>
    <details open><summary>Comunidades</summary><button class="btn-texto lateral-crear-comunidad" type="button" @click="abrirComunidad"><IconoForo nombre="mas"/> Crear comunidad</button><router-link to="/comunidades">Explorar comunidades</router-link><router-link v-if="usuario" to="/comunidades?mias=1">Mis comunidades</router-link><router-link v-for="c in nuevasComunidades" :key="c.id" :to="`/comunidades/${c.slug}`">{{c.nombre}}</router-link><p v-if="errorNuevas" class="error" role="alert">{{errorNuevas}}</p></details>
    <CrearComunidad v-if="modalComunidad" :categorias="categorias" @cerrar="modalComunidad=false" @creada="cargarComunidades"/>
    <details open><summary>Categorías</summary><router-link v-for="c in categorias" :key="c.id" :to="{path:'/',query:{categoria:String(c.id)}}" :class="{'lateral-activo':route.path==='/'&&route.query.categoria===String(c.id)}">{{c.nombre}}</router-link><p v-if="error" role="alert">{{error}} <button class="btn-texto" @click="cargar">Reintentar</button></p></details>
    <details v-if="usuario" open><summary>Categorías seguidas</summary><router-link v-for="c in categorias.filter(c=>c.siguiendo)" :key="c.id" :to="{path:'/',query:{categoria:String(c.id)}}">{{c.nombre}}</router-link><p v-if="!categorias.some(c=>c.siguiendo)" class="nota-demo">Aún no sigues categorías.</p></details>
  </aside>
</template>
