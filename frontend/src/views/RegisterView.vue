<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

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
    error.value = 'Password must be at least 6 characters'
    return
  }
  loading.value = true
  try {
    await auth.register(name.value, login.value, password.value)
    router.push('/dashboard')
  } catch (e) {
    error.value = e.response?.data?.detail || 'Registration failed'
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
      <h1 class="title">Create your account</h1>
      <p class="subtitle">Join <b>ownAi</b> and start analyzing audio in minutes.</p>

      <form @submit.prevent="submit" class="col" style="gap:14px;">
        <div>
          <label class="label">Name</label>
          <input v-model="name" type="text" placeholder="Your name" required autofocus />
        </div>
        <div>
          <label class="label">Login</label>
          <input v-model="login" type="text" placeholder="choose a login" required autocomplete="username" />
        </div>
        <div>
          <label class="label">Password</label>
          <input v-model="password" type="password" placeholder="At least 6 characters" required />
        </div>

        <div v-if="error" class="error-msg">{{ error }}</div>

        <button class="primary" type="submit" :disabled="loading">
          <span v-if="!loading">Create account</span>
          <span v-else class="row" style="justify-content:center;"><span class="spinner"></span></span>
        </button>
      </form>

      <p class="alt">
        Already have an account?
        <router-link to="/login">Sign in</router-link>
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
