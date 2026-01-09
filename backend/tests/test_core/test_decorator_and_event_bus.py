"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_decorator_and_event_bus.py
@DateTime: 2026-01-05 00:00:00
@Docs: core.decorator 与 core.event_bus 覆盖率补充测试.
"""

import asyncio

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.core.decorator import transactional, with_db_retry
from app.core.event_bus import Event, EventBus


class DummySession:
    def __init__(self) -> None:
        self.commit_count = 0
        self.rollback_count = 0

    async def commit(self) -> None:
        self.commit_count += 1

    async def rollback(self) -> None:
        self.rollback_count += 1


@pytest.mark.asyncio
async def test_transactional_raises_when_no_db_session() -> None:
    @transactional()
    async def fn(x: int) -> int:
        return x

    with pytest.raises(RuntimeError):
        await fn(1)


@pytest.mark.asyncio
async def test_transactional_commit_and_post_commit_tasks(monkeypatch: pytest.MonkeyPatch) -> None:
    session = DummySession()

    class Svc:
        def __init__(self) -> None:
            self._post_commit_tasks = []

    svc = Svc()

    called = {"ok": 0, "bad": 0}

    async def ok_task() -> None:
        called["ok"] += 1

    async def bad_task() -> None:
        called["bad"] += 1
        raise RuntimeError("boom")

    svc._post_commit_tasks = [ok_task, bad_task]

    @transactional()
    async def fn(self: Svc, *, db: DummySession) -> str:
        return "done"

    result = await fn(svc, db=session)
    assert result == "done"
    assert session.commit_count == 1
    assert session.rollback_count == 0
    assert called["ok"] == 1
    assert called["bad"] == 1
    assert svc._post_commit_tasks == []


@pytest.mark.asyncio
async def test_transactional_rollback_on_exception() -> None:
    session = DummySession()

    @transactional()
    async def fn(*, db: DummySession) -> None:
        raise ValueError("x")

    with pytest.raises(ValueError):
        await fn(db=session)

    assert session.commit_count == 0
    assert session.rollback_count == 1


@pytest.mark.asyncio
async def test_with_db_retry_retries_then_success(monkeypatch: pytest.MonkeyPatch) -> None:
    async def no_sleep(_: float) -> None:
        return None

    monkeypatch.setattr(asyncio, "sleep", no_sleep)

    called = {"count": 0}

    @with_db_retry(max_retries=2, initial_delay=0)
    async def fn() -> str:
        called["count"] += 1
        if called["count"] <= 2:
            raise SQLAlchemyError("fail")
        return "ok"

    assert await fn() == "ok"
    assert called["count"] == 3


@pytest.mark.asyncio
async def test_with_db_retry_exceeds_max_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    async def no_sleep(_: float) -> None:
        return None

    monkeypatch.setattr(asyncio, "sleep", no_sleep)

    @with_db_retry(max_retries=1, initial_delay=0)
    async def fn() -> None:
        raise SQLAlchemyError("fail")

    with pytest.raises(SQLAlchemyError):
        await fn()


@pytest.mark.asyncio
async def test_event_bus_publish_no_handlers_returns() -> None:
    bus = EventBus()

    class MyEvent(Event):
        pass

    await bus.publish(MyEvent())


@pytest.mark.asyncio
async def test_event_bus_publish_handlers_and_safe_call() -> None:
    bus = EventBus()

    class MyEvent(Event):
        pass

    called = {"ok": 0, "bad": 0}

    async def ok_handler(event: Event) -> None:
        called["ok"] += 1

    async def bad_handler(event: Event) -> None:
        called["bad"] += 1
        raise RuntimeError("boom")

    bus.subscribe(MyEvent, ok_handler)
    bus.subscribe(MyEvent, bad_handler)

    await bus.publish(MyEvent())
    await bus.drain(timeout=1.0)

    assert called["ok"] == 1
    assert called["bad"] == 1


@pytest.mark.asyncio
async def test_event_bus_drain_timeout() -> None:
    bus = EventBus()

    class MyEvent(Event):
        pass

    async def slow_handler(event: Event) -> None:
        await asyncio.sleep(0.05)

    bus.subscribe(MyEvent, slow_handler)

    await bus.publish(MyEvent())
    # 触发 timeout 分支（不要求抛出）
    await bus.drain(timeout=0.0)
    # 再等一次，避免遗留 pending task
    await bus.drain(timeout=1.0)
