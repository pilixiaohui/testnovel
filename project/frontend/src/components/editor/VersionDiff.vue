<template>
  <el-card class="diff">
    <div class="header">版本对比</div>
    <div class="grid">
      <div class="column">
        <div class="column-title">旧版本</div>
        <div v-for="line in diffLines" :key="`old-${line.index}`" :class="['line', line.status]">
          <span class="line-number">{{ line.index }}</span>
          <span class="line-text">{{ line.oldLine }}</span>
        </div>
      </div>
      <div class="column">
        <div class="column-title">新版本</div>
        <div v-for="line in diffLines" :key="`new-${line.index}`" :class="['line', line.status]">
          <span class="line-number">{{ line.index }}</span>
          <span class="line-text">{{ line.newLine }}</span>
        </div>
      </div>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  oldContent: string
  newContent: string
}>()

const { oldContent, newContent } = props

const diffLines = computed(() => {
  const oldLines = oldContent.split('\n')
  const newLines = newContent.split('\n')
  const maxLines = Math.max(oldLines.length, newLines.length)
  const lines = [] as Array<{
    index: number
    oldLine: string
    newLine: string
    status: 'same' | 'changed'
  }>

  for (let i = 0; i < maxLines; i += 1) {
    const oldLine = oldLines[i] ?? ''
    const newLine = newLines[i] ?? ''
    lines.push({
      index: i + 1,
      oldLine,
      newLine,
      status: oldLine === newLine ? 'same' : 'changed',
    })
  }

  return lines
})
</script>

<style scoped>
.diff {
  display: grid;
  gap: 12px;
}

.header {
  font-weight: 600;
}

.grid {
  display: grid;
  gap: 16px;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
}

.column {
  display: grid;
  gap: 6px;
}

.column-title {
  font-weight: 600;
  color: var(--color-muted);
}

.line {
  display: grid;
  grid-template-columns: 32px 1fr;
  gap: 8px;
  padding: 4px 6px;
  border-radius: 6px;
}

.line.changed {
  background: rgba(37, 99, 235, 0.08);
}

.line-number {
  color: var(--color-muted);
  font-size: 12px;
}

.line-text {
  white-space: pre-wrap;
}
</style>
