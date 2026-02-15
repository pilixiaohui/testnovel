import './element_plus_style_mock'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import type { SnowflakeChapter } from '@/types/snowflake'
import { useSnowflakeStore } from '@/stores/snowflake'
import * as chapterApi from '@/api/chapter'
import * as snowflakeApi from '@/api/snowflake'
import EditorView from '../src/views/EditorView.vue'

vi.mock('@/api/chapter', () => ({
  reviewChapter: vi.fn(),
  renderChapter: vi.fn(),
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({
    params: { sceneId: 'scene-alpha' },
    query: { root_id: 'root-alpha', branch_id: 'branch-alpha' },
  }),
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
  }),
}))

vi.mock('@/api/branch', () => ({
  branchApi: {
    listBranches: vi.fn().mockResolvedValue(['main']),
    switchBranch: vi.fn(),
    getBranchHistory: vi.fn(),
    getRootSnapshot: vi.fn(),
    resetBranch: vi.fn(),
  },
}))

vi.mock('@/api/snowflake', () => ({
  snowflakeApi: {
    listActs: vi.fn().mockResolvedValue([]),
    listChapters: vi.fn().mockResolvedValue([]),
  },
}))

const chapterApiMock = vi.mocked(chapterApi) as unknown as {
  reviewChapter: ReturnType<typeof vi.fn>
}

const snowflakeApiMock = vi.mocked(snowflakeApi) as unknown as {
  snowflakeApi: {
    listActs: ReturnType<typeof vi.fn>
    listChapters: ReturnType<typeof vi.fn>
  }
}

const buildChapter = (overrides: Partial<SnowflakeChapter> = {}): SnowflakeChapter => ({
  id: 'chapter-1',
  act_id: 'act-1',
  sequence: 1,
  title: 'Chapter 1',
  focus: 'Focus',
  review_status: 'pending',
  ...overrides,
})

const setupEditor = (chapters: SnowflakeChapter[]) => {
  const pinia = createPinia()
  setActivePinia(pinia)
  snowflakeApiMock.snowflakeApi.listActs.mockResolvedValue([{ id: 'act-1' }])
  snowflakeApiMock.snowflakeApi.listChapters.mockResolvedValue(chapters)
  const store = useSnowflakeStore(pinia)
  store.steps.chapters = chapters
  const wrapper = mount(EditorView, { global: { plugins: [pinia] } })
  return { wrapper, store }
}

describe('M3-T2 chapter review UI', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders review buttons and pending status tag', () => {
    const { wrapper } = setupEditor([buildChapter()])

    const approveButton = wrapper.find('[data-test="chapter-approve"]')
    const rejectButton = wrapper.find('[data-test="chapter-reject"]')
    expect(approveButton.exists()).toBe(true)
    expect(rejectButton.exists()).toBe(true)

    const statusTag = wrapper.find('[data-test="chapter-review-status"]')
    expect(statusTag.text()).toBe('pending')
    expect(statusTag.attributes('type')).toBe('info')
  })

  it('approves chapter and updates status tag', async () => {
    chapterApiMock.reviewChapter.mockResolvedValue({
      id: 'chapter-1',
      review_status: 'approved',
    })
    const { wrapper } = setupEditor([buildChapter()])

    await wrapper.find('[data-test="chapter-approve"]').trigger('click')
    await flushPromises()

    expect(chapterApiMock.reviewChapter).toHaveBeenCalledWith('chapter-1', 'approved')

    const statusTag = wrapper.find('[data-test="chapter-review-status"]')
    expect(statusTag.text()).toBe('approved')
    expect(statusTag.attributes('type')).toBe('success')
  })

  it('rejects chapter and updates status tag', async () => {
    chapterApiMock.reviewChapter.mockResolvedValue({
      id: 'chapter-1',
      review_status: 'rejected',
    })
    const { wrapper } = setupEditor([buildChapter()])

    await wrapper.find('[data-test="chapter-reject"]').trigger('click')
    await flushPromises()

    expect(chapterApiMock.reviewChapter).toHaveBeenCalledWith('chapter-1', 'rejected')

    const statusTag = wrapper.find('[data-test="chapter-review-status"]')
    expect(statusTag.text()).toBe('rejected')
    expect(statusTag.attributes('type')).toBe('danger')
  })
})
