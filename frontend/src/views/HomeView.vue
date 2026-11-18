<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { RANKING_DEMO } from '../datos/demostracion.js'
import { apiFetch } from '../services/api.js'
import {
  autenticado,
  exigirSesion,
  limiteContenido,
  pedirSesion,
  plan,
  usuario,
} from '../services/sesion.js'
import { formatearFecha, iniciales, textoRespuestas } from '../utils/formato.js'

const router = useRouter()

const categorias = ref([])
const preguntas = ref([])
const filtroCategoria = ref('')
const cargando = ref(false)
const errorLista = ref('')

const idCategoriaNueva = ref('')
const tituloNuevo = ref('')
const contenidoNuevo = ref('')
const errorFormulario = ref('')
const enviando = ref(false)
const mostrarFormulario = ref(false)
const mensajeExito = ref('')
const idNuevo = ref(null)

function elegirCategoria(id) {
  filtroCategoria.value = id
  cargarPreguntas()
}

function abrirFormulario() {
  if (!exigirSesion('Inicia sesión para publicar tu pregunta.')) return
  mostrarFormulario.value = true
  errorFormulario.value = ''
}

function cancelarFormulario() {
  mostrarFormulario.value = false
  errorFormulario.value = ''
}

function participar(pregunta) {
  if (!exigirSesion('Inicia sesión para participar.')) return
  router.push({ path: `/preguntas/${pregunta.id}`, hash: '#opinar' })
}

async function cargarCategorias() {
  categorias.value = await apiFetch('foro', '/categorias')
}

async function completarConteos(lista) {
  await Promise.all(
    lista.map(async (pregunta) => {
      const [votos, respuestas] = await Promise.all([
        apiFetch('interacciones', `/votos/pregunta/${pregunta.id}`).catch(() => null),
        apiFetch('interacciones', `/respuestas/pregunta/${pregunta.id}`).catch(() => null),
      ])
      pregunta.total_votos = votos ? votos.total_votos : null
      pregunta.cantidad_respuestas = Array.isArray(respuestas) ? respuestas.length : null
    }),
  )
}

async function cargarPreguntas() {
  cargando.value = true
  errorLista.value = ''
  try {
    const ruta = filtroCategoria.value
      ? `/preguntas/categoria/${filtroCategoria.value}`
      : '/preguntas'
    const lista = await apiFetch('foro', ruta)
    preguntas.value = lista.map((pregunta) => ({
      ...pregunta,
      total_votos: null,
      cantidad_respuestas: null,
      aviso: '',
    }))
  } catch (e) {
    preguntas.value = []
    errorLista.value = e.message
  } finally {
    cargando.value = false
  }
  if (preguntas.value.length > 0) {
    await completarConteos(preguntas.value)
  }
}

async function votar(pregunta) {
  if (!exigirSesion('Inicia sesión para votar.')) return
  pregunta.aviso = ''
  try {
    await apiFetch('interacciones', '/votos', {
      method: 'POST',
      body: JSON.stringify({ voto: 1, id_pregunta: pregunta.id }),
    })
    const votos = await apiFetch('interacciones', `/votos/pregunta/${pregunta.id}`)
    pregunta.total_votos = votos.total_votos
  } catch (e) {
    if (e.status === 401) {
      pedirSesion('Tu sesión expiró. Inicia sesión para votar.')
      return
    }
    pregunta.aviso = e.message
  }
}

