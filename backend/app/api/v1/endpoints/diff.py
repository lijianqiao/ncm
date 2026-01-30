"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: diff.py
@DateTime: 2026-01-10 04:10:00
@Docs: 配置差异 API 接口 (Diff API).
"""

from uuid import UUID

from fastapi import APIRouter, Depends

from app.api import deps
from app.core.permissions import PermissionCode
from app.schemas.common import ResponseBase
from app.schemas.diff import DiffResponse

router = APIRouter(tags=["配置差异"])


@router.get(
    "/device/{device_id}/latest",
    response_model=ResponseBase[DiffResponse],
    summary="获取设备最新配置差异",
)
async def get_device_latest_diff(
    device_id: UUID,
    diff_service: deps.DiffServiceDep,
    current_user: deps.CurrentUser,
    _: deps.User = Depends(deps.require_permissions([PermissionCode.DIFF_VIEW.value])),
) -> ResponseBase[DiffResponse]:
    """计算并获取指定设备最新两个备份版本之间的配置差异。

    该接口会自动寻找最新的成功备份及其前一个版本进行 Diff 计算。

    Args:
        device_id (UUID): 设备 ID。
        diff_service (DiffService): 差异计算服务依赖。
        current_user (User): 当前登录用户。

    Returns:
        ResponseBase[DiffResponse]: 包含 Unified Diff 格式文本及版本 MD5 的响应。
    """
    new_bak, old_bak = await diff_service.get_latest_pair(device_id)
    if not new_bak:
        return ResponseBase(data=DiffResponse(device_id=device_id, message="暂无备份记录，无法生成差异"))
    if not old_bak:
        return ResponseBase(
            data=DiffResponse(
                device_id=device_id,
                device_name=getattr(getattr(new_bak, "device", None), "name", None),
                new_backup_id=new_bak.id,
                new_hash=new_bak.md5_hash,
                new_md5=new_bak.md5_hash,
                has_changes=False,
                message="仅有一份成功备份，暂无可对比的上一版本",
            )
        )

    if not old_bak.content or not new_bak.content:
        return ResponseBase(
            data=DiffResponse(
                device_id=device_id,
                device_name=getattr(getattr(new_bak, "device", None), "name", None),
                old_backup_id=old_bak.id,
                new_backup_id=new_bak.id,
                old_hash=old_bak.md5_hash,
                new_hash=new_bak.md5_hash,
                old_md5=old_bak.md5_hash,
                new_md5=new_bak.md5_hash,
                has_changes=False,
                message="备份内容未直存数据库（可能为大配置/MinIO 未集成），暂不支持差异计算",
            )
        )

    diff_text = diff_service.compute_unified_diff(old_bak.content, new_bak.content, context_lines=3)
    has_changes = bool(diff_text.strip())
    return ResponseBase(
        data=DiffResponse(
            device_id=device_id,
            device_name=getattr(getattr(new_bak, "device", None), "name", None),
            old_backup_id=old_bak.id,
            new_backup_id=new_bak.id,
            old_hash=old_bak.md5_hash,
            new_hash=new_bak.md5_hash,
            diff_content=diff_text,
            has_changes=has_changes,
            old_md5=old_bak.md5_hash,
            new_md5=new_bak.md5_hash,
            diff=diff_text,
        )
    )
