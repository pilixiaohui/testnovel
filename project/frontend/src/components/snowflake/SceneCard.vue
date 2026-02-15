<template>
  <el-card class="card" data-test="scene-card">
    <div class="header" data-test="scene-card-title">{{ scene.title }}</div>
    <div class="body">
      <p data-test="scene-card-sequence-index">序号：{{ scene.sequence_index }}</p>
      <p data-test="scene-card-expected-outcome">预期结果：{{ scene.expected_outcome || '' }}</p>
      <p data-test="scene-card-conflict-type">冲突类型：{{ scene.conflict_type || '' }}</p>
      <p data-test="scene-card-actual-outcome">实际结果：{{ scene.actual_outcome || '' }}</p>
      <p data-test="scene-card-parent-act">父幕：{{ scene.parent_act_id }}</p>
    </div>
    <pre class="raw" data-test="scene-card-raw">{{ JSON.stringify(scene, null, 2) }}</pre>
  </el-card>
</template>

<script setup lang="ts">
import type { SceneNode } from '../../types/snowflake'

const props = defineProps<{
  scene: SceneNode
}>()

const { scene } = props
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
