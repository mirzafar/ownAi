<script setup>
import { MessagesSquare, Check } from 'lucide-vue-next'
</script>

<template>
  <div class="container">
    <div class="stub card">
      <div class="stub-icon"><MessagesSquare :size="36" /></div>
      <div class="stub-tag">Скоро</div>
      <h1 class="stub-title">Чаты появятся здесь</h1>
      <p class="stub-sub">
        Раздел временно отключён. Подключим переписки через
        <b>Wazzup</b> — WhatsApp, Telegram, Instagram и другие каналы будут
        выгружаться и анализироваться так же, как звонки.
      </p>
      <div class="stub-list">
        <div class="stub-item">
          <span class="stub-dot"><Check :size="12" /></span>
          <span>Список диалогов с фильтром по дате и каналу</span>
        </div>
        <div class="stub-item">
          <span class="stub-dot"><Check :size="12" /></span>
          <span>Анализ переписки по тем же критериям, что и звонки</span>
        </div>
        <div class="stub-item">
          <span class="stub-dot"><Check :size="12" /></span>
          <span>Операторы и средний балл чатов в Dashboard</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.stub {
  margin-top: 40px;
  text-align: center;
  padding: 60px 40px;
  max-width: 640px;
  margin-left: auto;
  margin-right: auto;
}
.stub-icon {
  width: 72px; height: 72px;
  border-radius: 20px;
  background: var(--brand-grad);
  color: #fff;
  display: grid; place-items: center;
  margin: 0 auto 18px;
  box-shadow: 0 16px 40px -16px rgba(20, 184, 166, 0.55);
}
.stub-dot {
  width: 22px; height: 22px;
  border-radius: 50%;
  background: var(--success-soft);
  color: var(--success);
  display: grid; place-items: center;
  flex-shrink: 0;
}
.stub-tag {
  display: inline-block;
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  color: var(--brand);
  background: var(--brand-soft);
  padding: 4px 12px;
  border-radius: 999px;
  margin-bottom: 14px;
}
.stub-title {
  font-size: 26px;
  font-weight: 800;
  letter-spacing: -0.02em;
  margin: 0 0 10px;
}
.stub-sub {
  font-size: 15px;
  line-height: 1.6;
  color: var(--text-dim);
  margin: 0 0 28px;
}
.stub-sub b { color: var(--text); }
.stub-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  text-align: left;
  max-width: 460px;
  margin: 0 auto;
}
.stub-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  background: var(--surface-2);
  border-radius: 12px;
  font-size: 14px;
  color: var(--text);
}
</style>
