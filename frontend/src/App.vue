<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import AppHeader from './components/AppHeader.vue'
import BackgroundTasks from './components/BackgroundTasks.vue'

const route = useRoute()
const showHeader = computed(() => !!route.meta?.auth)
</script>

<template>
  <div class="app-shell" :class="{ 'with-sidebar': showHeader }">
    <AppHeader v-if="showHeader" />
    <main class="app-main">
      <router-view v-slot="{ Component }">
        <transition name="fade" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </main>
    <BackgroundTasks />
  </div>
</template>

<style>
.app-shell.with-sidebar .app-main {
  margin-left: 240px;
  min-height: 100vh;
}
@media (max-width: 800px) {
  .app-shell.with-sidebar .app-main {
    margin-left: 0;
    padding-top: 64px;
  }
}
</style>
