<script setup>
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import QuickUploadModal from './QuickUploadModal.vue'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

const userMenuOpen = ref(false)
const uploadOpen = ref(false)

function logout() {
  auth.logout()
  router.push('/login')
}

function go(path) {
  userMenuOpen.value = false
  router.push(path)
}

function isActive(prefix) {
  return route.path === prefix || route.path.startsWith(prefix + '/')
}
</script>

<template>
  <aside class="sidebar">
    <router-link to="/dashboard" class="brand">
      <span class="brand-icon">🎙️</span>
      <span class="brand-name">ownAi</span>
    </router-link>

    <button class="quick-upload" @click="uploadOpen = true">
      <span class="qu-plus">＋</span>
      <span>Загрузить аудио</span>
    </button>

    <nav class="nav">
      <router-link to="/dashboard" class="nav-link" :class="{ active: isActive('/dashboard') }">
        <span class="ico">▦</span><span>Dashboard</span>
      </router-link>
      <router-link to="/calls" class="nav-link" :class="{ active: isActive('/calls') }">
        <span class="ico">☎</span><span>Звонки</span>
      </router-link>
      <router-link to="/chats" class="nav-link" :class="{ active: isActive('/chats') }">
        <span class="ico">💬</span><span>Чаты</span>
        <span class="soon">скоро</span>
      </router-link>
      <router-link to="/analyses" class="nav-link" :class="{ active: isActive('/analyses') || isActive('/t') }">
        <span class="ico">✦</span><span>Анализы</span>
      </router-link>
      <router-link to="/operators" class="nav-link" :class="{ active: isActive('/operators') }">
        <span class="ico">🎧</span><span>Операторы</span>
      </router-link>
      <router-link to="/leads" class="nav-link" :class="{ active: isActive('/leads') }">
        <span class="ico">📋</span><span>Лиды</span>
      </router-link>
      <router-link
        v-if="auth.user?.is_admin"
        to="/users"
        class="nav-link"
        :class="{ active: isActive('/users') }"
      >
        <span class="ico">👥</span><span>Пользователи</span>
      </router-link>
    </nav>

    <div class="sidebar-foot">
      <div class="user" :class="{ open: userMenuOpen }" @click="userMenuOpen = !userMenuOpen">
        <div class="avatar">{{ auth.user?.name?.[0]?.toUpperCase() || '?' }}</div>
        <div class="user-text">
          <div class="user-name">{{ auth.user?.name }}</div>
          <div class="user-login">@{{ auth.user?.login }}</div>
        </div>
        <span class="chev">⌃</span>

        <div v-if="userMenuOpen" class="user-menu" @click.stop>
          <button class="menu-item" @click="go('/profile')">
            <span class="mi-ico">👤</span>Профиль
          </button>
          <div class="menu-sep"></div>
          <button class="menu-item danger" @click="logout">
            <span class="mi-ico">⎋</span>Выйти
          </button>
        </div>
      </div>
    </div>
  </aside>

  <QuickUploadModal v-if="uploadOpen" @close="uploadOpen = false" />
</template>

<style scoped>
.sidebar {
  position: fixed;
  top: 0; left: 0; bottom: 0;
  width: 240px;
  padding: 22px 16px;
  background: rgba(255, 255, 255, 0.9);
  backdrop-filter: saturate(180%) blur(20px);
  -webkit-backdrop-filter: saturate(180%) blur(20px);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  gap: 18px;
  z-index: 50;
}

.brand {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  color: var(--text);
  font-weight: 800;
  font-size: 18px;
  letter-spacing: -0.02em;
  padding: 4px 8px;
}
.brand:hover { text-decoration: none; }
.brand-icon { font-size: 22px; filter: drop-shadow(0 4px 14px rgba(3, 129, 254, 0.3)); }
.brand-name {
  background: var(--brand-grad);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}

.quick-upload {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 12px 14px;
  border-radius: 12px;
  background: var(--brand-grad);
  color: #fff;
  border: 1px solid transparent;
  font-weight: 600;
  font-size: 14px;
  box-shadow: 0 8px 22px -10px rgba(3, 129, 254, 0.55);
}
.quick-upload:hover { filter: brightness(1.04); }
.qu-plus { font-size: 18px; line-height: 1; }

.nav {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.nav-link {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border-radius: 10px;
  color: var(--text-dim);
  font-size: 14px;
  font-weight: 500;
}
.nav-link:hover { color: var(--text); background: var(--surface-2); text-decoration: none; }
.nav-link.active {
  color: var(--text);
  background: var(--surface-3);
  font-weight: 600;
}
.ico {
  width: 22px;
  display: inline-grid;
  place-items: center;
  font-size: 14px;
  color: var(--brand);
}
.nav-link.active .ico { color: var(--text); }
.soon {
  margin-left: auto;
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--text-muted);
  background: var(--surface-3);
  padding: 2px 7px;
  border-radius: 999px;
}

.sidebar-foot {
  margin-top: auto;
  position: relative;
}
.user {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 8px;
  border-radius: 12px;
  cursor: pointer;
  position: relative;
}
.user:hover { background: var(--surface-2); }
.user.open { background: var(--surface-2); }
.avatar {
  width: 34px; height: 34px;
  border-radius: 50%;
  background: var(--brand-grad);
  color: #fff;
  display: grid; place-items: center;
  font-weight: 700; font-size: 13px;
  flex-shrink: 0;
  box-shadow: 0 4px 14px -4px rgba(3, 129, 254, 0.45);
}
.user-text {
  flex: 1; min-width: 0;
  line-height: 1.2;
}
.user-name {
  font-size: 13px; font-weight: 600;
  overflow: hidden; white-space: nowrap; text-overflow: ellipsis;
}
.user-login {
  font-size: 11px; color: var(--text-muted);
  overflow: hidden; white-space: nowrap; text-overflow: ellipsis;
}
.chev { color: var(--text-muted); font-size: 12px; }
.user.open .chev { transform: rotate(180deg); }

.user-menu {
  position: absolute;
  bottom: calc(100% + 8px);
  left: 0;
  right: 0;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 6px;
  box-shadow: var(--shadow-lg);
  z-index: 100;
}
.menu-item {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 9px 10px;
  background: transparent;
  border: none;
  color: var(--text);
  font-size: 13px;
  font-weight: 500;
  text-align: left;
  border-radius: 8px;
  box-shadow: none;
  cursor: pointer;
}
.menu-item:hover { background: var(--surface-2); }
.menu-item.danger { color: var(--danger); }
.menu-item.danger:hover { background: var(--danger-soft); }
.mi-ico { width: 18px; display: inline-grid; place-items: center; }
.menu-sep { height: 1px; background: var(--border); margin: 4px 0; }

@media (max-width: 800px) {
  .sidebar {
    flex-direction: row;
    width: auto;
    right: 0;
    bottom: auto;
    padding: 10px 14px;
    gap: 10px;
    align-items: center;
  }
  .brand-name, .user-text { display: none; }
  .nav { flex-direction: row; gap: 4px; flex: 1; justify-content: center; }
  .nav-link { padding: 8px 10px; }
  .quick-upload { padding: 8px 10px; }
  .quick-upload span:not(.qu-plus) { display: none; }
  .sidebar-foot { margin: 0; }
}
</style>
