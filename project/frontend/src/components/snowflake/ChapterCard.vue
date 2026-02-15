<template>
  <el-card class="card" data-test="chapter-card">
    <div class="header" data-test="chapter-card-title">第 {{ chapter.sequence }} 章 · {{ chapter.title }}</div>
    <div class="body">
      <p data-test="chapter-card-focus">焦点：{{ chapter.focus }}</p>
      <p data-test="chapter-card-word-count">字数：{{ chapter.word_count ?? '' }}</p>
      <p data-test="chapter-card-pov">视角角色：{{ chapter.pov_character_id || '' }}</p>
    </div>
    <pre class="raw" data-test="chapter-card-raw">{{ JSON.stringify(chapter, null, 2) }}</pre>
  </el-card>
</template>

<script setup lang="ts">
import type { Chapter } from '../../types/snowflake'

const props = defineProps<{
  chapter: Chapter
}>()

const { chapter } = props
</script>

<style scoped>
.card {
  display: grid;
  gap: 8px;
}

.header {
  font-weight: 600;
}

.body {
  color: var(--color-muted);
  font-size: 13px;
  display: grid;
  gap: 4px;
}

.body p {
  margin: 0;
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
</style>
