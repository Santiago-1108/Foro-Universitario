<script setup>
import { onMounted, ref } from 'vue'
import { apiFetch } from '../services/api.js'
import { usuario } from '../services/sesion.js'
import { formatearFecha } from '../utils/formato.js'

const CLAVE_SUSPENSION = 'suspensiones_demo'

const pestaña = ref('usuarios')
const cargando = ref(false)
const error = ref('')
const aviso = ref('')
const usuarios = ref([])
const preguntas = ref([])
const idPregunta = ref('')
const detalle = ref([])
const suspendidos = ref(leerSuspensiones())

function leerSuspensiones() {
  try {
    const lista = JSON.parse(localStorage.getItem(CLAVE_SUSPENSION) || '[]')
    return new Set(Array.isArray(lista) ? lista : [])
  } catch {
    return new Set()
  }
}

function guardarSuspensiones(conjunto) {
  suspendidos.value = conjunto
  localStorage.setItem(CLAVE_SUSPENSION, JSON.stringify([...conjunto]))
}

function estaSuspendido(id) {
  return suspendidos.value.has(id)
}

function alternarSuspension(id) {
  const copia = new Set(suspendidos.value)
  if (copia.has(id)) copia.delete(id)
  else copia.add(id)
  guardarSuspensiones(copia)
  aviso.value = 'La suspensión es una demostración de este navegador. El servidor no guarda bloqueos.'
}

async function cargarUsuarios() {
  usuarios.value = await apiFetch('usuarios', '/usuarios')
}

async function cargarPreguntas() {
  preguntas.value = await apiFetch('foro', '/preguntas')
  if (!idPregunta.value && preguntas.value.length > 0) {
    idPregunta.value = String(preguntas.value[0].id)
  }
}

async function cargarDetalle() {
  if (!idPregunta.value) {
    detalle.value = []
    return
  }
  try {
    const respuestas = await apiFetch('interacciones', `/respuestas/pregunta/${idPregunta.value}`)
    detalle.value = await Promise.all(
      respuestas.map(async (respuesta) => {
        const comentarios = await apiFetch('interacciones', `/comentarios/respuesta/${respuesta.id}`).catch(() => [])
        return { ...respuesta, comentarios }
      }),
    )
  } catch (e) {
    error.value = e.message
  }
}

async function iniciar() {
  cargando.value = true
  error.value = ''
  try {
    await Promise.all([cargarUsuarios(), cargarPreguntas()])
    await cargarDetalle()
  } catch (e) {
    error.value = e.message
  } finally {
    cargando.value = false
  }
}

async function eliminarUsuario(persona) {
  if (persona.id === usuario.value?.id) return
  if (!window.confirm(`¿Eliminar a ${persona.nombre_apellido}? Esta acción usa el servidor.`)) return
  error.value = ''
  try {
    await apiFetch('usuarios', `/usuarios/${persona.id}`, { method: 'DELETE' })
    usuarios.value = usuarios.value.filter((item) => item.id !== persona.id)
    aviso.value = 'Usuario eliminado.'
  } catch (e) {
    error.value = e.message
  }
}

async function eliminarPregunta(pregunta) {
  if (!window.confirm(`¿Eliminar la pregunta «${pregunta.titulo}»?`)) return
  error.value = ''
  try {
    await apiFetch('foro', `/preguntas/${pregunta.id}`, { method: 'DELETE' })
    preguntas.value = preguntas.value.filter((item) => item.id !== pregunta.id)
    if (idPregunta.value === String(pregunta.id)) {
      idPregunta.value = preguntas.value[0] ? String(preguntas.value[0].id) : ''
      await cargarDetalle()
    }
    aviso.value = 'Pregunta eliminada.'
  } catch (e) {
    error.value = e.message
  }
}

async function eliminarRespuesta(respuesta) {
  if (!window.confirm('¿Eliminar esta respuesta?')) return
  error.value = ''
  try {
    await apiFetch('interacciones', `/respuestas/${respuesta.id}`, { method: 'DELETE' })
    await cargarDetalle()
    aviso.value = 'Respuesta eliminada.'
  } catch (e) {
    error.value = e.message
  }
}

async function eliminarComentario(respuesta, comentario) {
  if (!window.confirm('¿Eliminar este comentario?')) return
  error.value = ''
  try {
    await apiFetch('interacciones', `/comentarios/${comentario.id}`, { method: 'DELETE' })
    respuesta.comentarios = respuesta.comentarios.filter((item) => item.id !== comentario.id)
    aviso.value = 'Comentario eliminado.'
  } catch (e) {
    error.value = e.message
  }
}

onMounted(iniciar)
</script>

