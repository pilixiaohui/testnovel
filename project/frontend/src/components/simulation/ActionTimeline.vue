<template>
  <el-card class="timeline">
    <div class="header">Action Timeline</div>
    <el-timeline>
      <el-timeline-item v-for="round in rounds" :key="round.round_id" @click="emit('select', round)">
        <div class="round">
          <div class="round-header">
            <span>Round {{ round.round_id }}</span>
            <el-tag size="small" type="warning">info +{{ round.info_gain }}</el-tag>
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
          <div v-if="round.dm_arbitration.conflicts_resolved.length" class="section">
            <div class="section-title">Conflicts</div>
            <el-alert
              v-for="(conflict, index) in round.dm_arbitration.conflicts_resolved"
              :key="index"
              type="warning"
              :title="conflict.resolution"
              :description="conflict.agents.join(' / ')"
              show-icon
              class="alert"
            />
          </div>
        </div>
      </el-timeline-item>
    </el-timeline>
  </el-card>
</template>

<script setup lang="ts">
import type { SimulationRoundResult } from '../../types/simulation'

defineProps<{
  rounds: SimulationRoundResult[]
}>()

const emit = defineEmits<{
  (event: 'select', round: SimulationRoundResult): void
}>()
</script>

<style scoped>
.timeline {
  display: grid;
  gap: 12px;
}

.header {
  font-weight: 600;
}

.round {
  display: grid;
  gap: 10px;
}

.round-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
}

.section {
  display: grid;
  gap: 6px;
}

.section-title {
  font-size: 12px;
  color: var(--color-muted);
  font-weight: 600;
}

.list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: grid;
  gap: 4px;
}

.label {
  font-weight: 600;
  margin-right: 6px;
}

.alert + .alert {
  margin-top: 6px;
}
</style>
