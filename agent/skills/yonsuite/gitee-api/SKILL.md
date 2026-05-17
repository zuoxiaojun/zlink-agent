---
name: gitee-api
description: Gitee（码云）开放 API 操作技能。仓库增删查改、文件读写、用户信息、企业组织等操作，以及将本地 Hermes Skill 同步到 Gitee 仓库的完整流程。触发：Gitee、码云、仓库管理、创建仓库、上传文件到Gitee、将技能同步到Gitee、上传skill到Gitee、技能备份Gitee、push skill to gitee、上传文件夹到Gitee、Gitee批量上传、文件夹同步到Gitee、从Gitee安装skill、Gitee克隆skill、下载安装skill、gitee。
trigger: Gitee / 码云 / 仓库管理 / 创建仓库 / 上传文件到Gitee / 将技能同步到Gitee / 上传skill到Gitee / 技能备份Gitee / push skill to gitee / 上传文件夹到Gitee / Gitee批量上传 / 文件夹同步到Gitee / 从Gitee安装skill / Gitee克隆skill / 下载安装skill / gitee
---

# Gitee API Skill

## 认证

Gitee 使用私人令牌认证，需先在 Gitee 个人设置 → 私人令牌 创建，勾选所需权限。

```bash
# 环境变量方式（推荐）
export GITEE_TOKEN="your_private_token"

# 或直接在请求URL带token参数
curl "https://gitee.com/api/v5/user?access_token=YOUR_TOKEN"
```

## 基础信息

| 项目 | 内容 |
|------|------|
| 基础 URL | `https://gitee.com/api/v5` |
| 认证方式 | `access_token` URL参数 或 `Authorization: Bearer` Header |
| API 文档 | https://gitee.com/api/v5/swagger |
| Scope | repo（仓库）、user（用户）、project（项目）等 |

## 用户信息

```bash
# 获取当前用户信息
curl "https://gitee.com/api/v5/user?access_token=$GITEE_TOKEN"

# 获取指定用户信息
curl "https://gitee.com/api/v5/users/{username}?access_token=$GITEE_TOKEN"
```

## 仓库操作

### 列出当前用户的仓库

```bash
curl "https://gitee.com/api/v5/user/repos?access_token=$GITEE_TOKEN&sort=updated&per_page=20"
```

### 获取仓库详情

```bash
# 公共仓库
curl "https://gitee.com/api/v5/repos/{owner}/{repo}"

# 当前用户私有仓库（需认证）
curl "https://gitee.com/api/v5/repos/{owner}/{repo}?access_token=$GITEE_TOKEN"
```

### 创建仓库

```bash
curl -X POST "https://gitee.com/api/v5/user/repos?access_token=$GITEE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my-repo",
    "description": "仓库描述",
    "private": false,
    "auto_init": true
  }'
```

### 上传/更新文件（核心：POST 创建，PUT 更新）

**Gitee 关键规则**：
- 新建文件 → `POST`（不带 sha）
- 更新已有文件 → `PUT`（必须带 sha）
- 对不存在的文件用 PUT → 报错 `400 {"messages":["sha is missing","sha is empty"]}`

```bash
# 1. 判断文件是否存在（GET 返回类型：文件=dict，目录=list）
curl -s "https://gitee.com/api/v5/repos/{owner}/{repo}/contents/{path}?ref=master&access_token=$GITEE_TOKEN"

# 2a. 创建新文件 → POST（不带 sha）
curl -X POST "https://gitee.com/api/v5/repos/{owner}/{repo}/contents/{path}?access_token=$GITEE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "添加文件",
    "content": "'"$(base64 -i file.txt | tr -d '\n')"'",
    "branch": "master"
  }'

# 2b. 更新已有文件 → PUT（必须带 sha）
SHA=$(curl -s "https://gitee.com/api/v5/repos/{owner}/{repo}/contents/{path}?ref=master&access_token=$GITEE_TOKEN" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['sha'])")
curl -X PUT "https://gitee.com/api/v5/repos/{owner}/{repo}/contents/{path}?access_token=$GITEE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "更新文件",
    "content": "'"$(base64 -i file.txt | tr -d '\n')"'",
    "sha": "'"$SHA"'",
    "branch": "master"
  }'
```

