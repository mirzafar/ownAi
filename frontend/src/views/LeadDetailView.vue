<script setup>
import { computed, onMounted, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../api'
import {
  ArrowLeft, ArrowRight, RotateCcw, Sparkles, X, Play, MessageSquare,
} from 'lucide-vue-next'

const route = useRoute()
const router = useRouter()

const lead = ref(null)
const loading = ref(true)
const error = ref('')
const activity = ref({ timeline: [], calls: [] })
const activityLoading = ref(false)
const activityError = ref('')
const playingCall = ref(null)

const analysis = ref(null)
const analysisLoading = ref(false)   // загрузка кэша
const analysisError = ref('')
let pollTimer = null

const analysisRunning = computed(() => analysis.value?.status === 'processing')

function startPolling() {
  if (pollTimer) return
  pollTimer = setInterval(() => {
    if (analysis.value?.status !== 'processing') {
      stopPolling()
      return
    }
    loadAnalysis(true)
  }, 5000)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

async function loadAnalysis(silent = false) {
  if (!silent) analysisLoading.value = true
  analysisError.value = ''
  try {
    const { data } = await api.get(`/bitrix/leads/${route.params.id}/analysis`)
    analysis.value = data
    if (data.status === 'processing') startPolling()
    else stopPolling()
  } catch (e) {
    if (e.response?.status === 404) {
      analysis.value = null
      stopPolling()
    } else if (!silent) {
      analysisError.value = e.response?.data?.detail || 'Не удалось получить анализ'
    }
  } finally {
    if (!silent) analysisLoading.value = false
  }
}

async function runAnalysis(force = false) {
  analysisError.value = ''
  try {
    const { data } = await api.post(
      `/bitrix/leads/${route.params.id}/analyze`,
      null,
      { params: force ? { force: true } : {} },
    )
    analysis.value = data
    if (data.status === 'processing') startPolling()
  } catch (e) {
    analysisError.value = e.response?.data?.detail || 'Не удалось запустить анализ'
  }
}

async function loadActivity() {
  activityLoading.value = true
  activityError.value = ''
  try {
    const { data } = await api.get(`/bitrix/leads/${route.params.id}/activity`)
    activity.value = data
  } catch (e) {
    activityError.value = e.response?.data?.detail || 'Не удалось загрузить активность'
    activity.value = { timeline: [], calls: [] }
  } finally {
    activityLoading.value = false
  }
}

async function load() {
  loading.value = true
  error.value = ''
  analysis.value = null
  try {
    const { data } = await api.get(`/bitrix/leads/${route.params.id}`)
    lead.value = data
    loadActivity()
    loadAnalysis()
  } catch (e) {
    error.value = e.response?.data?.detail || 'Не удалось загрузить лида'
    lead.value = null
  } finally {
    loading.value = false
  }
}

watch(() => route.params.id, () => {
  stopPolling()
  load()
})

onBeforeUnmount(stopPolling)

const fullName = computed(() => {
  if (!lead.value) return ''
  return [lead.value.honorific, lead.value.last_name, lead.value.name, lead.value.second_name]
    .filter(Boolean).join(' ').trim()
})

const displayTitle = computed(() => {
  if (!lead.value) return ''
  return lead.value.title || fullName.value || `Лид #${lead.value.id}`
})

const hasUtm = computed(() => {
  if (!lead.value) return false
  return !!(lead.value.utm_source || lead.value.utm_medium || lead.value.utm_campaign)
})

const hasAnalyzableActivity = computed(() => {
  const calls = activity.value?.calls?.length || 0
  const comments = (activity.value?.timeline || []).filter(e => e.kind === 'comment').length
  return calls > 0 || comments > 0
})

const analyzeDisabledReason = computed(() => {
  if (analysisRunning.value) return ''
  if (activityLoading.value) return 'Загрузка активности…'
  if (!hasAnalyzableActivity.value) return 'По лиду нет звонков и комментариев — нечего анализировать'
  return ''
})

function fmtDate(s) {
  if (!s) return '—'
  return new Date(s).toLocaleString('ru-RU', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

function fmtMoney(amount, currency) {
  if (!amount) return '—'
  const v = new Intl.NumberFormat('ru-RU').format(Math.round(amount))
  return currency ? `${v} ${currency}` : v
}

function fmtDuration(sec) {
  if (!sec) return '—'
  const m = Math.floor(sec / 60)
  const s = sec % 60
  return `${m}:${String(s).padStart(2, '0')}`
}

function activityIcon(type) {
  return ({
    call: '📞',
    email: '✉',
    meeting: '🗓',
    task: '✓',
    activity: '•',
  })[type] || '•'
}

function activityLabel(type) {
  return ({
    call: 'Звонок',
    email: 'Письмо',
    meeting: 'Встреча',
    task: 'Задача',
    activity: 'Действие',
  })[type] || 'Действие'
}

function togglePlay(call) {
  playingCall.value = playingCall.value === call.id ? null : call.id
}

const riskLabel = {
  low: 'Низкий',
  medium: 'Средний',
  high: 'Высокий',
}

const CATEGORY_ORDER = ['opening', 'qualification', 'presentation', 'objections', 'closing']
const CATEGORY_NAME = {
  opening: 'Открытие звонка',
  qualification: 'Квалификация',
  presentation: 'Презентация объекта',
  objections: 'Работа с возражениями',
  closing: 'Закрытие и следующий шаг',
}

const scoring = computed(() => analysis.value?.scoring || null)
const leadData = computed(() => analysis.value?.lead || null)

const groupedCriteria = computed(() => {
  const sa = scoring.value
  if (!sa?.criteria_scores?.length) return []
  const byCat = {}
  for (const c of sa.criteria_scores) {
    const k = c.category_id || 'other'
    if (!byCat[k]) byCat[k] = { id: k, name: c.category_name || CATEGORY_NAME[k] || k, items: [], earned: 0, max: 0 }
    byCat[k].items.push(c)
    byCat[k].earned += Number(c.score) || 0
    byCat[k].max += Number(c.max_score) || 0
  }
  return CATEGORY_ORDER.map(k => byCat[k]).filter(Boolean)
})

const triggeredStops = computed(() => {
  const list = scoring.value?.stop_factors || []
  return list.filter(s => s.triggered)
})

function gradeKey(grade) {
  const g = (grade || '').toLowerCase()
  if (g.includes('эталон')) return 'reference'
  if (g.includes('хорош')) return 'good'
  if (g.includes('удовл')) return 'ok'
  return 'bad'
}

function critClass(c) {
  const max = Number(c.max_score) || 0
  const score = Number(c.score) || 0
  if (!max) return 'crit-zero'
  const r = score / max
  if (r >= 0.8) return 'crit-good'
  if (r >= 0.6) return 'crit-ok'
  if (r >= 0.4) return 'crit-warn'
  if (r > 0) return 'crit-low'
  return 'crit-zero'
}

function fmtAgo(s) {
  if (!s) return ''
  const diff = Date.now() - new Date(s).getTime()
  const min = Math.floor(diff / 60_000)
  if (min < 1) return 'только что'
  if (min < 60) return `${min} мин назад`
  const h = Math.floor(min / 60)
  if (h < 24) return `${h} ч назад`
  return `${Math.floor(h / 24)} дн назад`
}

function goBack() {
  // Если в истории есть предыдущая страница в этой же вкладке — возвращаемся
  // туда (тогда URL с фильтрами лидов восстановится). Иначе — fallback на /leads
  // (читалка LeadsView поднимет фильтры из sessionStorage).
  if (window.history.length > 1) router.back()
  else router.push('/leads')
}

onMounted(load)
</script>

<template>
  <div class="container">
    <button class="ghost back" @click="goBack"><ArrowLeft :size="14" /> К лидам</button>

    <div v-if="error" class="error-msg" style="margin-bottom:16px;">{{ error }}</div>

    <div v-if="loading" class="loading"><span class="spinner"></span> Загрузка…</div>

    <template v-else-if="lead">
      <div class="hero card">
        <div class="hero-main">
          <div class="hero-tag">Лид #{{ lead.id }}</div>
          <h1 class="hero-title">{{ displayTitle }}</h1>
          <div v-if="lead.title && fullName" class="hero-sub">{{ fullName }}</div>
          <div class="hero-meta">
            <span class="status-pill">{{ lead.status_name || lead.status_id || '—' }}</span>
            <span v-if="lead.source_id" class="meta-chip">Источник: {{ lead.source_id }}</span>
          </div>
        </div>
        <div class="hero-side">
          <div class="hero-actions">
            <button
              class="analyze-btn"
              :disabled="analysisRunning || !!analyzeDisabledReason"
              @click="runAnalysis(analysis?.status === 'done')"
              :title="analyzeDisabledReason || (analysis?.status === 'done' ? 'Пересчитать с учётом новых данных' : 'Сводный анализ по всем звонкам и комментариям')"
            >
              <span v-if="analysisRunning" class="spinner-sm"></span>
              <span v-if="analysisRunning">Анализирую…</span>
              <span v-else-if="analysis?.status === 'done'" class="btn-inline"><RotateCcw :size="14" /> Пересчитать анализ</span>
              <span v-else class="btn-inline"><Sparkles :size="14" /> Проанализировать лид</span>
            </button>
            <a
              v-if="lead.bitrix_url"
              :href="lead.bitrix_url"
              target="_blank"
              rel="noopener"
              class="bitrix-btn"
              title="Открыть карточку лида в Bitrix24"
            >
              <span>Открыть в Bitrix</span>
              <span class="bitrix-arrow">↗</span>
            </a>
          </div>
          <div class="hero-money">
            <div class="money-cap">Сумма</div>
            <div class="money-val">{{ fmtMoney(lead.opportunity, lead.currency_id) }}</div>
          </div>
        </div>
      </div>

      <div class="grid">
        <div class="card section">
          <h2 class="sec-title">Контакты</h2>

          <div v-if="lead.phones.length" class="contact-block">
            <div class="contact-cap">Телефоны</div>
            <div v-for="(p, i) in lead.phones" :key="'p' + i" class="contact-row">
              <a :href="`tel:${p.value}`" class="contact-val mono">{{ p.value }}</a>
              <span v-if="p.kind" class="contact-kind">{{ p.kind }}</span>
            </div>
          </div>

          <div v-if="lead.emails.length" class="contact-block">
            <div class="contact-cap">Email</div>
            <div v-for="(e, i) in lead.emails" :key="'e' + i" class="contact-row">
              <a :href="`mailto:${e.value}`" class="contact-val">{{ e.value }}</a>
              <span v-if="e.kind" class="contact-kind">{{ e.kind }}</span>
            </div>
          </div>

          <div v-if="lead.webs.length" class="contact-block">
            <div class="contact-cap">Сайт</div>
            <div v-for="(w, i) in lead.webs" :key="'w' + i" class="contact-row">
              <a :href="w.value" target="_blank" rel="noopener" class="contact-val">{{ w.value }}</a>
              <span v-if="w.kind" class="contact-kind">{{ w.kind }}</span>
            </div>
          </div>

          <div v-if="lead.ims.length" class="contact-block">
            <div class="contact-cap">Мессенджеры</div>
            <div v-for="(m, i) in lead.ims" :key="'i' + i" class="contact-row">
              <span class="contact-val">{{ m.value }}</span>
              <span v-if="m.kind" class="contact-kind">{{ m.kind }}</span>
            </div>
          </div>

          <div v-if="!lead.phones.length && !lead.emails.length && !lead.webs.length && !lead.ims.length" class="empty-inline">
            Контактных данных нет.
          </div>
        </div>

        <div class="card section">
          <h2 class="sec-title">Компания и адрес</h2>
          <div class="kv-row" v-if="lead.company_title">
            <div class="kv-key">Компания</div>
            <div class="kv-val">{{ lead.company_title }}</div>
          </div>
          <div class="kv-row" v-if="lead.post">
            <div class="kv-key">Должность</div>
            <div class="kv-val">{{ lead.post }}</div>
          </div>
          <div class="kv-row" v-if="lead.address">
            <div class="kv-key">Адрес</div>
            <div class="kv-val">{{ lead.address }}</div>
          </div>
          <div v-if="!lead.company_title && !lead.post && !lead.address" class="empty-inline">
            Не заполнено.
          </div>
        </div>

        <div class="card section">
          <h2 class="sec-title">Ответственный</h2>
          <div class="mgr-card" v-if="lead.assigned_by">
            <div class="mgr-avatar-lg">{{ lead.assigned_by[0]?.toUpperCase() }}</div>
            <div>
              <div class="mgr-name-lg">{{ lead.assigned_by }}</div>
              <div class="mgr-id muted">ID: {{ lead.assigned_by_id }}</div>
            </div>
          </div>
          <div v-else class="empty-inline">Не назначен.</div>

          <div class="kv-row" v-if="lead.created_by">
            <div class="kv-key">Создал</div>
            <div class="kv-val">{{ lead.created_by }}</div>
          </div>
        </div>

        <div class="card section">
          <h2 class="sec-title">Даты</h2>
          <div class="kv-row">
            <div class="kv-key">Создан</div>
            <div class="kv-val">{{ fmtDate(lead.created_at) }}</div>
          </div>
          <div class="kv-row">
            <div class="kv-key">Изменён</div>
            <div class="kv-val">{{ fmtDate(lead.modified_at) }}</div>
          </div>
        </div>

        <div v-if="hasUtm" class="card section">
          <h2 class="sec-title">UTM</h2>
          <div class="kv-row" v-if="lead.utm_source">
            <div class="kv-key">Source</div>
            <div class="kv-val mono">{{ lead.utm_source }}</div>
          </div>
          <div class="kv-row" v-if="lead.utm_medium">
            <div class="kv-key">Medium</div>
            <div class="kv-val mono">{{ lead.utm_medium }}</div>
          </div>
          <div class="kv-row" v-if="lead.utm_campaign">
            <div class="kv-key">Campaign</div>
            <div class="kv-val mono">{{ lead.utm_campaign }}</div>
          </div>
        </div>

        <div v-if="lead.source_description" class="card section">
          <h2 class="sec-title">Описание источника</h2>
          <div class="lead-text">{{ lead.source_description }}</div>
        </div>
      </div>

      <div v-if="lead.comments" class="card section comments-card">
        <h2 class="sec-title">Комментарий</h2>
        <div class="lead-text" v-html="lead.comments"></div>
      </div>

      <div v-if="analysisError" class="card section analysis-card error-card">
        <div class="sec-head"><h2 class="sec-title" style="margin:0;">AI-анализ лида</h2></div>
        <div class="error-msg">{{ analysisError }}</div>
        <button class="ghost small-btn" @click="runAnalysis(true)" :disabled="analysisRunning">Повторить</button>
      </div>

      <div v-else-if="analysis?.status === 'failed'" class="card section analysis-card error-card">
        <div class="sec-head"><h2 class="sec-title" style="margin:0;">AI-анализ лида</h2></div>
        <div class="error-msg">{{ analysis.error || 'Анализ не удался' }}</div>
        <button class="ghost small-btn" @click="runAnalysis(true)" :disabled="analysisRunning">Повторить</button>
      </div>

      <div v-else-if="analysisRunning" class="card section analysis-card placeholder-card">
        <div class="sec-head"><h2 class="sec-title" style="margin:0;">AI-анализ лида</h2></div>
        <div class="loading">
          <span class="spinner"></span>
          Анализирую.
        </div>
      </div>

      <div v-else-if="analysis?.status === 'done' && leadData" class="card section analysis-card">
        <div class="sec-head">
          <h2 class="sec-title" style="margin:0;">AI-анализ лида</h2>
          <div class="analysis-meta">
            <span :class="['risk-pill', `risk-${leadData.risk}`]">Риск: {{ riskLabel[leadData.risk] || leadData.risk }}</span>
            <span v-if="analysis.updated_at" class="muted small">обновлён {{ fmtAgo(analysis.updated_at) }}</span>
          </div>
        </div>

        <div v-if="leadData.summary" class="analysis-summary">{{ leadData.summary }}</div>

        <div class="analysis-grid">
          <div v-if="leadData.client_request" class="analysis-block">
            <div class="block-cap">Запрос клиента</div>
            <div class="lead-text">{{ leadData.client_request }}</div>
          </div>

          <div v-if="leadData.next_step" class="analysis-block highlight">
            <div class="block-cap">Следующий шаг</div>
            <div class="lead-text">{{ leadData.next_step }}</div>
          </div>

          <div v-if="leadData.risk_reason" class="analysis-block">
            <div class="block-cap">Почему такой риск</div>
            <div class="lead-text">{{ leadData.risk_reason }}</div>
          </div>

          <div v-if="leadData.objections?.length" class="analysis-block">
            <div class="block-cap">Возражения / блокеры</div>
            <ul class="analysis-list">
              <li v-for="(o, i) in leadData.objections" :key="'o' + i">{{ o }}</li>
            </ul>
          </div>

          <div v-if="scoring?.strengths?.length" class="analysis-block pros">
            <div class="block-cap">Менеджер: плюсы</div>
            <ul class="analysis-list">
              <li v-for="(p, i) in scoring.strengths" :key="'p' + i">{{ p }}</li>
            </ul>
          </div>

          <div v-if="scoring?.weaknesses?.length" class="analysis-block cons">
            <div class="block-cap">Менеджер: минусы</div>
            <ul class="analysis-list">
              <li v-for="(c, i) in scoring.weaknesses" :key="'c' + i">{{ c }}</li>
            </ul>
          </div>
        </div>

        <div class="analysis-foot muted small">
          Учтено: {{ leadData.calls_count }} зв. (проанализировано {{ (leadData.call_refs || []).filter(c => c.analyzed).length }}),
          {{ leadData.comments_count }} комм.
          <span v-if="(leadData.call_refs || []).some(c => !c.analyzed)">
            · пропущено {{ (leadData.call_refs || []).filter(c => !c.analyzed).length }} (без записи или ошибка)
          </span>
        </div>
      </div>

      <div v-if="analysis?.status === 'done' && scoring" class="card section scorecard-card">
        <div class="sec-head scorecard-head">
          <div>
            <h2 class="sec-title" style="margin:0;">Карта оценки работы с лидом</h2>
            <div v-if="scoring.meta.verdict" class="scorecard-verdict">
              {{ scoring.meta.verdict }}
            </div>
          </div>
          <div class="scorecard-meta">
            <div class="score-big">
              <span class="score-num">{{ scoring.meta.normalized_score }}</span>
              <span class="score-den">/ 100</span>
            </div>
            <span :class="['grade-pill', `grade-${gradeKey(scoring.meta.grade)}`]">
              {{ scoring.meta.grade }}
            </span>
          </div>
        </div>

        <div class="criteria-section">
          <div v-for="cat in groupedCriteria" :key="cat.id" class="cat-group">
            <div class="cat-head">
              <span class="cat-name">{{ cat.name }}</span>
              <span class="cat-score">{{ cat.earned }} / {{ cat.max }}</span>
            </div>
            <div v-for="c in cat.items" :key="c.id" class="crit-row">
              <div class="crit-main">
                <div class="crit-name">{{ c.name }}</div>
                <div v-if="c.comment" class="crit-comment">{{ c.comment }}</div>
              </div>
              <div class="crit-score-cell">
                <div class="crit-score">
                  <span :class="['crit-num', critClass(c)]">{{ c.score }}</span><span class="crit-max">/{{ c.max_score }}</span>
                </div>
                <div class="crit-bar">
                  <div
                    :class="['crit-bar-fill', critClass(c)]"
                    :style="{ width: c.max_score ? (c.score / c.max_score * 100) + '%' : '0%' }"
                  ></div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div v-if="triggeredStops.length" class="stops-section">
          <div class="block-cap">Сработавшие стоп-факторы</div>
          <div v-for="sf in triggeredStops" :key="sf.id" class="stop-row">
            <span class="stop-penalty">−{{ sf.penalty }}</span>
            <div class="stop-main">
              <div class="stop-name">{{ sf.name }}</div>
              <div v-if="sf.comment" class="stop-comment">{{ sf.comment }}</div>
            </div>
          </div>
        </div>

        <div v-if="scoring.coaching_tasks?.length" class="coaching-section">
          <div class="block-cap">Задачи на коучинг</div>
          <div
            v-for="(t, i) in scoring.coaching_tasks"
            :key="'t' + i"
            class="coach-row"
          >
            <div class="coach-title">{{ t.title }}</div>
            <div v-if="t.focus_area" class="coach-focus muted small">{{ t.focus_area }}</div>
            <div v-if="t.action_item" class="coach-action"><ArrowRight :size="14" /> {{ t.action_item }}</div>
          </div>
        </div>
      </div>

      <div class="card section calls-card">
        <div class="sec-head">
          <h2 class="sec-title" style="margin:0;">Звонки</h2>
          <span v-if="activity.calls.length" class="muted small">{{ activity.calls.length }} зв.</span>
        </div>

        <div v-if="activityLoading && !activity.calls.length" class="muted small">Загрузка…</div>
        <div v-else-if="activityError" class="muted small">{{ activityError }}</div>
        <div v-else-if="!activity.calls.length" class="empty-inline">Звонков по лиду нет.</div>

        <div v-else class="calls-list">
          <div v-for="c in activity.calls" :key="c.id" class="call-row">
            <div class="call-dir" :class="c.direction === 'Входящий' ? 'in' : 'out'">
              {{ c.direction === 'Входящий' ? '↙' : '↗' }}
            </div>
            <div class="call-main">
              <div class="call-top">
                <span class="mono">{{ c.phone || '—' }}</span>
                <span class="muted small">· {{ fmtDate(c.date) }}</span>
                <span class="muted small">· {{ fmtDuration(c.duration) }}</span>
              </div>
              <div v-if="c.manager" class="call-mgr muted small">{{ c.manager }}</div>
            </div>
            <div class="call-actions">
              <button
                v-if="c.record_url"
                class="play-icon"
                :class="{ active: playingCall === c.id }"
                :title="playingCall === c.id ? 'Скрыть плеер' : 'Слушать'"
                @click="togglePlay(c)"
              >
                <X v-if="playingCall === c.id" :size="13" />
                <Play v-else :size="13" />
              </button>
              <button
                v-if="c.analyzed && c.analysis_id"
                class="ghost small-btn"
                @click="router.push(`/t/${c.analysis_id}`)"
                title="Открыть анализ"
              >Анализ <ArrowRight :size="13" /></button>
            </div>
            <div v-if="playingCall === c.id && c.record_url" class="call-player">
              <audio :src="c.record_url" controls autoplay preload="none" style="width:100%;"></audio>
            </div>
          </div>
        </div>
      </div>

      <div class="card section timeline-card">
        <div class="sec-head">
          <h2 class="sec-title" style="margin:0;">Таймлайн</h2>
          <span v-if="activity.timeline.length" class="muted small">{{ activity.timeline.length }} событий</span>
        </div>

        <div v-if="activityLoading && !activity.timeline.length" class="muted small">Загрузка…</div>
        <div v-else-if="activityError" class="muted small">{{ activityError }}</div>
        <div v-else-if="!activity.timeline.length" class="empty-inline">Событий пока нет.</div>

        <ul v-else class="timeline">
          <li
            v-for="e in activity.timeline"
            :key="e.kind + e.id"
            class="tl-item"
            :class="['tl-' + (e.kind === 'comment' ? 'comment' : e.activity_type || 'activity'), { done: e.completed }]"
          >
            <div class="tl-dot">{{ e.kind === 'comment' ? '💬' : activityIcon(e.activity_type) }}</div>
            <div class="tl-body">
              <div class="tl-head">
                <span class="tl-kind">
                  {{ e.kind === 'comment' ? 'Комментарий' : activityLabel(e.activity_type) }}
                </span>
                <span v-if="e.author" class="tl-author">· {{ e.author }}</span>
                <span class="tl-date muted small">{{ fmtDate(e.date) }}</span>
              </div>
              <div v-if="e.subject" class="tl-subject">{{ e.subject }}</div>
              <div v-if="e.text" class="tl-text" v-html="e.text"></div>
            </div>
          </li>
        </ul>
      </div>
    </template>
  </div>
</template>

<style scoped>
.back { margin-bottom: 16px; padding: 8px 14px; font-size: 13px; }
.loading { display: flex; align-items: center; gap: 10px; color: var(--text-dim); padding: 30px 0; }

.hero {
  display: flex;
  gap: 24px;
  align-items: center;
  padding: 22px 26px;
  margin-bottom: 20px;
}
.hero-main { flex: 1; min-width: 0; }
.hero-tag {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-muted);
}
.hero-title {
  font-size: 24px;
  font-weight: 800;
  letter-spacing: -0.02em;
  margin: 4px 0 4px;
}
.hero-sub { color: var(--text-dim); font-size: 14px; margin-bottom: 10px; }
.hero-meta { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }

.status-pill {
  padding: 5px 12px;
  border-radius: 999px;
  background: var(--brand-soft);
  color: var(--brand);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.02em;
}
.meta-chip {
  padding: 4px 10px;
  border-radius: 999px;
  background: var(--surface-2);
  color: var(--text-dim);
  font-size: 12px;
  font-weight: 600;
}

.hero-side {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 12px;
  min-width: 180px;
}
.hero-actions {
  display: flex;
  flex-direction: column;
  gap: 6px;
  align-items: flex-end;
}
.analyze-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  border-radius: 999px;
  background: var(--brand);
  color: #fff;
  border: none;
  font-size: 12.5px;
  font-weight: 700;
  cursor: pointer;
  white-space: nowrap;
  box-shadow: none;
  transition: background .15s, opacity .15s;
}
.analyze-btn:hover { background: var(--brand-hover); }
.analyze-btn:disabled { opacity: .7; cursor: progress; }
.spinner-sm {
  width: 12px; height: 12px;
  border: 2px solid rgba(255,255,255,.5);
  border-top-color: #fff;
  border-radius: 50%;
  display: inline-block;
  animation: spin .8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
.bitrix-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  border-radius: 999px;
  background: var(--surface-2);
  border: 1px solid var(--border);
  color: var(--text);
  font-size: 12.5px;
  font-weight: 600;
  text-decoration: none;
  white-space: nowrap;
  transition: background .15s, color .15s, border-color .15s;
}
.bitrix-btn:hover {
  background: var(--brand);
  border-color: transparent;
  color: #fff;
}
.bitrix-arrow { font-size: 13px; }
.hero-money {
  text-align: right;
  min-width: 160px;
}
.money-cap {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--text-muted);
  font-weight: 700;
}
.money-val {
  font-size: 26px;
  font-weight: 800;
  letter-spacing: -0.02em;
  margin-top: 4px;
  background: var(--brand-grad);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  font-family: 'SF Mono', Menlo, monospace;
  white-space: nowrap;
}

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 16px;
  margin-bottom: 18px;
}
.section { padding: 18px 20px; }
.sec-title {
  font-size: 14px;
  font-weight: 700;
  letter-spacing: -0.01em;
  margin: 0 0 12px;
}

