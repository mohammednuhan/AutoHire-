export type UUID = string;
export type ISODateTime = string;

export enum ApplicationStatus {
  Queued = "queued",
  AgentProcessing = "agent_processing",
  NeedsHuman = "needs_human",
  ReadyToSubmit = "ready_to_submit",
  Submitted = "submitted",
  Shortlisted = "shortlisted",
  Interview = "interview",
  Rejected = "rejected",
  Offer = "offer",
  Ghosted = "ghosted",
  Interrupted = "interrupted",
  Failed = "failed",
}

export type RecommendationEnum = "APPLY" | "SKIP" | "STRETCH";

export interface EducationItem {
  institution: string;
  degree: string;
  field?: string | null;
  graduation_year?: number | null;
  gpa?: string | null;
  relevant_courses: string[];
}

export interface ExperienceItem {
  company: string;
  role: string;
  start_date?: string | null;
  end_date?: string | null;
  is_current: boolean;
  location?: string | null;
  description: string[];
  tech_stack: string[];
}

export interface ProjectItem {
  name: string;
  description?: string | null;
  tech_stack: string[];
  url?: string | null;
  duration?: string | null;
}

export interface SkillsProfile {
  languages: string[];
  frameworks: string[];
  databases: string[];
  tools: string[];
  cloud: string[];
  soft_skills: string[];
}

export interface CertificationItem {
  name: string;
  issuer?: string | null;
  year?: number | null;
}

export interface ResumeProfile {
  full_name: string;
  email?: string | null;
  phone?: string | null;
  location?: string | null;
  linkedin_url?: string | null;
  github_url?: string | null;
  portfolio_url?: string | null;
  summary?: string | null;
  education: EducationItem[];
  experience: ExperienceItem[];
  projects: ProjectItem[];
  skills: SkillsProfile;
  certifications: CertificationItem[];
  achievements: string[];
  languages_spoken: string[];
}

export interface UserPreferences {
  target_roles: string[];
  preferred_locations: string[];
  work_type: "remote" | "hybrid" | "onsite" | "any";
  salary_min_inr?: number | null;
  salary_max_inr?: number | null;
  experience_level: "internship" | "entry" | "mid" | "senior";
  job_types: string[];
  industry_include: string[];
  industry_exclude: string[];
  blacklisted_companies: string[];
  dream_companies: string[];
  keyword_blacklist: string[];
  score_threshold: number;
  max_apps_per_day: number;
  schedule_cron: string;
  telegram_chat_id?: string | null;
  llm_provider: "gemini" | "claude" | "ollama";
  llm_quality_mode: "fast" | "balanced" | "maximum";
  enabled_boards: string[];
}

export interface JobResponse {
  id: UUID;
  board: string;
  external_id: string;
  title: string;
  company: string;
  url: string;
  location?: string | null;
  work_type?: string | null;
  salary_min_inr?: number | null;
  salary_max_inr?: number | null;
  experience_level?: string | null;
  skills_required: string[];
  posted_at?: ISODateTime | null;
  scraped_at: ISODateTime;
  status: string;
  total_score?: number | null;
  recommendation?: RecommendationEnum | null;
}

export interface JobsPageResponse {
  page: number;
  per_page: number;
  total: number;
  items: JobResponse[];
}

export interface ScoreBreakdown {
  total_score: number;
  technical_match?: number | null;
  experience_match?: number | null;
  domain_match?: number | null;
  location_match?: number | null;
  growth_potential?: number | null;
  missing_skills: string[];
  matching_skills: string[];
  score_explanation?: string | null;
  recommendation?: RecommendationEnum | null;
  scored_at?: ISODateTime | null;
}

export interface JobDetailResponse extends JobResponse {
  description?: string | null;
  content_hash?: string | null;
  score_breakdown?: ScoreBreakdown | null;
}

export interface CoverLetterResponse {
  id: UUID;
  application_id: UUID;
  content: string;
  word_count?: number | null;
  tone: string;
  fact_check_passed: boolean;
  generation_attempts: number;
  created_at: ISODateTime;
}

export interface AgentLogEntry {
  id: UUID;
  application_id: UUID;
  trace_id: UUID;
  step_number: number;
  field_name?: string | null;
  action_type?: string | null;
  action_data?: Record<string, unknown> | null;
  confidence?: number | null;
  status?: string | null;
  screenshot_path?: string | null;
  attempt_number: number;
  error_message?: string | null;
  created_at: ISODateTime;
}

export interface ApplicationEventResponse {
  id: UUID;
  application_id?: UUID | null;
  trace_id?: UUID | null;
  event_type: string;
  event_data: Record<string, unknown>;
  created_at: ISODateTime;
}

export interface ApplicationListItem {
  id: UUID;
  job_id: UUID;
  resume_id: UUID;
  trace_id: UUID;
  title?: string | null;
  company?: string | null;
  board?: string | null;
  is_dream_company: boolean;
  status: ApplicationStatus;
  failure_reason?: string | null;
  queued_at: ISODateTime;
  started_at?: ISODateTime | null;
  completed_at?: ISODateTime | null;
  submitted_at?: ISODateTime | null;
}

export interface ApplicationDetailResponse extends ApplicationListItem {
  notes?: string | null;
  tailored_resume_pdf_path?: string | null;
  tailored_resume_docx_path?: string | null;
  job?: JobDetailResponse | null;
  cover_letter?: CoverLetterResponse | null;
  agent_log: AgentLogEntry[];
  events: ApplicationEventResponse[];
}

