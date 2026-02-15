<template>
  <div class="app-shell">
    <AppHeader />
    <div class="app-body">
      <div class="app-sidebar">
        <AppSidebar />
      </div>
      <main class="app-main">
        <RouterView />
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import AppHeader from './components/common/AppHeader.vue'
import AppSidebar from './components/common/AppSidebar.vue'
</script>

<style scoped>
.app-shell {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background: var(--color-background);
}

.app-body {
  display: flex;
  flex: 1;
  min-height: 0;
}

.app-sidebar {
  width: 240px;
  background: var(--color-surface);
  border-right: 1px solid var(--color-border);
}

.app-main {
  flex: 1;
  padding: 24px;
  background: var(--color-background);
  overflow: auto;
}

@media (max-width: 1024px) {
  .app-body {
    flex-direction: column;
  }

  .app-sidebar {
    width: 100%;
    border-right: none;
    border-bottom: 1px solid var(--color-border);
  }

  .app-main {
    padding: 16px;
  }
}
</style>
