<template>
  <header class="app-header">
    <div class="brand" @click="handleSelect('/')">
      <span class="logo">AI Novel</span>
    </div>
    <el-menu
      class="nav"
      mode="horizontal"
      :default-active="activeIndex"
      @select="handleSelect"
    >
      <el-menu-item v-for="item in navigationItems" :key="item.index" :index="item.index">
        {{ item.label }}
      </el-menu-item>
    </el-menu>
  </header>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useProjectStore } from '@/stores/project'
import { buildNavigationTarget, navigationItems, resolveActivePath } from '../../utils/navigation'

const router = useRouter()
const route = useRoute()
const projectStore = useProjectStore()

const activeIndex = computed(() => resolveActivePath(route.path))

const handleSelect = (index: string) => {
  router.push(
    buildNavigationTarget(index, {
      root_id: projectStore.root_id,
      branch_id: projectStore.branch_id,
      scene_id: projectStore.scene_id,
    }),
  )
}
</script>

<style scoped>
.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  border-bottom: 1px solid var(--color-border);
  background: var(--color-surface);
  gap: 16px;
}

.brand {
  display: flex;
  align-items: center;
  cursor: pointer;
}

.logo {
  font-weight: 700;
  font-size: 18px;
  color: var(--color-text);
}

.nav {
  flex: 1;
  justify-content: flex-end;
  border-bottom: none;
}

@media (max-width: 768px) {
  .app-header {
    flex-direction: column;
    align-items: flex-start;
    padding: 12px 16px;
  }

  .nav {
    width: 100%;
    justify-content: flex-start;
  }
}
</style>
