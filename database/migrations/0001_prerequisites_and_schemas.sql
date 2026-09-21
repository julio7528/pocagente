BEGIN;

-- Fail before creating application schemas when the PostgreSQL major version
-- differs from the version approved for this project.
DO $migration$
DECLARE
    server_major integer;
BEGIN
    server_major := current_setting('server_version_num')::integer / 10000;

    IF server_major <> 17 THEN
        RAISE EXCEPTION
            'Unsupported PostgreSQL major version: expected 17, found %',
            server_major;
    END IF;
END
$migration$;

CREATE EXTENSION IF NOT EXISTS vector;

-- Validate the active extension version and its vector type without creating
-- a temporary or permanent application table.
DO $migration$
DECLARE
    vector_version text;
    vector_schema name;
BEGIN
    SELECT extension.extversion, namespace.nspname
    INTO vector_version, vector_schema
    FROM pg_extension AS extension
    JOIN pg_namespace AS namespace
        ON namespace.oid = extension.extnamespace
    WHERE extension.extname = 'vector';

    IF vector_version IS DISTINCT FROM '0.8.6' THEN
        RAISE EXCEPTION
            'Unsupported pgvector version: expected 0.8.6, found %',
            coalesce(vector_version, '<not installed>');
    END IF;

    IF to_regtype(format('%I.vector', vector_schema)) IS NULL THEN
        RAISE EXCEPTION 'pgvector type vector is unavailable';
    END IF;
END
$migration$;

CREATE SCHEMA rag;
CREATE SCHEMA ops;
CREATE SCHEMA audit;

COMMIT;
