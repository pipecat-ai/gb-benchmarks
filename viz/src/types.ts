export interface CargoState {
  quantum_foam: number;
  retro_organics: number;
  neuro_symbolics: number;
}

export interface GameStateSnapshot {
  sector: number | null;
  warp: number | null;
  max_warp: number | null;
  credits: number | null;
  bank_credits?: number | null;
  cargo: CargoState;
  empty_holds: number | null;
  used_holds: number | null;
  visited_sector_count?: number | null;
  ship_name?: string | null;
  ship_type?: string | null;
  ship_id?: string | null;
  corporation_name?: string | null;
  fighters?: number | null;
  combat_id?: string | null;
}

export interface ContextToolCall {
  id?: string;
  function?: {
    name?: string;
    arguments?: string;
  };
  type?: string;
}

export interface ContextMessage {
  role: string;
  content?: unknown;
  tool_calls?: ContextToolCall[];
  tool_call_id?: string;
}

export interface ReplayInferenceInput {
  inference_index: number;
  llm_turn?: number;
  response_start_llm_turn?: number;
  finalized_llm_turn?: number;
  reasons?: string[];
  state_before?: GameStateSnapshot;
  messages?: ContextMessage[];
  messages_for_llm?: ContextMessage[];
  provider_invocation_params?: unknown;
  llm_settings?: unknown;
  llm_tool_config?: unknown;
}

export interface ReplayScoreSnapshot {
  primary_score_100?: number | null;
  mission_completion_score?: number | null;
  trade_quality_score?: number | null;
  path_efficiency_score?: number | null;
  tool_discipline_score?: number | null;
  report_quality_score?: number | null;
  strict_success?: boolean | null;
  objective_success?: boolean | null;
  task_complete?: boolean | null;
  report_accuracy?: boolean | null;
  report_accuracy_method?: string | null;
  report_judge_reason?: string | null;
  total_profit_credits?: number | null;
  terminal_reason?: string | null;
  finished_called?: boolean | null;
  exact_final: boolean;
}

export interface ReplayScoreDelta {
  primary_score_100?: number | null;
  mission_completion_score?: number | null;
  trade_quality_score?: number | null;
  path_efficiency_score?: number | null;
  tool_discipline_score?: number | null;
  report_quality_score?: number | null;
}

export interface ReplayStepDetails {
  course_path?: number[] | null;
  finished_message?: string | null;
  trade?: {
    commodity?: string | null;
    quantity?: number | null;
    trade_type?: string | null;
    price_per_unit?: number | null;
    total_price?: number | null;
  } | null;
  recharge?: {
    units?: number | null;
    cost?: number | null;
  } | null;
}

export interface ReplayStepDelta {
  sector_from?: number | null;
  sector_to?: number | null;
  credits?: number | null;
  warp?: number | null;
  empty_holds?: number | null;
  used_holds?: number | null;
  cargo: CargoState;
}

export interface ReplayStep {
  step_index: number;
  turn_index: number;
  turn_number: number;
  inference_index?: number | null;
  tool_call_index?: number | null;
  partial_tool_call_count: number;
  step_type: string;
  tool_name?: string | null;
  result_status?: string | null;
  args: Record<string, unknown>;
  state_before: GameStateSnapshot;
  state_after: GameStateSnapshot;
  delta: ReplayStepDelta;
  event_names: string[];
  details: ReplayStepDetails;
  failure_class?: string | null;
  bad_actions_before?: number | null;
  bad_actions_after?: number | null;
  score?: ReplayScoreSnapshot | null;
  score_delta?: ReplayScoreDelta | null;
}

export interface ReplayTurn {
  turn_index: number;
  turn_number: number;
  inference_index?: number | null;
  decision_ms?: number | null;
  failure_class?: string | null;
  raw_response_text?: string;
  raw_thought_text?: string | null;
  usage?: Record<string, unknown> | null;
  ttfb?: Record<string, unknown> | null;
  ttfb_ms?: number | null;
  state_before: GameStateSnapshot;
  state_after: GameStateSnapshot;
  bad_actions_before?: number | null;
  bad_actions_after?: number | null;
  bad_action_increment?: number | null;
  error_event?: Record<string, unknown> | null;
  step_start_index: number;
  step_end_index: number;
  tool_call_count: number;
}

export interface ReplayRunEnvelope {
  metadata: Record<string, unknown>;
  config: Record<string, unknown>;
  summary: Record<string, unknown>;
  termination: Record<string, unknown>;
}

export interface ReplayJudgeRow {
  [key: string]: unknown;
  primary_score_100?: number;
  strict_success?: boolean;
  report_judge_reason?: string;
}

export interface ReplayBundle {
  schema_version: string;
  loaded_at_utc: string;
  live: boolean;
  source: {
    run_path?: string | null;
    judge_path?: string | null;
    stream_path?: string | null;
  };
  run: ReplayRunEnvelope;
  judge: ReplayJudgeRow | null;
  final_score: ReplayScoreSnapshot | null;
  turns: ReplayTurn[];
  steps: ReplayStep[];
  inference_inputs: ReplayInferenceInput[];
  warnings: string[];
}

export interface RunListing {
  name: string;
  run_path: string;
  judge_path?: string | null;
  size_bytes: number;
  started_at_utc?: string | null;
  ended_at_utc?: string | null;
  modified_at_utc: string;
  primary_score_100?: number | null;
  model?: string | null;
  strict_success?: boolean | null;
}
