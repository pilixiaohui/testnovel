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
        <button class="primary" @click="submitNewTask">Start New Task</button>
        <div class="muted">{{ taskModalStatus }}</div>
      </div>
    </div>
  </div>

  <main>
    <section id="logsPane">
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
      <pre id="log" ref="logRef">{{ logText }}</pre>
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

      <div v-if="activeTab === 'summary'" class="panel">
        <div class="card">
          <div class="muted">迭代摘要</div>
          <div style="height: 8px"></div>
          <div class="summaryList">
            <div v-if="summaryItems.length === 0" class="muted">暂无摘要</div>
            <div v-for="item in summaryItems" :key="item.iteration" class="summaryItem">
              <div class="summaryTitle">
                <b>Iteration {{ item.iteration }}</b>
                <span class="muted">agent: {{ item.subagent.agent }}</span>
              </div>
              <div class="muted">{{ item.summary }}</div>
              <div style="height: 6px"></div>
              <div>
                <b>MAIN 决策</b>
                <code>{{ item.main_decision.next_agent }}</code> - {{ item.main_decision.reason }}
              </div>
              <template v-if="item.main_decision.next_agent === 'USER'">
                <div class="muted">抉择: {{ item.main_decision.decision_title }}</div>
                <div class="muted">问题: {{ item.main_decision.question }}</div>
                <div class="muted" v-if="item.main_decision.recommended_option_id">
                  推荐: {{ item.main_decision.recommended_option_id }}
                </div>
              </template>
              <div style="height: 6px"></div>
              <div><b>子代理</b> <code>{{ item.subagent.agent }}</code></div>
              <div class="muted">任务: {{ item.subagent.task_summary }}</div>
              <div class="muted">报告: {{ item.subagent.report_summary }}</div>
              <div style="height: 6px"></div>
              <div><b>步骤</b></div>
              <ol class="summarySteps">
                <li v-for="step in item.steps" :key="step.step">
                  <code>{{ step.actor }}</code> {{ step.detail }}
                </li>
              </ol>
              <div v-if="item.artifacts" class="summaryArtifacts">
                artifacts: {{ JSON.stringify(item.artifacts) }}
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
          <textarea
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
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue';
import type { IterationSummary, MainDecision, UiState, UserDecisionOption } from './types';

const logOffset = ref(0);
const logText = ref('');
const autoScroll = ref(true);
const logStatus = ref('');
const runCtlStatus = ref('');
const msgStatus = ref('');
const decisionStatus = ref('');
const fileStatus = ref('');
const taskModalStatus = ref('');

const showTaskModal = ref(false);
const taskGoalInput = ref('');
const messageInput = ref('');
const activeTab = ref<'decision' | 'summary' | 'message' | 'files' | 'state'>('decision');

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

const logRef = ref<HTMLElement | null>(null);
const taskGoalInputRef = ref<HTMLTextAreaElement | null>(null);

const tabs = [
  { id: 'decision', label: 'Decision' },
  { id: 'summary', label: 'Summary' },
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

const canStart = computed(() => !isRunning.value);
const canResume = computed(() => !isRunning.value && resumeAvailable.value);
const canInterrupt = computed(() => isRunning.value);
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
  return JSON.stringify(state.value ?? {}, null, 2);
});

const summaryItems = computed<IterationSummary[]>(() => {
  if (activeTab.value !== 'summary') {
    return [];
  }
  const history = state.value.summary_history ?? null;
  if (history !== null && history !== undefined && !Array.isArray(history)) {
    throw new Error('summary_history 必须是数组');
  }
  const items = history && history.length > 0
    ? history
    : (state.value.last_iteration_summary ? [state.value.last_iteration_summary] : []);
  for (const item of items) {
    if (!item || typeof item.iteration !== 'number') {
      throw new Error('摘要缺少 iteration');
    }
    const decision = item.main_decision;
    if (!decision || !decision.next_agent || !decision.reason) {
      throw new Error('摘要 main_decision 缺失');
    }
    const subagent = item.subagent;
    if (!subagent || !subagent.agent || !subagent.task_summary || !subagent.report_summary) {
      throw new Error('摘要 subagent 缺失');
    }
    if (!Array.isArray(item.steps)) {
      throw new Error('摘要 steps 必须是数组');
    }
    for (const step of item.steps) {
      if (!step || typeof step.step !== 'number' || !step.actor || !step.detail) {
        throw new Error('摘要 steps 无效');
      }
    }
  }
  return items;
});

function setActiveTab(id: 'decision' | 'summary' | 'message' | 'files' | 'state') {
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
    body: JSON.stringify({ task_goal: goal })
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
    lastDecisionKey.value = null;
    await fetchState();
  }
}

async function clearLog() {
  logPaused = true;
  const epoch = ++logEpoch;
  logText.value = '';
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

onMounted(() => {
  fetchState();
  refreshFiles();
  stateTimer = window.setInterval(fetchState, 800);
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
  window.removeEventListener('keydown', handleGlobalKeydown);
});
</script>
