"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: backup_service.py
@DateTime: 2026-01-09 20:30:00
@Docs: 配置备份服务业务逻辑 (Backup Service Logic).
"""

from datetime import UTC, datetime, timedelta
from enum import Enum
from re import S
from typing import Any
from uuid import UUID, uuid4

from scrapli.exceptions import ScrapliAuthenticationFailed
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.decorator import transactional
from app.core.enums import AuthType, BackupStatus, BackupType, DeviceStatus
from app.core.exceptions import BadRequestException, NotFoundException, OTPRequiredException
from app.core.logger import logger
from app.core.minio_client import delete_object, get_text, put_text
from app.core.otp import otp_coordinator
from app.celery.tasks.task_grouping import build_backup_batches
from app.core.otp_service import otp_service
from app.crud.crud_backup import CRUDBackup
from app.crud.crud_credential import CRUDCredential
from app.crud.crud_device import CRUDDevice
from app.models.backup import Backup
from app.models.device import Device
from app.network.otp_utils import handle_otp_auth_failure, handle_otp_auth_failure_sync
from app.network.platform_config import get_platform_for_vendor
from app.schemas.backup import (
    BackupBatchDeleteResult,
    BackupBatchRequest,
    BackupBatchRestoreResult,
    BackupBatchResult,
    BackupCreate,
    BackupListQuery,
    BackupTaskStatus,
)
from app.schemas.credential import DeviceCredential
from app.services.base import DeviceCredentialMixin
from app.core.otp_helpers import build_otp_notice_from_info, build_otp_required_info, record_pause_and_build_notice
from app.utils.validators import compute_text_md5, should_skip_backup_save_due_to_unchanged_md5


class BackupService(DeviceCredentialMixin):
    """
    配置备份服务类。

    提供：
    - 单设备手动备份
    - 批量设备备份（支持 OTP 断点续传）
    - 备份内容获取（DB/MinIO 自动路由）
    - 定时任务调用的备份接口
    """

    def __init__(
        self,
        db: AsyncSession,
        backup_crud: CRUDBackup,
        device_crud: CRUDDevice,
        credential_crud: CRUDCredential,
    ):
        """
        初始化备份服务。

        Args:
            db: 异步数据库会话
            backup_crud: 备份 CRUD 实例
            device_crud: 设备 CRUD 实例
            credential_crud: 凭据 CRUD 实例
        """
        self.db = db
        self.backup_crud = backup_crud
        self.device_crud = device_crud
        self.credential_crud = credential_crud

    def _normalize_device_group_value(self, value: str | Enum | None) -> str | None:
        """
        规范化设备分组值。

        Args:
            value: 设备分组值（字符串、枚举或 None）

        Returns:
            str | None: 规范化后的字符串值
        """
        if value is None:
            return None
        if isinstance(value, Enum):
            return str(value.value)
        text = str(value)
        if text.startswith("DeviceGroup."):
            text = text.split(".", maxsplit=1)[-1]
        return text

    # ===== 备份列表查询 =====

    async def get_backups_paginated(self, query: BackupListQuery) -> tuple[list[Backup], int]:
        """
        获取分页过滤的备份列表。

        Args:
            query: 查询参数

        Returns:
            (items, total): 备份列表和总数
        """
        return await self.backup_crud.get_multi_paginated(
            self.db,
            page=query.page,
            page_size=query.page_size,
            device_id=query.device_id,
            backup_type=query.backup_type.value if query.backup_type else None,
            status=query.status.value if query.status else None,
            start_date=query.start_date,
            end_date=query.end_date,
            keyword=query.keyword,
            device_group=query.device_group,
            auth_type=query.auth_type,
            device_status=query.device_status,
            vendor=query.vendor,
        )

    async def get_recycle_backups_paginated(self, query: BackupListQuery) -> tuple[list[Backup], int]:
        """获取回收站（已软删除）备份列表。"""

        return await self.backup_crud.get_multi_deleted_paginated(
            self.db,
            page=query.page,
            page_size=query.page_size,
            device_id=query.device_id,
            backup_type=query.backup_type.value if query.backup_type else None,
            status=query.status.value if query.status else None,
            start_date=query.start_date,
            end_date=query.end_date,
            keyword=query.keyword,
            device_group=query.device_group,
            auth_type=query.auth_type,
            device_status=query.device_status,
            vendor=query.vendor,
        )

    async def get_backup(self, backup_id: UUID) -> Backup:
        """
        根据 ID 获取备份。

        Args:
            backup_id: 备份ID

        Returns:
            Backup: 备份对象

        Raises:
            NotFoundException: 备份不存在
        """
        backup = await self.backup_crud.get(self.db, id=backup_id)
        if not backup:
            raise NotFoundException(message="备份不存在")
        return backup

    async def _get_backup_any(self, backup_id: UUID) -> Backup:
        """获取备份（包括已软删除）。"""

        q = select(Backup).where(Backup.id == backup_id)
        r = await self.db.execute(q)
        backup = r.scalars().first()
        if not backup:
            raise NotFoundException(message="备份不存在")
        return backup

    async def get_device_backups(self, device_id: UUID, page: int = 1, page_size: int = 20) -> tuple[list[Backup], int]:
        """
        获取设备的备份历史。

        Args:
            device_id: 设备ID
            page: 页码
            page_size: 每页数量

        Returns:
            (items, total): 备份列表和总数
        """
        # 验证设备存在
        device = await self.device_crud.get(self.db, id=device_id)
        if not device:
            raise NotFoundException(message="设备不存在")

        return await self.backup_crud.get_paginated(
            self.db,
            page=page,
            page_size=page_size,
            max_size=500,
            device_id=device_id,
            order_by=Backup.created_at.desc(),
            options=self.backup_crud._BACKUP_OPTIONS,
        )

    async def get_device_latest_backup(self, device_id: UUID) -> Backup | None:
        """
        获取设备的最新成功备份。

        Args:
            device_id: 设备ID

        Returns:
            Backup | None: 最新备份或 None
        """
        # 验证设备存在
        device = await self.device_crud.get(self.db, id=device_id)
        if not device:
            raise NotFoundException(message="设备不存在")

        return await self.backup_crud.get_latest_by_device(self.db, device_id=device_id)

    @transactional()
    async def delete_backup(self, backup_id: UUID, hard_delete: bool = False) -> None:
        """
        删除备份（支持软删除和硬删除）。

        Args:
            backup_id: 备份ID
            hard_delete: 是否硬删除（物理删除），默认软删除

        Raises:
            NotFoundException: 备份不存在
        """
        # 硬删除时需要查询包括已软删除的记录
        if hard_delete:
            backup = await self._get_backup_any(backup_id)
        else:
            backup = await self.backup_crud.get(self.db, id=backup_id)
            if not backup:
                raise NotFoundException(message="备份不存在")

        # 先删对象存储（尽力而为），再删 DB 记录
        if backup.content_path:
            try:
                await delete_object(backup.content_path)
            except Exception as e:
                logger.warning(f"MinIO 删除对象失败: path={backup.content_path}, error={e}")

        success_count, _ = await self.backup_crud.batch_remove(self.db, ids=[backup_id], hard_delete=hard_delete)
        if success_count != 1:
            raise NotFoundException(message="备份不存在")

        delete_type = "硬删除" if hard_delete else "软删除"
        logger.info(f"备份已{delete_type}: backup_id={backup_id}")

    @transactional()
    async def delete_backups_batch(self, backup_ids: list[UUID], hard_delete: bool = False) -> BackupBatchDeleteResult:
        """
        批量删除备份（支持软删除和硬删除）。

        Args:
            backup_ids: 备份ID列表
            hard_delete: 是否硬删除（物理删除），默认软删除

        Returns:
            BackupBatchDeleteResult: 批量删除结果
        """
        if not backup_ids:
            return BackupBatchDeleteResult(success_count=0, failed_ids=[])

        unique_ids = list(dict.fromkeys(backup_ids))

        # 查询备份记录以删除对象存储
        if hard_delete:
            # 硬删除：包含已软删除的记录
            q = select(Backup).where(Backup.id.in_(unique_ids))
        else:
            # 软删除：仅查询未删除的记录
            q = select(Backup).where(Backup.id.in_(unique_ids)).where(Backup.is_deleted.is_(False))

        r = await self.db.execute(q)
        backups = list(r.scalars().all())

        # 先尽力删除对象存储
        for b in backups:
            if b.content_path:
                try:
                    await delete_object(b.content_path)
                except Exception as e:
                    logger.warning(f"MinIO 删除对象失败: path={b.content_path}, error={e}")

        success_count, failed_ids = await self.backup_crud.batch_remove(
            self.db, ids=unique_ids, hard_delete=hard_delete
        )

        delete_type = "硬删除" if hard_delete else "软删除"
        logger.info(f"批量{delete_type}备份完成: success={success_count}, failed={len(failed_ids)}")
        return BackupBatchDeleteResult(success_count=success_count, failed_ids=failed_ids)

    @transactional()
    async def restore_backup(self, backup_id: UUID) -> None:
        """恢复已软删除备份。"""

        success_count, _ = await self.backup_crud.batch_restore(self.db, ids=[backup_id])
        if success_count == 0:
            raise NotFoundException(message="备份不存在")
        logger.info(f"备份已恢复: backup_id={backup_id}")

    @transactional()
    async def restore_backups_batch(self, backup_ids: list[UUID]) -> BackupBatchRestoreResult:
        """批量恢复已软删除备份。"""
        if not backup_ids:
            return BackupBatchRestoreResult(success_count=0, failed_ids=[])

        success_count, failed_ids = await self.backup_crud.batch_restore(self.db, ids=backup_ids)
        logger.info(f"批量恢复备份完成: success={success_count}, failed={len(failed_ids)}")
        return BackupBatchRestoreResult(success_count=success_count, failed_ids=failed_ids)

    # ===== 备份内容获取 =====

    async def get_backup_content(self, backup_id: UUID) -> str:
        """
        获取备份配置内容。

        自动根据存储位置（DB 或 MinIO）获取内容。

        Args:
            backup_id: 备份ID

        Returns:
            str: 配置内容

        Raises:
            NotFoundException: 备份不存在
            BadRequestException: 备份失败或内容不可用
        """
        backup = await self.get_backup(backup_id)

        if backup.status != BackupStatus.SUCCESS.value:
            raise BadRequestException(message="备份失败，无法获取内容")

        # 优先从数据库获取
        if backup.content:
            return backup.content

        # 从 MinIO 获取
        if backup.content_path:
            return await self._get_content_from_minio(backup.content_path)

        raise BadRequestException(message="备份内容不可用")

    async def _get_content_from_minio(self, content_path: str) -> str:
        """
        从 MinIO 获取备份内容。

        Args:
            content_path: MinIO 存储路径

        Returns:
            str: 配置内容

        Note:
            MinIO 集成需要后续实现
        """
        try:
            return await get_text(content_path)
        except Exception as e:
            raise BadRequestException(message=f"从 MinIO 获取备份内容失败: {e}") from e

    # ===== 单设备备份 =====

    @transactional()
    async def backup_single_device(
        self,
        device_id: UUID,
        backup_type: BackupType = BackupType.MANUAL,
        operator_id: UUID | None = None,
        otp_code: str | None = None,
    ) -> Backup:
        """
        备份单台设备配置。

        流程：
        1. 验证设备状态
        2. 获取设备凭据
        3. 执行备份（同步，适用于单设备）
        4. 保存备份结果

        Args:
            device_id: 设备ID
            backup_type: 备份类型
            operator_id: 操作人ID

        Returns:
            Backup: 备份记录

        Raises:
            NotFoundException: 设备不存在
            BadRequestException: 设备状态异常
            OTPRequiredException: 需要输入 OTP（otp_manual 模式）
        """
        # 1. 获取设备
        device = await self.device_crud.get(self.db, id=device_id)
        if not device:
            raise NotFoundException(message="设备不存在")

        if device.status != DeviceStatus.ACTIVE.value:
            raise BadRequestException(message=f"设备 {device.name} 状态异常，无法备份")

        # 2. 如为手动 OTP 且传入 otp_code，则先缓存
        auth_type = AuthType(device.auth_type)
        if otp_code and auth_type == AuthType.OTP_MANUAL:
            if not device.dept_id:
                raise BadRequestException(message=f"设备 {device.name} 缺少部门关联")
            if not device.device_group:
                raise BadRequestException(message=f"设备 {device.name} 缺少设备分组")
            ttl = await otp_service.cache_otp(device.dept_id, device.device_group, otp_code)
            if ttl == 0:
                raise BadRequestException(message="OTP 缓存失败：Redis 服务未连接，请联系管理员")

        # 3. 获取凭据
        try:
            credential = await self._get_device_credential(device)
        except OTPRequiredException:
            # OTP 过期，需要用户重新输入
            raise

        # 4. 执行备份
        from app.network.connection_test import execute_command_on_device
        from app.network.platform_config import get_command, get_platform_for_vendor

        platform = device.platform or get_platform_for_vendor(device.vendor or "")
        try:
            backup_command = get_command("backup_config", platform)
        except ValueError as e:
            raise BadRequestException(message=str(e)) from e

        try:
            result_dict = await execute_command_on_device(
                host=device.ip_address,
                username=credential.username,
                password=credential.password,
                command=backup_command,
                platform=platform,
                port=device.ssh_port,
                timeout=60,
            )

            if not result_dict.get("success"):
                raise Exception(result_dict.get("error", "备份命令执行失败"))

            result = result_dict.get("output", "")

            # 4. 保存成功备份
            return await self._save_backup_result(
                device=device,
                backup_type=backup_type,
                operator_id=operator_id,
                config_content=result,
                status=BackupStatus.SUCCESS,
            )

        except ScrapliAuthenticationFailed as e:
            # 认证失败：调用 OTP 处理逻辑（清除缓存并抛出 OTPRequiredException）
            # 注意：这将中断当前请求并返回 428
            host_data = {
                "auth_type": "otp_manual" if AuthType(device.auth_type) == AuthType.OTP_MANUAL else "static",
                "dept_id": str(device.dept_id) if device.dept_id else None,
                "device_group": device.device_group,
                "device_id": str(device.id),
            }
            handle_otp_auth_failure_sync(host_data, e)
            raise  # handle_otp_auth_failure_sync 会 raise，这里仅仅是为了通过静态检查

        except Exception as e:
            logger.error(f"设备 {device.name} 备份失败: {e}")
            # 保存失败备份
            return await self._save_backup_result(
                device=device,
                backup_type=backup_type,
                operator_id=operator_id,
                config_content=None,
                status=BackupStatus.FAILED,
                error_message=str(e),
            )

    async def backup_with_credential(
        self,
        device: Device,
        credential: DeviceCredential,
        backup_type: BackupType = BackupType.MANUAL,
        operator_id: UUID | None = None,
    ) -> Backup:
        """
        使用已验证的凭据备份设备配置（不带事务装饰器）。

        专为 preset_service 等内部调用设计，避免：
        1. 重复获取凭据（复用已验证的 OTP）
        2. 事务嵌套问题

        Args:
            device: 设备对象
            credential: 已验证的凭据（DeviceCredential）
            backup_type: 备份类型
            operator_id: 操作人ID

        Returns:
            Backup: 备份记录
        """
        from app.network.connection_test import execute_command_on_device
        from app.network.platform_config import get_command, get_platform_for_vendor

        platform = device.platform or get_platform_for_vendor(device.vendor or "")
        try:
            backup_command = get_command("backup_config", platform)
        except ValueError as e:
            raise BadRequestException(message=str(e)) from e

        try:
            result_dict = await execute_command_on_device(
                host=device.ip_address,
                username=credential.username,
                password=credential.password,
                command=backup_command,
                platform=platform,
                port=device.ssh_port,
                timeout=60,
            )

            if not result_dict.get("success"):
                raise Exception(result_dict.get("error", "备份命令执行失败"))

            result = result_dict.get("output", "")

            # 保存成功备份
            return await self._save_backup_result(
                device=device,
                backup_type=backup_type,
                operator_id=operator_id,
                config_content=result,
                status=BackupStatus.SUCCESS,
            )

        except ScrapliAuthenticationFailed as e:
            # 认证失败：调用 OTP 处理逻辑（使用异步版本）
            host_data = {
                "auth_type": "otp_manual" if AuthType(device.auth_type) == AuthType.OTP_MANUAL else "static",
                "dept_id": str(device.dept_id) if device.dept_id else None,
                "device_group": device.device_group,
                "device_id": str(device.id),
            }
            await handle_otp_auth_failure(host_data, e)
            raise  # handle_otp_auth_failure 会 raise OTPRequiredException

        except Exception as e:
            logger.error(f"设备 {device.name} 备份失败: {e}")
            # 保存失败备份
            return await self._save_backup_result(
                device=device,
                backup_type=backup_type,
                operator_id=operator_id,
                config_content=None,
                status=BackupStatus.FAILED,
                error_message=str(e),
            )

    async def _save_backup_result(
        self,
        device: Device,
        backup_type: BackupType,
        operator_id: UUID | None,
        config_content: str | None,
        status: BackupStatus,
        error_message: str | None = None,
    ) -> Backup:
        """
        保存备份结果。

        存储策略：
        - 配置 < 64KB：直接存储在 content 字段
        - 配置 >= 64KB：存储到 MinIO，路径存储在 content_path

        Args:
            device: 设备对象
            backup_type: 备份类型
            operator_id: 操作人ID
            config_content: 配置内容（可为 None）
            status: 备份状态
            error_message: 错误信息

        Returns:
            Backup: 备份记录
        """
        content = None
        content_path = None
        content_size = 0
        md5_hash = None

        if config_content:
            content_size = len(config_content.encode("utf-8"))
            md5_hash = compute_text_md5(config_content)

            # md5 去重：仅对 pre/post 变更备份生效，避免前后都备份导致重复存储
            if status == BackupStatus.SUCCESS and backup_type in {BackupType.PRE_CHANGE, BackupType.POST_CHANGE}:
                old_md5 = await self.backup_crud.get_latest_md5_by_device(self.db, device.id)
                if should_skip_backup_save_due_to_unchanged_md5(
                    backup_type=backup_type.value,
                    status=status.value,
                    old_md5=old_md5,
                    new_md5=md5_hash,
                ):
                    latest = await self.backup_crud.get_latest_by_device(self.db, device.id)
                    if latest:
                        logger.info(
                            f"备份内容未变化，跳过保存: device={device.name}, type={backup_type.value}, md5={md5_hash}"
                        )
                        return latest

            if content_size < settings.BACKUP_CONTENT_SIZE_THRESHOLD_BYTES:
                # 小配置：直接存 DB
                content = config_content
            else:
                # 大配置：存 MinIO
                content_path = await self._save_content_to_minio(
                    device_id=device.id,
                    config_content=config_content,
                )

        backup_data = BackupCreate(
            backup_type=backup_type,
            device_id=device.id,
            content=content,
            content_path=content_path,
            content_size=content_size,
            md5_hash=md5_hash,
            status=status,
            operator_id=operator_id,
            error_message=error_message,
        )

        backup = Backup(**backup_data.model_dump())
        self.db.add(backup)
        await self.db.flush()
        await self.db.refresh(backup)

        logger.info(f"备份保存完成: device={device.name}, status={status.value}, size={content_size}")

        # 保留策略：按条数（各类型可配）+ 按天数（默认 7 天），保证每台设备至少保留 1 条
        if status == BackupStatus.SUCCESS:
            await self._enforce_retention(device_id=device.id)

        return backup

    def _get_keep_count(self, backup_type: BackupType) -> int:
        if backup_type == BackupType.SCHEDULED:
            return settings.BACKUP_RETENTION_SCHEDULED_KEEP
        if backup_type == BackupType.MANUAL:
            return settings.BACKUP_RETENTION_MANUAL_KEEP
        if backup_type == BackupType.PRE_CHANGE:
            return settings.BACKUP_RETENTION_PRE_CHANGE_KEEP
        if backup_type == BackupType.POST_CHANGE:
            return settings.BACKUP_RETENTION_POST_CHANGE_KEEP
        if backup_type == BackupType.INCREMENTAL:
            return settings.BACKUP_RETENTION_INCREMENTAL_KEEP
        return 0

    async def _enforce_retention(self, device_id: UUID) -> None:
        # 保底保留：最新一条 + 最新成功一条（如存在），避免“超过天数后把可用备份删光”
        keep_ids: set[UUID] = set()

        latest_any_q = (
            select(Backup.id)
            .where(Backup.device_id == device_id)
            .where(Backup.is_deleted.is_(False))
            .order_by(Backup.created_at.desc())
            .limit(1)
        )
        latest_any = await self.db.execute(latest_any_q)
        latest_any_id = latest_any.scalar()
        if latest_any_id:
            keep_ids.add(latest_any_id)

        latest_success_q = (
            select(Backup.id)
            .where(Backup.device_id == device_id)
            .where(Backup.is_deleted.is_(False))
            .where(Backup.status == BackupStatus.SUCCESS.value)
            .order_by(Backup.created_at.desc())
            .limit(1)
        )
        latest_success = await self.db.execute(latest_success_q)
        latest_success_id = latest_success.scalar()
        if latest_success_id:
            keep_ids.add(latest_success_id)

        to_delete: dict[UUID, Backup] = {}

        # 1) 按条数保留（按类型、仅清理成功备份；失败备份交给按天数清理）
        for bt in BackupType:
            keep = self._get_keep_count(bt)
            if keep <= 0:
                continue

            q = (
                select(Backup)
                .where(Backup.device_id == device_id)
                .where(Backup.is_deleted.is_(False))
                .where(Backup.status == BackupStatus.SUCCESS.value)
                .where(Backup.backup_type == bt.value)
                .order_by(Backup.created_at.desc())
                .offset(keep)
            )
            r = await self.db.execute(q)
            for b in r.scalars().all():
                if b.id in keep_ids:
                    continue
                to_delete[b.id] = b

        # 2) 按天数保留（所有备份类型；至少保留 keep_ids）
        keep_days = settings.BACKUP_RETENTION_KEEP_DAYS
        if keep_days > 0:
            cutoff = datetime.now(UTC) - timedelta(days=keep_days)
            q = (
                select(Backup)
                .where(Backup.device_id == device_id)
                .where(Backup.is_deleted.is_(False))
                .where(Backup.created_at < cutoff)
            )
            r = await self.db.execute(q)
            for b in r.scalars().all():
                if b.id in keep_ids:
                    continue
                to_delete[b.id] = b

        if not to_delete:
            return

        deleted = 0
        for b in to_delete.values():
            if b.content_path:
                try:
                    await delete_object(b.content_path)
                except Exception as e:
                    logger.warning(f"MinIO 删除对象失败: path={b.content_path}, error={e}")

            b.is_deleted = True
            self.db.add(b)
            deleted += 1

        await self.db.flush()
        logger.info(f"备份保留策略清理完成: device_id={device_id}, deleted={deleted}")

    async def _save_content_to_minio(self, device_id: UUID, config_content: str) -> str:
        """
        将配置内容保存到 MinIO。

        Args:
            device_id: 设备ID
            config_content: 配置内容

        Returns:
            str: MinIO 存储路径

        Note:
            MinIO 集成需要后续实现
        """
        object_name = f"backups/{device_id}/{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.txt"
        await put_text(object_name, config_content)
        return object_name

    # ===== 批量备份 =====

    async def backup_devices_batch(
        self,
        request: BackupBatchRequest,
        operator_id: UUID | None = None,
    ) -> BackupBatchResult:
        """
        批量备份设备（异步 Celery 任务）。

        支持断点续传：
        - 如果提供 skip_device_ids，会跳过这些已成功的设备
        - 如果 OTP 过期，抛出 OTPRequiredException 携带进度信息

        Args:
            request: 批量备份请求
            operator_id: 操作人ID

        Returns:
            BackupBatchResult: 批量备份结果（含任务ID）

        Raises:
            OTPRequiredException: 需要输入 OTP（含断点续传信息）
        """
        # 1. 获取待备份设备
        device_ids_to_backup = [
            did for did in request.device_ids if not request.skip_device_ids or did not in request.skip_device_ids
        ]

        if not device_ids_to_backup:
            return BackupBatchResult(
                task_id=request.resume_task_id or "no-op",
                total_devices=0,
                success_count=len(request.skip_device_ids or []),
                failed_count=0,
                success_devices=request.skip_device_ids or [],
            )

        # 2. 批量获取设备
        devices = await self.device_crud.get_by_ids(self.db, device_ids_to_backup, options=self.device_crud._DEVICE_OPTIONS)
        if not devices:
            raise BadRequestException(message="没有找到有效设备")

        # 3. 按认证类型/部门/分组拆分并按 100 台分批
        selected_devices = list(devices)
        batches = build_backup_batches(selected_devices, chunk_size=100)
        if not batches:
            raise BadRequestException(message="没有可备份的设备")

        batch_id = request.resume_task_id or str(uuid4())
        children: list[dict[str, Any]] = []
        pending_notice: tuple[UUID, str, list[str], str] | None = None
        waiting_notice: tuple[UUID, str, list[str], str] | None = None
        waiting_groups: dict[tuple[str, str], dict[str, Any]] = {}

        from app.celery.tasks.backup import async_backup_devices

        for batch in batches:
            dept_id = batch.get("dept_id")
            device_group = batch.get("device_group")
            batch_devices: list[Device] = batch.get("devices") or []
            if not batch_devices:
                continue

            # OTP 手动设备预检
            otp_device_ids = [str(d.id) for d in batch_devices if AuthType(d.auth_type) == AuthType.OTP_MANUAL]
            batch_device_ids = [str(d.id) for d in batch_devices]
            if otp_device_ids:
                if not dept_id or not device_group:
                    raise BadRequestException(message="设备缺少部门或设备分组")
                otp_check = await otp_coordinator.get_or_require_otp(
                    dept_id,
                    str(device_group),
                    task_id=batch_id,
                    pending_device_ids=batch_device_ids,
                )
                if otp_check["status"] != "ready":
                    await otp_coordinator.record_pause(
                        batch_id,
                        dept_id,
                        str(device_group),
                        batch_device_ids,
                        reason="otp_required",
                    )
                    key = (str(dept_id), str(device_group))
                    entry = waiting_groups.get(key)
                    if not entry:
                        entry = {
                            "dept_id": str(dept_id),
                            "device_group": str(device_group),
                            "pending_device_ids": set(),
                            "otp_wait_status": otp_check["status"],
                        }
                        waiting_groups[key] = entry
                    entry["pending_device_ids"].update(batch_device_ids)
                    if waiting_notice is None:
                        waiting_notice = (dept_id, str(device_group), batch_device_ids, otp_check["status"])
                    if otp_check["should_notify"] and pending_notice is None:
                        pending_notice = waiting_notice
                    continue

            hosts_data: list[dict[str, Any]] = []
            for device in batch_devices:
                try:
                    auth_type = AuthType(device.auth_type)
                    if auth_type == AuthType.OTP_MANUAL:
                        if not device.dept_id:
                            raise BadRequestException(message=f"设备 {device.name} 缺少部门关联")
                        credential_row = await self.credential_crud.get_by_dept_and_group(
                            self.db,
                            device.dept_id,
                            self._normalize_device_group_value(device.device_group) or "",
                        )
                        if not credential_row:
                            raise BadRequestException(message=f"设备 {device.name} 的凭据未配置")
                        username = credential_row.username
                        password = ""
                        extra_data = {
                            "auth_type": "otp_manual",
                            "dept_id": str(device.dept_id),
                            "device_group": str(device.device_group),
                            "device_id": str(device.id),
                            "device_name": device.name,
                            "vendor": device.vendor,
                        }
                    elif auth_type == AuthType.OTP_SEED:
                        if not device.dept_id:
                            raise BadRequestException(message=f"设备 {device.name} 缺少部门关联")
                        credential_row = await self.credential_crud.get_by_dept_and_group(
                            self.db,
                            device.dept_id,
                            self._normalize_device_group_value(device.device_group) or "",
                        )
                        if not credential_row or not credential_row.otp_seed_encrypted:
                            raise BadRequestException(message=f"设备 {device.name} 的凭据未配置 OTP 种子")
                        username = credential_row.username
                        password = ""
                        extra_data = {
                            "auth_type": "otp_seed",
                            "otp_seed_encrypted": credential_row.otp_seed_encrypted,
                            "dept_id": str(device.dept_id),
                            "device_group": str(device.device_group),
                            "device_id": str(device.id),
                            "device_name": device.name,
                            "vendor": device.vendor,
                        }
                    else:
                        credential = await self._get_device_credential(device)
                        username = credential.username
                        password = credential.password
                        extra_data = {
                            "auth_type": "static",
                            "device_id": str(device.id),
                            "device_name": device.name,
                            "vendor": device.vendor,
                        }

                    hosts_data.append(
                        {
                            "name": str(device.id),
                            "hostname": device.ip_address,
                            "platform": device.platform or get_platform_for_vendor(str(device.vendor)),
                            "username": username,
                            "password": password,
                            "port": device.ssh_port,
                            "device_id": str(device.id),
                            "operator_id": str(operator_id) if operator_id else None,
                            "data": extra_data,
                        }
                    )
                except Exception as e:
                    logger.warning(f"设备 {device.name} 凭据获取失败: {e}")

            if not hosts_data:
                continue

            def _auth_priority(h: dict) -> int:
                auth_type = (h.get("data") or {}).get("auth_type")
                if auth_type == "otp_manual":
                    return 0
                if auth_type == "otp_seed":
                    return 1
                return 2

            hosts_data.sort(key=_auth_priority)
            task = async_backup_devices.delay(  # type: ignore[attr-defined]
                hosts_data=hosts_data,
                num_workers=min(100, len(hosts_data)),
                backup_type=request.backup_type.value,
                operator_id=str(operator_id) if operator_id else None,
            )
            children.append(
                {
                    "task_id": task.id,
                    "dept_id": str(dept_id) if dept_id else None,
                    "device_group": str(device_group) if device_group else None,
                    "device_ids": [str(d.id) for d in batch_devices],
                    "batch_index": batch.get("batch_index"),
                }
            )

        waiting_groups_payload = [
            {
                "dept_id": entry["dept_id"],
                "device_group": entry["device_group"],
                "pending_device_ids": sorted(entry["pending_device_ids"]),
                "otp_wait_status": entry.get("otp_wait_status"),
            }
            for entry in waiting_groups.values()
        ]

        if request.resume_task_id:
            appended = await otp_coordinator.registry.append_children(batch_id, children)
            if not appended:
                await otp_coordinator.registry.create_batch(
                    batch_id,
                    {
                        "task_type": "backup",
                        "children": children,
                        "waiting_groups": waiting_groups_payload,
                        "backup_type": request.backup_type.value,
                        "operator_id": str(operator_id) if operator_id else None,
                        "total_devices": len(selected_devices),
                    },
                )
        else:
            await otp_coordinator.registry.create_batch(
                batch_id,
                {
                    "task_type": "backup",
                    "children": children,
                    "waiting_groups": waiting_groups_payload,
                    "backup_type": request.backup_type.value,
                    "operator_id": str(operator_id) if operator_id else None,
                    "total_devices": len(selected_devices),
                },
            )

        notice = pending_notice
        if not notice and not children and waiting_notice:
            notice = waiting_notice
        if notice:
            dept_id, device_group, pending_ids, wait_status = notice
            message = "用户未提供 OTP 验证码，连接失败" if wait_status == "timeout" else "需要输入 OTP 验证码"
            raise OTPRequiredException(
                dept_id=dept_id,
                device_group=device_group,
                failed_devices=pending_ids,
                message=message,
                otp_wait_status=wait_status,
                task_id=batch_id,
                pending_device_ids=pending_ids,
            )

        if not children:
            raise BadRequestException(message="没有可备份的设备（全部等待 OTP）")

        logger.info(f"批量备份任务已提交: task_id={batch_id}, 子任务数={len(children)}")
        return BackupBatchResult(
            task_id=batch_id,
            total_devices=len(selected_devices),
            success_count=0,
            failed_count=0,
            can_resume=True,
        )

    async def get_task_status(self, task_id: str) -> BackupTaskStatus:
        """
        查询 Celery 任务状态。

        Args:
            task_id: Celery 任务ID

        Returns:
            BackupTaskStatus: 任务状态
        """
        batch_info = await otp_coordinator.registry.get_batch(task_id)
        if batch_info:
            return await self._get_batch_task_status(task_id, batch_info)

        from celery.result import AsyncResult

        from app.celery.app import celery_app

        result = AsyncResult(task_id, app=celery_app)

        # 调试日志：记录原始状态
        logger.debug(
            "查询任务状态",
            task_id=task_id,
            celery_status=result.status,
            info_type=type(result.info).__name__ if result.info else None,
            info_keys=list(result.info.keys()) if isinstance(result.info, dict) else None,
        )

        # 将 Celery 状态转换为前端期望的小写格式
        status_map = {
            "PENDING": "pending",
            "STARTED": "running",
            "PROGRESS": "running",
            "SUCCESS": "success",
            "FAILURE": "failed",
            "REVOKED": "failed",
        }
        mapped_status = status_map.get(result.status, result.status.lower()) or "pending"

        status_response = BackupTaskStatus(
            task_id=task_id,
            status=mapped_status,
        )

        if result.status == "PROGRESS":
            # 提取进度信息中的数值进度（如有）
            info = result.info or {}
            if isinstance(info, dict):
                if info.get("otp_required"):
                    notice = await build_otp_notice_from_info(info, task_id=task_id, force=True)
                    if not notice:
                        return status_response
                    status_response.status = "running"
                    status_response.otp_notice = notice
                    return status_response
                stage = info.get("stage", "")
                message = info.get("message", "")
                status_response.progress = {"stage": stage, "message": message}

                # 提取进度数值（用于前端进度条）
                completed = info.get("completed")
                total = info.get("total")
                if completed is not None:
                    status_response.completed = completed
                if total is not None:
                    status_response.total = total
                    if completed is not None and total > 0:
                        status_response.percent = min(100, int(completed * 100 / total))
            else:
                status_response.progress = {"message": str(info)}
        elif result.status == "SUCCESS":
            info = result.result or {}
            if info.get("otp_required"):
                notice = await build_otp_notice_from_info(info, task_id=task_id, force=True)
                if not notice:
                    return status_response
                status_response.status = "running"
                status_response.otp_notice = notice
                return status_response

            # 获取汇总数据
            total = info.get("total", 0)
            success = info.get("success", 0)
            failed = info.get("failed", 0)

            status_response.total_devices = total
            status_response.success_count = success
            status_response.failed_count = failed

            # 完成时的进度数值（100%）
            status_response.completed = total
            status_response.total = total
            status_response.percent = 100 if total > 0 else 0

            status_response.failed_devices = [
                {"name": v.get("device_name") or k, "error": v.get("error")}
                for k, v in info.get("results", {}).items()
                if v.get("status") == "failed"
            ]

            # 调试日志：记录实际返回的数据
            logger.debug(
                "任务状态查询 SUCCESS",
                task_id=task_id,
                raw_result_keys=list(info.keys()) if isinstance(info, dict) else type(info).__name__,
                total=total,
                success=success,
                failed=failed,
            )
        elif result.status == "FAILURE":
            from app.core.exceptions import OTPRequiredException

            if isinstance(result.result, OTPRequiredException):
                wait_status = None
                if isinstance(result.result.details, dict):
                    wait_status = result.result.details.get("otp_wait_status")
                pending_ids = result.result.failed_devices or None
                if isinstance(result.result.details, dict) and result.result.details.get("pending_device_ids"):
                    pending_ids = result.result.details.get("pending_device_ids")
                info = build_otp_required_info(
                    dept_id=str(result.result.dept_id) if result.result.dept_id else None,
                    device_group=result.result.device_group,
                    failed_device_ids=pending_ids,
                    wait_status=wait_status,
                )
                notice = await build_otp_notice_from_info(
                    info,
                    task_id=task_id,
                    message=str(result.result) or None,
                    force=True,
                )
                if notice:
                    status_response.status = "running"
                    status_response.otp_notice = notice
                    return status_response
            else:
                status_response.progress = {"error": str(result.result)}

        return status_response

    async def _get_batch_task_status(self, task_id: str, batch_info: dict[str, Any]) -> BackupTaskStatus:
        from celery.result import AsyncResult

        from app.celery.app import celery_app

        children: list[dict[str, Any]] = batch_info.get("children") or []
        latest_children: dict[tuple[str, str, int], dict[str, Any]] = {}
        for child in children:
            dept_id = str(child.get("dept_id") or "")
            device_group = str(child.get("device_group") or "")
            batch_index_raw = child.get("batch_index")
            batch_index = int(batch_index_raw) if batch_index_raw is not None else -1
            key = (dept_id, device_group, batch_index)
            latest_children[key] = child
        effective_children = list(latest_children.values())
        total_devices = int(batch_info.get("total_devices") or 0) or sum(
            len(child.get("device_ids") or []) for child in effective_children
        )
        status_response = BackupTaskStatus(
            task_id=task_id,
            status="running",
            total=total_devices,
            total_devices=total_devices,
        )

        completed = 0
        success_count = 0
        failed_count = 0
        failed_devices: list[dict[str, Any]] = []
        has_running = False

        for child in effective_children:
            child_id = child.get("task_id")
            if not child_id:
                continue
            result = AsyncResult(child_id, app=celery_app)
            if result.status in {"PENDING", "STARTED", "PROGRESS"}:
                has_running = True
                if isinstance(result.info, dict):
                    completed += int(result.info.get("completed") or 0)
                continue

            if result.status == "SUCCESS":
                info = result.result or {}
                if isinstance(info, dict) and info.get("otp_required"):
                    dept_id = info.get("otp_dept_id") or child.get("dept_id")
                    device_group = info.get("otp_device_group") or child.get("device_group")
                    pending_ids = child.get("device_ids") or info.get("otp_failed_device_ids") or []
                    if dept_id and device_group:
                        notice = await record_pause_and_build_notice(
                            task_id=task_id,
                            dept_id=UUID(str(dept_id)),
                            device_group=str(device_group),
                            pending_device_ids=pending_ids,
                            wait_status=info.get("otp_wait_status"),
                            message=info.get("message"),
                            force=True,
                        )
                        if notice:
                            status_response.otp_notice = notice
                            return status_response
                    continue

                if isinstance(info, dict):
                    total = int(info.get("total") or 0)
                    success = int(info.get("success") or 0)
                    failed = int(info.get("failed") or 0)
                    completed += total
                    success_count += success
                    failed_count += failed
                    for name, res in (info.get("results") or {}).items():
                        if isinstance(res, dict) and res.get("status") == "failed":
                            failed_devices.append({"name": res.get("device_name") or name, "error": res.get("error")})
                continue

            if result.status == "FAILURE":
                from app.core.exceptions import OTPRequiredException

                if isinstance(result.result, OTPRequiredException):
                    dept_id = result.result.details.get("dept_id") if isinstance(result.result.details, dict) else None
                    device_group = result.result.details.get("device_group") if isinstance(result.result.details, dict) else None
                    pending_ids = []
                    if child.get("device_ids"):
                        pending_ids.extend(child.get("device_ids") or [])
                    if isinstance(result.result.details, dict) and result.result.details.get("pending_device_ids"):
                        pending_ids.extend(result.result.details.get("pending_device_ids") or [])
                    pending_ids = list({str(x) for x in pending_ids if x})
                    if dept_id and device_group:
                        wait_status = None
                        if isinstance(result.result.details, dict):
                            wait_status = result.result.details.get("otp_wait_status")
                        notice = await record_pause_and_build_notice(
                            task_id=task_id,
                            dept_id=UUID(str(dept_id)),
                            device_group=str(device_group),
                            pending_device_ids=pending_ids,
                            wait_status=wait_status,
                            message=str(result.result) or None,
                            force=True,
                        )
                        if notice:
                            status_response.otp_notice = notice
                            return status_response
                # 失败任务按子任务设备数计入
                failed_count += len(child.get("device_ids") or [])
                completed += len(child.get("device_ids") or [])

        waiting_groups_payload = batch_info.get("waiting_groups") or []
        for group in waiting_groups_payload:
            dept_id = group.get("dept_id")
            device_group = group.get("device_group")
            if not dept_id or not device_group:
                continue
            pause_state = await otp_coordinator.get_pause(task_id, UUID(str(dept_id)), str(device_group))
            if not pause_state:
                continue
            pending_ids = pause_state.get("pending_device_ids") or group.get("pending_device_ids") or []
            info = build_otp_required_info(
                dept_id=dept_id,
                device_group=device_group,
                failed_device_ids=pending_ids,
                wait_status=group.get("otp_wait_status"),
            )
            notice = await build_otp_notice_from_info(info, task_id=task_id, force=True)
            if notice:
                status_response.otp_notice = notice
                return status_response

        status_response.completed = completed
        status_response.total = total_devices
        status_response.percent = int((completed * 100 / total_devices)) if total_devices > 0 else 0
        status_response.success_count = success_count
        status_response.failed_count = failed_count
        status_response.failed_devices = failed_devices

        if not has_running and completed >= total_devices:
            status_response.status = "success" if failed_count == 0 else "failed"

        return status_response

    # ===== 定时任务接口 =====

    async def get_all_active_devices_for_backup(self) -> list[Device]:
        """
        获取所有活跃设备（供定时任务使用）。

        Returns:
            list[Device]: 活跃设备列表
        """
        devices, _ = await self.device_crud.get_paginated(
            self.db,
            page=1,
            page_size=10000,
            max_size=10000,
            status=DeviceStatus.ACTIVE.value,
        )
        return devices

    async def check_config_changed(self, device_id: UUID, new_md5: str) -> bool:
        """
        检查设备配置是否变更。

        Args:
            device_id: 设备ID
            new_md5: 新配置的 MD5 值

        Returns:
            bool: True 表示配置已变更
        """
        old_md5 = await self.backup_crud.get_latest_md5_by_device(self.db, device_id)
        return old_md5 != new_md5