.contact-block { margin-bottom: 12px; }
.contact-block:last-child { margin-bottom: 0; }
.contact-cap {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--text-muted);
  font-weight: 700;
  margin-bottom: 4px;
}
.contact-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 4px 0;
}
.contact-val {
  font-size: 14px;
  font-weight: 500;
  color: var(--text);
  text-decoration: none;
}
a.contact-val:hover { color: var(--brand); text-decoration: underline; }
.contact-kind {
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--text-muted);
  background: var(--surface-2);
  padding: 2px 6px;
  border-radius: 999px;
}

.kv-row {
  display: grid;
  grid-template-columns: 110px 1fr;
  gap: 12px;
  padding: 6px 0;
  font-size: 13.5px;
  border-bottom: 1px dashed var(--border);
}
.kv-row:last-child { border-bottom: none; }
.kv-key { color: var(--text-muted); font-weight: 600; font-size: 12px; }
.kv-val { color: var(--text); overflow-wrap: anywhere; }

.mgr-card {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
}
.mgr-avatar-lg {
  width: 40px; height: 40px;
  border-radius: 50%;
  background: var(--brand-grad);
  color: #fff;
  display: grid; place-items: center;
  font-weight: 700; font-size: 14px;
  flex-shrink: 0;
}
.mgr-name-lg { font-weight: 700; font-size: 14px; }
.mgr-id { font-size: 12px; }
.muted { color: var(--text-muted); }

