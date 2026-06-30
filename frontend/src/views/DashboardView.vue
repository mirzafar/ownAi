<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api'
import { useAuthStore } from '../stores/auth'
import {
  Calendar,
  Phone,
  Sparkles,
  Clock,
  Users as UsersIcon,
  TrendingUp,
  TrendingDown,
  ArrowRight,
  ClipboardList,
} from 'lucide-vue-next'

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
const kind = ref('all')           // all | call | lead | chat
const loading = ref(true)
const error = ref('')
const data = ref(null)

async function load() {
  loading.value = true
  error.value = ''
  try {
    const params = {}
    if (kind.value !== 'all') params.kind = kind.value
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

function setKind(k) {
  if (kind.value === k) return
  kind.value = k
  load()
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
  if (score >= 90) return 'good'
  if (score >= 75) return 'ok'
  if (score >= 60) return 'warn'
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

function fmtShortDate(s) {
  if (!s) return '—'
  return new Date(s).toLocaleDateString('ru-RU', { day: '2-digit', month: 'short' })
}

const totals = computed(() => data.value || {
  total: 0, analyzed: 0, avg_score: null, total_duration: 0,
  by_kind: { calls: 0, leads: 0, chats: 0 },
  sentiment_breakdown: {}, grade_breakdown: {},
  criteria: [], operators: [], daily: [],
})

const totalLabel = computed(() => {
  if (kind.value === 'call') return 'звонков'
  if (kind.value === 'lead') return 'лидов'
  if (kind.value === 'chat') return 'чатов'
  return 'записей'
})

const sentimentLabels = {
  positive: 'Позитивные',
  negative: 'Негативные',
  neutral: 'Нейтральные',
  mixed: 'Смешанные',
  unknown: 'Неизвестно',
}

const trend = computed(() => {
  const daily = totals.value.daily || []
  if (daily.length < 4) return { delta: null, dir: 'flat' }
  const half = Math.floor(daily.length / 2)
  const first = daily.slice(0, half).reduce((s, d) => s + (d.total || 0), 0)
  const second = daily.slice(half).reduce((s, d) => s + (d.total || 0), 0)
  if (first === 0) return { delta: second > 0 ? 100 : 0, dir: 'up' }
  const pct = Math.round(((second - first) / first) * 100)
  return { delta: Math.abs(pct), dir: pct >= 0 ? 'up' : 'down' }
})

const chartWidth = 720
const chartHeight = 220
const chartPad = { top: 20, right: 16, bottom: 28, left: 32 }

const chart = computed(() => {
  const daily = totals.value.daily || []
  if (!daily.length) return null
  const innerW = chartWidth - chartPad.left - chartPad.right
  const innerH = chartHeight - chartPad.top - chartPad.bottom
  const max = Math.max(1, ...daily.map(d => d.total || 0))
  const step = daily.length > 1 ? innerW / (daily.length - 1) : 0
  const points = daily.map((d, i) => ({
    x: chartPad.left + i * step,
    y: chartPad.top + innerH - ((d.total || 0) / max) * innerH,
    v: d.total || 0,
    date: d.date,
  }))
  let line = ''
  if (points.length === 1) {
    line = `M ${points[0].x} ${points[0].y}`
  } else {
    line = `M ${points[0].x} ${points[0].y}`
    for (let i = 0; i < points.length - 1; i++) {
      const p0 = points[i - 1] || points[i]
      const p1 = points[i]
      const p2 = points[i + 1]
      const p3 = points[i + 2] || p2
      const cp1x = p1.x + (p2.x - p0.x) / 6
      const cp1y = p1.y + (p2.y - p0.y) / 6
      const cp2x = p2.x - (p3.x - p1.x) / 6
      const cp2y = p2.y - (p3.y - p1.y) / 6
      line += ` C ${cp1x} ${cp1y}, ${cp2x} ${cp2y}, ${p2.x} ${p2.y}`
    }
  }
  const area = `${line} L ${points[points.length - 1].x} ${chartPad.top + innerH} L ${points[0].x} ${chartPad.top + innerH} Z`
  const yTicks = [0, 0.25, 0.5, 0.75, 1].map(t => ({
    y: chartPad.top + innerH - innerH * t,
    label: Math.round(max * t),
  }))
  const xLabelEvery = Math.max(1, Math.ceil(daily.length / 6))
  const xLabels = points.map((p, i) => ({ ...p, show: i % xLabelEvery === 0 || i === points.length - 1 }))
  return { points, line, area, yTicks, xLabels, max }
})

const gradeOrder = ['Эталон', 'Хороший', 'Удовлетворительно', 'Неудовлетворительно']
const gradeRows = computed(() => {
  const map = totals.value.grade_breakdown || {}
  return gradeOrder
    .map(g => ({ name: g, count: map[g] || 0 }))
    .filter(r => r.count > 0)
})

function gradeClass(name) {
  if (name === 'Эталон') return 'good'
  if (name === 'Хороший') return 'ok'
  if (name === 'Удовлетворительно') return 'warn'
  return 'bad'
}

onMounted(load)
</script>

<template>
  <div class="container">

    <div class="filters card">
      <div class="filter-row">
        <div class="period-block">
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
          <button class="primary" @click="load" :disabled="loading">Применить</button>
        </div>
      </div>
      <div class="filter-row2">
        <div class="presets">
          <button class="chip" :class="{ active: isPreset('today') }" @click="setPreset('today')">Сегодня</button>
          <button class="chip" :class="{ active: isPreset('7d') }" @click="setPreset('7d')">7 дней</button>
          <button class="chip" :class="{ active: isPreset('30d') }" @click="setPreset('30d')">30 дней</button>
          <button class="chip" :class="{ active: isPreset('all') }" @click="setPreset('all')">За всё время</button>
        </div>
        <div class="kind-switch">
          <button class="chip" :class="{ active: kind === 'all' }" @click="setKind('all')">Все</button>
          <button class="chip" :class="{ active: kind === 'call' }" @click="setKind('call')">Звонки</button>
          <button class="chip" :class="{ active: kind === 'lead' }" @click="setKind('lead')">Лиды</button>
          <button class="chip" :class="{ active: kind === 'chat' }" @click="setKind('chat')">Чаты</button>
        </div>
      </div>
    </div>

    <div v-if="error" class="error-msg" style="margin-bottom:16px;">{{ error }}</div>

    <div v-if="loading" class="loading"><span class="spinner"></span> Загрузка…</div>

    <template v-else>
      <!-- KPI -->
      <div class="kpis">
        <div class="kpi card">
          <div class="kpi-top">
            <div class="kpi-icon brand"><Phone :size="18" /></div>
            <span v-if="trend.delta != null && totals.daily.length" class="kpi-trend" :class="trend.dir">
              <component :is="trend.dir === 'up' ? TrendingUp : TrendingDown" :size="12" />
              {{ trend.delta }}%
            </span>
          </div>
          <div class="kpi-label">Всего {{ totalLabel }}</div>
          <div class="kpi-value">{{ totals.total.toLocaleString('ru-RU') }}</div>
          <div class="kpi-sub">
            <template v-if="kind === 'all'">
              {{ totals.by_kind.calls }} звонков · {{ totals.by_kind.leads }} лидов
            </template>
            <template v-else>{{ totals.analyzed }} с анализом</template>
          </div>
        </div>
        <div class="kpi card">
          <div class="kpi-top">
            <div class="kpi-icon accent"><Sparkles :size="18" /></div>
          </div>
          <div class="kpi-label">Средний балл</div>
          <div class="kpi-value" :class="scoreClass(totals.avg_score)">{{ totals.avg_score ?? '—' }}</div>
          <div class="kpi-sub">по 100-балльной шкале</div>
        </div>
        <div class="kpi card">
          <div class="kpi-top">
            <div class="kpi-icon warn"><Clock :size="18" /></div>
          </div>
          <div class="kpi-label">Общее время</div>
          <div class="kpi-value">{{ fmtMinutes(totals.total_duration) }}</div>
          <div class="kpi-sub">сумма по звонкам</div>
        </div>
        <div class="kpi card">
          <div class="kpi-top">
            <div class="kpi-icon info"><UsersIcon :size="18" /></div>
          </div>
          <div class="kpi-label">Операторов</div>
          <div class="kpi-value">{{ totals.operators.length }}</div>
          <div class="kpi-sub">в выборке</div>
        </div>
      </div>

      <!-- Big chart -->
      <div class="card chart-card">
        <div class="chart-head">
          <div>
            <div class="chart-eyebrow">Динамика — {{ totalLabel }}</div>
            <div class="chart-title">
              {{ totals.total.toLocaleString('ru-RU') }} <span class="chart-unit">{{ totalLabel }}</span>
            </div>
          </div>
          <div v-if="trend.delta != null" class="chart-trend" :class="trend.dir">
            <component :is="trend.dir === 'up' ? TrendingUp : TrendingDown" :size="14" />
            {{ trend.delta }}% за период
          </div>
        </div>
        <div v-if="!chart" class="empty-inline">Нет данных за выбранный период.</div>
        <svg v-else
          class="chart-svg"
          :viewBox="`0 0 ${chartWidth} ${chartHeight}`"
          preserveAspectRatio="none"
        >
          <defs>
            <linearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stop-color="#8B5CF6" stop-opacity="0.30" />
              <stop offset="60%" stop-color="#EC4899" stop-opacity="0.08" />
              <stop offset="100%" stop-color="#EC4899" stop-opacity="0" />
            </linearGradient>
            <linearGradient id="lineGrad" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stop-color="#8B5CF6" />
              <stop offset="100%" stop-color="#EC4899" />
            </linearGradient>
          </defs>
          <g class="grid">
            <line v-for="(t, i) in chart.yTicks" :key="i"
              :x1="chartPad.left" :x2="chartWidth - chartPad.right"
              :y1="t.y" :y2="t.y" />
          </g>
          <g class="y-axis">
            <text v-for="(t, i) in chart.yTicks" :key="i"
              :x="chartPad.left - 8" :y="t.y + 4"
              text-anchor="end">{{ t.label }}</text>
          </g>
          <path :d="chart.area" fill="url(#areaGrad)" />
          <path :d="chart.line" fill="none" stroke="url(#lineGrad)" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round" />
          <g class="points">
            <circle v-for="(p, i) in chart.points" :key="i"
              :cx="p.x" :cy="p.y" r="3"
              fill="#fff" stroke="#EC4899" stroke-width="2">
              <title>{{ fmtDate(p.date) }} · {{ p.v }}</title>
            </circle>
          </g>
          <g class="x-axis">
            <text v-for="(p, i) in chart.xLabels.filter(pp => pp.show)" :key="i"
              :x="p.x" :y="chartHeight - 8"
              text-anchor="middle">{{ fmtShortDate(p.date) }}</text>
          </g>
        </svg>
      </div>

      <!-- Settles -->
      <div class="grid-2">
        <div class="card">
          <h2 class="card-title">Средние оценки по критериям</h2>
          <div v-if="!totals.criteria.length" class="empty-inline">Нет данных за период.</div>
          <div v-else class="crit-list">
            <div v-for="c in totals.criteria" :key="c.id" class="crit">
              <div class="crit-head">
                <div class="crit-name">{{ c.name }}</div>
                <div class="crit-score" :class="scoreClass(Math.round((c.avg_score / Math.max(1,c.max_score)) * 100))">
                  {{ c.avg_score }}<span class="crit-max">/{{ c.max_score }}</span>
                </div>
              </div>
              <div class="crit-bar">
                <div class="crit-bar-fill"
                  :class="scoreClass(Math.round((c.avg_score / Math.max(1,c.max_score)) * 100))"
                  :style="{ width: Math.min(100, (c.avg_score / Math.max(1,c.max_score)) * 100) + '%' }"></div>
              </div>
              <div class="crit-meta">{{ c.samples }} оценок · {{ c.category_name }}</div>
            </div>
          </div>
        </div>

        <div class="card">
          <h2 class="card-title">Распределение оценок</h2>
          <div v-if="!gradeRows.length" class="empty-inline">Нет данных.</div>
          <div v-else class="grade-list">
            <div v-for="g in gradeRows" :key="g.name" class="grade" :class="gradeClass(g.name)">
              <span class="grade-dot"></span>
              <span class="grade-name">{{ g.name }}</span>
              <span class="grade-count">{{ g.count }}</span>
            </div>
          </div>

          <h2 class="card-title" style="margin-top:24px;">Тональность</h2>
          <div v-if="!Object.keys(totals.sentiment_breakdown).length" class="empty-inline">Нет данных.</div>
          <div v-else class="sentiment-list">
            <div
              v-for="(count, key) in totals.sentiment_breakdown"
              :key="key"
              class="sent"
              :class="key"
            >
              <span class="sent-dot"></span>
              <span class="sent-name">{{ sentimentLabels[key] || key }}</span>
              <span class="sent-count">{{ count }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Operators -->
      <div class="card op-card">
        <div class="card-head-row">
          <h2 class="card-title">Операторы</h2>
          <button class="link-btn" @click="router.push('/operators')">
            Все операторы <ArrowRight :size="14" />
          </button>
        </div>

        <div v-if="!totals.operators.length" class="empty-inline">Нет записей за выбранный период.</div>

        <div v-else class="op-table">
          <div class="op-thead">
            <div class="op-name-col">Оператор</div>
            <div>Звонков</div>
            <div>Лидов</div>
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
            <div class="num">{{ op.leads }}</div>
            <div class="num">{{ fmtMinutes(op.total_duration) }}</div>
            <div class="num muted">{{ fmtDate(op.last_activity_at) }}</div>
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
.filter-row2 {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-top: 14px;
  flex-wrap: wrap;
}
.period-block .label { margin-bottom: 8px; }
.filter-actions { display: flex; gap: 10px; }

.date-range {
  display: flex; align-items: center; gap: 8px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 4px 10px;
  max-width: 460px;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.date-range:focus-within {
  border-color: var(--brand);
  box-shadow: 0 0 0 4px rgba(20, 184, 166, 0.12);
}
.date-input {
  position: relative;
  display: flex; align-items: center; gap: 8px;
  flex: 1; min-width: 0;
  padding: 6px 8px;
  cursor: pointer;
}
.date-input .cal-ico { color: var(--text-muted); pointer-events: none; }
.date-input input {
  border: none; background: transparent;
  padding: 0; width: 100%;
  font-size: 13px; font-weight: 500;
  color: var(--text);
  font-family: inherit;
  outline: none; cursor: pointer; box-shadow: none;
}
.date-input input::-webkit-calendar-picker-indicator {
  position: absolute; inset: 0; width: 100%; height: 100%; opacity: 0; cursor: pointer;
}
.date-sep { color: var(--text-muted); font-size: 14px; flex-shrink: 0; }

.presets, .kind-switch { display: flex; gap: 8px; flex-wrap: wrap; }

.loading { display: flex; align-items: center; gap: 10px; color: var(--text-dim); padding: 30px 0; }

.kpis {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 18px;
}
.kpi { padding: 20px 22px; }
.kpi-top { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.kpi-icon {
  width: 38px; height: 38px;
  border-radius: 12px;
  display: grid; place-items: center;
  color: #fff;
}
.kpi-icon.brand { background: var(--brand-grad); box-shadow: 0 8px 18px -8px rgba(20, 184, 166, 0.55); }
.kpi-icon.accent { background: var(--accent-grad); box-shadow: 0 8px 18px -8px rgba(139, 92, 246, 0.5); }
.kpi-icon.warn { background: linear-gradient(135deg, #FBBF24, #F59E0B); box-shadow: 0 8px 18px -8px rgba(245, 158, 11, 0.45); }
.kpi-icon.info { background: linear-gradient(135deg, #60A5FA, #3B82F6); box-shadow: 0 8px 18px -8px rgba(59, 130, 246, 0.45); }
.kpi-trend {
  display: inline-flex; align-items: center; gap: 3px;
  font-size: 11px; font-weight: 700;
  padding: 4px 8px; border-radius: 999px;
}
.kpi-trend.up { background: var(--success-soft); color: var(--success); }
.kpi-trend.down { background: var(--danger-soft); color: var(--danger); }
.kpi-label { font-size: 13px; color: var(--text-dim); font-weight: 500; }
.kpi-value { font-size: 28px; font-weight: 700; letter-spacing: -0.02em; margin-top: 2px; color: var(--text); }
.kpi-value.good { color: var(--success); }
.kpi-value.ok { color: var(--brand-hover); }
.kpi-value.warn { color: var(--warn); }
.kpi-value.bad { color: var(--danger); }
.kpi-value.empty { color: var(--text-muted); }
.kpi-sub { font-size: 12px; color: var(--text-muted); margin-top: 4px; }

.chart-card { padding: 22px 22px 14px; margin-bottom: 18px; }
.chart-head { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px; gap: 12px; flex-wrap: wrap; }
.chart-eyebrow { font-size: 12px; font-weight: 600; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.06em; }
.chart-title { font-size: 26px; font-weight: 700; letter-spacing: -0.02em; margin-top: 4px; }
.chart-unit { font-size: 14px; font-weight: 500; color: var(--text-muted); }
.chart-trend {
  display: inline-flex; align-items: center; gap: 4px;
  font-size: 12px; font-weight: 600;
  padding: 6px 10px; border-radius: 999px;
}
.chart-trend.up { background: var(--success-soft); color: var(--success); }
.chart-trend.down { background: var(--danger-soft); color: var(--danger); }
.chart-svg { width: 100%; height: auto; display: block; }
.chart-svg .grid line { stroke: var(--border); stroke-dasharray: 3 4; }
.chart-svg .y-axis text,
.chart-svg .x-axis text { font-size: 10px; fill: var(--text-muted); font-weight: 500; }

.card-title { font-size: 15px; font-weight: 700; margin: 0 0 14px; letter-spacing: -0.01em; }
.card-head-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; }
.card-head-row .card-title { margin: 0; }
.muted { color: var(--text-muted); }
.link-btn {
  display: inline-flex; align-items: center; gap: 4px;
  background: transparent; border: none; padding: 6px 8px;
  color: var(--brand); font-size: 13px; font-weight: 600;
  box-shadow: none;
}
.link-btn:hover { color: var(--brand-hover); background: var(--brand-soft); }

.grid-2 {
  display: grid; grid-template-columns: 1.2fr 1fr;
  gap: 18px; margin-bottom: 18px;
}
.empty-inline { color: var(--text-muted); font-size: 14px; padding: 12px 0; }

.crit-list { display: flex; flex-direction: column; gap: 16px; }
.crit-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
.crit-name { font-size: 14px; font-weight: 600; }
.crit-score {
  font-size: 12px; font-weight: 700;
  padding: 3px 10px; border-radius: 999px;
}
.crit-max { color: var(--text-muted); margin-left: 2px; font-weight: 600; }
.crit-score.good { color: var(--success); background: var(--success-soft); }
.crit-score.ok { color: var(--brand-hover); background: var(--brand-soft); }
.crit-score.warn { color: var(--warn); background: var(--warn-soft); }
.crit-score.bad { color: var(--danger); background: var(--danger-soft); }
.crit-score.empty { color: var(--text-muted); background: var(--surface-3); }
.crit-bar { height: 6px; background: var(--surface-3); border-radius: 999px; overflow: hidden; }
.crit-bar-fill { height: 100%; border-radius: 999px; transition: width .6s ease; }
.crit-bar-fill.good { background: linear-gradient(90deg, #10B981, #34D399); }
.crit-bar-fill.ok { background: var(--brand-grad); }
.crit-bar-fill.warn { background: linear-gradient(90deg, #F59E0B, #FBBF24); }
.crit-bar-fill.bad { background: linear-gradient(90deg, #EF4444, #F87171); }
.crit-meta { font-size: 11px; color: var(--text-muted); margin-top: 6px; }

.grade-list, .sentiment-list { display: flex; flex-direction: column; gap: 8px; }
.grade, .sent {
  display: flex; align-items: center; gap: 10px;
  padding: 12px 14px;
  border-radius: 12px;
  font-size: 13px; font-weight: 600;
}
.grade-dot, .sent-dot { width: 8px; height: 8px; border-radius: 50%; background: currentColor; }
.grade-name, .sent-name { flex: 1; }
.grade-count, .sent-count { font-size: 14px; font-weight: 800; }
.grade.good, .sent.positive { background: var(--success-soft); color: var(--success); }
.grade.bad, .sent.negative { background: var(--danger-soft); color: var(--danger); }
.grade.warn, .sent.mixed { background: var(--warn-soft); color: var(--warn); }
.grade.ok { background: var(--brand-soft); color: var(--brand-hover); }
.sent.neutral, .sent.unknown { background: var(--surface-3); color: var(--text-dim); }

.op-card { padding: 22px; }
.op-table { display: flex; flex-direction: column; }
.op-thead, .op-row {
  display: grid;
  grid-template-columns: 1.6fr 80px 80px 90px 110px 110px;
  gap: 12px;
  align-items: center;
}
.op-thead {
  padding: 10px 0;
  font-size: 11px; font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase; letter-spacing: 0.06em;
  border-bottom: 1px solid var(--border);
}
.op-row { padding: 14px 0; border-bottom: 1px solid var(--border); font-size: 13px; }
.op-row:last-child { border-bottom: none; }
.op-name-col { display: flex; align-items: center; gap: 10px; min-width: 0; }
.op-avatar {
  width: 36px; height: 36px;
  border-radius: 50%;
  background: var(--brand-grad);
  color: #fff;
  display: grid; place-items: center;
  font-weight: 700; font-size: 13px;
  flex-shrink: 0;
}
.op-name {
  font-weight: 600;
  overflow: hidden; white-space: nowrap; text-overflow: ellipsis;
}
.num { font-variant-numeric: tabular-nums; color: var(--text-dim); }
.op-score-col { display: flex; justify-content: flex-end; }
.score-pill {
  min-width: 56px; height: 30px;
  padding: 0 12px;
  border-radius: 10px;
  display: grid; place-items: center;
  font-weight: 700; font-size: 13px;
  letter-spacing: -0.02em;
}
.score-pill.good { background: var(--success-soft); color: var(--success); }
.score-pill.ok { background: var(--brand-soft); color: var(--brand-hover); }
.score-pill.warn { background: var(--warn-soft); color: var(--warn); }
.score-pill.bad { background: var(--danger-soft); color: var(--danger); }
.score-pill.empty {
  background: transparent;
  border: 1px dashed var(--border-strong);
  color: var(--text-muted);
  font-weight: 500;
  min-width: 40px;
}

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
