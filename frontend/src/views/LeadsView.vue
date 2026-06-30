<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../api'
import {
  Search, ClipboardList, RefreshCw, RotateCcw, Sparkles, Check,
  ChevronLeft, ChevronRight,
} from 'lucide-vue-next'

const router = useRouter()
const route = useRoute()

const PAGE_SIZE = 20

const statuses = ref([])
const sources = ref([])
const items = ref([])
const total = ref(0)
const loading = ref(true)
const loadingStatuses = ref(true)
const error = ref('')

// Источник правды по фильтрам — URL. Изменение полей формы записывает их в query,
// загрузка читает их обратно. Так при возврате с детальной страницы состояние сохраняется.
const filters = ref({
  status_id: '',
  source_id: '',
  search: '',
  date_from: '',
  date_to: '',
  page: 1,
})

// Локальный буфер поиска — чтобы можно было нажать «Применить», а не дёргать API на каждой букве.
const searchDraft = ref('')

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / PAGE_SIZE)))

const activeFiltersCount = computed(() => {
  let n = 0
  if (filters.value.status_id) n++
  if (filters.value.source_id) n++
  if (filters.value.search) n++
  if (filters.value.date_from) n++
  if (filters.value.date_to) n++
  return n
})

function readFromQuery() {
  const q = route.query
  filters.value = {
    status_id: typeof q.status_id === 'string' ? q.status_id : '',
    source_id: typeof q.source_id === 'string' ? q.source_id : '',
    search: typeof q.search === 'string' ? q.search : '',
    date_from: typeof q.date_from === 'string' ? q.date_from : '',
    date_to: typeof q.date_to === 'string' ? q.date_to : '',
    page: Math.max(1, parseInt(q.page, 10) || 1),
  }
  searchDraft.value = filters.value.search
}

function writeToQuery(patch = {}) {
  const next = { ...filters.value, ...patch }
  filters.value = next
  const query = {}
  for (const [k, v] of Object.entries(next)) {
    if (v === '' || v == null || (k === 'page' && v === 1)) continue
    query[k] = String(v)
  }
  router.replace({ path: '/leads', query })
}

