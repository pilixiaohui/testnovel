import type { Page, Route } from '@playwright/test'

type JsonObject = Record<string, unknown>

type ProjectSummary = {
  root_id: string
  name: string
  created_at: string
  logline: string
}

const ROOT_ID = 'root-wuxia'
const MAIN_BRANCH = 'main'
const REVIEW_BRANCH = 'review'
const PRIMARY_SCENE_ID = 'scene-01'

const createdAt = '2026-02-21T00:00:00Z'

const prompts = {
  step1: '请给出 10 条武侠故事一句话梗概。',
  step2: '围绕梗概写出三灾与主题结局。',
  step3: '为武侠故事生成角色小传。',
  step4: '生成场景清单，覆盖推进冲突。',
  step5: '按十章结构生成章节纲要。',
  step6: '生成章节锚点约束。',
}

export const wuxiaIdea =
  '以江湖门派纷争为背景，主角沈孤舟在十章内完成复仇与和解的武侠短篇。'

export const wuxiaLoglines = [
  '沈孤舟携残卷入江湖，十章追查师门血案。',
  '青锋断、旧誓在，少年剑客十章破局复仇。',
  '魔教与正道交锋，落魄弟子十章重铸侠义。',
  '一纸悬赏引发武林追杀，孤客十章守护真相。',
  '雪夜灭门后，沈孤舟十章踏遍江湖寻凶。',
  '双城对峙将启，剑客十章止战平怨。',
  '神兵出世前夜，沈孤舟十章断旧仇结新盟。',
  '掌门遗命现世，少年十章重整门规。',
  '黑市奇案牵出旧友，侠客十章救人与自救。',
  '江湖失序之年，孤舟十章以义服众。',
]

export const wuxiaRoot = {
  logline: wuxiaLoglines[0],
  three_disasters: ['师门覆灭', '挚友背离', '宗门内乱'],
  ending: '沈孤舟放下私怨，重建山门秩序',
  theme: '侠义在于守护而非杀戮',
}

export const wuxiaCharacters = [
  {
    entity_id: 'char-shen',
    id: 'char-shen',
    name: '沈孤舟',
    ambition: '查明灭门真相并重振师门',
    conflict: '复仇执念与侠义底线冲突',
    epiphany: '真正的胜利是止戈',
    voice_dna: '冷峻内敛',
    one_sentence_summary: '少年剑客在复仇路上学会守护江湖。',
  },
  {
    entity_id: 'char-lin',
    id: 'char-lin',
    name: '林晚晴',
    ambition: '保护百姓远离门派纷争',
    conflict: '家族立场与个人信念冲突',
    epiphany: '不再沉默，主动调停',
    voice_dna: '温和果断',
    one_sentence_summary: '医者少女在纷争中成为和解桥梁。',
  },
  {
    entity_id: 'char-xie',
    id: 'char-xie',
    name: '谢无咎',
    ambition: '夺取盟主之位统一江湖',
    conflict: '掌控欲与旧友情义冲突',
    epiphany: '承认权力无法换来敬重',
    voice_dna: '凌厉讥诮',
    one_sentence_summary: '昔日同门在权力与情义间反复摇摆。',
  },
]

export const wuxiaScenes = Array.from({ length: 10 }, (_, index) => ({
  id: `scene-${String(index + 1).padStart(2, '0')}`,
  title: `第${index + 1}场：江湖风起`,
  branch_id: MAIN_BRANCH,
  parent_act_id: index < 5 ? 'act-1' : 'act-2',
  pov_character_id: index % 2 === 0 ? 'char-shen' : 'char-lin',
  expected_outcome: `主角推进第 ${index + 1} 章主线`,
  conflict_type: index % 2 === 0 ? 'external' : 'internal',
  actual_outcome: '待定',
  logic_exception: false,
  is_dirty: false,
  sequence_index: index + 1,
}))

export const wuxiaActs = [
  {
    id: 'act-1',
    root_id: ROOT_ID,
    sequence: 1,
    title: '第一幕：旧案重启',
    purpose: '建立冲突与人物关系',
    tone: '压抑紧绷',
  },
  {
    id: 'act-2',
    root_id: ROOT_ID,
    sequence: 2,
    title: '第二幕：止戈决断',
    purpose: '收束冲突并完成角色成长',
    tone: '激烈克制',
  },
]