.mono { font-family: 'SF Mono', Menlo, monospace; }

.empty-inline { color: var(--text-muted); font-size: 13px; }

.lead-text {
  font-size: 14px;
  line-height: 1.55;
  color: var(--text);
  white-space: pre-wrap;
  word-wrap: break-word;
}
.comments-card { padding: 18px 22px; }

.sec-head {
  display: flex; align-items: baseline; justify-content: space-between;
  gap: 8px;
  margin-bottom: 12px;
}
.small { font-size: 12px; }

.analysis-card { padding: 18px 22px; margin-bottom: 18px; }
.analysis-card .sec-head { margin-bottom: 14px; }
.analysis-meta { display: flex; align-items: center; gap: 10px; }
.risk-pill {
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 11.5px;
  font-weight: 700;
  letter-spacing: 0.02em;
  text-transform: uppercase;
}
.risk-low { background: var(--success-soft); color: var(--success); }
.risk-medium { background: var(--warn-soft); color: var(--warn); }
.risk-high { background: var(--danger-soft); color: var(--danger); }
.analysis-summary {
  font-size: 14px;
  line-height: 1.55;
  color: var(--text);
  padding: 12px 14px;
  background: var(--surface-2);
  border-radius: 10px;
  margin-bottom: 14px;
}
.analysis-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 14px;
}
.analysis-block {
  padding: 12px 14px;
  border-radius: 10px;
  background: var(--surface);
  border: 1px solid var(--border);
}
.analysis-block.highlight {
  background: var(--brand-soft);
  border-color: transparent;
}
.analysis-block.pros { border-left: 3px solid var(--success); }
.analysis-block.cons { border-left: 3px solid var(--danger); }
.block-cap {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-muted);
  margin-bottom: 6px;
}
.analysis-list {
  margin: 0;
  padding-left: 18px;
  font-size: 13.5px;
  line-height: 1.5;
  color: var(--text);
}
.analysis-list li + li { margin-top: 4px; }
.analysis-foot {
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px dashed var(--border);
}
.error-card .error-msg { margin-bottom: 10px; }
.placeholder-card .loading { padding: 16px 0 0; }

