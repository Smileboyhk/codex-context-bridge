# Codex Context Bridge

**把 Codex 本地开发现场，稳定地交给 ChatGPT 网页版继续理解和判断。**

Codex Context Bridge（CCB）是一个零第三方 Python 运行时依赖的小工具。它不会把整个仓库自动上传给任何模型，而是在项目本地生成一份**证据型项目快照**：项目状态、Git 版本、自动测试、最新截图/PNG/HTML/指标、目录结构，以及可选的精确源码包。

它特别适合这种工作流：

```text
Codex 开发 / 调试
      ↓
ccb snapshot
      ↓
.ai-context/
      ↓
Google Drive / GitHub / 手动上传
      ↓
ChatGPT 网页版
      ↓
产品判断 / 技术审查 / 下一步 Codex 指令
```

## 为什么不是单纯把 README 或源码丢给 ChatGPT？

因为“代码写了”不等于“功能真的可用”。CCB 会把项目证据拆成四层：

1. **Runtime / visual artifacts**：实际 PNG、截图、HTML、指标等运行结果。
2. **Automated checks**：测试、构建、lint、评估脚本的真实结果。
3. **Git evidence**：分支、HEAD、未提交改动、diff stat、最近提交。
4. **Project documents**：`STATE.md`、`DECISIONS.md`、`AGENTS.md` 等人的声明和设计意图。

生成的 `CHATGPT_ENTRY.md` 会明确要求 ChatGPT：当这些证据互相冲突时，优先相信更强的证据；缺证据时必须标记为“未验证”，不能因为 Codex 写了一句 done 就判断成功。

## 适合你的典型场景

例如 PUBG 运营路线生产图工具：

- `STATE.md`：Route V2-A 做到哪一步；
- Git：本轮到底改了哪些模块；
- Tests：身份追踪/轨迹融合测试是否通过；
- Artifacts：最新路线 PNG、debug 截图、metrics JSON；
- ChatGPT：判断“实际效果是否比上一个阶段更好”，并给出下一步 Codex 指令。

## 快速开始

要求 Python 3.11+。

```powershell
git clone https://github.com/Smileboyhk/codex-context-bridge.git
cd codex-context-bridge
python -m pip install -e .

# 如果在离线/内网环境已经有 setuptools，可使用：
python -m pip install -e . --no-build-isolation
```

进入任何 Codex 项目：

```powershell
cd D:\work\your-project
ccb init
```

它会加入：

```text
.ccb.toml
STATE.md
DECISIONS.md
```

编辑 `.ccb.toml`，尤其是项目目标、检查命令和实际产物路径。

然后生成快照：

```powershell
ccb snapshot --run-checks
```

需要把少量关键源码一起交给 ChatGPT 时：

```powershell
ccb snapshot --run-checks --include-source
```

输出：

```text
.ai-context/
├─ CHATGPT_ENTRY.md       # 网页 ChatGPT 第一入口
├─ PROJECT_SNAPSHOT.md    # 状态 + Git + 项目文档
├─ PROJECT_SNAPSHOT.json  # 机器可读版本
├─ CHECKS.md              # 自动测试/构建结果
├─ ARTIFACTS.md           # 最新实际输出清单
├─ SOURCE_INDEX.md        # 目录结构与文件统计
├─ SOURCE_PACK.md         # 仅在 --include-source 时生成
├─ MANIFEST.json          # 快照文件 hash
├─ artifacts/             # 复制后的最新 PNG/HTML/JSON 等
└─ history/               # 最近若干次 snapshot JSON
```

## Google Drive 同步

CCB 不依赖 Google API。最简单稳定的方式，是让 Google Drive for Desktop 先把一个本地目录同步到云端。

例如：

```toml
[sync]
target = "G:/My Drive/AI Context"
```

然后：

```powershell
ccb snapshot --run-checks --sync
```

CCB 只会复制 `.ai-context` 的内容到：

```text
G:/My Drive/AI Context/<project-name>/
```

