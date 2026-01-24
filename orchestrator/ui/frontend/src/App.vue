<template>
  <header>
    <div class="brand">Orchestrator</div>
    <div class="pill">
      <div class="dot" :style="{ background: phaseDotColor }"></div>
      <div>
        <div class="k">phase</div>
        <div class="v">{{ phase }}</div>
      </div>
    </div>
    <div class="stat">
      <div class="k">iteration</div>
      <div class="v">{{ iteration }}</div>
    </div>
    <div class="stat">
      <div class="k">agent</div>
      <div class="v">{{ agent }}</div>
    </div>
    <div class="stat">
      <div class="k">main_session_id</div>
      <div class="v">{{ mainSessionId }}</div>
    </div>
    <div style="margin-left: auto" class="row">
      <button class="primary" :disabled="!canStart" @click="startRun">Start</button>
      <button :disabled="!canResume" @click="resumeRun">Resume</button>
      <button :disabled="!canStart" @click="openTaskModal">New Task</button>
      <button :disabled="!canReset" @click="resetRun">重置</button>
      <button :disabled="!canInterrupt" @click="interruptRun">Interrupt</button>
      <div class="muted">{{ runCtlStatus }}</div>
    </div>
  </header>

  <div class="modal" :class="{ hidden: !showTaskModal }" aria-hidden="true">
    <div class="modalBackdrop" @click="closeTaskModal"></div>
    <div class="modalContent card" @click.stop>
      <div class="row" style="justify-content: space-between">
        <div>
          <div><b>New Task</b></div>
          <div class="muted">
            请输入本次任务目标（将追加写入 <code>memory/project_history.md</code> 并触发新会话；MAIN
            下一轮会注入 history 看到）。
          </div>
        </div>
        <button @click="closeTaskModal">Close</button>
      </div>
      <div style="height: 10px"></div>
      <textarea
        ref="taskGoalInputRef"
        v-model="taskGoalInput"
        class="mono"
        placeholder="例如：修复 XXX，新增 YYY，验收标准：..."
        @keydown="onTaskGoalKeydown"
      ></textarea>
      <div style="height: 10px"></div>
      <div class="row">
        <select multiple v-model="taskDocRefs" class="docSelect">
          <option v-for="doc in uploadedDocs" :key="doc.path" :value="doc.path">@doc:{{ doc.path }}</option>
        </select>
        <button :disabled="taskDocRefs.length === 0" @click="insertTaskDocRefs">插入引用</button>
        <button @click="fetchUploadedDocs">刷新文档</button>
      </div>
      <div class="muted">引用格式：@doc:category/filename.md</div>
      <div style="height: 10px"></div>
      <div class="resetOptions">
        <div class="muted">重置选项（勾选后将清空对应内容）：</div>
        <label class="resetOption">
          <input type="checkbox" v-model="resetDevPlan" />
          <span>重置 dev_plan.md（开发计划）</span>
        </label>
        <label class="resetOption">
          <input type="checkbox" v-model="resetProjectHistory" />
          <span>重置 project_history.md（项目历史）</span>
        </label>
      </div>
      <div style="height: 10px"></div>
      <div class="row">
        <button class="primary" @click="submitNewTask">Start New Task</button>
        <div class="muted">{{ taskModalStatus }}</div>
      </div>
    </div>
  </div>

  <main>
    <section id="logsPane" class="logPane">
      <div class="paneHeader">
        <h2>Logs</h2>
        <div class="row">
          <label class="muted">
            <input type="checkbox" v-model="autoScroll" /> 自动滚动
          </label>
          <button @click="clearLog">Clear</button>
          <button @click="copyLog">Copy</button>
          <div class="muted">{{ logStatus }}</div>
        </div>
      </div>
      <div class="logSplit">
        <div class="logSummaryPane">
          <div class="logSummaryHeader">
            <div class="muted">日志摘要</div>
            <div class="row">
              <button @click="loadLogSummaryConfig">加载配置</button>
              <button class="primary" @click="saveLogSummaryConfig">保存配置</button>
              <button @click="summarizeNow" :disabled="logSummaryInFlight">立即摘要</button>
              <label class="muted">
                <input type="checkbox" v-model="logSummaryAuto" /> 自动摘要
              </label>
              <span class="muted">待摘要 {{ logSummaryBufferLines }} 行</span>
              <span class="muted">{{ logSummaryStatus }}</span>
            </div>
          </div>
          <div class="logSummaryConfig">
            <div class="configGrid">
              <div class="configField">
                <div class="k">Base URL</div>
                <input v-model="logSummaryConfig.base_url" type="text" placeholder="https://api.toponeapi.top" />
              </div>
              <div class="configField">
                <div class="k">Model</div>
                <input v-model="logSummaryConfig.model" type="text" placeholder="gemini-3-pro-preview-11-2025" />
              </div>
              <div class="configField">
                <div class="k">API Key</div>
                <input v-model="logSummaryConfig.api_key" type="password" placeholder="YOUR_API_KEY" />
              </div>
              <div class="configField">
                <div class="k">触发阈值(行)</div>
                <input v-model.number="logSummaryThreshold" type="number" min="10" />
              </div>
            </div>
          </div>
          <div class="logSummaryList">
            <div v-if="logSummaryItems.length === 0" class="muted">暂无摘要</div>
            <div v-for="item in logSummaryItems" :key="item.id" class="logSummaryCard">
              <div class="row summaryMeta">
                <span class="pill">#{{ item.id }}</span>
                <span class="muted">{{ item.created_at }}</span>
                <span class="pill">{{ item.line_count }} 行</span>
              </div>
              <pre class="logSummaryText">{{ item.summary }}</pre>
            </div>
          </div>
        </div>
        <div class="logStreamPane">
          <pre id="log" ref="logRef">{{ logText }}</pre>
        </div>
      </div>
    </section>

    <section id="rightPane">
      <div class="tabs">
        <button
          v-for="tab in tabs"
          :key="tab.id"
          class="tab"
          :class="{ active: activeTab === tab.id, badge: tab.id === 'decision' && decisionBadge }"
          @click="setActiveTab(tab.id)"
        >
          {{ tab.label }}
        </button>
      </div>

      <div class="panel" :class="{ hidden: activeTab !== 'decision' }">
        <div class="card">
          <template v-if="!decisionData">
            <div class="muted">暂无需要确认的抉择。</div>
          </template>
          <template v-else>
            <div class="muted">需要你的抉择</div>
            <div style="height: 8px"></div>
            <div><b>{{ decisionTitle }}</b></div>
            <div class="muted">{{ decisionReason }}</div>
            <div style="height: 10px"></div>
            <div>{{ decisionQuestion }}</div>
            <div style="height: 10px"></div>
            <div id="optList">
              <label v-for="opt in decisionOptions" :key="opt.option_id" class="opt">
                <input type="radio" name="opt" :value="opt.option_id" v-model="selectedOption" />
                <span>
                  <code>{{ opt.option_id }}</code> - {{ opt.description }}
                  <span v-if="decisionRecommended === opt.option_id" class="muted">(recommended)</span>
                </span>
              </label>
            </div>
            <div style="height: 10px"></div>
            <textarea
              v-model="decisionComment"
              placeholder="补充说明（可选）"
              class="mono"
            ></textarea>
            <div style="height: 10px"></div>
            <div class="row">
              <button class="primary" @click="submitDecision">Submit</button>
              <div class="muted">{{ decisionStatus }}</div>
            </div>
          </template>
        </div>
      </div>

      <div v-if="activeTab === 'progress'" class="panel">
        <div class="card">
          <div class="row" style="justify-content: space-between">
            <div class="muted">进度概览</div>
            <div class="muted">{{ progressStatus }}</div>
          </div>
          <div style="height: 8px"></div>
          <template v-if="progress && progress.total_tasks > 0">
            <div class="progressBar">
              <div class="progressBarDone" :style="{ width: `${progress.completion_percentage}%` }"></div>
              <div class="progressBarVerified" :style="{ width: `${progress.verification_percentage}%` }"></div>
            </div>
            <div class="progressLegend">
              <span class="pill">完成 {{ progress.completion_percentage.toFixed(1) }}%</span>
              <span class="pill">验证 {{ progress.verification_percentage.toFixed(1) }}%</span>
              <span class="muted" v-if="currentMilestoneLabel">当前：{{ currentMilestoneLabel }}</span>
            </div>
            <div class="progressStats">
              <div class="statCard">
                <div class="k">total</div>
                <div class="v">{{ progress.total_tasks }}</div>
              </div>
              <div class="statCard">
                <div class="k">done</div>
                <div class="v">{{ progress.completed_tasks }}</div>
              </div>
              <div class="statCard">
                <div class="k">verified</div>
                <div class="v">{{ progress.verified_tasks }}</div>
              </div>
              <div class="statCard">
                <div class="k">doing</div>
                <div class="v">{{ progress.in_progress_tasks }}</div>
              </div>
              <div class="statCard">
                <div class="k">blocked</div>
                <div class="v">{{ progress.blocked_tasks }}</div>
              </div>
              <div class="statCard">
                <div class="k">todo</div>
                <div class="v">{{ progress.todo_tasks }}</div>
              </div>
            </div>
            <div style="height: 12px"></div>
            <div class="muted">里程碑进度</div>
            <div class="milestoneList">
              <div v-for="m in progress.milestones" :key="m.milestone_id" class="milestoneCard">
                <div class="row" style="justify-content: space-between">
                  <div>
                    <b>{{ m.milestone_id }}</b>
                    <span class="muted"> {{ m.milestone_name }}</span>
                  </div>
                  <span class="pill">{{ m.percentage.toFixed(1) }}%</span>
                </div>
                <div class="progressBar small">
                  <div class="progressBarDone" :style="{ width: `${m.percentage}%` }"></div>
                </div>
                <div class="muted">
                  {{ m.completed_tasks }}/{{ m.total_tasks }} 完成，{{ m.verified_tasks }} 已验证
                </div>
                <div v-if="tasksByMilestone(m.milestone_id).length" class="milestoneTasks">
                  <div v-for="task in tasksByMilestone(m.milestone_id)" :key="task.task_id" class="milestoneTask">
                    <span class="taskId">{{ task.task_id }}</span>
                    <span class="taskTitle">{{ task.title }}</span>
                    <span class="pill statusPill" :class="`status-${task.status.toLowerCase()}`">{{ task.status }}</span>
                  </div>
                </div>
              </div>
            </div>
          </template>
          <div v-else class="muted">暂无任务</div>
        </div>
      </div>

      <div v-if="activeTab === 'summary'" class="panel">
        <div class="card">
          <div class="muted">迭代摘要</div>
          <div style="height: 8px"></div>
          <div class="summaryList">
            <div v-if="summaryItems.length === 0" class="muted">暂无摘要</div>
            <div v-for="item in summaryItems" :key="item.iteration" class="summaryCard">
              <div class="summaryHeader">
                <div>
                  <div class="summaryTitle">
                    <b>Iteration {{ item.iteration }}</b>
                  </div>
                  <div class="muted">agent: {{ item.subagent.agent }}</div>
                </div>
                <div v-if="item.progress" class="summaryBadge">
                  完成 {{ item.progress.completion_percentage.toFixed(1) }}%
                </div>
              </div>
              <div class="summarySection">
                <div class="summaryLabel">概览</div>
                <div class="summaryValue">{{ item.summary }}</div>
              </div>
              <div class="summarySection">
                <div class="summaryLabel">MAIN 决策</div>
                <div class="summaryValue">
                  <code>{{ item.main_decision.next_agent }}</code> - {{ item.main_decision.reason }}
                </div>
              </div>
              <div v-if="item.main_decision.next_agent === 'USER'" class="summarySection">
                <div class="summaryLabel">抉择</div>
                <div class="summaryValue">
                  {{ item.main_decision.decision_title }} / {{ item.main_decision.question }}
                  <span v-if="item.main_decision.recommended_option_id" class="muted">
                    推荐: {{ item.main_decision.recommended_option_id }}
                  </span>
                </div>
              </div>
              <div class="summarySection">
                <div class="summaryLabel">子代理</div>
                <div class="summaryValue">
                  <code>{{ item.subagent.agent }}</code>
                  <div class="muted">任务: {{ item.subagent.task_summary }}</div>
                  <div class="muted">报告: {{ item.subagent.report_summary }}</div>
                </div>
              </div>
              <div v-if="item.progress" class="summarySection">
                <div class="summaryLabel">进度</div>
                <div class="summaryValue">
                  <div class="progressBar small">
                    <div class="progressBarDone" :style="{ width: `${item.progress.completion_percentage}%` }"></div>
                    <div class="progressBarVerified" :style="{ width: `${item.progress.verification_percentage}%` }"></div>
                  </div>
                  <div class="muted">
                    完成 {{ item.progress.completed_tasks }}/{{ item.progress.total_tasks }}，
                    验证 {{ item.progress.verified_tasks }}，
                    当前 {{ item.progress.current_milestone || '-' }}
                  </div>
                </div>
              </div>
              <div class="summarySection">
                <div class="summaryLabel">步骤</div>
                <div class="timeline">
                  <div v-for="step in item.steps" :key="step.step" class="timelineItem">
                    <div class="timelineDot"></div>
                    <div class="timelineContent">
                      <code>{{ step.actor }}</code> {{ step.detail }}
                    </div>
                  </div>
                </div>
              </div>
              <div v-if="item.artifacts" class="summaryArtifacts">
                artifacts: {{ JSON.stringify(item.artifacts) }}
              </div>
            </div>
          </div>
        </div>
      </div>

      <div v-if="activeTab === 'documents'" class="panel">
        <div class="card">
          <div class="row" style="justify-content: space-between">
            <div class="muted">文档管理</div>
            <div class="muted">{{ docsStatus }}</div>
          </div>
          <div style="height: 8px"></div>
          <div class="row">
            <select v-model="uploadCategory">
              <option value="requirements">requirements</option>
              <option value="specs">specs</option>
              <option value="references">references</option>
            </select>
            <input type="file" accept=".md" @change="onUploadFileChange" />
            <button class="primary" :disabled="!uploadFile" @click="uploadDoc">Upload</button>
            <button @click="fetchUploadedDocs">Refresh</button>
          </div>
          <div style="height: 10px"></div>
          <div class="docList">
            <div v-if="uploadedDocs.length === 0" class="muted">暂无文档</div>
            <div v-for="doc in uploadedDocs" :key="doc.path" class="docItem">
              <div class="docMeta">
                <div><code>{{ doc.path }}</code></div>
                <div class="muted">{{ doc.size }} bytes · {{ doc.upload_time }}</div>
              </div>
              <div class="row">
                <button @click="copyDocRef(doc)">Copy @doc</button>
                <button @click="addDocToFinishReview(doc)">加入验收</button>
                <button class="danger" @click="deleteDoc(doc)">Delete</button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="panel" :class="{ hidden: activeTab !== 'message' }">
        <div class="card">
          <div class="muted">
            发送给系统的用户消息（将追加写入 <code>memory/project_history.md</code>，MAIN 下一轮会看到）。快捷键：
            <span class="kbd">Ctrl</span> + <span class="kbd">Enter</span> 发送
          </div>
          <div style="height: 8px"></div>
          <div class="row">
            <select multiple v-model="messageDocRefs" class="docSelect">
              <option v-for="doc in uploadedDocs" :key="doc.path" :value="doc.path">@doc:{{ doc.path }}</option>
            </select>
            <button :disabled="messageDocRefs.length === 0" @click="insertMessageDocRefs">插入引用</button>
            <button @click="fetchUploadedDocs">刷新文档</button>
          </div>
          <div class="muted">引用格式：@doc:category/filename.md</div>
          <div style="height: 8px"></div>
          <textarea
            ref="messageInputRef"
            v-model="messageInput"
            placeholder="输入你的补充说明/偏好/约束..."
            class="mono"
            @keydown="onMessageKeydown"
          ></textarea>
          <div style="height: 8px"></div>
          <div class="row">
            <button class="primary" @click="sendMessage">Send</button>
            <div class="muted">{{ msgStatus }}</div>
          </div>
        </div>
      </div>

      <div class="panel" :class="{ hidden: activeTab !== 'files' }">
        <div class="card">
          <div class="muted">查看/编辑项目内的 md 文件（运行中只读）</div>
          <div style="height: 8px"></div>
          <div class="row">
            <button @click="refreshFiles">Refresh</button>
            <button @click="quickOpen('orchestrator/memory/global_context.md')">Open global_context</button>
            <button @click="quickOpen('orchestrator/memory/dev_plan.md')">Open dev_plan</button>
            <button @click="quickOpen('orchestrator/memory/project_history.md')">Open project_history</button>
            <div class="muted">{{ fileStatus }}</div>
          </div>
          <div class="muted">
            {{ runLocked ? '运行中：md 文件编辑已锁定（只读）。如需修改，请 Interrupt 后再保存。' : '' }}
          </div>
          <div style="height: 10px"></div>
          <div class="split">
            <select v-model="selectedFile" @change="loadSelectedFile">
              <option v-for="path in mdFiles" :key="path" :value="path">{{ path }}</option>
            </select>
            <div class="fileMeta">
              <div class="muted">loaded: <code>{{ loadedFilePath || '-' }}</code></div>
              <div class="muted">{{ fileDirty ? 'unsaved changes' : '' }}</div>
            </div>
            <textarea
              v-model="fileContent"
              placeholder="选择文件后自动加载..."
              class="mono"
              :readonly="runLocked"
              @input="onFileInput"
            ></textarea>
            <div class="row">
              <button @click="loadSelectedFile">Reload</button>
              <button class="primary" :disabled="runLocked || !fileDirty" @click="saveSelectedFile">Save</button>
            </div>
          </div>
        </div>
      </div>

      <div v-if="activeTab === 'state'" class="panel">
        <div class="card">
          <div class="muted">Agent State（只读 JSON）</div>
          <div style="height: 8px"></div>
          <pre>{{ stateJson }}</pre>
        </div>
      </div>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, reactive, ref } from 'vue';
