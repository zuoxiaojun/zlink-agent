# Contributing to YS-Agent

感谢你考虑为 YS-Agent 贡献代码！

## 开发环境

```bash
# 克隆仓库
git clone https://gitee.com/leftxiaojun/ys-agent.git
cd ys-agent

# Python 虚拟环境
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt

# 安装 pre-commit hook
pre-commit install

# 前端
cd web
npm ci
cd ..
```

## 代码规范

- **Python**：使用 [ruff](https://docs.astral.sh/ruff/) 进行 lint 和格式化
  - 配置见 `pyproject.toml`
  - 手动检查：`ruff check . && ruff format --check .`
  - 自动修复：`ruff check --fix . && ruff format .`
- **TypeScript/Vue**：使用 eslint
  - `cd web && npm run lint`

## 提交流程

1. 确保 pre-commit hook 已安装（`pre-commit install`）
2. 提交前自动运行：ruff lint + format、尾空格检查等
3. 运行测试确保全部通过：`python -m pytest tests/ -v`
4. 提交信息用中文，简要描述改动内容

## 测试

```bash
# 跑全部测试
python -m pytest tests/ -v

# 跑单个文件
python -m pytest tests/test_extensions.py -v

# 带覆盖率
python -m pytest tests/ --cov=agent --cov=backend --cov-report=term-missing
```

覆盖率目标：≥ 70%。

## PR 指南

- PR 标题简要说明改动
- 描述中说明改动原因和测试情况
- 确保 CI 全部通过后再请求 review

## 报告 Issue

请在 [Gitee Issues](https://gitee.com/leftxiaojun/ys-agent/issues) 提交，包含：
- Python / Node.js 版本
- 复现步骤
- 期望行为 vs 实际行为
