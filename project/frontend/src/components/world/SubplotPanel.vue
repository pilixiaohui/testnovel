<template>
  <div class="panel">
    <el-card v-for="subplot in subplots" :key="subplot.id" class="subplot">
      <div class="header">
        <div class="title">{{ subplot.title }}</div>
        <el-tag size="small">{{ subplot.subplot_type }}</el-tag>
      </div>
      <div class="meta">状态：{{ subplot.status }}</div>
      <div class="content">冲突：{{ subplot.central_conflict }}</div>
      <div class="actions">
        <el-button size="small" type="primary" @click="emit('activate', subplot)">激活</el-button>
        <el-button size="small" type="success" @click="emit('resolve', subplot)">解决</el-button>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import type { Subplot } from '../../types/entity'

defineProps<{
  subplots: Subplot[]
}>()

const emit = defineEmits<{
  (event: 'activate', subplot: Subplot): void
  (event: 'resolve', subplot: Subplot): void
}>()
</script>

<style scoped>
.panel {
  display: grid;
  gap: 12px;
}

.subplot {
  display: grid;
  gap: 8px;
}

.header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.title {
  font-weight: 600;
}

.meta,
.content {
  color: var(--color-muted);
  font-size: 12px;
}

.actions {
  display: flex;
  gap: 8px;
}
</style>