> 注意：content 必须为 Base64 编码后的字符串。

### 删除仓库

```bash
curl -X DELETE "https://gitee.com/api/v5/repos/{owner}/{repo}?access_token=$GITEE_TOKEN"
```

### 获取仓库目录列表

```bash
# 注意：Gitee 默认分支通常是 master，不是 main
curl "https://gitee.com/api/v5/repos/{owner}/{repo}/contents/?access_token=$GITEE_TOKEN&ref=master"
```

**关键发现**：国内 Gitee 仓库默认分支通常是 `master` 而非 `main`，必须显式指定 `?ref=master` 才能正确获取内容，否则返回空。公共仓库无需 token 也能直接请求。

### 下载文件内容

文件下载时响应 `content` 字段是 **Base64 编码**的字符串，需要解码后才能得到真实内容：

```bash
curl -s "https://gitee.com/api/v5/repos/{owner}/{repo}/contents/{path}?ref=master" \
  | python3 -c "
import sys,json,base64
d=json.load(sys.stdin)
content=d.get('content','')
with open('/local/path','w') as f:
    f.write(base64.b64decode(content).decode('utf-8'))
print('done')
"
```

### 获取文件内容

```bash
curl "https://gitee.com/api/v5/repos/{owner}/{repo}/contents/{path}?access_token=$GITEE_TOKEN"
```

## 文件操作

### 上传创建文件

```bash
curl -X POST "https://gitee.com/api/v5/repos/{owner}/{repo}/contents/{path}?access_token=$GITEE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "提交说明",
    "content": "'"$(base64 -i file.txt | tr -d '\n')"'",
    "branch": "main"
  }'
```

> 注意：Gitee API 要求 content 为 Base64 编码后的字符串。

### 更新文件

```bash
curl -X PUT "https://gitee.com/api/v5/repos/{owner}/{repo}/contents/{path}?access_token=$GITEE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "更新说明",
    "content": "'"$(base64 -i updated.txt | tr -d '\n')"'",
    "sha": "上一版本的sha值",
    "branch": "main"
  }'
```

> 更新文件必须提供上一版本的 `sha`，可通过 GET /repos/{owner}/{repo}/contents/{path} 获取。

### 删除文件

```bash
curl -X DELETE "https://gitee.com/api/v5/repos/{owner}/{repo}/contents/{path}?access_token=$GITEE_TOKEN&sha={file_sha}&message=删除说明&branch=main"
```

## 组织与企业

```bash
# 列出当前用户所属组织
curl "https://gitee.com/api/v5/user/orgs?access_token=$GITEE_TOKEN"

# 列出组织的仓库
curl "https://gitee.com/api/v5/orgs/{org}/repos?access_token=$GITEE_TOKEN"
```

## 常用仓库权限级别

| 权限 | 说明 |
|------|------|
| `public` | 公开仓库，任何人可读 |
| `private` | 私有仓库，仅自己和协作者可读 |
| `internal` | 内部仓库，企业/组织内可见 |

## Token 失效排查（重要）

**症状：** Gitee API 返回 `401 Unauthorized: Access token does not exist` 或 `401 Unauthorized: Access token is wrong type`

**原因：** 私人令牌过期、被撤销、或格式不正确

**验证方法：**
```bash
# 用 Bearer Header 方式验证（推荐）
curl -s -H "Authorization: Bearer $GITEE_TOKEN" \
  "https://gitee.com/api/v5/user"

# 或 URL 参数方式
curl -s "https://gitee.com/api/v5/user?access_token=$GITEE_TOKEN"
```

