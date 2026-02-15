import { createRouter, createWebHistory } from 'vue-router'
import { useProjectStore } from '@/stores/project'
import HomeView from '../views/HomeView.vue'
import SnowflakeView from '../views/SnowflakeView.vue'
import SimulationView from '../views/SimulationView.vue'
import EditorView from '../views/EditorView.vue'
import WorldView from '../views/WorldView.vue'
import SettingsView from '../views/SettingsView.vue'

const routes = [
  {
    path: '/',
    name: 'home',
    component: HomeView,
  },
  {
    path: '/snowflake',
    name: 'snowflake',
    component: SnowflakeView,
  },
  {
    path: '/snowflake/:rootId',
    name: 'snowflake-root',
    component: SnowflakeView,
  },
  {
    path: '/simulation/:sceneId?',
    name: 'simulation',
    component: SimulationView,
  },
  {
    path: '/editor/:sceneId?',
    name: 'editor',
    component: EditorView,
  },
  {
    path: '/world',
    name: 'world',
    component: WorldView,
  },
  {
    path: '/settings',
    name: 'settings',
    component: SettingsView,
  },
]

const normalizeRouteValue = (value: unknown): string | undefined => {
  if (typeof value === 'string') {
    return value
  }
  if (Array.isArray(value) && value.length > 0 && typeof value[0] === 'string') {
    return value[0]
  }
  return undefined
}

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
})

router.beforeEach((to) => {
  const store = useProjectStore()
  return store.syncFromRoute({
    name: typeof to.name === 'string' ? to.name : undefined,
    params: {
      sceneId: normalizeRouteValue(to.params.sceneId),
      rootId: normalizeRouteValue(to.params.rootId),
      branchId: normalizeRouteValue(to.params.branchId),
    },
    query: {
      root_id: normalizeRouteValue(to.query.root_id),
      branch_id: normalizeRouteValue(to.query.branch_id),
    },
  })
})

export default router
