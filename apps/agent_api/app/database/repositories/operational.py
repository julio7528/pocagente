"""Connection-bound persistence adapter for the approved OPS schema."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from psycopg import sql
from psycopg.rows import dict_row

from apps.agent_api.app.database.mapping import (
    map_automation_run,
    map_email_attachment,
    map_establishment,
    map_execution_failure_evidence,
    map_execution_log,
    map_incoming_email,
    map_protocol_status_facts,
    map_recent_executed_protocol,
    map_service_request,
)
from apps.agent_api.app.database.models import (
    AutomationRunRecord,
    EmailAttachmentRecord,
    EstablishmentRecord,
    ExecutionFailureEvidence,
    ExecutionLogRecord,
    IncomingEmailRecord,
    ProtocolStatusFacts,
    RecentExecutedProtocolRecord,
    ServiceRequestRecord,
    OperationalAnalyticsQuery,
    OperationalAnalyticsResult,
    OperationalAnalyticsRow,
    OperationalAnalyticsGroup,
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

    async def list_automation_runs_for_request(
        self, request_id: int
    ) -> Sequence[AutomationRunRecord]:
        """Correlate the creating R1 run and later runs linked by request logs."""
        statement = """
            WITH correlated_runs AS (
                SELECT r1_run_id AS run_id FROM ops.service_requests WHERE request_id = %s
                UNION SELECT run_id FROM ops.execution_log WHERE request_id = %s
                UNION SELECT el.run_id FROM ops.execution_log AS el
                      JOIN ops.establishments AS e ON e.establishment_id = el.establishment_id
                      WHERE e.request_id = %s
                UNION SELECT el.run_id FROM ops.execution_log AS el
                      JOIN ops.service_requests AS sr ON sr.email_id = el.email_id
                      WHERE sr.request_id = %s
                UNION SELECT el.run_id FROM ops.execution_log AS el
                      JOIN ops.email_attachments AS ea ON ea.attachment_id = el.attachment_id
                      JOIN ops.service_requests AS sr ON sr.email_id = ea.email_id
                      WHERE sr.request_id = %s
            )
            SELECT ar.run_id, ar.robot, ar.started_at, ar.finished_at,
                   ar.status, ar.result_message, ar.created_at
            FROM correlated_runs AS correlated
            JOIN ops.automation_runs AS ar ON ar.run_id = correlated.run_id
            ORDER BY ar.started_at ASC, ar.run_id ASC
        """
        async with self._cursor(row_factory=dict_row) as cursor:
            await cursor.execute(statement, (request_id,) * 5)
            rows = await cursor.fetchall()
        return tuple(map_automation_run(row) for row in rows)

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

    async def get_incoming_email(self, email_id: int) -> IncomingEmailRecord | None:
        statement = """
            SELECT email_id, run_id, received_at, processed_at, sender, recipient,
                   subject, attachment_count, sender_status, processing_status,
                   rejection_reason, created_at
            FROM ops.incoming_emails
            WHERE email_id = %s
        """
        async with self._cursor(row_factory=dict_row) as cursor:
            await cursor.execute(statement, (email_id,))
            row = await cursor.fetchone()
        return map_incoming_email(row) if row is not None else None

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

    async def list_email_attachments(self, email_id: int) -> Sequence[EmailAttachmentRecord]:
        statement = """
            SELECT attachment_id, email_id, file_name, file_type, received_at,
                   validation_status, validation_message, establishment_count,
                   processing_status, created_at
            FROM ops.email_attachments
            WHERE email_id = %s
            ORDER BY attachment_id ASC
        """
        async with self._cursor(row_factory=dict_row) as cursor:
            await cursor.execute(statement, (email_id,))
            rows = await cursor.fetchall()
        return tuple(map_email_attachment(row) for row in rows)

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

    async def list_recent_protocols_by_execution(self, limit: int) -> Sequence[RecentExecutedProtocolRecord]:
        """Order requests by the latest actual R1/R2 run start timestamp."""
        if not 1 <= limit <= 5:
            raise ValueError("Recent service request limit must be between 1 and 5")
        statement = """
            SELECT sr.request_id, sr.protocol_number, sr.email_id, sr.r1_run_id,
                   sr.created_at, sr.updated_at, sr.status, sr.result,
                   sr.failure_reason, sr.completed_at, sr.return_email_at,
                   execution_recency.last_execution_at
            FROM ops.service_requests AS sr
            JOIN (
                SELECT correlated.request_id, MAX(ar.started_at) AS last_execution_at
                FROM (
                    SELECT request_id, r1_run_id AS run_id FROM ops.service_requests
                    UNION
                    SELECT request_id, run_id FROM ops.execution_log WHERE request_id IS NOT NULL
                    UNION
                    SELECT e.request_id, el.run_id FROM ops.execution_log AS el
                    JOIN ops.establishments AS e ON e.establishment_id = el.establishment_id
                    UNION
                    SELECT sr.request_id, el.run_id FROM ops.execution_log AS el
                    JOIN ops.service_requests AS sr ON sr.email_id = el.email_id
                    UNION
                    SELECT sr.request_id, el.run_id FROM ops.execution_log AS el
                    JOIN ops.email_attachments AS ea ON ea.attachment_id = el.attachment_id
                    JOIN ops.service_requests AS sr ON sr.email_id = ea.email_id
                ) AS correlated
                JOIN ops.automation_runs AS ar ON ar.run_id = correlated.run_id
                WHERE correlated.request_id IS NOT NULL
                GROUP BY correlated.request_id
            ) AS execution_recency ON execution_recency.request_id = sr.request_id
            ORDER BY execution_recency.last_execution_at DESC, sr.request_id DESC
            LIMIT %s
        """
        async with self._cursor(row_factory=dict_row) as cursor:
            await cursor.execute(statement, (limit,))
            rows = await cursor.fetchall()
        return tuple(map_recent_executed_protocol(row) for row in rows)

    async def query_operational_analytics(
        self, query: OperationalAnalyticsQuery
    ) -> OperationalAnalyticsResult:
        """Run one bounded grain-specific query; all selectable fragments are closed allowlists."""
        if query.grain == "EXECUTION":
            basis = {
                "EXECUTION_STARTED": "started_at",
                "EXECUTION_FINISHED": "finished_at",
            }[query.time_basis]
            base = f"""SELECT run_id, NULL::text AS protocol_number, robot, status,
                CASE WHEN status = 'SUCCESS' THEN 'SUCCESS'
                     WHEN status = 'ERROR' THEN 'FAILURE' ELSE 'OTHER' END AS outcome,
                {basis} AS occurred_at, finished_at, NULL::text AS event
                FROM ops.automation_runs"""
        elif query.grain == "EVENT":
            base = """SELECT NULL::bigint AS run_id, NULL::text AS protocol_number, robot, status,
                CASE WHEN status = 'SUCCESS' THEN 'SUCCESS'
                     WHEN status IN ('ERROR', 'EXCEPTION') THEN 'FAILURE' ELSE 'OTHER' END AS outcome,
                logged_at AS occurred_at, NULL::timestamptz AS finished_at, event
                FROM ops.execution_log"""
        else:
            basis = {
                "PROTOCOL_CREATED": "COALESCE(domain_created.created_at, sr.created_at)",
                "PROTOCOL_OUTCOME_AT": "CASE WHEN sr.status = 'COMPLETED' THEN sr.completed_at WHEN sr.status = 'FAILED' THEN failures.failure_at ELSE COALESCE(domain_created.created_at, sr.created_at) END",
                "FIRST_EXECUTION": "run_times.first_execution_at",
                "LAST_EXECUTION": "run_times.last_execution_at",
            }[query.time_basis]
            base = f"""WITH correlated_runs AS (
                    SELECT request_id, r1_run_id AS run_id FROM ops.service_requests
                    UNION SELECT request_id, run_id FROM ops.execution_log WHERE request_id IS NOT NULL
                    UNION SELECT e.request_id, el.run_id FROM ops.execution_log AS el
                          JOIN ops.establishments AS e ON e.establishment_id = el.establishment_id
                    UNION SELECT sr0.request_id, el.run_id FROM ops.execution_log AS el
                          JOIN ops.service_requests AS sr0 ON sr0.email_id = el.email_id
                    UNION SELECT sr0.request_id, el.run_id FROM ops.execution_log AS el
                          JOIN ops.email_attachments AS ea ON ea.attachment_id = el.attachment_id
                          JOIN ops.service_requests AS sr0 ON sr0.email_id = ea.email_id
                ), run_times AS (
                    SELECT cr.request_id, MIN(ar.started_at) AS first_execution_at,
                           MAX(ar.started_at) AS last_execution_at
                    FROM correlated_runs AS cr
                    JOIN ops.automation_runs AS ar ON ar.run_id = cr.run_id
                    WHERE cr.request_id IS NOT NULL GROUP BY cr.request_id
                ), domain_created AS (
                    SELECT request_id, MIN(logged_at) AS created_at
                    FROM ops.execution_log
                    WHERE event = 'PROTOCOLO_CRIADO' AND request_id IS NOT NULL
                    GROUP BY request_id
                ), linked_events AS (
                    SELECT request_id, logged_at, status FROM ops.execution_log WHERE request_id IS NOT NULL
                    UNION SELECT e.request_id, el.logged_at, el.status FROM ops.execution_log AS el
                          JOIN ops.establishments AS e ON e.establishment_id = el.establishment_id
                    UNION SELECT sr0.request_id, el.logged_at, el.status FROM ops.execution_log AS el
                          JOIN ops.service_requests AS sr0 ON sr0.email_id = el.email_id
                    UNION SELECT sr0.request_id, el.logged_at, el.status FROM ops.execution_log AS el
                          JOIN ops.email_attachments AS ea ON ea.attachment_id = el.attachment_id
                          JOIN ops.service_requests AS sr0 ON sr0.email_id = ea.email_id
                ), failures AS (
                    SELECT request_id, MAX(logged_at) AS failure_at FROM linked_events
                    WHERE status IN ('ERROR', 'EXCEPTION') GROUP BY request_id
                )
                SELECT NULL::bigint AS run_id, sr.protocol_number, NULL::text AS robot,
                    sr.status,
                    CASE WHEN sr.status = 'COMPLETED' THEN 'SUCCESS'
                         WHEN sr.status = 'FAILED' THEN 'FAILURE' ELSE 'OTHER' END AS outcome,
                    {basis} AS occurred_at, sr.completed_at AS finished_at, NULL::text AS event
                FROM ops.service_requests AS sr
                LEFT JOIN run_times ON run_times.request_id = sr.request_id
                LEFT JOIN domain_created ON domain_created.request_id = sr.request_id
                LEFT JOIN failures ON failures.request_id = sr.request_id"""

        predicates: list[str] = ["occurred_at IS NOT NULL"] if query.time_basis in {"FIRST_EXECUTION", "LAST_EXECUTION", "EXECUTION_FINISHED", "PROTOCOL_OUTCOME_AT"} else []
        parameters: list[object] = []
        if query.start_at is not None:
            predicates.append("occurred_at >= %s")
            parameters.append(query.start_at)
        if query.end_at is not None:
            predicates.append("occurred_at < %s")
            parameters.append(query.end_at)
        if query.outcome_filter is not None:
            predicates.append("outcome = %s")
            parameters.append(query.outcome_filter)
        if query.status_filter is not None:
            predicates.append("status = %s")
            parameters.append(query.status_filter)
        if query.robot_filter is not None:
            predicates.append("robot = %s")
            parameters.append(query.robot_filter)
        where = " WHERE " + " AND ".join(predicates) if predicates else ""
        cte = f"WITH base AS ({base}), filtered AS (SELECT * FROM base{where}) "

        if query.metric in {"LIST", "FIRST", "LAST"}:
            direction = "ASC" if query.ordering == "EARLIEST" or query.metric == "FIRST" else "DESC"
            sql_text = cte + f"""SELECT protocol_number, run_id, robot, status, outcome,
                occurred_at, finished_at, event, COUNT(*) OVER()::bigint AS matched_count FROM filtered
                ORDER BY occurred_at {direction}, COALESCE(run_id, 0) {direction}, protocol_number {direction}
                LIMIT %s"""
            async with self._cursor(row_factory=dict_row) as cursor:
                await cursor.execute(sql_text, (*parameters, query.limit))
                raw_rows = await cursor.fetchall()
            matched_count = int(raw_rows[0]["matched_count"]) if raw_rows else 0
            rows = tuple(
                OperationalAnalyticsRow(**{key: value for key, value in row.items() if key != "matched_count"})
                for row in raw_rows
            )
            return OperationalAnalyticsResult(exists=matched_count > 0, total_count=matched_count, rows=rows)

        group_expressions = {
            "OUTCOME": ("outcome", "outcome"),
            "ROBOT": ("robot", "robot"),
        }
        selected = [group_expressions[group][0] for group in query.group_by]
        if selected:
            selection = ", ".join((*selected, "COUNT(*)::bigint AS count"))
            grouping = " GROUP BY " + ", ".join(selected)
            ordering = " ORDER BY " + ", ".join(f"{column} ASC" for column in selected)
            sql_text = cte + f"SELECT {selection} FROM filtered{grouping}{ordering}"
            async with self._cursor(row_factory=dict_row) as cursor:
                await cursor.execute(sql_text, tuple(parameters))
                raw_groups = await cursor.fetchall()
            groups = tuple(OperationalAnalyticsGroup(**row) for row in raw_groups)
            total = sum(group.count for group in groups)
        else:
            sql_text = cte + "SELECT COUNT(*)::bigint AS count FROM filtered"
            async with self._cursor(row_factory=dict_row) as cursor:
                await cursor.execute(sql_text, tuple(parameters))
                row = await cursor.fetchone()
            total = int(row["count"]) if row else 0
            groups = (OperationalAnalyticsGroup(count=total),)
        return OperationalAnalyticsResult(exists=total > 0, total_count=total, groups=groups)

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
            FROM ops.execution_log AS el
            WHERE el.request_id = %s
               OR el.establishment_id IN (
                    SELECT e.establishment_id FROM ops.establishments AS e WHERE e.request_id = %s
               )
               OR el.email_id = (
                    SELECT sr.email_id FROM ops.service_requests AS sr WHERE sr.request_id = %s
               )
               OR el.attachment_id IN (
                    SELECT e.attachment_id FROM ops.establishments AS e WHERE e.request_id = %s
               )
            ORDER BY el.logged_at DESC, el.log_id DESC
            LIMIT %s
        """
        async with self._cursor(row_factory=dict_row) as cursor:
            await cursor.execute(statement, (request_id, request_id, request_id, request_id, limit))
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
                       WHERE (
                             previous_success.request_id = sr.request_id
                             OR previous_success.establishment_id IN (
                                 SELECT e.establishment_id FROM ops.establishments AS e WHERE e.request_id = sr.request_id
                             )
                             OR previous_success.email_id = sr.email_id
                             OR previous_success.attachment_id IN (
                                 SELECT e.attachment_id FROM ops.establishments AS e WHERE e.request_id = sr.request_id
                             )
                         )
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
            JOIN ops.execution_log AS l ON (
                l.request_id = sr.request_id
                OR l.establishment_id IN (
                    SELECT e.establishment_id FROM ops.establishments AS e WHERE e.request_id = sr.request_id
                )
                OR l.email_id = sr.email_id
                OR l.attachment_id IN (
                    SELECT e.attachment_id FROM ops.establishments AS e WHERE e.request_id = sr.request_id
                )
            )
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
