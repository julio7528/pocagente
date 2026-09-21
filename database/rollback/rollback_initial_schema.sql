BEGIN;

-- This destructive rollback is for the empty local POC only. Refuse to
-- proceed when any approved application table contains data.
DO $rollback$
BEGIN
    IF EXISTS (SELECT 1 FROM rag.sources)
        OR EXISTS (SELECT 1 FROM rag.documents)
        OR EXISTS (SELECT 1 FROM rag.chunks)
        OR EXISTS (SELECT 1 FROM rag.ingestion_runs)
        OR EXISTS (SELECT 1 FROM ops.automation_runs)
        OR EXISTS (SELECT 1 FROM ops.incoming_emails)
        OR EXISTS (SELECT 1 FROM ops.email_attachments)
        OR EXISTS (SELECT 1 FROM ops.service_requests)
        OR EXISTS (SELECT 1 FROM ops.establishments)
        OR EXISTS (SELECT 1 FROM ops.execution_log)
        OR EXISTS (SELECT 1 FROM audit.security_events) THEN
        RAISE EXCEPTION
            'Refusing destructive initial-schema rollback: application data exists';
    END IF;
END
$rollback$;

-- Explicit indexes created by 0006_indexes.sql.
DROP INDEX rag.gin_chunks__search_vector;
DROP INDEX rag.idx_ingestion_runs__source_id_started_at;
DROP INDEX rag.idx_ingestion_runs__document_id_started_at;
DROP INDEX ops.idx_automation_runs__robot_started_at;
DROP INDEX ops.idx_automation_runs__status_started_at;
DROP INDEX ops.idx_automation_runs__started_at;
DROP INDEX ops.idx_incoming_emails__run_id_received_at;
DROP INDEX ops.idx_incoming_emails__processing_status_received_at;
DROP INDEX ops.idx_email_attachments__email_id;
DROP INDEX ops.idx_service_requests__r1_run_id_created_at;
DROP INDEX ops.idx_service_requests__status_updated_at;
DROP INDEX ops.idx_establishments__attachment_id;
DROP INDEX ops.idx_establishments__r2_eligibility;
DROP INDEX ops.idx_execution_log__run_id_logged_at;
DROP INDEX ops.idx_execution_log__request_id_logged_at;
DROP INDEX ops.idx_execution_log__establishment_id_logged_at;
DROP INDEX ops.idx_execution_log__logged_at;
DROP INDEX audit.idx_security_events__occurred_at;
DROP INDEX audit.idx_security_events__event_type_occurred_at;
DROP INDEX audit.idx_security_events__request_reference_occurred_at;
DROP INDEX audit.idx_security_events__unreviewed_occurred_at;

-- Foreign keys created by 0005_constraints.sql.
ALTER TABLE rag.ingestion_runs DROP CONSTRAINT fk_ingestion_runs__document_id_source_id;
ALTER TABLE ops.execution_log DROP CONSTRAINT fk_execution_log__run_id_robot;
ALTER TABLE ops.service_requests DROP CONSTRAINT fk_service_requests__email_id_r1_run_id;
ALTER TABLE rag.documents DROP CONSTRAINT fk_documents__source_id;
ALTER TABLE rag.chunks DROP CONSTRAINT fk_chunks__document_id;
ALTER TABLE rag.ingestion_runs DROP CONSTRAINT fk_ingestion_runs__source_id;
ALTER TABLE ops.incoming_emails DROP CONSTRAINT fk_incoming_emails__run_id;
ALTER TABLE ops.email_attachments DROP CONSTRAINT fk_email_attachments__email_id;
ALTER TABLE ops.establishments DROP CONSTRAINT fk_establishments__request_id;
ALTER TABLE ops.establishments DROP CONSTRAINT fk_establishments__attachment_id;
ALTER TABLE ops.execution_log DROP CONSTRAINT fk_execution_log__email_id;
ALTER TABLE ops.execution_log DROP CONSTRAINT fk_execution_log__attachment_id;
ALTER TABLE ops.execution_log DROP CONSTRAINT fk_execution_log__request_id;
ALTER TABLE ops.execution_log DROP CONSTRAINT fk_execution_log__establishment_id;