import type {
  IterationSummary,
  MainDecision,
  ProgressInfo,
  UiState,
  UploadedDocument,
  UserDecisionOption
} from './types';

type LogSummaryItem = {
  id: number;
  created_at: string;
  line_count: number;
  summary: string;
};

const logOffset = ref(0);
const logText = ref('');
const autoScroll = ref(true);
const logStatus = ref('');
const logSummaryStatus = ref('');
const logSummaryAuto = ref(true);
const logSummaryThreshold = ref(80);
const logSummaryBuffer = ref('');
const logSummaryBufferLines = ref(0);
const logSummaryItems = ref<LogSummaryItem[]>([]);
const logSummaryConfig = reactive({
  base_url: '',
  api_key: '',
  model: ''
});
const logSummaryInFlight = ref(false);
const runCtlStatus = ref('');
const msgStatus = ref('');
const decisionStatus = ref('');
const fileStatus = ref('');
const taskModalStatus = ref('');
const progressStatus = ref('');
const docsStatus = ref('');

const showTaskModal = ref(false);
const taskGoalInput = ref('');
const resetDevPlan = ref(false);
const resetProjectHistory = ref(false);
const messageInput = ref('');
const activeTab = ref<'decision' | 'progress' | 'summary' | 'documents' | 'message' | 'files' | 'state'>('decision');

