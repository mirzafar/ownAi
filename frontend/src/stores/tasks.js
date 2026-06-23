import { defineStore } from 'pinia'

let _seq = 0

// Глобальные фоновые задачи. UI продолжает работать, тосты висят справа снизу.
export const useTasksStore = defineStore('tasks', {
  state: () => ({
    items: [], // { id, label, hint?, status: 'running'|'done'|'error', error?, startedAt }
  }),

  actions: {
    /**
     * Запускает асинхронную работу в фоне.
     * Возвращает Promise с результатом fn, чтобы вызвавший мог обновить локальный стейт.
     */
    async run({ label, hint = '', kind = '', meta = {} }, fn) {
      const id = ++_seq
      const task = {
        id,
        label,
        hint,
        kind,
        meta,
        status: 'running',
        error: '',
        startedAt: Date.now(),
      }
      this.items.push(task)
      try {
        const result = await fn()
        task.status = 'done'
        // авто-скрытие через 4с
        setTimeout(() => this.dismiss(id), 4000)
        return result
      } catch (e) {
        task.status = 'error'
        task.error = e?.response?.data?.detail || e?.message || 'Не удалось выполнить'
        // ошибки висят дольше, можно закрыть руками
        setTimeout(() => this.dismiss(id), 8000)
        throw e
      }
    },

    dismiss(id) {
      this.items = this.items.filter(t => t.id !== id)
    },

    hasActive(kind, metaMatch = null) {
      return this.items.some(t => {
        if (t.status !== 'running') return false
        if (kind && t.kind !== kind) return false
        if (metaMatch) {
          for (const k of Object.keys(metaMatch)) {
            if (t.meta?.[k] !== metaMatch[k]) return false
          }
        }
        return true
      })
    },
  },
})