**两个常见 token 存放位置（均需检查）：**
1. `~/.hermes/config.yaml` 的 `gitee.headers.Authorization`（格式：`Bearer xxx`）
2. 环境变量 `GITEE_TOKEN`

两个 token 可能都失效，需要重新生成。

**重新生成令牌：**
https://gitee.com → 右上角头像 → 设置 → 私人令牌 → 生成新令牌（需勾选 `repo` 权限）

---

## 备选方案：Git 直接推送（当 API 不可用时）

若 Gitee API token 失效，但本地已完成初始化，可用 git push 手动推送：

```bash
cd ~/.hermes/skills/{skill-name}

# 1. 初始化（如尚未 git init）
git init
git config user.email "zuoxiaojun@hermes.local"
git config user.name "左小军"

# 2. 添加远程仓库（假设已创建空仓库）
git remote add origin https://gitee.com/{owner}/{repo}.git

# 3. 忽略敏感文件（.env 等已在 .gitignore 中）
# 确认 .gitignore 包含：.env, __pycache__/, *.pyc, .venv/, output/

# 4. 提交
git add .
git commit -m "chore: initial commit"

# 5. 推送（需要仓库创建权限，通常 token 失效时只能手动在网页创建仓库后再 push）
git push -u origin master
```

**注意：** API token 失效时，无法通过 API 创建仓库，需先在 Gitee 网页上手动创建空仓库，再 git push。

---

## 常见错误处理
| code | 说明 | 处理方式 |
|------|------|---------|
| 400 | sha missing/empty | 新文件应用 POST 而不是 PUT |
| 401 "does not exist" | Token 不存在或已过期 | 重新生成私人令牌 |
| 401 "wrong type" | Token 类型错误（OAuth vs 私人令牌） | 使用私人令牌格式，非 OAuth |
| 403 | 权限不足 | 确认 Token 已勾选对应 Scope（如 repo） |
| 404 | 仓库或文件不存在 | 检查 owner/repo/path 是否正确 |
| 422 | 文件已存在（sha 冲突） | 创建新文件时不要传 sha，更新时才需要 |
## 与 GitHub API 的主要区别

| 对比项 | Gitee | GitHub |
|--------|-------|--------|
| 认证 | URL参数 `access_token` | Header `Authorization: Bearer` |
| 文件上传 | 需 Base64 编码 content | 原生支持，支持大文件 |
| 创建文件 | POST（不带 sha） | POST |
| 更新文件 | PUT（必须带 sha） | PUT |
| 400 错误 | sha missing → 用 POST 创建 | 通常不会混淆 |
| Scope | repo/user/org 等 | repo/user/org 等 |
| API 文档 | https://gitee.com/api/v5/swagger | https://docs.github.com/rest |

---

# 场景：将本地 Hermes Skill 同步到 Gitee

## 完整流程

### 1. 确认 token 有效

```bash
curl -s -H "Authorization: Bearer YOUR_TOKEN" https://gitee.com/api/v5/user
# 期望返回用户 JSON，若 401 则 token 无效
```

### 2. 创建 Gitee 仓库

⚠️ **注意**：`public: true` 会报错 `"public is invalid"`。正确写法是 `private: false`：

```bash
curl -s -X POST \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"repo-name","description":"描述","private":false}' \
  "https://gitee.com/api/v5/user/repos"
```

返回 `html_url` 即创建成功。

### 3. 初始化本地 git（若尚未 git init）

```bash
cd ~/.hermes/skills/YOUR_SKILL
git init
git config user.email "zuoxiaojun@hermes.local"
git config user.name "leftxiaojun"
```

### 4. 配置 remote 并 push

```bash
git remote add origin https://gitee.com/USERNAME/REPO.git
# ⚠️ 不要把 token 嵌入 URL（terminal prompt 会阻塞）
GIT_TERMINAL_PROMPT=0 git push -u origin main
```

## 常见错误

