import { defineStore } from 'pinia'
import api from '../api'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    user: null,
    token: null
  }),

  getters: {
    isAuthenticated: (s) => !!s.token
  },

  actions: {
    hydrate() {
      const token = localStorage.getItem('token')
      const user = localStorage.getItem('user')
      if (token) this.token = token
      if (user) {
        try { this.user = JSON.parse(user) } catch {}
      }
    },

    persist() {
      if (this.token) localStorage.setItem('token', this.token)
      else localStorage.removeItem('token')
      if (this.user) localStorage.setItem('user', JSON.stringify(this.user))
      else localStorage.removeItem('user')
    },

    async refresh() {
      if (!this.token) return
      try {
        const { data } = await api.get('/auth/me')
        this.user = data
        this.persist()
      } catch {
        // 401 handled by api interceptor
      }
    },

    async login(login, password) {
      const { data } = await api.post('/auth/login-json', { login, password })
      this.token = data.access_token
      this.user = data.user
      this.persist()
    },

    async register(name, login, password) {
      const { data } = await api.post('/auth/register', { name, login, password })
      this.token = data.access_token
      this.user = data.user
      this.persist()
    },

    logout() {
      this.user = null
      this.token = null
      this.persist()
    }
  }
})
