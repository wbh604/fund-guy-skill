# 平台适配

## 单一真源

业务规则只在：

`skills/fund-manager-forensics/`

平台 manifest、`AGENTS.md`、`CLAUDE.md`、`GEMINI.md` 和安装器只负责发现。禁止在平台目录复制研究规则。

查看安全计划：

```bash
python3 scripts/install_skill.py --list-platforms
python3 scripts/install_skill.py --platform all --dry-run
```

真正安装需显式加 `--install`。已存在的目标不会被覆盖。

## 支持矩阵

| 平台 | 项目入口 | 用户级入口 / 安装方式 | 验证 |
|---|---|---|---|
| Codex | `.codex-plugin/plugin.json` + `skills/` + `agents/openai.yaml` | `~/.agents/skills/fund-manager-forensics` | 在可用 Skills 中查找或显式调用 `$fund-manager-forensics` |
| Claude Code | `.claude-plugin/plugin.json` + `skills/` | `~/.claude/skills/fund-manager-forensics` | `claude plugin validate .` 或检查 Skills 列表 |
| Cursor | `.cursor-plugin/plugin.json` + `skills/` | `~/.cursor/skills/fund-manager-forensics`；安装器默认复用开放目录 `~/.agents/skills` | Slash 菜单或 Settings → Skills |
| Gemini CLI | `gemini-extension.json` + `GEMINI.md` + `skills/` | `~/.gemini/skills/fund-manager-forensics`，也可 `gemini extensions link .` | `/skills` 与 `/extensions list` |
| Hermes | canonical `SKILL.md` | `~/.hermes/skills/fund-manager-forensics` | `hermes skills list`，再用自然语言触发 |
| OpenClaw | `openclaw.plugin.json` 或 Codex-compatible bundle | `~/.openclaw/skills`；安装器默认复用 `~/.agents/skills` | `openclaw skills list` / `check` / `info` |
| OpenCode | canonical `SKILL.md` | `~/.agents/skills/fund-manager-forensics`；项目也可 `.opencode/skills` | 启动后检查 Skill 列表 |
| WorkBuddy | 本地 Skill 发布包 | “技能 → 添加技能 → 上传本地技能包” | 对比包内 `PACKAGE-MANIFEST.json` 的版本与 SHA-256 |
| CodeBuddy | canonical `SKILL.md` | `~/.codebuddy/skills/fund-manager-forensics`；项目可 `.codebuddy/skills` | `/skills` 或 Skills 面板 |

## WorkBuddy 快照例外

WorkBuddy 的公开流程是上传本地 Skill 包，不是持续读取仓库目录，因此它客观上是一个发布快照。构建：

```bash
python3 scripts/install_skill.py --platform workbuddy --install
```

产物在 `dist/`，包含 `PACKAGE-MANIFEST.json`。它记录版本、canonical 根和每个文件的 SHA-256。更新时重新构建和上传，不手改平台内副本。

## CodeBuddy 项目模式

CodeBuddy 支持项目 `.codebuddy/skills/<name>/SKILL.md`。为了避免仓库内出现第二份规则，不提交复制品；需要项目模式时运行：

```bash
python3 scripts/install_skill.py \
  --platform generic \
  --target "$PWD/.codebuddy/skills/fund-manager-forensics" \
  --install
```

默认 `link` 到 canonical Skill。Windows 无符号链接权限时显式 `--mode copy`，并用 WorkBuddy 同样的 SHA-256 方式核对更新。

## 防漂移

1. 只改 `skills/fund-manager-forensics/`。
2. 本地平台优先符号链接，不复制。
3. 托管平台发布包保留版本与 SHA-256。
4. CI/本地运行 `tests/test_platform_contract.py`，检查 manifest 身份、版本、入口和唯一 `SKILL.md`。
5. 不在平台指令文件粘贴 Agent 工作流；它们只指向 canonical Skill。

## 官方依据

- Codex 使用开放 Agent Skills，并支持仓库/用户级 `.agents/skills` 与插件 bundle。
- Claude Code 插件使用 `.claude-plugin/plugin.json`，组件目录位于插件根。
- Cursor 2.4+ 识别 `SKILL.md`，项目原生目录为 `.cursor/skills`，并支持开放目录。
- Gemini Extension 根使用 `gemini-extension.json`，可打包 `skills/`。
- Hermes 从 `~/.hermes/skills` 发现包含 `SKILL.md` 的目录。
- OpenClaw 可读 workspace、`.agents/skills`、用户 Skills，也能识别 Codex/Claude/Cursor bundle。
- WorkBuddy 支持上传本地技能包；第三方 Skill 安装前应核对权限和代码。