| 错误 | 原因 | 解决 |
|------|------|------|
| `public is invalid` | Gitee API 不接受 `public` 字段 | 改用 `private: false` |
| `could not read Password` | token 嵌入 URL 触发 credential prompt | 去掉 URL 中的 token，用 `GIT_TERMINAL_PROMPT=0` |
| `401 Unauthorized` | token 过期或类型错误 | 重新生成 Gitee 私人令牌 |
| `Not Found Project` (API查询) | 仓库未创建或查询时未带 token | 带 token 重查 |

## ⚠️ 仓库最终可能是 private

即使传 `private: false`，Gitee API 有时仍会创建为 private 仓库。若需 public 访问，需手动在 Gitee 页面仓库设置中修改。

## Token 安全存储（三处都要更新）

**token 变更后需同时更新以下三处，否则不同调用路径会用到过期 token：**

1. **macOS Keychain**（用于 git 交互式认证，如果用过 git push）
   ```bash
   security find-internet-password -s gitee.com  # 查找是否存着旧 token
   security delete-internet-password -s gitee.com # 删除旧记录
   security add-generic-password -s "gitee-token" -a "USERNAME" -w "NEW_TOKEN"
   ```

2. **环境变量 `GITEE_TOKEN`**（API 调用和脚本用这个，最重要）
   ```bash
   export GITEE_TOKEN="NEW_TOKEN"
   # 持久化到 ~/.hermes/.env
   echo "GITEE_TOKEN=NEW_TOKEN" >> ~/.hermes/.env
   ```

3. **~/.hermes/config.yaml**（gitee MCP 用，如果配置了）
   ```yaml
   # 找到 gitee MCP 配置，Bearer token 替换
   Authorization: Bearer NEW_TOKEN
   ```

验证三处一致：
```bash
grep "GITEE_TOKEN" ~/.hermes/.env
grep "Authorization.*Bearer" ~/.hermes/config.yaml
```

## 推送前排除文件

```bash
# 排除敏感文件和大文件
git add .gitignore SKILL.md *.py modules/ assets/ docs/ examples/ output/.gitkeep tests/
# 不要 add：.env cache/ __pycache__/ .venv/ *.json（业务数据）
```

---

# 场景：本地文件夹批量上传到 Gitee

## 适用场景

将本地文件夹（如 skill 目录）完整同步到 Gitee 仓库，保持目录结构。

## 核心逻辑

Gitee API 没有"上传整个文件夹"的接口，需要遍历本地文件、逐文件 base64 编码后 POST 上传。

## 完整流程

### 第一步：确认 Token

```bash
# 推荐从环境变量读取
echo $GITEE_TOKEN
# 或从 ~/.hermes/.env 读取
grep GITEE_TOKEN ~/.hermes/.env
```

### 第二步：确认本地文件夹路径

```bash
find ~/.hermes/skills/<skill-name> -type f | sort
```

### 第三步：编写上传脚本

```python
import subprocess, base64, json, os

token = "your_token"  # 从环境变量 GITEE_TOKEN 读取
owner = "leftxiaojun"
repo = "leftSkill"
local_dir = "/path/to/local/folder"
remote_base = "skill-name"  # 远程目录名

def get_sha(path):
    url = f"https://gitee.com/api/v5/repos/{owner}/{repo}/contents/{path}?access_token={token}&ref=master"
    r = subprocess.run(["curl", "-s", url], capture_output=True, text=True)
    try:
        data = json.loads(r.stdout)
        return data.get("sha")
    except:
        return None

def put_file(path, content):
    b64 = base64.b64encode(content.encode()).decode()
    url = f"https://gitee.com/api/v5/repos/{owner}/{repo}/contents/{path}?access_token={token}"
    payload = {"message": f"上传 {path}", "content": b64, "branch": "master"}
    r = subprocess.run(
        ["curl", "-s", "-X", "POST", url, "-H", "Content-Type: application/json",
         "-d", json.dumps(payload)],
        capture_output=True, text=True)
    resp = json.loads(r.stdout)
    return resp.get("commit", {}).get("sha", resp.get("message", "error"))[:20]

# 遍历本地文件夹，构造远程路径
for root, dirs, files in os.walk(local_dir):
    for filename in files:
        local_path = os.path.join(root, filename)
        rel_path = os.path.relpath(local_path, local_dir)
        remote_path = f"{remote_base}/{rel_path}"
        content = open(local_path).read()
        print(f"上传 {rel_path} -> {remote_path}")
        print(put_file(remote_path, content))
```

