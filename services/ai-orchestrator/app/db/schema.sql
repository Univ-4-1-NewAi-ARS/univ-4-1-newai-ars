CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS survey_sessions (
    id UUID PRIMARY KEY,
    survey_id TEXT NOT NULL,
    participant_ref TEXT NOT NULL,
    channel TEXT NOT NULL,
    status TEXT NOT NULL,
    current_question_id TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_survey_sessions_survey_id ON survey_sessions (survey_id);
CREATE INDEX IF NOT EXISTS idx_survey_sessions_status ON survey_sessions (status);

CREATE TABLE IF NOT EXISTS survey_responses (
    id UUID PRIMARY KEY,
    session_id UUID NOT NULL REFERENCES survey_sessions(id) ON DELETE CASCADE,
    question_id TEXT NOT NULL,
    raw_transcript TEXT,
    cleaned_text TEXT,
    answer_type TEXT NOT NULL,
    selected_option TEXT,
    confidence DOUBLE PRECISION NOT NULL,
    sentiment TEXT NOT NULL,
    keywords JSONB NOT NULL DEFAULT '[]'::jsonb,
    needs_retry BOOLEAN NOT NULL DEFAULT false,
    review_required BOOLEAN NOT NULL DEFAULT false,
    reason TEXT,
    agent_result JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_survey_responses_session_id ON survey_responses (session_id);
CREATE INDEX IF NOT EXISTS idx_survey_responses_question_id ON survey_responses (question_id);

CREATE TABLE IF NOT EXISTS audio_records (
    id UUID PRIMARY KEY,
    session_id UUID REFERENCES survey_sessions(id) ON DELETE CASCADE,
    question_id TEXT,
    record_type TEXT NOT NULL,
    file_path TEXT NOT NULL,
    duration_sec DOUBLE PRECISION,
    provider TEXT NOT NULL,
    retention_until TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_audio_records_session_id ON audio_records (session_id);

CREATE TABLE IF NOT EXISTS stats_snapshots (
    id UUID PRIMARY KEY,
    survey_id TEXT NOT NULL,
    snapshot JSONB NOT NULL,
    generated_by TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_stats_snapshots_survey_id ON stats_snapshots (survey_id);

CREATE TABLE IF NOT EXISTS agent_logs (
    id UUID PRIMARY KEY,
    session_id UUID REFERENCES survey_sessions(id) ON DELETE CASCADE,
    question_id TEXT,
    provider TEXT NOT NULL,
    prompt_hash TEXT,
    request_schema JSONB NOT NULL DEFAULT '{}'::jsonb,
    raw_response TEXT,
    parsed_result JSONB,
    retry_count INTEGER NOT NULL DEFAULT 0,
    fallback_used BOOLEAN NOT NULL DEFAULT false,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_agent_logs_session_id ON agent_logs (session_id);
CREATE INDEX IF NOT EXISTS idx_agent_logs_provider ON agent_logs (provider);
