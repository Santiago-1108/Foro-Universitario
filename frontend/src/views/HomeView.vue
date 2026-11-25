<script setup>
import CargaMultimedia from '../components/CargaMultimedia.vue'
import MultimediaPublicacion from '../components/MultimediaPublicacion.vue'
import IconoForo from '../components/IconoForo.vue'
import ReportarContenido from '../components/ReportarContenido.vue'
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AvatarUsuario from '../components/AvatarUsuario.vue'
import { apiFetch } from '../services/api.js'
import {
  autenticado,
  exigirSesion,
  pedirSesion,
  usuario,
} from '../services/sesion.js'
import { formatearFecha, textoRespuestas } from '../utils/formato.js'

const router = useRouter()
const route = useRoute()

const comunidadDestino=ref(null), idComunidadNueva=ref(null), comunidadesNuevas=ref([]), errorNuevas=ref(''), cargaImagenes=ref(null), cargaVideo=ref(null), archivosImagen=ref(0), archivosVideo=ref(0), claveCarga=ref(0)
const filtroComunidad=computed(()=>typeof route.query.comunidad==='string'&&/^\d+$/.test(route.query.comunidad)?route.query.comunidad:'')
let versionComunidad=0
async function cargarComunidadDestino(){const v=++versionComunidad;comunidadDestino.value=null;if(!filtroComunidad.value||typeof route.query.slug!=='string')return;try{const c=await apiFetch('foro',`/comunidades/${encodeURIComponent(route.query.slug)}`);if(v===versionComunidad&&String(c.id)===filtroComunidad.value){comunidadDestino.value=c;if(mostrarFormulario.value){idComunidadNueva.value=c.id;idCategoriaNueva.value=String(c.id_categoria)}}}catch(e){if(v===versionComunidad)errorNuevas.value=e.message}}
async function cargarNuevas(){try{comunidadesNuevas.value=await apiFetch('foro','/comunidades')}catch(e){errorNuevas.value=e.message}}
const categorias = ref([])
const preguntas = ref([])
const filtroCategoria = computed(() => typeof route.query.categoria === 'string' && /^\d+$/.test(route.query.categoria) ? route.query.categoria : '')
const comunidad = computed(() => categorias.value.find(c => String(c.id) === filtroCategoria.value))
const soloSeguidas = computed(() => route.query.comunidades === 'seguidas' && autenticado.value)
const categoriasVisibles = computed(() => soloSeguidas.value ? categorias.value.filter(c => c.siguiendo) : categorias.value)
const orden = ref('para_ti'), vista = ref('todas'), etiqueta = ref(''), tipoFiltro = ref(''), estado = ref('')
const tituloPublicacion = ref(null)
const etiquetas = ['duda','debate','recurso','anuncio','proyecto']
const densidad=ref(localStorage.getItem('foro-densidad')==='compacta'?'compacta':'tarjetas')
watch(densidad,v=>localStorage.setItem('foro-densidad',v))
const filtrosActivos=computed(()=>[etiqueta.value,tipoFiltro.value,estado.value].filter(Boolean).length)
function restablecerFiltros(){orden.value=vista.value==='todas'?'para_ti':'reciente';etiqueta.value='';tipoFiltro.value='';estado.value=''}
function cambiarFeed(v){if(v==='personalizado'&&!exigirSesion('Inicia sesión para ver tus seguimientos.'))return;const query={...route.query};delete query.crear;delete query.borrador;delete query.explorar;delete query.orden;delete query.comunidades; if(v==='personalizado')query.vista=v;else delete query.vista;router.push({path:'/',query})}
function puedeEditar(p){return usuario.value&&(usuario.value.id===p.id_usuario||usuario.value.rol==='admin')}
async function accionPublicacion(p,accion){
  if(p.gestionando)return
  if(accion==='eliminar'&&!confirm('¿Eliminar esta publicación?'))return
  p.gestionando=true;p.aviso=''
  try{if(accion==='eliminar'){await apiFetch('foro',`/preguntas/${p.id}`,{method:'DELETE'});await cargarCategorias()}
    else{await apiFetch('usuarios',`/moderacion/preguntas/${p.id}`,{method:'PUT',body:JSON.stringify({[accion]:!p[accion]})})}
    await cargarPreguntas()
  }catch(e){p.aviso=e.message}finally{p.gestionando=false}
}
function cerrarMenus(e){document.querySelectorAll('.feed-toolbar details[open], .acciones-contexto[open]').forEach(d=>{if(e.key==='Escape'||(e.type==='click'&&!d.contains(e.target)))d.open=false})}
onMounted(()=>{document.addEventListener('click',cerrarMenus);document.addEventListener('keydown',cerrarMenus);window.addEventListener('comunidades-actualizadas',cargarNuevas)})
onUnmounted(()=>{document.removeEventListener('click',cerrarMenus);document.removeEventListener('keydown',cerrarMenus);window.removeEventListener('comunidades-actualizadas',cargarNuevas);versionCarga++})
async function preferencia(p, accion) {
  if (p.gestionando || !exigirSesion('Inicia sesión para guardar u ocultar publicaciones.')) return
  const campo = accion === 'guardar' ? 'guardada' : 'oculta'
  p.gestionando = true; p.aviso = ''
  try {
    const r = await apiFetch('foro', `/preguntas/${p.id}/${accion}`, {method:'PUT',body:JSON.stringify({activo:!p[campo]})})
    p[campo] = r.activo
    if (accion === 'ocultar' || vista.value === 'guardadas') await cargarPreguntas()
  } catch(e) { p.aviso = e.message }
  finally { p.gestionando = false }
}
const ranking = ref([]), errorRanking = ref(''), errorComunidad = ref(''), siguiendo = ref(false)
let versionCategorias = 0
async function cargarRanking() {
  errorRanking.value = ''
  try { ranking.value = await apiFetch('usuarios','/usuarios/ranking') }
  catch(e) { errorRanking.value = e.message }
}
async function seguirComunidad(cat = comunidad.value) {
  if (!cat || siguiendo.value || !exigirSesion('Inicia sesión para seguir comunidades.')) return
  siguiendo.value = true; errorComunidad.value = ''
  try {
    await apiFetch('foro', `/categorias/${cat.id}/seguir`, {method:'PUT',body:JSON.stringify({seguir:!cat.siguiendo})})
    await cargarCategorias()
    window.dispatchEvent(new Event('categorias-actualizadas'))
    if(vista.value==='personalizado'||orden.value==='para_ti')await cargarPreguntas()
    if (soloSeguidas.value) {
      if (filtroCategoria.value === String(cat.id) && !categorias.value.find(c => c.id === cat.id)?.siguiendo) {
        elegirCategoria('')
      } else { await cargarPreguntas() }
    }
  } catch(e) { errorComunidad.value = e.message }
  finally { siguiendo.value = false }
}

