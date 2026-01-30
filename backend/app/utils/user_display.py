"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: user_display.py
@DateTime: 2026-01-12
@Docs: 用户展示名格式化工具。
"""


def format_user_display_name(nickname: str | None, username: str | None) -> str | None:
    """格式化用户显示名称。

    优先使用昵称，格式为 "昵称(用户名)"。如果只有昵称或用户名，则返回对应的值。

    Args:
        nickname: 用户昵称
        username: 用户名

    Returns:
        str | None: 格式化后的显示名称，两者都为空时返回 None
    """
    nick = (nickname or "").strip()
    user = (username or "").strip()
    if nick and user:
        return f"{nick}({user})"
    return nick or user or None
