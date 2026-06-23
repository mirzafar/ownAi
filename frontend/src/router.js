import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from './stores/auth'

import LoginView from './views/LoginView.vue'
import RegisterView from './views/RegisterView.vue'
import DashboardView from './views/DashboardView.vue'
import UploadView from './views/UploadView.vue'
import TranscriptionView from './views/TranscriptionView.vue'
import BitrixCallsView from './views/BitrixCallsView.vue'
import BitrixChatsView from './views/BitrixChatsView.vue'
import AnalysesView from './views/AnalysesView.vue'
import OperatorsView from './views/OperatorsView.vue'
import OperatorDetailView from './views/OperatorDetailView.vue'
import ProfileView from './views/ProfileView.vue'
import UsersView from './views/UsersView.vue'

const routes = [
  { path: '/', redirect: '/dashboard' },
  { path: '/login', component: LoginView, meta: { guest: true } },
  { path: '/register', component: RegisterView, meta: { guest: true } },
  { path: '/dashboard', component: DashboardView, meta: { auth: true } },
  { path: '/calls', component: BitrixCallsView, meta: { auth: true } },
  { path: '/chats', component: BitrixChatsView, meta: { auth: true } },
  { path: '/bitrix', redirect: '/calls' },
  { path: '/analyses', component: AnalysesView, meta: { auth: true } },
  { path: '/operators', component: OperatorsView, meta: { auth: true } },
  { path: '/operators/:id', component: OperatorDetailView, meta: { auth: true } },
  { path: '/upload', component: UploadView, meta: { auth: true } },
  { path: '/profile', component: ProfileView, meta: { auth: true } },
  { path: '/users', component: UsersView, meta: { auth: true, admin: true } },
  { path: '/t/:id', component: TranscriptionView, meta: { auth: true } }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (to.meta.auth && !auth.isAuthenticated) return '/login'
  if (to.meta.guest && auth.isAuthenticated) return '/dashboard'
  if (to.meta.admin && !auth.user?.is_admin) return '/dashboard'
})

export default router