const cargando = ref(false)
const errorLista = ref('')
const hayMas = ref(false)
const TAMANO_PAGINA = 20
let versionCarga = 0

const idCategoriaNueva = ref('')
const tituloNuevo = ref('')
const contenidoNuevo = ref('')
const limiteContenido = 2000
const tipoNuevo = ref('texto'), etiquetaNueva = ref('')
const tiposEditor=[{id:'texto',nombre:'Texto',icono:'publicaciones'},{id:'multimedia',nombre:'Imágenes',icono:'imagen'},{id:'video',nombre:'Video',icono:'video'},{id:'enlace',nombre:'Enlace',icono:'enlace'},{id:'encuesta',nombre:'Encuesta',icono:'encuesta'}]
const tipoEditor=computed(()=>tipoNuevo.value==='imagen'?'multimedia':tipoNuevo.value)
function reiniciarAdjuntos(){claveCarga.value++;archivosImagen.value=0;archivosVideo.value=0}
const recursoNuevo = ref('')
const opcionesNuevas = ref(['', ''])
const borradorGuardado = ref(false)
function datosFormulario() {
  return { id_comunidad:idComunidadNueva.value, id_categoria: idCategoriaNueva.value ? Number(idCategoriaNueva.value) : null,
    titulo: tituloNuevo.value, contenido: contenidoNuevo.value, tipo: tipoNuevo.value,
    recurso_url: recursoNuevo.value, opciones_encuesta: opcionesNuevas.value, etiqueta: etiquetaNueva.value }
}
function limpiarFormulario() {
  reiniciarAdjuntos()
  idComunidadNueva.value=null; idCategoriaNueva.value = ''; tituloNuevo.value = ''; contenidoNuevo.value = ''
  tipoNuevo.value = 'texto'; etiquetaNueva.value = ''; recursoNuevo.value = ''; opcionesNuevas.value = ['', '']
  borradorGuardado.value = false
}
async function gestionarBorrador(accion) {
  if (!exigirSesion('Inicia sesión para gestionar tus borradores.') || enviando.value) return
  enviando.value = true; errorFormulario.value = ''
  try {
    if (accion === 'guardar') {
      await apiFetch('foro', '/preguntas/borrador', { method: 'PUT', body: JSON.stringify({datos: datosFormulario()}) })
      borradorGuardado.value = true; mensajeExito.value = 'Borrador guardado'
    } else if (accion === 'recuperar') {
      if((archivosImagen.value||archivosVideo.value)&&!window.confirm('Recuperar el borrador reemplazará los archivos seleccionados. ¿Continuar?'))return
      const d = await apiFetch('foro', '/preguntas/borrador')
      if (!d) { errorFormulario.value = 'No tienes un borrador guardado.'; return }
      reiniciarAdjuntos(); idCategoriaNueva.value = d.id_categoria ? String(d.id_categoria) : '';idComunidadNueva.value=d.id_comunidad||null
      tituloNuevo.value = d.titulo; contenidoNuevo.value = d.contenido; tipoNuevo.value = d.tipo
      etiquetaNueva.value = d.etiqueta || ''; recursoNuevo.value = d.recurso_url; opcionesNuevas.value = d.opciones_encuesta.length ? d.opciones_encuesta : ['', '']
      borradorGuardado.value = true
    } else {
      if(!window.confirm('¿Descartar el borrador guardado?'))return
      await apiFetch('foro', '/preguntas/borrador', { method: 'DELETE' }); limpiarFormulario()
    }
  } catch(e) { errorFormulario.value = e.message }
  finally { enviando.value = false }
}
const errorFormulario = ref('')
const enviando = ref(false)
const mostrarFormulario = ref(false)
const mensajeExito = ref('')
const idNuevo = ref(null)

