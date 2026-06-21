<script setup>
import { onMounted, reactive, ref } from 'vue'
import api from '../api'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()

const users = ref([])
const loading = ref(true)
const error = ref('')
const showCreate = ref(false)
const creating = ref(false)
const createError = ref('')

const resetTarget = ref(null)
const resetPwd = ref('')
const resetting = ref(false)
const resetError = ref('')

const form = reactive({
  login: '',
  name: '',
  password: '',
  phone: '',
  email: '',
  address: '',
  is_admin: false,
})

function resetForm() {
  Object.assign(form, {
    login: '', name: '', password: '',
    phone: '', email: '', address: '', is_admin: false,
  })
  createError.value = ''
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const { data } = await api.get('/auth/users')
    users.value = data
  } catch (e) {
    error.value = e.response?.data?.detail || 'Не удалось загрузить пользователей'
  } finally {
    loading.value = false
  }
}

async function create() {
  creating.value = true
  createError.value = ''
  try {
    await api.post('/auth/users', form)
    showCreate.value = false
    resetForm()
    await load()
  } catch (e) {
    createError.value = e.response?.data?.detail || 'Не удалось создать пользователя'
  } finally {
    creating.value = false
  }
}

async function remove(u) {
  if (u.id === auth.user?.id) return
  if (!confirm(`Удалить пользователя «${u.login}»?`)) return
  try {
    await api.delete(`/auth/users/${u.id}`)
    users.value = users.value.filter(x => x.id !== u.id)
  } catch (e) {
    error.value = e.response?.data?.detail || 'Не удалось удалить'
  }
}

function openReset(u) {
  resetTarget.value = u
  resetPwd.value = ''
  resetError.value = ''
}

function closeReset() {
  if (resetting.value) return
  resetTarget.value = null
}

