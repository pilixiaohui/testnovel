<template>
  <el-card class="panel">
    <div class="title">收敛状态</div>
    <el-progress :percentage="progress" :status="progressStatus" />
    <el-descriptions :column="1" size="small" border class="descriptions">
      <el-descriptions-item label="目标锚点">{{ resolvedConvergence.next_anchor_id }}</el-descriptions-item>
      <el-descriptions-item label="距离">{{ resolvedConvergence.distance }}</el-descriptions-item>
      <el-descriptions-item label="平均信息增量">{{ avgInfoGainDisplay }}</el-descriptions-item>
    </el-descriptions>
    <el-alert v-if="alertMessage" :title="alertMessage" :type="alertType" show-icon class="alert" />
  </el-card>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ConvergenceCheck } from '../../types/simulation'

type ConvergencePayload = ConvergenceCheck | { score: number; check: ConvergenceCheck }

const props = defineProps<{
  convergence: ConvergencePayload
  avgInfoGain?: number
  isStagnant?: boolean
}>()

const resolvedConvergence = computed(() =>
  'check' in props.convergence ? props.convergence.check : props.convergence,
)

const progress = computed(() => (1 - resolvedConvergence.value.distance) * 100)

const progressStatus = computed(() => {
  if (props.isStagnant || resolvedConvergence.value.convergence_needed) {
    return 'warning'
  }
  return 'success'
})

const alertMessage = computed(() => {
  if (props.isStagnant) {
    return '推演可能停滞，建议引入新的冲突或信息。'
  }
  if (resolvedConvergence.value.convergence_needed) {
    if (resolvedConvergence.value.suggested_action) {
      return resolvedConvergence.value.suggested_action
    }
    return '建议收敛至目标锚点。'
  }
  return ''
})

const alertType = computed(() => (props.isStagnant ? 'warning' : 'info'))
const avgInfoGainDisplay = computed(() =>
  props.avgInfoGain === undefined ? '-' : props.avgInfoGain,
)
</script>

<style scoped>
.panel {
  display: grid;
  gap: 14px;
}

.title {
  font-weight: 600;
}

.descriptions {
  background: var(--color-surface);
}

.alert {
  margin-top: 4px;
}
</style>
