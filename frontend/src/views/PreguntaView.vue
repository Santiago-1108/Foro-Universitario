<script setup>
import { nextTick, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { apiFetch } from '../services/api.js'
import { exigirSesion, pedirSesion } from '../services/sesion.js'
import { formatearFecha, iniciales } from '../utils/formato.js'

const route = useRoute()

const cargando = ref(false)
const error = ref('')
const pregunta = ref(null)
const respuestas = ref([])
const opinion = ref('')
const errorOpinion = ref('')
const enviandoOpinion = ref(false)

async function cargar() {
  cargando.value = true
  error.value = ''
  pregunta.value = null
  respuestas.value = []
  try {
    const id = route.params.id
    const [datosPregunta, lista, votos] = await Promise.all([
      apiFetch('foro', `/preguntas/${id}`),
      apiFetch('interacciones', `/respuestas/pregunta/${id}`),
      apiFetch('interacciones', `/votos/pregunta/${id}`).catch(() => ({ total_votos: null })),
    ])
    pregunta.value = { ...datosPregunta, total_votos: votos.total_votos, aviso: '' }
    respuestas.value = await Promise.all(
      lista.map(async (respuesta) => {
        const [votosRespuesta, comentarios] = await Promise.all([
          apiFetch('interacciones', `/votos/respuesta/${respuesta.id}`).catch(() => ({ total_votos: null })),
          apiFetch('interacciones', `/comentarios/respuesta/${respuesta.id}`).catch(() => []),
        ])
        return {
          ...respuesta,
          total_votos: votosRespuesta.total_votos,
          comentarios,
          comentarioNuevo: '',
          mostrarComentario: false,
          aviso: '',
          enviando: false,
        }
      }),
    )
  } catch (e) {
    error.value = e.message
  } finally {
    cargando.value = false
  }

  if (route.hash === '#opinar') {
    await nextTick()
    document.getElementById('opinar')?.scrollIntoView()
  }
}

async function votarPregunta() {
  if (!pregunta.value || !exigirSesion('Inicia sesión para votar.')) return
  pregunta.value.aviso = ''
  try {
    await apiFetch('interacciones', '/votos', {
      method: 'POST',
      body: JSON.stringify({ voto: 1, id_pregunta: pregunta.value.id }),
    })
    const votos = await apiFetch('interacciones', `/votos/pregunta/${pregunta.value.id}`)
    pregunta.value.total_votos = votos.total_votos
  } catch (e) {
    if (e.status === 401) pedirSesion('Tu sesión expiró. Inicia sesión para votar.')
    else pregunta.value.aviso = e.message
  }
}

async function votarRespuesta(respuesta) {
  if (!exigirSesion('Inicia sesión para votar.')) return
  respuesta.aviso = ''
  try {
    await apiFetch('interacciones', '/votos', {
      method: 'POST',
      body: JSON.stringify({ voto: 1, id_respuesta: respuesta.id }),
    })
    const votos = await apiFetch('interacciones', `/votos/respuesta/${respuesta.id}`)
    respuesta.total_votos = votos.total_votos
  } catch (e) {
    if (e.status === 401) pedirSesion('Tu sesión expiró. Inicia sesión para votar.')
    else respuesta.aviso = e.message
  }
}

function abrirComentario(respuesta) {
  if (!exigirSesion('Inicia sesión para comentar.')) return
  respuesta.mostrarComentario = true
  respuesta.aviso = ''
}

async function publicarOpinion() {
  if (!pregunta.value || !exigirSesion('Inicia sesión para compartir tu opinión.')) return
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
  if (!exigirSesion('Inicia sesión para comentar.')) return
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

watch(() => route.params.id, cargar, { immediate: true })
</script>

<template>
  <main class="pagina pagina-lectura">
    <router-link to="/" class="btn-texto enlace-volver">Volver al inicio</router-link>

    <p v-if="cargando" class="foro-estado">Cargando…</p>
    <p v-else-if="error" class="error foro-estado" role="alert">{{ error }}</p>

    <template v-else-if="pregunta">
      <article class="tarjeta-pregunta">
        <span class="insignia">{{ pregunta.nombre_categoria }}</span>
        <h1>{{ pregunta.titulo }}</h1>
        <p class="lectura-contenido">{{ pregunta.contenido }}</p>
        <p class="tarjeta-meta">
          <span class="avatar avatar-chico" aria-hidden="true">{{ iniciales(pregunta.nombre_autor) }}</span>
          <span>{{ pregunta.nombre_autor }}</span>
          <span aria-hidden="true">·</span>
          <time :datetime="pregunta.fecha_creacion">{{ formatearFecha(pregunta.fecha_creacion) }}</time>
        </p>
        <div class="tarjeta-acciones">
          <button type="button" class="btn-voto" @click="votarPregunta">
            Votar
            <span v-if="pregunta.total_votos != null">{{ pregunta.total_votos }}</span>
          </button>
        </div>
        <p v-if="pregunta.aviso" class="error aviso-tarjeta" role="alert">{{ pregunta.aviso }}</p>
      </article>

      <section class="bloque-respuestas" aria-label="Respuestas">
        <h2>{{ respuestas.length === 1 ? '1 respuesta' : `${respuestas.length} respuestas` }}</h2>
        <p v-if="respuestas.length === 0" class="foro-vacio">Todavía no hay respuestas. La pregunta se puede leer igual.</p>

        <article v-for="respuesta in respuestas" :key="respuesta.id" class="tarjeta-pregunta">
          <p class="lectura-contenido">{{ respuesta.contenido }}</p>
          <p class="tarjeta-meta">
            <span class="avatar avatar-chico" aria-hidden="true">{{ iniciales(respuesta.nombre_autor) }}</span>
            <span>{{ respuesta.nombre_autor }}</span>
            <span aria-hidden="true">·</span>
            <time :datetime="respuesta.fecha_creacion">{{ formatearFecha(respuesta.fecha_creacion) }}</time>
          </p>
          <div class="tarjeta-acciones">
            <button type="button" class="btn-voto" @click="votarRespuesta(respuesta)">
              Votar
              <span v-if="respuesta.total_votos != null">{{ respuesta.total_votos }}</span>
            </button>
            <button type="button" class="btn-texto" @click="abrirComentario(respuesta)">Comentar</button>
          </div>
          <p v-if="respuesta.aviso" class="error aviso-tarjeta" role="alert">{{ respuesta.aviso }}</p>

          <ul v-if="respuesta.comentarios.length" class="lista-comentarios">
            <li v-for="comentario in respuesta.comentarios" :key="comentario.id">
              <p>{{ comentario.contenido }}</p>
              <p class="tarjeta-meta">
                <span>{{ comentario.nombre_autor }}</span>
                <span aria-hidden="true">·</span>
                <time :datetime="comentario.fecha_creacion">{{ formatearFecha(comentario.fecha_creacion) }}</time>
              </p>
            </li>
          </ul>

          <form v-if="respuesta.mostrarComentario" class="form-comentario" @submit.prevent="publicarComentario(respuesta)">
            <label>
              Comentario
              <textarea v-model="respuesta.comentarioNuevo" rows="2"></textarea>
            </label>
            <button type="submit" class="btn-primario btn-ancho-auto" :disabled="respuesta.enviando">
              {{ respuesta.enviando ? 'Publicando…' : 'Publicar comentario' }}
            </button>
          </form>
        </article>
      </section>

      <section id="opinar" class="foro-formulario" aria-label="Compartir tu opinión">
        <h2>Compartir tu opinión</h2>
        <form @submit.prevent="publicarOpinion">
          <label>
            Respuesta
            <textarea v-model="opinion" rows="4"></textarea>
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