function elegirCategoria(id) {
  router.push({ path:'/', query: { ...(soloSeguidas.value ? {comunidades:'seguidas'} : {}), ...(vista.value==='personalizado'?{vista:'personalizado'}:{}), ...(id ? {categoria:id} : {}) } })
}

async function abrirFormulario() {
  if (!exigirSesion('Inicia sesión para publicar tu pregunta.')) return
  mostrarFormulario.value = true
  if (comunidad.value) idCategoriaNueva.value = String(comunidad.value.id)
  if(comunidadDestino.value){idComunidadNueva.value=comunidadDestino.value.id;idCategoriaNueva.value=String(comunidadDestino.value.id_categoria)}
  errorFormulario.value = ''
  await nextTick()
  tituloPublicacion.value?.focus()
}

async function cancelarFormulario() {
  if((archivosImagen.value||archivosVideo.value)&&!window.confirm('¿Cerrar el editor y retirar los archivos seleccionados? El texto se conserva mientras permanezcas en esta página.'))return
  reiniciarAdjuntos(); mostrarFormulario.value = false
  errorFormulario.value = ''
  await nextTick()
  document.querySelector('.nav-crear')?.focus()
  if(route.query.crear)await router.replace({path:'/',query:{...route.query,crear:undefined,borrador:undefined}})
}

function participar(pregunta) {
  if (pregunta.cerrada) { router.push(`/preguntas/${pregunta.id}`); return }
  if (!autenticado.value) { router.push(`/preguntas/${pregunta.id}`); return }
  router.push({ path: `/preguntas/${pregunta.id}`, hash: '#opinar' })
}

async function cargarCategorias() {
  const actual = ++versionCategorias
  const datos = await apiFetch('foro', '/categorias')
  if (actual === versionCategorias) categorias.value = datos
}

async function cargarPreguntas(agregar = false) {
  const version = ++versionCarga
  cargando.value = true
  errorLista.value = ''
  if (!agregar) {
    preguntas.value = []
    hayMas.value = false
  }
  const offset = preguntas.value.length
  try {
    const ruta = filtroCategoria.value
      ? `/preguntas/categoria/${filtroCategoria.value}`
      : '/preguntas'
    const params = new URLSearchParams({limite:TAMANO_PAGINA+1,offset,orden:orden.value,vista:autenticado.value ? vista.value : 'todas',etiqueta:etiqueta.value,tipo:tipoFiltro.value,estado:estado.value,...(soloSeguidas.value ? {seguidas:'1'} : {}),...(filtroComunidad.value?{comunidad:filtroComunidad.value}:{})})
    const lista = await apiFetch('foro', `${ruta}?${params}`)
    if (version !== versionCarga) return
    hayMas.value = lista.length > TAMANO_PAGINA
    const pagina = lista.slice(0, TAMANO_PAGINA).map(pregunta => ({ ...pregunta, aviso: '', votando: false }))
    preguntas.value = agregar ? [...preguntas.value, ...pagina] : pagina
  } catch (e) {
    if (version === versionCarga) errorLista.value = e.message
  } finally {
    if (version === versionCarga) cargando.value = false
  }
}

async function votar(pregunta, signo) {
  if (!exigirSesion('Inicia sesión para votar.')) return
  if (pregunta.votando) return
  pregunta.votando = true
  pregunta.aviso = ''
  try {
    const votos = await apiFetch('interacciones', '/votos', {
      method: 'POST',
      body: JSON.stringify({ voto: pregunta.mi_voto === signo ? 0 : signo, id_pregunta: pregunta.id }),
    })
    pregunta.total_votos = votos.total_votos
    pregunta.mi_voto = votos.voto
    cargarRanking()
  } catch (e) {
    if (e.status === 401) {
      pedirSesion('Tu sesión expiró. Inicia sesión para votar.')
      return
    }
    pregunta.aviso = e.message
  } finally {
    pregunta.votando = false
  }
}