const state = ref<UiState>({});
const decisionData = ref<MainDecision | null>(null);
const lastDecisionKey = ref<string | null>(null);
const selectedOption = ref('');
const decisionComment = ref('');

const mdFiles = ref<string[]>([]);
const selectedFile = ref('');
const loadedFilePath = ref('');
const fileContent = ref('');
const fileDirty = ref(false);

const progress = ref<ProgressInfo | null>(null);
const uploadedDocs = ref<UploadedDocument[]>([]);
const uploadCategory = ref('requirements');
const uploadFile = ref<File | null>(null);
const taskDocRefs = ref<string[]>([]);
const messageDocRefs = ref<string[]>([]);

const logRef = ref<HTMLElement | null>(null);
const taskGoalInputRef = ref<HTMLTextAreaElement | null>(null);
const messageInputRef = ref<HTMLTextAreaElement | null>(null);

const currentMilestoneLabel = computed(() => {
  const milestoneId = progress.value?.current_milestone;
  if (!milestoneId) {
    return '';
  }
  const milestone = progress.value?.milestones.find((item) => item.milestone_id === milestoneId);
  return milestone ? `${milestone.milestone_id} ${milestone.milestone_name}` : milestoneId;
});

function tasksByMilestone(milestoneId: string) {
  if (!progress.value) {
    throw new Error('progress is required');
  }
  return progress.value.tasks.filter((task) => task.milestone_id === milestoneId);
}