async function publicarPregunta() {
  errorFormulario.value = ''
  if (!exigirSesion('Inicia sesión para publicar tu pregunta.')) return

  if (!idCategoriaNueva.value || !tituloNuevo.value.trim() || !contenidoNuevo.value.trim()) {
    errorFormulario.value = 'Elige una categoría y escribe el título y el contenido.'
    return
  }
  if (contenidoNuevo.value.trim().length > limiteContenido.value) {
    errorFormulario.value = `El texto admite hasta ${limiteContenido.value} caracteres.`
    return
  }

  enviando.value = true
  try {
    const creada = await apiFetch('foro', '/preguntas', {
      method: 'POST',
      body: JSON.stringify({
        id_categoria: Number(idCategoriaNueva.value),
        titulo: tituloNuevo.value,
        contenido: contenidoNuevo.value,
      }),
    })
    idCategoriaNueva.value = ''
    tituloNuevo.value = ''
    contenidoNuevo.value = ''
    mostrarFormulario.value = false
    mensajeExito.value = 'Pregunta publicada'
    idNuevo.value = creada.id
    await cargarPreguntas()
    window.setTimeout(() => {
      mensajeExito.value = ''
    }, 4000)
    window.setTimeout(() => {
      idNuevo.value = null
    }, 2000)
  } catch (e) {
    if (e.status === 401) {
      pedirSesion('Tu sesión expiró. Inicia sesión para publicar.')
    } else {
      errorFormulario.value = e.message
    }
  } finally {
    enviando.value = false
  }
}

onMounted(async () => {
  try {
    await cargarCategorias()
  } catch (e) {
    errorLista.value = e.message
  }
  await cargarPreguntas()
})
</script>

