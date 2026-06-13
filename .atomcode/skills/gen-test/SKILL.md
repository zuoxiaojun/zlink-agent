---
name: gen-test
description: 根据 tests/ 目录中的已有测试模式，为新模块生成 pytest 测试文件
version: 1.0.0
agent_rules: []
invoke:
  disable_model_invocation: true
  user_invocable: true
---

# 生成测试文件

## 用法
输入模块路径，根据现有 `tests/` 目录中的测试风格生成测试文件。

## 生成规范
- 使用 `tests/conftest.py` 中的 fixtures
- 遵循项目已有的测试结构（参考 `test_agent_loop.py`、`test_extensions.py` 等）
- 使用 pytest + pytest-asyncio（对 async 函数）
- 覆盖率目标 > 80%
