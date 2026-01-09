"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: rate_limiter.py
@DateTime: 2025-12-30 16:15:00
@Docs: 请求频率限制器配置 (Rate Limiter Configuration using slowapi).
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

# 创建限流器实例，使用客户端 IP 作为标识
limiter = Limiter(key_func=get_remote_address)
