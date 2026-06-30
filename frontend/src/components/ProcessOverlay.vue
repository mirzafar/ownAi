<script setup>
import { computed } from 'vue'
import { Check } from 'lucide-vue-next'

const props = defineProps({
  visible: { type: Boolean, default: false },
  title: { type: String, default: 'Обработка…' },
  stages: { type: Array, default: () => [] },
  activeIndex: { type: Number, default: 0 },
  progress: { type: Number, default: null },
})

const showBar = computed(() => props.progress !== null && props.progress >= 0)
</script>

<template>
  <Transition name="proc-fade">
    <div v-if="visible" class="proc-overlay" role="dialog" aria-modal="true">
      <div class="proc-card card">
        <div class="proc-spinner-wrap">
          <div class="proc-spinner"></div>
        </div>
        <div class="proc-title">{{ title }}</div>

        <div v-if="stages.length" class="proc-steps">
          <div
            v-for="(s, i) in stages"
            :key="i"
            class="proc-step"
            :class="{
              done: i < activeIndex,
              active: i === activeIndex,
              pending: i > activeIndex,
            }"
          >
            <div class="proc-step-mark">
              <Check v-if="i < activeIndex" :size="12" />
              <span v-else-if="i === activeIndex" class="proc-mini-spinner"></span>
              <span v-else>{{ i + 1 }}</span>
            </div>
            <div class="proc-step-label">{{ s }}</div>
          </div>
        </div>

        <div v-if="showBar" class="proc-bar">
          <div class="proc-bar-fill" :style="{ width: Math.min(100, Math.max(0, progress)) + '%' }"></div>
        </div>
        <div v-if="showBar" class="proc-bar-text">{{ Math.round(progress) }}%</div>

        <div class="proc-hint">Не закрывайте вкладку до завершения.</div>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.proc-overlay {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.55);
  backdrop-filter: blur(6px);
  z-index: 300;
  display: grid;
  place-items: center;
  padding: 24px;
}
.proc-card {
  width: 100%;
  max-width: 440px;
  padding: 32px 28px 24px;
  text-align: center;
  border-radius: var(--radius-xl);
  animation: proc-pop .2s ease;
}
@keyframes proc-pop {
  from { transform: scale(.97); opacity: 0; }
  to { transform: scale(1); opacity: 1; }
}
.proc-fade-enter-active, .proc-fade-leave-active { transition: opacity .18s ease; }
.proc-fade-enter-from, .proc-fade-leave-to { opacity: 0; }

.proc-spinner-wrap { display: grid; place-items: center; margin-bottom: 18px; }
.proc-spinner {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  border: 4px solid var(--surface-3);
  border-top-color: var(--brand);
  animation: proc-spin 0.9s linear infinite;
}
@keyframes proc-spin { to { transform: rotate(360deg); } }

.proc-title {
  font-size: 17px;
  font-weight: 700;
  margin-bottom: 18px;
  color: var(--text);
}

.proc-steps {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin: 6px auto 16px;
  text-align: left;
  max-width: 280px;
}
.proc-step {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 12px;
  border-radius: 10px;
  transition: background .2s;
}
.proc-step.active { background: var(--brand-soft); }
.proc-step.done .proc-step-label { color: var(--text-dim); }
.proc-step.pending .proc-step-label { color: var(--text-muted); }
.proc-step-mark {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  font-size: 12px;
  font-weight: 800;
  background: var(--surface-3);
  color: var(--text-muted);
  flex-shrink: 0;
}
.proc-step.done .proc-step-mark { background: var(--success-soft); color: var(--success); }
.proc-step.active .proc-step-mark { background: var(--brand); color: #fff; }
.proc-step-label { font-size: 14px; font-weight: 600; color: var(--text); }

.proc-mini-spinner {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  border: 2px solid rgba(255, 255, 255, 0.35);
  border-top-color: #fff;
  animation: proc-spin 0.7s linear infinite;
  display: inline-block;
}

.proc-bar {
  margin: 6px auto 4px;
  width: 100%;
  max-width: 280px;
  height: 6px;
  background: var(--surface-3);
  border-radius: 999px;
  overflow: hidden;
}
.proc-bar-fill {
  height: 100%;
  background: var(--brand-grad);
  transition: width 0.2s ease;
}
.proc-bar-text {
  font-size: 12px;
  color: var(--text-dim);
  margin-bottom: 10px;
  font-variant-numeric: tabular-nums;
}

.proc-hint {
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 6px;
}
</style>
