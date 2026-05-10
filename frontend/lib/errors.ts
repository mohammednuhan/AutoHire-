export type ErrorCopy = {
  title: string;
  message: string;
  action: string;
  persistent: boolean;
};

export const ERROR_MESSAGES: Record<string, ErrorCopy> = {
  PARSE_FAILED: {
    title: "Resume parsing failed",
    message: "We could not extract text from your resume. Use a text-based PDF, not a scanned image.",
    action: "Export from Word or Google Docs and upload again.",
    persistent: false,
  },
  EXTRACTION_INCOMPLETE: {
    title: "Resume parsing incomplete",
    message: "We could not extract every required field from your resume.",
    action: "Review the highlighted profile fields and fill the missing details.",
    persistent: false,
  },
  AGENT_ALREADY_RUNNING: {
    title: "Agent already running",
    message: "The agent is already running.",
    action: "Use the Stop button if you need to start a new scan.",
    persistent: false,
  },
  SCAN_ALREADY_RUNNING: {
    title: "Scan already running",
    message: "A scan is already running.",
    action: "Wait for it to finish or use the Stop button.",
    persistent: false,
  },
  RUNGUARD_FAIL_INTERNET: {
    title: "No internet connection",
    message: "No internet connection detected. AutoHire will retry when the connection is restored.",
    action: "Check your connection.",
    persistent: true,
  },
  RUNGUARD_FAIL_DB: {
    title: "Database unavailable",
    message: "AutoHire cannot reach the database.",
    action: "Check Docker and database health.",
    persistent: true,
  },
  REDIS_UNAVAILABLE: {
    title: "Redis unavailable",
    message: "AutoHire cannot reach Redis, so live state and stop controls may not work.",
    action: "Check the cache service in Docker.",
    persistent: true,
  },
  SCAN_FAILED: {
    title: "Scan failed",
    message: "The latest job scan failed before completion.",
    action: "Review logs, then run the scan again.",
    persistent: true,
  },
  CAPTCHA_DETECTED: {
    title: "CAPTCHA detected",
    message: "A CAPTCHA appeared on the application form.",
    action: "Open the dashboard and complete it manually.",
    persistent: true,
  },
  LLM_FAILURE: {
    title: "AI model failed",
    message: "The AI model did not respond correctly.",
    action: "AutoHire will retry this application next run.",
    persistent: false,
  },
  COVER_LETTER_VALIDATION_FAILED: {
    title: "Cover letter needs review",
    message: "The cover letter generator could not produce a verified cover letter after 3 attempts.",
    action: "Review and write it manually.",
    persistent: true,
  },
  BLOCKED_NAVIGATION: {
    title: "Navigation blocked",
    message: "AutoHire blocked a navigation attempt to an unauthorized domain.",
    action: "Review the job link before continuing.",
    persistent: true,
  },
};

export function errorCopy(code?: string, fallback?: string): ErrorCopy {
  if (code && ERROR_MESSAGES[code]) return ERROR_MESSAGES[code];
  return {
    title: code ?? "Something went wrong",
    message: fallback ?? "AutoHire hit an unexpected error.",
    action: "Review the dashboard for details.",
    persistent: true,
  };
}
