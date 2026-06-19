<script setup>
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../api'

const route = useRoute()
const router = useRouter()
const item = ref(null)
const loading = ref(true)
const error = ref('')
const copied = ref(false)

async function load() {
  loading.value = true
  try {
    const { data } = await api.get(`/transcriptions/${route.params.id}`)
    item.value = data
  } catch (e) {
    error.value = e.response?.data?.detail || 'Failed to load'
  } finally {
    loading.value = false
  }
}

async function remove() {
  if (!confirm('Delete this transcription?')) return
  await api.delete(`/transcriptions/${route.params.id}`)
  router.push('/dashboard')
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

onMounted(load)
</script>

<template>
  <div class="container">
    <button class="ghost back" @click="router.push('/dashboard')">← Back</button>

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
        <button class="danger" @click="remove">Delete</button>
      </div>

      <div v-if="item.error" class="error-msg" style="margin-bottom:18px;">{{ item.error }}</div>

      <div class="grid">
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
</style>