export const wuxiaChapters = Array.from({ length: 10 }, (_, index) => ({
  id: `chapter-${String(index + 1).padStart(2, '0')}`,
  act_id: index < 5 ? 'act-1' : 'act-2',
  sequence: index + 1,
  title: `第${index + 1}章`,
  focus: `推进第 ${index + 1} 章关键转折`,
  pov_character_id: index % 2 === 0 ? 'char-shen' : 'char-lin',
  word_count: 2000,
  review_status: 'pending',
}))

export const wuxiaAnchors = Array.from({ length: 10 }, (_, index) => ({
  id: `anchor-${String(index + 1).padStart(2, '0')}`,
  anchor_type: 'chapter_goal',
  description: `第${index + 1}章必须完成主线推进`,
  constraint_type: 'hard',
  required_conditions: ['角色动机一致', '冲突有效推进'],
  achieved: false,
}))

const buildChapterRender = (chapterId: string) => {
  const chapterNumber = chapterId.slice(-2)
  return `第${chapterNumber}章\n${'侠'.repeat(2000)}`
}

const responseJson = async (route: Route, payload: unknown, status = 200) => {
  await route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(payload),
  })
}

const parseBody = (route: Route): JsonObject => {
  const raw = route.request().postData()
  if (!raw) {
    return {}
  }
  return JSON.parse(raw) as JsonObject
}

