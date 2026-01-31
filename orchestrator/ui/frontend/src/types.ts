export type UserDecisionOption = {
  option_id: string;
  description: string;
};

export type DocPatch = {
  file: string;
  action: 'append' | 'replace' | 'insert';
  content: string;
  reason: string;
  old_content?: string;
  after_marker?: string;
};

export type MainDecisionDispatch = {
  next_agent: 'TEST' | 'DEV' | 'REVIEW' | 'FINISH';
  reason: string;
  decision_title?: string;
  question?: string;
  options?: UserDecisionOption[];
  recommended_option_id?: string | null;
};

export type MainDecisionUser = {
  next_agent: 'USER';
  reason: string;
  decision_title: string;
  question: string;
  options: UserDecisionOption[];
  recommended_option_id?: string | null;
  doc_patches?: DocPatch[] | null;
};

export type MainDecision = MainDecisionDispatch | MainDecisionUser;

export type SummaryStep = {
  step: number;
  actor: string;
  detail: string;
};

export type MilestoneProgress = {
  milestone_id: string;
  milestone_name: string;
  total_tasks: number;
  completed_tasks: number;
  verified_tasks: number;
  percentage: number;
};

export type TaskProgress = {
  task_id: string;
  title: string;
  status: string;
  milestone_id: string;
};

export type ProgressInfo = {
  total_tasks: number;
  completed_tasks: number;
  verified_tasks: number;
  in_progress_tasks: number;
  blocked_tasks: number;
  todo_tasks: number;
  completion_percentage: number;
  verification_percentage: number;
  current_milestone: string | null;
  milestones: MilestoneProgress[];
  tasks: TaskProgress[];
};

export type UploadedDocument = {
  filename: string;
  path: string;
  category: string;
  size: number;
  upload_time: string;
};

export type SubagentSummary = {
  agent: string;
  task_summary: string;
  report_summary: string;
};

export type CodeChanges = {
  files_modified?: string[];
  tests_passed?: boolean;
  coverage?: number;
};

export type IterationSummary = {
  iteration: number;
  main_decision: MainDecision;
  subagent: SubagentSummary;
  steps: SummaryStep[];
  summary: string;
  progress?: ProgressInfo | null;
  artifacts?: Record<string, unknown>;
  verdict?: string;  // PASS | FAIL | BLOCKED
  key_findings?: string[];
  changes?: CodeChanges;
};

export type UiState = {
  phase?: string;
  iteration?: number;
  current_agent?: string;
  main_session_id?: string | null;
  last_iteration_summary?: IterationSummary | null;
  summary_history?: IterationSummary[] | null;
  awaiting_user_decision?: MainDecision | null;
  run_locked?: boolean;
  resume_available?: boolean;
  last_error?: string | null;
};