const tabs = [
  { id: 'decision', label: 'Decision' },
  { id: 'progress', label: 'Progress' },
  { id: 'summary', label: 'Summary' },
  { id: 'documents', label: 'Documents' },
  { id: 'message', label: 'Message' },
  { id: 'files', label: 'Files' },
  { id: 'state', label: 'State' }
] as const;

const phase = computed(() => state.value.phase ?? '-');
const iteration = computed(() => String(state.value.iteration ?? '-'));
const agent = computed(() => state.value.current_agent ?? '-');
const mainSessionId = computed(() => state.value.main_session_id ?? '-');

const isRunning = computed(() => {
  const p = (state.value.phase ?? '').toLowerCase();
  return p.startsWith('running') || p === 'awaiting_user' || p === 'starting' || p === 'interrupting';
});

const runLocked = computed(() => Boolean(state.value.run_locked ?? isRunning.value));
const resumeAvailable = computed(() => Boolean(state.value.main_session_id) || Boolean(state.value.resume_available));

const canStart = computed(() => !runLocked.value);
const canResume = computed(() => !runLocked.value && resumeAvailable.value);
const canInterrupt = computed(() => runLocked.value);
const canReset = computed(() => !runLocked.value);

const phaseDotColor = computed(() => {
  const p = (state.value.phase ?? '').toLowerCase();
  if (p === 'idle') return '#9ca3af';
  if (p === 'finished') return '#22c55e';
  if (p === 'error') return '#ef4444';
  if (p.startsWith('running')) return '#3b82f6';
  if (p === 'awaiting_user') return '#f59e0b';
  if (p === 'interrupting') return '#ef4444';
  return '#999';
});

