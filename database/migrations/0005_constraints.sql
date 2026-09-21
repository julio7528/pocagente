BEGIN;

-- UNIQUE constraints.
ALTER TABLE rag.sources
    ADD CONSTRAINT uq_sources__origin_reference UNIQUE (origin, reference);
ALTER TABLE rag.documents
    ADD CONSTRAINT uq_documents__source_id_document_key UNIQUE (source_id, document_key),
    ADD CONSTRAINT uq_documents__document_id_source_id UNIQUE (document_id, source_id);
ALTER TABLE rag.chunks
    ADD CONSTRAINT uq_chunks__document_id_chunk_order UNIQUE (document_id, chunk_order);
ALTER TABLE ops.automation_runs
    ADD CONSTRAINT uq_automation_runs__run_id_robot UNIQUE (run_id, robot);
ALTER TABLE ops.incoming_emails
    ADD CONSTRAINT uq_incoming_emails__email_id_run_id UNIQUE (email_id, run_id);
ALTER TABLE ops.service_requests
    ADD CONSTRAINT uq_service_requests__protocol_number UNIQUE (protocol_number),
    ADD CONSTRAINT uq_service_requests__email_id UNIQUE (email_id);
ALTER TABLE ops.establishments
    ADD CONSTRAINT uq_establishments__req_att_est
        UNIQUE (request_id, attachment_id, establishment_number),
    ADD CONSTRAINT uq_establishments__req_genfile
        UNIQUE (request_id, generated_file_name);

-- RAG CHECK constraints.
ALTER TABLE rag.sources
    ADD CONSTRAINT ck_sources__name_nonblank CHECK (btrim(name) <> ''),
    ADD CONSTRAINT ck_sources__source_type_allowed
        CHECK (source_type IN ('INTERNAL_DOCUMENT', 'INTERNAL_POLICY', 'PUBLIC_OFFICIAL')),
    ADD CONSTRAINT ck_sources__origin_allowed CHECK (origin IN ('INTERNAL', 'PUBLIC')),
    ADD CONSTRAINT ck_sources__source_type_origin_agreement CHECK (
        (origin = 'INTERNAL' AND source_type IN ('INTERNAL_DOCUMENT', 'INTERNAL_POLICY'))
        OR (origin = 'PUBLIC' AND source_type = 'PUBLIC_OFFICIAL')
    ),
    ADD CONSTRAINT ck_sources__reference_nonblank CHECK (btrim(reference) <> ''),
    ADD CONSTRAINT ck_sources__status_allowed CHECK (status IN ('ACTIVE', 'INACTIVE')),
    ADD CONSTRAINT ck_sources__priority_nonnegative CHECK (priority >= 0);

ALTER TABLE rag.documents
    ADD CONSTRAINT ck_documents__document_key_nonblank CHECK (btrim(document_key) <> ''),
    ADD CONSTRAINT ck_documents__title_nonblank CHECK (btrim(title) <> ''),
    ADD CONSTRAINT ck_documents__document_type_allowed CHECK (
        document_type IN ('PDD', 'SDD', 'TECHNICAL_OVERVIEW', 'POLICY', 'PUBLIC_PAGE', 'OTHER')
    ),
    ADD CONSTRAINT ck_documents__status_allowed CHECK (status IN ('PENDING', 'ACTIVE', 'INACTIVE')),
    ADD CONSTRAINT ck_documents__content_checksum_format_when_present CHECK (
        content_checksum IS NULL OR content_checksum ~ '^[0-9a-f]{64}$'
    );

ALTER TABLE rag.chunks
    ADD CONSTRAINT ck_chunks__content_nonblank CHECK (btrim(content) <> ''),
    ADD CONSTRAINT ck_chunks__chunk_order_nonnegative CHECK (chunk_order >= 0),
    ADD CONSTRAINT ck_chunks__content_type_allowed CHECK (
        content_type IN ('TEXT', 'BUSINESS_RULE', 'PROCEDURE', 'TECHNICAL', 'TABLE', 'CODE')
    ),
    ADD CONSTRAINT ck_chunks__metadata_object CHECK (jsonb_typeof(metadata) = 'object');

