<script setup>
import { ref } from 'vue'
import { useRoute } from 'vue-router'
import { apiFetch } from '../services/api.js'
import { destinoSeguro, guardarSesion } from '../services/sesion.js'

const route = useRoute()

const nombre = ref('')
const correo = ref('')
const password = ref('')
const error = ref('')
const cargando = ref(false)
const mostrarPassword = ref(false)

async function crearCuenta() {
  error.value = ''
  if (!nombre.value.trim() || !correo.value.trim() || !password.value) {
    error.value = 'El nombre, el correo y la contraseña son obligatorios'
    return
  }

  if (password.value.length < 8 || !password.value.trim()) {
    error.value = 'La contraseña debe tener al menos 8 caracteres.'
    return
  }
  cargando.value = true
  try {
    await apiFetch('usuarios', '/auth/registro', {
      method: 'POST',
      body: JSON.stringify({
        nombre_apellido: nombre.value,
        correo: correo.value,
        password: password.value,
      }),
    })
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
      <p class="login-lema">Crea tu cuenta para preguntar, votar y comentar.</p>
    </aside>

    <section class="login-columna">
      <div class="login-tarjeta">
        <h1>Crear cuenta</h1>
        <p class="login-apoyo">El registro te deja participar. Leer el foro no la necesita.</p>

        <form @submit.prevent="crearCuenta">
          <label>
            Nombre y apellido
            <input v-model="nombre" type="text" autocomplete="name" />
          </label>
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
                autocomplete="new-password"
              />
              <button
                type="button"
                class="btn-texto"
                :aria-pressed="mostrarPassword"
                @click="mostrarPassword = !mostrarPassword"
              >
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
            {{ cargando ? 'Creando cuenta…' : 'Crear cuenta' }}
          </button>
        </form>

        <p class="login-pie">
          <router-link :to="{ path: '/login', query: route.query }">Ya tengo cuenta</router-link>
          <router-link to="/">Ver preguntas sin cuenta</router-link>
        </p>
      </div>
    </section>
  </main>
</template>
