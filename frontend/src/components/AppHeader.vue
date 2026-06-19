<script setup>
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const auth = useAuthStore()

function logout() {
  auth.logout()
  router.push('/login')
}
</script>

<template>
  <header class="header">
    <div class="header-inner">
      <router-link to="/dashboard" class="brand">
        <span class="brand-icon">🎙️</span>
        <span class="brand-name">ownAi</span>
      </router-link>

      <nav class="nav">
        <router-link to="/dashboard" class="nav-link">Dashboard</router-link>
        <router-link to="/upload" class="nav-link">New transcription</router-link>
      </nav>

      <div class="user">
        <div class="avatar">{{ auth.user?.name?.[0]?.toUpperCase() || '?' }}</div>
        <div class="user-text">
          <div class="user-name">{{ auth.user?.name }}</div>
          <div class="user-login">@{{ auth.user?.login }}</div>
        </div>
        <button class="ghost logout" @click="logout">Logout</button>
      </div>
    </div>
  </header>
</template>

<style scoped>
.header {
  position: sticky;
  top: 0;
  z-index: 50;
  border-bottom: 1px solid var(--border);
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: saturate(180%) blur(20px);
  -webkit-backdrop-filter: saturate(180%) blur(20px);
}
.header-inner {
  max-width: 1100px;
  margin: 0 auto;
  padding: 14px 24px;
  display: flex;
  align-items: center;
  gap: 28px;
}
.brand {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  color: var(--text);
  font-weight: 800;
  font-size: 18px;
  letter-spacing: -0.02em;
}
.brand:hover { text-decoration: none; }
.brand-icon { font-size: 22px; filter: drop-shadow(0 4px 14px rgba(3, 129, 254, 0.3)); }
.brand-name {
  background: var(--brand-grad);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}

.nav {
  display: flex;
  gap: 4px;
  margin-left: 12px;
}
.nav-link {
  color: var(--text-dim);
  padding: 8px 14px;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 500;
}
.nav-link:hover { color: var(--text); background: var(--surface); text-decoration: none; }
.nav-link.router-link-active {
  color: var(--text);
  background: var(--surface-strong);
}

.user {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 12px;
}
.avatar {
  width: 38px; height: 38px;
  border-radius: 50%;
  background: var(--brand-grad);
  color: #ffffff;
  display: grid;
  place-items: center;
  font-weight: 700;
  font-size: 14px;
  box-shadow: 0 4px 14px -4px rgba(3, 129, 254, 0.45);
}
.user-text { line-height: 1.2; }
.user-name { font-size: 13px; font-weight: 600; }
.user-login { font-size: 11px; color: var(--text-muted); }
.logout { padding: 8px 14px; font-size: 13px; }

@media (max-width: 700px) {
  .nav { display: none; }
  .user-text { display: none; }
}
</style>
