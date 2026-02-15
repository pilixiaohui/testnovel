<template>
  <section class="panel">
    <SceneCard v-for="scene in scenes" :key="scene.id" :scene="scene" />
    <div v-if="scenes.length === 0" class="empty">暂无场景</div>
  </section>
</template>

<script setup lang="ts">
import SceneCard from './SceneCard.vue'
import type { SceneNode } from '../../types/snowflake'

const props = defineProps<{
  scenes: SceneNode[]
}>()

const { scenes } = props
</script>

<style scoped>
.panel {
  display: grid;
  gap: 12px;
}

.empty {
  color: var(--color-muted);
}
</style>
