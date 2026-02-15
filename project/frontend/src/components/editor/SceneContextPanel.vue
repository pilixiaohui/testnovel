<template>
  <el-card class="panel">
    <div class="header">场景上下文</div>
    <div class="section">
      <div class="section-title">摘要</div>
      <div class="text">{{ context.summary }}</div>
    </div>
    <div class="section">
      <div class="section-title">预期结果</div>
      <div class="text">{{ context.expected_outcome }}</div>
    </div>
    <div class="section">
      <div class="section-title">语义状态</div>
      <ul class="list">
        <li v-for="[key, value] in semanticEntries" :key="key">
          <span class="label">{{ key }}</span>
          <span class="value">{{ formatValue(value) }}</span>
        </li>
      </ul>
    </div>
    <div class="section">
      <div class="section-title">出场实体</div>
      <div class="tags">
        <el-tag v-for="entity in context.scene_entities" :key="entity.entity_id" size="small">
          {{ entity.name || entity.entity_id }}
        </el-tag>
      </div>
    </div>
    <div class="section">
      <div class="section-title">角色</div>
      <div class="tags">
        <el-tag v-for="character in context.characters" :key="character.entity_id" size="small" type="info">
          {{ character.name || character.entity_id }}
        </el-tag>
      </div>
    </div>
    <div class="section">
      <div class="section-title">关系</div>
      <ul class="list">
        <li v-for="relation in context.relations" :key="relation.from_entity_id + relation.to_entity_id">
          <span class="label">{{ relation.from_entity_id }} → {{ relation.to_entity_id }}</span>
          <span class="value">{{ relation.relation_type }} ({{ relation.tension }})</span>
        </li>
      </ul>
    </div>
    <div class="section">
      <div class="section-title">前后场景</div>
      <div class="text">Prev: {{ context.prev_scene_id }}</div>
      <div class="text">Next: {{ context.next_scene_id }}</div>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { SceneContextView } from '../../types/entity'

const props = defineProps<{
  context: SceneContextView
}>()

const { context } = props

const semanticEntries = computed(() => Object.entries(context.semantic_states))

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
  gap: 14px;
}

.header {
  font-weight: 600;
}

.section {
  display: grid;
  gap: 6px;
}

.section-title {
  font-weight: 600;
  color: var(--color-text);
}

.text {
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

.tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
</style>