-- CHECK constraints created by 0005_constraints.sql.
ALTER TABLE rag.sources DROP CONSTRAINT ck_sources__name_nonblank;
ALTER TABLE rag.sources DROP CONSTRAINT ck_sources__source_type_allowed;
ALTER TABLE rag.sources DROP CONSTRAINT ck_sources__origin_allowed;
ALTER TABLE rag.sources DROP CONSTRAINT ck_sources__source_type_origin_agreement;
ALTER TABLE rag.sources DROP CONSTRAINT ck_sources__reference_nonblank;
ALTER TABLE rag.sources DROP CONSTRAINT ck_sources__status_allowed;
ALTER TABLE rag.sources DROP CONSTRAINT ck_sources__priority_nonnegative;
ALTER TABLE rag.documents DROP CONSTRAINT ck_documents__document_key_nonblank;
ALTER TABLE rag.documents DROP CONSTRAINT ck_documents__title_nonblank;
ALTER TABLE rag.documents DROP CONSTRAINT ck_documents__document_type_allowed;
ALTER TABLE rag.documents DROP CONSTRAINT ck_documents__status_allowed;
ALTER TABLE rag.documents DROP CONSTRAINT ck_documents__content_checksum_format_when_present;
ALTER TABLE rag.chunks DROP CONSTRAINT ck_chunks__content_nonblank;
ALTER TABLE rag.chunks DROP CONSTRAINT ck_chunks__chunk_order_nonnegative;
ALTER TABLE rag.chunks DROP CONSTRAINT ck_chunks__content_type_allowed;
ALTER TABLE rag.chunks DROP CONSTRAINT ck_chunks__metadata_object;
ALTER TABLE rag.ingestion_runs DROP CONSTRAINT ck_ingestion_runs__status_allowed;
ALTER TABLE rag.ingestion_runs DROP CONSTRAINT ck_ingestion_runs__operation_allowed;
ALTER TABLE rag.ingestion_runs DROP CONSTRAINT ck_ingestion_runs__chunks_created_nonnegative;
ALTER TABLE rag.ingestion_runs DROP CONSTRAINT ck_ingestion_runs__lifecycle_consistent;
ALTER TABLE ops.automation_runs DROP CONSTRAINT ck_automation_runs__robot_allowed;
ALTER TABLE ops.automation_runs DROP CONSTRAINT ck_automation_runs__status_allowed;
ALTER TABLE ops.automation_runs DROP CONSTRAINT ck_automation_runs__lifecycle_consistent;
ALTER TABLE ops.incoming_emails DROP CONSTRAINT ck_incoming_emails__sender_nonblank;
ALTER TABLE ops.incoming_emails DROP CONSTRAINT ck_incoming_emails__recipient_nonblank;
ALTER TABLE ops.incoming_emails DROP CONSTRAINT ck_incoming_emails__attachment_count_nonnegative;
ALTER TABLE ops.incoming_emails DROP CONSTRAINT ck_incoming_emails__sender_status_allowed;
ALTER TABLE ops.incoming_emails DROP CONSTRAINT ck_incoming_emails__processing_status_allowed;
ALTER TABLE ops.incoming_emails DROP CONSTRAINT ck_incoming_emails__processed_at_terminal;
ALTER TABLE ops.incoming_emails DROP CONSTRAINT ck_incoming_emails__rejection_reason_when_rejected;
ALTER TABLE ops.email_attachments DROP CONSTRAINT ck_email_attachments__file_name_nonblank;
ALTER TABLE ops.email_attachments DROP CONSTRAINT ck_email_attachments__establishment_count_nonnegative_when_present;
ALTER TABLE ops.email_attachments DROP CONSTRAINT ck_email_attachments__validation_status_allowed;
ALTER TABLE ops.email_attachments DROP CONSTRAINT ck_email_attachments__processing_status_allowed;
ALTER TABLE ops.service_requests DROP CONSTRAINT ck_service_requests__status_allowed;
ALTER TABLE ops.service_requests DROP CONSTRAINT ck_service_requests__failure_reason_when_failed;
ALTER TABLE ops.service_requests DROP CONSTRAINT ck_service_requests__completed_at_consistent;
ALTER TABLE ops.establishments DROP CONSTRAINT ck_establishments__establishment_number_nonblank;
ALTER TABLE ops.establishments DROP CONSTRAINT ck_establishments__generated_file_name_nonblank;
ALTER TABLE ops.establishments DROP CONSTRAINT ck_establishments__processing_status_allowed;
ALTER TABLE ops.establishments DROP CONSTRAINT ck_establishments__upload_status_allowed;
ALTER TABLE ops.establishments DROP CONSTRAINT ck_establishments__download_status_allowed;
ALTER TABLE ops.establishments DROP CONSTRAINT ck_establishments__upload_at_when_success;
ALTER TABLE ops.establishments DROP CONSTRAINT ck_establishments__download_at_when_downloaded;
ALTER TABLE ops.execution_log DROP CONSTRAINT ck_execution_log__robot_allowed;
ALTER TABLE ops.execution_log DROP CONSTRAINT ck_execution_log__event_nonblank;
ALTER TABLE ops.execution_log DROP CONSTRAINT ck_execution_log__status_allowed;
ALTER TABLE ops.execution_log DROP CONSTRAINT ck_execution_log__message_nonblank;
ALTER TABLE audit.security_events DROP CONSTRAINT ck_security_events__event_type_allowed;
ALTER TABLE audit.security_events DROP CONSTRAINT ck_security_events__source_component_nonblank;
ALTER TABLE audit.security_events DROP CONSTRAINT ck_security_events__user_identifier_nonblank_when_present;
ALTER TABLE audit.security_events DROP CONSTRAINT ck_security_events__request_reference_nonblank_when_present;
ALTER TABLE audit.security_events DROP CONSTRAINT ck_security_events__resource_category_allowed;
ALTER TABLE audit.security_events DROP CONSTRAINT ck_security_events__sanitized_content_nonblank_when_present;
ALTER TABLE audit.security_events DROP CONSTRAINT ck_security_events__action_taken_allowed;
ALTER TABLE audit.security_events DROP CONSTRAINT ck_security_events__result_allowed;
ALTER TABLE audit.security_events DROP CONSTRAINT ck_security_events__review_status_allowed;
ALTER TABLE audit.security_events DROP CONSTRAINT ck_security_events__review_timestamps_consistent;
ALTER TABLE audit.security_events DROP CONSTRAINT ck_security_events__review_note_nonblank_when_present;

