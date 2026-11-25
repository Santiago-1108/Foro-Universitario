<script setup>
import { onMounted, ref } from 'vue'
import { apiFetch } from '../services/api.js'
import { formatearFecha } from '../utils/formato.js'

const pestaña = ref('usuarios')
const cargando = ref(false), ocupado = ref(false)
const error = ref(''), aviso = ref('')
const usuarios = ref([]), preguntas = ref([]), idPregunta = ref(''), detalle = ref([])
const estadisticas = ref({}), reportes = ref([]), historial = ref([])
const estadoReporte = ref('pendiente'), siguienteReporte = ref(null), siguienteHistorial = ref(null)
const titulos = {usuarios:'Usuarios',suspendidos:'Suspendidos',comunidades:'Comunidades',publicaciones:'Publicaciones',respuestas:'Respuestas',comentarios:'Comentarios',cerradas:'Conversaciones cerradas',reportes_pendientes:'Reportes pendientes'}
async function cargarEstadisticas(){estadisticas.value=await apiFetch('usuarios','/moderacion/estadisticas')}
async function cargarReportes(mas=false){
  if(ocupado.value) return
  ocupado.value=true; error.value=''
  try{const r=await apiFetch('usuarios',`/moderacion/reportes?estado=${estadoReporte.value}${mas&&siguienteReporte.value?'&antes='+siguienteReporte.value:''}`); reportes.value=mas?[...reportes.value,...r.elementos]:r.elementos; siguienteReporte.value=r.siguiente}
  catch(e){error.value=e.message}finally{ocupado.value=false}
}
async function cargarHistorial(mas=false){
  if(ocupado.value) return
  ocupado.value=true; error.value=''
  try{const r=await apiFetch('usuarios',`/moderacion/historial${mas&&siguienteHistorial.value?'?antes='+siguienteHistorial.value:''}`); historial.value=mas?[...historial.value,...r.elementos]:r.elementos; siguienteHistorial.value=r.siguiente}
  catch(e){error.value=e.message}finally{ocupado.value=false}
}
async function abrirTab(tab){pestaña.value=tab; if(tab==='reportes') await cargarReportes(); if(tab==='historial') await cargarHistorial(); if(tab==='estadisticas'){try{await cargarEstadisticas()}catch(e){error.value=e.message}}}
async function alternarSuspension(persona){
  if(ocupado.value || persona.rol==='admin') return
  const motivo=window.prompt(persona.suspendido?'Motivo de reactivación':'Motivo de suspensión'); if(!motivo?.trim()) return
  ocupado.value=true; error.value=''; aviso.value=''
  try{const r=await apiFetch('usuarios',`/moderacion/usuarios/${persona.id}/suspension`,{method:'PUT',body:JSON.stringify({activo:!persona.suspendido,motivo})}); persona.suspendido=r.suspendido; aviso.value='Estado de cuenta actualizado.'; await cargarEstadisticas()}
  catch(e){error.value=e.message}finally{ocupado.value=false}
}
async function moderarPregunta(pregunta,campo){
  if(ocupado.value)return
  const motivo=window.prompt('Motivo de la acción (opcional)',''); if(motivo===null)return
  ocupado.value=true; error.value=''; aviso.value=''
  try{const r=await apiFetch('usuarios',`/moderacion/preguntas/${pregunta.id}`,{method:'PUT',body:JSON.stringify({[campo]:!pregunta[campo],motivo})}); Object.assign(pregunta,r); aviso.value='Publicación actualizada.'; await cargarEstadisticas()}
  catch(e){error.value=e.message}finally{ocupado.value=false}
}
async function revisarReporte(reporte,estado){
  if(ocupado.value)return
  const nota=window.prompt('Nota de revisión (opcional)',''); if(nota===null)return
  ocupado.value=true; error.value=''; aviso.value=''
  try{await apiFetch('usuarios',`/moderacion/reportes/${reporte.id}`,{method:'PUT',body:JSON.stringify({estado,nota})}); reporte.estado=estado; if(estadoReporte.value==='pendiente')reportes.value=reportes.value.filter(r=>r.id!==reporte.id); aviso.value='Reporte revisado.'; await cargarEstadisticas()}
  catch(e){error.value=e.message}finally{ocupado.value=false}
}
async function retirarReportado(reporte){
  if(ocupado.value || !window.confirm('¿Retirar este contenido? Se conservará en la base de datos.'))return
  const destinos={pregunta:['foro','preguntas'],respuesta:['interacciones','respuestas'],comentario:['interacciones','comentarios']}; const destino=destinos[reporte.tipo]; if(!destino)return
  ocupado.value=true; error.value=''; aviso.value=''
  try{await apiFetch(destino[0],`/${destino[1]}/${reporte.id_objeto}`,{method:'DELETE'}); aviso.value='Contenido retirado. Revisa el reporte cuando termines.'; await cargarPreguntas(); await cargarDetalle(); await cargarEstadisticas()}
  catch(e){error.value=e.message}finally{ocupado.value=false}
}

