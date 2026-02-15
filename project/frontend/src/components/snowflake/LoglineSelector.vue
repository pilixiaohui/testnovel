<template>
  <el-radio-group
    class="logline-selector"
    :model-value="modelValue"
    @update:model-value="handleChange"
  >
    <el-radio v-for="option in options" :key="option" :label="option">
      {{ option }}
    </el-radio>
  </el-radio-group>
</template>

<script setup lang="ts">
const props = defineProps<{
  options: string[]
  modelValue: string
}>()

const emit = defineEmits<{
  (event: 'update:modelValue', value: string): void
}>()

const handleChange = (value: string) => {
  emit('update:modelValue', value)
}
</script>

<style scoped>
.logline-selector {
  display: grid;
  gap: 8px;
}
</style>
