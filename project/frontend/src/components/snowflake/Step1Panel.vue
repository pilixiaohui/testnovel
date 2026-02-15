<template>
  <section class="panel">
    <el-input
      :model-value="modelValue"
      type="textarea"
      :rows="4"
      placeholder="请输入你的故事想法"
      @update:model-value="handleInput"
    />
    <div class="actions">
      <el-button type="primary" :loading="loading" @click="emit('submit')">生成</el-button>
    </div>
  </section>
</template>

<script setup lang="ts">
const props = withDefaults(
  defineProps<{
    modelValue: string
    loading?: boolean
  }>(),
  {
    loading: false,
  },
)

const emit = defineEmits<{
  (event: 'update:modelValue', value: string): void
  (event: 'submit'): void
}>()

const handleInput = (value: string) => {
  emit('update:modelValue', value)
}

const { modelValue, loading } = props
</script>

<style scoped>
.panel {
  display: grid;
  gap: 12px;
}

.actions {
  display: flex;
  justify-content: flex-end;
}
</style>
