export type UserDecisionOption = {
  option_id: string;
  description: string;
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
};

export type MainDecision = MainDecisionDispatch | MainDecisionUser;

export type SummaryStep = {
  step: number;
  actor: string;
  detail: string;
};

export type SubagentSummary = {
  agent: string;
  task_summary: string;
  report_summary: string;
};

export type IterationSummary = {
  iteration: number;
  main_decision: MainDecision;
  subagent: SubagentSummary;
  steps: SummaryStep[];
  summary: string;
  artifacts?: Record<string, unknown>;
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
