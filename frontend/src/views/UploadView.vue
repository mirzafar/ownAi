<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api'
import ProcessOverlay from '../components/ProcessOverlay.vue'

const router = useRouter()
const file = ref(null)
const dragging = ref(false)
const loading = ref(false)
const progress = ref(0)
const error = ref('')
const inputRef = ref(null)
const language = ref('ru')

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

async function upload() {
  if (!file.value) return
  error.value = ''
  loading.value = true
  progress.value = 0
  stageIndex.value = 0
  const form = new FormData()
  form.append('file', file.value)
  form.append('language', language.value)
  try {
    const { data } = await api.post('/transcriptions', form, {
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
    router.push(`/t/${data.id}`)
  } catch (e) {
    error.value = e.response?.data?.detail || 'Upload failed'
  } finally {
    clearAnalyzeTimer()
    loading.value = false
    stageIndex.value = 0
  }
}

function reset() {
  file.value = null
  progress.value = 0
  if (inputRef.value) inputRef.value.value = ''
}
</script>

<template>
  <div class="container" style="max-width:720px;">
    <h1 class="page-title">Загрузка аудио</h1>
    <p class="page-subtitle">Перетащите файл или выберите с диска — расшифруем и сделаем анализ.</p>

    <div
      class="dropzone card"
      :class="{ dragging, has: !!file }"
      @dragover.prevent="dragging = true"
      @dragleave.prevent="dragging = false"
      @drop.prevent="onDrop"
      @click="!file && pick()"
    >
      <input ref="inputRef" type="file" accept="audio/*,video/*" @change="onFile" hidden />

      <div v-if="!file" class="dz-empty">
        <div class="dz-icon">⬆️</div>
        <h3>Перетащите файл сюда</h3>
        <p>или нажмите чтобы выбрать</p>
        <small>MP3, WAV, M4A, OGG, WEBM, MP4 · до 25 МБ</small>
      </div>

      <div v-else class="dz-file">
        <div class="file-icon">🎵</div>
        <div class="file-info">
          <div class="file-name">{{ file.name }}</div>
          <div class="file-meta">{{ fileSize }} · {{ file.type || 'audio' }}</div>
        </div>
        <button class="ghost" @click.stop="reset" :disabled="loading">Убрать</button>
      </div>
    </div>

    <div class="lang-row">
      <label class="lang-label">Язык аудио</label>
      <div class="lang-options" role="radiogroup" aria-label="Язык аудио">
        <button
          type="button"
          class="lang-chip"
          :class="{ active: language === 'ru' }"
          :disabled="loading"
          @click="language = 'ru'"
        >Русский</button>
        <button
          type="button"
          class="lang-chip"
          :class="{ active: language === 'kk' }"
          :disabled="loading"
          @click="language = 'kk'"
        >Қазақша</button>
      </div>
    </div>

    <div v-if="error" class="error-msg" style="margin-top:16px;">{{ error }}</div>

    <ProcessOverlay
      :visible="loading"
      title="Обработка записи"
      :stages="STAGES"
      :active-index="stageIndex"
      :progress="overlayProgress"
    />

    <div class="actions">
      <button class="ghost" @click="router.push('/analyses')" :disabled="loading">Отмена</button>
      <button class="primary" :disabled="!file || loading" @click="upload">
        <span v-if="!loading">Анализировать</span>
        <span v-else class="row" style="gap:8px;"><span class="spinner"></span> Обработка…</span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.dropzone {
  margin-top: 8px;
  border: 2px dashed var(--border-strong);
  background: var(--surface);
  padding: 40px 24px;
  text-align: center;
  transition: background 0.2s, border-color 0.2s, transform 0.15s;
  cursor: pointer;
}
.dropzone.dragging {
  border-color: var(--brand);
  background: var(--brand-soft-2);
  transform: scale(1.01);
}
.dropzone.has { cursor: default; padding: 24px; }

.dz-empty .dz-icon {
  font-size: 42px;
  margin-bottom: 10px;
}
.dz-empty h3 { margin: 4px 0; font-size: 18px; font-weight: 700; }
.dz-empty p { margin: 0; color: var(--text-dim); font-size: 14px; }
.dz-empty small { display:block; margin-top: 14px; color: var(--text-muted); font-size: 12px; }

.dz-file { display: flex; align-items: center; gap: 14px; text-align: left; }
.file-icon { font-size: 36px; }
.file-info { flex: 1; min-width: 0; }
.file-name {
  font-weight: 600;
  font-size: 15px;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.file-meta { font-size: 12px; color: var(--text-muted); margin-top: 2px; }

.progress-wrap {
  margin-top: 18px;
  padding: 16px;
  border: 1px solid var(--border);
  border-radius: 14px;
  background: var(--surface);
}
.progress-bar {
  height: 8px;
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
.progress-text {
  margin-top: 10px;
  font-size: 13px;
  color: var(--text-dim);
  display: flex; align-items: center; gap: 8px;
}

.actions {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
  margin-top: 22px;
}

.lang-row {
  margin-top: 18px;
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
}
.lang-label {
  font-size: 13px;
  color: var(--text-dim);
  font-weight: 600;
}
.lang-options { display: flex; gap: 8px; }
.lang-chip {
  border: 1px solid var(--border-strong);
  background: var(--surface);
  color: var(--text);
  padding: 8px 14px;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: background .15s, border-color .15s, color .15s;
}
.lang-chip:hover:not(:disabled) { border-color: var(--brand); }
.lang-chip.active {
  background: var(--brand-soft-2);
  border-color: var(--brand);
  color: var(--brand);
}
.lang-chip:disabled { opacity: .6; cursor: not-allowed; }
</style>
