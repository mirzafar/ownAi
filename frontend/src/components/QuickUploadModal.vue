<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api'
import ProcessOverlay from './ProcessOverlay.vue'
import { UploadCloud, AudioLines, X } from 'lucide-vue-next'

const emit = defineEmits(['close'])
const router = useRouter()

const file = ref(null)
const dragging = ref(false)
const loading = ref(false)
const progress = ref(0)
const error = ref('')
const inputRef = ref(null)

const STAGES = ['Загрузка файла', 'Расшифровка аудио', 'Анализ диалога']
const stageIndex = ref(0)
const overlayProgress = computed(() => (stageIndex.value === 0 ? progress.value : null))
let analyzeTimer = null

function clearAnalyzeTimer() {
  if (analyzeTimer) {
    clearTimeout(analyzeTimer)
    analyzeTimer = null
  }
}

const fileSize = computed(() => {
  if (!file.value) return ''
  const kb = file.value.size / 1024
  if (kb < 1024) return `${kb.toFixed(0)} KB`
  return `${(kb / 1024).toFixed(2)} MB`
})

function pick() { inputRef.value?.click() }

function onFile(e) {
  const f = e.target.files?.[0]
  if (f) file.value = f
}

function onDrop(e) {
  dragging.value = false
  const f = e.dataTransfer?.files?.[0]
  if (f) file.value = f
}

function reset() {
  file.value = null
  progress.value = 0
  if (inputRef.value) inputRef.value.value = ''
}

function close() {
  if (loading.value) return
  emit('close')
}

async function upload() {
  if (!file.value) return
  error.value = ''
  loading.value = true
  progress.value = 0
  stageIndex.value = 0
  const form = new FormData()
  form.append('file', file.value)
  try {
    const { data } = await api.post('/analyses/upload', form, {
      onUploadProgress: (e) => {
        if (e.total) {
          progress.value = Math.round((e.loaded / e.total) * 100)
          if (progress.value >= 100 && stageIndex.value === 0) {
            stageIndex.value = 1
            analyzeTimer = setTimeout(() => {
              if (stageIndex.value === 1) stageIndex.value = 2
            }, 12000)
          }
        }
      }
    })
    clearAnalyzeTimer()
    stageIndex.value = STAGES.length
    emit('close')
    router.push(`/t/${data.id}`)
  } catch (e) {
    error.value = e.response?.data?.detail || 'Не удалось загрузить файл'
  } finally {
    clearAnalyzeTimer()
    loading.value = false
    stageIndex.value = 0
  }
}
</script>

<template>
  <div class="overlay" @click.self="close">
    <div class="modal card">
      <div class="modal-head">
        <h2 class="modal-title">Загрузка аудио</h2>
        <button class="ghost icon-btn" @click="close" :disabled="loading"><X :size="14" /></button>
      </div>
      <p class="modal-sub">Перетащите файл или выберите с диска — расшифруем и сделаем анализ.</p>

      <div
        class="dropzone"
        :class="{ dragging, has: !!file }"
        @dragover.prevent="dragging = true"
        @dragleave.prevent="dragging = false"
        @drop.prevent="onDrop"
        @click="!file && pick()"
      >
        <input ref="inputRef" type="file" accept="audio/*,video/*" @change="onFile" hidden />

        <div v-if="!file" class="dz-empty">
          <div class="dz-icon"><UploadCloud :size="28" /></div>
          <div class="dz-title">Перетащите файл сюда</div>
          <div class="dz-sub">или нажмите чтобы выбрать</div>
          <small>MP3, WAV, M4A, OGG, WEBM, MP4 · до 25 МБ</small>
        </div>

        <div v-else class="dz-file">
          <div class="file-icon"><AudioLines :size="18" /></div>
          <div class="file-info">
            <div class="file-name">{{ file.name }}</div>
            <div class="file-meta">{{ fileSize }}</div>
          </div>
          <button class="ghost" @click.stop="reset" :disabled="loading">Убрать</button>
        </div>
      </div>

      <div v-if="error" class="error-msg" style="margin-top:14px;">{{ error }}</div>

      <ProcessOverlay
        :visible="loading"
        title="Обработка записи"
        :stages="STAGES"
        :active-index="stageIndex"
        :progress="overlayProgress"
      />

      <div class="modal-actions">
        <button class="ghost" @click="close" :disabled="loading">Отмена</button>
        <button class="primary" :disabled="!file || loading" @click="upload">
          <span v-if="!loading">Анализировать</span>
          <span v-else class="row" style="gap:8px;"><span class="spinner"></span> Обработка…</span>
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.overlay {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.40);
  backdrop-filter: blur(4px);
  z-index: 200;
  display: grid;
  place-items: center;
  padding: 24px;
}
.modal {
  width: 100%;
  max-width: 540px;
  padding: 28px;
  border-radius: var(--radius-xl);
  animation: pop .18s ease;
}
@keyframes pop {
  from { transform: scale(.97); opacity: 0; }
  to { transform: scale(1); opacity: 1; }
}
.modal-head { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
.modal-title { font-size: 18px; font-weight: 700; margin: 0; letter-spacing: -0.01em; }
.icon-btn {
  width: 32px; height: 32px;
  padding: 0;
  display: grid; place-items: center;
  border-radius: 10px;
}
.modal-sub { color: var(--text-dim); font-size: 14px; margin: 6px 0 18px; }

.dropzone {
  border: 2px dashed var(--border-strong);
  background: var(--surface-2);
  padding: 28px 20px;
  text-align: center;
  border-radius: 14px;
  cursor: pointer;
  transition: background .15s, border-color .15s, transform .12s;
}
.dropzone.dragging { border-color: var(--brand); background: var(--brand-soft); }
.dropzone.has { cursor: default; padding: 18px; }

.dz-empty .dz-icon {
  width: 52px; height: 52px;
  border-radius: 14px;
  background: var(--brand-soft);
  color: var(--brand-hover);
  display: grid; place-items: center;
  margin: 0 auto 8px;
}
.dz-title { font-weight: 600; font-size: 15px; }
.dz-sub { color: var(--text-dim); font-size: 13px; }
.dz-empty small { display: block; margin-top: 10px; color: var(--text-muted); font-size: 12px; }

.dz-file { display: flex; align-items: center; gap: 12px; text-align: left; }
.file-icon {
  width: 38px; height: 38px;
  border-radius: 10px;
  background: var(--brand-grad);
  color: #fff;
  display: grid; place-items: center;
  flex-shrink: 0;
}
.file-info { flex: 1; min-width: 0; }
.file-name { font-weight: 600; font-size: 14px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.file-meta { font-size: 12px; color: var(--text-muted); margin-top: 2px; }

.progress-wrap {
  margin-top: 14px;
  padding: 14px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--surface);
}
.progress-bar {
  height: 6px;
  width: 100%;
  background: var(--surface-3);
  border-radius: 999px;
  overflow: hidden;
}
.progress-fill {
  height: 100%;
  background: var(--brand-grad);
  transition: width 0.2s ease;
}
.progress-text { margin-top: 8px; font-size: 13px; color: var(--text-dim); display: flex; align-items: center; gap: 8px; }

.modal-actions { display: flex; gap: 10px; justify-content: flex-end; margin-top: 20px; }
</style>
