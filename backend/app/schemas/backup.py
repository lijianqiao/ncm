"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: backup.py
@DateTime: 2026-01-09 20:00:00
@Docs: 配置备份 Pydantic Schema 定义。
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.core.enums import BackupStatus, BackupType, DeviceGroup
from app.schemas.common import PaginatedQuery
from app.schemas.device import DeviceResponse


class BackupBase(BaseModel):
    """备份基础模型。"""

    backup_type: BackupType = Field(default=BackupType.MANUAL, description="备份类型")


class BackupCreate(BackupBase):
    """创建备份请求（内部使用）。"""

    device_id: UUID = Field(..., description="设备ID")
    content: str | None = Field(default=None, description="配置内容")
    content_path: str | None = Field(default=None, description="MinIO 存储路径")
    content_size: int = Field(default=0, description="配置大小(字节)")
    md5_hash: str | None = Field(default=None, description="MD5 哈希值")
    status: BackupStatus = Field(default=BackupStatus.SUCCESS, description="备份状态")
    operator_id: UUID | None = Field(default=None, description="操作人ID")
    error_message: str | None = Field(default=None, description="错误信息")


class BackupResponse(BaseModel):
    """备份响应模型。"""

    id: UUID
    device_id: UUID
    backup_type: BackupType
    status: BackupStatus
    content_size: int
    md5_hash: str | None = None
    error_message: str | None = None
    operator_id: str | None = Field(default=None, description="操作人(昵称(用户名))")
    created_at: datetime
    updated_at: datetime

    # 关联设备（可选）
    device: DeviceResponse | None = None

    # 内部字段（用于计算 has_content）
    content: str | None = Field(default=None, exclude=True)
    content_path: str | None = Field(default=None, exclude=True)

    @computed_field
    @property
    def has_content(self) -> bool:
        """是否有配置内容（不直接返回内容，需要单独接口获取）。"""
        return bool(self.content or self.content_path)

    model_config = ConfigDict(from_attributes=True, use_enum_values=True)


class BackupContentResponse(BaseModel):
    """备份配置内容响应。"""

    id: UUID
    device_id: UUID
    content: str = Field(..., description="配置内容")
    content_size: int
    md5_hash: str | None = None


class BackupListQuery(PaginatedQuery):
    """备份列表查询参数。"""

    device_id: UUID | None = Field(default=None, description="设备ID筛选")
    backup_type: BackupType | None = Field(default=None, description="备份类型筛选")
    status: BackupStatus | None = Field(default=None, description="备份状态筛选")
    start_date: datetime | None = Field(default=None, description="开始时间")
    end_date: datetime | None = Field(default=None, description="结束时间")

    # 关键字搜索（设备名称/IP地址）
    keyword: str | None = Field(default=None, max_length=100, description="关键字搜索（设备名称/IP地址）")

    # 独立筛选参数（用于下拉菜单）
    device_group: str | None = Field(default=None, description="设备分组筛选")
    auth_type: str | None = Field(default=None, description="认证方式筛选")
    device_status: str | None = Field(default=None, description="设备状态筛选")
    vendor: str | None = Field(default=None, description="厂商筛选")


class BackupDeviceRequest(BaseModel):
    """单设备备份请求。"""

    backup_type: BackupType = Field(default=BackupType.MANUAL, description="备份类型")
    otp_code: str | None = Field(default=None, min_length=6, max_length=8, description="OTP 验证码（手动输入模式可选）")


class BackupBatchRequest(BaseModel):
    """批量备份请求。"""

    device_ids: list[UUID] = Field(..., min_length=1, max_length=500, description="设备ID列表")
    backup_type: BackupType = Field(default=BackupType.MANUAL, description="备份类型")

    # 断点续传参数
    resume_task_id: str | None = Field(default=None, description="断点续传任务ID")
    skip_device_ids: list[UUID] | None = Field(default=None, description="跳过已成功的设备ID")


class BackupBatchByGroupRequest(BaseModel):
    """按设备分组批量备份请求。"""

    dept_id: UUID = Field(..., description="部门ID")
    device_group: DeviceGroup = Field(..., description="设备分组")
    backup_type: BackupType = Field(default=BackupType.MANUAL, description="备份类型")

    # OTP 验证码（手动输入模式）
    otp_code: str | None = Field(default=None, min_length=6, max_length=8, description="OTP 验证码")


