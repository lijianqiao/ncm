"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: conftest.py
@DateTime: 2025-12-30 16:30:00
@Docs: pytest 测试配置和 fixtures.
"""

import asyncio
from collections.abc import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import StaticPool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.deps import get_db
from app.core.config import settings
from app.core.rate_limiter import limiter
from app.core.security import get_password_hash
from app.crud.crud_log import login_log, operation_log
from app.crud.crud_menu import menu as menu_crud
from app.crud.crud_role import role as role_crud
from app.crud.crud_user import user as user_crud
from app.main import app
from app.models.base import Base
from app.models.user import User
from app.services.dashboard_service import DashboardService

# 测试数据库 URL (使用内存 SQLite)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop]:
    """
    创建事件循环 fixture.
    """
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def async_engine():
    """
    创建测试数据库引擎。
    """
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(async_engine) -> AsyncGenerator[AsyncSession]:
    """
    创建测试数据库会话。
    """
    async_session_maker = async_sessionmaker(
        bind=async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )

    async with async_session_maker() as session:
        yield session


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient]:
    """
    创建测试 HTTP 客户端。
    """

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture(scope="function")
async def test_user(db_session: AsyncSession) -> User:
    """
    创建测试用户。
    """
    user = User(
        username="testuser",
        password=get_password_hash("Test@123456"),
        email="test@example.com",
        phone="+8613800138001",
        nickname="测试用户",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture(scope="function")
async def test_superuser(db_session: AsyncSession) -> User:
    """
    创建测试超级管理员。
    """
    user = User(
        username="admin",
        password=get_password_hash("Admin@123456"),
        email="admin@example.com",
        phone="+8613800138000",
        nickname="管理员",
        is_active=True,
        is_superuser=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture(scope="function")
async def auth_headers(client: AsyncClient, test_superuser: User) -> dict[str, str]:
    """
    获取认证头 (使用超级管理员登录)。
    """
    response = await client.post(
        f"{settings.API_V1_STR}/auth/login",
        data={"username": "admin", "password": "Admin@123456"},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="session", autouse=True)
def override_settings():
    """
    强制覆盖测试配置。
    """
    settings.PASSWORD_COMPLEXITY_ENABLED = True
    limiter.enabled = False


@pytest.fixture(scope="function")
def dashboard_service(db_session: AsyncSession) -> DashboardService:
    """
    创建 DashboardService fixture.
    """
    return DashboardService(
        db=db_session,
        user_crud=user_crud,
        role_crud=role_crud,
        menu_crud=menu_crud,
        login_log_crud=login_log,
        operation_log_crud=operation_log,
    )
