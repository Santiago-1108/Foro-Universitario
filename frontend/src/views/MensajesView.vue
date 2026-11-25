<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { apiFetch } from '../services/api.js'
import { autenticado, usuario } from '../services/sesion.js'
import { formatearFecha } from '../utils/formato.js'
import AvatarUsuario from '../components/AvatarUsuario.vue'

const route = useRoute()
const otro = computed(() => typeof route.params.id === 'string' ? route.params.id : '')
const conversaciones = ref([]), mensajes = ref([]), contacto = ref(null), siguiente = ref(null)
const texto = ref(''), error = ref(''), cargando = ref(false), enviando = ref(false), leyendo = ref(false)
const paginasExtra = ref(false), totalPendientes = ref(0)
let version = 0, timer, controlador
const ruta = () => `/mensajes${otro.value ? '/' + encodeURIComponent(otro.value) : ''}`
const actual = (v, token) => v === version && autenticado.value && token === localStorage.getItem('token')
const avisar = () => window.dispatchEvent(new Event('mensajes-actualizados'))

async function cargar(mas = false, silencioso = false) {
  if (!autenticado.value || cargando.value || enviando.value || leyendo.value || (mas && !siguiente.value)) return
  const v = version, token = localStorage.getItem('token'), esHilo = Boolean(otro.value)
  const base = ruta(), ctrl = new AbortController(); controlador = ctrl
  cargando.value = true; if (!silencioso) error.value = ''
  try {
    const r = await apiFetch('usuarios', `${base}?limite=30${mas ? '&antes=' + encodeURIComponent(siguiente.value) : ''}`, {signal:ctrl.signal})
    if (!actual(v,token)) return
    error.value = ''
    if (esHilo) {
      contacto.value = r.contacto
      mensajes.value = mas ? [...r.mensajes.filter(m => !mensajes.value.some(x=>x.id===m.id)), ...mensajes.value] : r.mensajes
    } else {
      totalPendientes.value = r.pendientes
      conversaciones.value = mas ? [...conversaciones.value, ...r.conversaciones.filter(c=>!conversaciones.value.some(x=>x.id_usuario===c.id_usuario))] : r.conversaciones
    }
    siguiente.value = r.siguiente
    paginasExtra.value = mas || (silencioso && paginasExtra.value)
  } catch (e) {
    if (actual(v,token) && e.name !== 'AbortError') {
      error.value = e.message
      if (e.status === 403 || e.status === 404) { contacto.value=null; mensajes.value=[]; conversaciones.value=[]; siguiente.value=null }
    }
  } finally { if (actual(v,token)) cargando.value = false; if (controlador===ctrl) controlador=null }
}

async function marcarLectura() {
  const ultimo = mensajes.value.at(-1)
  if (!ultimo || !contacto.value || leyendo.value || cargando.value || enviando.value || !autenticado.value) return
  const v = version, token = localStorage.getItem('token'), base = ruta()
  leyendo.value=true; error.value=''
  try {
    await apiFetch('usuarios', `${base}/leer`, {method:'PUT',body:JSON.stringify({hasta:ultimo.id})})
    if (!actual(v,token)) return
    mensajes.value = mensajes.value.map(m=>m.propio ? m : {...m,leido:true})
    avisar()
  } catch(e) { if(actual(v,token)) { error.value=e.message; if(e.status===403||e.status===404){contacto.value=null;mensajes.value=[];siguiente.value=null} } }
  finally { if(actual(v,token)) leyendo.value=false }
}

async function enviar() {
  if (!autenticado.value || enviando.value || cargando.value || leyendo.value || !contacto.value || contacto.value.suspendido || !texto.value.trim()) return
  const v=version, token=localStorage.getItem('token'), base=ruta(), contenido=texto.value
  enviando.value=true; error.value=''
  let enviado=false
  try {
    await apiFetch('usuarios',base,{method:'POST',body:JSON.stringify({contenido})})
    if (!actual(v,token)) return
    texto.value=''; enviado=true
  } catch(e) { if(actual(v,token)) {error.value=e.message; if(e.status===403||e.status===404){contacto.value=null;mensajes.value=[];siguiente.value=null}} }
  finally { if(actual(v,token)) enviando.value=false }
  if (enviado && actual(v,token)) { await cargar(); avisar() }
}

function reiniciar() {
  version++; controlador?.abort(); controlador=null
  conversaciones.value=[]; mensajes.value=[]; contacto.value=null; siguiente.value=null
  texto.value=''; error.value=''; cargando.value=false; enviando.value=false; leyendo.value=false; paginasExtra.value=false; totalPendientes.value=0
  cargar()
}
function refrescar() { if(document.visibilityState==='visible' && !paginasExtra.value) cargar(false,true) }
watch([otro,()=>usuario.value],reiniciar,{immediate:true,flush:'sync'})
onMounted(()=>{timer=window.setInterval(refrescar,60000);document.addEventListener('visibilitychange',refrescar)})
onUnmounted(()=>{version++;controlador?.abort();window.clearInterval(timer);document.removeEventListener('visibilitychange',refrescar)})
</script>

