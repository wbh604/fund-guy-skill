# 主动基金经理取证 · v0.2.0 测试版

这是与根目录的 Fund Guy Skill 并列的另一套实现。原版围绕历史买卖行为做审计；这个版本从一个基金份额、一个研究日期开始，结合经理任期、披露持仓和四席评审给出结论。两版使用各自的入口，互不依赖。

## 从哪里开始

在本目录打开终端。报告入口需要 Python 3.10+；安装器与打包命令需要 Python 3.11+。以下命令只建本地档案，不联网，不会直接给买卖结论。将代码和日期换成你要研究的份额和截面。

```sh
python3 run.py 000019 --init --as-of 2025-01-27
```

接下来按[输入和取数说明](skills/fund-manager-forensics/references/run-case.md)核验身份、记录证据并完成评审，再运行 `python3 run.py 000019 --mode deep`。输出在本机的 `cases/`，打开对应的 `report.html` 即可。未完成评审时，命令会告诉你缺什么。

## 安装和验证

- [WorkBuddy 安装包](dist/fund-manager-forensics-0.2.0-workbuddy.zip)：下载 ZIP 后在 WorkBuddy 的技能面板导入。
- [各平台入口](docs/PLATFORMS.md)：先用 `python3 scripts/install_skill.py --platform all --dry-run` 看安装位置。平台配置已提供，未逐个客户端验收。
- [Agent 工作规则](skills/fund-manager-forensics/SKILL.md) · [设计总纲](DESIGN.md)

```sh
python3 -m unittest discover -s tests -q
python3 scripts/install_skill.py --platform workbuddy --install
```

公开测试使用合成材料；实名报告、经理照片、原始持仓和研究缓存不随包分发。历史持仓变化来自定期披露，不能当作真实成交回单。仅供研究。
