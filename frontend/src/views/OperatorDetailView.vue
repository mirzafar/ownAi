<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../api'

const route = useRoute()
const router = useRouter()

const detail = ref(null)
const loading = ref(true)
const error = ref('')
const days = ref(5)

const managerId = computed(() => decodeURIComponent(route.params.id))

// Полная серия по дням (с заполнением пропусков), хронологически по возрастанию.
const series = computed(() => {
  if (!detail.value) return []
  const map = new Map((detail.value.daily || []).map(d => [d.date, d]))
  const period = detail.value.period_days || 5
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const out = []
  for (let i = period - 1; i >= 0; i--) {
    const dt = new Date(today)
    dt.setDate(today.getDate() - i)
    const key = [
      dt.getFullYear(),
      String(dt.getMonth() + 1).padStart(2, '0'),
      String(dt.getDate()).padStart(2, '0'),
    ].join('-')
    const row = map.get(key)
    out.push({
      date: key,
      calls: row?.calls || 0,
      analyzed: row?.analyzed || 0,
      avg_score: row?.avg_score ?? null,
      total_duration: row?.total_duration || 0,
    })
  }
  // delta vs prev day with data
  let prev = null
  for (const r of out) {
    if (r.avg_score != null) {
      r.delta = prev != null ? Math.round((r.avg_score - prev) * 10) / 10 : null
      prev = r.avg_score
    } else {
      r.delta = null
    }
  }
  return out
})

const trend = computed(() => {
  const s = series.value
  const withScore = s.filter(d => d.avg_score != null)
  if (withScore.length < 1) return null
  const first = withScore[0]
  const last = withScore[withScore.length - 1]
  const change = withScore.length >= 2
    ? Math.round((last.avg_score - first.avg_score) * 10) / 10
    : 0
  const best = withScore.reduce((a, b) => (b.avg_score > a.avg_score ? b : a), withScore[0])
  const worst = withScore.reduce((a, b) => (b.avg_score < a.avg_score ? b : a), withScore[0])
  return { first, last, change, best, worst, points: withScore.length }
})

const chartHover = ref(null)

const chart = computed(() => {
  const data = series.value
  if (!data.length) return null
  const W = 720
  const H = 220
  const padL = 36
  const padR = 16
  const padT = 18
  const padB = 36
  const innerW = W - padL - padR
  const innerH = H - padT - padB

  const n = data.length
  const xStep = n > 1 ? innerW / (n - 1) : 0
  const x = i => padL + (n > 1 ? i * xStep : innerW / 2)
  const y = score => padT + innerH - (score / 100) * innerH

  const maxCalls = Math.max(1, ...data.map(d => d.calls || 0))
  const barW = Math.max(6, Math.min(28, innerW / n - 6))
  const barX = i => x(i) - barW / 2
  const barH = c => Math.max(0, (c / maxCalls) * (innerH * 0.35))
  const barY = c => padT + innerH - barH(c)

  const pts = data.map((d, i) => ({
    i,
    cx: x(i),
    cy: d.avg_score != null ? y(d.avg_score) : null,
    barX: barX(i),
    barY: barY(d.calls || 0),
    barH: barH(d.calls || 0),
    barW,
    data: d,
  }))

  // Линия только по точкам со score (разрывы)
  const segments = []
  let current = []
  for (const p of pts) {
    if (p.cy != null) {
      current.push(p)
    } else if (current.length) {
      segments.push(current)
      current = []
    }
  }
  if (current.length) segments.push(current)

  // Сглаживание Catmull-Rom → кубический Безье. Контрольные точки
  // строим как касательные к соседним вершинам с натяжением `tension`.
  const tension = 0.35
  function smoothPath(seg, { closeBottom = false, baseY = 0 } = {}) {
    if (!seg.length) return ''
    if (seg.length === 1) return ''
    const cmds = [`M ${seg[0].cx} ${seg[0].cy}`]
    for (let i = 0; i < seg.length - 1; i++) {
      const p0 = seg[i - 1] || seg[i]
      const p1 = seg[i]
      const p2 = seg[i + 1]
      const p3 = seg[i + 2] || p2
      const c1x = p1.cx + (p2.cx - p0.cx) * tension
      const c1y = p1.cy + (p2.cy - p0.cy) * tension
      const c2x = p2.cx - (p3.cx - p1.cx) * tension
      const c2y = p2.cy - (p3.cy - p1.cy) * tension
      cmds.push(`C ${c1x} ${c1y}, ${c2x} ${c2y}, ${p2.cx} ${p2.cy}`)
    }
    if (closeBottom) {
      cmds.push(`L ${seg[seg.length - 1].cx} ${baseY}`)
      cmds.push(`L ${seg[0].cx} ${baseY}`)
      cmds.push('Z')
    }
    return cmds.join(' ')
  }

  const linePath = segments.map(seg => smoothPath(seg))
    .filter(Boolean).join(' ')

  const baseY = padT + innerH
  const areaPath = segments.map(seg => smoothPath(seg, { closeBottom: true, baseY }))
    .filter(Boolean).join(' ')

  const yTicks = [0, 25, 50, 75, 100].map(v => ({ v, y: y(v) }))

  return { W, H, padL, padR, padT, padB, innerW, innerH, pts, linePath, areaPath, yTicks }
})

