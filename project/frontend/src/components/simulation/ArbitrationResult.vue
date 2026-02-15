<template>
  <el-card class="panel">
    <div class="title">裁决结果</div>
    <div class="section">
      <div class="section-title">行动结果</div>
      <div v-for="result in arbitration.action_results" :key="result.action_id" class="result">
        <el-tag :type="statusType(result.success)" size="small">{{ result.success }}</el-tag>
        <div class="result-body">
          <div class="result-main">角色 {{ result.agent_id }}：{{ result.actual_outcome }}</div>
          <div class="result-reason">原因：{{ result.reason }}</div>
        </div>
      </div>
    </div>
    <div v-if="arbitration.conflicts_resolved.length" class="section">
      <div class="section-title">冲突解决</div>
      <el-alert
        v-for="(conflict, index) in arbitration.conflicts_resolved"
        :key="index"
        type="warning"
        :title="conflict.resolution"
        :description="conflict.agents.join(' / ')"
        show-icon
        class="alert"
      />
    </div>
    <div v-if="arbitration.environment_changes.length" class="section">
      <div class="section-title">环境变化</div>
      <ul class="list">
        <li v-for="(change, index) in arbitration.environment_changes" :key="index">
          <span class="label">{{ change.type }}</span>
          <span class="value">{{ change.description }}</span>
        </li>
      </ul>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import type { DMArbitration } from '../../types/simulation'

const props = defineProps<{
  arbitration: DMArbitration
}>()

const { arbitration } = props

const statusType = (status: string) => {
  if (status === 'success') {
    return 'success'
  }
  if (status === 'partial') {
    return 'warning'
  }
  return 'danger'
}
</script>

<style scoped>
.panel {
  display: grid;
  gap: 16px;
}

.title {
  font-weight: 600;
}

.section {
  display: grid;
  gap: 10px;
}

.section-title {
  font-weight: 600;
  color: var(--color-text);
}

.result {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.result-body {
  display: grid;
  gap: 4px;
}

.result-reason {
  font-size: 12px;
  color: var(--color-muted);
}

.list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 6px;
}

.label {
  font-weight: 600;
  margin-right: 6px;
}

.value {
  color: var(--color-muted);
}

.alert + .alert {
  margin-top: 8px;
}
</style>
