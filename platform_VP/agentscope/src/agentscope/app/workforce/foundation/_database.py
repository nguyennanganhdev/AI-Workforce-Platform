# -*- coding: utf-8 -*-
"""Async SQL database and explicit-commit Unit of Work for Workforce."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
import inspect
from typing import Any, Self


class SqlAlchemyUnitOfWork(AbstractAsyncContextManager):
    """One SQLAlchemy session with callbacks that run only after commit.

    Leaving the context without an explicit commit always rolls the session
    back.  This matches the shared UnitOfWork contract and prevents a service
    from accidentally committing an injected transaction.
    """

    def __init__(self, session_factory: Callable[[], Any]) -> None:
        self._session_factory = session_factory
        self._session: Any | None = None
        self._callbacks: list[Callable[[], Any]] = []
        self._committed = False
        self._finished = False

    async def __aenter__(self) -> "SqlAlchemyUnitOfWork":
        if self._session is not None:
            raise RuntimeError("unit of work cannot be entered twice")
        self._session = self._session_factory()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: Any,
    ) -> bool:
        del exc_value, traceback
        try:
            if exc_type is not None or not self._committed:
                await self.rollback()
        finally:
            if self._session is not None:
                await self._session.close()
            self._finished = True
        return False

    @property
    def session(self) -> Any:
        if self._session is None:
            raise RuntimeError("unit of work has not been entered")
        return self._session

    @property
    def bind(self) -> Any:
        """Compatibility surface for Core repositories using AsyncSession."""
        bind = self.session.get_bind()
        return bind

    async def execute(self, statement: Any, params: Any = None) -> Any:
        if params is None:
            return await self.session.execute(statement)
        return await self.session.execute(statement, params)

    async def scalar(self, statement: Any, params: Any = None) -> Any:
        if params is None:
            return await self.session.scalar(statement)
        return await self.session.scalar(statement, params)

    def begin_nested(self) -> Any:
        return self.session.begin_nested()

    async def commit(self) -> None:
        if self._finished or self._committed:
            raise RuntimeError("unit of work has already finished")
        await self.session.commit()
        self._committed = True
        callbacks, self._callbacks = self._callbacks, []
        for callback in callbacks:
            result = callback()
            if inspect.isawaitable(result):
                await result

    async def rollback(self) -> None:
        if self._session is not None and not self._committed:
            await self._session.rollback()
        self._callbacks.clear()

    def add_after_commit(self, callback: Callable[[], Any]) -> None:
        if self._committed or self._finished:
            raise RuntimeError("cannot register callback after completion")
        self._callbacks.append(callback)


class SqlAlchemyUnitOfWorkFactory:
    """Callable shared by repositories that need the canonical UOW."""

    def __init__(self, session_factory: Callable[[], Any]) -> None:
        self.session_factory = session_factory

    def __call__(self) -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(self.session_factory)


class WorkforceDatabase(AbstractAsyncContextManager):
    """Own the Workforce SQL pool without importing SQL in core SDK paths."""

    def __init__(
        self,
        database_url: str,
        *,
        engine_kwargs: dict[str, Any] | None = None,
    ) -> None:
        if not database_url:
            raise ValueError("database_url is required")
        self._database_url = database_url
        self._engine_kwargs = dict(engine_kwargs or {})
        self._engine: Any | None = None
        self._session_factory: Any | None = None

    async def __aenter__(self) -> Self:
        from sqlalchemy.ext.asyncio import (
            async_sessionmaker,
            create_async_engine,
        )

        if self._engine is not None:
            raise RuntimeError("WorkforceDatabase is already open")
        self._engine = create_async_engine(
            self._database_url,
            **self._engine_kwargs,
        )
        self._session_factory = async_sessionmaker(
            self._engine,
            expire_on_commit=False,
        )
        return self

    async def __aexit__(self, *args: Any) -> None:
        del args
        if self._engine is not None:
            await self._engine.dispose()
        self._session_factory = None
        self._engine = None

    @property
    def engine(self) -> Any:
        if self._engine is None:
            raise RuntimeError(
                "WorkforceDatabase has not entered its lifespan",
            )
        return self._engine

    @property
    def session_factory(self) -> Any:
        if self._session_factory is None:
            raise RuntimeError(
                "WorkforceDatabase has not entered its lifespan",
            )
        return self._session_factory

    @property
    def uows(self) -> SqlAlchemyUnitOfWorkFactory:
        return SqlAlchemyUnitOfWorkFactory(self.session_factory)


__all__ = [
    "SqlAlchemyUnitOfWork",
    "SqlAlchemyUnitOfWorkFactory",
    "WorkforceDatabase",
]
