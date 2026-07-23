import { defineStore } from 'pinia'

let _seq = 0

// Глобальные уведомления. Висят в правом верхнем углу.
export const useToastStore = defineStore('toast', {
  state: () => ({
    items: [], // { id, type: 'error'|'success'|'info', title, message }
  }),

  actions: {
    push({ type = 'info', title = '', message = '', timeout = 6000 }) {
      const id = ++_seq
      this.items.push({ id, type, title, message })
      if (timeout) setTimeout(() => this.dismiss(id), timeout)
      return id
    },

    error(message, title = 'Ошибка') {
      return this.push({ type: 'error', title, message, timeout: 8000 })
    },

    success(message, title = 'Готово') {
      return this.push({ type: 'success', title, message, timeout: 4000 })
    },

    info(message, title = '') {
      return this.push({ type: 'info', title, message })
    },

    // Достаёт человекочитаемое сообщение из ошибки axios
    fromError(e, fallback = 'Не удалось выполнить запрос', title = 'Ошибка') {
      const msg = e?.response?.data?.detail || e?.message || fallback
      return this.error(typeof msg === 'string' ? msg : fallback, title)
    },

    dismiss(id) {
      this.items = this.items.filter(t => t.id !== id)
    },
  },
})