async function submitReset() {
  resetError.value = ''
  if (resetPwd.value.length < 6) {
    resetError.value = 'Минимум 6 символов'
    return
  }
  resetting.value = true
  try {
    await api.post(`/auth/users/${resetTarget.value.id}/password`, {
      new_password: resetPwd.value,
    })
    resetTarget.value = null
  } catch (e) {
    resetError.value = e.response?.data?.detail || 'Не удалось сбросить пароль'
  } finally {
    resetting.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="container">
    <div class="head">
      <div>
        <h1 class="page-title">Пользователи</h1>
        <p class="page-subtitle">Управление учётными записями системы.</p>
      </div>
      <div class="spacer"></div>
      <button class="primary" @click="resetForm(); showCreate = true">+ Добавить</button>
    </div>

    <div v-if="error" class="error-msg" style="margin-bottom:16px;">{{ error }}</div>

    <div v-if="loading" class="loading"><span class="spinner"></span> Загрузка…</div>

    <div v-else-if="!users.length" class="empty card">
      <div class="empty-icon">👥</div>
      <h3>Нет пользователей</h3>
    </div>

    <div v-else class="list card">
      <div v-for="u in users" :key="u.id" class="row-item">
        <div class="avatar">{{ (u.name || u.login)[0]?.toUpperCase() }}</div>
        <div class="info">
          <div class="row-title">
            {{ u.name || u.login }}
            <span v-if="u.is_admin" class="admin-chip">Админ</span>
          </div>
          <div class="row-meta">
            <span>@{{ u.login }}</span>
            <span v-if="u.email">· {{ u.email }}</span>
            <span v-if="u.phone">· {{ u.phone }}</span>
          </div>
        </div>
        <div class="actions">
          <button class="ghost" title="Сбросить пароль" @click="openReset(u)">🔑 Пароль</button>
          <button
            class="danger"
            :disabled="u.id === auth.user?.id"
            :title="u.id === auth.user?.id ? 'Нельзя удалить себя' : ''"
            @click="remove(u)"
          >Удалить</button>
        </div>
      </div>
    </div>

    <div v-if="resetTarget" class="overlay" @click.self="closeReset">
      <div class="modal card" style="max-width:460px;">
        <div class="modal-head">
          <h2 class="modal-title">Сброс пароля</h2>
          <button class="ghost icon-btn" @click="closeReset" :disabled="resetting">✕</button>
        </div>
        <p style="color:var(--text-dim);font-size:14px;margin:0 0 16px;">
          Новый пароль для <b>@{{ resetTarget.login }}</b>. Сообщите его пользователю — текущий пароль перестанет работать.
        </p>
        <form class="modal-form" @submit.prevent="submitReset">
          <div>
            <label class="label">Новый пароль</label>
            <input v-model="resetPwd" type="text" autocomplete="new-password" required minlength="6" autofocus />
          </div>
          <div v-if="resetError" class="error-msg">{{ resetError }}</div>
          <div class="modal-actions">
            <button type="button" class="ghost" @click="closeReset" :disabled="resetting">Отмена</button>
            <button class="primary" type="submit" :disabled="resetting">
              <span v-if="!resetting">Сбросить пароль</span>
              <span v-else class="row" style="gap:8px;"><span class="spinner"></span> Сохранение…</span>
            </button>
          </div>
        </form>
      </div>
    </div>

    <div v-if="showCreate" class="overlay" @click.self="!creating && (showCreate = false)">
      <div class="modal card">
        <div class="modal-head">
          <h2 class="modal-title">Новый пользователь</h2>
          <button class="ghost icon-btn" @click="showCreate = false" :disabled="creating">✕</button>
        </div>

        <form class="modal-form" @submit.prevent="create">
          <div class="grid">
            <div>
              <label class="label">Логин *</label>
              <input v-model="form.login" required minlength="3" autocomplete="off" />
            </div>
            <div>
              <label class="label">Имя *</label>
              <input v-model="form.name" required />
            </div>
            <div>
              <label class="label">Пароль *</label>
              <input v-model="form.password" type="password" required minlength="6" autocomplete="new-password" />
            </div>
            <div>
              <label class="label">Телефон</label>
              <input v-model="form.phone" type="tel" />
            </div>
            <div>
              <label class="label">Email</label>
              <input v-model="form.email" type="email" />
            </div>
            <div>
              <label class="label">Адрес</label>
              <input v-model="form.address" />
            </div>
          </div>
          <label class="check">
            <input type="checkbox" v-model="form.is_admin" />
            <span>Сделать администратором</span>
          </label>

          <div v-if="createError" class="error-msg">{{ createError }}</div>

          <div class="modal-actions">
            <button type="button" class="ghost" @click="showCreate = false" :disabled="creating">Отмена</button>
            <button class="primary" type="submit" :disabled="creating">
              <span v-if="!creating">Создать</span>
              <span v-else class="row" style="gap:8px;"><span class="spinner"></span> Создание…</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<style scoped>
.head { display: flex; align-items: flex-start; gap: 16px; margin-bottom: 22px; }
.loading { display: flex; align-items: center; gap: 10px; color: var(--text-dim); padding: 30px 0; }

.empty { text-align: center; padding: 60px 30px; }
.empty-icon { font-size: 42px; margin-bottom: 10px; }

.list { padding: 0; overflow: hidden; }
.row-item {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 14px 22px;
  border-bottom: 1px solid var(--border);
}
.row-item:last-child { border-bottom: none; }
.avatar {
  width: 44px; height: 44px;
  border-radius: 50%;
  background: var(--brand-grad);
  color: #fff;
  display: grid; place-items: center;
  font-weight: 700; font-size: 14px;
  flex-shrink: 0;
}
.info { flex: 1; min-width: 0; }
.row-title { font-weight: 600; font-size: 15px; display: flex; align-items: center; gap: 8px; }
.admin-chip {
  font-size: 11px;
  background: var(--brand-soft);
  color: var(--brand);
  padding: 2px 8px;
  border-radius: 999px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}
.row-meta { font-size: 12px; color: var(--text-muted); margin-top: 4px; display: flex; gap: 6px; flex-wrap: wrap; }
.actions button { padding: 7px 12px; font-size: 12px; }

.overlay {
  position: fixed; inset: 0;
  background: rgba(16, 24, 40, 0.45);
  backdrop-filter: blur(4px);
  z-index: 200;
  display: grid; place-items: center;
  padding: 24px;
}
.modal {
  width: 100%;
  max-width: 560px;
  padding: 28px;
}
.modal-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px; }
.modal-title { font-size: 20px; font-weight: 800; margin: 0; letter-spacing: -0.01em; }
.icon-btn { padding: 6px 12px; font-size: 14px; }

.modal-form { display: flex; flex-direction: column; gap: 16px; }
.grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
.check { display: flex; align-items: center; gap: 10px; font-size: 14px; color: var(--text-dim); }
.check input { width: auto; }
.modal-actions { display: flex; gap: 10px; justify-content: flex-end; }

@media (max-width: 600px) {
  .grid { grid-template-columns: 1fr; }
}
</style>
