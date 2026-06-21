<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../api'

const route = useRoute()
const router = useRouter()
const item = ref(null)
const loading = ref(true)
const error = ref('')
const copied = ref(false)
const audioUrl = ref('')

async function load() {
  loading.value = true
  try {
    const { data } = await api.get(`/transcriptions/${route.params.id}`)
    item.value = data
    if (data.has_audio) await fetchAudio()
  } catch (e) {
    error.value = e.response?.data?.detail || 'Не удалось загрузить'
  } finally {
    loading.value = false
  }
}

async function fetchAudio() {
  try {
    const { data } = await api.get(`/transcriptions/${route.params.id}/audio`, {
      responseType: 'blob',
    })
    if (audioUrl.value) URL.revokeObjectURL(audioUrl.value)
    audioUrl.value = URL.createObjectURL(data)
  } catch (e) {
    // молча — плеер не покажем
  }
}

onBeforeUnmount(() => {
  if (audioUrl.value) URL.revokeObjectURL(audioUrl.value)
})

function fmtCallDate(s) {
  if (!s) return ''
  return new Date(s).toLocaleString('ru-RU', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

function fmtDuration(sec) {
  if (!sec) return ''
  const m = Math.floor(sec / 60)
  const s = sec % 60
  return `${m}:${String(s).padStart(2, '0')}`
}

async function remove() {
  if (!confirm('Удалить этот анализ?')) return
  await api.delete(`/transcriptions/${route.params.id}`)
  router.push('/analyses')
}

async function copyText() {
  if (!item.value?.text) return
  await navigator.clipboard.writeText(item.value.text)
  copied.value = true
  setTimeout(() => (copied.value = false), 1500)
}

function fmtDate(s) {
  if (!s) return ''
  return new Date(s).toLocaleString()
}

function scoreClass(score) {
  if (score >= 80) return 'good'
  if (score >= 60) return 'ok'
  if (score >= 40) return 'warn'
  return 'bad'
}

const chatMessages = computed(() => {
  if (item.value?.source !== 'bitrix_chat' || !item.value?.text) return []
  const lines = item.value.text.split(/\r?\n/)
  const messages = []
  for (const raw of lines) {
    const line = raw.trim()
    if (!line) continue
    const m = line.match(/^([^:]+):\s*(.*)$/)
    if (m) {
      const author = m[1].trim()
      const text = m[2]
      const isOperator = author.toLowerCase() === 'менеджер' || author.toLowerCase() === 'оператор'
        || (item.value.bitrix_manager && author === item.value.bitrix_manager)
      messages.push({ author, text, mine: isOperator })
    } else if (messages.length) {
      messages[messages.length - 1].text += '\n' + line
    } else {
      messages.push({ author: '', text: line, mine: false })
    }
  }
  return messages
})

onMounted(load)
</script>

<template>
  <div class="container">
    <button class="ghost back" @click="router.push('/analyses')">← Назад</button>

    <div v-if="loading" class="row" style="color:var(--text-dim);gap:10px;">
      <span class="spinner"></span> Loading…
    </div>

    <div v-else-if="error" class="error-msg">{{ error }}</div>

    <template v-else-if="item">
      <div class="head">
        <div>
          <h1 class="page-title" style="margin-bottom:6px;">{{ item.filename }}</h1>
          <div class="row" style="gap:8px;flex-wrap:wrap;">
            <span class="badge" :class="item.status">{{ item.status }}</span>
            <span class="badge">{{ fmtDate(item.created_at) }}</span>
            <span v-if="item.analysis?.language" class="badge">{{ item.analysis.language.toUpperCase() }}</span>
            <span v-if="item.analysis?.sentiment" class="badge" :class="item.analysis.sentiment">
              {{ item.analysis.sentiment }}
            </span>
          </div>
        </div>
        <div class="spacer"></div>
        <button class="danger" @click="remove">Удалить</button>
      </div>

      <div v-if="item.source === 'bitrix_chat'" class="call-card card">
        <div class="call-grid">
          <div v-if="item.bitrix_manager" class="call-cell">
            <div class="call-cell-label">Оператор</div>
            <div class="call-cell-value">
              <div class="op-avatar-sm">{{ item.bitrix_manager[0]?.toUpperCase() }}</div>
              {{ item.bitrix_manager }}
            </div>
          </div>
          <div v-if="item.bitrix_channel" class="call-cell">
            <div class="call-cell-label">Канал</div>
            <div class="call-cell-value">{{ item.bitrix_channel }}</div>
          </div>
          <div v-if="item.bitrix_client" class="call-cell">
            <div class="call-cell-label">Клиент</div>
            <div class="call-cell-value">{{ item.bitrix_client }}</div>
          </div>
          <div v-if="item.bitrix_call_date" class="call-cell">
            <div class="call-cell-label">Дата</div>
            <div class="call-cell-value">{{ fmtCallDate(item.bitrix_call_date) }}</div>
          </div>
          <div v-if="item.messages_count" class="call-cell">
            <div class="call-cell-label">Сообщений</div>
            <div class="call-cell-value mono">{{ item.messages_count }}</div>
          </div>
        </div>
      </div>

      <div v-if="item.source === 'bitrix_call'" class="call-card card">
        <div class="call-grid">
          <div v-if="item.bitrix_manager" class="call-cell">
            <div class="call-cell-label">Оператор</div>
            <div class="call-cell-value">
              <div class="op-avatar-sm">{{ item.bitrix_manager[0]?.toUpperCase() }}</div>
              {{ item.bitrix_manager }}
            </div>
          </div>
          <div v-if="item.bitrix_phone" class="call-cell">
            <div class="call-cell-label">Телефон</div>
            <div class="call-cell-value mono">{{ item.bitrix_phone }}</div>
          </div>
          <div v-if="item.bitrix_direction" class="call-cell">
            <div class="call-cell-label">Тип</div>
            <div class="call-cell-value">{{ item.bitrix_direction }}</div>
          </div>
          <div v-if="item.bitrix_call_date" class="call-cell">
            <div class="call-cell-label">Дата звонка</div>
            <div class="call-cell-value">{{ fmtCallDate(item.bitrix_call_date) }}</div>
          </div>
          <div v-if="item.duration" class="call-cell">
            <div class="call-cell-label">Длительность</div>
            <div class="call-cell-value mono">{{ fmtDuration(item.duration) }}</div>
          </div>
        </div>
        <div v-if="audioUrl" class="call-audio">
          <audio :src="audioUrl" controls preload="metadata" style="width:100%;"></audio>
        </div>
        <div v-else-if="item.has_audio" class="call-audio-loading">
          <span class="spinner"></span> Загрузка записи…
        </div>
      </div>

      <div v-if="item.error" class="error-msg" style="margin-bottom:18px;">{{ item.error }}</div>

      <!-- OKO Sales Analysis -->
      <template v-if="item.sales_analysis">
        <div class="oko-hero card">
          <div class="oko-hero-left">
            <div class="oko-tag">OKO Systems · Аудит коммуникации</div>
            <p class="oko-verdict">{{ item.sales_analysis.meta.system_verdict || '—' }}</p>
          </div>
          <div class="oko-score" :class="scoreClass(item.sales_analysis.meta.total_score)">
            <svg viewBox="0 0 100 100" class="score-ring">
              <circle cx="50" cy="50" r="42" class="ring-bg" />
              <circle
                cx="50" cy="50" r="42"
                class="ring-fg"
                :stroke-dasharray="264"
                :stroke-dashoffset="264 - (264 * item.sales_analysis.meta.total_score / 100)"
              />
            </svg>
            <div class="score-text">
              <div class="score-value">{{ item.sales_analysis.meta.total_score }}</div>
              <div class="score-label">из 100</div>
            </div>
          </div>
        </div>

        <div class="oko-grid">
          <div class="card sw-card">
            <h2>Сильные стороны</h2>
            <ul v-if="item.sales_analysis.analysis.strengths.length" class="sw-list strengths">
              <li v-for="(s, i) in item.sales_analysis.analysis.strengths" :key="i">
                <span class="sw-mark">✓</span><span>{{ s }}</span>
              </li>
            </ul>
            <div v-else class="empty-inline">Не выделены.</div>
          </div>
          <div class="card sw-card">
            <h2>Слабые стороны</h2>
            <ul v-if="item.sales_analysis.analysis.weaknesses.length" class="sw-list weaknesses">
              <li v-for="(w, i) in item.sales_analysis.analysis.weaknesses" :key="i">
                <span class="sw-mark">!</span><span>{{ w }}</span>
              </li>
            </ul>
            <div v-else class="empty-inline">Не выделены.</div>
          </div>
        </div>

        <div class="card criteria-card">
          <h2>Оценка по критериям</h2>
          <div class="criteria-list">
            <div
              v-for="c in item.sales_analysis.criteria_scores"
              :key="c.criterion_id"
              class="crit"
            >
              <div class="crit-head">
                <div class="crit-name">{{ c.criterion_name }}</div>
                <div class="crit-score" :class="scoreClass(c.score)">{{ c.score }}</div>
              </div>
              <div class="crit-bar">
                <div
                  class="crit-bar-fill"
                  :class="scoreClass(c.score)"
                  :style="{ width: c.score + '%' }"
                ></div>
              </div>
              <div v-if="c.comment" class="crit-comment">{{ c.comment }}</div>
            </div>
          </div>
        </div>

        <div v-if="item.sales_analysis.ai_coaching_tasks.length" class="card tasks-card">
          <h2>Задачи на развитие</h2>
          <div class="tasks-grid">
            <div
              v-for="(task, i) in item.sales_analysis.ai_coaching_tasks"
              :key="i"
              class="task"
            >
              <div class="task-icon">🎯</div>
              <div class="task-body">
                <div class="task-title">{{ task.title }}</div>
                <div class="task-meta">
                  <span class="badge">{{ task.focus_area }}</span>
                  <span class="task-action">{{ task.action_item }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div v-if="item.source === 'bitrix_chat'" class="card transcript-card transcript-full">
          <div class="card-head">
            <h2>Переписка</h2>
            <button class="ghost small" @click="copyText">
              {{ copied ? '✓ Скопировано' : 'Копировать' }}
            </button>
          </div>
          <div v-if="chatMessages.length" class="chat-thread">
            <div
              v-for="(m, i) in chatMessages"
              :key="i"
              class="msg"
              :class="m.mine ? 'mine' : 'theirs'"
            >
              <div class="msg-author">{{ m.author || (m.mine ? 'Менеджер' : 'Клиент') }}</div>
              <div class="msg-bubble">{{ m.text }}</div>
            </div>
          </div>
          <div v-else class="empty-inline">Сообщения не найдены.</div>
        </div>

        <div v-else class="card transcript-card transcript-full">
          <div class="card-head">
            <h2>Транскрипт</h2>
            <button class="ghost small" @click="copyText">
              {{ copied ? '✓ Скопировано' : 'Копировать' }}
            </button>
          </div>
          <div v-if="item.text" class="transcript">{{ item.text }}</div>
          <div v-else class="empty-inline">Транскрипт отсутствует.</div>
        </div>
      </template>

      <!-- Legacy generic analysis -->
      <div v-else class="grid">
        <div class="card transcript-card">
          <div class="card-head">
            <h2>Transcript</h2>
            <button class="ghost small" @click="copyText">
              {{ copied ? '✓ Copied' : 'Copy' }}
            </button>
          </div>
          <div v-if="item.text" class="transcript">{{ item.text }}</div>
          <div v-else class="empty-inline">No transcript available.</div>
        </div>

        <div class="col" style="gap:16px;">
          <div class="card">
            <h2>Summary</h2>
            <p class="summary">{{ item.analysis?.summary || '—' }}</p>
          </div>

          <div class="card">
            <h2>Topics</h2>
            <div v-if="item.analysis?.topics?.length" class="topics">
              <span v-for="t in item.analysis.topics" :key="t" class="topic">#{{ t }}</span>
            </div>
            <div v-else class="empty-inline">No topics identified.</div>
          </div>

          <div class="card">
            <h2>Action items</h2>
            <ul v-if="item.analysis?.action_items?.length" class="actions-list">
              <li v-for="(a, i) in item.analysis.action_items" :key="i">{{ a }}</li>
            </ul>
            <div v-else class="empty-inline">No action items.</div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.back { margin-bottom: 16px; padding: 8px 14px; font-size: 13px; }

.head {
  display: flex; align-items: flex-start; gap: 16px;
  margin-bottom: 22px;
}

.grid {
  display: grid;
  grid-template-columns: 1.4fr 1fr;
  gap: 18px;
  align-items: start;
}
@media (max-width: 900px) {
  .grid { grid-template-columns: 1fr; }
}

.card-head {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 14px;
}
h2 {
  font-size: 14px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--text-dim);
  margin: 0 0 12px;
}
.card-head h2 { margin: 0; }
.small { padding: 6px 12px; font-size: 12px; }

.transcript-card { max-height: 80vh; overflow-y: auto; }
.transcript {
  font-size: 15px;
  line-height: 1.75;
  color: var(--text);
  white-space: pre-wrap;
}

.summary {
  font-size: 15px;
  line-height: 1.6;
  margin: 0;
  color: var(--text);
}

.topics {
  display: flex; flex-wrap: wrap; gap: 8px;
}
.topic {
  font-size: 13px;
  color: var(--brand);
  background: var(--brand-soft);
  border: 1px solid #cce2ff;
  padding: 5px 12px;
  border-radius: 999px;
  font-weight: 500;
}

.actions-list {
  margin: 0;
  padding-left: 18px;
  display: flex; flex-direction: column; gap: 8px;
}
.actions-list li { font-size: 14px; line-height: 1.5; }

.empty-inline { color: var(--text-muted); font-size: 14px; }

.call-card { margin-bottom: 18px; padding: 18px 22px; }
.call-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 16px;
  margin-bottom: 14px;
}
.call-cell { min-width: 0; }
.call-cell-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.08em;
}
.call-cell-value {
  font-size: 14px;
  font-weight: 600;
  margin-top: 4px;
  display: flex; align-items: center; gap: 8px;
  overflow: hidden; white-space: nowrap; text-overflow: ellipsis;
}
.call-cell-value.mono { font-family: 'SF Mono', Menlo, monospace; font-size: 13px; }
.op-avatar-sm {
  width: 24px; height: 24px;
  border-radius: 50%;
  background: var(--brand-grad);
  color: #fff;
  display: grid; place-items: center;
  font-size: 11px; font-weight: 700;
  flex-shrink: 0;
}
.call-audio { padding-top: 8px; border-top: 1px solid var(--border); }
.call-audio-loading {
  display: flex; align-items: center; gap: 10px;
  padding: 10px 0 0;
  border-top: 1px solid var(--border);
  color: var(--text-dim);
  font-size: 13px;
}

