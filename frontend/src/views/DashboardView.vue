<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const router = useRouter()

function todayISO() {
  const d = new Date()
  const off = d.getTimezoneOffset()
  return new Date(d.getTime() - off * 60_000).toISOString().slice(0, 10)
}
function daysAgoISO(n) {
  const d = new Date(); d.setDate(d.getDate() - n)
  const off = d.getTimezoneOffset()
  return new Date(d.getTime() - off * 60_000).toISOString().slice(0, 10)
}

const dateFrom = ref(daysAgoISO(29))
const dateTo = ref(todayISO())
const loading = ref(true)
const error = ref('')
const data = ref(null)

async function load() {
  loading.value = true
  error.value = ''
  try {
    const params = {}
    if (dateFrom.value) params.date_from = new Date(dateFrom.value).toISOString()
    if (dateTo.value) {
      const d = new Date(dateTo.value); d.setHours(23, 59, 59, 999)
      params.date_to = d.toISOString()
    }
    const { data: d } = await api.get('/analytics/overview', { params })
    data.value = d
  } catch (e) {
    error.value = e.response?.data?.detail || 'Не удалось загрузить аналитику'
  } finally {
    loading.value = false
  }
}

function setPreset(p) {
  const t = new Date()
  const fmt = (d) => {
    const off = d.getTimezoneOffset()
    return new Date(d.getTime() - off * 60_000).toISOString().slice(0, 10)
  }
  if (p === 'today') { dateFrom.value = fmt(t); dateTo.value = fmt(t) }
  else if (p === '7d') { const s = new Date(t); s.setDate(t.getDate() - 6); dateFrom.value = fmt(s); dateTo.value = fmt(t) }
  else if (p === '30d') { const s = new Date(t); s.setDate(t.getDate() - 29); dateFrom.value = fmt(s); dateTo.value = fmt(t) }
  else if (p === 'all') { dateFrom.value = ''; dateTo.value = '' }
  load()
}

function isPreset(p) {
  if (p === 'all') return !dateFrom.value && !dateTo.value
  if (!dateFrom.value || !dateTo.value) return false
  const t = new Date()
  const fmt = (d) => {
    const off = d.getTimezoneOffset()
    return new Date(d.getTime() - off * 60_000).toISOString().slice(0, 10)
  }
  if (p === 'today') return dateFrom.value === fmt(t) && dateTo.value === fmt(t)
  if (p === '7d') { const s = new Date(t); s.setDate(t.getDate() - 6); return dateFrom.value === fmt(s) && dateTo.value === fmt(t) }
  if (p === '30d') { const s = new Date(t); s.setDate(t.getDate() - 29); return dateFrom.value === fmt(s) && dateTo.value === fmt(t) }
  return false
}

function scoreClass(score) {
  if (score == null) return 'empty'
  if (score >= 80) return 'good'
  if (score >= 60) return 'ok'
  if (score >= 40) return 'warn'
  return 'bad'
}

function fmtMinutes(sec) {
  if (!sec) return '0м'
  const h = Math.floor(sec / 3600)
  const m = Math.round((sec % 3600) / 60)
  if (h > 0) return `${h}ч ${m}м`
  return `${m}м`
}

function fmtDate(s) {
  if (!s) return '—'
  return new Date(s).toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit', year: '2-digit' })
}

const totals = computed(() => data.value || {
  total_calls: 0, analyzed: 0, avg_score: null, total_duration: 0,
  sentiment_breakdown: {}, criteria: [], operators: [], daily: [],
})

const sentimentLabels = {
  positive: 'Позитивные',
  negative: 'Негативные',
  neutral: 'Нейтральные',
  mixed: 'Смешанные',
  unknown: 'Неизвестно',
}

const dailyMax = computed(() => {
  const calls = totals.value.daily.map(d => d.calls || 0)
  return Math.max(1, ...calls)
})

onMounted(load)
</script>

