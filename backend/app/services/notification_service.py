"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: notification_service.py
@DateTime: 2026-01-10 03:50:00
@Docs: 告警通知服务 (Notification Service).

说明：
- Webhook：可配置启用，支持通用 HTTP POST。
- 邮件：仅提供配置项，默认不启用；即使配置也不会发送，除非显式开启 ALERT_EMAIL_ENABLED。
"""

import json
from email.message import EmailMessage

import httpx

from app.core.config import settings
from app.core.logger import logger
from app.models.alert import Alert


class NotificationService:
    """告警通知服务。"""

    async def send_webhook(self, alert: Alert) -> None:
        """发送 Webhook 通知（按配置决定是否启用）。"""
        if not settings.ALERT_WEBHOOK_ENABLED:
            return

        url = (settings.ALERT_WEBHOOK_URL or "").strip()
        if not url:
            logger.warning("Webhook 已启用但未配置 ALERT_WEBHOOK_URL，已跳过发送")
            return

        payload = {
            "id": str(alert.id),
            "type": alert.alert_type,
            "severity": alert.severity,
            "status": alert.status,
            "title": alert.title,
            "message": alert.message,
            "details": alert.details,
            "source": alert.source,
            "related_device_id": str(alert.related_device_id) if alert.related_device_id else None,
            "related_discovery_id": str(alert.related_discovery_id) if alert.related_discovery_id else None,
            "created_at": alert.created_at.isoformat() if alert.created_at else None,
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, json=payload)
                if resp.status_code >= 400:
                    logger.warning(
                        "Webhook 发送失败",
                        status_code=resp.status_code,
                        response_text=resp.text[:500],
                    )
        except Exception as e:
            logger.warning("Webhook 发送异常", error=str(e))

    async def send_email(self, alert: Alert) -> None:
        """
        发送邮件通知（默认禁用）。

        注意：你当前没有邮件服务器，因此我们仅支持配置但不启用；
        只有当 ALERT_EMAIL_ENABLED=true 时才会实际发送。
        """
        if not settings.ALERT_EMAIL_ENABLED:
            return

        host = (settings.ALERT_EMAIL_HOST or "").strip()
        if not host:
            logger.warning("邮件通知已启用但未配置 ALERT_EMAIL_HOST，已跳过发送")
            return

        # 使用标准库 SMTP 发送（同步），放到线程里避免阻塞事件循环
        msg = EmailMessage()
        msg["Subject"] = f"[NCM告警] {alert.title}"
        msg["From"] = settings.ALERT_EMAIL_FROM or settings.ALERT_EMAIL_USER
        msg["To"] = settings.ALERT_EMAIL_TO
        msg.set_content(
            json.dumps(
                {
                    "id": str(alert.id),
                    "type": alert.alert_type,
                    "severity": alert.severity,
                    "title": alert.title,
                    "message": alert.message,
                    "details": alert.details,
                },
                ensure_ascii=False,
                indent=2,
            )
        )

        import asyncio
        import smtplib

        def _send_sync() -> None:
            with smtplib.SMTP(host=host, port=settings.ALERT_EMAIL_PORT, timeout=10) as server:
                if settings.ALERT_EMAIL_USER:
                    server.login(settings.ALERT_EMAIL_USER, settings.ALERT_EMAIL_PASSWORD)
                server.send_message(msg)

        try:
            await asyncio.to_thread(_send_sync)
        except Exception as e:
            logger.warning("邮件发送异常", error=str(e))

