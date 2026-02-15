<template>
  <el-card class="preview">
    <div class="header">Markdown 预览</div>
    <ContentRenderer :content="content" format="markdown" />
  </el-card>
</template>

<script setup lang="ts">
import ContentRenderer from './ContentRenderer.vue'

defineProps<{
  content: string
}>()
</script>

<style scoped>
.preview {
  display: grid;
  gap: 12px;
}

.header {
  font-weight: 600;
}
</style>
