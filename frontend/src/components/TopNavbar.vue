<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()

const pageTitle = computed(() => {
  const m = route.meta?.title
  if (m) return m
  const map = {
    '/dashboard': 'Dashboard',
    '/calls': 'Звонки',
    '/chats': 'Чаты',
    '/analyses': 'Анализы',
    '/operators': 'Операторы',
    '/leads': 'Лиды',
    '/users': 'Пользователи',
    '/profile': 'Профиль',
    '/upload': 'Загрузка',
  }
  for (const k of Object.keys(map)) {
    if (route.path === k || route.path.startsWith(k + '/')) return map[k]
  }
  return ''
})
</script>

<template>
  <header class="topbar">
    <div class="topbar-inner">
      <h1 class="topbar-title">{{ pageTitle }}</h1>
    </div>
  </header>
</template>

<style scoped>
.topbar {
  position: sticky;
  top: 0;
  z-index: 40;
  background: rgba(248, 249, 250, 0.85);
  backdrop-filter: saturate(180%) blur(14px);
  -webkit-backdrop-filter: saturate(180%) blur(14px);
  border-bottom: 1px solid var(--border);
}
.topbar-inner {
  display: flex;
  align-items: center;
  padding: 14px 28px;
  height: var(--topbar-h);
}
.topbar-title {
  font-size: 20px;
  font-weight: 700;
  letter-spacing: -0.02em;
  margin: 0;
  color: var(--text);
}

@media (max-width: 900px) {
  .topbar-inner { padding: 10px 16px; }
  .topbar-title { font-size: 16px; }
}
@media (max-width: 640px) {
  .topbar { display: none; }
}
</style>
