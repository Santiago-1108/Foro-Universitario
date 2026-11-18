<script setup>
import { ref } from 'vue'
import { useRoute } from 'vue-router'
import { apiFetch } from '../services/api.js'
import { destinoSeguro, guardarSesion } from '../services/sesion.js'

const route = useRoute()
const correo = ref('')
const password = ref('')
const error = ref('')
const cargando = ref(false)
// Solo interfaz: alterna el tipo del campo de contraseña
const mostrarPassword = ref(false)

async function ingresar() {
  error.value = ''

  if (!correo.value.trim() || !password.value) {
    error.value = 'El correo y la contraseña son obligatorios'
    return
  }

  cargando.value = true
  try {
    // POST /auth/login en el servicio de usuarios. Respuesta: { token, usuario }
    const datos = await apiFetch('usuarios', '/auth/login', {
      method: 'POST',
      body: JSON.stringify({
        correo: correo.value,
        password: password.value,
      }),
    })

    guardarSesion(datos.token, datos.usuario)
    window.location.assign(destinoSeguro(route.query.redirect))
  } catch (e) {
    error.value = e.message
  } finally {
    cargando.value = false
  }
}
</script>

<template>
  <main class="login-pantalla">
    <aside class="login-panel">
      <p class="login-marca">Foro universitario</p>
      <p class="login-lema">Pregunta, responde y aprende con tu comunidad</p>
    </aside>

    <section class="login-columna">
      <div class="login-tarjeta">
        <h1>Iniciar sesión</h1>
        <p class="login-apoyo">Ingresa para publicar, votar y comentar. Leer el foro no requiere cuenta.</p>

        <form @submit.prevent="ingresar">
          <label>
            Correo
            <input v-model="correo" type="email" autocomplete="username" />
          </label>

          <label>
            Contraseña
            <div class="campo-clave">
              <input
                v-model="password"
                :type="mostrarPassword ? 'text' : 'password'"
                autocomplete="current-password"
              />
              <button
                type="button"
                class="btn-texto"
                :aria-pressed="mostrarPassword"
                @click="mostrarPassword = !mostrarPassword"
              >
                <!-- Ojo simple: abierto o tachado según el estado -->
                <svg class="icono-ojo" viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z" />
                  <circle cx="12" cy="12" r="3" />
                  <path v-if="mostrarPassword" d="M4 20 L20 4" />
                </svg>
                {{ mostrarPassword ? 'Ocultar' : 'Mostrar' }}
              </button>
            </div>
          </label>

          <p v-if="error" class="error" role="alert">{{ error }}</p>

          <button type="submit" class="btn-primario" :disabled="cargando">
            {{ cargando ? 'Ingresando…' : 'Ingresar al foro' }}
          </button>
        </form>

        <p class="login-pie">
          <router-link :to="{ path: '/registro', query: route.query }">Crear cuenta</router-link>
          <router-link to="/">Ver preguntas sin cuenta</router-link>
        </p>
      </div>
    </section>
  </main>
</template>
