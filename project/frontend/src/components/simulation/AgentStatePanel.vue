<template>
  <el-card class="panel">
    <div class="header">
      <el-avatar :size="40" class="avatar">{{ agentState.character_id.slice(0, 1).toUpperCase() }}</el-avatar>
      <div class="meta">
        <div class="name">{{ agentState.character_id }}</div>
        <div class="sub">代理 {{ agentState.id }}</div>
      </div>
    </div>
    <el-collapse class="collapse" accordion>
      <el-collapse-item title="Beliefs" name="beliefs">
        <ul class="list">
          <li v-for="[key, value] in beliefEntries" :key="key">
            <span class="label">{{ key }}</span>
            <span class="value">{{ formatValue(value) }}</span>
          </li>
        </ul>
      </el-collapse-item>
      <el-collapse-item title="Desires" name="desires">
        <div class="desires">
          <div v-for="desire in sortedDesires" :key="desire.id" class="desire-item">
            <el-tag size="small" type="info">P{{ desire.priority }}</el-tag>
            <div class="desire-body">
              <div class="desire-title">{{ desire.description }}</div>
              <div class="desire-meta">{{ desire.type }} · {{ desire.satisfaction_condition }}</div>
            </div>
          </div>
        </div>
      </el-collapse-item>
      <el-collapse-item title="Intentions" name="intentions">
        <div class="intentions">
          <div v-for="intention in agentState.intentions" :key="intention.id" class="intention-item">
            <el-tag size="small">{{ intention.action_type }}</el-tag>
            <div class="intention-body">
              <div class="intention-target">目标：{{ intention.target }}</div>
              <div class="intention-meta">预期：{{ intention.expected_outcome }}</div>
            </div>
          </div>
        </div>
      </el-collapse-item>
    </el-collapse>
  </el-card>
</template>

<script setup lang="ts">
import { computed, toRefs } from 'vue'
import type { CharacterAgentState } from '../../types/simulation'

const props = defineProps<{
  agentState: CharacterAgentState
}>()

const { agentState } = toRefs(props)

const beliefEntries = computed(() => Object.entries(agentState.value.beliefs))
const sortedDesires = computed(() => [...agentState.value.desires].sort((a, b) => b.priority - a.priority))

const formatValue = (value: unknown) => {
  if (typeof value === 'string') {
    return value
  }
  return JSON.stringify(value)
}
</script>

<style scoped>
.panel {
  display: grid;
  gap: 12px;
}

.header {
  display: flex;
  align-items: center;
  gap: 12px;
}

.avatar {
  background: var(--color-primary);
  color: #fff;
}

.name {
  font-weight: 600;
}

.sub {
  font-size: 12px;
  color: var(--color-muted);
}

.list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 8px;
}

.label {
  font-weight: 600;
  margin-right: 6px;
}

.value {
  color: var(--color-muted);
}

.desires,
.intentions {
  display: grid;
  gap: 10px;
}

.desire-item,
.intention-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.desire-body,
.intention-body {
  display: grid;
  gap: 4px;
}

.desire-meta,
.intention-meta,
.intention-target {
  font-size: 12px;
  color: var(--color-muted);
}
</style>
