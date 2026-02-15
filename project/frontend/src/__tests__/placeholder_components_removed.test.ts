import { describe, expect, it } from 'vitest'
import { existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const __dirname = dirname(fileURLToPath(import.meta.url))
const srcRoot = resolve(__dirname, '..')
const componentsRoot = resolve(srcRoot, 'components')

const placeholderComponents = [
  'common/EmptyState.vue',
  'EntityBadge.vue',
  'SimulationStatus.vue',
  'FilterBar.vue',
  'SearchBox.vue',
  'SimulationControls.vue',
  'SceneTimeline.vue',
  'ModalDialog.vue',
  'PageHeader.vue',
  'LlmStatus.vue',
  'ProjectHeader.vue',
  'CommitList.vue',
  'SubplotList.vue',
  'SnowflakeStepCard.vue',
  'ProgressBar.vue',
  'SectionTitle.vue',
  'SceneToolbar.vue',
  'WorldCard.vue',
  'LoadingIndicator.vue',
  'BeatCard.vue',
  'StatusBadge.vue',
  'BranchList.vue',
  'ErrorBanner.vue',
  'MetricsPanel.vue',
  'WorldToolbar.vue',
  'FeedbackForm.vue',
]

describe('M1-T4 empty components cleanup', () => {
  it('removes placeholder components', () => {
    const remaining = placeholderComponents.filter((relativePath) =>
      existsSync(resolve(componentsRoot, relativePath)),
    )

    expect(remaining).toEqual([])
  })
})