.chat-thread {
  display: flex;
  flex-direction: column;
  gap: 14px;
  max-height: 80vh;
  overflow-y: auto;
  padding-right: 4px;
}
.msg { display: flex; flex-direction: column; max-width: 78%; }
.msg.theirs { align-self: flex-start; }
.msg.mine { align-self: flex-end; align-items: flex-end; }
.msg-author {
  font-size: 11px;
  font-weight: 700;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin-bottom: 4px;
  padding: 0 4px;
}
.msg.mine .msg-author { color: var(--brand); }
.msg-bubble {
  padding: 10px 14px;
  border-radius: 16px;
  font-size: 14px;
  line-height: 1.45;
  white-space: pre-wrap;
  word-wrap: break-word;
}
.msg.theirs .msg-bubble {
  background: var(--surface-2);
  color: var(--text);
  border-bottom-left-radius: 4px;
}
.msg.mine .msg-bubble {
  background: var(--brand);
  color: #fff;
  border-bottom-right-radius: 4px;
  box-shadow: 0 8px 22px -10px rgba(3, 129, 254, 0.55);
}

/* ===== OKO Sales Analysis ===== */

.oko-hero {
  display: flex;
  align-items: center;
  gap: 32px;
  margin-bottom: 18px;
  background:
    radial-gradient(600px 200px at 0% 0%, rgba(3, 129, 254, 0.08), transparent 70%),
    var(--surface);
}
.oko-hero-left { flex: 1; min-width: 0; }
.oko-tag {
  display: inline-block;
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  color: var(--brand);
  background: var(--brand-soft);
  padding: 4px 10px;
  border-radius: 999px;
  margin-bottom: 14px;
}
.oko-verdict {
  font-size: 18px;
  line-height: 1.55;
  font-weight: 500;
  color: var(--text);
  margin: 0;
}