<template>
  <main class="pagina foro-contenido pagina-mensajes">
    <router-link :to="otro ? '/mensajes' : '/'" class="btn-texto enlace-volver">{{ otro ? 'Volver a mensajes' : 'Volver al inicio' }}</router-link>
    <h1>Mensajes privados</h1>
    <template v-if="!autenticado">
      <p class="foro-estado">Inicia sesión para acceder a tu bandeja privada.</p>
      <router-link :to="{path:'/login',query:{redirect:route.fullPath}}" class="btn-primario btn-ancho-auto">Iniciar sesión</router-link>
    </template>
    <template v-else>
      <p v-if="error" class="error" role="alert">{{ error }}</p>
      <div class="tarjeta-acciones">
        <button type="button" class="btn-secundario" :disabled="cargando || enviando || leyendo" @click="cargar()">Actualizar</button>
        <router-link v-if="!otro" to="/" class="btn-texto">Buscar usuarios en el foro</router-link>
        <span v-if="!otro" class="insignia">{{ totalPendientes }} sin leer</span>
      </div>
      <p v-if="cargando" class="foro-estado" role="status">Cargando mensajes…</p>
      <template v-if="!otro">
        <p v-if="!cargando && !error && !conversaciones.length" class="foro-vacio">No tienes conversaciones. Abre el perfil de otro usuario y selecciona Enviar mensaje.</p>
        <ul class="foro-lista bandeja-mensajes">
          <li v-for="c in conversaciones" :key="c.id_usuario" class="tarjeta-pregunta conversacion-resumen" :class="{'conversacion-nueva': c.pendientes > 0}">
            <div class="tarjeta-meta"><AvatarUsuario :nombre="c.nombre_apellido" :url="c.avatar_url" chico/><router-link :to="`/mensajes/${c.id_usuario}`" class="foro-nombre">{{c.nombre_apellido}}</router-link><span v-if="c.pendientes" class="insignia">{{c.pendientes}} sin leer</span><span v-if="c.suspendido" class="insignia">Suspendido</span></div>
            <p class="tarjeta-extracto">{{ c.ultimo.propio ? 'Tú: ' : '' }}{{ c.ultimo.contenido }}</p>
            <time class="tarjeta-meta" :datetime="c.ultimo.fecha_creacion">{{formatearFecha(c.ultimo.fecha_creacion)}}</time>
          </li>
        </ul>
        <button v-if="siguiente" class="btn-secundario" type="button" :disabled="cargando" @click="cargar(true)">Cargar más conversaciones</button>
      </template>
      <template v-else-if="contacto">
        <section class="tarjeta-pregunta">
          <div class="tarjeta-meta"><AvatarUsuario :nombre="contacto.nombre_apellido" :url="contacto.avatar_url"/><router-link :to="`/usuarios/${contacto.id}`" class="foro-nombre">{{contacto.nombre_apellido}}</router-link></div>
          <p v-if="contacto.suspendido" class="foro-estado">Cuenta suspendida. Puedes consultar el historial, pero no enviar mensajes.</p>
          <div class="tarjeta-acciones"><button type="button" class="btn-texto" :disabled="!mensajes.length || cargando || enviando || leyendo" @click="marcarLectura">Marcar como leídos hasta el último mensaje visible</button></div>
        </section>
        <button v-if="siguiente" class="btn-secundario" type="button" :disabled="cargando || enviando || leyendo" @click="cargar(true)">Cargar mensajes anteriores</button>
        <p v-if="!mensajes.length && !cargando" class="foro-vacio">Todavía no hay mensajes. Inicia la conversación.</p>
        <ul class="foro-lista historial-mensajes" aria-label="Historial de mensajes">
          <li v-for="m in mensajes" :key="m.id" class="tarjeta-pregunta burbuja-mensaje" :class="{'mensaje-propio':m.propio}">
            <div class="tarjeta-meta"><strong>{{m.propio ? 'Tú' : contacto.nombre_apellido}}</strong><time :datetime="m.fecha_creacion">{{formatearFecha(m.fecha_creacion)}}</time><span v-if="!m.propio && !m.leido" class="insignia">Nuevo</span></div>
            <p class="lectura-contenido" style="overflow-wrap:anywhere">{{m.contenido}}</p>
          </li>
        </ul>
        <form v-if="!contacto.suspendido" class="foro-formulario mensaje-editor" @submit.prevent="enviar">
          <label for="mensaje-contenido">Escribir mensaje</label>
          <textarea id="mensaje-contenido" v-model="texto" maxlength="2000" rows="4" required :disabled="enviando" placeholder="Escribe tu mensaje…"></textarea>
          <span class="tarjeta-meta">{{texto.length}} / 2000</span>
          <button type="submit" class="btn-primario btn-ancho-auto" :disabled="!texto.trim() || enviando || cargando || leyendo">{{enviando ? 'Enviando…' : 'Enviar mensaje'}}</button>
        </form>
      </template>
    </template>
  </main>
</template>
