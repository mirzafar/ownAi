<script setup>
import { onMounted, ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api'
import {
  Search, Sparkles, SearchX, Trash2, ChevronRight,
  Phone, MessagesSquare, ClipboardList,
} from 'lucide-vue-next'

const router = useRouter()
const items = ref([])
const loading = ref(true)
const error = ref('')
const query = ref('')
const kind = ref('all') // all | call | lead | chat

const filtered = computed(() => {
  const q = query.value.trim().toLowerCase()
  if (!q) return items.value
  return items.value.filter(i =>
    (i.title || '').toLowerCase().includes(q)
    || (i.scoring?.meta?.verdict || '').toLowerCase().includes(q)
    || (i.scoring?.summary || '').toLowerCase().includes(q)
    || (i.lead?.summary || '').toLowerCase().includes(q)
    || (i.source_text || '').toLowerCase().includes(q)
  )
})

const stats = computed(() => {
  const done = items.value.filter(i => i.status === 'done').length
  const failed = items.value.filter(i => i.status === 'failed').length
  const scores = items.value
    .map(i => i.scoring?.meta?.normalized_score)
    .filter(v => typeof v === 'number' && v > 0)
  const avgScore = scores.length
    ? Math.round(scores.reduce((a, b) => a + b, 0) / scores.length)
    : null
  return { total: items.value.length, done, failed, avgScore }
})

async function load() {
  loading.value = true
  error.value = ''
  try {
    const params = {}
    if (kind.value !== 'all') params.kind = kind.value
    const { data } = await api.get('/analyses', { params })
    items.value = data
  } catch (e) {
    error.value = e.response?.data?.detail || 'Не удалось загрузить анализы'
  } finally {
    loading.value = false
  }
}

function setKind(k) {
  if (kind.value === k) return
  kind.value = k
  load()
}

async function remove(id) {
  if (!confirm('Удалить анализ?')) return
  await api.delete(`/analyses/${id}`)
  items.value = items.value.filter(i => i.id !== id)
}

function fmtDate(s) {
  if (!s) return ''
  return new Date(s).toLocaleString('ru-RU', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

function preview(item) {
  if (item.scoring?.meta?.verdict) return item.scoring.meta.verdict
  if (item.kind === 'lead' && item.lead?.summary) return item.lead.summary
  if (item.scoring?.summary) return item.scoring.summary
  const t = item.source_text || ''
  return t.length > 200 ? t.slice(0, 200) + '…' : t || 'Обработка…'
}

function scoreClass(score) {
  if (score == null || score === 0) return 'empty'
  if (score >= 90) return 'good'
  if (score >= 75) return 'ok'
  if (score >= 60) return 'warn'
  return 'bad'
}

function statusLabel(s) {
  return { done: 'Готов', processing: 'В работе', failed: 'Ошибка' }[s] || s
}

function gradeShort(grade) {
  const map = {
    'Эталон': 'Эталон',
    'Хороший': 'Хорошо',
    'Удовлетворительно': 'Удовл.',
    'Неудовлетворительно': 'Неуд.',
  }
  return map[grade] || grade
}

function sentimentShort(s) {
  return {
    positive: 'Позитив',
    negative: 'Негатив',
    neutral: 'Нейтр.',
    mixed: 'Смеш.',
  }[s] || s
}

function openItem(item) {
  if (item.kind === 'lead' && item.lead?.bitrix_lead_id) {
    router.push(`/leads/${item.lead.bitrix_lead_id}`)
  } else {
    router.push(`/t/${item.id}`)
  }
}

function kindIcon(k) {
  if (k === 'lead') return ClipboardList
  if (k === 'chat') return MessagesSquare
  return Phone
}

function kindLabel(k) {
  return { call: 'Звонок', lead: 'Лид', chat: 'Чат' }[k] || k
}

onMounted(load)
</script>

<template>
  <div class="container">
    <div class="head">
      <div>
        <h1 class="page-title">Анализы</h1>
        <p class="page-subtitle">Все оценки по карте Swiss Collection — звонки, лиды, чаты.</p>
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

    <div class="toolbar card">
      <div class="search-wrap">
        <Search :size="16" class="search-ico" />
        <input v-model="query" class="search-input" type="search" placeholder="Поиск по названию, тексту или вердикту…" />
      </div>
      <div class="kind-switch">
        <button class="chip" :class="{ active: kind === 'all' }" @click="setKind('all')">Все</button>
        <button class="chip" :class="{ active: kind === 'call' }" @click="setKind('call')">Звонки</button>
        <button class="chip" :class="{ active: kind === 'lead' }" @click="setKind('lead')">Лиды</button>
        <button class="chip" :class="{ active: kind === 'chat' }" @click="setKind('chat')">Чаты</button>
      </div>
    </div>

    <div v-if="error" class="error-msg" style="margin-bottom:16px;">{{ error }}</div>

    <div v-if="loading" class="loading">
      <span class="spinner"></span> Загрузка…
    </div>

    <div v-else-if="!items.length" class="empty card">
      <div class="empty-icon"><Sparkles :size="28" /></div>
      <h3>Пока нет анализов</h3>
      <p>Загрузите аудио или запустите анализ лида — мы соберём всё здесь.</p>
    </div>

    <div v-else-if="!filtered.length" class="empty card">
      <div class="empty-icon"><SearchX :size="28" /></div>
      <h3>Ничего не найдено</h3>
      <p>Попробуйте другой запрос.</p>
    </div>

    <div v-else class="list card">
      <div class="row-item" v-for="item in filtered" :key="item.id" @click="openItem(item)">
        <div class="row-left">
          <div v-if="item.scoring?.meta?.normalized_score" class="score-pill" :class="scoreClass(item.scoring.meta.normalized_score)">
            {{ item.scoring.meta.normalized_score }}
          </div>
          <div v-else class="score-pill empty">—</div>
          <div class="info">
            <div class="row-title">{{ item.title }}</div>
            <div class="row-summary">{{ preview(item) }}</div>
            <div class="row-meta">
              <span>{{ fmtDate(item.date || item.created_at) }}</span>
              <span class="meta-chip">
                <component :is="kindIcon(item.kind)" :size="11" />
                {{ kindLabel(item.kind) }}
              </span>
              <span v-if="item.manager" class="meta-chip muted-chip">{{ item.manager }}</span>
              <span v-if="item.scoring?.sentiment" class="mini-chip" :class="item.scoring.sentiment">
                <span class="mini-dot"></span>{{ sentimentShort(item.scoring.sentiment) }}
              </span>
              <span v-if="item.scoring?.meta?.grade" class="mini-chip" :class="scoreClass(item.scoring.meta.normalized_score)">
                {{ gradeShort(item.scoring.meta.grade) }}
              </span>
              <span class="mini-chip" :class="item.status">{{ statusLabel(item.status) }}</span>
            </div>
          </div>
        </div>
        <div class="row-right" @click.stop>
          <button class="ghost open-btn" @click="openItem(item)">
            <ChevronRight :size="16" />
          </button>
          <button v-if="item.kind !== 'lead'" class="danger" @click="remove(item.id)">
            <Trash2 :size="14" />
          </button>
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
  margin-bottom: 18px;
}
.stat { padding: 18px 20px; }
.stat-label { font-size: 12px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.06em; font-weight: 600; }
.stat-value {
  font-size: 26px;
  font-weight: 700;
  letter-spacing: -0.02em;
  margin-top: 4px;
  color: var(--text);
}
.toolbar {
  margin-bottom: 16px;
  padding: 12px 14px;
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
  justify-content: space-between;
}
.search-wrap {
  position: relative;
  flex: 1;
  max-width: 460px;
  display: flex;
  align-items: center;
  min-width: 200px;
}
.search-ico { position: absolute; left: 12px; color: var(--text-muted); pointer-events: none; }
.search-input {
  width: 100%;
  background: transparent;
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 9px 14px 9px 36px;
  font-size: 14px;
}
.kind-switch { display: flex; gap: 6px; flex-wrap: wrap; }

.loading { display: flex; align-items: center; gap: 10px; color: var(--text-dim); padding: 30px 0; }

.empty { text-align: center; padding: 60px 30px; }
.empty-icon {
  width: 56px; height: 56px;
  border-radius: 16px;
  background: var(--brand-soft);
  color: var(--brand);
  display: grid; place-items: center;
  margin: 0 auto 12px;
}
.empty h3 { margin: 0 0 6px; font-size: 18px; }
.empty p { color: var(--text-dim); margin: 0; font-size: 14px; }

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
  width: 48px; height: 48px;
  border-radius: 12px;
  display: grid; place-items: center;
  font-weight: 700; font-size: 16px;
  flex-shrink: 0;
  letter-spacing: -0.02em;
}
.score-pill.good { background: var(--success-soft); color: var(--success); }
.score-pill.ok { background: var(--brand-soft); color: var(--brand-hover); }
.score-pill.warn { background: var(--warn-soft); color: var(--warn); }
.score-pill.bad { background: var(--danger-soft); color: var(--danger); }
.score-pill.empty {
  width: 32px; height: 32px;
  border-radius: 10px;
  background: transparent;
  border: 1px dashed var(--border-strong);
  color: var(--text-muted);
  font-size: 12px;
  font-weight: 600;
}

.info { flex: 1; min-width: 0; }
.row-title {
  font-weight: 600; font-size: 14px;
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
.mini-chip {
  display: inline-flex; align-items: center; gap: 4px;
  font-size: 11px; font-weight: 600;
  padding: 2px 8px;
  border-radius: 999px;
  background: var(--surface-3);
  color: var(--text-dim);
  white-space: nowrap;
  line-height: 1.4;
}
.mini-dot { width: 6px; height: 6px; border-radius: 50%; background: currentColor; }
.mini-chip.positive { background: var(--success-soft); color: var(--success); }
.mini-chip.negative { background: var(--danger-soft); color: var(--danger); }
.mini-chip.neutral { background: var(--surface-3); color: var(--text-dim); }
.mini-chip.mixed { background: var(--warn-soft); color: var(--warn); }
.mini-chip.good { background: var(--success-soft); color: var(--success); }
.mini-chip.ok { background: var(--brand-soft); color: var(--brand-hover); }
.mini-chip.warn { background: var(--warn-soft); color: var(--warn); }
.mini-chip.bad { background: var(--danger-soft); color: var(--danger); }
.mini-chip.empty { background: var(--surface-3); color: var(--text-muted); }
.mini-chip.done { background: var(--success-soft); color: var(--success); }
.mini-chip.processing { background: var(--brand-soft); color: var(--brand-hover); }
.mini-chip.failed { background: var(--danger-soft); color: var(--danger); }

.meta-chip {
  display: inline-flex; align-items: center; gap: 4px;
  font-size: 11px;
  padding: 3px 9px;
  border-radius: 999px;
  background: var(--brand-soft);
  color: var(--brand-hover);
  font-weight: 600;
}
.meta-chip.muted-chip {
  background: var(--surface-3);
  color: var(--text-dim);
}

.row-right { display: flex; gap: 6px; flex-shrink: 0; }
.row-right button {
  width: 34px; height: 34px;
  padding: 0;
  display: grid; place-items: center;
  font-size: 12px;
}
.open-btn { border-radius: 10px; }

@media (max-width: 800px) {
  .stats { grid-template-columns: repeat(2, 1fr); }
  .row-right { display: none; }
}
</style>
