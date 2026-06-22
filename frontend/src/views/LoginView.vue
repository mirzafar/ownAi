<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const auth = useAuthStore()
const login = ref('')
const password = ref('')
const loading = ref(false)
const error = ref('')

async function submit() {
  error.value = ''
  loading.value = true
  try {
    await auth.login(login.value, password.value)
    router.push('/dashboard')
  } catch (e) {
    error.value = e.response?.data?.detail || 'Login failed'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="auth-page">
    <div class="auth-card card">
      <div class="logo-wrap">
        <div class="logo">🎙️</div>
      </div>
      <h1 class="title">ownAi</h1>
      <p class="subtitle">Вход</p>

      <form @submit.prevent="submit" class="col" style="gap:14px;">
        <div>
          <label class="label">Логин</label>
          <input v-model="login" type="text" placeholder="ваш логин" required autofocus autocomplete="username" />
        </div>
        <div>
          <label class="label">Пароль</label>
          <input v-model="password" type="password" placeholder="••••••••" required />
        </div>

        <div v-if="error" class="error-msg">{{ error }}</div>

        <button class="primary" type="submit" :disabled="loading">
          <span v-if="!loading">Войти</span>
          <span v-else class="row" style="justify-content:center;"><span class="spinner"></span></span>
        </button>
      </form>

      <p class="alt">
        Нет аккаунта?
        <router-link to="/register">Создать</router-link>
      </p>
    </div>
  </div>
</template>

<style scoped>
.auth-page {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 24px;
}
.auth-card {
  width: 100%;
  max-width: 440px;
  padding: 36px;
}
.logo-wrap { display: flex; justify-content: center; margin-bottom: 12px; }
.logo {
  width: 64px; height: 64px;
  border-radius: 20px;
  background: var(--brand-grad);
  display: grid; place-items: center;
  font-size: 32px;
  box-shadow: 0 16px 40px -12px rgba(3, 129, 254, 0.45);
}
.title {
  font-size: 26px;
  font-weight: 800;
  letter-spacing: -0.02em;
  text-align: center;
  margin: 6px 0 6px;
}
.subtitle {
  font-size: 14px;
  color: var(--text-dim);
  text-align: center;
  margin: 0 0 26px;
}
.alt {
  text-align: center;
  font-size: 14px;
  color: var(--text-dim);
  margin: 20px 0 0;
}
</style>
