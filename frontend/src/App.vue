<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import AppHeader from './components/AppHeader.vue'
import TopNavbar from './components/TopNavbar.vue'
import BackgroundTasks from './components/BackgroundTasks.vue'

const route = useRoute()
const showChrome = computed(() => !!route.meta?.auth)
</script>

<template>
  <div class="app-shell" :class="{ 'with-sidebar': showChrome }">
    <AppHeader v-if="showChrome" />
    <div class="app-pane">
      <TopNavbar v-if="showChrome" />
      <main class="app-main">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </main>
    </div>
    <BackgroundTasks />
  </div>
</template>

<style>
.app-shell.with-sidebar .app-pane {
  margin-left: var(--sidebar-w);
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}
.app-main {
  flex: 1;
  min-width: 0;
}
@media (max-width: 800px) {
  .app-shell.with-sidebar .app-pane {
    margin-left: 0;
    padding-top: 60px;
  }
}
</style>
