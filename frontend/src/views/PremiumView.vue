<script setup>
import { ref } from 'vue'
import { activarPremiumDemo, LIMITE_GRATIS, LIMITE_PREMIUM, plan, quitarPremiumDemo } from '../services/sesion.js'

const ciclo = ref('mes')
const medio = ref('tarjeta')
const aviso = ref('')

const precios = {
  mes: '$4.99 / mes',
  anio: '$49.99 / año',
}

function confirmar() {
  activarPremiumDemo()
  const medioTexto = medio.value === 'paypal' ? 'PayPal' : 'tarjeta'
  aviso.value = `Plan Premium de demostración activo con ${medioTexto} (${precios[ciclo.value]}). No se realizó ningún cobro.`
}

function volverGratis() {
  quitarPremiumDemo()
  aviso.value = 'Volviste al plan gratuito en este navegador.'
}
</script>

<template>
  <main class="pagina">
    <header class="pagina-encabezado">
      <h1>Planes</h1>
      <p>Leer, preguntar y votar sigue disponible en el plan gratuito. Premium solo amplía la participación.</p>
      <p class="nota-demo">Demostración: no se realiza ningún cobro. El plan se guarda solo en este navegador.</p>
    </header>

    <div class="ciclo" role="group" aria-label="Periodo de la suscripción">
      <button type="button" :class="{ 'ciclo-activo': ciclo === 'mes' }" @click="ciclo = 'mes'">Mensual</button>
      <button type="button" :class="{ 'ciclo-activo': ciclo === 'anio' }" @click="ciclo = 'anio'">Anual</button>
    </div>

    <div class="rejilla-planes">
      <article class="plan">
        <h2>Gratis</h2>
        <p class="plan-precio">$0</p>
        <ul>
          <li>Leer preguntas, respuestas y comentarios</li>
          <li>Publicar, votar y comentar con cuenta</li>
          <li>Preguntas de hasta {{ LIMITE_GRATIS }} caracteres</li>
        </ul>
        <button
          v-if="plan === 'premium'"
          type="button"
          class="btn-secundario"
          @click="volverGratis"
        >
          Volver al plan gratuito
        </button>
        <p v-else class="nota-demo">Este es tu plan actual.</p>
      </article>

      <article class="plan plan-destacado">
        <p class="insignia insignia-premium">Premium</p>
        <h2>Premium</h2>
        <p class="plan-precio">{{ precios[ciclo] }}</p>
        <ul>
          <li>Todo lo del plan gratuito</li>
          <li>Preguntas de hasta {{ LIMITE_PREMIUM }} caracteres</li>
          <li>Distintivo Premium junto a tu nombre</li>
        </ul>
        <p v-if="plan === 'premium'" class="nota-demo">Activo en este navegador.</p>
      </article>
    </div>

    <form v-if="plan !== 'premium'" class="pago-demo" @submit.prevent="confirmar">
      <fieldset>
        <legend>Forma de pago de demostración</legend>
        <label class="opcion-pago">
          <input v-model="medio" type="radio" value="tarjeta" />
          Tarjeta
        </label>
        <label class="opcion-pago">
          <input v-model="medio" type="radio" value="paypal" />
          PayPal
        </label>
      </fieldset>
      <button type="submit" class="btn-premium">Activar Premium de demostración</button>
    </form>

    <p v-if="aviso" class="aviso-exito" role="status">{{ aviso }}</p>
  </main>
</template>
