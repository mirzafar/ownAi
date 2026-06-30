<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../api'
import { useTasksStore } from '../stores/tasks'
import { ArrowLeft, RotateCcw, Check, Target, Trash2 } from 'lucide-vue-next'

const route = useRoute()
const router = useRouter()
const tasks = useTasksStore()
const item = ref(null)
const loading = ref(true)
const error = ref('')
const copied = ref(false)
const audioUrl = ref('')

const reanalyzing = computed(() =>
  tasks.hasActive('reanalyze', { id: route.params.id })
)
const retranscribing = computed(() =>
  tasks.hasActive('retranscribe', { id: route.params.id })
)

async function load() {
  loading.value = true
  try {
    const { data } = await api.get(`/analyses/${route.params.id}`)
    item.value = data
    if (data.call?.has_audio) await fetchAudio()
  } catch (e) {
    error.value = e.response?.data?.detail || 'Не удалось загрузить'
  } finally {
    loading.value = false
  }
}

async function fetchAudio() {
  try {
    const { data } = await api.get(`/analyses/${route.params.id}/audio`, {
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
  await api.delete(`/analyses/${route.params.id}`)
  router.push('/analyses')
}

async function reanalyze() {
  if (!confirm('Запустить анализ заново по текущему тексту?')) return
  const tid = route.params.id
  error.value = ''
  try {
    const data = await tasks.run(
      {
        kind: 'reanalyze',
        meta: { id: tid },
        label: `Анализ · ${item.value?.title || tid}`,
        hint: 'Выполняется повторный анализ диалога',
      },
      async () => {
        const { data } = await api.post(`/analyses/${tid}/reanalyze`)
        return data
      }
    )
    // обновим только если пользователь всё ещё на этом анализе
    if (route.params.id === tid) item.value = data
  } catch (e) {
    // тост покажет ошибку, локально тоже отметим
    if (route.params.id === tid) {
      error.value = e.response?.data?.detail || 'Не удалось выполнить анализ'
    }
  }
}

async function retranscribe() {
  if (retranscribing.value) return
  if (!confirm('Запустить повторную транскрипцию по сохранённому аудио?')) return
  const tid = route.params.id
  error.value = ''
  try {
    const data = await tasks.run(
      {
        kind: 'retranscribe',
        meta: { id: tid },
        label: `Транскрайб · ${item.value?.title || tid}`,
        hint: 'Скачиваем аудио, расшифровываем и анализируем',
      },
      async () => {
        const { data } = await api.post(`/analyses/${tid}/retranscribe`)
        return data
      }
    )
    if (route.params.id === tid) item.value = data
  } catch (e) {
    if (route.params.id === tid) {
      error.value = e.response?.data?.detail || 'Не удалось выполнить транскрипцию'
    }
  }
}

async function copyText() {
  if (!item.value?.source_text) return
  await navigator.clipboard.writeText(item.value.source_text)
  copied.value = true
  setTimeout(() => (copied.value = false), 1500)
}

function fmtDate(s) {
  if (!s) return ''
  return new Date(s).toLocaleString()
}

function scoreClass(score) {
  if (score == null) return 'empty'
  if (score >= 90) return 'good'
  if (score >= 75) return 'ok'
  if (score >= 60) return 'warn'
  return 'bad'
}

function critClass(score, max) {
  if (!max) return 'bad'
  const pct = (score / max) * 100
  if (pct >= 80) return 'good'
  if (pct >= 60) return 'ok'
  if (pct >= 40) return 'warn'
  return 'bad'
}

function gradeClass(grade) {
  if (!grade) return ''
  if (grade.startsWith('Эталон')) return 'good'
  if (grade.startsWith('Хорош')) return 'ok'
  if (grade.startsWith('Удовлет')) return 'warn'
  return 'bad'
}

const scoring = computed(() => item.value?.scoring || null)

const criteriaByCategory = computed(() => {
  const list = scoring.value?.criteria_scores || []
  const groups = []
  const seen = new Map()
  for (const c of list) {
    const key = c.category_id || 'other'
    if (!seen.has(key)) {
      const g = { id: key, name: c.category_name || 'Прочее', items: [] }
      seen.set(key, g)
      groups.push(g)
    }
    seen.get(key).items.push(c)
  }
  return groups
})

const stopFactorsTriggered = computed(
  () => (scoring.value?.stop_factors || []).filter(s => s.triggered)
)

const chatMessages = computed(() => {
  if (item.value?.kind !== 'chat' || !item.value?.source_text) return []
  const lines = item.value.source_text.split(/\r?\n/)
  const messages = []
  for (const raw of lines) {
    const line = raw.trim()
    if (!line) continue
    const m = line.match(/^([^:]+):\s*(.*)$/)
    if (m) {
      const author = m[1].trim()
      const text = m[2]
      const isOperator = author.toLowerCase() === 'менеджер' || author.toLowerCase() === 'оператор'
        || (item.value.manager && author === item.value.manager)
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
    <button class="ghost back" @click="router.push('/analyses')"><ArrowLeft :size="14" /> Назад</button>

    <div v-if="loading" class="row" style="color:var(--text-dim);gap:10px;">
      <span class="spinner"></span> Loading…
    </div>

    <div v-else-if="error" class="error-msg">{{ error }}</div>

    <template v-else-if="item">
      <div class="head">
        <div>
          <h1 class="page-title" style="margin-bottom:6px;">{{ item.title }}</h1>
          <div class="row" style="gap:8px;flex-wrap:wrap;">
            <span class="badge" :class="item.status">{{ item.status }}</span>
            <span class="badge">{{ fmtDate(item.created_at) }}</span>
            <span v-if="scoring?.sentiment" class="badge" :class="scoring.sentiment">
              {{ scoring.sentiment }}
            </span>
          </div>
        </div>
        <div class="spacer"></div>
        <div class="head-actions">
          <button
            v-if="item.call?.has_audio"
            class="ghost"
            :disabled="reanalyzing || retranscribing"
            title="Заново скачать аудио, расшифровать и проанализировать"
            @click="retranscribe"
          >
            <span v-if="retranscribing" class="row" style="gap:8px;"><span class="spinner"></span> Транскрайб…</span>
            <span v-else class="btn-inline"><RotateCcw :size="14" /> Транскрайб</span>
          </button>
          <button
            class="ghost"
            :disabled="reanalyzing || retranscribing"
            title="Запустить анализ по существующему тексту"
            @click="reanalyze"
          >
            <span v-if="reanalyzing" class="row" style="gap:8px;"><span class="spinner"></span> Анализ…</span>
            <span v-else class="btn-inline"><RotateCcw :size="14" /> Анализ</span>
          </button>
          <button class="danger btn-inline" :disabled="reanalyzing || retranscribing" @click="remove"><Trash2 :size="14" /> Удалить</button>
        </div>
      </div>

      <div v-if="item.kind === 'chat'" class="call-card card">
        <div class="call-grid">
          <div v-if="item.manager" class="call-cell">
            <div class="call-cell-label">Оператор</div>
            <div class="call-cell-value">
              <div class="op-avatar-sm">{{ item.manager[0]?.toUpperCase() }}</div>
              {{ item.manager }}
            </div>
          </div>
          <div v-if="item.chat?.channel" class="call-cell">
            <div class="call-cell-label">Канал</div>
            <div class="call-cell-value">{{ item.chat.channel }}</div>
          </div>
          <div v-if="item.chat?.client" class="call-cell">
            <div class="call-cell-label">Клиент</div>
            <div class="call-cell-value">{{ item.chat.client }}</div>
          </div>
          <div v-if="item.date" class="call-cell">
            <div class="call-cell-label">Дата</div>
            <div class="call-cell-value">{{ fmtCallDate(item.date) }}</div>
          </div>
          <div v-if="item.chat?.messages_count" class="call-cell">
            <div class="call-cell-label">Сообщений</div>
            <div class="call-cell-value mono">{{ item.chat.messages_count }}</div>
          </div>
        </div>
      </div>

      <div v-if="item.kind === 'call'" class="call-card card">
        <div class="call-grid">
          <div v-if="item.manager" class="call-cell">
            <div class="call-cell-label">Оператор</div>
            <div class="call-cell-value">
              <div class="op-avatar-sm">{{ item.manager[0]?.toUpperCase() }}</div>
              {{ item.manager }}
            </div>
          </div>
          <div v-if="item.call?.phone" class="call-cell">
            <div class="call-cell-label">Телефон</div>
            <div class="call-cell-value mono">{{ item.call.phone }}</div>
          </div>
          <div v-if="item.call?.direction" class="call-cell">
            <div class="call-cell-label">Тип</div>
            <div class="call-cell-value">{{ item.call.direction }}</div>
          </div>
          <div v-if="item.date" class="call-cell">
            <div class="call-cell-label">Дата звонка</div>
            <div class="call-cell-value">{{ fmtCallDate(item.date) }}</div>
          </div>
          <div v-if="item.duration" class="call-cell">
            <div class="call-cell-label">Длительность</div>
            <div class="call-cell-value mono">{{ fmtDuration(item.duration) }}</div>
          </div>
        </div>
        <div v-if="audioUrl" class="call-audio">
          <audio :src="audioUrl" controls preload="metadata" style="width:100%;"></audio>
        </div>
        <div v-else-if="item.call?.has_audio" class="call-audio-loading">
          <span class="spinner"></span> Загрузка записи…
        </div>
      </div>

      <div v-if="item.error" class="error-msg" style="margin-bottom:18px;">{{ item.error }}</div>

      <!-- Swiss Collection scoring -->
      <template v-if="scoring">
        <div class="oko-hero card">
          <div class="oko-hero-left">
            <div class="oko-tag">Swiss Collection by RAAF Group · Карта оценки звонка</div>
            <p class="oko-verdict">{{ scoring.meta.verdict || '—' }}</p>
            <div v-if="scoring.meta.grade" class="oko-grade" :class="gradeClass(scoring.meta.grade)">
              {{ scoring.meta.grade }}
            </div>
          </div>
          <div class="oko-score" :class="scoreClass(scoring.meta.normalized_score)">
            <svg viewBox="0 0 100 100" class="score-ring">
              <circle cx="50" cy="50" r="42" class="ring-bg" />
              <circle
                cx="50" cy="50" r="42"
                class="ring-fg"
                :stroke-dasharray="264"
                :stroke-dashoffset="264 - (264 * scoring.meta.normalized_score / 100)"
              />
            </svg>
            <div class="score-text">
              <div class="score-value">{{ scoring.meta.normalized_score }}</div>
              <div class="score-label">из 100</div>
            </div>
          </div>
        </div>

        <div class="oko-grid">
          <div class="card sw-card">
            <h2>Сильные стороны</h2>
            <ul v-if="scoring.strengths.length" class="sw-list strengths">
              <li v-for="(s, i) in scoring.strengths" :key="i">
                <span class="sw-mark"><Check :size="11" /></span><span>{{ s }}</span>
              </li>
            </ul>
            <div v-else class="empty-inline">Не выделены.</div>
          </div>
          <div class="card sw-card">
            <h2>Слабые стороны</h2>
            <ul v-if="scoring.weaknesses.length" class="sw-list weaknesses">
              <li v-for="(w, i) in scoring.weaknesses" :key="i">
                <span class="sw-mark">!</span><span>{{ w }}</span>
              </li>
            </ul>
            <div v-else class="empty-inline">Не выделены.</div>
          </div>
        </div>

        <div v-if="stopFactorsTriggered.length" class="card stop-card">
          <h2>Стоп-факторы</h2>
          <div class="stop-list">
            <div
              v-for="s in stopFactorsTriggered"
              :key="s.id"
              class="stop-item"
            >
              <div class="stop-head">
                <span class="stop-name">{{ s.name }}</span>
                <span class="stop-penalty">−{{ s.penalty }}</span>
              </div>
              <div v-if="s.comment" class="stop-comment">{{ s.comment }}</div>
            </div>
          </div>
        </div>

        <div class="card criteria-card">
          <h2>Оценка по критериям</h2>
          <div class="cat-list">
            <div
              v-for="g in criteriaByCategory"
              :key="g.id"
              class="cat-block"
            >
              <div class="cat-title">{{ g.name }}</div>
              <div class="criteria-list">
                <div
                  v-for="c in g.items"
                  :key="c.id"
                  class="crit"
                >
                  <div class="crit-head">
                    <div class="crit-name">{{ c.name }}</div>
                    <div class="crit-score" :class="critClass(c.score, c.max_score)">
                      {{ c.score }} / {{ c.max_score }}
                    </div>
                  </div>
                  <div class="crit-bar">
                    <div
                      class="crit-bar-fill"
                      :class="critClass(c.score, c.max_score)"
                      :style="{ width: (c.max_score ? (c.score / c.max_score) * 100 : 0) + '%' }"
                    ></div>
                  </div>
                  <div v-if="c.comment" class="crit-comment">{{ c.comment }}</div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div v-if="scoring.coaching_tasks.length" class="card tasks-card">
          <h2>Задачи на развитие</h2>
          <div class="tasks-grid">
            <div
              v-for="(task, i) in scoring.coaching_tasks"
              :key="i"
              class="task"
            >
              <div class="task-icon"><Target :size="16" /></div>
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

        <div v-if="item.kind === 'chat'" class="card transcript-card transcript-full">
          <div class="card-head">
            <h2>Переписка</h2>
            <button class="ghost small btn-inline" @click="copyText">
              <Check v-if="copied" :size="13" />
              {{ copied ? 'Скопировано' : 'Копировать' }}
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
            <button class="ghost small btn-inline" @click="copyText">
              <Check v-if="copied" :size="13" />
              {{ copied ? 'Скопировано' : 'Копировать' }}
            </button>
          </div>
          <div v-if="item.source_text" class="transcript">{{ item.source_text }}</div>
          <div v-else class="empty-inline">Транскрипт отсутствует.</div>
        </div>
      </template>

      <div v-else class="card" style="padding:40px 24px; text-align:center;">
        <p class="empty-inline">
          {{ item.status === 'processing' ? 'Идёт обработка…' : 'Анализ пока недоступен.' }}
        </p>
      </div>
    </template>

  </div>
</template>

<style scoped>
.back { margin-bottom: 16px; padding: 8px 14px; font-size: 13px; }
.head-actions { display: flex; gap: 8px; flex-wrap: wrap; justify-content: flex-end; }
.head-actions button { padding: 8px 14px; font-size: 13px; }

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
  box-shadow: 0 8px 22px -10px rgba(20, 184, 166, 0.55);
}

/* ===== OKO Sales Analysis ===== */

.oko-hero {
  display: flex;
  align-items: center;
  gap: 32px;
  margin-bottom: 18px;
  background:
    radial-gradient(600px 200px at 0% 0%, rgba(20, 184, 166, 0.08), transparent 70%),
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
.oko-grade {
  display: inline-block;
  margin-top: 14px;
  padding: 4px 14px;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.02em;
}
.oko-grade.good { color: var(--success); background: var(--success-soft); }
.oko-grade.ok { color: var(--brand); background: var(--brand-soft); }
.oko-grade.warn { color: var(--warn); background: var(--warn-soft); }
.oko-grade.bad { color: var(--danger); background: var(--danger-soft); }

.stop-card { margin-bottom: 18px; border-left: 4px solid var(--danger); }
.stop-list { display: flex; flex-direction: column; gap: 12px; }
.stop-item {
  padding: 12px 14px;
  background: var(--danger-soft);
  border-radius: var(--radius);
}
.stop-head {
  display: flex; justify-content: space-between; align-items: center;
  gap: 10px;
}
.stop-name { font-size: 14px; font-weight: 600; color: var(--text); }
.stop-penalty {
  font-size: 14px;
  font-weight: 800;
  color: var(--danger);
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}
.stop-comment { font-size: 13px; color: var(--text-dim); margin-top: 6px; line-height: 1.45; }

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
.cat-list { display: flex; flex-direction: column; gap: 22px; }
.cat-block { padding-top: 4px; }
.cat-title {
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  color: var(--brand);
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border);
}
.criteria-list {
  display: flex;
  flex-direction: column;
  gap: 18px;
}
.crit { padding: 4px 0; }
.crit-head {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 8px;
  gap: 12px;
}
.crit-name { font-size: 14px; font-weight: 600; flex: 1; min-width: 0; }
.crit-score {
  font-size: 13px;
  font-weight: 700;
  padding: 2px 10px;
  border-radius: 999px;
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
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