export interface NeedsHumanPayload {
  application_id: UUID;
  trace_id: UUID;
  reason: string;
  message: string;
  field_name?: string | null;
  screenshot_path?: string | null;
  options: string[];
  context: Record<string, unknown>;
}

export interface AgentStatusResponse {
  is_running: boolean;
  stop_requested: boolean;
  active_application_id?: UUID | null;
  active_trace_id?: UUID | null;
  current_step?: string | null;
  last_heartbeat_at?: ISODateTime | null;
  lock_expires_at?: ISODateTime | null;
}

export interface TaskResponse {
  id: UUID;
  task_type: string;
  status: string;
  scheduled_at: ISODateTime;
  started_at?: ISODateTime | null;
  completed_at?: ISODateTime | null;
  jobs_found: number;
  apps_attempted: number;
  apps_completed: number;
  result_summary?: string | null;
  error_message?: string | null;
}

export interface AgentRunRequest {
  boards?: string[] | null;
}

export interface AgentRunResponse {
  task_id: UUID;
  status: "started";
}

export interface MetricsResponse {
  apps_sent_vs_confirmed: {
    sent: number;
    confirmed: number;
    rate: number;
  };
  form_fill_success_rate: Record<string, number>;
  llm_confidence_avg: number;
  avg_time_per_application_seconds: number;
  human_gate_trigger_rate: number;
  updated_at: ISODateTime;
}

export interface ErrorResponse {
  error: string;
  message: string;
}

export interface WebSocketEventBase {
  event: string;
  timestamp: ISODateTime;
}

export interface AgentStatusEvent extends WebSocketEventBase {
  event: "AGENT_STATUS";
  status: "idle" | "running" | "paused" | "error";
}

export interface RunStartedEvent extends WebSocketEventBase {
  event: "RUN_STARTED";
  task_id: UUID;
  boards: string[];
}

export interface RunCompletedEvent extends WebSocketEventBase {
  event: "RUN_COMPLETED";
  task_id: UUID;
  jobs_found: number;
  apps_attempted: number;
  apps_completed: number;
  duration_seconds: number;
}

export interface JobDiscoveredEvent extends WebSocketEventBase {
  event: "JOB_DISCOVERED";
  job_id: UUID;
  company: string;
  title: string;
  board: string;
  score: number;
  recommendation: RecommendationEnum;
}

export interface ApplicationStartedEvent extends WebSocketEventBase {
  event: "APPLICATION_STARTED";
  application_id: UUID;
  trace_id: UUID;
  company: string;
  role: string;
}

export interface BrowserActionEvent extends WebSocketEventBase {
  event: "BROWSER_ACTION";
  trace_id?: UUID;
  step: number;
  action: string;
  field: string;
  confidence?: number;
}

export interface LLMCallEvent extends WebSocketEventBase {
  event: "LLM_CALL";
  trace_id: UUID;
  purpose: string;
  model: string;
  tokens: number;
}

export interface ValidationResultEvent extends WebSocketEventBase {
  event: "VALIDATION_RESULT";
  trace_id: UUID;
  field: string;
  confidence: number;
  passed: boolean;
}

export interface ApplicationSuccessEvent extends WebSocketEventBase {
  event: "APPLICATION_SUCCESS";
  application_id: UUID;
  trace_id: UUID;
  company: string;
  role: string;
  status: "ready_to_submit" | "submitted";
}

export interface ApplicationFailedEvent extends WebSocketEventBase {
  event: "APPLICATION_FAILED";
  application_id: UUID;
  trace_id: UUID;
  reason: string;
  step: number;
}

export interface NeedsHumanEvent extends WebSocketEventBase {
  event: "NEEDS_HUMAN";
  application_id: UUID;
  trace_id: UUID;
  company: string;
  role: string;
  reason:
    | "LOW_CONFIDENCE"
    | "DREAM_COMPANY"
    | "SALARY_QUESTION"
    | "SCREENING_QUESTION"
    | "PREREQ_FAILED"
    | "CAPTCHA_DETECTED"
    | "SUBMIT_CONFIRMATION_FAILED";
  field_name: string;
  question_text: string;
  draft_answer: string | null;
  confidence: number;
  screenshot_url: string;
  expires_at: ISODateTime;
}

export interface HealthCheckEvent extends WebSocketEventBase {
  event: "HEALTH_CHECK";
  db: "ok";
  redis: "ok";
  agent: "idle" | "running" | "paused";
}

export interface MorningSummaryEvent extends WebSocketEventBase {
  event: "MORNING_SUMMARY";
  date: string;
  jobs_scanned: number;
  new_high_score_jobs: number;
  apps_attempted: number;
  apps_completed: number;
  apps_needs_review: number;
}

export interface ErrorEvent extends WebSocketEventBase {
  event: "ERROR";
  error_code:
    | "LLM_FAILURE"
    | "RUNGUARD_FAIL_INTERNET"
    | "RUNGUARD_FAIL_DB"
    | "DISK_FULL"
    | "REDIS_UNAVAILABLE"
    | "SCAN_FAILED"
    | "BLOCKED_NAVIGATION"
    | "CAPTCHA_DETECTED"
    | "COVER_LETTER_VALIDATION_FAILED";
  message: string;
}

export type WebSocketEvent =
  | AgentStatusEvent
  | RunStartedEvent
  | RunCompletedEvent
  | JobDiscoveredEvent
  | ApplicationStartedEvent
  | BrowserActionEvent
  | LLMCallEvent
  | ValidationResultEvent
  | ApplicationSuccessEvent
  | ApplicationFailedEvent
  | NeedsHumanEvent
  | HealthCheckEvent
  | MorningSummaryEvent
  | ErrorEvent;