const decisionBadge = computed(() => Boolean(decisionData.value));
const decisionTitle = computed(() => decisionData.value?.decision_title ?? '');
const decisionReason = computed(() => decisionData.value?.reason ?? '');
const decisionQuestion = computed(() => decisionData.value?.question ?? '');
const decisionOptions = computed<UserDecisionOption[]>(() => decisionData.value?.options ?? []);
const decisionRecommended = computed(() => decisionData.value?.recommended_option_id ?? null);

const stateJson = computed(() => {
  if (activeTab.value !== 'state') {
    return '';
  }
  try {
    const stateObj = state.value ?? {};
    // 创建一个副本，避免修改原始对象
    const stateCopy = { ...stateObj };

    // 如果某些字段是字符串，尝试解析后再显示
    if (typeof stateCopy.summary_history === 'string') {
      try {
        stateCopy.summary_history = JSON.parse(stateCopy.summary_history);
      } catch (e) {
        // 保持原样
      }
    }

    if (typeof stateCopy.last_iteration_summary === 'string') {
      try {
        stateCopy.last_iteration_summary = JSON.parse(stateCopy.last_iteration_summary);
      } catch (e) {
        // 保持原样
      }
    }

    return JSON.stringify(stateCopy, null, 2);
  } catch (error) {
    console.error('序列化 state 时出错:', error);
    return `Error: ${error instanceof Error ? error.message : String(error)}`;
  }
});

const summaryItems = computed<IterationSummary[]>(() => {
  if (activeTab.value !== 'summary') {
    return [];
  }

  try {
    let history = state.value.summary_history ?? null;

    // 如果 history 是字符串，尝试解析
    if (typeof history === 'string') {
      try {
        history = JSON.parse(history);
      } catch (e) {
        console.error('Failed to parse summary_history:', e);
        history = null;
      }
    }

    // 类型检查
    if (history !== null && history !== undefined && !Array.isArray(history)) {
      console.error('summary_history 必须是数组，实际类型:', typeof history, history);
      return [];
    }

    // 获取 items
    let items = history && history.length > 0
      ? history
      : (state.value.last_iteration_summary ? [state.value.last_iteration_summary] : []);

    // 如果 last_iteration_summary 是字符串，尝试解析
    if (items.length === 1 && typeof items[0] === 'string') {
      try {
        items = [JSON.parse(items[0])];
      } catch (e) {
        console.error('Failed to parse last_iteration_summary:', e);
        return [];
      }
    }

    // 数据校验（使用更宽松的检查）
    const validItems: IterationSummary[] = [];
    for (const item of items) {
      if (!item || typeof item !== 'object') {
        console.warn('跳过无效的摘要项:', item);
        continue;
      }

      if (typeof item.iteration !== 'number') {
        console.warn('摘要缺少 iteration:', item);
        continue;
      }

      const decision = item.main_decision;
      if (!decision || typeof decision !== 'object' || !decision.next_agent || !decision.reason) {
        console.warn('摘要 main_decision 缺失或无效:', item);
        continue;
      }

      const subagent = item.subagent;
      if (!subagent || typeof subagent !== 'object' || !subagent.agent || !subagent.task_summary || !subagent.report_summary) {
        console.warn('摘要 subagent 缺失或无效:', item);
        continue;
      }

      if (!Array.isArray(item.steps)) {
        console.warn('摘要 steps 必须是数组:', item);
        continue;
      }

      // 校验 steps
      let stepsValid = true;
      for (const step of item.steps) {
        if (!step || typeof step !== 'object' || typeof step.step !== 'number' || !step.actor || !step.detail) {
          console.warn('摘要 steps 无效:', step);
          stepsValid = false;
          break;
        }
      }

      if (!stepsValid) {
        continue;
      }

      validItems.push(item as IterationSummary);
    }

    return validItems;
  } catch (error) {
    console.error('处理 summaryItems 时出错:', error);
    return [];
  }
});

function setActiveTab(id: 'decision' | 'progress' | 'summary' | 'documents' | 'message' | 'files' | 'state') {
  activeTab.value = id;
}

function updateDecisionIfChanged(decision: MainDecision | null) {
  if (!decision) {
    decisionData.value = null;
    lastDecisionKey.value = null;
    selectedOption.value = '';
    decisionComment.value = '';
    decisionStatus.value = '';
    return;
  }
  const opts = decision.options ?? [];
  const optKey = opts.map((o) => `${o.option_id}:${o.description}`).join('|');
  const key = [
    decision.decision_title ?? '',
    decision.question ?? '',
    decision.reason ?? '',
    decision.recommended_option_id ?? '',
    optKey
  ].join('||');
  if (key === lastDecisionKey.value) {
    return;
  }
  lastDecisionKey.value = key;
  decisionData.value = decision;
  selectedOption.value = '';
  decisionComment.value = '';
  decisionStatus.value = '';
  setActiveTab('decision');
}