.scorecard-card { padding: 20px 22px; margin-bottom: 18px; }
.scorecard-head { align-items: flex-start; margin-bottom: 16px; }
.scorecard-verdict {
  font-size: 13.5px;
  color: var(--text-dim);
  margin-top: 6px;
  max-width: 60ch;
  line-height: 1.5;
}
.scorecard-meta {
  display: flex;
  align-items: center;
  gap: 12px;
}
.score-big {
  display: flex;
  align-items: baseline;
  gap: 2px;
  font-family: 'SF Mono', Menlo, monospace;
}
.score-num {
  font-size: 32px;
  font-weight: 800;
  letter-spacing: -0.02em;
  background: var(--brand-grad);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}
.score-den { font-size: 16px; color: var(--text-muted); font-weight: 600; }
.grade-pill {
  padding: 5px 12px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.02em;
  white-space: nowrap;
}
.grade-reference { background: var(--info-soft); color: var(--info); }
.grade-good { background: var(--success-soft); color: var(--success); }
.grade-ok { background: var(--warn-soft); color: var(--warn); }
.grade-bad { background: var(--danger-soft); color: var(--danger); }

.sw-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
  margin-bottom: 18px;
}
@media (max-width: 720px) { .sw-grid { grid-template-columns: 1fr; } }

