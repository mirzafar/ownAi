<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api'
import { useTasksStore } from '../stores/tasks'
import {
  Calendar, Phone, RefreshCw, X, Play,
  ArrowDownLeft, ArrowUpRight, ArrowRight, Sparkles,
  ChevronLeft, ChevronRight,
} from 'lucide-vue-next'

const router = useRouter()
const tasks = useTasksStore()

function todayISO() {
  const d = new Date()
  const off = d.getTimezoneOffset()
  return new Date(d.getTime() - off * 60_000).toISOString().slice(0, 10)
}

const integration = ref('bitrix')
const direction = ref('all')
const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const loading = ref(true)
const error = ref('')
const dateFrom = ref(todayISO())
const dateTo = ref(todayISO())
const playingId = ref(null)

function isAnalyzing(callId) {
  return tasks.hasActive('analyze_call', { id: callId })
}

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))

async function load() {
  loading.value = true
  error.value = ''
  try {
    const params = { page: page.value, page_size: pageSize }
    if (dateFrom.value) params.date_from = new Date(dateFrom.value).toISOString()
    if (dateTo.value) {
      const d = new Date(dateTo.value)
      d.setHours(23, 59, 59, 999)
      params.date_to = d.toISOString()
    }
    if (direction.value !== 'all') params.direction = direction.value
    const { data } = await api.get('/bitrix/calls', { params })
    items.value = data.items
    total.value = data.total
  } catch (e) {
    error.value = e.response?.data?.detail || 'Не удалось загрузить звонки'
    items.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

function startAnalyze(item) {
  if (!item || !item.record_url) return
  if (isAnalyzing(item.id)) return
  const callId = item.id
  const label = `Анализ звонка · ${item.manager || item.phone || callId}`

  tasks.run(
    {
      kind: 'analyze_call',
      meta: { id: callId },
      label,
      hint: 'Скачиваем запись, расшифровываем и анализируем',
    },
    async () => {
      const { data } = await api.post(`/bitrix/calls/${callId}/analyze`)
      return data
    }
  ).then(() => {
    if (router.currentRoute.value.path.startsWith('/calls')) load()
  }).catch(() => {})
}

function openExisting(item) {
  if (item.analysis_id) router.push(`/t/${item.analysis_id}`)
}

function togglePlay(item) {
  playingId.value = playingId.value === item.id ? null : item.id
}

function applyFilters() {
  page.value = 1
  load()
}

function resetFilters() {
  dateFrom.value = todayISO()
  dateTo.value = todayISO()
  direction.value = 'all'
  page.value = 1
  load()
}

function setPreset(preset) {
  const t = new Date()
  const fmt = (d) => {
    const off = d.getTimezoneOffset()
    return new Date(d.getTime() - off * 60_000).toISOString().slice(0, 10)
  }
  if (preset === 'today') {
    dateFrom.value = fmt(t)
    dateTo.value = fmt(t)
  } else if (preset === 'yesterday') {
    const y = new Date(t); y.setDate(t.getDate() - 1)
    dateFrom.value = fmt(y); dateTo.value = fmt(y)
  } else if (preset === '7d') {
    const s = new Date(t); s.setDate(t.getDate() - 6)
    dateFrom.value = fmt(s); dateTo.value = fmt(t)
  } else if (preset === '30d') {
    const s = new Date(t); s.setDate(t.getDate() - 29)
    dateFrom.value = fmt(s); dateTo.value = fmt(t)
  }
  applyFilters()
}

function isPreset(preset) {
  const t = new Date()
  const fmt = (d) => {
    const off = d.getTimezoneOffset()
    return new Date(d.getTime() - off * 60_000).toISOString().slice(0, 10)
  }
  if (preset === 'today') return dateFrom.value === fmt(t) && dateTo.value === fmt(t)
  if (preset === 'yesterday') {
    const y = new Date(t); y.setDate(t.getDate() - 1)
    return dateFrom.value === fmt(y) && dateTo.value === fmt(y)
  }
  if (preset === '7d') {
    const s = new Date(t); s.setDate(t.getDate() - 6)
    return dateFrom.value === fmt(s) && dateTo.value === fmt(t)
  }
  if (preset === '30d') {
    const s = new Date(t); s.setDate(t.getDate() - 29)
    return dateFrom.value === fmt(s) && dateTo.value === fmt(t)
  }
  return false
}

function changePage(delta) {
  const next = page.value + delta
  if (next < 1 || next > totalPages.value) return
  page.value = next
  load()
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
  return `${m}:${String(s).padStart(2, '0')}`
}

function fmtPhone(p) {
  if (!p) return '—'
  return p.replace(/^(\+?\d)(\d{3})(\d{3})(\d{2})(\d{2}).*/, '$1 $2 $3-$4-$5')
}

onMounted(load)
</script>

<template>
  <div class="container">
    <div class="head">
      <div>
        <h1 class="page-title">Звонки</h1>
      </div>
      <div class="spacer"></div>
      <button class="ghost refresh-btn" @click="load" :disabled="loading">
        <span v-if="loading" class="spinner"></span>
        <template v-else><RefreshCw :size="14" /> Обновить</template>
      </button>
    </div>

    <div class="filters card">
      <div class="filter-grid">
        <div>
          <label class="label">Интеграция</label>
          <select v-model="integration" class="select">
            <option value="bitrix">Bitrix24</option>
            <option value="amocrm" disabled>amoCRM (скоро)</option>
            <option value="telephony" disabled>Телефония (скоро)</option>
          </select>
        </div>
        <div>
          <label class="label">Тип звонка</label>
          <select v-model="direction" class="select" @change="applyFilters">
            <option value="all">Все</option>
            <option value="in">Входящие</option>
            <option value="out">Исходящие</option>
          </select>
        </div>
        <div>
          <label class="label">Период</label>
          <div class="date-range">
            <label class="date-input">
              <Calendar :size="14" class="cal-ico" />
              <input type="date" v-model="dateFrom" />
            </label>
            <span class="date-sep">—</span>
            <label class="date-input">
              <Calendar :size="14" class="cal-ico" />
              <input type="date" v-model="dateTo" />
            </label>
          </div>
        </div>
        <div class="filter-actions">
          <button class="primary" @click="applyFilters" :disabled="loading">Применить</button>
          <button class="ghost" @click="resetFilters" :disabled="loading">Сбросить</button>
        </div>
      </div>

      <div class="presets">
        <button class="chip" :class="{ active: isPreset('today') }" @click="setPreset('today')">Сегодня</button>
        <button class="chip" :class="{ active: isPreset('yesterday') }" @click="setPreset('yesterday')">Вчера</button>
        <button class="chip" :class="{ active: isPreset('7d') }" @click="setPreset('7d')">7 дней</button>
        <button class="chip" :class="{ active: isPreset('30d') }" @click="setPreset('30d')">30 дней</button>
      </div>
    </div>

    <div v-if="error" class="error-msg" style="margin-bottom:16px;">{{ error }}</div>

    <div v-if="loading" class="loading">
      <span class="spinner"></span> Загрузка звонков…
    </div>

    <div v-else-if="!items.length" class="empty card">
      <div class="empty-icon"><Phone :size="28" /></div>
      <h3>Звонки не найдены</h3>
      <p>Измените фильтры или проверьте подключение.</p>
    </div>

    <div v-else class="table card">
      <div class="thead">
        <div class="col-date">Дата</div>
        <div class="col-direction">Тип</div>
        <div class="col-phone">Телефон</div>
        <div class="col-manager">Менеджер</div>
        <div class="col-duration">Длит.</div>
        <div class="col-record">Запись</div>
        <div class="col-actions">Действие</div>
      </div>

      <div
        v-for="item in items"
        :key="item.id"
        class="trow"
        :class="{ analyzed: item.analyzed }"
      >
        <div class="col-date">
          <div class="date-main">{{ fmtDate(item.date).split(',')[0] }}</div>
          <div class="date-sub">{{ fmtDate(item.date).split(',')[1] }}</div>
        </div>

        <div class="col-direction">
          <span class="dir-badge" :class="item.direction === 'Входящий' ? 'in' : 'out'">
            <component :is="item.direction === 'Входящий' ? ArrowDownLeft : ArrowUpRight" :size="12" />
            {{ item.direction || '—' }}
          </span>
        </div>

        <div class="col-phone mono">{{ fmtPhone(item.phone) }}</div>

        <div class="col-manager">
          <div class="mgr">
            <div class="mgr-avatar">{{ (item.manager || '?')[0]?.toUpperCase() }}</div>
            <div class="mgr-name">{{ item.manager || '—' }}</div>
          </div>
        </div>

        <div class="col-duration mono">{{ fmtDuration(item.duration) }}</div>

        <div class="col-record">
          <button
            v-if="item.record_url"
            class="play-icon"
            :class="{ active: playingId === item.id }"
            :title="playingId === item.id ? 'Скрыть плеер' : 'Слушать'"
            @click="togglePlay(item)"
          >
            <X v-if="playingId === item.id" :size="14" />
            <Play v-else :size="14" />
          </button>
          <span v-else class="muted">—</span>
        </div>

        <div class="col-actions">
          <button
            v-if="item.analyzed"
            class="action-icon open"
            title="Открыть анализ"
            @click="openExisting(item)"
          >
            <ArrowRight :size="16" />
          </button>
          <button
            v-else
            class="action-icon analyze"
            :disabled="!item.record_url || isAnalyzing(item.id)"
            :title="item.record_url ? (isAnalyzing(item.id) ? 'Анализ выполняется в фоне' : 'Анализировать') : 'Нет записи'"
            @click="startAnalyze(item)"
          >
            <span v-if="isAnalyzing(item.id)" class="spinner"></span>
            <Sparkles v-else :size="16" />
          </button>
        </div>

        <div v-if="playingId === item.id && item.record_url" class="player-row">
          <audio :src="item.record_url" controls autoplay preload="none" style="width:100%;"></audio>
        </div>
      </div>
    </div>

    <div v-if="items.length" class="pager">
      <button class="ghost pager-btn" @click="changePage(-1)" :disabled="page === 1 || loading">
        <ChevronLeft :size="14" /> Назад
      </button>
      <span class="pager-info">Стр. {{ page }} из {{ totalPages }}</span>
      <button class="ghost pager-btn" @click="changePage(1)" :disabled="page >= totalPages || loading">
        Вперёд <ChevronRight :size="14" />
      </button>
    </div>

  </div>
</template>

<style scoped>
.head { display: flex; align-items: center; gap: 16px; margin-bottom: 22px; }

.filters { padding: 18px 22px; margin-bottom: 22px; }
.filter-grid {
  display: grid;
  grid-template-columns: 1fr 1fr 1.6fr auto;
  gap: 14px;
  align-items: end;
}
.filter-actions { display: flex; gap: 10px; }

.date-range {
  display: flex;
  align-items: center;
  gap: 8px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 4px 10px;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.date-range:focus-within {
  border-color: var(--brand);
  box-shadow: 0 0 0 4px rgba(20, 184, 166, 0.12);
}
.date-input {
  position: relative;
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  min-width: 0;
  padding: 6px 8px;
  cursor: pointer;
}
.date-input .cal-ico { color: var(--text-muted); pointer-events: none; }
.date-input input {
  border: none;
  background: transparent;
  padding: 0;
  width: 100%;
  font-size: 13px;
  font-weight: 500;
  color: var(--text);
  font-family: inherit;
  outline: none;
  box-shadow: none;
  cursor: pointer;
}
.date-input input:focus { box-shadow: none; background: transparent; }
.date-input input::-webkit-calendar-picker-indicator {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  opacity: 0;
  cursor: pointer;
}
.date-sep { color: var(--text-muted); font-size: 14px; flex-shrink: 0; }

.presets {
  display: flex;
  gap: 8px;
  margin-top: 14px;
  flex-wrap: wrap;
}
.chip {
  padding: 6px 14px;
  font-size: 12px;
  font-weight: 600;
  border-radius: 999px;
  background: var(--surface);
  border: 1px solid var(--border);
  color: var(--text-dim);
  box-shadow: none;
  cursor: pointer;
  transition: background .15s, color .15s, border-color .15s;
}
.chip:hover { background: var(--surface-2); color: var(--text); }
.chip.active {
  background: var(--brand-soft);
  color: var(--brand-hover);
  border-color: rgba(20, 184, 166, 0.25);
}

.select {
  width: 100%;
  font-family: inherit;
  font-size: 14px;
  color: var(--text);
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 11px 14px;
  outline: none;
  transition: border-color 0.15s, box-shadow 0.15s;
  appearance: none;
  -webkit-appearance: none;
  background-image: url("data:image/svg+xml;charset=UTF-8,%3csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 14 8'%3e%3cpath fill='none' stroke='%2394A3B8' stroke-width='1.5' d='M1 1l6 6 6-6'/%3e%3c/svg%3e");
  background-repeat: no-repeat;
  background-position: right 14px center;
  background-size: 12px;
  padding-right: 36px;
}
.select:focus {
  border-color: var(--brand);
  box-shadow: 0 0 0 4px rgba(20, 184, 166, 0.12);
}

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

.refresh-btn { display: inline-flex; align-items: center; gap: 6px; }
.pager-btn { display: inline-flex; align-items: center; gap: 4px; }

.table { padding: 0; overflow: hidden; }

.thead {
  display: grid;
  grid-template-columns: 130px 130px 160px 1fr 80px 70px 70px;
  gap: 14px;
  padding: 14px 22px;
  font-size: 11px;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  border-bottom: 1px solid var(--border);
  background: var(--surface-2);
}

.trow {
  display: grid;
  grid-template-columns: 130px 130px 160px 1fr 80px 70px 70px;
  gap: 14px;
  padding: 14px 22px;
  align-items: center;
  border-bottom: 1px solid var(--border);
  transition: background 0.15s;
  position: relative;
}
.trow:last-child { border-bottom: none; }
.trow:hover { background: var(--surface-2); }
.trow.analyzed { background: linear-gradient(90deg, rgba(16, 185, 129, 0.04) 0%, transparent 35%); }

.date-main { font-weight: 600; font-size: 13px; }
.date-sub { font-size: 12px; color: var(--text-muted); }

.dir-badge {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
}
.dir-badge.in { color: var(--success); background: var(--success-soft); }
.dir-badge.out { color: var(--brand-hover); background: var(--brand-soft); }

.mono { font-family: 'SF Mono', Menlo, monospace; font-size: 13px; }
.muted { color: var(--text-muted); }

.mgr { display: flex; align-items: center; gap: 10px; min-width: 0; }
.mgr-avatar {
  width: 30px; height: 30px;
  border-radius: 50%;
  background: var(--brand-grad);
  color: #fff;
  display: grid; place-items: center;
  font-weight: 700; font-size: 12px;
  flex-shrink: 0;
}
.mgr-name {
  font-size: 13px; font-weight: 500;
  overflow: hidden; white-space: nowrap; text-overflow: ellipsis;
}

.col-record { display: flex; justify-content: center; }
.col-actions { display: flex; justify-content: flex-end; }

.play-icon {
  width: 34px; height: 34px;
  padding: 0;
  border-radius: 10px;
  display: grid; place-items: center;
  background: var(--brand-soft);
  border: 1px solid transparent;
  color: var(--brand-hover);
  box-shadow: none;
}
.play-icon:hover { background: rgba(20, 184, 166, 0.15); }
.play-icon.active {
  background: var(--danger-soft);
  color: var(--danger);
}

.action-icon {
  width: 34px; height: 34px;
  padding: 0;
  border-radius: 10px;
  display: grid; place-items: center;
  border: 1px solid transparent;
  box-shadow: none;
  cursor: pointer;
}
.action-icon .spinner { width: 14px; height: 14px; border-width: 2px; }
.action-icon.analyze {
  background: var(--brand);
  color: #fff;
  box-shadow: 0 6px 14px -6px rgba(20, 184, 166, 0.55);
}
.action-icon.analyze:hover { background: var(--brand-hover); }
.action-icon.analyze:disabled {
  background: var(--surface-3);
  color: var(--text-muted);
  box-shadow: none;
  cursor: not-allowed;
}
.action-icon.open {
  background: var(--success-soft);
  color: var(--success);
}
.action-icon.open:hover { background: #D1FAE5; }

.player-row {
  grid-column: 1 / -1;
  padding: 12px 0 4px;
}

.pager {
  display: flex; align-items: center; justify-content: center;
  gap: 16px;
  margin-top: 22px;
}
.pager-info { font-size: 13px; color: var(--text-dim); font-weight: 500; }

@media (max-width: 1100px) {
  .filter-grid { grid-template-columns: 1fr 1fr; }
  .filter-actions { grid-column: 1 / -1; }
}
@media (max-width: 600px) {
  .filter-grid { grid-template-columns: 1fr; }
}
@media (max-width: 1000px) {
  .thead { display: none; }
  .trow {
    grid-template-columns: 1fr 1fr;
    gap: 8px;
    padding: 16px;
  }
  .col-date, .col-phone, .col-direction, .col-manager,
  .col-duration, .col-record, .col-actions {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .col-record { align-items: flex-start; }
  .col-actions { grid-column: 1 / -1; align-items: flex-start; justify-content: flex-start; }
}

</style>