<template>
  <main class="pagina">
    <header class="pagina-encabezado">
      <h1>Administración</h1>
      <p>Modera usuarios, preguntas y comentarios. Esta sección solo aparece si tu rol es admin.</p>
    </header>

    <div class="chips" role="tablist" aria-label="Módulos de administración">
      <button type="button" class="chip" role="tab" :class="{ 'chip-activo': pestaña === 'usuarios' }" :aria-selected="pestaña === 'usuarios'" @click="pestaña = 'usuarios'">Usuarios</button>
      <button type="button" class="chip" role="tab" :class="{ 'chip-activo': pestaña === 'preguntas' }" :aria-selected="pestaña === 'preguntas'" @click="pestaña = 'preguntas'">Preguntas</button>
      <button type="button" class="chip" role="tab" :class="{ 'chip-activo': pestaña === 'comentarios' }" :aria-selected="pestaña === 'comentarios'" @click="pestaña = 'comentarios'">Comentarios</button>
    </div>

    <p v-if="aviso" class="aviso-exito" role="status">{{ aviso }}</p>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <p v-if="cargando" class="foro-estado">Cargando…</p>

    <section v-else-if="pestaña === 'usuarios'" aria-label="Usuarios">
      <p class="nota-demo">Suspender no bloquea la cuenta en el servidor: solo queda marcado en este navegador.</p>
      <ul class="lista-admin">
        <li v-for="persona in usuarios" :key="persona.id">
          <div>
            <strong>{{ persona.nombre_apellido }}</strong>
            <p class="tarjeta-meta">
              <span>{{ persona.correo }}</span>
              <span aria-hidden="true">·</span>
              <span>{{ persona.rol }}</span>
              <template v-if="estaSuspendido(persona.id)">
                <span aria-hidden="true">·</span>
                <span>Suspendido · demo</span>
              </template>
            </p>
          </div>
          <div class="acciones-admin">
            <button type="button" class="btn-texto" @click="alternarSuspension(persona.id)">
              {{ estaSuspendido(persona.id) ? 'Quitar suspensión' : 'Suspender' }}
            </button>
            <button
              type="button"
              class="btn-texto btn-peligro"
              :disabled="persona.id === usuario?.id"
              @click="eliminarUsuario(persona)"
            >
              Eliminar usuario
            </button>
          </div>
        </li>
      </ul>
    </section>

    <section v-else-if="pestaña === 'preguntas'" aria-label="Preguntas">
      <ul class="lista-admin">
        <li v-for="pregunta in preguntas" :key="pregunta.id">
          <div>
            <strong>{{ pregunta.titulo }}</strong>
            <p class="tarjeta-meta">
              <span>{{ pregunta.nombre_categoria }}</span>
              <span aria-hidden="true">·</span>
              <span>{{ pregunta.nombre_autor }}</span>
              <span aria-hidden="true">·</span>
              <time :datetime="pregunta.fecha_creacion">{{ formatearFecha(pregunta.fecha_creacion) }}</time>
            </p>
          </div>
          <button type="button" class="btn-texto btn-peligro" @click="eliminarPregunta(pregunta)">
            Eliminar pregunta
          </button>
        </li>
      </ul>
      <p v-if="preguntas.length === 0" class="foro-vacio">No hay preguntas publicadas.</p>
    </section>

    <section v-else aria-label="Comentarios">
      <label>
        Pregunta
        <select v-model="idPregunta" @change="cargarDetalle">
          <option v-if="preguntas.length === 0" value="" disabled>No hay preguntas</option>
          <option v-for="pregunta in preguntas" :key="pregunta.id" :value="String(pregunta.id)">
            {{ pregunta.titulo }}
          </option>
        </select>
      </label>

      <p v-if="detalle.length === 0" class="foro-vacio">Esta pregunta no tiene respuestas ni comentarios.</p>

      <article v-for="respuesta in detalle" :key="respuesta.id" class="tarjeta-pregunta bloque-moderar">
        <p class="lectura-contenido">{{ respuesta.contenido }}</p>
        <p class="tarjeta-meta">
          <span>{{ respuesta.nombre_autor }}</span>
          <span aria-hidden="true">·</span>
          <time :datetime="respuesta.fecha_creacion">{{ formatearFecha(respuesta.fecha_creacion) }}</time>
        </p>
        <button type="button" class="btn-texto btn-peligro" @click="eliminarRespuesta(respuesta)">
          Eliminar respuesta
        </button>
        <ul class="lista-comentarios">
          <li v-for="comentario in respuesta.comentarios" :key="comentario.id">
            <p>{{ comentario.contenido }}</p>
            <p class="tarjeta-meta">
              <span>{{ comentario.nombre_autor }}</span>
              <span aria-hidden="true">·</span>
              <time :datetime="comentario.fecha_creacion">{{ formatearFecha(comentario.fecha_creacion) }}</time>
            </p>
            <button type="button" class="btn-texto btn-peligro" @click="eliminarComentario(respuesta, comentario)">
              Eliminar comentario
            </button>
          </li>
        </ul>
      </article>
    </section>
  </main>
</template>