### 第四步：确认结构

```python
def list_dir(path):
    url = f"https://gitee.com/api/v5/repos/{owner}/{repo}/contents/{path}?access_token={token}&ref=master"
    r = subprocess.run(["curl", "-s", url], capture_output=True, text=True)
    return json.loads(r.stdout)
```

## 关键注意事项

1. **Gitee 不存在真实目录**，目录只是文件路径的前缀，POST 新路径后目录自动创建
2. **文件已存在时**：Gitee 返回 `sha is missing` 错误，需先 GET 获取 sha 再 PUT 更新
3. **删除旧路径**：移动文件时必须先 PUT 新路径，确认成功后再 DELETE 旧路径
4. **Base64 编码**：所有文件内容必须 base64 编码后通过 JSON 传递
5. **默认分支 master**：Gitee 仓库默认分支通常是 `master`，不是 `main`

## 常见错误处理

| 错误信息 | 原因 | 处理 |
|---------|------|------|
| `sha is missing` | 文件已存在 | 改用 PUT 并提供 sha 参数 |
| `sha is empty` | sha 参数为空 | 先 GET 获取 sha 再传 |
| `404` | 文件/目录不存在 | 检查路径是否正确 |
| `401` | Token 无效 | 确认 GITEE_TOKEN 正确 |

---

# 场景：从 Gitee 仓库下载安装 Hermes Skill

## 适用场景

从 Gitee 分享或备份的技能仓库安装到本地 ~/.hermes/skills/ 目录。

## 核心发现

- Gitee API 浏览仓库内容：`GET https://gitee.com/api/v5/repos/{owner}/{repo}/contents/{path}?ref={branch}`
- **注意**：Gitee 仓库默认分支通常是 `master`，不是 `main`，必须加 `?ref=master`
- 响应中 `content` 字段是 Base64 编码，需要解码后写入文件
- 公共仓库无需 token，直接请求即可

## 完整流程

### 1. 确认仓库结构和文件

```bash
# 查看仓库根目录
curl -s "https://gitee.com/api/v5/repos/{owner}/{repo}/contents/?ref=master" \
  | python3 -c "import sys,json; [print(f\"{d['type']}: {d['path']}\") for d in json.load(sys.stdin)]"

# 查看子目录
curl -s "https://gitee.com/api/v5/repos/{owner}/{repo}/contents/{skill-dir}?ref=master" \
  | python3 -c "import sys,json; [print(f\"{d['type']}: {d['path']}\") for d in json.load(sys.stdin)]"
```

### 2. 创建本地目录并下载文件

```bash
mkdir -p ~/.hermes/skills/{skill-name}/references

# 下载 SKILL.md（多文件同理）
curl -s "https://gitee.com/api/v5/repos/{owner}/{repo}/contents/{skill-dir}/SKILL.md?ref=master" \
  | python3 -c "
import sys,json,base64
d=json.load(sys.stdin)
content=d.get('content','')
with open('/Users/zuoxiaojun/.hermes/skills/{skill-name}/SKILL.md','w') as f:
    f.write(base64.b64decode(content).decode('utf-8'))
print('SKILL.md done')
"
```

### 3. 验证安装

```bash
hermes skills list | grep {skill-name}
```

## 示例：从 leftxiaojun/leftSkill 安装 yonyou-pptx