.oko-score {
  position: relative;
  width: 130px;
  height: 130px;
  flex-shrink: 0;
}
.score-ring {
  width: 100%;
  height: 100%;
  transform: rotate(-90deg);
}
.ring-bg {
  fill: none;
  stroke: var(--surface-3);
  stroke-width: 8;
}
.ring-fg {
  fill: none;
  stroke-width: 8;
  stroke-linecap: round;
  transition: stroke-dashoffset 0.8s cubic-bezier(0.4, 0, 0.2, 1);
}
.oko-score.good .ring-fg { stroke: var(--success); }
.oko-score.ok .ring-fg { stroke: var(--brand); }
.oko-score.warn .ring-fg { stroke: var(--warn); }
.oko-score.bad .ring-fg { stroke: var(--danger); }

.score-text {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}
.score-value {
  font-size: 36px;
  font-weight: 800;
  letter-spacing: -0.03em;
  line-height: 1;
}
.oko-score.good .score-value { color: var(--success); }
.oko-score.ok .score-value { color: var(--brand); }
.oko-score.warn .score-value { color: var(--warn); }
.oko-score.bad .score-value { color: var(--danger); }
.score-label {
  font-size: 11px;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.1em;
  margin-top: 2px;
}

.oko-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 18px;
  margin-bottom: 18px;
}
@media (max-width: 800px) {
  .oko-grid { grid-template-columns: 1fr; }
  .oko-hero { flex-direction: column; align-items: flex-start; }
}

