<script setup>
import { onMounted, reactive, ref } from 'vue'
import api from '../api'
import { useAuthStore } from '../stores/auth'
import { Lock, Check } from 'lucide-vue-next'

const auth = useAuthStore()

const form = reactive({
  name: '',
  phone: '',
  email: '',
  address: '',
})
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const ok = ref(false)

const pwd = reactive({
  next: '',
  confirm: '',
})
const pwdSaving = ref(false)
const pwdError = ref('')
const pwdOk = ref(false)

async function load() {
  loading.value = true
  error.value = ''
  try {
    const { data } = await api.get('/auth/me')
    Object.assign(form, {
      name: data.name || '',
      phone: data.phone || '',
      email: data.email || '',
      address: data.address || '',
    })
    auth.user = { ...auth.user, ...data }
    auth.persist()
  } catch (e) {
    error.value = e.response?.data?.detail || 'Не удалось загрузить профиль'
  } finally {
    loading.value = false
  }
}

async function save() {
  saving.value = true
  error.value = ''
  ok.value = false
  try {
    const { data } = await api.patch('/auth/me', form)
    auth.user = { ...auth.user, ...data }
    auth.persist()
    ok.value = true
    setTimeout(() => (ok.value = false), 1500)
  } catch (e) {
    error.value = e.response?.data?.detail || 'Не удалось сохранить'
  } finally {
    saving.value = false
  }
}

async function changePassword() {
  pwdError.value = ''
  pwdOk.value = false
  if (pwd.next.length < 6) {
    pwdError.value = 'Новый пароль — минимум 6 символов'
    return
  }
  if (pwd.next !== pwd.confirm) {
    pwdError.value = 'Пароли не совпадают'
    return
  }
  pwdSaving.value = true
  try {
    await api.post('/auth/me/password', { new_password: pwd.next })
    pwd.next = ''
    pwd.confirm = ''
    pwdOk.value = true
    setTimeout(() => (pwdOk.value = false), 2000)
  } catch (e) {
    pwdError.value = e.response?.data?.detail || 'Не удалось сменить пароль'
  } finally {
    pwdSaving.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="container narrow">
    <h1 class="page-title">Профиль</h1>
    <p class="page-subtitle">Личные данные и контакты.</p>

    <div v-if="loading" class="loading"><span class="spinner"></span> Загрузка…</div>

    <form v-else class="card form" @submit.prevent="save">
      <div class="header">
        <div class="avatar">{{ form.name?.[0]?.toUpperCase() || '?' }}</div>
        <div>
          <div class="header-name">{{ form.name || auth.user?.login }}</div>
          <div class="header-login">@{{ auth.user?.login }}<span v-if="auth.user?.is_admin" class="admin-chip">Админ</span></div>
        </div>
      </div>

      <div class="grid">
        <div>
          <label class="label">Имя</label>
          <input v-model="form.name" type="text" />
        </div>
        <div>
          <label class="label">Телефон</label>
          <input v-model="form.phone" type="tel" placeholder="+7 ___ ___ __ __" />
        </div>
        <div>
          <label class="label">Email</label>
          <input v-model="form.email" type="email" placeholder="you@example.com" />
        </div>
        <div>
          <label class="label">Адрес</label>
          <input v-model="form.address" type="text" placeholder="Город, улица, дом" />
        </div>
      </div>

      <div v-if="error" class="error-msg">{{ error }}</div>

      <div class="actions">
        <span v-if="ok" class="saved"><Check :size="14" /> Сохранено</span>
        <button class="primary" type="submit" :disabled="saving">
          <span v-if="!saving">Сохранить</span>
          <span v-else class="row" style="gap:8px;"><span class="spinner"></span> Сохранение…</span>
        </button>
      </div>
    </form>

    <form v-if="!loading" class="card form pwd-card" @submit.prevent="changePassword">
      <div class="section-head">
        <div class="section-icon"><Lock :size="18" /></div>
        <div>
          <h2 class="section-title">Смена пароля</h2>
          <p class="section-sub">Минимум 6 символов. Используйте надёжный пароль.</p>
        </div>
      </div>

      <div class="grid">
        <div>
          <label class="label">Новый пароль</label>
          <input v-model="pwd.next" type="password" autocomplete="new-password" required minlength="6" />
        </div>
        <div>
          <label class="label">Повторите новый</label>
          <input v-model="pwd.confirm" type="password" autocomplete="new-password" required minlength="6" />
        </div>
      </div>

      <div v-if="pwdError" class="error-msg">{{ pwdError }}</div>

      <div class="actions">
        <span v-if="pwdOk" class="saved"><Check :size="14" /> Пароль обновлён</span>
        <button class="primary" type="submit" :disabled="pwdSaving">
          <span v-if="!pwdSaving">Сменить пароль</span>
          <span v-else class="row" style="gap:8px;"><span class="spinner"></span> Сохранение…</span>
        </button>
      </div>
    </form>
  </div>
</template>

<style scoped>
.container.narrow { max-width: 720px; }
.loading { display: flex; align-items: center; gap: 10px; color: var(--text-dim); padding: 30px 0; }
.form { display: flex; flex-direction: column; gap: 22px; }
.header { display: flex; align-items: center; gap: 16px; }
.avatar {
  width: 64px; height: 64px;
  border-radius: 18px;
  background: var(--brand-grad);
  color: #fff;
  display: grid; place-items: center;
  font-size: 24px; font-weight: 700;
  box-shadow: 0 12px 28px -10px rgba(20, 184, 166, 0.45);
}
.header-name { font-size: 20px; font-weight: 700; }
.header-login { font-size: 13px; color: var(--text-muted); display: flex; align-items: center; gap: 8px; margin-top: 2px; }
.admin-chip {
  font-size: 10px;
  background: var(--brand-soft);
  color: var(--brand-hover);
  padding: 2px 8px;
  border-radius: 999px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}

.actions { display: flex; gap: 12px; justify-content: flex-end; align-items: center; }

.pwd-card { margin-top: 22px; }
.section-head { display: flex; align-items: center; gap: 14px; }
.section-icon {
  width: 40px; height: 40px;
  border-radius: 12px;
  background: var(--brand-soft);
  color: var(--brand-hover);
  display: grid; place-items: center;
  flex-shrink: 0;
}
.saved {
  display: inline-flex; align-items: center; gap: 4px;
  color: var(--success); font-weight: 600; font-size: 13px;
}
.section-title { margin: 0; font-size: 18px; font-weight: 700; }
.section-sub { margin: 2px 0 0; font-size: 13px; color: var(--text-dim); }
.grid .full { grid-column: 1 / -1; }

@media (max-width: 600px) {
  .grid { grid-template-columns: 1fr; }
}
</style>