async function fetchState() {
  const res = await fetch('/api/state');
  if (!res.ok) {
    return;
  }
  const s = await res.json();
  state.value = s;
  updateDecisionIfChanged(s.awaiting_user_decision ?? null);
}

async function fetchProgress() {
  progressStatus.value = 'loading...';
  const res = await fetch('/api/progress');
  if (!res.ok) {
    progressStatus.value = `error ${res.status}`;
    return;
  }
  progress.value = await res.json();
  progressStatus.value = 'ok';
}

async function fetchUploadedDocs() {
  docsStatus.value = 'loading...';
  const res = await fetch('/api/uploaded_docs');
  if (!res.ok) {
    docsStatus.value = `error ${res.status}`;
    return;
  }
  const data = await res.json();
  if (!Array.isArray(data)) {
    throw new Error('uploaded docs must be array');
  }
  uploadedDocs.value = data;
  docsStatus.value = 'ok';
}

function onUploadFileChange(event: Event) {
  const input = event.target as HTMLInputElement | null;
  uploadFile.value = input?.files?.[0] ?? null;
}

function readFileAsBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error('read file failed'));
    reader.onload = () => {
      const result = reader.result;
      if (typeof result !== 'string') {
        reject(new Error('unexpected file reader result'));
        return;
      }
      const parts = result.split(',', 2);
      resolve(parts.length === 2 ? parts[1] : result);
    };
    reader.readAsDataURL(file);
  });
}

async function uploadDoc() {
  if (!uploadFile.value) {
    docsStatus.value = '请选择文件';
    return;
  }
  if (!uploadFile.value.name.endsWith('.md')) {
    docsStatus.value = '仅允许 .md 文件';
    return;
  }
  docsStatus.value = 'uploading...';
  const content = await readFileAsBase64(uploadFile.value);
  const resp = await fetch('/api/upload_doc', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      filename: uploadFile.value.name,
      content,
      category: uploadCategory.value
    })
  });
  if (!resp.ok) {
    docsStatus.value = `error ${resp.status}`;
    return;
  }
  uploadFile.value = null;
  await fetchUploadedDocs();
  docsStatus.value = 'uploaded';
}

async function deleteDoc(doc: UploadedDocument) {
  if (!window.confirm(`确认删除 ${doc.path}?`)) {
    return;
  }
  docsStatus.value = 'deleting...';
  const resp = await fetch(`/api/uploaded_docs/${encodeURIComponent(doc.path)}`, { method: 'DELETE' });
  docsStatus.value = resp.ok ? 'deleted' : `error ${resp.status}`;
  if (resp.ok) {
    await fetchUploadedDocs();
  }
}

async function addDocToFinishReview(doc: UploadedDocument) {
  docsStatus.value = 'updating...';
  const resp = await fetch('/api/add_to_finish_review', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ doc_path: doc.path })
  });
  docsStatus.value = resp.ok ? 'added to finish_review' : `error ${resp.status}`;
}

async function copyDocRef(doc: UploadedDocument) {
  const text = `@doc:${doc.path}`;
  try {
    await navigator.clipboard.writeText(text);
    docsStatus.value = 'copied';
  } catch (err) {
    docsStatus.value = 'copy failed';
  }
}

function insertDocRefs(target: HTMLTextAreaElement | null, model: { value: string }, refs: string[]) {
  const tokens = refs.map((ref) => `@doc:${ref}`).join(' ');
  if (!tokens) {
    return;
  }
  if (!target) {
    model.value = `${model.value} ${tokens}`.trim();
    return;
  }
  const start = target.selectionStart ?? model.value.length;
  const end = target.selectionEnd ?? model.value.length;
  const before = model.value.slice(0, start);
  const after = model.value.slice(end);
  const leading = before && !before.endsWith(' ') ? ' ' : '';
  const trailing = after && !after.startsWith(' ') ? ' ' : '';
  model.value = `${before}${leading}${tokens}${trailing}${after}`;
  nextTick(() => {
    target.focus();
    const pos = start + leading.length + tokens.length;
    target.selectionStart = pos;
    target.selectionEnd = pos;
  });
}

function insertTaskDocRefs() {
  insertDocRefs(taskGoalInputRef.value, taskGoalInput, taskDocRefs.value);
  taskDocRefs.value = [];
}

function insertMessageDocRefs() {
  insertDocRefs(messageInputRef.value, messageInput, messageDocRefs.value);
  messageDocRefs.value = [];
}

let logEpoch = 0;
let logPaused = false;

async function initLog() {
  const epoch = ++logEpoch;
  logStatus.value = 'loading...';
  const res = await fetch('/api/log?tail_lines=100');
  if (!res.ok) {
    logStatus.value = `error ${res.status}`;
    return;
  }
  const data = await res.json();
  if (epoch !== logEpoch) {
    return;
  }
  if (typeof data.next_offset === 'number') {
    logOffset.value = data.next_offset;
  }
  logText.value = typeof data.data === 'string' ? data.data : '';
  logStatus.value = '';
  if (autoScroll.value && logRef.value) {
    await nextTick();
    logRef.value.scrollTop = logRef.value.scrollHeight;
  }
}

async function fetchLog() {
  if (logPaused) {
    return;
  }
  const epoch = logEpoch;
  const res = await fetch(`/api/log?offset=${logOffset.value}`);
  if (!res.ok) {
    return;
  }
  const data = await res.json();
  if (epoch !== logEpoch) {
    return;
  }
  if (typeof data.next_offset === 'number') {
    logOffset.value = data.next_offset;
  }
  // Only process if there's actual new data
  if (data.data && data.data.length > 0) {
    logText.value += data.data;
    appendLogSummaryBuffer(data.data);

    // Keep only the last 100 lines to avoid performance issues
    const lines = logText.value.split('\n');
    if (lines.length > 100) {
      logText.value = lines.slice(-100).join('\n');
    }

    if (autoScroll.value && logRef.value) {
      await nextTick();
      logRef.value.scrollTop = logRef.value.scrollHeight;
    }
  }
}

