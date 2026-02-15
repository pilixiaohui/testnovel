<template>
  <div class="renderer">
    <div v-if="format === 'markdown'" class="markdown" v-html="renderedContent" />
    <pre v-else class="text">{{ content }}</pre>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    content: string
    format?: 'markdown' | 'text'
  }>(),
  {
    format: 'text',
  },
)

const { content, format } = props

const escapeHtml = (value: string) =>
  value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')

const renderMarkdown = (value: string) => {
  let output = escapeHtml(value)
  output = output.replace(/^### (.*)$/gm, '<h3>$1</h3>')
  output = output.replace(/^## (.*)$/gm, '<h2>$1</h2>')
  output = output.replace(/^# (.*)$/gm, '<h1>$1</h1>')
  output = output.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
  output = output.replace(/\n/g, '<br />')
  return output
}

const renderedContent = computed(() => renderMarkdown(content))
</script>

<style scoped>
.renderer {
  display: grid;
  gap: 8px;
}

.text {
  white-space: pre-wrap;
  margin: 0;
}

.markdown h1,
.markdown h2,
.markdown h3 {
  margin: 12px 0 6px;
}
</style>
