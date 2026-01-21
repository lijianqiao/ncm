"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: backup_service.py
@DateTime: 2026-01-09 20:30:00
@Docs: 配置备份服务业务逻辑 (Backup Service Logic).
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from scrapli.exceptions import ScrapliAuthenticationFailed
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.decorator import transactional
from app.core.enums import AuthType, BackupStatus, BackupType, DeviceStatus
from app.core.exceptions import BadRequestException, NotFoundException, OTPRequiredException
from app.core.logger import logger
from app.core.minio_client import delete_object, get_text, put_text
from app.core.otp_service import otp_service
from app.crud.crud_backup import CRUDBackup
from app.crud.crud_credential import CRUDCredential
from app.crud.crud_device import CRUDDevice
from app.models.backup import Backup
from app.models.device import Device
from app.network.otp_utils import handle_otp_auth_failure_sync
from app.network.platform_config import get_platform_for_vendor
from app.schemas.backup import (
    BackupBatchDeleteResult,
    BackupBatchRequest,
    BackupBatchRestoreResult,
    BackupBatchResult,
    BackupCreate,
    BackupListQuery,
    BackupTaskStatus,
    OTPNotice,
)
from app.services.base import DeviceCredentialMixin
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
        self.db = db
        self.backup_crud = backup_crud
        self.device_crud = device_crud
        self.credential_crud = credential_crud

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

        return await self.backup_crud.get_by_device(self.db, device_id=device_id, page=page, page_size=page_size)

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
            device_id=device.id,
            backup_type=backup_type,
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
        devices = await self.device_crud.get_multi_by_ids(self.db, ids=device_ids_to_backup)
        if not devices:
            raise BadRequestException(message="没有找到有效设备")

        # 3. 按 (dept_id, device_group) 分组，检查 OTP 可用性
        device_groups: dict[tuple[UUID | None, str], list[Device]] = {}
        for device in devices:
            if device.status != DeviceStatus.ACTIVE.value:
                continue
            key = (device.dept_id, device.device_group)
            if key not in device_groups:
                device_groups[key] = []
            device_groups[key].append(device)

        # 4. 检查每个分组的 OTP（对于 otp_manual 类型）
        # 收集需要 OTP 的分组
        otp_required_groups: list[tuple[UUID, str]] = []
        for (dept_id, device_group), group_devices in device_groups.items():
            if not group_devices:
                continue

            first_device = group_devices[0]
            if AuthType(first_device.auth_type) == AuthType.OTP_MANUAL:
                if dept_id is None:
                    continue
                # 检查缓存
                cached_otp = await otp_service.get_cached_otp(dept_id, device_group)
                if not cached_otp:
                    otp_required_groups.append((dept_id, device_group))

        # 如果有分组需要 OTP，抛出异常
        if otp_required_groups:
            first_group = otp_required_groups[0]
            raise OTPRequiredException(
                dept_id=first_group[0],
                device_group=first_group[1],
                failed_devices=[str(d.id) for d in devices],
                message=f"需要为 {len(otp_required_groups)} 个设备分组输入 OTP",
            )

        # 5. 准备 Celery 任务数据
        hosts_data = []
        for device in devices:
            if device.status != DeviceStatus.ACTIVE.value:
                continue

            try:
                auth_type = AuthType(device.auth_type)

                if auth_type == AuthType.OTP_MANUAL:
                    if not device.dept_id:
                        raise BadRequestException(message=f"设备 {device.name} 缺少部门关联")
                    credential_row = await self.credential_crud.get_by_dept_and_group(
                        self.db, device.dept_id, device.device_group
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
                        self.db, device.dept_id, device.device_group
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
                        "name": device.name,
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
            raise BadRequestException(message="没有可备份的设备（凭据获取失败）")

        # OTP 手动设备优先执行，便于尽早发现 OTP 过期并提示前端
        def _auth_priority(h: dict) -> int:
            auth_type = (h.get("data") or {}).get("auth_type")
            if auth_type == "otp_manual":
                return 0
            if auth_type == "otp_seed":
                return 1
            return 2

        hosts_data.sort(key=_auth_priority)

        # 6. 提交 Celery 任务（使用异步 AsyncRunner + asyncssh）
        from app.celery.tasks.backup import async_backup_devices

        task = async_backup_devices.delay(  # type: ignore[attr-defined]
            hosts_data=hosts_data,
            num_workers=min(100, len(hosts_data)),
            backup_type=request.backup_type.value,
            operator_id=str(operator_id) if operator_id else None,
        )
        logger.info(f"批量备份任务已提交: task_id={task.id}, devices={len(hosts_data)}")

        return BackupBatchResult(
            task_id=task.id,
            total_devices=len(hosts_data),
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
        from celery.result import AsyncResult

        from app.celery.app import celery_app

        result = AsyncResult(task_id, app=celery_app)

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
                    status_response.status = "running"
                    status_response.otp_notice = OTPNotice(
                        dept_id=info.get("otp_dept_id"),
                        device_group=info.get("otp_device_group"),
                        pending_device_ids=info.get("otp_failed_device_ids") or None,
                    )
                    return status_response
                stage = info.get("stage", "")
                message = info.get("message", "")
                status_response.progress = {"stage": stage, "message": message}
            else:
                status_response.progress = {"message": str(info)}
        elif result.status == "SUCCESS":
            info = result.result or {}
            if info.get("otp_required"):
                status_response.status = "running"
                status_response.otp_notice = OTPNotice(
                    dept_id=info.get("otp_dept_id"),
                    device_group=info.get("otp_device_group"),
                    pending_device_ids=info.get("otp_failed_device_ids") or None,
                )
                return status_response

            status_response.total_devices = info.get("total", 0)
            status_response.success_count = info.get("success", 0)
            status_response.failed_count = info.get("failed", 0)
            status_response.failed_devices = [
                {"name": k, "error": v.get("error")}
                for k, v in info.get("results", {}).items()
                if v.get("status") == "failed"
            ]
        elif result.status == "FAILURE":
            from app.core.exceptions import OTPRequiredException

            if isinstance(result.result, OTPRequiredException):
                status_response.status = "running"
                pending_device_ids = None
                if result.result.failed_devices:
                    parsed = []
                    for x in result.result.failed_devices:
                        try:
                            parsed.append(UUID(str(x)))
                        except Exception:
                            pass
                    if parsed:
                        pending_device_ids = parsed

                status_response.otp_notice = OTPNotice(
                    message=str(result.result) or "需要重新输入 OTP 验证码",
                    dept_id=UUID(str(result.result.dept_id)),
                    device_group=result.result.device_group,
                    pending_device_ids=pending_device_ids,
                )
                return status_response
            else:
                status_response.progress = {"error": str(result.result)}

        return status_response

    # ===== 定时任务接口 =====

    async def get_all_active_devices_for_backup(self) -> list[Device]:
        """
        获取所有活跃设备（供定时任务使用）。

        Returns:
            list[Device]: 活跃设备列表
        """
        devices, _ = await self.device_crud.get_multi_paginated(
            self.db,
            page=1,
            page_size=10000,  # 大页获取所有
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
