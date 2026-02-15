<template>
  <el-card class="card" data-test="act-card">
    <div class="header" data-test="act-card-title">第 {{ act.sequence }} 幕 · {{ act.title }}</div>
    <div class="body">
      <p data-test="act-card-purpose">目的：{{ act.purpose }}</p>
      <p data-test="act-card-tone">基调：{{ act.tone }}</p>
    </div>
    <pre class="raw" data-test="act-card-raw">{{ JSON.stringify(act, null, 2) }}</pre>
  </el-card>
</template>

<script setup lang="ts">
import type { Act } from '../../types/snowflake'

const props = defineProps<{
  act: Act
}>()

const { act } = props
</script>

<style scoped>
.card {
  display: grid;
  gap: 8px;
}

.header {
  font-weight: 600;
}

.body {
  color: var(--color-muted);
  font-size: 13px;
  display: grid;
  gap: 4px;
}

.body p {
  margin: 0;
}

.raw {
  margin: 0;
  padding: 8px;
  border-radius: 8px;
  background: #f5f7fa;
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
