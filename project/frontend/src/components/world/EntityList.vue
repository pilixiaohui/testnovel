<template>
  <section class="entity-list" data-test="entity-list">
    <header class="header">
      <div>
        <h3>Entities</h3>
        <p class="meta">Total {{ entities.length }}</p>
      </div>
    </header>

    <div v-if="entities.length === 0" class="empty" data-test="entity-list-empty">
      <strong>No entities.</strong>
      <p class="subtitle">Select a world to load entities.</p>
    </div>

    <ul v-else class="list">
      <li v-for="entity in entities" :key="entity.id" class="item">
        <div class="title">{{ entity.name }}</div>
        <div class="meta">Type: {{ entity.type }}</div>
        <div class="meta">ID: {{ entity.id }}</div>
      </li>
    </ul>
  </section>
</template>

<script setup lang="ts">
import type { WorldEntity } from '../../types/entity'

defineProps<{
  entities: WorldEntity[]
}>()
</script>

<style scoped>
.entity-list {
  display: grid;
  gap: 12px;
}

.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.meta {
  margin: 2px 0 0;
  color: #6b7280;
  font-size: 12px;
}

.list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: grid;
  gap: 8px;
}

.item {
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 8px 12px;
  display: grid;
  gap: 4px;
}

.title {
  font-weight: 600;
}

.subtitle {
  margin: 4px 0 0;
  color: #6b7280;
}

.empty {
  border: 1px dashed #d1d5db;
  border-radius: 10px;
  padding: 12px;
}
</style>
