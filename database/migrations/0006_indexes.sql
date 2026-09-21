BEGIN;

-- RAG indexes.
CREATE INDEX gin_chunks__search_vector
    ON rag.chunks
    USING GIN (search_vector);
CREATE INDEX idx_ingestion_runs__source_id_started_at
    ON rag.ingestion_runs (source_id, started_at DESC);
CREATE INDEX idx_ingestion_runs__document_id_started_at
    ON rag.ingestion_runs (document_id, started_at DESC)
    WHERE document_id IS NOT NULL;

-- OPS indexes.
CREATE INDEX idx_automation_runs__robot_started_at
    ON ops.automation_runs (robot, started_at DESC);
CREATE INDEX idx_automation_runs__status_started_at
    ON ops.automation_runs (status, started_at DESC);
CREATE INDEX idx_automation_runs__started_at
    ON ops.automation_runs (started_at DESC);
CREATE INDEX idx_incoming_emails__run_id_received_at
    ON ops.incoming_emails (run_id, received_at DESC);
CREATE INDEX idx_incoming_emails__processing_status_received_at
    ON ops.incoming_emails (processing_status, received_at DESC);
CREATE INDEX idx_email_attachments__email_id
    ON ops.email_attachments (email_id);
CREATE INDEX idx_service_requests__r1_run_id_created_at
    ON ops.service_requests (r1_run_id, created_at DESC);
CREATE INDEX idx_service_requests__status_updated_at
    ON ops.service_requests (status, updated_at DESC);
CREATE INDEX idx_establishments__attachment_id
    ON ops.establishments (attachment_id);
CREATE INDEX idx_establishments__r2_eligibility
    ON ops.establishments (
        processing_status,
        upload_status,
        download_status,
        updated_at
    );
CREATE INDEX idx_execution_log__run_id_logged_at
    ON ops.execution_log (run_id, logged_at DESC);
CREATE INDEX idx_execution_log__request_id_logged_at
    ON ops.execution_log (request_id, logged_at DESC)
    WHERE request_id IS NOT NULL;
CREATE INDEX idx_execution_log__establishment_id_logged_at
    ON ops.execution_log (establishment_id, logged_at DESC)
    WHERE establishment_id IS NOT NULL;
CREATE INDEX idx_execution_log__logged_at
    ON ops.execution_log (logged_at DESC);

-- AUDIT indexes.
CREATE INDEX idx_security_events__occurred_at
    ON audit.security_events (occurred_at DESC);
CREATE INDEX idx_security_events__event_type_occurred_at
    ON audit.security_events (event_type, occurred_at DESC);
CREATE INDEX idx_security_events__request_reference_occurred_at
    ON audit.security_events (request_reference, occurred_at DESC)
    WHERE request_reference IS NOT NULL;
CREATE INDEX idx_security_events__unreviewed_occurred_at
    ON audit.security_events (occurred_at DESC)
    WHERE review_status = 'UNREVIEWED';

COMMIT;