<template>
  <div class="container">
    <div class="head">
      <div>
        <h1 class="page-title">Dashboard</h1>
        <p class="page-subtitle">Аналитика по звонкам и операторам — по времени звонка.</p>
      </div>
    </div>

    <div class="filters card">
      <div class="filter-row">
        <div class="period-block">
          <label class="label">Период (по дате звонка)</label>
          <div class="date-range">
            <label class="date-input">
              <span class="cal-ico">📅</span>
              <input type="date" v-model="dateFrom" />
            </label>
            <span class="date-sep">—</span>
            <label class="date-input">
              <span class="cal-ico">📅</span>
              <input type="date" v-model="dateTo" />
            </label>
          </div>
        </div>
        <div class="filter-actions">
          <button class="primary" @click="load" :disabled="loading">Применить</button>
        </div>
      </div>
      <div class="presets">
        <button class="chip" :class="{ active: isPreset('today') }" @click="setPreset('today')">Сегодня</button>
        <button class="chip" :class="{ active: isPreset('7d') }" @click="setPreset('7d')">7 дней</button>
        <button class="chip" :class="{ active: isPreset('30d') }" @click="setPreset('30d')">30 дней</button>
        <button class="chip" :class="{ active: isPreset('all') }" @click="setPreset('all')">За всё время</button>
      </div>
    </div>

    <div v-if="error" class="error-msg" style="margin-bottom:16px;">{{ error }}</div>

    <div v-if="loading" class="loading"><span class="spinner"></span> Загрузка…</div>

    <template v-else>
      <!-- KPI -->
      <div class="kpis">
        <div class="kpi card">
          <div class="kpi-label">Всего звонков</div>
          <div class="kpi-value">{{ totals.total_calls.toLocaleString() }}</div>
          <div class="kpi-sub">{{ totals.analyzed }} с анализом</div>
        </div>
        <div class="kpi card">
          <div class="kpi-label">Средний балл</div>
          <div class="kpi-value" :class="scoreClass(totals.avg_score)">{{ totals.avg_score ?? '—' }}</div>
          <div class="kpi-sub">{{ totals.analyzed }} оценок</div>
        </div>
        <div class="kpi card">
          <div class="kpi-label">Общее время</div>
          <div class="kpi-value">{{ fmtMinutes(totals.total_duration) }}</div>
          <div class="kpi-sub">сумма по звонкам</div>
        </div>
        <div class="kpi card">
          <div class="kpi-label">Операторов</div>
          <div class="kpi-value">{{ totals.operators.length }}</div>
          <div class="kpi-sub">в выборке</div>
        </div>
      </div>

      <!-- Settles -->
      <div class="grid-2">
        <div class="card">
          <h2 class="card-title">Средние оценки по критериям</h2>
          <div v-if="!totals.criteria.length" class="empty-inline">Нет данных за период.</div>
          <div v-else class="crit-list">
            <div v-for="c in totals.criteria" :key="c.criterion_id" class="crit">
              <div class="crit-head">
                <div class="crit-name">{{ c.criterion_name }}</div>
                <div class="crit-score" :class="scoreClass(c.avg_score)">{{ c.avg_score }}</div>
              </div>
              <div class="crit-bar">
                <div class="crit-bar-fill" :class="scoreClass(c.avg_score)" :style="{ width: c.avg_score + '%' }"></div>
              </div>
              <div class="crit-meta">{{ c.samples }} оценок</div>
            </div>
          </div>
        </div>

        <div class="card">
          <h2 class="card-title">Тональность разговоров</h2>
          <div v-if="!Object.keys(totals.sentiment_breakdown).length" class="empty-inline">Нет данных.</div>
          <div v-else class="sentiment-list">
            <div
              v-for="(count, key) in totals.sentiment_breakdown"
              :key="key"
              class="sent"
              :class="key"
            >
              <span class="sent-name">{{ sentimentLabels[key] || key }}</span>
              <span class="sent-count">{{ count }}</span>
            </div>
          </div>

          <h2 class="card-title" style="margin-top:24px;">Динамика по дням</h2>
          <div v-if="!totals.daily.length" class="empty-inline">Нет данных.</div>
          <div v-else class="daily">
            <div v-for="d in totals.daily" :key="d.date" class="day">
              <div class="day-bar">
                <div class="day-bar-fill" :style="{ height: (d.calls / dailyMax * 100) + '%' }"></div>
              </div>
              <div class="day-label">{{ fmtDate(d.date) }}</div>
              <div class="day-val">{{ d.calls }}</div>
            </div>
          </div>
        </div>
      </div>

      <!-- Operators -->
      <div class="card op-card">
        <div class="card-head-row">
          <h2 class="card-title">Операторы</h2>
          <span class="muted">{{ totals.operators.length }} в выборке</span>
        </div>

        <div v-if="!totals.operators.length" class="empty-inline">Нет звонков за выбранный период.</div>

        <div v-else class="op-table">
          <div class="op-thead">
            <div class="op-name-col">Оператор</div>
            <div>Звонков</div>
            <div>Анализ</div>
            <div>Время</div>
            <div>Последний</div>
            <div class="op-score-col">Средний балл</div>
          </div>
          <div v-for="op in totals.operators" :key="op.manager_id" class="op-row">
            <div class="op-name-col">
              <div class="op-avatar">{{ (op.manager || '?')[0]?.toUpperCase() }}</div>
              <div class="op-name">{{ op.manager || 'Без имени' }}</div>
            </div>
            <div class="num">{{ op.calls }}</div>
            <div class="num">{{ op.analyzed }}</div>
            <div class="num">{{ fmtMinutes(op.total_duration) }}</div>
            <div class="num">{{ fmtDate(op.last_call_at) }}</div>
            <div class="op-score-col">
              <div class="score-pill" :class="scoreClass(op.avg_score)">
                {{ op.avg_score ?? '—' }}
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.head { display: flex; align-items: flex-start; gap: 16px; margin-bottom: 22px; }

