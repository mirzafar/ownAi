<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../api'

const route = useRoute()
const router = useRouter()

const lead = ref(null)
const loading = ref(true)
const error = ref('')
const activity = ref({ timeline: [], calls: [] })
const activityLoading = ref(false)
const activityError = ref('')
const playingCall = ref(null)

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
  try {
    const { data } = await api.get(`/bitrix/leads/${route.params.id}`)
    lead.value = data
    loadActivity()
  } catch (e) {
    error.value = e.response?.data?.detail || 'Не удалось загрузить лида'
    lead.value = null
  } finally {
    loading.value = false
  }
}

watch(() => route.params.id, load)

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

onMounted(load)
</script>

<template>
  <div class="container">
    <button class="ghost back" @click="router.push('/leads')">← К лидам</button>

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
                <span v-if="playingCall === c.id">✕</span>
                <span v-else>▶</span>
              </button>
              <button
                v-if="c.analyzed && c.transcription_id"
                class="ghost small-btn"
                @click="router.push(`/t/${c.transcription_id}`)"
                title="Открыть анализ"
              >Анализ →</button>
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
  min-width: 160px;
}
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
.play-icon:hover { background: #d9e9ff; }
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