ALTER TABLE rag.ingestion_runs
    ADD CONSTRAINT ck_ingestion_runs__status_allowed
        CHECK (status IN ('RUNNING', 'SUCCESS', 'ERROR', 'SKIPPED')),
    ADD CONSTRAINT ck_ingestion_runs__operation_allowed
        CHECK (operation IN ('INGEST', 'REINGEST', 'SKIPPED_UNCHANGED')),
    ADD CONSTRAINT ck_ingestion_runs__chunks_created_nonnegative CHECK (chunks_created >= 0),
    ADD CONSTRAINT ck_ingestion_runs__lifecycle_consistent CHECK (
        (status = 'RUNNING' AND finished_at IS NULL AND chunks_created = 0)
        OR (
            status IN ('SUCCESS', 'ERROR', 'SKIPPED')
            AND finished_at IS NOT NULL
            AND finished_at >= started_at
            AND (
                (status = 'SUCCESS' AND chunks_created > 0)
                OR (status IN ('ERROR', 'SKIPPED') AND chunks_created = 0)
            )
        )
    );

-- OPS CHECK constraints.
ALTER TABLE ops.automation_runs
    ADD CONSTRAINT ck_automation_runs__robot_allowed CHECK (robot IN ('R1', 'R2')),
    ADD CONSTRAINT ck_automation_runs__status_allowed
        CHECK (status IN ('RUNNING', 'SUCCESS', 'PARTIAL', 'ERROR')),
    ADD CONSTRAINT ck_automation_runs__lifecycle_consistent CHECK (
        (status = 'RUNNING' AND finished_at IS NULL)
        OR (
            status IN ('SUCCESS', 'PARTIAL', 'ERROR')
            AND finished_at IS NOT NULL
            AND finished_at >= started_at
        )
    );

ALTER TABLE ops.incoming_emails
    ADD CONSTRAINT ck_incoming_emails__sender_nonblank CHECK (btrim(sender) <> ''),
    ADD CONSTRAINT ck_incoming_emails__recipient_nonblank CHECK (btrim(recipient) <> ''),
    ADD CONSTRAINT ck_incoming_emails__attachment_count_nonnegative CHECK (attachment_count >= 0),
    ADD CONSTRAINT ck_incoming_emails__sender_status_allowed
        CHECK (sender_status IN ('PENDING', 'VALID', 'INVALID')),
    ADD CONSTRAINT ck_incoming_emails__processing_status_allowed CHECK (
        processing_status IN ('RECEIVED', 'PROCESSING', 'PROCESSED', 'REJECTED', 'ERROR')
    ),
    ADD CONSTRAINT ck_incoming_emails__processed_at_terminal CHECK (
        (processing_status IN ('RECEIVED', 'PROCESSING') AND processed_at IS NULL)
        OR (
            processing_status IN ('PROCESSED', 'REJECTED', 'ERROR')
            AND processed_at IS NOT NULL
            AND processed_at >= received_at
        )
    ),
    ADD CONSTRAINT ck_incoming_emails__rejection_reason_when_rejected CHECK (
        processing_status <> 'REJECTED'
        OR (rejection_reason IS NOT NULL AND btrim(rejection_reason) <> '')
    );

ALTER TABLE ops.email_attachments
    ADD CONSTRAINT ck_email_attachments__file_name_nonblank CHECK (btrim(file_name) <> ''),
    ADD CONSTRAINT ck_email_attachments__establishment_count_nonnegative_when_present
        CHECK (establishment_count IS NULL OR establishment_count >= 0),
    ADD CONSTRAINT ck_email_attachments__validation_status_allowed
        CHECK (validation_status IN ('PENDING', 'VALID', 'INVALID')),
    ADD CONSTRAINT ck_email_attachments__processing_status_allowed
        CHECK (processing_status IN ('PENDING', 'PROCESSING', 'PROCESSED', 'ERROR'));