export const installWuxiaJourneyMocks = async (page: Page) => {
  const projects: ProjectSummary[] = []
  const reviewStatusByChapter = new Map(wuxiaChapters.map((chapter) => [chapter.id, 'pending']))
  const entities = [
    {
      id: 'entity-shen',
      created_at: createdAt,
      name: '沈孤舟',
      type: 'character',
      position: { x: 0, y: 0, z: 0 },
    },
    {
      id: 'entity-mountain',
      created_at: createdAt,
      name: '青岳山门',
      type: 'location',
      position: { x: 1, y: 0, z: 0 },
    },
  ]
  let currentBranch = MAIN_BRANCH
  let llmSettings = {
    llm_config: {
      model: 'gemini-1.5-pro',
      temperature: 0.7,
      max_tokens: 2048,
      timeout: 60,
      system_instruction: 'write wuxia in concise style',
    },
    system_config: {
      auto_save: true,
      ui_density: 'comfortable',
    },
  }

  await page.route('**/api/v1/**', async (route) => {
    const request = route.request()
    const method = request.method()
    const url = new URL(request.url())
    const path = url.pathname

    if (path === '/api/v1/roots' && method === 'GET') {
      await responseJson(route, { roots: projects })
      return
    }

    if (path === '/api/v1/roots' && method === 'POST') {
      const body = parseBody(route)
      const name = typeof body.name === 'string' ? body.name : ''
      const created: ProjectSummary = {
        root_id: ROOT_ID,
        name,
        created_at: createdAt,
        logline: '',
      }
      projects.push(created)
      await responseJson(route, created)
      return
    }

    if (path === `/api/v1/roots/${ROOT_ID}` && method === 'GET') {
      await responseJson(route, {
        root_id: ROOT_ID,
        branch_id: currentBranch,
        scene_id: PRIMARY_SCENE_ID,
        logline: wuxiaRoot.logline,
        theme: wuxiaRoot.theme,
        ending: wuxiaRoot.ending,
        three_disasters: wuxiaRoot.three_disasters,
        characters: wuxiaCharacters,
        scenes: wuxiaScenes,
        created_at: createdAt,
        relations: [{ from_entity_id: 'entity-shen', to_entity_id: 'entity-mountain' }],
      })
      return
    }

    if (path === `/api/v1/roots/${ROOT_ID}/snowflake/prompts` && method === 'GET') {
      await responseJson(route, prompts)
      return
    }

    if (path === `/api/v1/roots/${ROOT_ID}/snowflake/prompts` && method === 'PUT') {
      await responseJson(route, parseBody(route))
      return
    }

    if (path === `/api/v1/roots/${ROOT_ID}/snowflake/prompts/reset` && method === 'POST') {
      await responseJson(route, prompts)
      return
    }

    if (path === '/api/v1/snowflake/step1' && method === 'POST') {
      await responseJson(route, wuxiaLoglines)
      return
    }

    if (path === '/api/v1/snowflake/step2' && method === 'POST') {
      await responseJson(route, wuxiaRoot)
      return
    }

    if (path === '/api/v1/snowflake/step3' && method === 'POST') {
      await responseJson(route, wuxiaCharacters)
      return
    }

    if (path === '/api/v1/snowflake/step4' && method === 'POST') {
      await responseJson(route, {
        root_id: ROOT_ID,
        branch_id: MAIN_BRANCH,
        scenes: wuxiaScenes,
      })
      return
    }

    if (path === '/api/v1/snowflake/step5a' && method === 'POST') {
      await responseJson(route, wuxiaActs)
      return
    }

    if (path === '/api/v1/snowflake/step5b' && method === 'POST') {
      await responseJson(route, wuxiaChapters)
      return
    }

    if (path === `/api/v1/roots/${ROOT_ID}/snowflake/steps` && method === 'POST') {
      await responseJson(route, { ok: true })
      return
    }

    if (path === `/api/v1/roots/${ROOT_ID}/anchors` && method === 'POST') {
      await responseJson(route, wuxiaAnchors)
      return
    }

    if (path === `/api/v1/roots/${ROOT_ID}/anchors` && method === 'GET') {
      await responseJson(route, wuxiaAnchors)
      return
    }

    if (path === `/api/v1/roots/${ROOT_ID}/subplots` && method === 'GET') {
      await responseJson(route, ['沈孤舟与林晚晴的信任线'])
      return
    }

    if (path === `/api/v1/roots/${ROOT_ID}/acts` && method === 'GET') {
      await responseJson(route, wuxiaActs)
      return
    }

    if (path.startsWith('/api/v1/acts/') && path.endsWith('/chapters') && method === 'GET') {
      const actId = path.split('/')[4]
      const chapters = wuxiaChapters
        .filter((chapter) => chapter.act_id === actId)
        .map((chapter) => ({
          ...chapter,
          review_status: reviewStatusByChapter.get(chapter.id) || 'pending',
        }))
      await responseJson(route, chapters)
      return
    }

    if (path.startsWith('/api/v1/chapters/') && path.endsWith('/render') && method === 'POST') {
      const chapterId = path.split('/')[4]
      await responseJson(route, {
        rendered_content: buildChapterRender(chapterId),
        quality_scores: {
          coherence: 0.92,
          pacing: 0.9,
          character_consistency: 0.91,
        },
      })
      return
    }

    if (path.startsWith('/api/v1/chapters/') && path.endsWith('/review') && method === 'POST') {
      const chapterId = path.split('/')[4]
      const body = parseBody(route)
      const status = typeof body.status === 'string' ? body.status : 'pending'
      reviewStatusByChapter.set(chapterId, status)
      await responseJson(route, { id: chapterId, review_status: status })
      return
    }

    if (path.startsWith('/api/v1/scenes/') && path.endsWith('/context') && method === 'GET') {
      const sceneId = path.split('/')[4]
      await responseJson(route, {
        id: sceneId,
        title: '夜雨入城',
        summary: '沈孤舟潜入城中调查旧案线索。',
        outcome: 'success',
        content: '旧案线索逐步浮现。',
        scene_entities: [{ entity_id: 'entity-shen' }, { entity_id: 'entity-mountain' }],
        world_state: { distance: 1, tension: 'high' },
      })
      return
    }

    if (path.startsWith('/api/v1/scenes/') && path.endsWith('/render') && method === 'POST') {
      await responseJson(route, { content: '渲染后场景正文：江湖雨夜，剑光如雪。' })
      return
    }

    if (path.startsWith('/api/v1/scenes/') && path.endsWith('/complete') && method === 'POST') {
      await responseJson(route, { status: 'ok' })
      return
    }

    if (path.startsWith('/api/v1/scenes/') && path.endsWith('/diff') && method === 'GET') {
      await responseJson(route, { diff: '- 旧稿\n+ 新稿' })
      return
    }

    if (path === `/api/v1/roots/${ROOT_ID}/branches` && method === 'GET') {
      await responseJson(route, [MAIN_BRANCH, REVIEW_BRANCH])
      return
    }

    if (path.startsWith(`/api/v1/roots/${ROOT_ID}/branches/`) && path.endsWith('/switch') && method === 'POST') {
      currentBranch = path.split('/')[6] || MAIN_BRANCH
      await responseJson(route, { root_id: ROOT_ID, branch_id: currentBranch })
      return
    }

    if (path.startsWith(`/api/v1/roots/${ROOT_ID}/branches/`) && path.endsWith('/history') && method === 'GET') {
      await responseJson(route, [
        { id: 'commit-2', parent_id: 'commit-1', message: 'review update', created_at: createdAt },
        { id: 'commit-1', parent_id: null, message: 'initial', created_at: createdAt },
      ])
      return
    }

    if (path.startsWith(`/api/v1/roots/${ROOT_ID}/branches/`) && path.endsWith('/reset') && method === 'POST') {
      await responseJson(route, { status: 'ok' })
      return
    }

    if (path.startsWith(`/api/v1/roots/${ROOT_ID}/branches/`) && path.endsWith('/commit') && method === 'POST') {
      await responseJson(route, { id: 'commit-3' })
      return
    }

    if (path === '/api/v1/simulation/agents' && method === 'GET') {
      await responseJson(route, {
        agents: [{ id: 'agent-shen' }],
        convergence: {
          score: 0.35,
          check: {
            next_anchor_id: 'anchor-06',
            distance: 0.55,
            convergence_needed: true,
            suggested_action: '推进门派对峙并揭示真相',
          },
        },
      })
      return
    }

    if (path === '/api/v1/entities/agent-shen/agent/state' && method === 'GET') {
      await responseJson(route, {
        id: 'agent-shen',
        character_id: 'char-shen',
        branch_id: currentBranch,
        beliefs: { resolve: '坚定' },
        desires: [],
        intentions: [],
        memory: [],
        private_knowledge: {},
        last_updated_scene: 6,
        version: 3,
      })
      return
    }

    if (path === `/api/v1/simulation/logs/${PRIMARY_SCENE_ID}` && method === 'GET') {
      await responseJson(route, [
        {
          round_id: 'round-1',
          agent_actions: [],
          dm_arbitration: {
            round_id: 'round-1',
            action_results: [],
            conflicts_resolved: [],
            environment_changes: [],
          },
          narrative_events: [],
          sensory_seeds: [],
          convergence_score: 0.42,
          drama_score: 0.61,
          info_gain: 0.44,
          stagnation_count: 0,
        },
      ])
      return
    }

    if (path === '/api/v1/simulation/round' && method === 'POST') {
      await responseJson(route, {
        round_id: 'round-2',
        agent_actions: [
          {
            agent_id: 'agent-shen',
            internal_thought: '必须先保住盟约',
            action_type: 'negotiate',
            action_target: '长老会',
            action_description: '提出停战条件',
          },
        ],
        dm_arbitration: {
          round_id: 'round-2',
          action_results: [],
          conflicts_resolved: [],
          environment_changes: [],
        },
        narrative_events: [{ event: 'alliance reached' }],
        sensory_seeds: [{ type: 'sound', detail: '钟声沉鸣' }],
        convergence_score: 0.82,
        drama_score: 0.67,
        info_gain: 0.59,
        stagnation_count: 0,
      })
      return
    }

    if (path === '/api/v1/simulation/scene' && method === 'POST') {
      await responseJson(route, { status: 'running' })
      return
    }

    if (path === `/api/v1/roots/${ROOT_ID}/entities` && method === 'GET') {
      await responseJson(route, entities)
      return
    }

    if (path === `/api/v1/roots/${ROOT_ID}/entities` && method === 'POST') {
      await responseJson(route, { id: 'entity-new' })
      return
    }

    if (path.startsWith(`/api/v1/roots/${ROOT_ID}/entities/`) && method === 'PUT') {
      await responseJson(route, { id: path.split('/')[6] })
      return
    }

    if (path.startsWith(`/api/v1/roots/${ROOT_ID}/entities/`) && method === 'DELETE') {
      await responseJson(route, { id: path.split('/')[6] })
      return
    }

    if (path === '/api/v1/settings/llm' && method === 'GET') {
      await responseJson(route, llmSettings)
      return
    }

    if (path === '/api/v1/settings/llm' && method === 'PUT') {
      llmSettings = parseBody(route) as typeof llmSettings
      await responseJson(route, llmSettings)
      return
    }

    if (path === '/api/v1/state/extract' && method === 'POST') {
      await responseJson(route, [
        {
          entity_id: 'entity-shen',
          confidence: 0.93,
          semantic_states_patch: { morale: 'stable' },
        },
      ])
      return
    }

    if (path === '/api/v1/state/commit' && method === 'POST') {
      await responseJson(route, { ok: true })
      return
    }

    await route.abort()
  })
}

export const wuxiaContext = {
  rootId: ROOT_ID,
  branchId: MAIN_BRANCH,
  sceneId: PRIMARY_SCENE_ID,
}
