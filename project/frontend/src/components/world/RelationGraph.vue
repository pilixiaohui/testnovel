<template>
  <el-card class="graph">
    <div class="header">关系图谱</div>
    <svg :width="width" :height="height" class="canvas">
      <line
        v-for="edge in edges"
        :key="edge.from_entity_id + edge.to_entity_id"
        :x1="edge.source.x"
        :y1="edge.source.y"
        :x2="edge.target.x"
        :y2="edge.target.y"
        class="edge"
      />
      <g v-for="node in nodes" :key="node.entity.entity_id">
        <circle :cx="node.x" :cy="node.y" r="14" class="node" />
        <text :x="node.x" :y="node.y + 4" text-anchor="middle" class="label">
          {{ node.entity.name || node.entity.entity_id }}
        </text>
      </g>
    </svg>
    <div class="legend">
      <div v-for="relation in relations" :key="relation.from_entity_id + relation.to_entity_id + relation.relation_type">
        {{ relation.from_entity_id }} → {{ relation.to_entity_id }} ({{ relation.relation_type }})
      </div>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { EntityRelationView, EntityView } from '../../types/entity'

const props = defineProps<{
  entities: EntityView[]
  relations: EntityRelationView[]
}>()

const width = 360
const height = 240

const nodes = computed(() => {
  const count = props.entities.length || 1
  const radius = Math.min(width, height) / 2 - 30
  const centerX = width / 2
  const centerY = height / 2

  return props.entities.map((entity, index) => {
    const angle = (2 * Math.PI * index) / count
    return {
      entity,
      x: centerX + radius * Math.cos(angle),
      y: centerY + radius * Math.sin(angle),
    }
  })
})

const nodeMap = computed(() => {
  const map: Record<string, { x: number; y: number }> = {}
  nodes.value.forEach((node) => {
    map[node.entity.entity_id] = { x: node.x, y: node.y }
  })
  return map
})

const edges = computed(() =>
  props.relations.map((relation) => ({
    ...relation,
    source: nodeMap.value[relation.from_entity_id]!,
    target: nodeMap.value[relation.to_entity_id]!,
  })),
)
</script>

<style scoped>
.graph {
  display: grid;
  gap: 12px;
}

.header {
  font-weight: 600;
}

.canvas {
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: var(--color-surface);
}

.edge {
  stroke: var(--color-border);
  stroke-width: 2;
}

.node {
  fill: var(--color-primary);
}

.label {
  fill: #fff;
  font-size: 10px;
}

.legend {
  display: grid;
  gap: 4px;
  color: var(--color-muted);
  font-size: 12px;
}
</style>