ALTER TABLE ops.service_requests
    ADD CONSTRAINT ck_service_requests__status_allowed CHECK (
        status IN ('CREATED', 'PROCESSING', 'WAITING_RESULT', 'COMPLETED', 'FAILED')
    ),
    ADD CONSTRAINT ck_service_requests__failure_reason_when_failed CHECK (
        status <> 'FAILED' OR (failure_reason IS NOT NULL AND btrim(failure_reason) <> '')
    ),
    ADD CONSTRAINT ck_service_requests__completed_at_consistent CHECK (
        (status = 'COMPLETED' AND completed_at IS NOT NULL)
        OR (status <> 'COMPLETED' AND completed_at IS NULL)
    );

ALTER TABLE ops.establishments
    ADD CONSTRAINT ck_establishments__establishment_number_nonblank
        CHECK (btrim(establishment_number) <> ''),
    ADD CONSTRAINT ck_establishments__generated_file_name_nonblank
        CHECK (btrim(generated_file_name) <> ''),
    ADD CONSTRAINT ck_establishments__processing_status_allowed CHECK (
        processing_status IN (
            'PENDING', 'UPLOADING', 'WAITING_RESULT', 'RESULT_AVAILABLE', 'COMPLETED', 'ERROR'
        )
    ),
    ADD CONSTRAINT ck_establishments__upload_status_allowed
        CHECK (upload_status IN ('PENDING', 'SUCCESS', 'ERROR')),
    ADD CONSTRAINT ck_establishments__download_status_allowed
        CHECK (download_status IN ('NOT_AVAILABLE', 'AVAILABLE', 'DOWNLOADED', 'ERROR')),
    ADD CONSTRAINT ck_establishments__upload_at_when_success CHECK (
        upload_status <> 'SUCCESS' OR upload_at IS NOT NULL
    ),
    ADD CONSTRAINT ck_establishments__download_at_when_downloaded CHECK (
        download_status <> 'DOWNLOADED' OR download_at IS NOT NULL
    );

ALTER TABLE ops.execution_log
    ADD CONSTRAINT ck_execution_log__robot_allowed CHECK (robot IN ('R1', 'R2')),
    ADD CONSTRAINT ck_execution_log__event_nonblank CHECK (btrim(event) <> ''),
    ADD CONSTRAINT ck_execution_log__status_allowed
        CHECK (status IN ('SUCCESS', 'ERROR', 'EXCEPTION')),
    ADD CONSTRAINT ck_execution_log__message_nonblank CHECK (btrim(message) <> '');

-- AUDIT CHECK constraints.
ALTER TABLE audit.security_events
    ADD CONSTRAINT ck_security_events__event_type_allowed CHECK (
        event_type IN (
            'CREDENTIAL_REQUEST', 'SECRET_REQUEST', 'DATABASE_ACCESS_REQUEST',
            'SENSITIVE_INFRASTRUCTURE_REQUEST', 'PROMPT_INJECTION',
            'AUTHORIZATION_BYPASS_ATTEMPT', 'SECURITY_POLICY_PROBE'
        )
    ),
    ADD CONSTRAINT ck_security_events__source_component_nonblank
        CHECK (btrim(source_component) <> ''),
    ADD CONSTRAINT ck_security_events__user_identifier_nonblank_when_present
        CHECK (user_identifier IS NULL OR btrim(user_identifier) <> ''),
    ADD CONSTRAINT ck_security_events__request_reference_nonblank_when_present
        CHECK (request_reference IS NULL OR btrim(request_reference) <> ''),
    ADD CONSTRAINT ck_security_events__resource_category_allowed CHECK (
        resource_category IS NULL OR resource_category IN (
            'DATABASE_CREDENTIAL', 'API_KEY', 'PASSWORD', 'ACCESS_TOKEN',
            'PRIVATE_KEY', 'COOKIE', 'CONNECTION_STRING', 'SECRET_LOCATION',
            'PROTECTED_PATH', 'AUTHENTICATION_CONTROL', 'INTERNAL_INFRASTRUCTURE',
            'OTHER_PROTECTED_RESOURCE'
        )
    ),
    ADD CONSTRAINT ck_security_events__sanitized_content_nonblank_when_present
        CHECK (sanitized_content IS NULL OR btrim(sanitized_content) <> ''),
    ADD CONSTRAINT ck_security_events__action_taken_allowed CHECK (
        action_taken IN ('BLOCK', 'DENY_ACCESS', 'REDACT', 'SAFE_RESPONSE', 'ESCALATE')
    ),
    ADD CONSTRAINT ck_security_events__result_allowed
        CHECK (result IN ('SUCCESS', 'PARTIAL', 'ERROR')),
    ADD CONSTRAINT ck_security_events__review_status_allowed
        CHECK (review_status IN ('UNREVIEWED', 'REVIEWED')),
    ADD CONSTRAINT ck_security_events__review_timestamps_consistent CHECK (
        (review_status = 'UNREVIEWED' AND reviewed_at IS NULL)
        OR (
            review_status = 'REVIEWED'
            AND reviewed_at IS NOT NULL
            AND reviewed_at >= occurred_at
        )
    ),
    ADD CONSTRAINT ck_security_events__review_note_nonblank_when_present
        CHECK (review_note IS NULL OR btrim(review_note) <> '');