.filters { padding: 18px 22px; margin-bottom: 22px; }
.filter-row {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 14px;
  align-items: end;
}
.period-block .label { margin-bottom: 8px; }
.filter-actions { display: flex; gap: 10px; }

.date-range {
  display: flex;
  align-items: center;
  gap: 8px;
  background: var(--surface-2);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 6px 10px;
  max-width: 460px;
  transition: border-color 0.15s, background 0.15s, box-shadow 0.15s;
}
.date-range:focus-within {
  border-color: var(--brand);
  background: var(--surface);
  box-shadow: 0 0 0 4px rgba(3, 129, 254, 0.15);
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
.date-input .cal-ico { font-size: 14px; opacity: 0.7; pointer-events: none; }
.date-input input {
  border: none;
  background: transparent;
  padding: 0;
  width: 100%;
  font-size: 14px;
  font-weight: 500;
  color: var(--text);
  font-family: inherit;
  outline: none;
  cursor: pointer;
}
.date-input input::-webkit-calendar-picker-indicator {
  position: absolute; inset: 0;
  width: 100%; height: 100%;
  opacity: 0; cursor: pointer;
}
.date-sep { color: var(--text-muted); font-size: 14px; flex-shrink: 0; }

.presets { display: flex; gap: 8px; margin-top: 14px; flex-wrap: wrap; }
.chip {
  padding: 6px 14px;
  font-size: 12px;
  font-weight: 600;
  border-radius: 999px;
  background: var(--surface-2);
  border: 1px solid var(--border);
  color: var(--text-dim);
  box-shadow: none;
  cursor: pointer;
}
.chip:hover { background: var(--surface-3); color: var(--text); }
.chip.active { background: var(--brand); color: #fff; border-color: transparent; }
.chip.active:hover { background: var(--brand-hover); }

.loading { display: flex; align-items: center; gap: 10px; color: var(--text-dim); padding: 30px 0; }

.kpis {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14px;
  margin-bottom: 22px;
}
.kpi { padding: 18px 20px; }
.kpi-label { font-size: 12px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.08em; }
.kpi-value {
  font-size: 30px;
  font-weight: 800;
  letter-spacing: -0.02em;
  margin-top: 4px;
  background: var(--brand-grad);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}
.kpi-value.good { background: linear-gradient(135deg, var(--success), #2ec77a); -webkit-background-clip: text; background-clip: text; }
.kpi-value.warn { background: linear-gradient(135deg, var(--warn), #f0b020); -webkit-background-clip: text; background-clip: text; }
.kpi-value.bad { background: linear-gradient(135deg, var(--danger), #ff6b6b); -webkit-background-clip: text; background-clip: text; }
.kpi-value.empty { background: none; color: var(--text-muted); -webkit-text-fill-color: currentColor; }
.kpi-sub { font-size: 12px; color: var(--text-muted); margin-top: 2px; }

.card-title { font-size: 15px; font-weight: 700; margin: 0 0 14px; letter-spacing: -0.01em; }
.card-head-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; }
.card-head-row .card-title { margin: 0; }
.muted { color: var(--text-muted); font-size: 12px; }

.grid-2 {
  display: grid;
  grid-template-columns: 1.2fr 1fr;
  gap: 18px;
  margin-bottom: 22px;
}
.empty-inline { color: var(--text-muted); font-size: 14px; padding: 12px 0; }

.crit-list { display: flex; flex-direction: column; gap: 16px; }
.crit-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
.crit-name { font-size: 14px; font-weight: 600; }
.crit-score {
  font-size: 13px;
  font-weight: 700;
  padding: 2px 10px;
  border-radius: 999px;
}
.crit-score.good { color: var(--success); background: var(--success-soft); }
.crit-score.ok { color: var(--brand); background: var(--brand-soft); }
.crit-score.warn { color: var(--warn); background: var(--warn-soft); }
.crit-score.bad { color: var(--danger); background: var(--danger-soft); }
.crit-score.empty { color: var(--text-muted); background: var(--surface-3); }
.crit-bar { height: 6px; background: var(--surface-3); border-radius: 999px; overflow: hidden; }
.crit-bar-fill { height: 100%; border-radius: 999px; transition: width .6s ease; }
.crit-bar-fill.good { background: linear-gradient(90deg, #1f9d55, #2ec77a); }
.crit-bar-fill.ok { background: var(--brand-grad); }
.crit-bar-fill.warn { background: linear-gradient(90deg, #c98a00, #f0b020); }
.crit-bar-fill.bad { background: linear-gradient(90deg, #e5484d, #ff6b6b); }
.crit-meta { font-size: 11px; color: var(--text-muted); margin-top: 6px; }

.sentiment-list { display: flex; flex-direction: column; gap: 8px; }
.sent {
  display: flex; justify-content: space-between; align-items: center;
  padding: 10px 14px;
  border-radius: 12px;
  font-size: 13px;
  font-weight: 600;
}
.sent.positive { background: var(--success-soft); color: var(--success); }
.sent.negative { background: var(--danger-soft); color: var(--danger); }
.sent.neutral { background: var(--surface-3); color: var(--text-dim); }
.sent.mixed { background: var(--warn-soft); color: var(--warn); }
.sent.unknown { background: var(--surface-3); color: var(--text-muted); }
.sent-count { font-size: 14px; font-weight: 800; }

.daily {
  display: flex;
  gap: 6px;
  height: 120px;
  align-items: flex-end;
  overflow-x: auto;
  padding-bottom: 4px;
}
.day {
  display: flex; flex-direction: column; align-items: center;
  gap: 4px;
  flex-shrink: 0;
  min-width: 38px;
}
.day-bar {
  height: 80px; width: 100%;
  display: flex; align-items: flex-end;
  background: var(--surface-2);
  border-radius: 6px;
  overflow: hidden;
}
.day-bar-fill {
  width: 100%;
  background: var(--brand-grad);
  border-radius: 6px;
  min-height: 4px;
  transition: height .4s ease;
}
.day-label { font-size: 10px; color: var(--text-muted); }
.day-val { font-size: 11px; font-weight: 700; color: var(--text); }

.op-card { padding: 22px; }
.op-table { display: flex; flex-direction: column; }
.op-thead, .op-row {
  display: grid;
  grid-template-columns: 1.6fr 80px 80px 90px 100px 110px;
  gap: 12px;
  align-items: center;
}
.op-thead {
  padding: 10px 0;
  font-size: 11px;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  border-bottom: 1px solid var(--border);
}
.op-row {
  padding: 12px 0;
  border-bottom: 1px solid var(--border);
  font-size: 13px;
}
.op-row:last-child { border-bottom: none; }
.op-name-col { display: flex; align-items: center; gap: 10px; min-width: 0; }
.op-avatar {
  width: 32px; height: 32px;
  border-radius: 50%;
  background: var(--brand-grad);
  color: #fff;
  display: grid; place-items: center;
  font-weight: 700; font-size: 12px;
  flex-shrink: 0;
}
.op-name {
  font-weight: 600;
  overflow: hidden; white-space: nowrap; text-overflow: ellipsis;
}
.num { font-variant-numeric: tabular-nums; }
.op-score-col { display: flex; justify-content: flex-end; }

.score-pill {
  width: 56px; height: 32px;
  border-radius: 10px;
  display: grid; place-items: center;
  font-weight: 800; font-size: 14px;
  letter-spacing: -0.02em;
}
.score-pill.good { background: var(--success-soft); color: var(--success); }
.score-pill.ok { background: var(--brand-soft); color: var(--brand); }
.score-pill.warn { background: var(--warn-soft); color: var(--warn); }
.score-pill.bad { background: var(--danger-soft); color: var(--danger); }
.score-pill.empty { background: var(--surface-3); color: var(--text-muted); }

@media (max-width: 1100px) {
  .kpis { grid-template-columns: repeat(2, 1fr); }
  .grid-2 { grid-template-columns: 1fr; }
}
@media (max-width: 800px) {
  .op-thead, .op-row {
    grid-template-columns: 1.4fr 60px 90px;
  }
  .op-thead > :nth-child(3),
  .op-row > :nth-child(3),
  .op-thead > :nth-child(4),
  .op-row > :nth-child(4),
  .op-thead > :nth-child(5),
  .op-row > :nth-child(5) { display: none; }
  .filter-row { grid-template-columns: 1fr; }
}
</style>
