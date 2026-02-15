<template>
  <aside class="sidebar">
    <div class="section">
      <div class="section-title">导航</div>
      <el-menu class="menu" :default-active="activeIndex" @select="handleSelect">
        <el-menu-item v-for="item in navigationItems" :key="item.index" :index="item.index">
          <span>{{ item.label }}</span>
        </el-menu-item>
      </el-menu>
    </div>
  </aside>
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
.sidebar {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px;
}

.section-title {
  font-size: 12px;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--color-muted);
}

.menu {
  border-right: none;
}
</style>