-- Simple foreign keys.
ALTER TABLE rag.documents
    ADD CONSTRAINT fk_documents__source_id
        FOREIGN KEY (source_id) REFERENCES rag.sources (source_id)
        ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE rag.chunks
    ADD CONSTRAINT fk_chunks__document_id
        FOREIGN KEY (document_id) REFERENCES rag.documents (document_id)
        ON DELETE CASCADE ON UPDATE RESTRICT;
ALTER TABLE rag.ingestion_runs
    ADD CONSTRAINT fk_ingestion_runs__source_id
        FOREIGN KEY (source_id) REFERENCES rag.sources (source_id)
        ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE ops.incoming_emails
    ADD CONSTRAINT fk_incoming_emails__run_id
        FOREIGN KEY (run_id) REFERENCES ops.automation_runs (run_id)
        ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE ops.email_attachments
    ADD CONSTRAINT fk_email_attachments__email_id
        FOREIGN KEY (email_id) REFERENCES ops.incoming_emails (email_id)
        ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE ops.establishments
    ADD CONSTRAINT fk_establishments__request_id
        FOREIGN KEY (request_id) REFERENCES ops.service_requests (request_id)
        ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE ops.establishments
    ADD CONSTRAINT fk_establishments__attachment_id
        FOREIGN KEY (attachment_id) REFERENCES ops.email_attachments (attachment_id)
        ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE ops.execution_log
    ADD CONSTRAINT fk_execution_log__email_id
        FOREIGN KEY (email_id) REFERENCES ops.incoming_emails (email_id)
        ON DELETE SET NULL ON UPDATE RESTRICT;
ALTER TABLE ops.execution_log
    ADD CONSTRAINT fk_execution_log__attachment_id
        FOREIGN KEY (attachment_id) REFERENCES ops.email_attachments (attachment_id)
        ON DELETE SET NULL ON UPDATE RESTRICT;
ALTER TABLE ops.execution_log
    ADD CONSTRAINT fk_execution_log__request_id
        FOREIGN KEY (request_id) REFERENCES ops.service_requests (request_id)
        ON DELETE SET NULL ON UPDATE RESTRICT;
ALTER TABLE ops.execution_log
    ADD CONSTRAINT fk_execution_log__establishment_id
        FOREIGN KEY (establishment_id) REFERENCES ops.establishments (establishment_id)
        ON DELETE SET NULL ON UPDATE RESTRICT;

-- Composite foreign keys.
ALTER TABLE rag.ingestion_runs
    ADD CONSTRAINT fk_ingestion_runs__document_id_source_id
        FOREIGN KEY (document_id, source_id)
        REFERENCES rag.documents (document_id, source_id)
        ON DELETE SET NULL (document_id) ON UPDATE RESTRICT;
ALTER TABLE ops.service_requests
    ADD CONSTRAINT fk_service_requests__email_id_r1_run_id
        FOREIGN KEY (email_id, r1_run_id)
        REFERENCES ops.incoming_emails (email_id, run_id)
        ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE ops.execution_log
    ADD CONSTRAINT fk_execution_log__run_id_robot
        FOREIGN KEY (run_id, robot)
        REFERENCES ops.automation_runs (run_id, robot)
        ON DELETE RESTRICT ON UPDATE RESTRICT;

COMMIT;
