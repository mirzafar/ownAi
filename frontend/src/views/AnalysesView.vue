<script setup>
import { onMounted, ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api'

const router = useRouter()
const items = ref([])
const loading = ref(true)
const error = ref('')
const query = ref('')

const filtered = computed(() => {
  const q = query.value.trim().toLowerCase()
  if (!q) return items.value
  return items.value.filter(i =>
    (i.filename || '').toLowerCase().includes(q)
    || (i.analysis?.summary || '').toLowerCase().includes(q)
    || (i.sales_analysis?.meta?.system_verdict || '').toLowerCase().includes(q)
    || (i.text || '').toLowerCase().includes(q)
  )
})

const stats = computed(() => {
  const done = items.value.filter(i => i.status === 'done').length
  const failed = items.value.filter(i => i.status === 'failed').length
  const avgScore = (() => {
    const scores = items.value
      .map(i => i.sales_analysis?.meta?.total_score)
      .filter(v => typeof v === 'number')
    if (!scores.length) return null
    return Math.round(scores.reduce((a, b) => a + b, 0) / scores.length)
  })()
  return { total: items.value.length, done, failed, avgScore }
})

async function load() {
  loading.value = true
  error.value = ''
  try {
    const { data } = await api.get('/transcriptions')
    items.value = data
  } catch (e) {
    error.value = e.response?.data?.detail || 'Не удалось загрузить анализы'
  } finally {
    loading.value = false
  }
}

async function remove(id) {
  if (!confirm('Удалить анализ?')) return
  await api.delete(`/transcriptions/${id}`)
  items.value = items.value.filter(i => i.id !== id)
}

function fmtDate(s) {
  if (!s) return ''
  return new Date(s).toLocaleString('ru-RU', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit'
  })
}

function preview(item) {
  if (item.sales_analysis?.meta?.system_verdict) return item.sales_analysis.meta.system_verdict
  if (item.analysis?.summary) return item.analysis.summary
  const t = item.text || ''
  return t.length > 200 ? t.slice(0, 200) + '…' : t || 'Обработка…'
}

function scoreClass(score) {
  if (score >= 80) return 'good'
  if (score >= 60) return 'ok'
  if (score >= 40) return 'warn'
  return 'bad'
}

function statusLabel(s) {
  return { done: 'Готов', processing: 'В работе', failed: 'Ошибка' }[s] || s
}

onMounted(load)
</script>

<template>
  <div class="container">
    <div class="head">
      <div>
        <h1 class="page-title">Анализы</h1>
        <p class="page-subtitle">Все обработанные расшифровки и аудит звонков.</p>
      </div>
    </div>

    <div class="stats">
      <div class="stat card">
        <div class="stat-label">Всего</div>
        <div class="stat-value">{{ stats.total }}</div>
      </div>
      <div class="stat card">
        <div class="stat-label">Готовых</div>
        <div class="stat-value">{{ stats.done }}</div>
      </div>
      <div class="stat card">
        <div class="stat-label">Ошибок</div>
        <div class="stat-value">{{ stats.failed }}</div>
      </div>
      <div class="stat card">
        <div class="stat-label">Средний балл</div>
        <div class="stat-value">{{ stats.avgScore ?? '—' }}</div>
      </div>
    </div>

    <div class="toolbar">
      <input v-model="query" class="search" type="search" placeholder="Поиск по названию, тексту или вердикту…" />
    </div>

    <div v-if="error" class="error-msg" style="margin-bottom:16px;">{{ error }}</div>

    <div v-if="loading" class="loading">
      <span class="spinner"></span> Загрузка…
    </div>

    <div v-else-if="!items.length" class="empty card">
      <div class="empty-icon">✦</div>
      <h3>Пока нет анализов</h3>
      <p>Загрузите аудио — мы расшифруем и сделаем разбор.</p>
    </div>

    <div v-else-if="!filtered.length" class="empty card">
      <div class="empty-icon">🔍</div>
      <h3>Ничего не найдено</h3>
      <p>Попробуйте другой запрос.</p>
    </div>

    <div v-else class="list card">
      <div class="row-item" v-for="item in filtered" :key="item.id" @click="router.push(`/t/${item.id}`)">
        <div class="row-left">
          <div
            v-if="item.sales_analysis?.meta?.total_score != null"
            class="score-pill"
            :class="scoreClass(item.sales_analysis.meta.total_score)"
          >
            {{ item.sales_analysis.meta.total_score }}
          </div>
          <div v-else class="score-pill empty">—</div>
          <div class="info">
            <div class="row-title">{{ item.filename }}</div>
            <div class="row-summary">{{ preview(item) }}</div>
            <div class="row-meta">
              <span>{{ fmtDate(item.created_at) }}</span>
              <span v-if="item.source === 'bitrix_call'" class="meta-chip">Звонок · Bitrix24</span>
              <span v-else-if="item.source === 'bitrix_chat'" class="meta-chip">Чат · {{ item.bitrix_channel || 'Bitrix24' }}</span>
              <span v-if="item.analysis?.sentiment" class="badge" :class="item.analysis.sentiment">
                {{ item.analysis.sentiment }}
              </span>
              <span class="badge" :class="item.status">{{ statusLabel(item.status) }}</span>
            </div>
          </div>
        </div>
        <div class="row-right" @click.stop>
          <button class="ghost" @click="router.push(`/t/${item.id}`)">Открыть</button>
          <button class="danger" @click="remove(item.id)">Удалить</button>
        </div>
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
.row-left { display: flex; align-items: center; gap: 14px; flex: 1; min-width: 0; }
.score-pill {
  width: 52px; height: 52px;
  border-radius: 14px;
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

.info { flex: 1; min-width: 0; }
.row-title {
  font-weight: 600; font-size: 15px;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.row-summary {
  font-size: 13px; color: var(--text-dim);
  margin-top: 3px;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.row-meta {
  display: flex; gap: 8px; align-items: center;
  margin-top: 6px;
  flex-wrap: wrap;
  font-size: 12px; color: var(--text-muted);
}
.meta-chip {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 999px;
  background: var(--brand-soft);
  color: var(--brand);
  font-weight: 600;
}

.row-right { display: flex; gap: 8px; flex-shrink: 0; }
.row-right button { padding: 7px 12px; font-size: 12px; }

@media (max-width: 800px) {
  .stats { grid-template-columns: repeat(2, 1fr); }
  .row-right { display: none; }
}
</style>