async function load() {
  loading.value = true
  error.value = ''
  try {
    const { data } = await api.get(
      `/analytics/operators/${encodeURIComponent(managerId.value)}`,
      { params: { days: days.value } }
    )
    detail.value = data
  } catch (e) {
    error.value = e.response?.data?.detail || 'Не удалось загрузить оператора'
  } finally {
    loading.value = false
  }
}

watch(() => route.params.id, load)
watch(days, load)

function fmtDate(s) {
  if (!s) return '—'
  return new Date(s).toLocaleString('ru-RU', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

function fmtDay(s) {
  if (!s) return ''
  const d = new Date(s + 'T00:00:00')
  return d.toLocaleDateString('ru-RU', { day: '2-digit', month: 'short', weekday: 'short' })
}

function fmtDayShort(s) {
  if (!s) return ''
  const d = new Date(s + 'T00:00:00')
  return d.toLocaleDateString('ru-RU', { day: '2-digit', month: 'short' })
}

function fmtDelta(v) {
  if (v == null) return ''
  if (v === 0) return '±0'
  return (v > 0 ? '+' : '') + v
}

function deltaClass(v) {
  if (v == null || v === 0) return 'flat'
  return v > 0 ? 'up' : 'down'
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

function statusLabel(s) {
  return { done: 'Готов', processing: 'В работе', failed: 'Ошибка' }[s] || s
}

function preview(item) {
  if (item.sales_analysis?.meta?.system_verdict) return item.sales_analysis.meta.system_verdict
  if (item.analysis?.summary) return item.analysis.summary
  const t = item.text || ''
  return t.length > 200 ? t.slice(0, 200) + '…' : t || 'Обработка…'
}

onMounted(load)
</script>

<template>
  <div class="container">
    <div class="head">
      <button class="ghost back" @click="router.push('/operators')">← К операторам</button>
    </div>

    <div v-if="error" class="error-msg" style="margin-bottom:16px;">{{ error }}</div>

    <div v-if="loading" class="loading"><span class="spinner"></span> Загрузка…</div>

    <template v-else-if="detail">
      <div class="profile card">
        <div class="avatar-lg">{{ (detail.manager || '?')[0]?.toUpperCase() }}</div>
        <div class="profile-info">
          <h1 class="profile-name">{{ detail.manager || 'Без имени' }}</h1>
          <div class="profile-meta">
            <span>ID: <b>{{ detail.manager_id || '—' }}</b></span>
            <span>· Последний звонок: <b>{{ fmtDate(detail.stats.last_call_at) }}</b></span>
          </div>
        </div>
        <div class="profile-score" :class="scoreClass(detail.stats.avg_score)">
          {{ detail.stats.avg_score ?? '—' }}
          <div class="score-cap">средний балл</div>
        </div>
      </div>

      <div class="stats">
        <div class="stat card">
          <div class="stat-label">Звонков всего</div>
          <div class="stat-value">{{ detail.stats.calls }}</div>
        </div>
        <div class="stat card">
          <div class="stat-label">Проанализировано</div>
          <div class="stat-value">{{ detail.stats.analyzed }}</div>
        </div>
        <div class="stat card">
          <div class="stat-label">Длительность</div>
          <div class="stat-value">{{ fmtDuration(detail.stats.total_duration) }}</div>
        </div>
        <div class="stat card">
          <div class="stat-label">За {{ detail.period_days }} дн.</div>
          <div class="stat-value">{{ detail.analyses.length }}</div>
        </div>
      </div>

      <div class="section">
        <div class="section-head">
          <h2 class="section-title">Динамика за последние {{ detail.period_days }} дней</h2>
          <div class="day-switch">
            <button
              v-for="opt in [3, 5, 7, 14, 30]"
              :key="opt"
              class="day-btn"
              :class="{ active: days === opt }"
              @click="days = opt"
            >{{ opt }} дн.</button>
          </div>
        </div>

        <div v-if="!trend" class="empty card small">
          За выбранный период данных для графика нет.
        </div>

        <div v-else class="chart-wrap card">
          <div class="trend-row">
            <div class="trend-main">
              <div class="trend-cap">Изменение среднего балла</div>
              <div class="trend-val" :class="deltaClass(trend.change)">
                <span class="arr">{{ trend.change > 0 ? '↑' : trend.change < 0 ? '↓' : '→' }}</span>
                {{ fmtDelta(trend.change) }}
                <span class="trend-unit">балла</span>
              </div>
              <div class="trend-sub">
                {{ fmtDayShort(trend.first.date) }} ({{ trend.first.avg_score }})
                →
                {{ fmtDayShort(trend.last.date) }} ({{ trend.last.avg_score }})
              </div>
            </div>
            <div class="trend-side">
              <div class="trend-cell">
                <div class="cell-cap">Лучший день</div>
                <div class="cell-val good">{{ trend.best.avg_score }} <span class="cell-day">· {{ fmtDayShort(trend.best.date) }}</span></div>
              </div>
              <div class="trend-cell">
                <div class="cell-cap">Худший день</div>
                <div class="cell-val bad">{{ trend.worst.avg_score }} <span class="cell-day">· {{ fmtDayShort(trend.worst.date) }}</span></div>
              </div>
            </div>
          </div>

          <div class="chart-host" v-if="chart">
            <svg :viewBox="`0 0 ${chart.W} ${chart.H}`" preserveAspectRatio="none" class="chart-svg">
              <defs>
                <linearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stop-color="#0381fe" stop-opacity="0.32" />
                  <stop offset="100%" stop-color="#0381fe" stop-opacity="0" />
                </linearGradient>
                <linearGradient id="lineGrad" x1="0" y1="0" x2="1" y2="0">
                  <stop offset="0%" stop-color="#33a0ff" />
                  <stop offset="100%" stop-color="#0381fe" />
                </linearGradient>
                <linearGradient id="barGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stop-color="#0381fe" stop-opacity="0.25" />
                  <stop offset="100%" stop-color="#0381fe" stop-opacity="0.08" />
                </linearGradient>
                <filter id="lineGlow" x="-20%" y="-50%" width="140%" height="200%">
                  <feGaussianBlur in="SourceAlpha" stdDeviation="2.5" />
                  <feOffset dy="2" result="off" />
                  <feComponentTransfer><feFuncA type="linear" slope="0.45" /></feComponentTransfer>
                  <feMerge>
                    <feMergeNode />
                    <feMergeNode in="SourceGraphic" />
                  </feMerge>
                </filter>
              </defs>

              <g class="grid">
                <line
                  v-for="t in chart.yTicks"
                  :key="t.v"
                  :x1="chart.padL" :x2="chart.W - chart.padR"
                  :y1="t.y" :y2="t.y"
                />
                <text
                  v-for="t in chart.yTicks"
                  :key="'l' + t.v"
                  :x="chart.padL - 8" :y="t.y + 4"
                  class="grid-label" text-anchor="end"
                >{{ t.v }}</text>
              </g>

              <g class="bars">
                <rect
                  v-for="p in chart.pts" :key="'b' + p.i"
                  :x="p.barX" :y="p.barY" :width="p.barW" :height="p.barH"
                  rx="4" ry="4"
                  fill="url(#barGrad)"
                />
              </g>

              <path v-if="chart.areaPath" :d="chart.areaPath" fill="url(#areaGrad)" class="area" />
              <path v-if="chart.linePath" :d="chart.linePath" class="line" filter="url(#lineGlow)" />

              <line
                v-if="chartHover"
                class="hover-guide"
                :x1="chartHover.cx" :x2="chartHover.cx"
                :y1="chart.padT" :y2="chart.padT + chart.innerH"
              />

              <g class="dots">
                <g v-for="p in chart.pts" :key="'d' + p.i">
                  <circle
                    v-if="p.cy != null"
                    :cx="p.cx" :cy="p.cy"
                    :r="chartHover && chartHover.i === p.i ? 9 : 5"
                    class="dot-halo"
                    :class="{ active: chartHover && chartHover.i === p.i }"
                  />
                  <circle
                    v-if="p.cy != null"
                    :cx="p.cx" :cy="p.cy"
                    :r="chartHover && chartHover.i === p.i ? 5.5 : 4"
                    class="dot"
                  />
                  <text
                    v-if="p.cy != null && p.data.delta != null && p.data.delta !== 0"
                    :x="p.cx" :y="p.cy - 14"
                    :class="['delta-lbl', deltaClass(p.data.delta)]"
                    text-anchor="middle"
                  >{{ fmtDelta(p.data.delta) }}</text>
                </g>
              </g>

              <g class="x-labels">
                <text
                  v-for="p in chart.pts" :key="'x' + p.i"
                  :x="p.cx" :y="chart.H - 14"
                  class="grid-label" text-anchor="middle"
                  :class="{ active: chartHover && chartHover.i === p.i }"
                >{{ fmtDayShort(p.data.date) }}</text>
              </g>

              <g class="hit-areas">
                <rect
                  v-for="p in chart.pts" :key="'h' + p.i"
                  :x="p.cx - 18" :y="chart.padT"
                  :width="36" :height="chart.innerH"
                  fill="transparent"
                  @mouseenter="chartHover = p"
                  @mouseleave="chartHover = null"
                />
              </g>
            </svg>

            <div
              v-if="chartHover"
              class="tooltip"
              :style="{
                left: ((chartHover.cx / chart.W) * 100) + '%',
                top: ((chartHover.cy != null ? chartHover.cy : chart.padT) / chart.H * 100) + '%',
              }"
            >
              <div class="tt-date">{{ fmtDay(chartHover.data.date) }}</div>
              <div class="tt-row">
                <span class="muted">Балл</span>
                <b>{{ chartHover.data.avg_score ?? '—' }}</b>
                <span
                  v-if="chartHover.data.delta != null && chartHover.data.delta !== 0"
                  :class="['delta-chip', deltaClass(chartHover.data.delta)]"
                >{{ fmtDelta(chartHover.data.delta) }}</span>
              </div>
              <div class="tt-row"><span class="muted">Звонков</span><b>{{ chartHover.data.calls }}</b></div>
              <div class="tt-row"><span class="muted">Анализов</span><b>{{ chartHover.data.analyzed }}</b></div>
              <div class="tt-row"><span class="muted">Длит.</span><b>{{ fmtDuration(chartHover.data.total_duration) }}</b></div>
            </div>
          </div>

          <div class="legend">
            <span class="lg-item"><span class="lg-dot line"></span> Средний балл</span>
            <span class="lg-item"><span class="lg-dot bar"></span> Звонков в день</span>
          </div>
        </div>

      </div>

      <div class="section">
        <h2 class="section-title">Анализы за период ({{ detail.analyses.length }})</h2>

        <div v-if="!detail.analyses.length" class="empty card small">
          За выбранный период анализов не было.
        </div>

        <div v-else class="list card">
          <div
            v-for="item in detail.analyses"
            :key="item.id"
            class="row-item"
            @click="router.push(`/t/${item.id}`)"
          >
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
                <span>{{ fmtDate(item.bitrix_call_date || item.created_at) }}</span>
                <span v-if="item.bitrix_direction" class="meta-chip">{{ item.bitrix_direction }}</span>
                <span v-if="item.analysis?.sentiment" class="badge" :class="item.analysis.sentiment">
                  {{ item.analysis.sentiment }}
                </span>
                <span class="badge" :class="item.status">{{ statusLabel(item.status) }}</span>
              </div>
            </div>

            <button class="ghost" @click.stop="router.push(`/t/${item.id}`)">Открыть</button>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.head { display: flex; align-items: center; margin-bottom: 16px; }
.back { padding: 8px 14px; font-size: 13px; }

.loading { display: flex; align-items: center; gap: 10px; color: var(--text-dim); padding: 30px 0; }

.profile {
  display: flex;
  align-items: center;
  gap: 18px;
  padding: 20px 24px;
  margin-bottom: 20px;
}
.avatar-lg {
  width: 64px; height: 64px;
  border-radius: 50%;
  background: var(--brand-grad);
  color: #fff;
  display: grid; place-items: center;
  font-weight: 800; font-size: 22px;
  flex-shrink: 0;
  box-shadow: 0 8px 22px -10px rgba(3, 129, 254, 0.45);
}
.profile-info { flex: 1; min-width: 0; }
.profile-name { font-size: 22px; font-weight: 800; margin: 0; letter-spacing: -0.02em; }
.profile-meta { font-size: 13px; color: var(--text-muted); margin-top: 4px; display: flex; gap: 8px; flex-wrap: wrap; }
.profile-score {
  min-width: 96px; padding: 14px 16px;
  border-radius: 16px;
  display: grid; place-items: center;
  font-weight: 800; font-size: 28px;
  letter-spacing: -0.02em;
}
.profile-score .score-cap {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  margin-top: 2px;
  opacity: 0.7;
}
.profile-score.good { background: var(--success-soft); color: var(--success); }
.profile-score.ok { background: var(--brand-soft); color: var(--brand); }
.profile-score.warn { background: var(--warn-soft); color: var(--warn); }
.profile-score.bad { background: var(--danger-soft); color: var(--danger); }
.profile-score.empty { background: var(--surface-3); color: var(--text-muted); font-size: 22px; }

.stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14px;
  margin-bottom: 22px;
}
.stat { padding: 18px 20px; }
.stat-label { font-size: 12px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.08em; }
.stat-value {
  font-size: 24px;
  font-weight: 800;
  letter-spacing: -0.02em;
  margin-top: 4px;
  background: var(--brand-grad);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}

.section { margin-bottom: 22px; }
.section-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; gap: 12px; flex-wrap: wrap; }
.section-title { font-size: 17px; font-weight: 700; margin: 0; letter-spacing: -0.01em; }

