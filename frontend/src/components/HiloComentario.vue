<script setup>
import ReportarContenido from './ReportarContenido.vue'
import AvatarUsuario from './AvatarUsuario.vue'
import { ref } from 'vue'
import { apiFetch } from '../services/api.js'
import { exigirSesion } from '../services/sesion.js'
import { formatearFecha } from '../utils/formato.js'
const props = defineProps({ comentario: {type:Object, required:true}, nivel:{type:Number, default:0}, cerrada:{type:Boolean,default:false} })
const emit = defineEmits(['creado'])
const abierto = ref(false), colapsado = ref(false), texto = ref(''), aviso = ref(''), ocupado = ref(false)
async function responder() {
  if (props.cerrada || ocupado.value || !exigirSesion('Inicia sesión para responder.')) return
  ocupado.value = true; aviso.value = ''
  try {
    const nuevo = await apiFetch('interacciones','/comentarios',{method:'POST',body:JSON.stringify({id_respuesta:props.comentario.id_respuesta,id_comentario_padre:props.comentario.id,contenido:texto.value})})
    emit('creado',nuevo); texto.value = ''; abierto.value = false; colapsado.value = false
  } catch(e) { aviso.value = e.message }
  finally { ocupado.value = false }
}
</script>
<template>
  <li class="hilo-comentario" :id="`comentario-${comentario.id}`">
    <p>{{ comentario.contenido }}</p>
    <p v-if="!comentario.eliminado" class="tarjeta-meta">
      <AvatarUsuario :nombre="comentario.nombre_autor" :url="comentario.avatar_autor" chico /><router-link :to="`/usuarios/${comentario.id_usuario}`">{{ comentario.nombre_autor }}</router-link><span aria-hidden="true">·</span>
      <time :datetime="comentario.fecha_creacion">{{ formatearFecha(comentario.fecha_creacion) }}</time>
    </p>
    <div class="tarjeta-acciones">
      <button v-if="!comentario.eliminado && !cerrada" type="button" class="btn-texto" :aria-expanded="abierto" @click="exigirSesion('Inicia sesión para responder.') && (abierto = !abierto)">Responder</button>
      <button v-if="comentario.hijos.length" type="button" class="btn-texto" :aria-expanded="!colapsado" @click="colapsado = !colapsado">{{ colapsado ? 'Mostrar' : 'Ocultar' }} hilo ({{ comentario.hijos.length }})</button>
    </div>
    <ReportarContenido v-if="!comentario.eliminado" tipo="comentario" :identificador="comentario.id" :autor="comentario.id_usuario" />
    <form v-if="abierto && !cerrada" class="form-comentario" @submit.prevent="responder">
      <label>Respuesta al comentario<textarea v-model="texto" rows="2" maxlength="2000" required></textarea><small>Para mencionar a alguien, escribe @ seguido del ID de su perfil (ej. @23).</small></label>
      <button type="submit" class="btn-primario btn-ancho-auto" :disabled="ocupado">Publicar respuesta</button>
    </form>
    <p v-if="aviso" class="error" role="alert">{{ aviso }}</p>
    <ul v-if="!colapsado && comentario.hijos.length" class="lista-comentarios" :style="{paddingLeft:nivel < 5 ? '12px' : '0'}">
      <HiloComentario v-for="hijo in comentario.hijos" :key="hijo.id" :comentario="hijo" :nivel="nivel + 1" :cerrada="cerrada" @creado="emit('creado',$event)" />
    </ul>
  </li>
</template>
