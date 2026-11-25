<script setup>
import MultimediaPublicacion from '../components/MultimediaPublicacion.vue'
import ReportarContenido from '../components/ReportarContenido.vue'
import AvatarUsuario from '../components/AvatarUsuario.vue'
import { nextTick, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { apiFetch } from '../services/api.js'
import { exigirSesion, pedirSesion, usuario } from '../services/sesion.js'
import HiloComentario from '../components/HiloComentario.vue'
import { formatearFecha } from '../utils/formato.js'

const route = useRoute()
const router = useRouter()

const cargando = ref(false)
const error = ref('')
const pregunta = ref(null)
const respuestas = ref([])
const opinion = ref('')
const errorOpinion = ref('')
const enviandoOpinion = ref(false)
const encuesta = ref(null)
const editando = ref(false)
const edicion = ref({})
const ocupado = ref(false)
const avisoCompartir = ref(''), errorHistorial=ref('')
function puedeEditar(p) { return usuario.value && (usuario.value.id === p.id_usuario || usuario.value.rol === 'admin') }
function iniciarEdicion() {
  edicion.value = {titulo: pregunta.value.titulo, contenido: pregunta.value.contenido, recurso_url: pregunta.value.recurso_url || '', etiqueta: pregunta.value.etiqueta || ''}
  editando.value = true
}
async function modificar(accion) {
  if (ocupado.value || !exigirSesion('Inicia sesión.')) return
  if (accion === 'DELETE' && !window.confirm('¿Eliminar esta publicación?')) return
  ocupado.value = true; pregunta.value.aviso = ''
  try {
    await apiFetch('foro', `/preguntas/${pregunta.value.id}`, {method: accion, ...(accion === 'PUT' ? {body: JSON.stringify(edicion.value)} : {})})
    if (accion === 'DELETE') { await router.push('/'); return }
    editando.value = false; await cargar()
  } catch(e) { if (pregunta.value) pregunta.value.aviso = e.message }
  finally { ocupado.value = false }
}
async function votarEncuesta(opcion) {
  if (ocupado.value || !exigirSesion('Inicia sesión para votar en la encuesta.')) return
  ocupado.value = true; pregunta.value.aviso = ''
  try { encuesta.value = await apiFetch('foro', `/preguntas/${pregunta.value.id}/encuesta`, {method:'PUT',body:JSON.stringify({opcion})}) }
  catch(e) { if (pregunta.value) pregunta.value.aviso = e.message }
  finally { ocupado.value = false }
}
async function aceptarRespuesta(r) {
  if (ocupado.value || !exigirSesion('Inicia sesión.')) return
  ocupado.value = true; pregunta.value.aviso = ''
  try {
    const datos = await apiFetch('foro', `/preguntas/${pregunta.value.id}/aceptar`, {method:'PUT',body:JSON.stringify({id_respuesta: pregunta.value.id_respuesta_aceptada === r.id ? null : r.id})})
    pregunta.value.id_respuesta_aceptada = datos.id_respuesta_aceptada
  } catch(e) { if (pregunta.value) pregunta.value.aviso = e.message }
  finally { ocupado.value = false }
}
async function preferencia(accion) {
  if (ocupado.value || !exigirSesion('Inicia sesión para gestionar tus publicaciones.')) return
  const p = pregunta.value, campo = accion === 'guardar' ? 'guardada' : 'oculta'
  ocupado.value = true; p.aviso = ''
  try { const r = await apiFetch('foro', `/preguntas/${p.id}/${accion}`, {method:'PUT',body:JSON.stringify({activo:!p[campo]})}); p[campo] = r.activo }
  catch(e) { p.aviso = e.message } finally { ocupado.value = false }
}
async function compartir() {
  const enlace = new URL(`/preguntas/${pregunta.value.id}`, window.location.origin).href
  try { await navigator.clipboard.writeText(enlace); avisoCompartir.value = 'Enlace copiado' }
  catch { avisoCompartir.value = enlace }
}
function arbol(comentarios) {
  const mapa = new Map(comentarios.map(c => [c.id, {...c, hijos: []}]))
  const raices = []
  for (const c of mapa.values()) {
    const padre = mapa.get(c.id_comentario_padre)
    if (padre && padre.id !== c.id) padre.hijos.push(c); else raices.push(c)
  }
  return raices
}


let versionCarga = 0
async function cargar() {
  const version = ++versionCarga
  cargando.value = true
  error.value = ''
  pregunta.value = null
  encuesta.value = null
  editando.value = false
  avisoCompartir.value = '';errorHistorial.value=''
  respuestas.value = []
  try {
    const id = route.params.id
    const [datosPregunta, lista, votos] = await Promise.all([
      apiFetch('foro', `/preguntas/${id}`),
      apiFetch('interacciones', `/respuestas/pregunta/${id}`),
      apiFetch('interacciones', `/votos/pregunta/${id}`),
    ])
    if (version !== versionCarga) return
    pregunta.value = { ...datosPregunta, total_votos: votos.total_votos, mi_voto: votos.mi_voto, aviso: '' }
    if(route.query.editar==='1'&&puedeEditar(pregunta.value)) iniciarEdicion()
    const datosEncuesta = datosPregunta.tipo === 'encuesta' ? await apiFetch('foro', `/preguntas/${id}/encuesta`) : null
    const detalle = await Promise.all(
      lista.map(async (respuesta) => {
        const [votosRespuesta, comentarios] = await Promise.all([
          apiFetch('interacciones', `/votos/respuesta/${respuesta.id}`),
          apiFetch('interacciones', `/comentarios/respuesta/${respuesta.id}`),
        ])
        return {
          ...respuesta,
          total_votos: votosRespuesta.total_votos,
          mi_voto: votosRespuesta.mi_voto,
          comentarios,
          comentarioNuevo: '',
          mostrarComentario: false,
          aviso: '',
          enviando: false,
        }
      }),
    )
    if (version !== versionCarga) return
    encuesta.value = datosEncuesta
    respuestas.value = detalle
    if(usuario.value) apiFetch('foro',`/preguntas/${id}/visita`,{method:'POST',body:'{}'}).catch(e=>{if(version===versionCarga&&e.name!=='AbortError')errorHistorial.value='No se pudo registrar esta visita en tu historial.'})
  } catch (e) {
    if (version === versionCarga) error.value = e.message
  } finally {
    if (version === versionCarga) cargando.value = false
  }
  if (version !== versionCarga) return

  if (/^#(?:opinar|respuesta-\d+|comentario-\d+)$/.test(route.hash)) {
    await nextTick()
    document.getElementById(route.hash.slice(1))?.scrollIntoView()
  }
}

async function votar(objeto, signo, tipo) {
  if (objeto.votando || !exigirSesion('Inicia sesión para votar.')) return
  objeto.votando = true; objeto.aviso = ''
  try {
    const votos = await apiFetch('interacciones', '/votos', {method:'POST',body:JSON.stringify({voto: objeto.mi_voto === signo ? 0 : signo, [`id_${tipo}`]: objeto.id})})
    objeto.total_votos = votos.total_votos; objeto.mi_voto = votos.voto
  } catch(e) { objeto.aviso = e.message }
  finally { objeto.votando = false }
}

function abrirComentario(respuesta) {
  if (!exigirSesion('Inicia sesión para comentar.')) return
  respuesta.mostrarComentario = true
  respuesta.aviso = ''
}

async function publicarOpinion() {
  if (enviandoOpinion.value || !pregunta.value || !exigirSesion('Inicia sesión para compartir tu opinión.')) return
  errorOpinion.value = ''
  const contenido = opinion.value.trim()
  if (!contenido) {
    errorOpinion.value = 'Escribe tu opinión antes de publicarla.'
    return
  }
  enviandoOpinion.value = true
  try {
    await apiFetch('interacciones', '/respuestas', {
      method: 'POST',
      body: JSON.stringify({ id_pregunta: pregunta.value.id, contenido }),
    })
    opinion.value = ''
    await cargar()
  } catch (e) {
    if (e.status === 401) pedirSesion('Tu sesión expiró. Inicia sesión para participar.')
    else errorOpinion.value = e.message
  } finally {
    enviandoOpinion.value = false
  }
}

async function publicarComentario(respuesta) {
  if (respuesta.enviando || !exigirSesion('Inicia sesión para comentar.')) return
  const contenido = respuesta.comentarioNuevo.trim()
  if (!contenido) {
    respuesta.aviso = 'Escribe un comentario antes de publicarlo.'
    return
  }
  respuesta.enviando = true
  respuesta.aviso = ''
  try {
    const creado = await apiFetch('interacciones', '/comentarios', {
      method: 'POST',
      body: JSON.stringify({ id_respuesta: respuesta.id, contenido }),
    })
    respuesta.comentarios.push(creado)
    respuesta.comentarioNuevo = ''
    respuesta.mostrarComentario = false
  } catch (e) {
    if (e.status === 401) pedirSesion('Tu sesión expiró. Inicia sesión para comentar.')
    else respuesta.aviso = e.message
  } finally {
    respuesta.enviando = false
  }
}

watch([() => route.params.id, () => usuario.value?.id], cargar, { immediate: true })
watch(()=>route.hash,async()=>{await nextTick();if(/^#(?:opinar|respuesta-\d+|comentario-\d+)$/.test(route.hash))document.getElementById(route.hash.slice(1))?.scrollIntoView()})
</script>

<template>
  <main class="pagina pagina-lectura pagina-pregunta">
    <router-link to="/" class="btn-texto enlace-volver">Volver al inicio</router-link>

    <p v-if="cargando" class="foro-estado">Cargando…</p>
    <p v-else-if="error" class="error foro-estado" role="alert">{{ error }}</p>

    <template v-else-if="pregunta">
      <p v-if="errorHistorial" class="nota-demo" role="status">{{errorHistorial}}</p>
      <article class="tarjeta-pregunta">
        <router-link class="insignia" :to="{path:'/',query:{categoria:String(pregunta.id_categoria)}}">{{ pregunta.nombre_categoria }}</router-link>
        <h1>{{ pregunta.titulo }}</h1>
        <p class="lectura-contenido">{{ pregunta.contenido }}</p>
        <span v-if="pregunta.etiqueta" class="insignia">{{pregunta.etiqueta}}</span>
        <span v-if="pregunta.fijada" class="insignia">Fijada</span>
        <p v-if="pregunta.cerrada" class="tarjeta-meta">Conversación cerrada por moderación. No admite nuevas respuestas ni comentarios.</p>
        <p v-if="pregunta.fecha_edicion" class="tarjeta-meta">Editada</p>
        <span v-if="pregunta.id_respuesta_aceptada" class="insignia">Pregunta resuelta</span>
        <p v-if="pregunta.tipo === 'enlace'"><a :href="pregunta.recurso_url" target="_blank" rel="noopener noreferrer">Abrir enlace compartido</a></p>
        <MultimediaPublicacion v-if="['multimedia','video'].includes(pregunta.tipo)" :id="pregunta.id"/>
        <img v-if="pregunta.tipo === 'imagen'" :src="pregunta.recurso_url" alt="Imagen compartida por el autor" referrerpolicy="no-referrer" loading="lazy" style="max-width:100%;height:auto" />
        <section v-if="encuesta" class="foro-formulario encuesta-panel" aria-label="Encuesta">
          <h2>Encuesta</h2>
          <div v-for="(op, i) in encuesta.opciones" :key="i" class="encuesta-opcion">
            <button type="button" :class="encuesta.mi_opcion === i ? 'chip chip-activo' : 'btn-voto'" :aria-pressed="encuesta.mi_opcion === i" :disabled="ocupado" @click="votarEncuesta(i)">{{ op.texto }}</button>
            <span>{{ op.votos }} votos</span>
            <div class="encuesta-pista" aria-hidden="true"><div :style="{width: (100 * op.votos / (encuesta.opciones.reduce((total,o)=>total + Number(o.votos),0) || 1)) + '%'}"></div></div>
          </div>
          <button v-if="encuesta.mi_opcion !== null" type="button" class="btn-texto" :disabled="ocupado" @click="votarEncuesta(null)">Retirar voto</button>
        </section>
        <form v-if="editando" class="foro-formulario" @submit.prevent="modificar('PUT')">
          <label>Etiqueta<select v-model="edicion.etiqueta"><option value="">Sin etiqueta</option><option v-for="e in ['duda','debate','recurso','anuncio','proyecto']" :key="e" :value="e">{{e}}</option></select></label>
          <label>Título<input v-model="edicion.titulo" maxlength="200" required /></label>
          <label>Contenido<textarea v-model="edicion.contenido" maxlength="2000" required /></label>
          <label v-if="pregunta.tipo === 'enlace' || pregunta.tipo === 'imagen'">URL HTTPS<input v-model="edicion.recurso_url" type="url" required /></label>
          <button type="submit" class="btn-primario btn-ancho-auto" :disabled="ocupado">Guardar cambios</button>
          <button type="button" class="btn-texto" :disabled="ocupado" @click="editando = false">Cancelar</button>
        </form>
        <p class="tarjeta-meta">
          <AvatarUsuario :nombre="pregunta.nombre_autor" :url="pregunta.avatar_autor" chico />
          <router-link :to="`/usuarios/${pregunta.id_usuario}`">{{ pregunta.nombre_autor }}</router-link>
          <span aria-hidden="true">·</span>
          <time :datetime="pregunta.fecha_creacion">{{ formatearFecha(pregunta.fecha_creacion) }}</time>
        </p>
        <div class="tarjeta-acciones">
          <button type="button" :class="pregunta.mi_voto === 1 ? 'chip chip-activo' : 'btn-voto'" :aria-pressed="pregunta.mi_voto === 1" :disabled="pregunta.votando" @click="votar(pregunta,1,'pregunta')" aria-label="Voto positivo">↑</button>
          <span class="voto-puntos" :aria-label="`${pregunta.total_votos} puntos`">{{ pregunta.total_votos }}</span>
          <button type="button" :class="pregunta.mi_voto === -1 ? 'chip chip-activo' : 'btn-voto'" :aria-pressed="pregunta.mi_voto === -1" :disabled="pregunta.votando" @click="votar(pregunta,-1,'pregunta')" aria-label="Voto negativo">↓</button>
          <button type="button" class="btn-texto" :aria-pressed="!!pregunta.guardada" :disabled="ocupado" @click="preferencia('guardar')">{{pregunta.guardada ? 'Quitar de guardadas' : 'Guardar'}}</button>
          <button type="button" class="btn-texto" :aria-pressed="!!pregunta.oculta" :disabled="ocupado" @click="preferencia('ocultar')">{{pregunta.oculta ? 'Mostrar de nuevo' : 'Ocultar'}}</button>
          <button type="button" class="btn-texto" @click="compartir">Compartir</button>
          <button v-if="puedeEditar(pregunta)" type="button" class="btn-texto" :disabled="ocupado" @click="iniciarEdicion">Editar</button>
          <button v-if="puedeEditar(pregunta)" type="button" class="btn-texto btn-peligro" :disabled="ocupado" @click="modificar('DELETE')">Eliminar</button>
        </div>
        <ReportarContenido tipo="pregunta" :identificador="pregunta.id" :autor="pregunta.id_usuario" />
        <p v-if="avisoCompartir" role="status">{{ avisoCompartir }}</p>
        <p v-if="pregunta.aviso" class="error aviso-tarjeta" role="alert">{{ pregunta.aviso }}</p>
      </article>

      <section class="bloque-respuestas" aria-label="Respuestas">
        <h2>{{ respuestas.length === 1 ? '1 respuesta' : `${respuestas.length} respuestas` }}</h2>
        <p v-if="respuestas.length === 0" class="foro-vacio">Todavía no hay respuestas. La pregunta se puede leer igual.</p>

        <article v-for="respuesta in respuestas" :key="respuesta.id" :id="`respuesta-${respuesta.id}`" class="tarjeta-pregunta respuesta-tarjeta" :class="{'respuesta-aceptada':pregunta.id_respuesta_aceptada === respuesta.id}">
          <p class="lectura-contenido">{{ respuesta.contenido }}</p>
          <p class="tarjeta-meta">
            <AvatarUsuario :nombre="respuesta.nombre_autor" :url="respuesta.avatar_autor" chico />
            <router-link :to="`/usuarios/${respuesta.id_usuario}`">{{ respuesta.nombre_autor }}</router-link>
            <span aria-hidden="true">·</span>
            <time :datetime="respuesta.fecha_creacion">{{ formatearFecha(respuesta.fecha_creacion) }}</time>
          </p>
          <div class="tarjeta-acciones">
            <button type="button" :class="respuesta.mi_voto === 1 ? 'chip chip-activo' : 'btn-voto'" :aria-pressed="respuesta.mi_voto === 1" :disabled="respuesta.votando" @click="votar(respuesta,1,'respuesta')" aria-label="Voto positivo">↑</button>
            <span class="voto-puntos" :aria-label="`${respuesta.total_votos} puntos`">{{ respuesta.total_votos }}</span>
            <button type="button" :class="respuesta.mi_voto === -1 ? 'chip chip-activo' : 'btn-voto'" :aria-pressed="respuesta.mi_voto === -1" :disabled="respuesta.votando" @click="votar(respuesta,-1,'respuesta')" aria-label="Voto negativo">↓</button>
            <span v-if="pregunta.id_respuesta_aceptada === respuesta.id" class="insignia">Respuesta aceptada</span>
            <button v-if="puedeEditar(pregunta)" type="button" class="btn-texto" :disabled="ocupado" @click="aceptarRespuesta(respuesta)">{{ pregunta.id_respuesta_aceptada === respuesta.id ? 'Desmarcar solución' : 'Aceptar respuesta' }}</button>
            <button v-if="!pregunta.cerrada" type="button" class="btn-texto" @click="abrirComentario(respuesta)">Comentar</button>
          </div>
          <ReportarContenido tipo="respuesta" :identificador="respuesta.id" :autor="respuesta.id_usuario" />
          <p v-if="respuesta.aviso" class="error aviso-tarjeta" role="alert">{{ respuesta.aviso }}</p>

          <ul v-if="respuesta.comentarios.length" class="lista-comentarios">
            <HiloComentario v-for="comentario in arbol(respuesta.comentarios)" :key="comentario.id" :comentario="comentario" :cerrada="pregunta.cerrada" @creado="respuesta.comentarios.push($event)" />
          </ul>

          <form v-if="respuesta.mostrarComentario && !pregunta.cerrada" class="form-comentario" @submit.prevent="publicarComentario(respuesta)">
            <label>
              Comentario
              <textarea v-model="respuesta.comentarioNuevo" rows="2" maxlength="2000"></textarea><small>Para mencionar a alguien, escribe @ seguido del ID de su perfil (ej. @23).</small>
            </label>
            <button type="submit" class="btn-primario btn-ancho-auto" :disabled="respuesta.enviando">
              {{ respuesta.enviando ? 'Publicando…' : 'Publicar comentario' }}
            </button>
          </form>
        </article>
      </section>

      <section v-if="!pregunta.cerrada" id="opinar" class="foro-formulario" aria-label="Compartir tu opinión">
        <h2>Compartir tu opinión</h2>
        <form @submit.prevent="publicarOpinion">
          <label>
            Respuesta
            <textarea v-model="opinion" rows="4" maxlength="2000"></textarea><small>Para mencionar a alguien, escribe @ seguido del ID de su perfil (ej. @23).</small>
          </label>
          <div class="acciones-form">
            <p v-if="errorOpinion" class="error" role="alert">{{ errorOpinion }}</p>
            <button type="submit" class="btn-primario btn-ancho-auto" :disabled="enviandoOpinion">
              {{ enviandoOpinion ? 'Publicando…' : 'Publicar respuesta' }}
            </button>
          </div>
        </form>
      </section>
    </template>
  </main>
</template>
