"""
@Author: li
@Email: li
@FileName: snmp_credential.py
@DateTime: 2026-01-14
@Docs: SNMP 凭据 Schema 定义（按部门维度）。
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DeptSnmpCredentialCreate(BaseModel):
    dept_id: UUID = Field(..., description="部门ID")
    snmp_version: str = Field(default="v2c", description="SNMP 版本(v2c/v3)")
    port: int = Field(default=161, ge=1, le=65535, description="SNMP 端口")

    community: str | None = Field(default=None, description="SNMP 团体字串（明文，存储时加密）")

    v3_username: str | None = Field(default=None, description="SNMPv3 用户名")
    v3_auth_key: str | None = Field(default=None, description="SNMPv3 Auth Key（明文，加密存储）")
    v3_priv_key: str | None = Field(default=None, description="SNMPv3 Priv Key（明文，加密存储）")
    v3_auth_proto: str | None = Field(default=None, description="SNMPv3 Auth 协议")
    v3_priv_proto: str | None = Field(default=None, description="SNMPv3 Priv 协议")
    v3_security_level: str | None = Field(default=None, description="SNMPv3 安全级别")

    description: str | None = Field(default=None, max_length=200, description="描述")


class DeptSnmpCredentialUpdate(BaseModel):
    snmp_version: str | None = Field(default=None, description="SNMP 版本(v2c/v3)")
    port: int | None = Field(default=None, ge=1, le=65535, description="SNMP 端口")

    community: str | None = Field(default=None, description="SNMP 团体字串（明文，存储时加密）")

    v3_username: str | None = Field(default=None, description="SNMPv3 用户名")
    v3_auth_key: str | None = Field(default=None, description="SNMPv3 Auth Key（明文，加密存储）")
    v3_priv_key: str | None = Field(default=None, description="SNMPv3 Priv Key（明文，加密存储）")
    v3_auth_proto: str | None = Field(default=None, description="SNMPv3 Auth 协议")
    v3_priv_proto: str | None = Field(default=None, description="SNMPv3 Priv 协议")
    v3_security_level: str | None = Field(default=None, description="SNMPv3 安全级别")

    description: str | None = Field(default=None, max_length=200, description="描述")


class DeptSnmpCredentialResponse(BaseModel):
    id: UUID = Field(..., description="记录ID")
    dept_id: UUID = Field(..., description="部门ID")
    dept_name: str | None = Field(default=None, description="部门名称")

    snmp_version: str = Field(..., description="SNMP 版本")
    port: int = Field(..., description="SNMP 端口")

    has_community: bool = Field(..., description="是否配置了团体字串")
    description: str | None = Field(default=None, description="描述")

    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime | None = Field(default=None, description="更新时间")

    model_config = ConfigDict(from_attributes=True)


class SnmpCredentialBatchRequest(BaseModel):
    """SNMP 凭据批量操作请求。"""

    ids: list[UUID] = Field(..., min_length=1, description="SNMP 凭据ID列表")


class SnmpCredentialBatchResult(BaseModel):
    """SNMP 凭据批量操作结果。"""

    success_count: int = Field(..., description="成功数量")
    failed_count: int = Field(..., description="失败数量")
    failed_ids: list[UUID] = Field(default_factory=list, description="失败的ID列表")