<template>
  <main class="pagina">
    <div class="home-rejilla">
      <div>
        <div class="home-intro">
          <div>
            <h1>Preguntas de la comunidad</h1>
            <p v-if="autenticado">Sesión iniciada como {{ usuario.nombre_apellido }}.</p>
            <p v-else>Puedes leer sin cuenta. Publicar, votar y comentar pide inicio de sesión.</p>
          </div>
          <button
            v-if="!mostrarFormulario"
            type="button"
            class="btn-primario btn-ancho-auto"
            @click="abrirFormulario"
          >
            Haz tu pregunta
          </button>
        </div>

        <div class="foro-barra">
          <div class="chips" role="radiogroup" aria-label="Filtrar por categoría">
            <button
              type="button"
              class="chip"
              role="radio"
              :aria-checked="filtroCategoria === ''"
              :class="{ 'chip-activo': filtroCategoria === '' }"
              @click="elegirCategoria('')"
            >
              Todas
            </button>
            <button
              v-for="cat in categorias"
              :key="cat.id"
              type="button"
              class="chip"
              role="radio"
              :aria-checked="filtroCategoria === String(cat.id)"
              :class="{ 'chip-activo': filtroCategoria === String(cat.id) }"
              @click="elegirCategoria(String(cat.id))"
            >
              {{ cat.nombre }}
            </button>
          </div>
        </div>

        <p class="aviso-exito" role="status" aria-live="polite">{{ mensajeExito }}</p>

        <section v-if="mostrarFormulario" class="foro-formulario" aria-label="Nueva pregunta">
          <h2>Haz tu pregunta</h2>
          <form @submit.prevent="publicarPregunta">
            <label>
              Categoría
              <select v-model="idCategoriaNueva">
                <option value="" disabled>Elige una categoría</option>
                <option v-for="cat in categorias" :key="cat.id" :value="String(cat.id)">
                  {{ cat.nombre }}
                </option>
              </select>
            </label>
            <label>
              Título
              <input v-model="tituloNuevo" type="text" />
            </label>
            <label>
              Contenido
              <textarea v-model="contenidoNuevo" rows="4" :maxlength="limiteContenido"></textarea>
            </label>
            <p class="ayuda-limite">
              {{ contenidoNuevo.length }} / {{ limiteContenido }} caracteres.
              <router-link v-if="plan !== 'premium'" to="/premium">
                Premium permite textos más largos.
              </router-link>
              <span v-else>Plan Premium de demostración activo.</span>
            </p>
            <div class="acciones-form">
              <p v-if="errorFormulario" class="error" role="alert">{{ errorFormulario }}</p>
              <button type="submit" class="btn-primario btn-ancho-auto" :disabled="enviando">
                {{ enviando ? 'Publicando…' : 'Publicar pregunta' }}
              </button>
              <button type="button" class="btn-texto" @click="cancelarFormulario">Cancelar</button>
            </div>
          </form>
        </section>

        <p v-if="cargando" class="foro-estado">Cargando…</p>
        <p v-else-if="errorLista" class="error foro-estado" role="alert" aria-live="assertive">
          {{ errorLista }}
        </p>
        <p v-else-if="preguntas.length === 0" class="foro-vacio">
          No hay preguntas en esta categoría.
          <template v-if="autenticado">Usa <strong>Haz tu pregunta</strong> para publicar la primera.</template>
          <template v-else>Cuando alguien publique, podrás leerla aquí.</template>
        </p>

        <ul v-else class="foro-lista">
          <li
            v-for="pregunta in preguntas"
            :key="pregunta.id"
            class="tarjeta-pregunta"
            :class="{ 'tarjeta-nueva': pregunta.id === idNuevo }"
          >
            <div class="tarjeta-tope">
              <span class="insignia">{{ pregunta.nombre_categoria }}</span>
              <router-link class="tarjeta-respuestas" :to="`/preguntas/${pregunta.id}`">
                {{ textoRespuestas(pregunta.cantidad_respuestas) }}
              </router-link>
            </div>
            <h2>
              <router-link :to="`/preguntas/${pregunta.id}`">{{ pregunta.titulo }}</router-link>
            </h2>
            <p class="tarjeta-extracto">{{ pregunta.contenido }}</p>
            <p class="tarjeta-meta">
              <span class="avatar avatar-chico" aria-hidden="true">{{ iniciales(pregunta.nombre_autor) }}</span>
              <span>{{ pregunta.nombre_autor }}</span>
              <span aria-hidden="true">·</span>
              <time :datetime="pregunta.fecha_creacion">{{ formatearFecha(pregunta.fecha_creacion) }}</time>
            </p>
            <div class="tarjeta-acciones">
              <button type="button" class="btn-voto" @click="votar(pregunta)">
                Votar
                <span v-if="pregunta.total_votos != null">{{ pregunta.total_votos }}</span>
              </button>
              <button type="button" class="btn-texto" @click="participar(pregunta)">Participar</button>
            </div>
            <p v-if="pregunta.aviso" class="error aviso-tarjeta" role="alert">{{ pregunta.aviso }}</p>
          </li>
        </ul>
      </div>

      <aside class="home-lateral" aria-label="Participación y planes">
        <section class="panel-lateral">
          <header class="panel-encabezado">
            <h2>Ranking</h2>
            <p class="nota-demo">Demostración. Aún no viene del servidor.</p>
          </header>
          <ol class="ranking">
            <li v-for="(persona, indice) in RANKING_DEMO" :key="persona.id">
              <span class="ranking-puesto">{{ indice + 1 }}</span>
              <span class="avatar avatar-chico" aria-hidden="true">{{ iniciales(persona.nombre) }}</span>
              <span class="ranking-datos">
                <span class="ranking-nombre">{{ persona.nombre }}</span>
                <span class="estrellas" :aria-label="`${persona.estrellas} de 5 estrellas`">
                  <span
                    v-for="n in 5"
                    :key="n"
                    :class="{ 'estrella-activa': n <= persona.estrellas }"
                  >★</span>
                </span>
              </span>
              <span class="ranking-puntos">{{ persona.puntos }}</span>
            </li>
          </ol>
        </section>

        <section class="promo-premium">
          <p class="insignia insignia-premium">Premium</p>
          <h2>{{ plan === 'premium' ? 'Tu plan está activo' : 'Más espacio para preguntar' }}</h2>
          <p v-if="plan === 'premium'">
            En este navegador puedes publicar preguntas de hasta {{ limiteContenido }} caracteres.
          </p>
          <p v-else>
            El plan gratuito limita la extensión. Premium amplía ese espacio y muestra un distintivo.
          </p>
          <router-link to="/premium" class="btn-secundario">
            {{ plan === 'premium' ? 'Ver tu plan' : 'Ver planes' }}
          </router-link>
        </section>
      </aside>
    </div>
  </main>
</template>
