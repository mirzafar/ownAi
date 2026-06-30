<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { AudioLines } from 'lucide-vue-next'

const router = useRouter()
const auth = useAuthStore()
const name = ref('')
const login = ref('')
const password = ref('')
const loading = ref(false)
const error = ref('')

async function submit() {
  error.value = ''
  if (password.value.length < 6) {
    error.value = 'Пароль должен быть не короче 6 символов'
    return
  }
  loading.value = true
  try {
    await auth.register(name.value, login.value, password.value)
    router.push('/dashboard')
  } catch (e) {
    error.value = e.response?.data?.detail || 'Ошибка регистрации'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="auth-page">
    <div class="auth-bg">
      <div class="blob blob-1"></div>
      <div class="blob blob-2"></div>
    </div>

    <div class="auth-card">
      <div class="logo-wrap">
        <div class="logo"><AudioLines :size="28" /></div>
      </div>
      <h1 class="title">Создайте аккаунт</h1>
      <p class="subtitle">Начните анализировать звонки с <b>ownAi</b> уже сегодня.</p>

      <form @submit.prevent="submit" class="col" style="gap:14px;">
        <div>
          <label class="label">Имя</label>
          <input v-model="name" type="text" placeholder="Как к вам обращаться" required autofocus />
        </div>
        <div>
          <label class="label">Логин</label>
          <input v-model="login" type="text" placeholder="выберите логин" required autocomplete="username" />
        </div>
        <div>
          <label class="label">Пароль</label>
          <input v-model="password" type="password" placeholder="Минимум 6 символов" required />
        </div>

        <div v-if="error" class="error-msg">{{ error }}</div>

        <button class="primary auth-submit" type="submit" :disabled="loading">
          <span v-if="!loading">Создать аккаунт</span>
          <span v-else class="row" style="justify-content:center;"><span class="spinner"></span></span>
        </button>
      </form>

      <p class="alt">
        Уже есть аккаунт?
        <router-link to="/login">Войти</router-link>
      </p>
    </div>
  </div>
</template>

<style scoped>
.auth-page {
  position: relative;
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 24px;
  overflow: hidden;
}
.auth-bg { position: absolute; inset: 0; z-index: 0; pointer-events: none; }
.blob { position: absolute; border-radius: 50%; filter: blur(80px); opacity: 0.5; }
.blob-1 {
  width: 460px; height: 460px;
  background: radial-gradient(circle, #2DD4BF 0%, transparent 70%);
  top: -120px; left: -120px;
}
.blob-2 {
  width: 520px; height: 520px;
  background: radial-gradient(circle, #EC4899 0%, transparent 70%);
  bottom: -160px; right: -140px;
  opacity: 0.35;
}

.auth-card {
  position: relative;
  z-index: 1;
  width: 100%;
  max-width: 440px;
  background: #ffffff;
  border: 1px solid var(--border);
  border-radius: 20px;
  padding: 36px;
  box-shadow: var(--shadow-lg);
}
.logo-wrap { display: flex; justify-content: center; margin-bottom: 16px; }
.logo {
  width: 56px; height: 56px;
  border-radius: 16px;
  background: var(--brand-grad);
  color: #fff;
  display: grid; place-items: center;
  box-shadow: 0 16px 40px -12px rgba(20, 184, 166, 0.45);
}
.title {
  font-size: 24px;
  font-weight: 700;
  letter-spacing: -0.02em;
  text-align: center;
  margin: 6px 0 6px;
}
.subtitle {
  font-size: 14px;
  color: var(--text-dim);
  text-align: center;
  margin: 0 0 24px;
}
.auth-submit { width: 100%; padding: 13px 18px; }
.alt {
  text-align: center;
  font-size: 14px;
  color: var(--text-dim);
  margin: 20px 0 0;
}
</style>