.sw-list { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 10px; }
.sw-list li {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  font-size: 14px;
  line-height: 1.5;
}
.sw-mark {
  flex-shrink: 0;
  width: 22px; height: 22px;
  border-radius: 50%;
  display: grid; place-items: center;
  font-size: 12px;
  font-weight: 800;
}
.sw-list.strengths .sw-mark { background: var(--success-soft); color: var(--success); }
.sw-list.weaknesses .sw-mark { background: var(--danger-soft); color: var(--danger); }

.criteria-card { margin-bottom: 18px; }
.criteria-list {
  display: flex;
  flex-direction: column;
  gap: 18px;
}
.crit { padding: 4px 0; }
.crit-head {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 8px;
}
.crit-name { font-size: 14px; font-weight: 600; }
.crit-score {
  font-size: 14px;
  font-weight: 700;
  padding: 2px 10px;
  border-radius: 999px;
}
.crit-score.good { color: var(--success); background: var(--success-soft); }
.crit-score.ok { color: var(--brand); background: var(--brand-soft); }
.crit-score.warn { color: var(--warn); background: var(--warn-soft); }
.crit-score.bad { color: var(--danger); background: var(--danger-soft); }

.crit-bar {
  height: 6px;
  background: var(--surface-3);
  border-radius: 999px;
  overflow: hidden;
}
.crit-bar-fill {
  height: 100%;
  border-radius: 999px;
  transition: width 0.8s cubic-bezier(0.4, 0, 0.2, 1);
}
.crit-bar-fill.good { background: linear-gradient(90deg, #1f9d55, #2ec77a); }
.crit-bar-fill.ok { background: var(--brand-grad); }
.crit-bar-fill.warn { background: linear-gradient(90deg, #c98a00, #f0b020); }
.crit-bar-fill.bad { background: linear-gradient(90deg, #e5484d, #ff6b6b); }

.crit-comment {
  font-size: 13px;
  color: var(--text-dim);
  line-height: 1.5;
  margin-top: 8px;
}

.tasks-card { margin-bottom: 18px; }
.tasks-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 12px;
}
.task {
  display: flex;
  gap: 14px;
  padding: 16px 18px;
  background: linear-gradient(135deg, var(--brand-soft-2), var(--surface));
  border: 1px solid #d0e4fb;
  border-radius: var(--radius);
}
.task-icon { font-size: 22px; line-height: 1; flex-shrink: 0; }
.task-body { flex: 1; min-width: 0; }
.task-title {
  font-size: 14px;
  font-weight: 600;
  line-height: 1.45;
  margin-bottom: 6px;
}
.task-meta {
  display: flex; gap: 10px; align-items: center; flex-wrap: wrap;
}
.task-action {
  font-size: 13px;
  color: var(--text-dim);
}

.transcript-full {
  margin-top: 4px;
  max-height: none;
}
</style>
