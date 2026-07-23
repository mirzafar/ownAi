<script setup>
import { useToastStore } from '../stores/toast'
import { AlertTriangle, CheckCircle2, Info, X } from 'lucide-vue-next'

const toast = useToastStore()

const icons = { error: AlertTriangle, success: CheckCircle2, info: Info }
</script>

<template>
  <div class="toast-host" v-if="toast.items.length">
    <TransitionGroup name="toast">
      <div
        v-for="t in toast.items"
        :key="t.id"
        class="toast"
        :class="t.type"
      >
        <div class="toast-icon">
          <component :is="icons[t.type] || icons.info" :size="16" />
        </div>
        <div class="toast-body">
          <div class="toast-title" v-if="t.title">{{ t.title }}</div>
          <div class="toast-msg">{{ t.message }}</div>
        </div>
        <button class="toast-close" @click="toast.dismiss(t.id)" title="Закрыть">
          <X :size="13" />
        </button>
      </div>
    </TransitionGroup>
  </div>
</template>

<style scoped>
.toast-host {
  position: fixed;
  right: 18px;
  top: 18px;
  z-index: 400;
  display: flex;
  flex-direction: column;
  gap: 10px;
  pointer-events: none;
  max-width: 360px;
}
.toast {
  pointer-events: auto;
  display: flex;
  align-items: flex-start;
  gap: 12px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-left: 3px solid var(--brand);
  border-radius: 12px;
  padding: 12px 12px;
  box-shadow: var(--shadow-lg);
  min-width: 280px;
}
.toast.error { border-left-color: var(--danger); }
.toast.success { border-left-color: var(--success); }

.toast-icon {
  width: 30px; height: 30px;
  border-radius: 8px;
  display: grid; place-items: center;
  flex-shrink: 0;
  background: var(--brand-soft);
  color: var(--brand-hover);
}
.toast.error .toast-icon { background: var(--danger-soft); color: var(--danger); }
.toast.success .toast-icon { background: var(--success-soft); color: var(--success); }

.toast-body { flex: 1; min-width: 0; padding-top: 1px; }
.toast-title {
  font-weight: 700;
  font-size: 13px;
  color: var(--text);
}
.toast-msg {
  font-size: 12.5px;
  color: var(--text-muted);
  margin-top: 2px;
  line-height: 1.4;
  word-break: break-word;
}

.toast-close {
  background: transparent;
  border: none;
  color: var(--text-muted);
  padding: 4px 6px;
  box-shadow: none;
  cursor: pointer;
  border-radius: 6px;
  flex-shrink: 0;
}
.toast-close:hover { background: var(--surface-2); color: var(--text); }

.toast-enter-active, .toast-leave-active {
  transition: transform .22s ease, opacity .22s ease;
}
.toast-enter-from { opacity: 0; transform: translateX(20px); }
.toast-leave-to { opacity: 0; transform: translateX(20px); }

@media (max-width: 600px) {
  .toast-host { right: 10px; left: 10px; top: 10px; max-width: none; }
  .toast { min-width: 0; }
}
</style>
