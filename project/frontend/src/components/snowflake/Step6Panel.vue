<template>
  <section class="panel">
    <el-card v-for="anchor in anchors" :key="anchor.id" class="anchor-card" data-test="step6-anchor-card">
      <div class="title" data-test="step6-anchor-title">{{ anchor.anchor_type }} · {{ anchor.sequence }}</div>
      <p class="desc" data-test="step6-anchor-description">{{ anchor.description }}</p>
      <div class="meta">
        <span data-test="step6-anchor-constraint">约束: {{ anchor.constraint_type }}</span>
        <span data-test="step6-anchor-achieved">已达成: {{ anchor.achieved ? '是' : '否' }}</span>
      </div>
      <p class="conditions" data-test="step6-anchor-required-conditions">
        必备条件: {{ anchor.required_conditions.join(', ') }}
      </p>
      <pre class="raw" data-test="step6-anchor-raw">{{ JSON.stringify(anchor, null, 2) }}</pre>
    </el-card>
    <div v-if="anchors.length === 0" class="empty">暂无锚点</div>
  </section>
</template>

<script setup lang="ts">
import type { StoryAnchor } from '../../types/entity'

const props = defineProps<{
  anchors: StoryAnchor[]
}>()

const { anchors } = props
</script>

<style scoped>
.panel {
  display: grid;
  gap: 12px;
}

.anchor-card {
  display: grid;
  gap: 8px;
}

.title {
  font-weight: 600;
}

.desc {
  margin: 0;
  color: var(--color-muted);
}

.meta {
  display: flex;
  gap: 12px;
  font-size: 12px;
  color: var(--color-muted);
}

.conditions {
  margin: 0;
  font-size: 12px;
  color: var(--color-muted);
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

.empty {
  color: var(--color-muted);
}
</style>
