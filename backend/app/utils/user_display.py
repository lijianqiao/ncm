"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: user_display.py
@DateTime: 2026-01-12
@Docs: 用户展示名格式化工具。
"""


def format_user_display_name(nickname: str | None, username: str | None) -> str | None:
    nick = (nickname or "").strip()
    user = (username or "").strip()
    if nick and user:
        return f"{nick}({user})"
    return nick or user or None
