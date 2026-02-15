import { computed } from 'vue'
import { useSnowflakeStore } from '../stores/snowflake'

export const useSnowflake = () => {
  const store = useSnowflakeStore()

  const logline = computed(() => store.logline)
  const root = computed(() => store.root)
  const characters = computed(() => store.characters)
  const scenes = computed(() => store.scenes)
  const acts = computed(() => store.acts)
  const chapters = computed(() => store.chapters)
  const anchors = computed(() => store.anchors)

  const reset = () => {
    store.reset()
  }

  return {
    store,
    logline,
    root,
    characters,
    scenes,
    acts,
    chapters,
    anchors,
    reset,
  }
}
