<template>
  <section class="panel">
    <div v-if="root" class="content">
      <el-descriptions :column="1" border>
        <el-descriptions-item label="Logline">{{ root.logline }}</el-descriptions-item>
        <el-descriptions-item label="主题">{{ root.theme }}</el-descriptions-item>
        <el-descriptions-item label="结局">{{ root.ending }}</el-descriptions-item>
      </el-descriptions>
      <div class="disasters">
        <h4>三灾难</h4>
        <ul>
          <li v-for="item in root.three_disasters" :key="item">{{ item }}</li>
        </ul>
      </div>
    </div>
    <div v-else class="empty">暂无结构</div>
  </section>
</template>

<script setup lang="ts">
import type { SnowflakeRoot } from '../../types/snowflake'

const props = defineProps<{
  root: SnowflakeRoot | null
}>()

const { root } = props
</script>

<style scoped>
.panel {
  display: grid;
  gap: 12px;
}

.content {
  display: grid;
  gap: 12px;
}

.disasters ul {
  padding-left: 16px;
  list-style: disc;
}

.empty {
  color: var(--color-muted);
}
</style>