.criteria-section { display: flex; flex-direction: column; gap: 16px; }
.cat-group {
  border: 1px solid var(--border);
  border-radius: 12px;
  overflow: hidden;
}
.cat-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 14px;
  background: var(--surface-2);
  border-bottom: 1px solid var(--border);
}
.cat-name {
  font-size: 11.5px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-muted);
}
.cat-score {
  font-family: 'SF Mono', Menlo, monospace;
  font-size: 13px;
  font-weight: 700;
  color: var(--text);
}
.crit-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 140px;
  gap: 16px;
  padding: 10px 14px;
  border-top: 1px dashed var(--border);
  align-items: center;
}
.crit-row:first-of-type { border-top: none; }
.crit-main { min-width: 0; }
.crit-name { font-size: 13.5px; font-weight: 600; color: var(--text); }
.crit-comment {
  font-size: 12.5px;
  color: var(--text-dim);
  margin-top: 3px;
  line-height: 1.45;
}
.crit-score-cell { display: flex; flex-direction: column; gap: 4px; align-items: stretch; }
.crit-score {
  font-family: 'SF Mono', Menlo, monospace;
  font-size: 14px;
  text-align: right;
  font-weight: 700;
}
.crit-num.crit-good { color: var(--success); }
.crit-num.crit-ok { color: #b88500; }
.crit-num.crit-warn { color: #d97706; }
.crit-num.crit-low { color: var(--danger); }
.crit-num.crit-zero { color: var(--text-muted); }
.crit-max { color: var(--text-muted); font-weight: 500; }
.crit-bar {
  height: 4px;
  border-radius: 2px;
  background: var(--surface-2);
  overflow: hidden;
}
.crit-bar-fill {
  height: 100%;
  border-radius: 2px;
  transition: width .3s;
}
.crit-bar-fill.crit-good { background: var(--success); }
.crit-bar-fill.crit-ok { background: #f1b91a; }
.crit-bar-fill.crit-warn { background: #f59e0b; }
.crit-bar-fill.crit-low { background: var(--danger); }
.crit-bar-fill.crit-zero { background: var(--text-muted); opacity: .25; }

.stops-section {
  margin-top: 18px;
  padding: 12px 14px;
  background: var(--danger-soft);
  border-radius: 12px;
}
.stops-section .block-cap { color: var(--danger); margin-bottom: 8px; }
.stop-row {
  display: grid;
  grid-template-columns: 50px 1fr;
  gap: 12px;
  align-items: start;
  padding: 6px 0;
  border-top: 1px dashed rgba(0,0,0,.08);
}
.stop-row:first-of-type { border-top: none; }
.stop-penalty {
  font-family: 'SF Mono', Menlo, monospace;
  font-size: 14px;
  font-weight: 800;
  color: var(--danger);
}
.stop-name { font-size: 13.5px; font-weight: 600; color: var(--text); }
.stop-comment { font-size: 12.5px; color: var(--text-dim); margin-top: 2px; }

.coaching-section { margin-top: 18px; }
.coach-row {
  padding: 10px 12px;
  background: var(--brand-soft);
  border-radius: 10px;
  margin-bottom: 8px;
}
.coach-row:last-child { margin-bottom: 0; }
.coach-title { font-size: 13.5px; font-weight: 700; color: var(--text); }
.coach-focus { margin-top: 2px; }
.coach-action {
  font-size: 13px;
  color: var(--brand);
  margin-top: 4px;
  font-weight: 600;
}

.calls-card { padding: 18px 22px; margin-bottom: 18px; }
.calls-list { display: flex; flex-direction: column; }
.call-row {
  display: grid;
  grid-template-columns: 36px 1fr auto;
  gap: 12px;
  align-items: center;
  padding: 10px 0;
  border-bottom: 1px dashed var(--border);
}
.call-row:last-child { border-bottom: none; }
.call-dir {
  width: 30px; height: 30px;
  border-radius: 50%;
  display: grid; place-items: center;
  font-size: 14px; font-weight: 800;
  background: var(--brand-soft);
  color: var(--brand);
}
.call-dir.in { background: var(--success-soft); color: var(--success); }
.call-main { min-width: 0; }
.call-top { display: flex; gap: 4px; align-items: baseline; flex-wrap: wrap; }
.call-mgr { margin-top: 2px; }
.call-actions { display: flex; gap: 8px; align-items: center; }
.play-icon {
  width: 32px; height: 32px;
  padding: 0;
  border-radius: 50%;
  display: grid; place-items: center;
  background: var(--brand-soft);
  border: none;
  color: var(--brand);
  font-size: 12px;
  box-shadow: none;
  cursor: pointer;
}
.play-icon:hover { background: rgba(20, 184, 166, 0.18); }
.play-icon.active { background: var(--danger-soft); color: var(--danger); }
.small-btn { padding: 6px 12px; font-size: 12px; }
.call-player { grid-column: 1 / -1; padding-top: 4px; }

.timeline-card { padding: 18px 22px; }
.timeline {
  list-style: none;
  margin: 0;
  padding: 0;
  position: relative;
}
.timeline::before {
  content: '';
  position: absolute;
  left: 14px;
  top: 8px;
  bottom: 8px;
  width: 2px;
  background: var(--border);
  border-radius: 1px;
}
.tl-item {
  position: relative;
  padding: 6px 0 14px 42px;
}
.tl-item:last-child { padding-bottom: 0; }
.tl-dot {
  position: absolute;
  left: 0;
  top: 4px;
  width: 30px; height: 30px;
  border-radius: 50%;
  display: grid; place-items: center;
  font-size: 14px;
  background: var(--brand-soft);
  color: var(--brand);
  border: 3px solid var(--surface);
  z-index: 1;
}
.tl-comment .tl-dot { background: var(--surface-3); color: var(--text-dim); }
.tl-call .tl-dot { background: var(--brand-soft); color: var(--brand); }
.tl-email .tl-dot { background: var(--warn-soft); color: var(--warn); }
.tl-meeting .tl-dot { background: #ede2ff; color: #7a4ddc; }
.tl-task .tl-dot { background: var(--success-soft); color: var(--success); }
.tl-item.done .tl-dot { opacity: 0.85; }

.tl-head {
  display: flex; align-items: baseline; gap: 6px; flex-wrap: wrap;
  font-size: 12px;
}
.tl-kind { font-weight: 700; color: var(--text); }
.tl-author { color: var(--text-dim); font-weight: 500; }
.tl-date { margin-left: auto; }
.tl-subject {
  font-size: 14px;
  font-weight: 600;
  color: var(--text);
  margin-top: 4px;
}
.tl-text {
  font-size: 13.5px;
  color: var(--text-dim);
  margin-top: 4px;
  line-height: 1.5;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

@media (max-width: 700px) {
  .hero { flex-direction: column; align-items: flex-start; }
  .hero-side { align-items: flex-start; width: 100%; }
  .hero-money { text-align: left; }
  .kv-row { grid-template-columns: 1fr; gap: 2px; }
}
</style>