async function loadStatuses() {
  loadingStatuses.value = true
  try {
    const [s1, s2] = await Promise.all([
      api.get('/bitrix/leads/statuses'),
      api.get('/bitrix/leads/sources'),
    ])
    statuses.value = s1.data
    sources.value = s2.data
  } catch (e) {
    // тихо
  } finally {
    loadingStatuses.value = false
  }
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const params = { page: filters.value.page, page_size: PAGE_SIZE }
    if (filters.value.status_id) params.status_id = filters.value.status_id
    if (filters.value.source_id) params.source_id = filters.value.source_id
    if (filters.value.search) params.search = filters.value.search
    if (filters.value.date_from) params.date_from = filters.value.date_from
    if (filters.value.date_to) params.date_to = filters.value.date_to
    const { data } = await api.get('/bitrix/leads', { params })
    items.value = data.items
    total.value = data.total
  } catch (e) {
    error.value = e.response?.data?.detail || 'Не удалось загрузить лиды'
    items.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

function selectStatus(id) {
  writeToQuery({ status_id: id, page: 1 })
}

function selectSource(id) {
  writeToQuery({ source_id: id, page: 1 })
}

function applySearch() {
  writeToQuery({ search: searchDraft.value.trim(), page: 1 })
}

function applyDateFrom(v) {
  writeToQuery({ date_from: v, page: 1 })
}

function applyDateTo(v) {
  writeToQuery({ date_to: v, page: 1 })
}

function resetFilters() {
  searchDraft.value = ''
  writeToQuery({
    status_id: '', source_id: '', search: '', date_from: '', date_to: '', page: 1,
  })
}

function setDatePreset(preset) {
  const today = new Date()
  const fmt = (d) => {
    const off = d.getTimezoneOffset()
    return new Date(d.getTime() - off * 60_000).toISOString().slice(0, 10)
  }
  if (preset === 'today') {
    writeToQuery({ date_from: fmt(today), date_to: fmt(today), page: 1 })
  } else if (preset === '7d') {
    const s = new Date(today); s.setDate(today.getDate() - 6)
    writeToQuery({ date_from: fmt(s), date_to: fmt(today), page: 1 })
  } else if (preset === '30d') {
    const s = new Date(today); s.setDate(today.getDate() - 29)
    writeToQuery({ date_from: fmt(s), date_to: fmt(today), page: 1 })
  } else if (preset === 'month') {
    const s = new Date(today.getFullYear(), today.getMonth(), 1)
    writeToQuery({ date_from: fmt(s), date_to: fmt(today), page: 1 })
  }
}

function changePage(delta) {
  const next = filters.value.page + delta
  if (next < 1 || next > totalPages.value) return
  writeToQuery({ page: next })
}

function fullName(l) {
  return [l.last_name, l.name, l.second_name].filter(Boolean).join(' ').trim()
}

function fmtMoney(amount, currency) {
  if (!amount) return ''
  const v = new Intl.NumberFormat('ru-RU').format(Math.round(amount))
  return currency ? `${v} ${currency}` : v
}

function fmtDate(s) {
  if (!s) return '—'
  return new Date(s).toLocaleString('ru-RU', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

function daysAgo(s) {
  if (!s) return null
  const diff = Math.floor((Date.now() - new Date(s).getTime()) / (1000 * 60 * 60 * 24))
  return diff
}

function fmtAgo(s) {
  const d = daysAgo(s)
  if (d == null) return ''
  if (d === 0) return 'сегодня'
  if (d === 1) return 'вчера'
  if (d < 7) return `${d} д. назад`
  if (d < 30) return `${Math.floor(d / 7)} нед. назад`
  if (d < 365) return `${Math.floor(d / 30)} мес. назад`
  return `${Math.floor(d / 365)} г. назад`
}

function statusColor(s) {
  if (!s?.color) return null
  return s.color.startsWith('#') ? s.color : `#${s.color}`
}

const analyzingLeads = ref(new Set())

async function startAnalysis(lead, event) {
  event?.stopPropagation()
  if (analyzingLeads.value.has(lead.id)) return
  analyzingLeads.value.add(lead.id)
  // Локально отмечаем как processing, чтобы строка обновилась мгновенно
  lead.analysis_status = 'processing'
  try {
    await api.post(`/bitrix/leads/${lead.id}/analyze`)
  } catch (e) {
    lead.analysis_status = 'failed'
    // Не пугаем пользователя ошибкой здесь — если кликнут в детали лида, увидит причину
  } finally {
    analyzingLeads.value.delete(lead.id)
  }
}

function gradeFromScore(score) {
  if (score >= 90) return 'reference'
  if (score >= 75) return 'good'
  if (score >= 60) return 'ok'
  return 'bad'
}

// Перезагружаем при изменении query (включая возврат назад из детальной)
watch(() => route.query, () => {
  readFromQuery()
  load()
}, { deep: true })

onMounted(() => {
  readFromQuery()
  loadStatuses()
  load()
})
</script>

<template>
  <div class="container">
    <div class="head">
      <div>
        <h1 class="page-title">Лиды</h1>
        <p class="page-subtitle">Сделки на стадии воронки. По 20 на страницу.</p>
      </div>
      <div class="spacer"></div>
      <button class="ghost refresh-btn" @click="load" :disabled="loading">
        <span v-if="loading" class="spinner"></span>
        <template v-else><RefreshCw :size="14" /> Обновить</template>
      </button>
    </div>

    <div class="filters card">
      <div class="filter-grid">
        <div class="filter-cell search-cell">
          <label class="label">Поиск</label>
          <form @submit.prevent="applySearch" class="search-form">
            <input
              v-model="searchDraft"
              type="search"
              class="search"
              placeholder="По названию лида…"
              @keyup.enter="applySearch"
            />
            <button class="ghost" type="submit">Найти</button>
          </form>
        </div>
        <div class="filter-cell">
          <label class="label">Создан с</label>
          <input
            type="date"
            :value="filters.date_from"
            @change="e => applyDateFrom(e.target.value)"
            class="date-input"
          />
        </div>
        <div class="filter-cell">
          <label class="label">по</label>
          <input
            type="date"
            :value="filters.date_to"
            @change="e => applyDateTo(e.target.value)"
            class="date-input"
          />
        </div>
        <div class="filter-cell filter-actions">
          <button class="ghost" @click="resetFilters" :disabled="!activeFiltersCount">
            Сбросить{{ activeFiltersCount ? ` (${activeFiltersCount})` : '' }}
          </button>
        </div>
      </div>

      <div class="presets">
        <button class="chip-sm" @click="setDatePreset('today')">Сегодня</button>
        <button class="chip-sm" @click="setDatePreset('7d')">7 дней</button>
        <button class="chip-sm" @click="setDatePreset('30d')">30 дней</button>
        <button class="chip-sm" @click="setDatePreset('month')">Этот месяц</button>
      </div>
    </div>

    <div class="status-row card">
      <div class="status-row-title">Статусы</div>
      <div class="status-chips">
        <button
          class="chip"
          :class="{ active: !filters.status_id }"
          @click="selectStatus('')"
        >Все</button>
        <button
          v-for="s in statuses"
          :key="s.status_id"
          class="chip"
          :class="{ active: filters.status_id === s.status_id }"
          :style="filters.status_id === s.status_id && statusColor(s)
            ? { background: statusColor(s), borderColor: 'transparent', color: '#fff' }
            : statusColor(s) ? { boxShadow: `inset 3px 0 0 ${statusColor(s)}` } : null"
          @click="selectStatus(s.status_id)"
        >{{ s.name }}</button>
        <span v-if="loadingStatuses && !statuses.length" class="muted">Загрузка статусов…</span>
      </div>
    </div>

    <div v-if="sources.length" class="status-row card">
      <div class="status-row-title">Источники</div>
      <div class="status-chips">
        <button
          class="chip"
          :class="{ active: !filters.source_id }"
          @click="selectSource('')"
        >Все</button>
        <button
          v-for="s in sources"
          :key="s.status_id"
          class="chip"
          :class="{ active: filters.source_id === s.status_id }"
          @click="selectSource(s.status_id)"
        >{{ s.name }}</button>
      </div>
    </div>

    <div v-if="error" class="error-msg" style="margin-bottom:16px;">{{ error }}</div>

    <div v-if="loading" class="loading"><span class="spinner"></span> Загрузка лидов…</div>

    <div v-else-if="!items.length" class="empty card">
      <div class="empty-icon"><ClipboardList :size="28" /></div>
      <h3>Лидов нет</h3>
      <p>Для выбранного статуса ничего не найдено.</p>
    </div>

    <div v-else class="table card">
      <div class="thead">
        <div class="col-id">ID</div>
        <div class="col-title">Лид</div>
        <div class="col-status">Статус</div>
        <div class="col-source">Источник</div>
        <div class="col-amount">Сумма</div>
        <div class="col-contact">Контакт</div>
        <div class="col-mgr">Менеджер</div>
        <div class="col-date">Создан</div>
        <div class="col-analysis">Анализ</div>
      </div>

      <div
        v-for="l in items"
        :key="l.id"
        class="trow clickable"
        @click="router.push(`/leads/${l.id}`)"
      >
        <div class="col-id mono">#{{ l.id }}</div>

        <div class="col-title">
          <div class="lead-title">{{ l.title || fullName(l) || `Лид #${l.id}` }}</div>
          <div v-if="l.title && fullName(l)" class="lead-sub">{{ fullName(l) }}</div>
        </div>

        <div class="col-status">
          <span class="status-pill">{{ l.status_name || l.status_id || '—' }}</span>
        </div>

        <div class="col-source small">
          <span v-if="l.source_name || l.source_id">{{ l.source_name || l.source_id }}</span>
          <span v-else class="muted">—</span>
        </div>

        <div class="col-amount mono">
          <template v-if="l.opportunity">{{ fmtMoney(l.opportunity, l.currency_id) }}</template>
          <span v-else class="muted">—</span>
        </div>

        <div class="col-contact">
          <div v-if="l.phone" class="mono small">{{ l.phone }}</div>
          <div v-if="l.email" class="muted small">{{ l.email }}</div>
          <span v-if="!l.phone && !l.email" class="muted">—</span>
        </div>

        <div class="col-mgr">
          <div class="mgr" v-if="l.assigned_by">
            <div class="mgr-avatar">{{ l.assigned_by[0]?.toUpperCase() }}</div>
            <div class="mgr-name">{{ l.assigned_by }}</div>
          </div>
          <span v-else class="muted">—</span>
        </div>

        <div class="col-date small">
          <div>{{ fmtDate(l.created_at) }}</div>
          <div class="muted">{{ fmtAgo(l.created_at) }}</div>
        </div>

        <div class="col-analysis">
          <span v-if="l.analysis_status === 'processing'" class="ana-chip processing">
            <span class="spinner-mini"></span> Анализирую…
          </span>
          <span
            v-else-if="l.analysis_status === 'done'"
            :class="['ana-chip', 'done', `g-${gradeFromScore(l.analysis_score)}`]"
            :title="`Балл ${l.analysis_score} / 100${l.analysis_risk ? ' · риск: ' + l.analysis_risk : ''}`"
          >
            <Check :size="12" /> {{ l.analysis_score }}
          </span>
          <button
            v-else-if="l.analysis_status === 'failed'"
            class="ana-chip failed"
            @click="startAnalysis(l, $event)"
            title="Анализ упал — повторить"
          ><RotateCcw :size="12" /> Повторить</button>
          <button
            v-else
            class="ana-chip cta"
            @click="startAnalysis(l, $event)"
            title="Запустить AI-анализ лида в фоне"
          ><Sparkles :size="12" /> Анализ</button>
        </div>
      </div>
    </div>

    <div v-if="items.length" class="pager">
      <button class="ghost pager-btn" @click="changePage(-1)" :disabled="filters.page === 1 || loading">
        <ChevronLeft :size="14" /> Назад
      </button>
      <span class="pager-info">
        Стр. {{ filters.page }} из {{ totalPages }} · всего {{ total }}
      </span>
      <button class="ghost pager-btn" @click="changePage(1)" :disabled="filters.page >= totalPages || loading">
        Вперёд <ChevronRight :size="14" />
      </button>
    </div>
  </div>
</template>

<style scoped>
.head { display: flex; align-items: center; gap: 16px; margin-bottom: 22px; }

.status-row { padding: 16px 22px; margin-bottom: 18px; }
.status-row-title {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-muted);
  margin-bottom: 10px;
}
.status-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
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
.chip.active:hover { background: var(--brand-soft); }
.muted { color: var(--text-muted); font-size: 13px; }

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
.thead, .trow {
  display: grid;
  grid-template-columns:
    72px                /* ID */
    minmax(0, 2.4fr)    /* Лид */
    120px               /* Статус */
    minmax(0, 1fr)      /* Источник */
    140px               /* Сумма */
    minmax(0, 200px)    /* Контакт */
    minmax(0, 1.6fr)    /* Менеджер */
    140px               /* Дата */
    130px;              /* Анализ */
  gap: 14px;
  padding: 14px 22px;
  align-items: center;
}
.thead {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-muted);
  background: var(--surface-2);
  border-bottom: 1px solid var(--border);
}
.trow { border-bottom: 1px solid var(--border); transition: background .15s; }
.trow:last-child { border-bottom: none; }
.trow:hover { background: var(--surface-2); }
.trow.clickable { cursor: pointer; }

/* Все ячейки могут ужиматься и обрезать длинный текст */
.thead > *, .trow > * { min-width: 0; }
.col-amount, .col-date { justify-self: end; text-align: right; }
.thead .col-amount, .thead .col-date { text-align: right; }

.lead-title {
  font-weight: 600; font-size: 14px;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.lead-sub {
  font-size: 12px; color: var(--text-muted); margin-top: 2px;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}

.status-pill {
  display: inline-block;
  max-width: 100%;
  padding: 4px 10px;
  border-radius: 999px;
  background: var(--brand-soft);
  color: var(--brand-hover);
  font-size: 12px;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  vertical-align: middle;
}

.mono { font-family: 'SF Mono', Menlo, monospace; font-size: 13px; }
.small {
  font-size: 12.5px;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}

.col-contact { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.col-id, .col-amount { white-space: nowrap; }
.col-date { white-space: nowrap; color: var(--text-dim); }

.mgr { display: flex; align-items: center; gap: 8px; min-width: 0; }
.mgr-avatar {
  width: 26px; height: 26px;
  border-radius: 50%;
  background: var(--brand-grad);
  color: #fff;
  display: grid; place-items: center;
  font-weight: 700; font-size: 11px;
  flex-shrink: 0;
}
.mgr-name {
  font-size: 13px; font-weight: 500;
  overflow: hidden; white-space: nowrap; text-overflow: ellipsis;
  min-width: 0;
}

.pager {
  display: flex; align-items: center; justify-content: center;
  gap: 16px;
  margin-top: 22px;
}
.pager-info { font-size: 13px; color: var(--text-dim); font-weight: 500; }

.col-source { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.col-analysis { display: flex; justify-content: flex-start; align-items: center; }

.ana-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 5px 11px;
  border-radius: 999px;
  font-size: 11.5px;
  font-weight: 700;
  letter-spacing: 0.02em;
  white-space: nowrap;
  border: 1px solid transparent;
  cursor: default;
  background: var(--surface-2);
  color: var(--text-dim);
}
button.ana-chip { cursor: pointer; box-shadow: none; transition: background .15s, color .15s, border-color .15s; }
button.ana-chip.cta { background: var(--brand-soft); color: var(--brand-hover); border-color: transparent; }
button.ana-chip.cta:hover { background: var(--brand); color: #fff; }
button.ana-chip.failed { background: var(--danger-soft); color: var(--danger); }
button.ana-chip.failed:hover { background: var(--danger); color: #fff; }
.ana-chip.processing { background: var(--warn-soft); color: var(--warn); }
.ana-chip.done.g-reference { background: var(--info-soft); color: var(--info); }
.ana-chip.done.g-good { background: var(--success-soft); color: var(--success); }
.ana-chip.done.g-ok { background: var(--warn-soft); color: var(--warn); }
.ana-chip.done.g-bad { background: var(--danger-soft); color: var(--danger); }

.spinner-mini {
  width: 10px; height: 10px;
  border: 2px solid currentColor;
  border-top-color: transparent;
  border-radius: 50%;
  display: inline-block;
  animation: spin .8s linear infinite;
  opacity: .7;
}
@keyframes spin { to { transform: rotate(360deg); } }

.filters { padding: 18px 22px; margin-bottom: 18px; }
.filter-grid {
  display: grid;
  grid-template-columns: minmax(0, 2fr) 160px 160px auto;
  gap: 14px;
  align-items: end;
}
.filter-cell { display: flex; flex-direction: column; gap: 4px; min-width: 0; }
.label {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-muted);
}
.search-form { display: flex; gap: 8px; }
.search-form .search { flex: 1; padding: 10px 14px; font-size: 13px; }
.search-form .ghost { padding: 10px 16px; font-size: 13px; }
.date-input {
  padding: 10px 14px;
  font-size: 13px;
  font-family: inherit;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: var(--surface);
  color: var(--text);
}
.filter-actions { align-items: flex-start; }
.filter-actions .ghost { padding: 10px 16px; font-size: 13px; }

.presets {
  display: flex;
  gap: 8px;
  margin-top: 12px;
  flex-wrap: wrap;
}
.chip-sm {
  padding: 5px 12px;
  font-size: 12px;
  font-weight: 600;
  border-radius: 999px;
  background: var(--surface-2);
  border: 1px solid var(--border);
  color: var(--text-dim);
  box-shadow: none;
  cursor: pointer;
}
.chip-sm:hover { background: var(--surface-3); color: var(--text); }

@media (max-width: 900px) {
  .filter-grid { grid-template-columns: 1fr 1fr; }
  .filter-cell.search-cell { grid-column: 1 / -1; }
  .filter-actions { grid-column: 1 / -1; }
}

@media (max-width: 1100px) {
  .thead { display: none; }
  .trow {
    grid-template-columns: 1fr 1fr;
    gap: 8px;
    padding: 16px;
  }
  .col-title, .col-status, .col-amount, .col-contact, .col-mgr, .col-date, .col-id, .col-source {
    display: flex; flex-direction: column; gap: 4px;
  }
}
</style>
