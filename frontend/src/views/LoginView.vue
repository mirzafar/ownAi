<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { AudioLines, Sparkles, ShieldCheck, BarChart3 } from 'lucide-vue-next'

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
    <div class="auth-bg">
      <div class="blob blob-1"></div>
      <div class="blob blob-2"></div>
    </div>

    <div class="auth-grid">
      <div class="auth-hero">
        <div class="brand-row">
          <div class="brand-mark"><AudioLines :size="20" /></div>
          <span class="brand-name">ownAi</span>
        </div>
        <p class="hero-text">
          AI-аналитика звонков и чатов. Отслеживайте качество работы операторов,
          тональность диалогов и точность скриптов в одном месте.
        </p>
        <div class="hero-bullets">
          <div class="hero-bullet">
            <div class="bullet-ico"><Sparkles :size="16" /></div>
            <div>
              <div class="bullet-title">Автоматическая транскрипция и анализ</div>
              <div class="bullet-sub">оценки по критериям, тональность, ключевые моменты</div>
            </div>
          </div>
          <div class="hero-bullet">
            <div class="bullet-ico"><BarChart3 :size="16" /></div>
            <div>
              <div class="bullet-title">Прозрачная статистика операторов</div>
              <div class="bullet-sub">средний балл, динамика, разбор слабых мест</div>
            </div>
          </div>
          <div class="hero-bullet">
            <div class="bullet-ico"><ShieldCheck :size="16" /></div>
            <div>
              <div class="bullet-title">Безопасное хранение записей</div>
              <div class="bullet-sub">доступ по ролям, история изменений</div>
            </div>
          </div>
        </div>
      </div>

      <div class="auth-card">

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

          <button class="primary auth-submit" type="submit" :disabled="loading">
            <span v-if="!loading">Войти</span>
            <span v-else class="row" style="justify-content:center;"><span class="spinner"></span></span>
          </button>
        </form>

      </div>
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
.auth-bg {
  position: absolute;
  inset: 0;
  z-index: 0;
  pointer-events: none;
}
.blob {
  position: absolute;
  border-radius: 50%;
  filter: blur(80px);
  opacity: 0.55;
}
.blob-1 {
  width: 480px; height: 480px;
  background: radial-gradient(circle, #2DD4BF 0%, transparent 70%);
  top: -120px; left: -120px;
}
.blob-2 {
  width: 520px; height: 520px;
  background: radial-gradient(circle, #EC4899 0%, transparent 70%);
  bottom: -160px; right: -140px;
  opacity: 0.35;
}

.auth-grid {
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 56px;
  width: 100%;
  max-width: 1080px;
  align-items: center;
}

.auth-hero { padding: 24px 0; }
.brand-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 36px;
}
.brand-mark {
  width: 36px; height: 36px;
  border-radius: 11px;
  background: var(--brand-grad);
  color: #fff;
  display: grid; place-items: center;
  box-shadow: 0 8px 22px -8px rgba(20, 184, 166, 0.55);
}
.brand-name { font-size: 18px; font-weight: 700; letter-spacing: -0.02em; }

.hero-title {
  font-size: 38px;
  font-weight: 800;
  line-height: 1.15;
  letter-spacing: -0.03em;
  margin: 0 0 16px;
}
.hero-title .grad {
  background: var(--accent-grad);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}
.hero-text {
  font-size: 15px;
  color: var(--text-dim);
  line-height: 1.6;
  margin: 0 0 28px;
  max-width: 460px;
}
.hero-bullets {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.hero-bullet {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  padding: 12px 14px;
  background: rgba(255, 255, 255, 0.6);
  backdrop-filter: blur(8px);
  border: 1px solid var(--border);
  border-radius: 14px;
}
.bullet-ico {
  width: 32px; height: 32px;
  border-radius: 9px;
  background: var(--brand-soft);
  color: var(--brand-hover);
  display: grid; place-items: center;
  flex-shrink: 0;
}
.bullet-title { font-size: 13px; font-weight: 600; color: var(--text); }
.bullet-sub { font-size: 12px; color: var(--text-muted); margin-top: 2px; }

.auth-card {
  width: 100%;
  background: #ffffff;
  border: 1px solid var(--border);
  border-radius: 20px;
  padding: 36px;
  box-shadow: var(--shadow-lg);
}
.auth-card-head { margin-bottom: 24px; }
.title {
  font-size: 24px;
  font-weight: 700;
  letter-spacing: -0.02em;
  margin: 0 0 6px;
}
.subtitle {
  font-size: 14px;
  color: var(--text-dim);
  margin: 0;
}
.auth-submit {
  width: 100%;
  padding: 13px 18px;
  font-size: 14px;
  margin-top: 4px;
}
.alt {
  text-align: center;
  font-size: 14px;
  color: var(--text-dim);
  margin: 20px 0 0;
}

@media (max-width: 900px) {
  .auth-grid { grid-template-columns: 1fr; gap: 32px; max-width: 460px; }
  .auth-hero { display: none; }
  .hero-title { font-size: 28px; }
}
</style>
