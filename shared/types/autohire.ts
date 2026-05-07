export type ApplicationStatus =
  | "DISCOVERED"
  | "SCORED"
  | "QUEUED"
  | "NEEDS_HUMAN"
  | "SUBMITTED"
  | "SKIPPED"
  | "FAILED";

export type JobSource =
  | "WELLFOUND"
  | "NAUKRI"
  | "INSTAHYRE"
  | "COMPANY_SITE"
  | "LINKEDIN"
  | "MANUAL";

export type DecisionReason =
  | "SCORE_AUTO_QUEUE"
  | "LOW_CONFIDENCE"
  | "DREAM_COMPANY"
  | "DAILY_CAP_REACHED"
  | "USER_REQUESTED"
  | "LINKEDIN_SEMI_AUTOMATIC";

export interface UserProfile {
  id: string;
  fullName: string;
  email: string;
  phone?: string | null;
  location?: string | null;
  education: Record<string, unknown>;
  skills: string[];
  links: Record<string, string>;
  preferences: Record<string, unknown>;
}

export interface JobPosting {
  id: string;
  source: JobSource;
  title: string;
  companyName?: string | null;
  location?: string | null;
  url: string;
  description?: string | null;
  requiredSkills: string[];
}

export interface Application {
  id: string;
  jobPostingId: string;
  status: ApplicationStatus;
  score?: number | null;
  confidence?: number | null;
  decisionReason?: DecisionReason | null;
}

export interface HumanReview {
  applicationId: string;
  reason: DecisionReason;
  message: string;
}

export interface AgentLimits {
  scoreAutoQueueThreshold: number;
  confidenceGate: number;
  dailyApplicationCap: number;
  linkedinDailyCap: number;
}
