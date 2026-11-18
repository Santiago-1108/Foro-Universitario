import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '../views/HomeView.vue'
import LoginView from '../views/LoginView.vue'
import RegistroView from '../views/RegistroView.vue'
import PreguntaView from '../views/PreguntaView.vue'
import PremiumView from '../views/PremiumView.vue'
import AdminView from '../views/AdminView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: HomeView },
    { path: '/preguntas', redirect: '/' },
    { path: '/preguntas/:id', component: PreguntaView },
    { path: '/premium', component: PremiumView },
    { path: '/admin', component: AdminView, meta: { requiereAdmin: true } },
    { path: '/login', component: LoginView, meta: { barra: false, soloInvitado: true } },
    { path: '/registro', component: RegistroView, meta: { barra: false, soloInvitado: true } },
  ],
  scrollBehavior() {
    return { top: 0 }
  },
})

router.beforeEach((to) => {
  const token = localStorage.getItem('token')

  if (to.meta.soloInvitado && token) {
    return '/'
  }

  if (to.meta.requiereAdmin) {
    let rol = ''
    try {
      rol = JSON.parse(localStorage.getItem('usuario') || '{}').rol
    } catch {
      rol = ''
    }
    if (!token || rol !== 'admin') {
      return '/'
    }
  }
})

export default router
