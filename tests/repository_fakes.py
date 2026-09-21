"""Async Psycopg test doubles that never open a database connection."""

from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock


@dataclass(frozen=True)
class ExecutedStatement:
    sql: str
    parameters: object
    many: bool = False


def render_sql(statement: object) -> str:
    if hasattr(statement, "as_string"):
        return statement.as_string(None)
    return str(statement)


class FakeCursor:
    def __init__(self, connection: "FakeConnection") -> None:
        self._connection = connection
        self._result: object = None

    async def __aenter__(self) -> "FakeCursor":
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None

    async def execute(self, statement: object, parameters: object = None) -> None:
        self._connection.statements.append(
            ExecutedStatement(render_sql(statement), parameters)
        )
        self._result = self._connection.results.pop(0) if self._connection.results else None

    async def executemany(self, statement: object, parameters: object) -> None:
        self._connection.statements.append(
            ExecutedStatement(render_sql(statement), parameters, many=True)
        )

    async def fetchone(self) -> Any:
        if isinstance(self._result, list):
            return self._result[0] if self._result else None
        return self._result

    async def fetchall(self) -> list[Any]:
        if self._result is None:
            return []
        if isinstance(self._result, list):
            return self._result
        return [self._result]


class FakeConnection:
    def __init__(self, *results: object) -> None:
        self.results = list(results)
        self.statements: list[ExecutedStatement] = []
        self.cursor_calls = 0
        self.commit = AsyncMock()
        self.rollback = AsyncMock()
        self.close = AsyncMock()

    def cursor(self, **kwargs: object) -> FakeCursor:
        self.cursor_calls += 1
        return FakeCursor(self)


def normalized_sql(statement: ExecutedStatement) -> str:
    return " ".join(statement.sql.split())
