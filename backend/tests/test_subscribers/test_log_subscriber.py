"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_log_subscriber.py
@DateTime: 2026-01-05 00:00:00
@Docs: 日志订阅者单元测试.
"""

import pytest

import app.subscribers.log_subscriber as subscriber
from app.core.event_bus import Event, OperationLogEvent


class DummyLogger:
    def __init__(self) -> None:
        self.debug_calls: list[str] = []
        self.error_calls: list[str] = []

    def debug(self, msg: str) -> None:
        self.debug_calls.append(msg)

    def error(self, msg: str) -> None:
        self.error_calls.append(msg)


class FakeSession:
    def __init__(self, *, fail_commit: bool = False) -> None:
        self.added: list[object] = []
        self.committed = 0
        self.fail_commit = fail_commit

    def add(self, obj: object) -> None:
        self.added.append(obj)

    async def commit(self) -> None:
        self.committed += 1
        if self.fail_commit:
            raise RuntimeError("boom")


class FakeSessionFactory:
    def __init__(self, session: FakeSession) -> None:
        self.session = session

    def __call__(self) -> "FakeSessionFactory":
        return self

    async def __aenter__(self) -> FakeSession:
        return self.session

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None


class FakeOperationLog:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


@pytest.mark.asyncio
async def test_handle_operation_log_event_ignores_other_event(monkeypatch: pytest.MonkeyPatch) -> None:
    dummy_logger = DummyLogger()
    monkeypatch.setattr(subscriber, "logger", dummy_logger)

    await subscriber.handle_operation_log_event(Event())
    assert dummy_logger.debug_calls == []
    assert dummy_logger.error_calls == []


@pytest.mark.asyncio
async def test_handle_operation_log_event_saves_log_and_parses_module(monkeypatch: pytest.MonkeyPatch) -> None:
    dummy_logger = DummyLogger()
    fake_session = FakeSession()

    monkeypatch.setattr(subscriber, "logger", dummy_logger)
    monkeypatch.setattr(subscriber, "AsyncSessionLocal", FakeSessionFactory(fake_session))
    monkeypatch.setattr(subscriber, "OperationLog", FakeOperationLog)

    event = OperationLogEvent(
        user_id="00000000-0000-0000-0000-000000000001",
        username="u",
        ip="127.0.0.1",
        method="GET",
        path="/api/v1/users/",
        status_code=200,
        process_time=0.1,
        params={"query": {"a": "1"}},
        response_result={"code": 200, "msg": "ok"},
        user_agent="UA",
    )

    await subscriber.handle_operation_log_event(event)

    assert fake_session.committed == 1
    assert len(fake_session.added) == 1

    saved = fake_session.added[0]
    assert isinstance(saved, FakeOperationLog)
    assert saved.kwargs["module"] == "users"
    assert saved.kwargs["summary"] == "GET /api/v1/users/"
    assert saved.kwargs["params"] == {"query": {"a": "1"}}
    assert saved.kwargs["response_result"] == {"code": 200, "msg": "ok"}
    assert saved.kwargs["user_agent"] == "UA"


@pytest.mark.asyncio
async def test_handle_operation_log_event_commit_error_is_logged(monkeypatch: pytest.MonkeyPatch) -> None:
    dummy_logger = DummyLogger()
    fake_session = FakeSession(fail_commit=True)

    monkeypatch.setattr(subscriber, "logger", dummy_logger)
    monkeypatch.setattr(subscriber, "AsyncSessionLocal", FakeSessionFactory(fake_session))
    monkeypatch.setattr(subscriber, "OperationLog", FakeOperationLog)

    event = OperationLogEvent(
        user_id="00000000-0000-0000-0000-000000000001",
        username="u",
        ip=None,
        method="POST",
        path="/health",
        status_code=500,
        process_time=1.2,
        params=None,
        response_result=None,
        user_agent=None,
    )

    await subscriber.handle_operation_log_event(event)
    assert len(dummy_logger.error_calls) == 1


def test_register_log_subscribers_subscribes(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[type, object]] = []

    def fake_subscribe(event_type: type, handler: object) -> None:
        calls.append((event_type, handler))

    monkeypatch.setattr(subscriber.event_bus, "subscribe", fake_subscribe)

    subscriber.register_log_subscribers()
    assert calls
    assert calls[0][0].__name__ == "OperationLogEvent"
