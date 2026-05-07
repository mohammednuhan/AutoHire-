-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ───────────────────────────
-- USERS AND PROFILE
-- ───────────────────────────

CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username        VARCHAR(100) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE resumes (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id           UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    original_filename VARCHAR(500) NOT NULL,
    original_file_path TEXT NOT NULL,           -- stored at DATA_DIR/resumes/{id}/original.*
    raw_text          TEXT,                     -- extracted plain text
    profile_json      JSONB NOT NULL,           -- full structured ResumeProfile
    is_active         BOOLEAN DEFAULT true,
    parsed_at         TIMESTAMP WITH TIME ZONE,
    created_at        TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE user_preferences (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id               UUID NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    target_roles          TEXT[] DEFAULT '{}',
    preferred_locations   TEXT[] DEFAULT '{}',
    work_type             VARCHAR(50) DEFAULT 'any',  -- 'remote','hybrid','onsite','any'
    salary_min_inr        INTEGER,
    salary_max_inr        INTEGER,
    experience_level      VARCHAR(50) DEFAULT 'entry',  -- 'internship','entry','mid','senior'
    job_types             TEXT[] DEFAULT ARRAY['fulltime'],
    industry_include      TEXT[] DEFAULT '{}',
    industry_exclude      TEXT[] DEFAULT '{}',
    blacklisted_companies TEXT[] DEFAULT '{}',
    dream_companies       TEXT[] DEFAULT '{}',
    keyword_blacklist     TEXT[] DEFAULT ARRAY['10+ years','US citizenship required','no freshers'],
    score_threshold       INTEGER DEFAULT 70 CHECK (score_threshold BETWEEN 50 AND 95),
    max_apps_per_day      INTEGER DEFAULT 10 CHECK (max_apps_per_day BETWEEN 1 AND 30),
    schedule_cron         VARCHAR(100) DEFAULT '0 7 * * *',
    telegram_chat_id      VARCHAR(100),
    llm_provider          VARCHAR(50) DEFAULT 'gemini',  -- 'gemini','claude','ollama'
    llm_quality_mode      VARCHAR(50) DEFAULT 'balanced',
    enabled_boards        TEXT[] DEFAULT ARRAY['wellfound','internshala'],
    created_at            TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at            TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ───────────────────────────
-- JOBS
-- ───────────────────────────

CREATE TABLE jobs (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    board            VARCHAR(50) NOT NULL,        -- 'wellfound','internshala','naukri','foundit','career_page'
    external_id      VARCHAR(500) NOT NULL,       -- board's own job ID or URL slug
    title            VARCHAR(500) NOT NULL,
    company          VARCHAR(255) NOT NULL,
    description      TEXT,
    url              TEXT NOT NULL,
    location         VARCHAR(255),
    work_type        VARCHAR(50),                 -- 'remote','hybrid','onsite'
    salary_min_inr   INTEGER,                     -- null if not specified in posting
    salary_max_inr   INTEGER,
    experience_level VARCHAR(50),
    skills_required  TEXT[] DEFAULT '{}',
    posted_at        TIMESTAMP WITH TIME ZONE,
    scraped_at       TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    content_hash     VARCHAR(64),                 -- SHA256(title+company+description) for dedup
    status           VARCHAR(50) DEFAULT 'new',   -- 'new','scored','queued','applied','skipped','expired'
    CONSTRAINT jobs_board_external_id_unique UNIQUE (board, external_id),
    CONSTRAINT jobs_content_hash_unique UNIQUE (content_hash)
);

CREATE TABLE job_scores (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id           UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    resume_id        UUID NOT NULL REFERENCES resumes(id) ON DELETE CASCADE,
    total_score      INTEGER NOT NULL CHECK (total_score BETWEEN 0 AND 100),
    technical_match  INTEGER CHECK (technical_match BETWEEN 0 AND 100),
    experience_match INTEGER CHECK (experience_match BETWEEN 0 AND 100),
    domain_match     INTEGER CHECK (domain_match BETWEEN 0 AND 100),
    location_match   INTEGER CHECK (location_match BETWEEN 0 AND 100),
    growth_potential INTEGER CHECK (growth_potential BETWEEN 0 AND 100),
    missing_skills   TEXT[] DEFAULT '{}',
    matching_skills  TEXT[] DEFAULT '{}',
    score_explanation TEXT,
    recommendation   VARCHAR(20) CHECK (recommendation IN ('APPLY','SKIP','STRETCH')),
    scored_at        TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT job_scores_unique UNIQUE (job_id, resume_id)
);

-- ───────────────────────────
-- APPLICATIONS
-- ───────────────────────────

CREATE TABLE applications (
    id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id                   UUID NOT NULL REFERENCES jobs(id),
    resume_id                UUID NOT NULL REFERENCES resumes(id),
    trace_id                 UUID NOT NULL UNIQUE DEFAULT gen_random_uuid(),
    tailored_resume_pdf_path TEXT,               -- DATA_DIR/applications/{id}/resume_tailored.pdf
    tailored_resume_docx_path TEXT,              -- DATA_DIR/applications/{id}/resume_tailored.docx
    is_dream_company         BOOLEAN DEFAULT false,
    status                   VARCHAR(50) DEFAULT 'queued',
    -- Valid statuses:
    -- 'queued'           → waiting for agent to pick up
    -- 'agent_processing' → agent currently filling this form
    -- 'needs_human'      → paused, waiting for user input
    -- 'ready_to_submit'  → all fields filled, user must click Submit
    -- 'submitted'        → user clicked Submit, agent executed
    -- 'shortlisted'      → user manually updated
    -- 'interview'        → user manually updated
    -- 'rejected'         → user manually updated or detected
    -- 'offer'            → user manually updated
    -- 'ghosted'          → no response in 14+ days
    -- 'interrupted'      → agent crashed, can retry
    -- 'failed'           → unrecoverable failure
    failure_reason           VARCHAR(100),       -- only if status='failed'
    notes                    TEXT,
    queued_at                TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    started_at               TIMESTAMP WITH TIME ZONE,
    completed_at             TIMESTAMP WITH TIME ZONE,
    submitted_at             TIMESTAMP WITH TIME ZONE
);

CREATE TABLE cover_letters (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id      UUID NOT NULL UNIQUE REFERENCES applications(id) ON DELETE CASCADE,
    content             TEXT NOT NULL,
    word_count          INTEGER,
    tone                VARCHAR(50) DEFAULT 'professional',
    fact_check_passed   BOOLEAN DEFAULT false,
    generation_attempts INTEGER DEFAULT 1,
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Step-by-step agent execution log (enables crash recovery and audit trail)
CREATE TABLE agent_logs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id  UUID NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    trace_id        UUID NOT NULL,
    step_number     INTEGER NOT NULL,
    field_name      VARCHAR(255),
    action_type     VARCHAR(100),     -- 'navigate','fill','select','upload','click','validate','screenshot'
    action_data     JSONB,            -- {value, selector, url} depending on action
    confidence      FLOAT CHECK (confidence BETWEEN 0 AND 1),
    status          VARCHAR(50),      -- 'complete','needs_human','failed','skipped'
    screenshot_path TEXT,             -- DATA_DIR/applications/{id}/step_{step_number}.png
    attempt_number  INTEGER DEFAULT 1,
    error_message   TEXT,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Event stream — used for WebSocket live feed and dashboard timeline
CREATE TABLE application_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id  UUID REFERENCES applications(id) ON DELETE CASCADE,  -- nullable for system events
    trace_id        UUID,
    event_type      VARCHAR(100) NOT NULL,  -- matches WebSocket event names exactly
    event_data      JSONB DEFAULT '{}',
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_application_events_trace_id ON application_events(trace_id);
CREATE INDEX idx_application_events_created_at ON application_events(created_at DESC);

-- ───────────────────────────
-- MEMORY
-- ───────────────────────────

-- Previously answered screening questions — reuse answers on similar questions
CREATE TABLE qa_memory (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    question_hash     VARCHAR(64) NOT NULL,     -- SHA256 of normalized question text
    question_text     TEXT NOT NULL,
    question_category VARCHAR(50),              -- 'behavioral','technical','motivation','availability','salary','di'
    answer_text       TEXT NOT NULL,
    confidence        FLOAT DEFAULT 1.0,
    board             VARCHAR(50),
    company           VARCHAR(255),
    used_count        INTEGER DEFAULT 1,
    last_used_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at        TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT qa_memory_hash_unique UNIQUE (question_hash)
);

-- Cached form field maps per board — avoids repeated vision LLM calls for same form layout
CREATE TABLE form_template_cache (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    board                VARCHAR(50) NOT NULL,
    page_url_pattern     VARCHAR(500) NOT NULL,   -- e.g. 'https://wellfound.com/jobs/*/apply'
    page_structure_hash  VARCHAR(64) NOT NULL,     -- SHA256 of DOM structure snapshot
    field_map            JSONB NOT NULL,           -- [{field_name, label, type, selector_hint}]
    cached_at            TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_used_at         TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    hit_count            INTEGER DEFAULT 1,
    CONSTRAINT form_template_cache_unique UNIQUE (board, page_url_pattern)
);

-- Company research cache — 7-day TTL
CREATE TABLE company_cache (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_name_key      VARCHAR(255) NOT NULL UNIQUE,  -- lowercase, stripped
    mission               TEXT,
    values_text           TEXT,
    recent_news           TEXT,
    culture_signals       TEXT,
    cached_at             TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at            TIMESTAMP WITH TIME ZONE DEFAULT (NOW() + INTERVAL '7 days')
);

-- ───────────────────────────
-- SYSTEM
-- ───────────────────────────

CREATE TABLE tasks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_type       VARCHAR(100) NOT NULL,  -- 'morning_scan','on_demand_scan','morning_digest','follow_up_check'
    status          VARCHAR(50) DEFAULT 'pending',  -- 'pending','running','completed','failed'
    scheduled_at    TIMESTAMP WITH TIME ZONE NOT NULL,
    started_at      TIMESTAMP WITH TIME ZONE,
    completed_at    TIMESTAMP WITH TIME ZONE,
    jobs_found      INTEGER DEFAULT 0,
    apps_attempted  INTEGER DEFAULT 0,
    apps_completed  INTEGER DEFAULT 0,
    result_summary  TEXT,
    error_message   TEXT
);

-- ───────────────────────────
-- INDEXES
-- ───────────────────────────

CREATE INDEX idx_jobs_status ON jobs(status);
CREATE INDEX idx_jobs_board ON jobs(board);
CREATE INDEX idx_jobs_scraped_at ON jobs(scraped_at DESC);
CREATE INDEX idx_job_scores_total_score ON job_scores(total_score DESC);
CREATE INDEX idx_applications_status ON applications(status);
CREATE INDEX idx_applications_queued_at ON applications(queued_at DESC);
CREATE INDEX idx_agent_logs_application_id ON agent_logs(application_id);
CREATE INDEX idx_agent_logs_trace_id ON agent_logs(trace_id);
