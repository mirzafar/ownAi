<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api'

const router = useRouter()
const operators = ref([])
const loading = ref(true)
const error = ref('')
const query = ref('')

const filtered = computed(() => {
  const q = query.value.trim().toLowerCase()
  if (!q) return operators.value
  return operators.value.filter(o =>
    (o.manager || '').toLowerCase().includes(q)
    || (o.manager_id || '').toLowerCase().includes(q)
  )
})

const totals = computed(() => {
  const calls = operators.value.reduce((a, o) => a + (o.calls || 0), 0)
  const analyzed = operators.value.reduce((a, o) => a + (o.analyzed || 0), 0)
  const scored = operators.value.filter(o => typeof o.avg_score === 'number')
  const avgScore = scored.length
    ? Math.round(scored.reduce((a, o) => a + o.avg_score, 0) / scored.length)
    : null
  return { count: operators.value.length, calls, analyzed, avgScore }
})

async function load() {
  loading.value = true
  error.value = ''
  try {
    const { data } = await api.get('/analytics/operators')
    operators.value = data
  } catch (e) {
    error.value = e.response?.data?.detail || 'Не удалось загрузить операторов'
  } finally {
    loading.value = false
  }
}

function open(op) {
  const id = op.manager_id || '—'
  router.push(`/operators/${encodeURIComponent(id)}`)
}

function fmtDate(s) {
  if (!s) return '—'
  return new Date(s).toLocaleString('ru-RU', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

function fmtDuration(sec) {
  if (!sec) return '—'
  const m = Math.floor(sec / 60)
  const s = sec % 60
  if (m < 60) return `${m}м ${String(s).padStart(2, '0')}с`
  const h = Math.floor(m / 60)
  return `${h}ч ${String(m % 60).padStart(2, '0')}м`
}

function scoreClass(score) {
  if (score == null) return 'empty'
  if (score >= 80) return 'good'
  if (score >= 60) return 'ok'
  if (score >= 40) return 'warn'
  return 'bad'
}

onMounted(load)
</script>

<template>
  <div class="container">
    <div class="head">
      <div>
        <h1 class="page-title">Операторы</h1>
        <p class="page-subtitle">Список операторов и сводка по их звонкам.</p>
      </div>
    </div>

    <div class="stats">
      <div class="stat card">
        <div class="stat-label">Операторов</div>
        <div class="stat-value">{{ totals.count }}</div>
      </div>
      <div class="stat card">
        <div class="stat-label">Звонков</div>
        <div class="stat-value">{{ totals.calls }}</div>
      </div>
      <div class="stat card">
        <div class="stat-label">Проанализировано</div>
        <div class="stat-value">{{ totals.analyzed }}</div>
      </div>
      <div class="stat card">
        <div class="stat-label">Средний балл</div>
        <div class="stat-value">{{ totals.avgScore ?? '—' }}</div>
      </div>
    </div>

    <div class="toolbar">
      <input v-model="query" class="search" type="search" placeholder="Поиск по имени оператора…" />
    </div>

    <div v-if="error" class="error-msg" style="margin-bottom:16px;">{{ error }}</div>

    <div v-if="loading" class="loading"><span class="spinner"></span> Загрузка…</div>

    <div v-else-if="!operators.length" class="empty card">
      <div class="empty-icon">👤</div>
      <h3>Пока нет операторов</h3>
      <p>Как только появятся звонки из Bitrix24 — здесь соберётся список.</p>
    </div>

    <div v-else-if="!filtered.length" class="empty card">
      <div class="empty-icon">🔍</div>
      <h3>Ничего не найдено</h3>
    </div>

    <div v-else class="list card">
      <div v-for="op in filtered" :key="op.manager_id + op.manager" class="row-item" @click="open(op)">
        <div class="avatar">{{ (op.manager || '?')[0]?.toUpperCase() }}</div>
        <div class="info">
          <div class="row-title">{{ op.manager || 'Без имени' }}</div>
          <div class="row-meta">
            <span>ID: {{ op.manager_id || '—' }}</span>
            <span>· Звонков: <b>{{ op.calls }}</b></span>
            <span>· Анализов: <b>{{ op.analyzed }}</b></span>
            <span>· Длит.: <b>{{ fmtDuration(op.total_duration) }}</b></span>
            <span>· Последний: <b>{{ fmtDate(op.last_call_at) }}</b></span>
          </div>
        </div>
        <div class="score-pill" :class="scoreClass(op.avg_score)">
          {{ op.avg_score ?? '—' }}
        </div>
        <button class="ghost" @click.stop="open(op)">Открыть →</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.head { display: flex; align-items: flex-start; margin-bottom: 22px; }
.stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14px;
  margin-bottom: 22px;
}
.stat { padding: 18px 20px; }
.stat-label { font-size: 12px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.08em; }
.stat-value {
  font-size: 28px;
  font-weight: 800;
  letter-spacing: -0.02em;
  margin-top: 4px;
  background: var(--brand-grad);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}
.toolbar { margin-bottom: 16px; }
.search { max-width: 460px; padding: 12px 16px; }

.loading { display: flex; align-items: center; gap: 10px; color: var(--text-dim); padding: 30px 0; }

.empty { text-align: center; padding: 60px 30px; }
.empty-icon { font-size: 42px; margin-bottom: 10px; color: var(--brand); }
.empty h3 { margin: 0 0 6px; font-size: 20px; }
.empty p { color: var(--text-dim); margin: 0; }

.list { padding: 0; overflow: hidden; }
.row-item {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 16px 22px;
  border-bottom: 1px solid var(--border);
  cursor: pointer;
  transition: background 0.15s;
}
.row-item:last-child { border-bottom: none; }
.row-item:hover { background: var(--surface-2); }

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
.row-title {
  font-weight: 600; font-size: 15px;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.row-meta {
  font-size: 12px; color: var(--text-muted);
  margin-top: 4px;
  display: flex; gap: 6px; flex-wrap: wrap;
}
.score-pill {
  min-width: 52px; height: 52px;
  border-radius: 14px;
  padding: 0 12px;
  display: grid; place-items: center;
  font-weight: 800; font-size: 18px;
  flex-shrink: 0;
  letter-spacing: -0.02em;
}
.score-pill.good { background: var(--success-soft); color: var(--success); }
.score-pill.ok { background: var(--brand-soft); color: var(--brand); }
.score-pill.warn { background: var(--warn-soft); color: var(--warn); }
.score-pill.bad { background: var(--danger-soft); color: var(--danger); }
.score-pill.empty { background: var(--surface-3); color: var(--text-muted); font-size: 16px; }

.row-item button { padding: 7px 12px; font-size: 12px; flex-shrink: 0; }

@media (max-width: 800px) {
  .stats { grid-template-columns: repeat(2, 1fr); }
  .row-item button { display: none; }
}
</style>