```bash
# 1. 确认目录结构
curl -s "https://gitee.com/api/v5/repos/leftxiaojun/leftSkill/contents/yonyou-pptx?ref=master"
# 返回：dir: references, file: SKILL.md

# 2. 创建目录
mkdir -p ~/.hermes/skills/yonyou-pptx/references

# 3. 下载 SKILL.md
curl -s "https://gitee.com/api/v5/repos/leftxiaojun/leftSkill/contents/yonyou-pptx/SKILL.md?ref=master" \
  | python3 -c "
import sys,json,base64
d=json.load(sys.stdin)
with open('/Users/zuoxiaojun/.hermes/skills/yonyou-pptx/SKILL.md','w') as f:
    f.write(base64.b64decode(d['content']).decode('utf-8'))
print('SKILL.md done')
"

# 4. 下载 references 文件（如果有）
curl -s "https://gitee.com/api/v5/repos/leftxiaojun/leftSkill/contents/yonyou-pptx/references?ref=master" \
  | python3 -c "import sys,json; [print(d['path']) for d in json.load(sys.stdin)]"
# → file: yonyou-pptx/references/yonyou-design.md

# 5. 验证
hermes skills list | grep yonyou-pptx
```

## 常见问题

| 问题 | 原因 | 解决 |
|------|------|------|
| 返回空 | 默认分支是 `master` 不是 `main` | 加 `?ref=master` |
| Base64 解码后是乱字 | 内容被截断或编码错误 | 确认 content 字段完整 |
| hermes 看不到 | 需要重启或重新加载 skills | `hermes skills list` 重试 |

---

## 踩坑记录：git push 失败时用 API 直接上传

### 问题背景

当 git credential 缓存了过期 token 时，`git push` 会报：
```
fatal: could not read Password for 'https://gitee.com': terminal prompts disabled
```
即使设置了 `GIT_TERMINAL_PROMPT=0`、去掉了 URL 中的 token、或清空了 credential helper，macOS Keychain 仍会拦截弹窗，导致 push 完全无法进行。

### 解决方案：Gitee API 直接上传（绕过 git）

#### 第一步：确认默认分支

```bash
# 确认仓库的实际默认分支（可能是 main/master/maintain 等）
curl -s "https://gitee.com/api/v5/repos/{owner}/{repo}?access_token=$GITEE_TOKEN" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('default_branch:', d.get('default_branch'))"
```

#### 第二步：Python 脚本逐文件上传

```python
import subprocess, base64, json

TOKEN = "your_token"          # 从环境变量 GITEE_TOKEN 读取
OWNER = "your_username"
REPO = "your_repo"
BRANCH = "main"                # 第一步确认的分支名
LOCAL_DIR = "/path/to/local/repo"

def get_sha(path):
    """获取远程文件的当前 sha，必须加 ref=branch"""
    url = f"https://gitee.com/api/v5/repos/{OWNER}/{REPO}/contents/{path}?ref={BRANCH}&access_token={TOKEN}"
    r = subprocess.run(["curl", "-s", url], capture_output=True, text=True)
    d = json.loads(r.stdout)
    return d.get("sha") if isinstance(d, dict) and d.get("sha") else None

def put_file(path, content, sha=None):
    """上传/更新文件，sha=None 时用 POST 创建，sha 有值时用 PUT 更新"""
    b64 = base64.b64encode(content.encode("utf-8")).decode("ascii")
    data = {
        "message": "update: 文件更新",
        "content": b64,
        "branch": BRANCH,
    }
    if sha:
        data["sha"] = sha
    method = "PUT" if sha else "POST"
    url = f"https://gitee.com/api/v5/repos/{OWNER}/{REPO}/contents/{path}?access_token={TOKEN}"
    cmd = ["curl", "-s", "-X", method, url, "-H", "Content-Type: application/json", "-d", json.dumps(data)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return json.loads(r.stdout)

# 遍历本地文件，逐个上传
for local_path, remote_path in [
    (f"{LOCAL_DIR}/SKILL.md", "SKILL.md"),
    (f"{LOCAL_DIR}/models.py", "models.py"),
]:
    content = open(local_path).read()
    sha = get_sha(remote_path)          # 每次上传前重新 GET sha
    print(f"{'UPDATE' if sha else 'CREATE'} {remote_path}")
    result = put_file(remote_path, content, sha)
    commit = result.get("commit", {})
    print(f"  → {commit.get('sha', result.get('message', ''))}")
```