async function cargarUsuarios() {
  usuarios.value = await apiFetch('usuarios', '/usuarios')
}

async function cargarPreguntas() {
  preguntas.value = await apiFetch('foro', '/preguntas?gestion=1')
  if (!preguntas.value.some(p=>String(p.id)===idPregunta.value)) {
    idPregunta.value = preguntas.value.length ? String(preguntas.value[0].id) : ''
  }
}

async function cargarDetalle() {
  if (!idPregunta.value) {
    detalle.value = []
    return
  }
  try {
    const respuestas = await apiFetch('interacciones', `/respuestas/pregunta/${idPregunta.value}?gestion=1`)
    detalle.value = await Promise.all(
      respuestas.map(async (respuesta) => {
        const comentarios = await apiFetch('interacciones', `/comentarios/respuesta/${respuesta.id}?gestion=1`)
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
    await Promise.all([cargarUsuarios(), cargarPreguntas(), cargarEstadisticas()])
    await cargarDetalle()
  } catch (e) {
    error.value = e.message
  } finally {
    cargando.value = false
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
    await cargarDetalle()
    aviso.value = 'Comentario eliminado.'
  } catch (e) {
    error.value = e.message
  }
}

onMounted(iniciar)
</script>

<template>
  <main class="pagina pagina-admin">
    <header class="pagina-encabezado">
      <h1>Administración</h1>
      <p>Modera usuarios, preguntas y comentarios. Esta sección solo aparece si tu rol es admin.</p>
    </header>

    <div class="chips" role="group" aria-label="Módulos de administración">
      <button type="button" class="chip"  :class="{ 'chip-activo': pestaña === 'usuarios' }" :aria-pressed="pestaña === 'usuarios'" @click="pestaña = 'usuarios'">Usuarios</button>
      <button type="button" class="chip"  :class="{ 'chip-activo': pestaña === 'preguntas' }" :aria-pressed="pestaña === 'preguntas'" @click="pestaña = 'preguntas'">Preguntas</button>
      <button type="button" class="chip"  :class="{ 'chip-activo': pestaña === 'comentarios' }" :aria-pressed="pestaña === 'comentarios'" @click="pestaña = 'comentarios'">Comentarios</button>
      <button v-for="tab in ['reportes','estadisticas','historial']" :key="tab" type="button" class="chip"  :class="{'chip-activo':pestaña===tab}" :aria-pressed="pestaña===tab" :disabled="ocupado" @click="abrirTab(tab)">{{tab==='reportes'?'Reportes':tab==='estadisticas'?'Estadísticas':'Historial'}}</button>
    </div>

    <p v-if="aviso" class="aviso-exito" role="status">{{ aviso }}</p>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <p v-if="cargando" class="foro-estado">Cargando…</p>

    <section v-else-if="pestaña === 'usuarios'" aria-label="Usuarios">
      <p>Las suspensiones se guardan en el servidor y revocan las sesiones de la cuenta.</p>
      <ul class="lista-admin">
        <li v-for="persona in usuarios" :key="persona.id">
          <div>
            <strong>{{ persona.nombre_apellido }}</strong>
            <p class="tarjeta-meta">
              <span>{{ persona.correo }}</span>
              <span aria-hidden="true">·</span>
              <span>{{ persona.rol }}</span>
              <template v-if="persona.suspendido">
                <span aria-hidden="true">·</span>
                <span>Suspendido</span>
              </template>
            </p>
          </div>
          <div class="acciones-admin">
            <button type="button" class="btn-texto" :disabled="ocupado || persona.rol==='admin'" @click="alternarSuspension(persona)">
              {{ persona.suspendido ? 'Quitar suspensión' : 'Suspender' }}
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
          <div class="acciones-admin">
          <button type="button" class="btn-texto" :disabled="ocupado" @click="moderarPregunta(pregunta,'fijada')">{{pregunta.fijada?'Desfijar':'Fijar'}}</button>
          <button type="button" class="btn-texto" :disabled="ocupado" @click="moderarPregunta(pregunta,'cerrada')">{{pregunta.cerrada?'Reabrir':'Cerrar conversación'}}</button>
          <button type="button" class="btn-texto btn-peligro" @click="eliminarPregunta(pregunta)">
            Eliminar pregunta
          </button></div>
        </li>
      </ul>
      <p v-if="preguntas.length === 0" class="foro-vacio">No hay preguntas publicadas.</p>
    </section>

    <section v-else-if="pestaña==='reportes'" aria-label="Reportes">
      <label>Estado<select v-model="estadoReporte" :disabled="ocupado" @change="cargarReportes()"><option value="pendiente">Pendientes</option><option value="atendido">Atendidos</option><option value="descartado">Descartados</option><option value="todos">Todos</option></select></label>
      <p v-if="!reportes.length" class="foro-vacio">No hay reportes para este filtro.</p>
      <article v-for="r in reportes" :key="r.id" class="tarjeta-pregunta">
        <h2>{{r.tipo}} #{{r.id_objeto}} · {{r.motivo}}</h2><p>{{r.contenido_reportado || 'Contenido no disponible'}}</p><p>{{r.detalle}}</p>
        <p class="tarjeta-meta">Reportado por {{r.reportante}} · {{r.estado}} · {{formatearFecha(r.fecha_creacion)}}</p>
        <p v-if="r.nota_revision">Nota: {{r.nota_revision}}</p>
        <div class="tarjeta-acciones"><router-link v-if="r.id_pregunta" :to="`/preguntas/${r.id_pregunta}`">Abrir conversación</router-link><router-link v-if="r.tipo==='usuario'" :to="`/usuarios/${r.id_objeto}`">Abrir perfil</router-link>
          <button v-if="r.estado==='pendiente' && r.tipo!=='usuario'" type="button" class="btn-texto btn-peligro" :disabled="ocupado" @click="retirarReportado(r)">Retirar contenido</button>
          <button v-if="r.estado==='pendiente'" type="button" class="btn-texto" :disabled="ocupado" @click="revisarReporte(r,'atendido')">Marcar atendido</button>
          <button v-if="r.estado==='pendiente'" type="button" class="btn-texto" :disabled="ocupado" @click="revisarReporte(r,'descartado')">Descartar</button>
        </div>
      </article>
      <button v-if="siguienteReporte" class="btn-texto" type="button" :disabled="ocupado" @click="cargarReportes(true)">Cargar más</button>
    </section>
    <section v-else-if="pestaña==='estadisticas'" aria-label="Estadísticas"><ul class="lista-admin admin-metricas"><li v-for="(valor,clave) in estadisticas" :key="clave"><strong>{{titulos[clave] || clave}}</strong><span>{{valor}}</span></li></ul></section>
    <section v-else-if="pestaña==='historial'" aria-label="Historial"><p v-if="!historial.length" class="foro-vacio">No hay acciones registradas.</p><ul class="lista-admin"><li v-for="h in historial" :key="h.id"><div><strong>{{h.accion}} · {{h.tipo}} #{{h.id_objeto}}</strong><p>{{h.detalle}}</p><p class="tarjeta-meta">{{h.administrador}} · {{formatearFecha(h.fecha_creacion)}}</p></div></li></ul><button v-if="siguienteHistorial" class="btn-texto" type="button" :disabled="ocupado" @click="cargarHistorial(true)">Cargar más</button></section>
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
            <button v-if="!comentario.eliminado" type="button" class="btn-texto btn-peligro" @click="eliminarComentario(respuesta, comentario)">
              Eliminar comentario
            </button>
          </li>
        </ul>
      </article>
    </section>
  </main>
</template>
