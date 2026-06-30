<script setup>
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import QuickUploadModal from './QuickUploadModal.vue'
import {
  LayoutDashboard,
  Phone,
  MessagesSquare,
  Sparkles,
  Headphones,
  ClipboardList,
  Users as UsersIcon,
  Plus,
  ChevronDown,
  User,
  LogOut,
  AudioLines,
} from 'lucide-vue-next'

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
      <div class="brand-mark">
        <AudioLines :size="20" />
      </div>
      <span class="brand-name">ownAi</span>
    </router-link>

    <button class="quick-upload" @click="uploadOpen = true">
      <Plus :size="18" />
      <span>Загрузить аудио</span>
    </button>

    <div class="nav-section-title">Основное</div>
    <nav class="nav">
      <router-link to="/dashboard" class="nav-link" :class="{ active: isActive('/dashboard') }">
        <LayoutDashboard class="ico" />
        <span>Dashboard</span>
      </router-link>
      <router-link to="/calls" class="nav-link" :class="{ active: isActive('/calls') }">
        <Phone class="ico" />
        <span>Звонки</span>
      </router-link>
      <router-link to="/chats" class="nav-link" :class="{ active: isActive('/chats') }">
        <MessagesSquare class="ico" />
        <span>Чаты</span>
        <span class="soon">скоро</span>
      </router-link>
      <router-link to="/analyses" class="nav-link" :class="{ active: isActive('/analyses') || isActive('/t') }">
        <Sparkles class="ico" />
        <span>Анализы</span>
      </router-link>
    </nav>

    <div class="nav-section-title">Команда</div>
    <nav class="nav">
      <router-link to="/operators" class="nav-link" :class="{ active: isActive('/operators') }">
        <Headphones class="ico" />
        <span>Операторы</span>
      </router-link>
      <router-link to="/leads" class="nav-link" :class="{ active: isActive('/leads') }">
        <ClipboardList class="ico" />
        <span>Лиды</span>
      </router-link>
      <router-link
        v-if="auth.user?.is_admin"
        to="/users"
        class="nav-link"
        :class="{ active: isActive('/users') }"
      >
        <UsersIcon class="ico" />
        <span>Пользователи</span>
      </router-link>
    </nav>

    <div class="sidebar-foot">
      <div class="user" :class="{ open: userMenuOpen }" @click="userMenuOpen = !userMenuOpen">
        <div class="avatar">{{ auth.user?.name?.[0]?.toUpperCase() || '?' }}</div>
        <div class="user-text">
          <div class="user-name">{{ auth.user?.name }}</div>
          <div class="user-login">@{{ auth.user?.login }}</div>
        </div>
        <ChevronDown :size="16" class="chev" />

        <div v-if="userMenuOpen" class="user-menu" @click.stop>
          <button class="menu-item" @click="go('/profile')">
            <User :size="16" />Профиль
          </button>
          <div class="menu-sep"></div>
          <button class="menu-item danger" @click="logout">
            <LogOut :size="16" />Выйти
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
  width: var(--sidebar-w);
  padding: 22px 16px;
  background: #ffffff;
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  gap: 6px;
  z-index: 50;
}

.brand {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  color: var(--text);
  font-weight: 700;
  font-size: 17px;
  letter-spacing: -0.02em;
  padding: 4px 8px 8px;
  margin-bottom: 6px;
}
.brand:hover { text-decoration: none; }
.brand-mark {
  width: 32px; height: 32px;
  border-radius: 10px;
  background: var(--brand-grad);
  color: #fff;
  display: grid; place-items: center;
  box-shadow: 0 6px 16px -6px rgba(20, 184, 166, 0.55);
}
.brand-name { color: var(--text); }

.quick-upload {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 11px 14px;
  border-radius: 12px;
  background: var(--brand-grad);
  color: #fff;
  border: 1px solid transparent;
  font-weight: 600;
  font-size: 14px;
  box-shadow: 0 10px 22px -10px rgba(20, 184, 166, 0.55);
  margin-bottom: 14px;
}
.quick-upload:hover { filter: brightness(1.04); }

.nav-section-title {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--text-muted);
  padding: 12px 12px 6px;
}

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
  position: relative;
}
.nav-link:hover { color: var(--text); background: var(--surface-2); text-decoration: none; }
.nav-link.active {
  color: var(--brand-hover);
  background: var(--brand-soft);
  font-weight: 600;
}
.nav-link.active::before {
  content: '';
  position: absolute;
  left: -16px;
  top: 8px;
  bottom: 8px;
  width: 3px;
  border-radius: 0 3px 3px 0;
  background: var(--brand);
}
.ico {
  width: 18px;
  height: 18px;
  stroke-width: 1.75;
  flex-shrink: 0;
  color: currentColor;
}
.nav-link.active .ico { color: var(--brand); }
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
  padding-top: 12px;
  border-top: 1px solid var(--border);
}
.user {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 8px;
  border-radius: 12px;
  cursor: pointer;
  position: relative;
}
.user:hover { background: var(--surface-2); }
.user.open { background: var(--surface-2); }
.avatar {
  width: 34px; height: 34px;
  border-radius: 10px;
  background: var(--brand-grad);
  color: #fff;
  display: grid; place-items: center;
  font-weight: 700; font-size: 13px;
  flex-shrink: 0;
  box-shadow: 0 4px 14px -4px rgba(20, 184, 166, 0.45);
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
.chev { color: var(--text-muted); transition: transform 0.15s; }
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
    border-right: none;
    border-bottom: 1px solid var(--border);
  }
  .brand-name, .user-text, .nav-section-title { display: none; }
  .nav { flex-direction: row; gap: 4px; flex: 1; justify-content: center; }
  .nav-link { padding: 8px 10px; }
  .nav-link.active::before { display: none; }
  .quick-upload { padding: 8px 10px; margin: 0; }
  .quick-upload span { display: none; }
  .sidebar-foot { margin: 0; padding: 0; border: none; }
}
</style>
