"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: start.py
@DateTime: 2025-12-30 13:00:00
@Docs: 应用程序启动脚本.
"""

import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
