<template>
  <section class="timeline" data-test="anchor-timeline">
    <header class="header">
      <div>
        <h3>Anchors</h3>
        <p class="meta">Total {{ anchors.length }}</p>
      </div>
    </header>

    <div v-if="anchors.length === 0" class="empty" data-test="anchor-timeline-empty">
      <strong>No anchors.</strong>
      <p class="subtitle">Anchors will appear after loading a world.</p>
    </div>

    <ol v-else class="list">
      <li v-for="(anchor, index) in anchors" :key="`${index}-${anchor}`" class="item">
        <div class="marker">{{ index + 1 }}</div>
        <div class="content">
          <div class="title">{{ anchor }}</div>
        </div>
      </li>
    </ol>
  </section>
</template>

<script setup lang="ts">
defineProps<{
  anchors: string[]
}>()
</script>

<style scoped>
.timeline {
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
  gap: 10px;
}

.item {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 10px;
  align-items: center;
}

.marker {
  width: 28px;
  height: 28px;
  border-radius: 999px;
  border: 1px solid #d1d5db;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  color: #374151;
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