.day-switch { display: flex; gap: 6px; }
.day-btn {
  padding: 6px 12px;
  background: var(--surface);
  border: 1px solid var(--border);
  color: var(--text-dim);
  font-size: 12px;
  font-weight: 600;
  border-radius: 999px;
  box-shadow: none;
  cursor: pointer;
}
.day-btn:hover { background: var(--surface-2); color: var(--text); }
.day-btn.active {
  background: var(--brand-grad);
  color: #fff;
  border-color: transparent;
}

.empty.small { padding: 24px; text-align: center; color: var(--text-muted); font-size: 14px; }

.chart-wrap { padding: 20px 22px; }

.trend-row {
  display: flex;
  align-items: stretch;
  gap: 24px;
  flex-wrap: wrap;
  margin-bottom: 14px;
}
.trend-main { flex: 1; min-width: 220px; }
.trend-cap {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--text-muted);
}
.trend-val {
  font-size: 36px;
  font-weight: 800;
  letter-spacing: -0.02em;
  margin-top: 4px;
  display: flex;
  align-items: center;
  gap: 6px;
}
.trend-val.up { color: var(--success); }
.trend-val.down { color: var(--danger); }
.trend-val.flat { color: var(--text-muted); }
.trend-val .arr { font-size: 28px; line-height: 1; }
.trend-unit { font-size: 14px; color: var(--text-muted); font-weight: 600; }
.trend-sub { font-size: 12px; color: var(--text-muted); margin-top: 4px; }