#### 三个关键坑点

1. **`ref` 必须加在 GET sha 的 URL 上**：不带 `?ref=main` 时，Gitee 认为你没有指定分支，sha 返回 null，POST 上传会报错 `只允许在分支上创建或更新文件`

2. **`sha` 每次 PUT 前都要重新获取**（最重要）：
   - Gitee 的 sha 会随 commit 变化，如果两次 PUT 之间有其他操作（其他客户端、网页编辑等），sha 会失效
   - 报错 `Blob SHA does not match` → 解决：立即重新 GET sha 再 PUT，通常能成功（其他并发写入已落盘）
   - 报错 `文件名已存在` 但 sha=None → 说明 `ref` 没加，GET 没有命中分支，需要补上 `?ref={branch}`

3. **分支名要实测确认**：不同仓库默认分支可能不同（`main`/`master`/`maintain`），必须通过 API 确认：
   ```bash
   curl -s "https://gitee.com/api/v5/repos/{owner}/{repo}?access_token=$TOKEN" \
     | python3 -c "import sys,json; d=json.load(sys.stdin); print('default:', d.get('default_branch'))"
   ```
   常见仓库默认分支：`main`（新创建）、`master`（旧仓库）、`maintain`（部分维护仓库）

#### 典型操作序列（Python 示例）

```python
import subprocess, base64, json

TOKEN = "your_token"      # 从环境变量 GITEE_TOKEN
OWNER = "username"
REPO = "repo"
BRANCH = "main"           # 先用上面的 API 确认

def get_sha(path):
    url = f"https://gitee.com/api/v5/repos/{OWNER}/{REPO}/contents/{path}?ref={BRANCH}&access_token={TOKEN}"
    r = subprocess.run(["curl", "-s", url], capture_output=True, text=True)
    d = json.loads(r.stdout)
    return d.get("sha") if isinstance(d, dict) and d.get("sha") else None

def put_file(path, content, sha=None):
    b64 = base64.b64encode(content.encode("utf-8")).decode("ascii")
    data = {"message": "update", "content": b64, "branch": BRANCH}
    if sha:
        data["sha"] = sha
    method = "PUT" if sha else "POST"
    url = f"https://gitee.com/api/v5/repos/{OWNER}/{REPO}/contents/{path}?access_token={TOKEN}"
    cmd = ["curl", "-s", "-X", method, url, "-H", "Content-Type: application/json", "-d", json.dumps(data)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return json.loads(r.stdout)

# 更新已有文件
for local_path, remote_path in [(LOCAL_DIR, REMOTE_PATH), ...]:
    content = open(local_path).read()
    sha = get_sha(remote_path)
    result = put_file(remote_path, content, sha)
    if "Blob SHA does not match" in str(result):
        sha = get_sha(remote_path)   # 重试
        result = put_file(remote_path, content, sha)
    print(result.get("commit", {}).get("sha", result.get("message", "")))
```

#### git push 的 credential 拦截根因

macOS 自带 `osxkeychain` credential helper，git push 时会优先调用 Keychain 弹出交互式密码框，设置了 `GIT_TERMINAL_PROMPT=0` 也无法阻止。这个设计保证了安全，但 token 过期后即使更新了 Keychain 里的密码，旧的 cached credential 仍会阻止 push，此时用 API 绕过是最可靠的方式。