网页 ChatGPT 只需要读取这个专门的 AI Context 目录，不需要访问整个工作盘。

## `.ccb.toml` 示例

```toml
[project]
name = "PUBG RouteMap"
objective = "从比赛录像自动生成航线、圈型与 16 支队伍运营路线 PNG"
phase = "Route V2 tracklet fusion"
status = "research"

[bridge]
output_dir = ".ai-context"
max_tree_entries = 1500
ignore = ["*.log", "tmp/**"]

[documents]
include = [
  "README.md",
  "AGENTS.md",
  "STATE.md",
  "DECISIONS.md",
  ".planning/2026-09-16-route-v2-tracklet-fusion.md",
]
max_chars_per_file = 30000

[[checks]]
name = "route-v2-tests"
command = "python -m pytest tests/route_v2 -q"
timeout = 300

[[artifacts]]
name = "latest-route-png"
glob = "output/**/*.png"
limit = 3
copy = true

[[artifacts]]
name = "metrics"
glob = "output/**/*metrics*.json"
limit = 3
copy = true

[source_pack]
include = ["research/route_v2/**/*.py", "tests/route_v2/**/*.py"]
max_chars_per_file = 20000
max_total_chars = 180000

[history]
enabled = true
keep = 20

[sync]
target = "G:/My Drive/AI Context"
```

## 建议给 Codex 的固定规则

把 `templates/AGENTS_SNIPPET.md` 的内容追加到每个项目的 `AGENTS.md`。核心规则是：

- 重要阶段结束必须更新 `STATE.md`；
- “Implemented”和“Verified”必须分开写；
- 运行真实验证命令；
- 保留最新实际产物；
- 最后运行 `ccb snapshot --run-checks --sync`；
- 不允许把失败测试写成成功，也不允许用文档声明覆盖实际结果。

## 给 ChatGPT 网页版怎么说

最简单：

> 读取这个项目最新的 `CHATGPT_ENTRY.md` 以及它引用的 snapshot 文件。把状态分成 declared / implemented / verified / observed runtime result。告诉我本轮真正改变了什么、还有什么没验证、最关键 blocker 是什么，以及下一步应该让 Codex 做什么。不要因为代码存在就推断功能成功。

## 安全边界

CCB 默认：

- 拒绝读取 `.env`、私钥、常见 credentials 文件；
- 对常见 token / API key 字符串做基本脱敏；
- 不会主动联网；
- 不会执行扫描到的业务代码；
- 只有在你显式使用 `--run-checks` 时才运行 `.ccb.toml` 里写明的检查命令；
- 只有在 `--include-source` 时才打包配置中明确允许的源码 glob；
- 只同步 CCB 自己生成的 `.ai-context`，而不是整个项目目录。

这不是专业 DLP/secret scanner。首次将任何私有项目快照上传到云端前，仍建议人工检查一次 `.ai-context`。

## 与 AI Context Linker / Repomix 的关系

CCB 是独立实现，并不复制二者代码。设计上吸收了两个非常有价值的方向：

- AI Context Linker：通过受控项目资料生成 AI 可读上下文，而不是盲目上传整个代码库；
- Repomix：必要时才把选定源码整理成适合 LLM 阅读的代码包。

CCB 更关注 **Codex → ChatGPT 的开发交接**，尤其强化测试证据和实际视觉/运行产物。

## Roadmap

- [x] 本地项目初始化
- [x] Git 状态/提交/diff 采集
- [x] 项目文档受控读取
- [x] 自动测试/构建命令结果
- [x] PNG / HTML / JSON 等最新产物归档
- [x] 可选源码 pack
- [x] Google Drive Desktop 本地目录同步
- [x] 历史 snapshot
- [ ] snapshot diff（直接生成“本轮变化”）
- [ ] 多项目 dashboard
- [ ] GitHub Actions artifact ingestion
- [ ] 更完整 secret scanner
- [ ] 一条命令生成 Codex 下一轮 handoff prompt

## License

MIT