-- Non-PK UNIQUE constraints created by 0005_constraints.sql.
ALTER TABLE rag.sources DROP CONSTRAINT uq_sources__origin_reference;
ALTER TABLE rag.documents DROP CONSTRAINT uq_documents__source_id_document_key;
ALTER TABLE rag.documents DROP CONSTRAINT uq_documents__document_id_source_id;
ALTER TABLE rag.chunks DROP CONSTRAINT uq_chunks__document_id_chunk_order;
ALTER TABLE ops.automation_runs DROP CONSTRAINT uq_automation_runs__run_id_robot;
ALTER TABLE ops.incoming_emails DROP CONSTRAINT uq_incoming_emails__email_id_run_id;
ALTER TABLE ops.service_requests DROP CONSTRAINT uq_service_requests__protocol_number;
ALTER TABLE ops.service_requests DROP CONSTRAINT uq_service_requests__email_id;
ALTER TABLE ops.establishments DROP CONSTRAINT uq_establishments__req_att_est;
ALTER TABLE ops.establishments DROP CONSTRAINT uq_establishments__req_genfile;

-- Application tables created by 0004, 0003, and 0002, in reverse dependency order.
DROP TABLE audit.security_events;
DROP TABLE ops.execution_log;
DROP TABLE ops.establishments;
DROP TABLE ops.service_requests;
DROP TABLE ops.email_attachments;
DROP TABLE ops.incoming_emails;
DROP TABLE ops.automation_runs;
DROP TABLE rag.ingestion_runs;
DROP TABLE rag.chunks;
DROP TABLE rag.documents;
DROP TABLE rag.sources;

-- Application schemas created by 0001. The shared vector extension remains.
DROP SCHEMA audit;
DROP SCHEMA ops;
DROP SCHEMA rag;

COMMIT;