.trend-side { display: flex; gap: 24px; align-items: center; }
.trend-cell { min-width: 110px; }
.cell-cap {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--text-muted);
}
.cell-val { font-size: 22px; font-weight: 800; margin-top: 2px; letter-spacing: -0.02em; }
.cell-val.good { color: var(--success); }
.cell-val.bad { color: var(--danger); }
.cell-day { font-size: 11px; color: var(--text-muted); font-weight: 600; margin-left: 4px; letter-spacing: 0; text-transform: none; }

.chart-host { position: relative; width: 100%; }
.chart-svg { width: 100%; height: 260px; display: block; overflow: visible; }
.chart-svg .grid line { stroke: var(--border); stroke-width: 1; stroke-dasharray: 3 4; }
.chart-svg .grid-label {
  font-size: 10px;
  fill: var(--text-muted);
  font-weight: 600;
  transition: fill .2s ease;
}
.chart-svg .grid-label.active { fill: var(--brand); font-weight: 800; }
.chart-svg .bars rect { transition: opacity .2s ease; }
.chart-svg .area { transition: opacity .25s ease; }
.chart-svg .line {
  fill: none;
  stroke: url(#lineGrad);
  stroke-width: 2.75;
  stroke-linecap: round;
  stroke-linejoin: round;
  animation: line-draw 1s ease-out both;
}
@keyframes line-draw {
  from { stroke-dasharray: 0 2000; }
  to { stroke-dasharray: 2000 0; }
}
.chart-svg .hover-guide {
  stroke: #0381fe;
  stroke-width: 1.2;
  stroke-dasharray: 2 4;
  opacity: .55;
  pointer-events: none;
}
.chart-svg .dot {
  fill: #fff;
  stroke: #0381fe;
  stroke-width: 2.5;
  transition: r .18s cubic-bezier(.4, 1.4, .6, 1), stroke-width .18s ease;
}
.chart-svg .dot-halo {
  fill: #0381fe;
  opacity: 0;
  transition: r .25s cubic-bezier(.4, 1.4, .6, 1), opacity .2s ease;
}
.chart-svg .dot-halo.active { opacity: .18; }
.chart-svg .delta-lbl {
  font-size: 10px;
  font-weight: 700;
  paint-order: stroke;
  stroke: var(--surface);
  stroke-width: 3px;
  stroke-linejoin: round;
}
.chart-svg .delta-lbl.up { fill: var(--success); }
.chart-svg .delta-lbl.down { fill: var(--danger); }
.chart-svg .hit-areas rect { cursor: pointer; }

.tooltip {
  position: absolute;
  transform: translate(-50%, calc(-100% - 14px));
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 10px 12px;
  box-shadow: var(--shadow-lg);
  font-size: 12px;
  white-space: nowrap;
  pointer-events: none;
  z-index: 5;
  min-width: 160px;
  transition: left .22s cubic-bezier(.4, 0, .2, 1), top .22s cubic-bezier(.4, 0, .2, 1);
  animation: tt-pop .18s ease;
}
@keyframes tt-pop {
  from { opacity: 0; transform: translate(-50%, calc(-100% - 4px)); }
  to   { opacity: 1; transform: translate(-50%, calc(-100% - 14px)); }
}
.tt-date { font-weight: 700; margin-bottom: 6px; text-transform: capitalize; }
.tt-row { display: flex; align-items: center; gap: 6px; margin-top: 2px; }
.tt-row .muted { color: var(--text-muted); flex: 1; }
.tt-row b { font-weight: 700; }

.delta-chip {
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 999px;
  font-weight: 700;
}
.delta-chip.up { background: var(--success-soft); color: var(--success); }
.delta-chip.down { background: var(--danger-soft); color: var(--danger); }
.delta-chip.flat { background: var(--surface-3); color: var(--text-muted); }

.legend {
  display: flex; gap: 16px;
  margin-top: 10px;
  font-size: 12px;
  color: var(--text-muted);
  font-weight: 600;
}
.lg-item { display: inline-flex; align-items: center; gap: 6px; }
.lg-dot { width: 12px; height: 4px; border-radius: 2px; }
.lg-dot.line { background: #0381fe; }
.lg-dot.bar { background: rgba(3, 129, 254, 0.35); }

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
.row-title { font-weight: 600; font-size: 15px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.row-summary { font-size: 13px; color: var(--text-dim); margin-top: 3px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.row-meta { display: flex; gap: 8px; align-items: center; margin-top: 6px; flex-wrap: wrap; font-size: 12px; color: var(--text-muted); }
.meta-chip {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 999px;
  background: var(--brand-soft);
  color: var(--brand);
  font-weight: 600;
}
.row-item button { padding: 7px 12px; font-size: 12px; flex-shrink: 0; }

@media (max-width: 800px) {
  .stats { grid-template-columns: repeat(2, 1fr); }
  .row-item button { display: none; }
  .profile { flex-wrap: wrap; }
  .trend-side { gap: 12px; }
  .chart-svg { height: 220px; }
}
</style>
