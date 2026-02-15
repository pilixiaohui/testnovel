<template>
  <section v-if="loading || error" class="api-feedback" data-test="api-feedback">
    <div v-if="error" class="api-feedback-error" data-test="api-error">{{ error }}</div>
    <div v-else class="api-feedback-loading" data-test="api-loading">Loading...</div>
  </section>
</template>

<script setup lang="ts">
defineProps<{
  loading: boolean
  error: string
}>()
</script>

<style scoped>
.api-feedback {
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 10px 12px;
  display: grid;
  gap: 8px;
}

.api-feedback-loading {
  color: #2563eb;
  font-weight: 600;
}

.api-feedback-error {
  color: #b91c1c;
  font-weight: 600;
}
</style>
