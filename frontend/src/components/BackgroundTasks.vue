<script setup>
import { useTasksStore } from '../stores/tasks'

const tasks = useTasksStore()
</script>

<template>
  <div class="bg-tasks" v-if="tasks.items.length">
    <TransitionGroup name="bgt">
      <div
        v-for="t in tasks.items"
        :key="t.id"
        class="bg-toast"
        :class="t.status"
      >
        <div class="bg-icon">
          <span v-if="t.status === 'running'" class="bg-spinner"></span>
          <span v-else-if="t.status === 'done'">✓</span>
          <span v-else>!</span>
        </div>
        <div class="bg-body">
          <div class="bg-title">{{ t.label }}</div>
          <div class="bg-hint">
            <template v-if="t.status === 'running'">{{ t.hint || 'Выполняется в фоне…' }}</template>
            <template v-else-if="t.status === 'done'">Готово</template>
            <template v-else>{{ t.error }}</template>
          </div>
        </div>
        <button class="bg-close" @click="tasks.dismiss(t.id)" title="Скрыть">✕</button>
      </div>
    </TransitionGroup>
  </div>
</template>

<style scoped>
.bg-tasks {
  position: fixed;
  right: 18px;
  bottom: 18px;
  z-index: 250;
  display: flex;
  flex-direction: column;
  gap: 10px;
  pointer-events: none;
  max-width: 340px;
}
.bg-toast {
  pointer-events: auto;
  display: flex;
  align-items: center;
  gap: 12px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-left: 3px solid var(--brand);
  border-radius: 12px;
  padding: 10px 12px;
  box-shadow: var(--shadow-lg);
  min-width: 260px;
}
.bg-toast.done { border-left-color: var(--success); }
.bg-toast.error { border-left-color: var(--danger); }

.bg-icon {
  width: 28px; height: 28px;
  border-radius: 50%;
  display: grid; place-items: center;
  flex-shrink: 0;
  background: var(--brand-soft);
  color: var(--brand);
  font-weight: 800;
  font-size: 14px;
}
.bg-toast.done .bg-icon { background: var(--success-soft); color: var(--success); }
.bg-toast.error .bg-icon { background: var(--danger-soft); color: var(--danger); }

.bg-spinner {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  border: 2px solid var(--surface-3);
  border-top-color: var(--brand);
  animation: bg-spin 0.85s linear infinite;
  display: inline-block;
}
@keyframes bg-spin { to { transform: rotate(360deg); } }

.bg-body { flex: 1; min-width: 0; }
.bg-title {
  font-weight: 700;
  font-size: 13px;
  color: var(--text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.bg-hint {
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 2px;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.bg-close {
  background: transparent;
  border: none;
  color: var(--text-muted);
  font-size: 12px;
  padding: 4px 6px;
  box-shadow: none;
  cursor: pointer;
  border-radius: 6px;
}
.bg-close:hover { background: var(--surface-2); color: var(--text); }

.bgt-enter-active, .bgt-leave-active {
  transition: transform .22s ease, opacity .22s ease;
}
.bgt-enter-from { opacity: 0; transform: translateY(10px); }
.bgt-leave-to { opacity: 0; transform: translateX(10px); }

@media (max-width: 600px) {
  .bg-tasks { right: 10px; left: 10px; bottom: 10px; max-width: none; }
  .bg-toast { min-width: 0; }
}
</style>