async function publicarPregunta() {
  errorFormulario.value = ''
  if (!exigirSesion('Inicia sesión para publicar tu pregunta.')) return

  if (!idCategoriaNueva.value || !tituloNuevo.value.trim() || (!contenidoNuevo.value.trim() && !['multimedia','video'].includes(tipoNuevo.value))) {
    errorFormulario.value = 'Elige una categoría y escribe el título y el contenido.'
    return
  }
  if (contenidoNuevo.value.trim().length > limiteContenido) {
    errorFormulario.value = `El texto admite hasta ${limiteContenido} caracteres.`
    return
  }

  enviando.value = true
  try {
    const datos=datosFormulario();if(['multimedia','video'].includes(datos.tipo)){const carga=datos.tipo==='video'?cargaVideo.value:cargaImagenes.value;if(!carga)throw new Error('Selecciona archivos');datos.archivos=await carga.preparar()}
    const creada = await apiFetch('foro', '/preguntas', {
      method: 'POST',
      body: JSON.stringify(datos),
    })
    if (borradorGuardado.value) {
      try { await apiFetch('foro', '/preguntas/borrador', { method: 'DELETE' }) }
      catch { /* La publicación ya existe; el borrador se puede descartar manualmente. */ }
    }
    limpiarFormulario()
    mostrarFormulario.value = false
    mensajeExito.value = 'Pregunta publicada'
    idNuevo.value = creada.id
    if(route.query.crear)await router.replace({path:'/',query:{...route.query,crear:undefined,borrador:undefined}})
    await Promise.all([cargarPreguntas(), cargarCategorias().catch(e => { errorComunidad.value = e.message })])
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

const explorar=computed(()=>route.query.explorar==='1')
async function compartirFeed(p){const url=new URL(`/preguntas/${p.id}`,location.origin).href;try{await navigator.clipboard.writeText(url);mensajeExito.value='Enlace copiado'}catch{mensajeExito.value=url}}
async function aplicarRuta(){
  if(route.path!=='/')return
  const nuevaVista=route.query.vista==='personalizado'&&autenticado.value?'personalizado':'todas'
  if(vista.value!==nuevaVista||route.query.orden==='popular'||(!route.query.crear&&orden.value==='popular')) orden.value=route.query.orden==='popular'?'popular':nuevaVista==='personalizado'?'reciente':'para_ti'
  vista.value=nuevaVista
  if(route.query.crear==='1'){await abrirFormulario();if(route.query.borrador==='1'&&mostrarFormulario.value)await gestionarBorrador('recuperar')}
}
watch(()=>route.fullPath,aplicarRuta,{immediate:true})
watch([filtroComunidad,()=>route.query.slug,()=>usuario.value?.id],cargarComunidadDestino,{immediate:true})
watch(filtroComunidad,()=>{if(!filtroComunidad.value)idComunidadNueva.value=null})
function actualizarDestino(){const c=comunidadesNuevas.value.find(c=>c.id===idComunidadNueva.value);if(c)idCategoriaNueva.value=String(c.id_categoria)}
function actualizarCategoriaDestino(){if(idComunidadNueva.value&&String((comunidadesNuevas.value.find(c=>c.id===idComunidadNueva.value)||comunidadDestino.value)?.id_categoria)!==idCategoriaNueva.value)idComunidadNueva.value=null}
const destinos=computed(()=>{const a=[...comunidadesNuevas.value];if(comunidadDestino.value&&!a.some(c=>c.id===comunidadDestino.value.id))a.push(comunidadDestino.value);return a.filter(c=>c.tipo==='publica'||c.mi_rol)})
watch([filtroCategoria, filtroComunidad, soloSeguidas, orden, vista, etiqueta, tipoFiltro, estado], () => { errorComunidad.value = ''; cargarPreguntas() })
watch(() => usuario.value?.id, () => {
  limpiarFormulario(); mostrarFormulario.value = false; vista.value = 'todas'; orden.value='para_ti'
  categorias.value = []
  cargarCategorias().catch(e => { errorComunidad.value = e.message }); cargarNuevas(); cargarPreguntas()
  if(autenticado.value&&route.query.crear==='1')aplicarRuta()
})
onMounted(async () => {
  try {
    await cargarCategorias()
  } catch (e) {
    errorLista.value = e.message
  }
  await Promise.all([cargarPreguntas(), cargarRanking(), cargarNuevas()])
  if(route.query.crear==='1'&&comunidad.value&&!idCategoriaNueva.value) idCategoriaNueva.value=String(comunidad.value.id)
})
</script>

<template>
  <main class="pagina pagina-inicio">
    <div class="home-rejilla">
      <div class="home-principal">
        <div class="home-intro">
          <div>
            <h1>{{comunidadDestino?.nombre || 'Preguntas de la comunidad'}}</h1><router-link v-if="comunidadDestino" :to="`/comunidades/${comunidadDestino.slug}`">Información y administración de la comunidad</router-link>
            <p v-if="autenticado">Sesión iniciada como {{ usuario.nombre_apellido }}.</p>
            <p v-else>Puedes leer sin cuenta. Publicar, votar y comentar pide inicio de sesión.</p>
          </div>
        </div>

        <div class="foro-barra">
          <div class="chips" role="group" aria-label="Filtrar por categoría">
            <button
              type="button"
              class="chip"
              :aria-pressed="filtroCategoria === ''"
              :class="{ 'chip-activo': filtroCategoria === '' }"
              @click="elegirCategoria('')"
            >
              Todas
            </button>
            <button
              v-for="cat in categoriasVisibles"
              :key="cat.id"
              type="button"
              class="chip"
              :aria-pressed="filtroCategoria === String(cat.id)"
              :class="{ 'chip-activo': filtroCategoria === String(cat.id) }"
              @click="elegirCategoria(String(cat.id))"
            >
              {{ cat.nombre }}{{ cat.siguiendo ? ' ✓' : '' }}
            </button>
          </div>
        </div>

        <div v-if="autenticado" class="comunidades-acceso">
          <router-link :to="{path:'/',query:soloSeguidas ? {} : {comunidades:'seguidas'}}" class="btn-texto">{{ soloSeguidas ? 'Ver todas las comunidades' : 'Mis comunidades' }}</router-link>
        </div>
        <p v-if="soloSeguidas && !categoriasVisibles.length" class="foro-vacio">Aún no sigues comunidades. Consulta todas para elegir las tuyas.</p>
        <section v-if="comunidad" class="panel-lateral comunidad-resumen">
          <h2>{{ comunidad.nombre }}</h2>
          <p>{{ comunidad.descripcion }}</p>
          <div class="tarjeta-acciones"><span>{{ comunidad.seguidores }} miembros · {{ comunidad.publicaciones }} publicaciones</span>
            <button type="button" class="btn-secundario" :disabled="siguiendo" :aria-pressed="comunidad.siguiendo" @click="seguirComunidad()">{{ comunidad.siguiendo ? 'Dejar de seguir' : 'Unirme a la comunidad' }}</button>
          </div>
        </section>
        <p v-if="errorComunidad" class="error" role="alert">{{ errorComunidad }}</p>

        <section v-if="mostrarFormulario" class="foro-formulario editor-publicacion" aria-label="Nueva pregunta">
          <div class="editor-cabecera"><div><h2>Crear publicación</h2><p class="nota-demo">Comparte una pregunta, recurso o conversación con la comunidad.</p></div><button class="btn-icono" type="button" aria-label="Cerrar editor" :disabled="enviando" @click="cancelarFormulario"><IconoForo nombre="cerrar"/></button></div>
          <form @submit.prevent="publicarPregunta">
            <div class="editor-destinos">
            <label>
              Categoría
              <select v-model="idCategoriaNueva" :disabled="enviando" @change="actualizarCategoriaDestino">
                <option value="" disabled>Elige una categoría</option>
                <option v-for="cat in categorias" :key="cat.id" :value="String(cat.id)">
                  {{ cat.nombre }}
                </option>
              </select>
            </label>
            <label>Comunidad (opcional)<select v-model="idComunidadNueva" :disabled="enviando" @change="actualizarDestino"><option :value="null">Foro general</option><option v-for="c in destinos" :key="c.id" :value="c.id">{{c.nombre}}</option></select></label>
            </div>
            <div class="editor-tipos" role="group" aria-label="Tipo de publicación"><button v-for="t in tiposEditor" :key="t.id" type="button" :aria-pressed="tipoEditor===t.id" :disabled="enviando" @click="tipoNuevo=t.id==='multimedia'&&tipoNuevo==='imagen'?'imagen':t.id"><IconoForo :nombre="t.icono"/>{{t.nombre}}</button></div>
            <label>
              Título
              <input ref="tituloPublicacion" v-model="tituloNuevo" type="text" maxlength="200" placeholder="Escribe un título claro" />
            </label>
            <label>
              Contenido
              <textarea v-model="contenidoNuevo" rows="4" :maxlength="limiteContenido" placeholder="¿Qué quieres compartir?"></textarea><small>Para mencionar a alguien, escribe @ seguido del ID de su perfil (ej. @23).</small>
            </label>
            <p class="ayuda-limite">{{ contenidoNuevo.length }} / {{ limiteContenido }} caracteres.</p>
            <label>Etiqueta académica<select v-model="etiquetaNueva"><option value="">Sin etiqueta</option><option v-for="e in etiquetas" :key="e" :value="e">{{e}}</option></select></label>
            <div v-if="tipoEditor==='multimedia'" class="ux-segmentos" role="group" aria-label="Origen de la imagen"><button type="button" :aria-pressed="tipoNuevo==='multimedia'" :disabled="enviando" @click="tipoNuevo='multimedia'">Dispositivo</button><button type="button" :aria-pressed="tipoNuevo==='imagen'" :disabled="enviando" @click="tipoNuevo='imagen'">URL HTTPS</button></div>
            <label v-if="tipoNuevo === 'imagen' || tipoNuevo === 'enlace'">URL HTTPS
              <input v-model="recursoNuevo" type="url" maxlength="2048" placeholder="https://" />
            </label>
            <CargaMultimedia v-show="tipoNuevo==='multimedia'" :key="'imagen-'+claveCarga" ref="cargaImagenes" tipo="multimedia" :bloqueado="enviando" @cambio="archivosImagen=$event"/>
            <CargaMultimedia v-show="tipoNuevo==='video'" :key="'video-'+claveCarga" ref="cargaVideo" tipo="video" :bloqueado="enviando" @cambio="archivosVideo=$event"/>
            <template v-if="tipoNuevo === 'encuesta'">
              <label v-for="(_, i) in opcionesNuevas" :key="i">Opción {{ i + 1 }}
                <input v-model="opcionesNuevas[i]" maxlength="100" />
              </label>
              <div class="acciones-form">
                <button type="button" class="btn-texto" :disabled="opcionesNuevas.length >= 6" @click="opcionesNuevas.push('')">Añadir opción</button>
                <button type="button" class="btn-texto" :disabled="opcionesNuevas.length <= 2" @click="opcionesNuevas.pop()">Quitar última opción</button>
              </div>
            </template>
            <p v-if="errorFormulario" class="error" role="alert">{{ errorFormulario }}</p>
            <div class="editor-acciones"><details class="editor-borradores"><summary class="btn-secundario">Borrador{{borradorGuardado?' guardado':''}} <IconoForo nombre="guardados"/></summary><div class="editor-borradores-menu"><button type="button" class="btn-texto" :disabled="enviando" @click="gestionarBorrador('guardar')">Guardar borrador</button><button type="button" class="btn-texto" :disabled="enviando" @click="gestionarBorrador('recuperar')">Recuperar borrador</button><button type="button" class="btn-texto" :disabled="enviando" @click="gestionarBorrador('descartar')">Descartar borrador</button><small>Los archivos locales no forman parte del borrador guardado.</small></div></details><span class="ux-flex-spacer"></span><button type="button" class="btn-texto" :disabled="enviando" @click="cancelarFormulario">Cancelar</button><button type="submit" class="btn-primario btn-ancho-auto" :disabled="enviando">{{ enviando ? 'Publicando…' : 'Publicar' }}</button></div>
          </form>
        </section>


        <section v-if="explorar" class="panel-lateral"><h2>Explorar categorías</h2><router-link to="/comunidades">Explorar comunidades creadas por usuarios</router-link><p>Encuentra comunidades relacionadas con tus intereses académicos.</p><div class="comunidades-rejilla"><article v-for="c in categorias" :key="c.id"><router-link :to="{path:'/',query:{categoria:String(c.id)}}"><strong>{{c.nombre}}</strong></router-link><p>{{c.descripcion}}</p><p class="nota-demo">{{c.seguidores}} miembros · {{c.publicaciones}} publicaciones</p><button class="btn-secundario" :disabled="siguiendo" @click="seguirComunidad(c)">{{c.siguiendo?'Dejar de seguir':'Seguir'}}</button></article></div></section>
        <div class="feed-toolbar" aria-label="Controles de publicaciones">
          <div class="feed-tabs" role="group" aria-label="Vista del feed">
            <button v-for="v in [{id:'todas',nombre:'Para ti'},{id:'personalizado',nombre:'Siguiendo'}]" :key="v.id" type="button" :class="{'feed-tab-activo':vista===v.id}" :aria-pressed="vista===v.id" @click="cambiarFeed(v.id)">{{v.nombre}}</button>
          </div>
          <div class="feed-herramientas">
            <select v-model="orden" aria-label="Orden de publicaciones"><option value="para_ti">Recomendadas</option><option value="reciente">Recientes</option><option value="antiguo">Antiguas</option><option value="popular">Popularidad</option><option value="tendencias">Tendencias</option><option value="relevancia">Relevancia</option></select>
            <details class="feed-menu"><summary title="Filtros" aria-label="Filtros"><IconoForo nombre="filtros"/><span v-if="filtrosActivos">{{filtrosActivos}}</span></summary><div class="feed-menu-panel">
              <label>Etiqueta<select v-model="etiqueta"><option value="">Todas</option><option v-for="e in etiquetas" :key="e" :value="e">{{e}}</option></select></label>
              <label>Tipo<select v-model="tipoFiltro"><option value="">Todos</option><option v-for="t in ['texto','imagen','enlace','encuesta','multimedia','video']" :key="t" :value="t">{{t}}</option></select></label>
              <label>Estado<select v-model="estado"><option value="">Todos</option><option value="resuelta">Resueltas</option><option value="pendiente">Pendientes</option></select></label>
              <button type="button" class="btn-texto" @click="restablecerFiltros">Restablecer filtros</button>
            </div></details>
            <details class="feed-menu"><summary title="Cambiar visualización" aria-label="Cambiar visualización"><IconoForo :nombre="densidad"/>⌄</summary><div class="feed-menu-panel"><button v-for="d in ['tarjetas','compacta']" :key="d" type="button" class="btn-texto" :aria-pressed="densidad===d" @click="densidad=d;$event.currentTarget.closest('details').open=false"><IconoForo :nombre="d"/> {{d==='tarjetas'?'Tarjetas':'Compacta'}}</button></div></details>
          </div>
        </div>
        <p class="aviso-exito" role="status" aria-live="polite">{{ mensajeExito }}</p>


        
        <div v-if="cargando && !preguntas.length" role="status" aria-label="Cargando publicaciones"><div v-for="n in 3" :key="n" class="skeleton-tarjeta"><i></i><i></i><i></i></div></div>
        <p v-else-if="errorLista && !preguntas.length" class="error foro-estado" role="alert" aria-live="assertive">
          {{ errorLista }} <button type="button" class="btn-texto" @click="cargarPreguntas()">Reintentar</button>
        </p>
        <p v-else-if="preguntas.length === 0" class="foro-vacio">
          {{vista==='personalizado'?'No hay publicaciones de tus seguimientos. Sigue usuarios o categorías para verlas aquí.':'No hay publicaciones que coincidan con estos filtros.'}}
          <template v-if="autenticado">Prueba otros filtros o usa <strong>Crear publicación</strong>.</template>
          <template v-else>Cuando alguien publique, podrás leerla aquí.</template>
        </p>

        <ul v-else class="foro-lista feed-lista" :class="`feed-${densidad}`">
          <li
            v-for="pregunta in preguntas"
            :key="pregunta.id"
            class="tarjeta-pregunta"
            :class="{ 'tarjeta-nueva': pregunta.id === idNuevo }"
          >
            <div class="tarjeta-tope feed-cabecera">
              <router-link class="insignia" :to="pregunta.comunidad_slug?`/comunidades/${pregunta.comunidad_slug}`:{path:'/',query:{categoria:String(pregunta.id_categoria)}}">{{ pregunta.nombre_comunidad || pregunta.nombre_categoria }}</router-link>

            <div class="tarjeta-meta feed-autor"><AvatarUsuario :nombre="pregunta.nombre_autor" :url="pregunta.avatar_autor" chico/><router-link :to="`/usuarios/${pregunta.id_usuario}`">{{pregunta.nombre_autor}}</router-link><span>·</span><time :datetime="pregunta.fecha_creacion">{{formatearFecha(pregunta.fecha_creacion)}}</time></div></div>
            <h2>
              <router-link :to="`/preguntas/${pregunta.id}`">{{ pregunta.titulo }}</router-link>
              <span v-if="pregunta.fijada" class="insignia">Fijada</span><span v-if="pregunta.cerrada" class="insignia">Cerrada</span>
            </h2>
            <div class="feed-cuerpo"><p class="tarjeta-extracto">{{ pregunta.contenido }}</p>
            <img v-if="pregunta.tipo==='imagen' && pregunta.recurso_url" class="feed-imagen" :src="pregunta.recurso_url" alt="Imagen de la publicación" loading="lazy" referrerpolicy="no-referrer" /></div>
            <MultimediaPublicacion v-if="['multimedia','video'].includes(pregunta.tipo)" :id="pregunta.id"/><router-link v-if="pregunta.tipo==='enlace' && pregunta.recurso_url" :to="`/preguntas/${pregunta.id}`" class="feed-enlace">Ver enlace</router-link><router-link v-if="pregunta.tipo==='encuesta'" :to="`/preguntas/${pregunta.id}`" class="btn-texto">Ver encuesta</router-link>
            <span v-if="pregunta.etiqueta" class="insignia etiqueta-contenido">{{pregunta.etiqueta}}</span>
            <span v-if="pregunta.tipo !== 'texto'" class="insignia">{{ pregunta.tipo }}</span>
            <span v-if="pregunta.id_respuesta_aceptada" class="insignia">Resuelta</span>
            <div class="tarjeta-acciones acciones-publicacion">
              <div class="feed-votos"><button type="button" :class="pregunta.mi_voto === 1 ? 'chip chip-activo' : 'btn-voto'" :aria-pressed="pregunta.mi_voto === 1" :disabled="pregunta.votando" @click="votar(pregunta, 1)" aria-label="Voto positivo">↑</button>
              <span class="voto-puntos" :aria-label="`${pregunta.total_votos} puntos`">{{ pregunta.total_votos }}</span>
              <button type="button" :class="pregunta.mi_voto === -1 ? 'chip chip-activo' : 'btn-voto'" :aria-pressed="pregunta.mi_voto === -1" :disabled="pregunta.votando" @click="votar(pregunta, -1)" aria-label="Voto negativo">↓</button></div>
              <button type="button" class="btn-texto" @click="participar(pregunta)">{{textoRespuestas(pregunta.cantidad_respuestas)}}</button>
              <button type="button" class="btn-texto" :aria-pressed="!!pregunta.guardada" :disabled="pregunta.gestionando" @click="preferencia(pregunta,'guardar')">{{pregunta.guardada ? 'Quitar de guardadas' : 'Guardar'}}</button>
              <button type="button" class="btn-texto" @click="compartirFeed(pregunta)">Compartir</button>
              <details class="acciones-contexto"><summary title="Más acciones" aria-label="Más acciones">•••</summary>
              <div class="feed-menu-panel"><router-link v-if="puedeEditar(pregunta)" class="btn-texto" :to="{path:`/preguntas/${pregunta.id}`,query:{editar:'1'}}">Editar</router-link><button v-if="puedeEditar(pregunta)" class="btn-texto" :disabled="pregunta.gestionando" @click="accionPublicacion(pregunta,'eliminar')">Eliminar</button><template v-if="usuario?.rol==='admin'"><button class="btn-texto" :disabled="pregunta.gestionando" @click="accionPublicacion(pregunta,'fijada')">{{pregunta.fijada?'Desfijar':'Fijar'}}</button><button class="btn-texto" :disabled="pregunta.gestionando" @click="accionPublicacion(pregunta,'cerrada')">{{pregunta.cerrada?'Reabrir':'Cerrar'}}</button></template>
              <button type="button" class="btn-texto" :aria-pressed="!!pregunta.oculta" :disabled="pregunta.gestionando" @click="preferencia(pregunta,'ocultar')">{{pregunta.oculta ? 'Mostrar de nuevo' : 'Ocultar'}}</button>
              <ReportarContenido tipo="pregunta" :identificador="pregunta.id" :autor="pregunta.id_usuario" /></div>
              </details>
            </div>
            <p v-if="pregunta.aviso" class="error aviso-tarjeta" role="alert">{{ pregunta.aviso }}</p>
          </li>
        </ul>
        <p v-if="errorLista && preguntas.length" class="error" role="alert">{{ errorLista }}</p>
        <button v-if="hayMas" type="button" class="btn-texto" :disabled="cargando" @click="cargarPreguntas(true)">
          {{ cargando ? 'Cargando…' : 'Cargar más preguntas' }}
        </button>
      </div>

      <aside class="home-lateral" aria-label="Ranking y participación">
        <section class="panel-lateral"><h2>Comunidades de usuarios</h2><p v-if="errorNuevas" class="error">{{errorNuevas}}</p><article v-for="c in comunidadesNuevas.slice(0,5)" :key="c.id" class="sugerencia"><router-link :to="`/comunidades/${c.slug}`">{{c.nombre}}</router-link><p class="nota-demo">{{c.miembros}} miembros</p></article><router-link to="/comunidades">Ver todas</router-link></section><section class="panel-lateral"><h2>Categorías sugeridas</h2><p v-if="!categorias.some(c=>!c.siguiendo)" class="nota-demo">No hay nuevas categorías sugeridas.</p><article v-for="c in categorias.filter(c=>!c.siguiendo).slice(0,5)" :key="c.id" class="sugerencia"><router-link :to="{path:'/',query:{categoria:String(c.id)}}"><strong>{{c.nombre}}</strong></router-link><p class="nota-demo">{{c.publicaciones}} publicaciones · {{c.seguidores}} miembros</p><button class="btn-secundario" :disabled="siguiendo" @click="seguirComunidad(c)">Seguir</button></article><router-link to="/?explorar=1" class="btn-texto">Explorar todas</router-link></section>
        <section class="panel-lateral">
          <header class="panel-encabezado">
            <h2>Ranking</h2>
            <p class="nota-demo">Karma de votos recibidos. Una estrella por cada 10 puntos (máximo 5).</p>
          </header>
          <p v-if="errorRanking" class="error" role="alert">{{ errorRanking }}</p>
          <p v-if="!ranking.length && !errorRanking" class="nota-demo">Aún no hay usuarios en el ranking.</p>
          <ol class="ranking">
            <li v-for="(persona, indice) in ranking" :key="persona.id">
              <span class="ranking-puesto">{{ indice + 1 }}</span>
              <AvatarUsuario :nombre="persona.nombre_apellido" :url="persona.avatar_url" chico />
              <span class="ranking-datos">
                <router-link class="ranking-nombre" :to="`/usuarios/${persona.id}`">{{ persona.nombre_apellido }}</router-link>
                <span v-if="persona.karma >= 10" class="estrellas" :aria-label="`${Math.min(5,Math.floor(Math.max(0,persona.karma)/10))} de 5 estrellas`">
                  <span
                    v-for="n in 5"
                    :key="n"
                    :class="{ 'estrella-activa': n <= Math.min(5,Math.floor(Math.max(0,persona.karma)/10)) }"
                  >★</span>
                </span>
              </span>
              <span class="ranking-puntos" :aria-label="`${persona.karma} puntos de karma`">{{ persona.karma }}</span>
            </li>
          </ol>
        </section>

        <section class="promo-premium">
          <p class="insignia">Acceso gratuito</p>
          <h2>Más espacio para preguntar</h2>
          <p>Todos los usuarios pueden publicar hasta {{ limiteContenido }} caracteres sin pagar.</p>
          <router-link to="/premium" class="btn-secundario">Ver participación</router-link>
        </section>
      </aside>
    </div>
  </main>
</template>
