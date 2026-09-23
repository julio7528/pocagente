"""Connection-bound persistence adapter for the approved OPS schema."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from psycopg import sql
from psycopg.rows import dict_row

from apps.agent_api.app.database.mapping import (
    map_automation_run,
    map_establishment,
    map_execution_failure_evidence,
    map_execution_log,
    map_protocol_status_facts,
    map_service_request,
)
from apps.agent_api.app.database.models import (
    AutomationRunRecord,
    EstablishmentRecord,
    ExecutionFailureEvidence,
    ExecutionLogRecord,
    ProtocolStatusFacts,
    ServiceRequestRecord,
)
from apps.agent_api.app.database.repositories.base import BaseRepository
from apps.agent_api.app.database.repositories.contracts import RepositoryRecord


def _validate_record(
    record: Mapping[str, object],
    *,
    allowed: tuple[str, ...],
    required: frozenset[str] = frozenset(),
) -> tuple[str, ...]:
    unknown = set(record) - set(allowed)
    if unknown:
        raise ValueError(f"Unsupported fields: {', '.join(sorted(unknown))}")
    missing = required - set(record)
    if missing:
        raise ValueError(f"Missing required fields: {', '.join(sorted(missing))}")
    columns = tuple(column for column in allowed if column in record)
    if not columns:
        raise ValueError("At least one field is required")
    return columns


def _insert_statement(
    table: str,
    columns: tuple[str, ...],
    identity_column: str,
) -> sql.Composed:
    schema, table_name = table.split(".")
    return sql.SQL(
        "INSERT INTO {table} ({columns}) VALUES ({values}) RETURNING {identity}"
    ).format(
        table=sql.Identifier(schema, table_name),
        columns=sql.SQL(", ").join(map(sql.Identifier, columns)),
        values=sql.SQL(", ").join(sql.Placeholder() for _ in columns),
        identity=sql.Identifier(identity_column),
    )


def _update_statement(
    table: str,
    columns: tuple[str, ...],
    identity_column: str,
) -> sql.Composed:
    schema, table_name = table.split(".")
    assignments = [
        sql.SQL("{} = {}").format(sql.Identifier(column), sql.Placeholder())
        for column in columns
    ]
    return sql.SQL("UPDATE {table} SET {assignments} WHERE {identity} = %s").format(
        table=sql.Identifier(schema, table_name),
        assignments=sql.SQL(", ").join(assignments),
        identity=sql.Identifier(identity_column),
    )


_RUN_CREATE_COLUMNS = ("robot", "started_at", "finished_at", "status", "result_message")
_RUN_UPDATE_COLUMNS = ("finished_at", "status", "result_message")
_EMAIL_CREATE_COLUMNS = (
    "run_id",
    "received_at",
    "processed_at",
    "sender",
    "recipient",
    "subject",
    "attachment_count",
    "sender_status",
    "processing_status",
    "rejection_reason",
)
_EMAIL_UPDATE_COLUMNS = (
    "processed_at",
    "subject",
    "attachment_count",
    "sender_status",
    "processing_status",
    "rejection_reason",
)
_ATTACHMENT_CREATE_COLUMNS = (
    "email_id",
    "file_name",
    "file_type",
    "received_at",
    "validation_status",
    "validation_message",
    "establishment_count",
    "processing_status",
)
_ATTACHMENT_UPDATE_COLUMNS = (
    "file_type",
    "validation_status",
    "validation_message",
    "establishment_count",
    "processing_status",
)
_REQUEST_CREATE_COLUMNS = (
    "protocol_number",
    "email_id",
    "r1_run_id",
    "updated_at",
    "status",
    "result",
    "failure_reason",
    "completed_at",
    "return_email_at",
)
_REQUEST_UPDATE_COLUMNS = (
    "updated_at",
    "status",
    "result",
    "failure_reason",
    "completed_at",
    "return_email_at",
)
_ESTABLISHMENT_IDENTITY_COLUMNS = (
    "request_id",
    "attachment_id",
    "establishment_number",
    "generated_file_name",
)
_ESTABLISHMENT_MUTABLE_COLUMNS = (
    "processing_status",
    "upload_status",
    "upload_at",
    "download_status",
    "download_at",
    "return_email_at",
    "result_message",
    "updated_at",
)
_ESTABLISHMENT_CREATE_COLUMNS = (
    *_ESTABLISHMENT_IDENTITY_COLUMNS,
    *_ESTABLISHMENT_MUTABLE_COLUMNS,
)
_EXECUTION_LOG_COLUMNS = (
    "run_id",
    "logged_at",
    "robot",
    "event",
    "status",
    "message",
    "email_id",
    "attachment_id",
    "request_id",
    "establishment_id",
)


def _validate_limit(limit: int) -> None:
    if not 1 <= limit <= 100:
        raise ValueError("Operational query limit must be between 1 and 100")


class OperationalRepository(BaseRepository):
    """Persist and query deterministic operational facts."""

    async def create_automation_run(self, run: RepositoryRecord) -> int:
        columns = _validate_record(
            run,
            allowed=_RUN_CREATE_COLUMNS,
            required=frozenset({"robot"}),
        )
        statement = _insert_statement("ops.automation_runs", columns, "run_id")
        async with self._cursor(row_factory=dict_row) as cursor:
            await cursor.execute(statement, tuple(run[column] for column in columns))
            row = await cursor.fetchone()
        if row is None:
            raise RuntimeError("Automation run creation returned no identity")
        return int(row["run_id"])

    async def update_automation_run(
        self,
        run_id: int,
        changes: RepositoryRecord,
    ) -> None:
        columns = _validate_record(changes, allowed=_RUN_UPDATE_COLUMNS)
        statement = _update_statement("ops.automation_runs", columns, "run_id")
        parameters = tuple(changes[column] for column in columns) + (run_id,)
        async with self._cursor() as cursor:
            await cursor.execute(statement, parameters)

    async def get_automation_run(self, run_id: int) -> AutomationRunRecord | None:
        statement = """
            SELECT run_id, robot, started_at, finished_at, status,
                   result_message, created_at
            FROM ops.automation_runs
            WHERE run_id = %s
        """
        async with self._cursor(row_factory=dict_row) as cursor:
            await cursor.execute(statement, (run_id,))
            row = await cursor.fetchone()
        return map_automation_run(row) if row is not None else None

    async def create_incoming_email(self, email: RepositoryRecord) -> int:
        columns = _validate_record(
            email,
            allowed=_EMAIL_CREATE_COLUMNS,
            required=frozenset({"run_id", "received_at", "sender", "recipient"}),
        )
        statement = _insert_statement("ops.incoming_emails", columns, "email_id")
        async with self._cursor(row_factory=dict_row) as cursor:
            await cursor.execute(statement, tuple(email[column] for column in columns))
            row = await cursor.fetchone()
        if row is None:
            raise RuntimeError("Incoming email creation returned no identity")
        return int(row["email_id"])

    async def update_incoming_email(
        self,
        email_id: int,
        changes: RepositoryRecord,
    ) -> None:
        columns = _validate_record(changes, allowed=_EMAIL_UPDATE_COLUMNS)
        statement = _update_statement("ops.incoming_emails", columns, "email_id")
        parameters = tuple(changes[column] for column in columns) + (email_id,)
        async with self._cursor() as cursor:
            await cursor.execute(statement, parameters)

    async def create_email_attachment(self, attachment: RepositoryRecord) -> int:
        columns = _validate_record(
            attachment,
            allowed=_ATTACHMENT_CREATE_COLUMNS,
            required=frozenset({"email_id", "file_name", "received_at"}),
        )
        statement = _insert_statement(
            "ops.email_attachments", columns, "attachment_id"
        )
        async with self._cursor(row_factory=dict_row) as cursor:
            await cursor.execute(statement, tuple(attachment[column] for column in columns))
            row = await cursor.fetchone()
        if row is None:
            raise RuntimeError("Email attachment creation returned no identity")
        return int(row["attachment_id"])

    async def update_email_attachment(
        self,
        attachment_id: int,
        changes: RepositoryRecord,
    ) -> None:
        columns = _validate_record(changes, allowed=_ATTACHMENT_UPDATE_COLUMNS)
        statement = _update_statement(
            "ops.email_attachments", columns, "attachment_id"
        )
        parameters = tuple(changes[column] for column in columns) + (attachment_id,)
        async with self._cursor() as cursor:
            await cursor.execute(statement, parameters)

    async def create_service_request(self, request: RepositoryRecord) -> int:
        columns = _validate_record(
            request,
            allowed=_REQUEST_CREATE_COLUMNS,
            required=frozenset(
                {"protocol_number", "email_id", "r1_run_id", "updated_at"}
            ),
        )
        statement = _insert_statement("ops.service_requests", columns, "request_id")
        async with self._cursor(row_factory=dict_row) as cursor:
            await cursor.execute(statement, tuple(request[column] for column in columns))
            row = await cursor.fetchone()
        if row is None:
            raise RuntimeError("Service request creation returned no identity")
        return int(row["request_id"])

    async def update_service_request(
        self,
        request_id: int,
        changes: RepositoryRecord,
    ) -> None:
        columns = _validate_record(changes, allowed=_REQUEST_UPDATE_COLUMNS)
        statement = _update_statement("ops.service_requests", columns, "request_id")
        parameters = tuple(changes[column] for column in columns) + (request_id,)
        async with self._cursor() as cursor:
            await cursor.execute(statement, parameters)

    async def get_service_request_by_protocol(
        self,
        protocol_number: str,
    ) -> ServiceRequestRecord | None:
        statement = """
            SELECT request_id, protocol_number, email_id, r1_run_id, created_at,
                   updated_at, status, result, failure_reason, completed_at,
                   return_email_at
            FROM ops.service_requests
            WHERE protocol_number = %s
        """
        async with self._cursor(row_factory=dict_row) as cursor:
            await cursor.execute(statement, (protocol_number,))
            row = await cursor.fetchone()
        return map_service_request(row) if row is not None else None

    async def list_recent_service_requests(self, limit: int) -> Sequence[ServiceRequestRecord]:
        """Order protocols by request creation time, with stable identity tie-breaking."""

        if not 1 <= limit <= 5:
            raise ValueError("Recent service request limit must be between 1 and 5")
        statement = """
            SELECT request_id, protocol_number, email_id, r1_run_id, created_at,
                   updated_at, status, result, failure_reason, completed_at,
                   return_email_at
            FROM ops.service_requests
            ORDER BY created_at DESC, request_id DESC
            LIMIT %s
        """
        async with self._cursor(row_factory=dict_row) as cursor:
            await cursor.execute(statement, (limit,))
            rows = await cursor.fetchall()
        return tuple(map_service_request(row) for row in rows)

    async def upsert_establishment(self, establishment: RepositoryRecord) -> int:
        columns = _validate_record(
            establishment,
            allowed=_ESTABLISHMENT_CREATE_COLUMNS,
            required=frozenset({*_ESTABLISHMENT_IDENTITY_COLUMNS, "updated_at"}),
        )
        identity_values = tuple(
            establishment[column] for column in _ESTABLISHMENT_IDENTITY_COLUMNS
        )
        lookup = """
            SELECT establishment_id, request_id, attachment_id,
                   establishment_number, generated_file_name
            FROM ops.establishments
            WHERE (
                request_id = %s AND attachment_id = %s AND establishment_number = %s
            ) OR (request_id = %s AND generated_file_name = %s)
            ORDER BY establishment_id ASC
            LIMIT 2
        """
        lookup_parameters = (
            establishment["request_id"],
            establishment["attachment_id"],
            establishment["establishment_number"],
            establishment["request_id"],
            establishment["generated_file_name"],
        )
        async with self._cursor(row_factory=dict_row) as cursor:
            await cursor.execute(lookup, lookup_parameters)
            matches = await cursor.fetchall()

        if len(matches) > 1:
            raise ValueError("Establishment identities resolve to different rows")
        if matches:
            match = matches[0]
            if tuple(match[column] for column in _ESTABLISHMENT_IDENTITY_COLUMNS) != identity_values:
                raise ValueError("Establishment identity conflicts with an existing row")
            changes = {
                column: establishment[column]
                for column in _ESTABLISHMENT_MUTABLE_COLUMNS
                if column in establishment
            }
            await self.update_establishment(int(match["establishment_id"]), changes)
            return int(match["establishment_id"])

        statement = _insert_statement(
            "ops.establishments", columns, "establishment_id"
        )
        async with self._cursor(row_factory=dict_row) as cursor:
            await cursor.execute(
                statement,
                tuple(establishment[column] for column in columns),
            )
            row = await cursor.fetchone()
        if row is None:
            raise RuntimeError("Establishment creation returned no identity")
        return int(row["establishment_id"])

    async def update_establishment(
        self,
        establishment_id: int,
        changes: RepositoryRecord,
    ) -> None:
        columns = _validate_record(changes, allowed=_ESTABLISHMENT_MUTABLE_COLUMNS)
        statement = _update_statement(
            "ops.establishments", columns, "establishment_id"
        )
        parameters = tuple(changes[column] for column in columns) + (establishment_id,)
        async with self._cursor() as cursor:
            await cursor.execute(statement, parameters)

    async def list_establishments_for_request(
        self,
        request_id: int,
    ) -> Sequence[EstablishmentRecord]:
        statement = """
            SELECT establishment_id, request_id, attachment_id,
                   establishment_number, generated_file_name, processing_status,
                   upload_status, upload_at, download_status, download_at,
                   return_email_at, result_message, updated_at
            FROM ops.establishments
            WHERE request_id = %s
            ORDER BY establishment_id ASC
        """
        async with self._cursor(row_factory=dict_row) as cursor:
            await cursor.execute(statement, (request_id,))
            rows = await cursor.fetchall()
        return tuple(map_establishment(row) for row in rows)

    async def append_execution_log(self, event: RepositoryRecord) -> int:
        columns = _validate_record(
            event,
            allowed=_EXECUTION_LOG_COLUMNS,
            required=frozenset(
                {"run_id", "logged_at", "robot", "event", "status", "message"}
            ),
        )
        statement = _insert_statement("ops.execution_log", columns, "log_id")
        async with self._cursor(row_factory=dict_row) as cursor:
            await cursor.execute(statement, tuple(event[column] for column in columns))
            row = await cursor.fetchone()
        if row is None:
            raise RuntimeError("Execution log append returned no identity")
        return int(row["log_id"])

    async def list_execution_timeline_for_run(
        self,
        run_id: int,
        limit: int,
    ) -> Sequence[ExecutionLogRecord]:
        _validate_limit(limit)
        statement = """
            SELECT log_id, run_id, logged_at, robot, event, status, message,
                   email_id, attachment_id, request_id, establishment_id, created_at
            FROM ops.execution_log
            WHERE run_id = %s
            ORDER BY logged_at DESC, log_id DESC
            LIMIT %s
        """
        async with self._cursor(row_factory=dict_row) as cursor:
            await cursor.execute(statement, (run_id, limit))
            rows = await cursor.fetchall()
        return tuple(map_execution_log(row) for row in rows)

    async def list_execution_timeline_for_request(
        self,
        request_id: int,
        limit: int,
    ) -> Sequence[ExecutionLogRecord]:
        _validate_limit(limit)
        statement = """
            SELECT log_id, run_id, logged_at, robot, event, status, message,
                   email_id, attachment_id, request_id, establishment_id, created_at
            FROM ops.execution_log
            WHERE request_id = %s
            ORDER BY logged_at DESC, log_id DESC
            LIMIT %s
        """
        async with self._cursor(row_factory=dict_row) as cursor:
            await cursor.execute(statement, (request_id, limit))
            rows = await cursor.fetchall()
        return tuple(map_execution_log(row) for row in rows)

    async def get_protocol_status_facts(
        self,
        protocol_number: str,
    ) -> Sequence[ProtocolStatusFacts]:
        statement = """
            SELECT sr.request_id, sr.protocol_number, sr.email_id, sr.r1_run_id,
                   sr.created_at, sr.updated_at, sr.status, sr.result,
                   sr.failure_reason, sr.completed_at, sr.return_email_at,
                   COALESCE(
                       (
                           SELECT jsonb_agg(to_jsonb(e) ORDER BY e.establishment_id ASC)
                           FROM ops.establishments AS e
                           WHERE e.request_id = sr.request_id
                       ),
                       '[]'::jsonb
                   ) AS establishments,
                   COALESCE(
                       (
                           SELECT jsonb_agg(
                               to_jsonb(l) ORDER BY l.logged_at ASC, l.log_id ASC
                           )
                           FROM ops.execution_log AS l
                           WHERE l.request_id = sr.request_id
                       ),
                       '[]'::jsonb
                   ) AS execution_timeline
            FROM ops.service_requests AS sr
            WHERE sr.protocol_number = %s
        """
        async with self._cursor(row_factory=dict_row) as cursor:
            await cursor.execute(statement, (protocol_number,))
            rows = await cursor.fetchall()
        return tuple(map_protocol_status_facts(row) for row in rows)

    async def get_execution_failure_facts(
        self,
        protocol_number: str,
        run_id: int | None = None,
    ) -> Sequence[ExecutionFailureEvidence]:
        run_filter = "" if run_id is None else "AND l.run_id = %s"
        statement = sql.SQL(
            """
            SELECT sr.request_id, sr.protocol_number, sr.status AS request_status,
                   sr.failure_reason, ar.run_id, ar.robot,
                   ar.started_at, ar.finished_at, ar.status AS run_status,
                   ar.result_message AS run_result_message,
                   l.log_id, l.logged_at, l.event, l.status AS event_status,
                   l.message AS event_message, l.email_id, l.attachment_id,
                   l.establishment_id,
                   (
                       SELECT to_jsonb(previous_success)
                       FROM ops.execution_log AS previous_success
                       WHERE previous_success.request_id = sr.request_id
                         AND previous_success.status = 'SUCCESS'
                         AND (
                             previous_success.logged_at < l.logged_at
                             OR (
                                 previous_success.logged_at = l.logged_at
                                 AND previous_success.log_id < l.log_id
                             )
                         )
                       ORDER BY previous_success.logged_at DESC,
                                previous_success.log_id DESC
                       LIMIT 1
                   ) AS last_successful_evidence
            FROM ops.service_requests AS sr
            JOIN ops.execution_log AS l ON l.request_id = sr.request_id
            JOIN ops.automation_runs AS ar ON ar.run_id = l.run_id
            WHERE sr.protocol_number = %s
              AND l.status IN ('ERROR', 'EXCEPTION')
              {run_filter}
            ORDER BY l.logged_at ASC, l.log_id ASC
            """
        ).format(run_filter=sql.SQL(run_filter))
        parameters = (protocol_number,) if run_id is None else (protocol_number, run_id)
        async with self._cursor(row_factory=dict_row) as cursor:
            await cursor.execute(statement, parameters)
            rows = await cursor.fetchall()
        return tuple(map_execution_failure_evidence(row) for row in rows)