class OTPNotice(BaseModel):
    """OTP 提示信息（用于前端独立处理）。"""

    type: str = Field(default="otp_required", description="提示类型")
    message: str = Field(default="需要重新输入 OTP 验证码", description="提示消息")
    dept_id: UUID | None = Field(default=None, description="需要 OTP 的部门ID")
    device_group: str | None = Field(default=None, description="需要 OTP 的设备分组")
    pending_device_ids: list[UUID] | None = Field(default=None, description="待继续处理的设备ID列表")
    task_id: str | None = Field(default=None, description="批量任务ID")
    otp_wait_status: str | None = Field(default=None, description="等待状态 waiting/timeout")
    otp_wait_timeout: int | None = Field(default=None, description="等待 OTP 超时时间（秒）")
    otp_cache_ttl: int | None = Field(default=None, description="OTP 缓存有效期（秒）")


class BackupTaskStatus(BaseModel):
    """备份任务状态响应。"""

    task_id: str = Field(..., description="任务ID")
    status: str = Field(..., description="任务状态 (pending/running/success/failed)")
    progress: dict | None = Field(default=None, description="进度信息")

    # 进度数值（用于前端进度条）
    completed: int | None = Field(default=None, description="已完成设备数")
    total: int | None = Field(default=None, description="总设备数（用于进度条）")
    percent: int | None = Field(default=None, description="完成百分比 (0-100)")

    # 结果摘要（任务完成时）
    total_devices: int | None = Field(default=None, description="总设备数")
    success_count: int | None = Field(default=None, description="成功数量")
    failed_count: int | None = Field(default=None, description="失败数量")
    failed_devices: list[dict] | None = Field(default=None, description="失败设备列表")

    otp_notice: OTPNotice | None = Field(
        default=None,
        description="OTP 提示信息（独立结构，前端可优先判断并弹窗处理）",
    )

    # OTP 过期信息（需要用户重新输入）
    otp_required: bool | None = Field(default=None, description="是否需要重新输入 OTP（兼容字段）")
    otp_dept_id: UUID | None = Field(default=None, description="需要 OTP 的部门ID")
    otp_device_group: str | None = Field(default=None, description="需要 OTP 的设备分组")
    pending_device_ids: list[UUID] | None = Field(default=None, description="待继续处理的设备ID列表")


class BackupBatchResult(BaseModel):
    """批量备份结果。"""

    task_id: str = Field(..., description="任务ID")
    total_devices: int = Field(..., description="总设备数")
    success_count: int = Field(..., description="成功数量")
    failed_count: int = Field(..., description="失败数量")
    success_devices: list[UUID] = Field(default_factory=list, description="成功设备ID列表")
    failed_devices: list[dict] = Field(default_factory=list, description="失败设备详情")

    # 断点续传信息
    can_resume: bool = Field(default=False, description="是否可以断点续传")
    pending_device_ids: list[UUID] | None = Field(default=None, description="待处理设备ID列表")


class BackupBatchDeleteRequest(BaseModel):
    """批量删除备份请求。"""

    backup_ids: list[UUID] = Field(..., min_length=1, max_length=500, description="备份ID列表")


class BackupBatchDeleteResult(BaseModel):
    """批量删除备份结果。"""

    success_count: int = Field(..., description="成功删除数量")
    failed_ids: list[UUID] = Field(default_factory=list, description="删除失败的备份ID列表")


class BackupBatchRestoreRequest(BaseModel):
    """批量恢复备份请求。"""

    backup_ids: list[UUID] = Field(..., min_length=1, max_length=500, description="备份ID列表")


class BackupBatchRestoreResult(BaseModel):
    """批量恢复备份结果。"""

    success_count: int = Field(..., description="成功恢复数量")
    failed_ids: list[UUID] = Field(default_factory=list, description="恢复失败的备份ID列表")


class BackupBatchHardDeleteRequest(BaseModel):
    """批量硬删除备份请求。"""

    backup_ids: list[UUID] = Field(..., min_length=1, max_length=500, description="备份ID列表")


# 向后兼容：BackupBatchHardDeleteResult 与 BackupBatchDeleteResult 结构相同
# 保留此别名以兼容现有前端代码
BackupBatchHardDeleteResult = BackupBatchDeleteResult
