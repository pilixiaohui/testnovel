<template>
  <section class="panel">
    <CharacterCard
      v-for="character in characters"
      :key="character.id ?? character.name"
      :character="character"
    />
    <div v-if="characters.length === 0" class="empty">暂无角色</div>
  </section>
</template>

<script setup lang="ts">
import CharacterCard from './CharacterCard.vue'
import type { CharacterSheet } from '../../types/snowflake'

const props = defineProps<{
  characters: CharacterSheet[]
}>()

const { characters } = props
</script>

<style scoped>
.panel {
  display: grid;
  gap: 12px;
}

.empty {
  color: var(--color-muted);
}
</style>
