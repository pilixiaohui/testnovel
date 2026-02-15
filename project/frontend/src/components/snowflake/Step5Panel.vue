<template>
  <section class="panel">
    <div class="section">
      <h4>幕结构</h4>
      <ActCard v-for="act in acts" :key="act.id" :act="act" />
      <div v-if="acts.length === 0" class="empty">暂无幕</div>
    </div>
    <div class="section">
      <h4>章结构</h4>
      <ChapterCard v-for="chapter in chapters" :key="chapter.id" :chapter="chapter" />
      <div v-if="chapters.length === 0" class="empty">暂无章</div>
    </div>
  </section>
</template>

<script setup lang="ts">
import ActCard from './ActCard.vue'
import ChapterCard from './ChapterCard.vue'
import type { Act, Chapter } from '../../types/snowflake'

const props = defineProps<{
  acts: Act[]
  chapters: Chapter[]
}>()

const { acts, chapters } = props
</script>

<style scoped>
.panel {
  display: grid;
  gap: 16px;
}

.section {
  display: grid;
  gap: 8px;
}

.empty {
  color: var(--color-muted);
}
</style>
