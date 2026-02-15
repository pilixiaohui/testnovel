<template>
  <el-steps class="step-indicator" :active="activeIndex" align-center>
    <el-step
      v-for="(step, index) in normalizedSteps"
      :key="`${index}-${step.title}`"
      :title="step.title"
      :description="step.description"
      :status="step.status"
    />
  </el-steps>
</template>

<script setup lang="ts">
import { computed } from 'vue'

type StepItem = {
  title: string
  description?: string
}

type StepView = {
  title: string
  description: string
  status: 'wait' | 'process' | 'finish'
}

const props = defineProps<{
  currentStep: number
  steps: StepItem[]
}>()

const statusLabel = (index: number) => {
  if (index < props.currentStep - 1) return '已完成'
  if (index === props.currentStep - 1) return '进行中'
  return '待完成'
}

const statusValue = (index: number): StepView['status'] => {
  if (index < props.currentStep - 1) return 'finish'
  if (index === props.currentStep - 1) return 'process'
  return 'wait'
}

const normalizedSteps = computed<StepView[]>(() =>
  props.steps.map((step, index) => {
    const label = statusLabel(index)
    const description = step.description ? `${label} · ${step.description}` : label
    return {
      title: step.title,
      description,
      status: statusValue(index),
    }
  }),
)

const activeIndex = computed(() => Math.max(0, props.currentStep - 1))
</script>

<style scoped>
.step-indicator {
  width: 100%;
}
</style>
