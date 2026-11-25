<script setup>
import GestionAlmacenamiento from "../components/GestionAlmacenamiento.vue"
import MultimediaPublicacion from '../components/MultimediaPublicacion.vue'
import { actividadDeTipo } from '../utils/actividad.js'
import ReportarContenido from '../components/ReportarContenido.vue'
import { computed, nextTick, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { apiFetch } from '../services/api.js'
import { usuario, exigirSesion } from '../services/sesion.js'
import { formatearFecha } from '../utils/formato.js'
import AvatarUsuario from '../components/AvatarUsuario.vue'

const route = useRoute(), router=useRouter()
const portada=ref(''), falloPortada=ref(false), enlacePerfil=ref(''), editorAvatar=ref(null)
const privadas=['guardadas','historial','ocultas','positivos','negativos','logros','configuracion']
const tabs=computed(()=>[{id:'general',n:'Vista general'},{id:'publicacion',n:'Publicaciones'},{id:'respuesta',n:'Respuestas'},{id:'comentario',n:'Comentarios'},...(propio.value?[{id:'guardadas',n:'Guardados'},{id:'historial',n:'Historial'},{id:'ocultas',n:'Ocultos'},{id:'positivos',n:'Votos positivos'},{id:'negativos',n:'Votos negativos'}]:[])])
const tab=computed(()=>{const t=String(route.query.tab||'general');return ['general','publicacion','respuesta','comentario'].includes(t)|| (propio.value&&privadas.includes(t))?t:'general'})
const listaPrivada=computed(()=>['guardadas','historial','ocultas','positivos','negativos'].includes(tab.value))
let versionActividad=0, offsetActividad=0
const tipoVoto=ref('publicacion')
async function compartirPerfil(){const url=new URL(`/usuarios/${perfil.value.id}`,location.origin).href;try{await navigator.clipboard.writeText(url);enlacePerfil.value='Enlace copiado'}catch{enlacePerfil.value=url}}
async function limpiarHistorial(){if(!propio.value||!confirm('¿Borrar tu historial de visitas?'))return;try{await apiFetch('foro','/preguntas/historial',{method:'DELETE'});await reiniciarActividad()}catch(e){errorActividad.value=e.message}}
async function reiniciarActividad(){versionActividad++;offsetActividad=0;actividad.value=[];hayMas.value=false;cargandoActividad.value=false;errorActividad.value='';await cargarActividad()}
async function abrirEdicion(){if(!propio.value||!route.query.editar)return;editando.value=true;await nextTick();if(route.query.editar==='avatar')editorAvatar.value?.focus()}

const perfil = ref(null), actividad = ref([]), seguidos = ref([])
const cargando = ref(false), ocupado = ref(false), cargandoActividad = ref(false), cargandoSeguidos = ref(false)
const error = ref(''), aviso = ref(''), errorActividad = ref(''), errorSeguidos = ref('')
const hayMas = ref(false), hayMasSeguidos = ref(false), editando = ref(false), verSeguidos = ref(false)
const biografia = ref(''), avatar = ref('')
const bloqueados = ref([]), verBloqueados = ref(false), masBloqueados = ref(false), cargandoBloqueados = ref(false), errorBloqueados = ref('')
async function cargarBloqueados() {
  if (!propio.value || cargandoBloqueados.value) return
  const actual = version; verBloqueados.value = true; cargandoBloqueados.value = true; errorBloqueados.value = ''
  try { const r = await apiFetch('usuarios', `/usuarios/perfil/bloqueados?offset=${bloqueados.value.length}`); if (actual===version) { bloqueados.value.push(...r.usuarios); masBloqueados.value=r.hay_mas } }
  catch(e) { if (actual===version) errorBloqueados.value=e.message }
  finally { if (actual===version) cargandoBloqueados.value=false }
}
async function bloquear() {
  if (ocupado.value || propio.value || !exigirSesion('Inicia sesión para bloquear usuarios.')) return
  const actual=version, id=perfil.value.id, activo=!perfil.value.bloqueado
  if (activo && !window.confirm('¿Bloquear a este usuario? Dejarán de seguirse y no podrán interactuar directamente.')) return
  ocupado.value=true; aviso.value=''
  try { await apiFetch('usuarios', `/usuarios/${id}/bloquear`, {method:'PUT',body:JSON.stringify({activo})}); if (actual===version) await cargar() }
  catch(e) { if (actual===version) aviso.value=e.message } finally { if (actual===version) ocupado.value=false }
}
const propio = computed(() => !!perfil.value && !!usuario.value && String(usuario.value.id) === String(perfil.value.id))
let version = 0

async function cargar() {
  const actual = ++version
  const id = route.params.id
  cargando.value = true
  versionActividad++;offsetActividad=0;enlacePerfil.value='';falloPortada.value=false;perfil.value = null; actividad.value = []; seguidos.value = []; bloqueados.value=[]; verBloqueados.value=false; masBloqueados.value=false; cargandoBloqueados.value=false; errorBloqueados.value=''
  hayMas.value = false; hayMasSeguidos.value = false; verSeguidos.value = false
  error.value = ''; aviso.value = ''; errorActividad.value = ''; errorSeguidos.value = ''
  editando.value = false; ocupado.value = false; cargando.value = true
  cargandoActividad.value = false; cargandoSeguidos.value = false
  try {
    const datos = await apiFetch('usuarios', `/usuarios/${id}/perfil`)
    if (actual !== version) return
    perfil.value = datos
    biografia.value = datos.biografia; avatar.value = datos.avatar_url || '';portada.value=datos.portada_url||''
    await abrirEdicion();if(actual===version){cargando.value=false;await reiniciarActividad()}
  } catch (e) { if (actual === version) error.value = e.message }
  finally { if (actual === version) cargando.value = false }
}
async function cargarActividad() {
  if (cargandoActividad.value || !perfil.value || perfil.value.bloqueo_mutuo || ['logros','configuracion'].includes(tab.value)) return
  const actual = versionActividad, seccion=tab.value, idPerfil=perfil.value.id
  const vigente=()=>actual===versionActividad && tab.value===seccion && perfil.value?.id===idPerfil
  cargandoActividad.value = true; errorActividad.value = ''
  try {
    if(['positivos','negativos'].includes(seccion)){
      if(!propio.value)return
      const datos=await apiFetch('usuarios',`/usuarios/perfil/votos?${new URLSearchParams({signo:seccion==='positivos'?'1':'-1',tipo:tipoVoto.value,offset:offsetActividad})}`)
      if(!vigente()||!propio.value)return
      offsetActividad+=datos.actividad.length;actividad.value.push(...datos.actividad);hayMas.value=datos.hay_mas
    }else if(listaPrivada.value){
      if(!propio.value)return
      const datos=await apiFetch('foro',`/preguntas?${new URLSearchParams({vista:seccion,orden:'reciente',offset:offsetActividad,limite:21})}`)
      if(!vigente()||!propio.value)return
      hayMas.value=datos.length>20;offsetActividad+=Math.min(datos.length,20);actividad.value.push(...datos.slice(0,20).map(p=>({...p,tipo_publicacion:p.tipo,tipo:'publicacion',id_pregunta:p.id,extracto:p.contenido})))
    }else{
      const datos=await apiFetch('usuarios',`/usuarios/${idPerfil}/actividad?${new URLSearchParams({offset:offsetActividad,tipo:seccion==='general'?'':seccion})}`)
      if(!vigente())return
      offsetActividad+=datos.actividad.length;actividad.value.push(...actividadDeTipo(datos.actividad,seccion));hayMas.value=datos.hay_mas
    }
  } catch (e) { if (actual === versionActividad) errorActividad.value = e.message }
  finally { if (actual === versionActividad) cargandoActividad.value = false }
}
async function cargarSeguidos() {
  if (!propio.value || cargandoSeguidos.value) return
  const actual = version
  verSeguidos.value = true; cargandoSeguidos.value = true; errorSeguidos.value = ''
  try {
    const datos = await apiFetch('usuarios', `/usuarios/perfil/seguidos?offset=${seguidos.value.length}`)
    if (actual !== version) return
    seguidos.value.push(...datos.usuarios); hayMasSeguidos.value = datos.hay_mas
  } catch (e) { if (actual === version) errorSeguidos.value = e.message }
  finally { if (actual === version) cargandoSeguidos.value = false }
}
async function guardar() {
  if (!propio.value || ocupado.value) return
  const actual = version
  ocupado.value = true; aviso.value = ''
  try {
    await apiFetch('usuarios', '/usuarios/perfil', { method:'PUT', body:JSON.stringify({biografia:biografia.value,avatar_url:avatar.value,portada_url:portada.value}) })
    if (actual === version) { if(usuario.value?.id===perfil.value.id) {usuario.value={...usuario.value,avatar_url:avatar.value};localStorage.setItem('usuario',JSON.stringify(usuario.value))};await router.replace({path:route.path,query:{tab:tab.value}});await cargar();aviso.value='Perfil actualizado.' }
  } catch (e) { if (actual === version) aviso.value = e.message }
  finally { if (actual === version) ocupado.value = false }
}
async function seguir() {
  if (ocupado.value || propio.value || !exigirSesion('Inicia sesión para seguir usuarios.')) return
  const actual = version, id = perfil.value.id
  ocupado.value = true; aviso.value = ''
  try {
    await apiFetch('usuarios', `/usuarios/${id}/seguir`, { method:'PUT', body:JSON.stringify({seguir:!perfil.value.siguiendo}) })
    if (actual === version) await cargar()
  } catch (e) { if (actual === version) aviso.value = e.message }
  finally { if (actual === version) ocupado.value = false }
}
watch([() => route.params.id, () => usuario.value?.id], cargar, { immediate:true,flush:'sync' })
watch([tab,tipoVoto],()=>{if(perfil.value&&!cargando.value)reiniciarActividad()},{flush:'sync'})
watch(()=>route.query.editar,abrirEdicion)
onUnmounted(()=>{version++;versionActividad++})
</script>
<template>
  <main class="pagina foro-contenido pagina-perfil">
    <router-link to="/" class="btn-texto enlace-volver">Volver al inicio</router-link>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <p v-else-if="cargando && !perfil" class="foro-estado">Cargando perfil…</p>
    <template v-if="perfil">
      <header class="perfil-cabecera"><div class="perfil-identidad"><AvatarUsuario :nombre="perfil.nombre_apellido" :url="perfil.avatar_url"/><div><h1>{{perfil.nombre_apellido}}</h1><p class="tarjeta-meta">@{{perfil.id}} · {{perfil.rol}}</p></div></div><nav class="perfil-tabs" aria-label="Secciones del perfil"><router-link v-for="t in tabs" :key="t.id" :to="{path:route.path,query:{tab:t.id}}" :class="{'chip-activo':tab===t.id}" :aria-current="tab===t.id?'page':undefined">{{t.n}}</router-link></nav></header>
      <div class="perfil-rejilla"><aside class="perfil-lateral">
      <article class="tarjeta-pregunta perfil-ficha">
        <div class="perfil-portada" :class="{'sin-portada':!perfil.portada_url||falloPortada}"><img v-if="perfil.portada_url&&!falloPortada" :src="perfil.portada_url" alt="Portada del perfil" referrerpolicy="no-referrer" @error="falloPortada=true" /></div>
        <div class="perfil-identidad"><AvatarUsuario :nombre="perfil.nombre_apellido" :url="perfil.avatar_url" /><div><h1>{{ perfil.nombre_apellido }}</h1><span class="insignia">{{ perfil.rol }}</span></div></div>
        <p class="tarjeta-meta">Mención: @{{ perfil.id }}</p>
        <p class="lectura-contenido">{{ perfil.biografia || 'Sin biografía.' }}</p>
        <p class="tarjeta-meta">Miembro desde {{ formatearFecha(perfil.fecha_registro) }}</p>
        <dl class="perfil-metricas" aria-label="Estadísticas del perfil">
          <div v-for="m in [{n:'Karma',v:perfil.karma},{n:'Publicaciones',v:perfil.publicaciones},{n:'Respuestas',v:perfil.respuestas},{n:'Contribuciones',v:perfil.publicaciones+perfil.respuestas+(perfil.comentarios||0)},{n:'Soluciones',v:perfil.soluciones},{n:'Seguidores',v:perfil.seguidores},{n:'Seguidos',v:perfil.seguidos},{n:'Comunidades',v:perfil.comunidades}]" :key="m.n"><dt>{{ m.n }}</dt><dd>{{ m.v }}</dd></div>
        </dl>
        <div class="tarjeta-acciones perfil-acciones-principales">
          <button type="button" class="btn-secundario" @click="compartirPerfil">Compartir perfil</button>
          <button v-if="propio" type="button" class="btn-secundario" :disabled="ocupado" @click="editando = !editando">{{ editando ? 'Cerrar edición' : 'Editar perfil' }}</button>
          <button v-else-if="!perfil.bloqueo_mutuo" type="button" class="btn-secundario" :disabled="ocupado" :aria-pressed="perfil.siguiendo" @click="seguir">{{ perfil.siguiendo ? 'Dejar de seguir' : 'Seguir usuario' }}</button>
          <router-link v-if="usuario && !propio && !perfil.bloqueo_mutuo" :to="`/mensajes/${perfil.id}`" class="btn-secundario">Enviar mensaje</router-link>
          <button v-if="!propio && (!perfil.bloqueo_mutuo || perfil.bloqueado)" type="button" class="btn-texto" :disabled="ocupado" @click="bloquear">{{perfil.bloqueado ? 'Desbloquear' : 'Bloquear usuario'}}</button>
        </div><details v-if="propio" class="perfil-opciones"><summary>Más opciones</summary><div class="perfil-opciones-lista"><button v-if="!verBloqueados" type="button" class="btn-texto" @click="cargarBloqueados">Usuarios bloqueados</button>
          <button v-if="propio && !verSeguidos" type="button" class="btn-texto" @click="cargarSeguidos">Usuarios que sigo</button>
          <router-link v-if="propio" :to="{path:'/',query:{comunidades:'seguidas'}}" class="btn-texto">Mis categorías seguidas</router-link><router-link v-if="propio" to="/comunidades?mias=1" class="btn-texto">Mis comunidades</router-link><router-link :to="{path:route.path,query:{tab:'configuracion'}}" class="btn-texto">Configuración</router-link></div></details>
        <p v-if="enlacePerfil" role="status" class="lectura-contenido">{{enlacePerfil}}</p>
        <ReportarContenido v-if="!propio" tipo="usuario" :identificador="perfil.id" :autor="perfil.id" />
        <form v-if="editando && propio" class="foro-formulario" @submit.prevent="guardar">
          <label>Biografía<textarea v-model="biografia" maxlength="500" rows="3"></textarea></label>
          <label>Avatar (URL HTTPS, vacío para quitarlo)<input ref="editorAvatar" v-model="avatar" type="url" maxlength="2048" /></label>
          <label>Portada (URL HTTPS)<input v-model="portada" type="url" maxlength="2048" /></label>
          <button type="submit" class="btn-primario btn-ancho-auto" :disabled="ocupado">Guardar perfil</button>
        </form>
        <p v-if="perfil.bloqueo_mutuo">Perfil restringido por bloqueo.</p>
        <p v-if="aviso" class="foro-estado" role="status">{{ aviso }}</p>
      </article>
      <section class="panel-lateral">
        <h2>Reconocimientos académicos</h2>
        <div v-if="perfil.insignias.length" class="tarjeta-acciones"><span v-for="i in perfil.insignias" :key="i" class="insignia">{{ i }}</span></div>
        <p v-else class="foro-vacio">Aún no tiene insignias.</p>
      </section>
      <section v-if="propio && verSeguidos" class="panel-lateral">
        <h2>Usuarios que sigo</h2>
        <ul class="ranking"><li v-for="p in seguidos" :key="p.id"><AvatarUsuario :nombre="p.nombre_apellido" :url="p.avatar_url" chico /><router-link :to="`/usuarios/${p.id}`">{{ p.nombre_apellido }}</router-link></li></ul>
        <p v-if="errorSeguidos" class="error" role="alert">{{ errorSeguidos }}</p>
        <p v-else-if="!seguidos.length && !cargandoSeguidos">No sigues usuarios todavía.</p>
        <button v-if="hayMasSeguidos || errorSeguidos" type="button" class="btn-texto" :disabled="cargandoSeguidos" @click="cargarSeguidos">{{ errorSeguidos ? 'Reintentar' : 'Cargar más' }}</button>
      </section>
      <section v-if="propio && verBloqueados" class="panel-lateral">
        <h2>Usuarios bloqueados</h2><ul class="ranking"><li v-for="u in bloqueados" :key="u.id"><router-link :to="`/usuarios/${u.id}`">{{u.nombre_apellido}} (gestionar bloqueo)</router-link></li></ul>
        <p v-if="errorBloqueados" class="error">{{errorBloqueados}}</p><p v-else-if="!bloqueados.length && !cargandoBloqueados">No tienes usuarios bloqueados.</p>
        <button v-if="masBloqueados || errorBloqueados" type="button" class="btn-texto" :disabled="cargandoBloqueados" @click="cargarBloqueados">Cargar más</button>
      </section>
      </aside><div class="perfil-actividad">
      <section v-if="propio&&tab==='configuracion'" class="panel-lateral"><h2>Configuración del perfil</h2><button class="btn-secundario" @click="editando=true">Editar datos públicos</button><p>Gestiona tus seguimientos y bloqueos desde el panel del perfil.</p><button class="btn-texto" @click="limpiarHistorial">Borrar historial privado</button><GestionAlmacenamiento :key="perfil.id"/></section>
      <section v-else-if="propio&&tab==='logros'" class="panel-lateral"><h2>Mis logros</h2><p v-if="!perfil.insignias.length">Aún no tienes reconocimientos.</p><p v-for="i in perfil.insignias" :key="i" class="insignia">{{i}}</p></section>
      <section v-else-if="!perfil.bloqueo_mutuo" class="bloque-respuestas" :key="tab">
        <h2>{{tabs.find(t=>t.id===tab)?.n || 'Actividad'}}</h2><label v-if="['positivos','negativos'].includes(tab)" class="perfil-filtro-votos">Contenido votado<select v-model="tipoVoto"><option value="publicacion">Publicaciones</option><option value="respuesta">Respuestas</option></select></label><p v-if="listaPrivada" class="nota-demo">Solo tú puedes ver esta sección. </p><button v-if="tab==='historial'" class="btn-texto" @click="limpiarHistorial">Borrar historial</button>
        <p v-if="cargandoActividad" class="foro-estado">Cargando actividad…</p>
        <p v-else-if="!actividad.length && !errorActividad" class="foro-vacio">No hay contenido en esta sección.</p>
        <ul class="foro-lista"><li v-for="a in actividad" :key="`${a.tipo}-${a.id}`" class="tarjeta-pregunta">
          <span class="insignia">{{ a.tipo==='publicacion'?'Publicación':a.tipo==='respuesta'?'Respuesta':'Comentario' }}</span>
          <h2><router-link :to="{path:`/preguntas/${a.id_pregunta}`,hash:a.tipo==='respuesta'?`#respuesta-${a.id}`:a.tipo==='comentario'?`#comentario-${a.id}`:''}">{{ a.tipo==='publicacion'?a.titulo:`En: ${a.titulo}` }}</router-link></h2>
          <p class="tarjeta-extracto">{{ a.extracto }}</p><MultimediaPublicacion v-if="a.tipo==='publicacion'&&['multimedia','video'].includes(a.tipo_publicacion)" :id="a.id_pregunta"/><time class="tarjeta-meta">{{ formatearFecha(a.fecha_creacion) }}</time>
        </li></ul>
        <p v-if="errorActividad" class="error" role="alert">{{ errorActividad }}</p>
        <button v-if="hayMas || errorActividad" type="button" class="btn-texto" :disabled="cargandoActividad" @click="cargarActividad">{{ errorActividad ? 'Reintentar' : 'Cargar más actividad' }}</button>
      </section></div></div>
    </template>
  </main>
</template>
