<template>
  <el-card class="editor">
    <div class="header">场景编辑：{{ sceneId }}</div>
    <el-input
      v-model="draft"
      type="textarea"
      :rows="10"
      placeholder="请输入场景内容"
    />
    <div class="actions">
      <el-button type="primary" @click="handleSave">保存</el-button>
      <el-button @click="emit('cancel')">取消</el-button>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'

const props = withDefaults(
  defineProps<{
    sceneId: string
    content?: string
  }>(),
  {
    content: '',
  },
)

const emit = defineEmits<{
  (event: 'save', payload: { sceneId: string; content: string }): void
  (event: 'cancel'): void
}>()

const { sceneId, content } = props
const draft = ref(content)

watch(
  () => content,
  (value) => {
    draft.value = value
  },
)

const handleSave = () => {
  emit('save', { sceneId, content: draft.value })
}
</script>

<style scoped>
.editor {
  display: grid;
  gap: 12px;
}

.header {
  font-weight: 600;
}

.actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>
