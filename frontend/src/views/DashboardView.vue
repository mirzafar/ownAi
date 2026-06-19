<script setup>
import { onMounted, ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api'

const router = useRouter()
const items = ref([])
const loading = ref(true)
const error = ref('')

const stats = computed(() => {
  const done = items.value.filter(i => i.status === 'done').length
  const failed = items.value.filter(i => i.status === 'failed').length
  const words = items.value.reduce((acc, i) => acc + (i.text?.split(/\s+/).filter(Boolean).length || 0), 0)
  return { total: items.value.length, done, failed, words }
})

async function load() {
  loading.value = true
  error.value = ''
  try {
    const { data } = await api.get('/transcriptions')
    items.value = data
  } catch (e) {
    error.value = e.response?.data?.detail || 'Failed to load transcriptions'
  } finally {
    loading.value = false
  }
}

async function remove(id) {
  if (!confirm('Delete this transcription?')) return
  await api.delete(`/transcriptions/${id}`)
  items.value = items.value.filter(i => i.id !== id)
}

function fmtDate(s) {
  if (!s) return ''
  const d = new Date(s)
  return d.toLocaleString()
}

function preview(text) {
  if (!text) return ''
  return text.length > 180 ? text.slice(0, 180) + '…' : text
}

onMounted(load)
</script>

<template>
  <div class="container">
    <div class="row" style="margin-bottom:28px;">
      <div>
        <h1 class="page-title">Your transcriptions</h1>
        <p class="page-subtitle">All audio you've processed with ownAi.</p>
      </div>
      <div class="spacer"></div>
      <button class="primary" @click="router.push('/upload')">+ New transcription</button>
    </div>

    <div class="stats">
      <div class="stat card">
        <div class="stat-label">Total</div>
        <div class="stat-value">{{ stats.total }}</div>
      </div>
      <div class="stat card">
        <div class="stat-label">Completed</div>
        <div class="stat-value">{{ stats.done }}</div>
      </div>
      <div class="stat card">
        <div class="stat-label">Failed</div>
        <div class="stat-value">{{ stats.failed }}</div>
      </div>
      <div class="stat card">
        <div class="stat-label">Words transcribed</div>
        <div class="stat-value">{{ stats.words.toLocaleString() }}</div>
      </div>
    </div>

    <div v-if="error" class="error-msg" style="margin-bottom:16px;">{{ error }}</div>

    <div v-if="loading" class="loading">
      <span class="spinner"></span> Loading…
    </div>

    <div v-else-if="items.length === 0" class="empty card">
      <div class="empty-icon">🎧</div>
      <h3>No transcriptions yet</h3>
      <p>Upload your first audio file to start.</p>
      <button class="primary" @click="router.push('/upload')">Upload audio</button>
    </div>

    <div v-else class="list">
      <div
        v-for="item in items"
        :key="item.id"
        class="item card"
        @click="router.push(`/t/${item.id}`)"
      >
        <div class="item-head">
          <div class="item-title">
            <span class="dot"></span>
            {{ item.filename }}
          </div>
          <span class="badge" :class="item.status">{{ item.status }}</span>
        </div>

        <div class="item-meta">
          <span>{{ fmtDate(item.created_at) }}</span>
          <span v-if="item.analysis?.language">· {{ item.analysis.language.toUpperCase() }}</span>
          <span v-if="item.analysis?.sentiment">
            · <span class="badge" :class="item.analysis.sentiment">{{ item.analysis.sentiment }}</span>
          </span>
        </div>

        <p class="item-summary">{{ item.analysis?.summary || preview(item.text) || 'Processing…' }}</p>

        <div class="topics" v-if="item.analysis?.topics?.length">
          <span class="topic" v-for="t in item.analysis.topics.slice(0,5)" :key="t">#{{ t }}</span>
        </div>

        <div class="item-actions" @click.stop>
          <button class="ghost" @click="router.push(`/t/${item.id}`)">Open</button>
          <button class="danger" @click="remove(item.id)">Delete</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14px;
  margin-bottom: 28px;
}
.stat { padding: 18px 20px; }
.stat-label { font-size: 12px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.08em; }
.stat-value {
  font-size: 28px;
  font-weight: 800;
  letter-spacing: -0.02em;
  margin-top: 4px;
  background: var(--brand-grad);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}

.loading {
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--text-dim);
  padding: 20px 0;
}

.empty {
  text-align: center;
  padding: 60px 30px;
}
.empty-icon { font-size: 48px; margin-bottom: 12px; }
.empty h3 { margin: 0 0 6px; font-size: 20px; }
.empty p { color: var(--text-dim); margin: 0 0 20px; }

.list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: 18px;
}
.item {
  cursor: pointer;
  transition: transform 0.15s, border-color 0.2s, box-shadow 0.2s;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.item:hover {
  transform: translateY(-2px);
  border-color: #cfd6df;
  box-shadow: 0 18px 40px -20px rgba(16, 24, 40, 0.18);
}
.item-head {
  display: flex; justify-content: space-between; align-items: center; gap: 10px;
}
.item-title {
  font-weight: 600;
  font-size: 15px;
  display: flex; align-items: center; gap: 8px;
  overflow: hidden; white-space: nowrap; text-overflow: ellipsis;
}
.dot {
  width: 8px; height: 8px; border-radius: 50%;
  background: var(--brand-grad);
}
.item-meta {
  font-size: 12px;
  color: var(--text-muted);
  display: flex; gap: 6px; flex-wrap: wrap; align-items: center;
}
.item-summary {
  font-size: 14px;
  color: var(--text-dim);
  line-height: 1.55;
  margin: 0;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.topics {
  display: flex; flex-wrap: wrap; gap: 6px;
}
.topic {
  font-size: 11px;
  color: var(--brand);
  background: var(--brand-soft);
  border: 1px solid #cce2ff;
  padding: 3px 9px;
  border-radius: 999px;
  font-weight: 500;
}
.item-actions {
  display: flex; gap: 8px; margin-top: auto;
}
.item-actions button { font-size: 12px; padding: 8px 12px; }

@media (max-width: 900px) {
  .stats { grid-template-columns: repeat(2, 1fr); }
}
</style>
