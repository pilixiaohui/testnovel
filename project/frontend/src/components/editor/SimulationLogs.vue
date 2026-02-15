<template>
  <div class="logs">
    <el-card v-for="round in logs" :key="round.round_id" class="round">
      <div class="header">
        <div class="title">回合 {{ round.round_id }}</div>
        <div class="meta">
          <el-tag size="small">{{ round.agent_actions.length }} actions</el-tag>
          <el-tag size="small" type="info">convergence {{ round.convergence_score }}</el-tag>
          <el-tag size="small" type="warning">info +{{ round.info_gain }}</el-tag>
        </div>
      </div>
      <div class="section">
        <div class="section-title">Agent Actions</div>
        <ul class="list">
          <li v-for="(action, index) in round.agent_actions" :key="index">
            <span class="label">{{ action.agent_id }}</span>
            {{ action.action_type }} → {{ action.action_target }}
          </li>
        </ul>
      </div>
      <div class="section">
        <div class="section-title">裁决摘要</div>
        <div class="summary">结果数：{{ round.dm_arbitration.action_results.length }}</div>
        <div class="summary">冲突数：{{ round.dm_arbitration.conflicts_resolved.length }}</div>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import type { SimulationRoundResult } from '../../types/simulation'

defineProps<{
  logs: SimulationRoundResult[]
}>()
</script>

<style scoped>
.logs {
  display: grid;
  gap: 16px;
}

.round {
  display: grid;
  gap: 12px;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.title {
  font-weight: 600;
}

.meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.section {
  display: grid;
  gap: 8px;
}

.section-title {
  font-weight: 600;
  color: var(--color-text);
}

.list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: grid;
  gap: 6px;
}

.label {
  font-weight: 600;
  margin-right: 6px;
}

.summary {
  color: var(--color-muted);
  font-size: 12px;
}
</style>
