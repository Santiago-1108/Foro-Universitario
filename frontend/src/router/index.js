import { createRouter, createWebHistory } from 'vue-router'
import BuscarView from '../views/BuscarView.vue'
import ComunidadesView from '../views/ComunidadesView.vue'
import HomeView from '../views/HomeView.vue'
import LoginView from '../views/LoginView.vue'
import RegistroView from '../views/RegistroView.vue'
import PreguntaView from '../views/PreguntaView.vue'
import PremiumView from '../views/PremiumView.vue'
import AdminView from '../views/AdminView.vue'
import PerfilView from '../views/PerfilView.vue'
import MensajesView from '../views/MensajesView.vue'
import { apiFetch } from '../services/api.js'
import { usuario } from '../services/sesion.js'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: HomeView },
    { path: '/buscar', component: BuscarView },
    { path: '/comunidades/:slug?', component: ComunidadesView },
    { path: '/preguntas', redirect: '/' },
    { path: '/preguntas/:id', component: PreguntaView },
    { path: '/usuarios/:id', component: PerfilView },
    { path: '/mensajes/:id?', component: MensajesView, meta: { requiereSesion: true } },
    { path: '/premium', component: PremiumView },
    { path: '/admin', component: AdminView, meta: { requiereAdmin: true } },
    { path: '/login', component: LoginView, meta: { barra: false, soloInvitado: true } },
    { path: '/registro', component: RegistroView, meta: { barra: false, soloInvitado: true } },
  ],
  scrollBehavior(to, from, savedPosition) {
    if (savedPosition) return savedPosition
    return { top: 0 }
  },
})

router.beforeEach(async (to) => {
  const token = localStorage.getItem('token')

  if (to.meta.soloInvitado && token) {
    return '/'
  }

  if ((to.meta.requiereSesion || to.meta.requiereAdmin) && !token) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }
  if (to.meta.requiereAdmin) {
    try {
      const actual = await apiFetch('usuarios', '/usuarios/yo')
      if (actual.rol !== 'admin') return '/'
      usuario.value = actual
      localStorage.setItem('usuario', JSON.stringify(actual))
    } catch { return '/' }
  }
})

export default router