let logSummarySeq = 0;

async function loadLogSummaryConfig() {
  logSummaryStatus.value = 'loading...';
  const res = await fetch('/api/log_summary/config');
  if (!res.ok) {
    logSummaryStatus.value = res.status === 404 ? '未配置' : `error ${res.status}`;
    return;
  }
  const data = await res.json();
  logSummaryConfig.base_url = data.base_url;
  logSummaryConfig.api_key = data.api_key;
  logSummaryConfig.model = data.model;
  logSummaryStatus.value = 'loaded';
}

async function saveLogSummaryConfig() {
  logSummaryStatus.value = 'saving...';
  const resp = await fetch('/api/log_summary/config', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      base_url: logSummaryConfig.base_url,
      api_key: logSummaryConfig.api_key,
      model: logSummaryConfig.model
    })
  });
  if (!resp.ok) {
    logSummaryStatus.value = `error ${resp.status}`;
    return;
  }
  const data = await resp.json();
  logSummaryConfig.base_url = data.base_url;
  logSummaryConfig.api_key = data.api_key;
  logSummaryConfig.model = data.model;
  logSummaryStatus.value = 'saved';
}

function appendLogSummaryBuffer(chunk: string) {
  logSummaryBuffer.value += chunk;
  const segments = chunk.split('\n');
  let lineCount = segments.length - 1;
  if (chunk && !chunk.endsWith('\n')) {
    lineCount += 1;
  }
  if (lineCount > 0) {
    logSummaryBufferLines.value += lineCount;
  }
  if (logSummaryAuto.value && logSummaryBufferLines.value >= logSummaryThreshold.value) {
    summarizeLogBuffer();
  }
}

async function summarizeLogBuffer() {
  if (logSummaryInFlight.value) {
    return;
  }
  if (!logSummaryBuffer.value.trim()) {
    logSummaryStatus.value = 'no logs';
    return;
  }
  logSummaryInFlight.value = true;
  logSummaryStatus.value = 'summarizing...';
  try {
    const resp = await fetch('/api/log_summary', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ logs: logSummaryBuffer.value })
    });
    if (!resp.ok) {
      logSummaryStatus.value = `error ${resp.status}`;
      return;
    }
    const data = await resp.json();
    if (!data.summary || typeof data.summary !== 'string') {
      logSummaryStatus.value = 'invalid summary';
      return;
    }
    logSummarySeq += 1;
    logSummaryItems.value.unshift({
      id: logSummarySeq,
      created_at: new Date().toISOString(),
      line_count: logSummaryBufferLines.value,
      summary: data.summary.trim()
    });
    logSummaryBuffer.value = '';
    logSummaryBufferLines.value = 0;
    logSummaryStatus.value = 'ok';
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    logSummaryStatus.value = `error ${msg}`;
  } finally {
    logSummaryInFlight.value = false;
  }
}

async function summarizeNow() {
  await summarizeLogBuffer();
}

async function startRun() {
  runCtlStatus.value = 'starting...';
  const resp = await fetch('/api/control/start', { method: 'POST' });
  runCtlStatus.value = resp.ok ? 'start requested' : `error ${resp.status}`;
}

async function resumeRun() {
  runCtlStatus.value = '继续中...';
  const resp = await fetch('/api/control/start', { method: 'POST' });
  runCtlStatus.value = resp.ok ? '继续请求已提交' : `error ${resp.status}`;
}

function openTaskModal() {
  taskModalStatus.value = '';
  taskGoalInput.value = '';
  resetDevPlan.value = false;
  resetProjectHistory.value = false;
  showTaskModal.value = true;
  nextTick(() => taskGoalInputRef.value?.focus());
}

function closeTaskModal() {
  showTaskModal.value = false;
}

function onTaskGoalKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') {
    closeTaskModal();
    return;
  }
  if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
    submitNewTask();
  }
}

async function submitNewTask() {
  const goal = taskGoalInput.value.trim();
  if (!goal) {
    taskModalStatus.value = '请输入任务目标';
    return;
  }
  taskModalStatus.value = 'submitting...';
  const resp = await fetch('/api/control/new_task', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      task_goal: goal,
      reset_dev_plan: resetDevPlan.value,
      reset_project_history: resetProjectHistory.value
    })
  });
  if (!resp.ok) {
    taskModalStatus.value = `error ${resp.status}`;
    return;
  }
  closeTaskModal();
  runCtlStatus.value = 'new task requested';
}

async function interruptRun() {
  runCtlStatus.value = 'interrupting...';
  const resp = await fetch('/api/control/interrupt', { method: 'POST' });
  runCtlStatus.value = resp.ok ? 'interrupt requested' : `error ${resp.status}`;
}

async function resetRun() {
  if (!window.confirm('确认重置？将清空历史/摘要/工单/报告/日志等进度信息。')) {
    return;
  }
  runCtlStatus.value = '重置中...';
  const resp = await fetch('/api/control/reset', { method: 'POST' });
  runCtlStatus.value = resp.ok ? '已重置' : `错误 ${resp.status}`;
  if (resp.ok) {
    logOffset.value = 0;
    logText.value = '';
    logSummaryBuffer.value = '';
    logSummaryBufferLines.value = 0;
    logSummaryItems.value = [];
    logSummaryStatus.value = '';
    lastDecisionKey.value = null;
    await fetchState();
  }
}

