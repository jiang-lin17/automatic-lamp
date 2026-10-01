#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""顶层入口：GitHub Actions 执行 `python main.py` 时触发。

所有业务逻辑在 src/ 下；这里只做启动 + 顶层异常处理。
"""

import sys
import traceback

from src.utils import log, close_session


def main() -> int:
    try:
        # lazy import 避免启动时就拉一堆依赖
        from src.main import run
        run()
        log.info("=" * 50)
        log.info("DONE ✅")
        log.info("=" * 50)
        return 0
    except Exception as e:
        log.error("FATAL ERROR: %s", e)
        traceback.print_exc()
        return 1
    finally:
        close_session()


if __name__ == "__main__":
    sys.exit(main())
