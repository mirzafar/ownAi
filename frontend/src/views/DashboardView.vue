<script setup>
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
</script>

<template>
  <div class="container">
    <div class="hero">
      <div class="hero-tag">Dashboard</div>
      <h1 class="hero-title">Привет, {{ auth.user?.name?.split(' ')[0] || 'друг' }} 👋</h1>
      <p class="hero-sub">Здесь скоро появятся метрики и быстрые отчёты.</p>
    </div>
  </div>
</template>

<style scoped>
.hero {
  padding: 80px 30px;
  text-align: center;
}
.hero-tag {
  display: inline-block;
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  color: var(--brand);
  background: var(--brand-soft);
  padding: 4px 12px;
  border-radius: 999px;
  margin-bottom: 16px;
}
.hero-title {
  font-size: 38px;
  font-weight: 800;
  letter-spacing: -0.02em;
  margin: 0 0 10px;
}
.hero-sub {
  font-size: 16px;
  color: var(--text-dim);
  margin: 0;
}
</style>