async function clearLog() {
  logPaused = true;
  const epoch = ++logEpoch;
  logText.value = '';
  logSummaryBuffer.value = '';
  logSummaryBufferLines.value = 0;
  logSummaryItems.value = [];
  logSummaryStatus.value = '';
  logStatus.value = 'clearing...';
  try {
    // 跳到日志文件末尾：后续只展示“Clear 之后产生”的新日志。
    const res = await fetch('/api/log?tail_lines=0');
    if (!res.ok) {
      logStatus.value = `error ${res.status}`;
      return;
    }
    const data = await res.json();
    if (epoch !== logEpoch) {
      return;
    }
    if (typeof data.next_offset === 'number') {
      logOffset.value = data.next_offset;
    }
    logStatus.value = 'cleared';
  } finally {
    if (epoch === logEpoch) {
      logPaused = false;
    }
  }
}

async function copyLog() {
  const text = logText.value || '';
  try {
    await navigator.clipboard.writeText(text);
    logStatus.value = 'copied';
  } catch (err) {
    logStatus.value = 'copy failed';
  }
}

async function sendMessage() {
  const message = messageInput.value.trim();
  if (!message) {
    msgStatus.value = '请输入内容';
    return;
  }
  msgStatus.value = 'sending...';
  const resp = await fetch('/api/user_message', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message })
  });
  msgStatus.value = resp.ok ? 'sent' : `error ${resp.status}`;
  if (resp.ok) {
    messageInput.value = '';
  }
}

function onMessageKeydown(event: KeyboardEvent) {
  if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
    sendMessage();
  }
}

async function submitDecision() {
  if (!selectedOption.value) {
    decisionStatus.value = '请选择一个选项';
    return;
  }
  decisionStatus.value = 'sending...';
  const resp = await fetch('/api/user_decision', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ option_id: selectedOption.value, comment: decisionComment.value || '' })
  });
  decisionStatus.value = resp.ok ? 'sent' : `error ${resp.status}`;
}

async function refreshFiles() {
  fileStatus.value = 'loading...';
  const res = await fetch('/api/md_files');
  if (!res.ok) {
    fileStatus.value = `error ${res.status}`;
    return;
  }
  const files = await res.json();
  if (!Array.isArray(files)) {
    throw new Error('md files must be array');
  }
  mdFiles.value = files;
  const current = selectedFile.value;
  if (mdFiles.value.length > 0) {
    selectedFile.value = current && mdFiles.value.includes(current) ? current : mdFiles.value[0];
  }
  fileStatus.value = 'ok';
  if (!loadedFilePath.value && selectedFile.value) {
    await loadSelectedFile();
  }
}

async function loadSelectedFile() {
  const path = selectedFile.value;
  if (!path) {
    fileStatus.value = 'no file selected';
    return;
  }
  if (fileDirty.value && !window.confirm('当前文件有未保存修改，仍要重新加载吗？')) {
    fileStatus.value = 'canceled';
    return;
  }
  fileStatus.value = 'loading...';
  const res = await fetch(`/api/file?path=${encodeURIComponent(path)}`);
  if (!res.ok) {
    fileStatus.value = `error ${res.status}`;
    return;
  }
  const data = await res.json();
  fileContent.value = data.content ?? '';
  loadedFilePath.value = data.path ?? path;
  fileDirty.value = false;
  fileStatus.value = 'loaded';
}

async function saveSelectedFile() {
  const path = loadedFilePath.value || selectedFile.value;
  if (!path) {
    fileStatus.value = 'no file selected';
    return;
  }
  fileStatus.value = 'saving...';
  const res = await fetch('/api/file', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path, content: fileContent.value || '' })
  });
  if (res.ok) {
    fileDirty.value = false;
    fileStatus.value = 'saved';
    return;
  }
  let detail = '';
  try {
    const data = await res.json();
    detail = data.error ?? '';
  } catch (err) {
    detail = '';
  }
  fileStatus.value = `error ${res.status}${detail ? `: ${detail}` : ''}`;
}

function onFileInput() {
  if (!loadedFilePath.value) {
    return;
  }
  fileDirty.value = true;
}

async function quickOpen(path: string) {
  await refreshFiles();
  selectedFile.value = path;
  await loadSelectedFile();
  setActiveTab('files');
}

function handleGlobalKeydown(event: KeyboardEvent) {
  if (!showTaskModal.value) {
    return;
  }
  if (event.key === 'Escape') {
    closeTaskModal();
  }
}

let stateTimer: number | undefined;
let logTimer: number | undefined;
let progressTimer: number | undefined;

onMounted(() => {
  fetchState();
  refreshFiles();
  fetchProgress();
  fetchUploadedDocs();
  loadLogSummaryConfig();
  stateTimer = window.setInterval(fetchState, 800);
  progressTimer = window.setInterval(fetchProgress, 5000);
  initLog().finally(() => {
    if (!logTimer) {
      logTimer = window.setInterval(fetchLog, 400);
    }
  });
  window.addEventListener('keydown', handleGlobalKeydown);
});

onUnmounted(() => {
  if (stateTimer) {
    window.clearInterval(stateTimer);
  }
  if (logTimer) {
    window.clearInterval(logTimer);
  }
  if (progressTimer) {
    window.clearInterval(progressTimer);
  }
  window.removeEventListener('keydown', handleGlobalKeydown);
});
</script>
