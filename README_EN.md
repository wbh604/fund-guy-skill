<div align="center">

# Fund Guy Skill · 基佬skill

*"The platform rates him 84. We audited every single trade he made — and gave him 62."*

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://python.org)
[![Agent Skill](https://img.shields.io/badge/Agent-Skill-blueviolet)]()
[![Data](https://img.shields.io/badge/Data-Free%20%26%20Zero%20API%20Key-brightgreen)]()
[![Modules](https://img.shields.io/badge/Report%20Modules-12-orange)]()

A deep behavioral audit engine for fund managers · **We grade behavior, not NAV**

[Live Demo](https://wbh604.github.io/fund-guy-skill/assets/fund-163417.html) · [What Is This](#what-is-this) · [Install](#install) · [Report Tour](#-what-the-report-looks-like) · [Quick Start](#quick-start) · [Hard Rules](#methodology-hard-rules) · [Data Sources](#data-sources)

[中文](README.md) | **English**

</div>

---

## Acknowledgements

Learn AI at L站!
Thanks to the [Linux.do](https://linux.do/) community for their support.

## What Is This

One sentence: give it a mutual fund code, and the Agent digs up every trade the manager made over 8 years, back-tests each entry and exit against what actually happened in the following 12 months, then produces a 700KB self-contained interactive report — animated K-line battle replays, trade autopsies, an independence trial, and a fame-machine background check.

**Live demo**: Xingquan Heyi (163417) → [open it](https://wbh604.github.io/fund-guy-skill/assets/fund-163417.html) (self-contained HTML, works offline; the demo masks the manager's name and photo)

## Why This Exists

99% of fund buyers look at exactly two things: the NAV curve and the platform rating. But —

- A rising NAV ≠ a skilled manager. It may be pure style beta (large-cap growth printed money in 2020 no matter who ran it)
- Platform ratings score returns and years of service. **Nobody checks whether his sells were actually right**
- "Holdings differ from the firm's" gets marketed as independence, but nobody verifies whether he **made money when he disagreed**
- If copying his quarterly disclosures gets you nearly the same return, what is his first-mover edge actually worth?

This skill answers all of that with public data. Every conclusion is reproducible and sourced; anything unverifiable is labeled "unverified" — numbers are never invented.

---

## Install

### OpenClaw (easiest)

Send this to your agent and it sets itself up:

```bash
git clone https://github.com/wbh604/fund-guy-skill.git ~/.openclaw/skills/fund-guy-skill && pip install -r ~/.openclaw/skills/fund-guy-skill/requirements.txt
```

Then just say:

> Use `skills/fund-manager-alpha/SKILL.md` in fund-guy-skill to analyze fund 163417. Reference scripts are under `scripts/`.

### Claude Code (Plugin)

```bash
/plugin marketplace add wbh604/fund-guy-skill
/plugin install fund-manager-alpha@fund-guy-skill
```

You get three slash commands: `/analyze-fund 163417` (full audit), `/quick-check 163417` (5-minute triage), `/find-similar 163417` (holdings collision lookup).

### Claude Code (Skill)

```bash
git clone https://github.com/wbh604/fund-guy-skill.git && pip install -r fund-guy-skill/requirements.txt
```

Open the fund-guy-skill directory in Claude Code — skills under `skills/` are auto-discovered.

### Codex

Drop this on Codex:

> Clone https://github.com/wbh604/fund-guy-skill , run `pip install -r requirements.txt`, then run `python run.py 163417 --no-browser` to analyze the fund. Give me the report path when done.

### Cursor

Clone and open the repo folder in Cursor — the project skill under `.cursor/skills/` is auto-discovered; just say "analyze fund 163417". Or drop this in:

> Clone https://github.com/wbh604/fund-guy-skill , install deps with `pip install -r requirements.txt`, then read `skills/fund-manager-alpha/SKILL.md` and analyze fund 163417 following its workflow. Reference scripts are under `scripts/`.

### Windsurf / Devin / other agents

The repo root ships `AGENTS.md` (a universal agent guide) and `.agents/skills/` (Codex project skill), which most agents pick up on open; if yours doesn't, drop in the paragraph above.

### Plain CLI

```bash
git clone https://github.com/wbh604/fund-guy-skill.git
cd fund-guy-skill && pip install -r requirements.txt
python run.py 163417
```

---

## 📸 What the Report Looks Like

> All screenshots below come from the real analysis of Xingquan Heyi (163417), light theme.

### The Verdict · Subject + Behavior Score

Total 62 = timing 35% + control 35% + alpha quality 30%, every point rule-based and recomputable. The stamp says it plainly: "Wait."

<img src="docs/screenshots/shot-hero.png" width="760" />

### Platform Rating Face-off · 84 vs 62

The platform gives him 84, we give 62 — the 22-point gap is mostly one thing: the platform never checked *when he sells*.

<img src="docs/screenshots/shot-platform.png" width="760" />

### Battle Replay · Real Weekly K-lines + Every Trade

Left: his biggest winners / losers / sold-too-early list. Right: real K-lines with every trade marked — green dots for buys, red for active sells, yellow for forced trims (10% cap / redemptions), plus cost and exit lines. Hit "Replay" and the chart grows week by week while that year's news and his moves replay frame by frame.

<img src="docs/screenshots/shot-replay.png" width="760" />

### Trade Autopsy · 65 Buys + 16 Full Exits, All Tested

Every action is tested against the following 12 months: buy win rate 58% (beating the index counts as a win), exit dodge rate only 31%. One-line verdict: **great buyer, bad seller.**

<img src="docs/screenshots/shot-autopsy.png" width="760" />

### Best and Worst Calls

Montage Technology: +227% in the 12 months after he added. Sanan Optoelectronics: +119% after he exited (sold way too early). Wins and losses are both on the table — cherry-picking winners would kill the report's credibility.

<img src="docs/screenshots/shot-bestworst.png" width="760" />

### What He Does Underwater + Bear Market Defense

32 actions taken while a position was below his cost: 20 cut-losses vs 12 buy-the-dips — disciplined, doesn't ride losers into the ground. Next to it: his defense record across four bear years.

<img src="docs/screenshots/shot-loss.png" width="760" />

### The Independence War · How Different Is He From His Firm

Divergence gauge: him 78.8%, roughly the same as the average gap between colleagues — not a lone wolf. The step that matters: in his most-divergent quarters vs least-divergent quarters, who beat the index over the following 6 months?

<img src="docs/screenshots/shot-indep.png" width="760" />

### His Current Hand · Top-10 Holdings by Industry

Chips & AI compute at 23.3% is the clear main line, innovative pharma 10% plays support — a classic tech-growth book that will swing with the semiconductor cycle.

<img src="docs/screenshots/shot-theme.png" width="760" />

### Holdings Collision Board · Same Firm + Whole Market

Which sibling funds look most like his, and which active funds market-wide also hold his heavyweights — all with overlap progress bars. Want any of them dissected? Just ask the Agent to run the pipeline again.

<img src="docs/screenshots/shot-crash.png" width="760" />

### This Year's Top 10 Funds · Holdings Sync Rate

This year's ten hottest funds overlap with him on just 0.8 of 10 heavyweights on average — his returns were not made by chasing this year's leaderboard.

<img src="docs/screenshots/shot-top10.png" width="760" />

### Copycat Index · His Entry vs You Waiting for Disclosures

Copy him after each quarterly disclosure and you still keep 80% of the alpha — his first-mover edge is worth about 4.4 points a year, which cross-checks his weak timing score.

<img src="docs/screenshots/shot-copy.png" width="760" />

### The Disaster Movie · How You Would Have Lost Money

Drag the slider to pick an amount and see exactly what your money would have become had you bought at the February 2021 peak — and how many days until breakeven.

<img src="docs/screenshots/shot-disaster.png" width="760" />

### Institutional View · Up/Down Capture

The numbers institutional allocators care about most, annotated in plain language.

<img src="docs/screenshots/shot-capture.png" width="760" />

### Luck Decomposition · How Much of the Return Was Free Style Beta

Regress 103 months of returns against market / size / growth-value factors. What survives: +7.7% a year — that part is real skill.

<img src="docs/screenshots/shot-factor.png" width="760" />

### Fame-Machine Check · Star Manager Background Scan

Dumping losers on juniors / cherry-picking track records / burying dead funds / peak-time cash grabs — checked item by item. Unverifiable items are marked "unverified", never "doesn't exist".

<img src="docs/screenshots/shot-star.png" width="760" />

---

## 🎨 Three Report Styles

Beyond the main report above, three complete style prototypes share the same methodology with totally different narrative skins (currently mock-data demos, usable as alternative render templates):

### Style A · Detective Dossier — "TOP SECRET"

Kraft paper, red stamps, investigator margin notes. The manager is treated as a suspect: personnel file, exhibits, closing statement. [View live](https://wbh604.github.io/fund-guy-skill/assets/style-a-dossier.html)

<img src="docs/screenshots/style-a.png" width="760" />

### Style B · Gacha Card — "You Pulled an SSR"

Card-game language: rarity, stat panel, match history, death replays, tier-list debates. [View live](https://wbh604.github.io/fund-guy-skill/assets/style-b-card.html)

<img src="docs/screenshots/style-b.png" width="760" />

### Style C · Health Checkup — "Mostly Healthy, But Flares Up in Cold Weather"

Clinic language: general conclusion, lab results, medical history, Rx with dosage control. [View live](https://wbh604.github.io/fund-guy-skill/assets/style-c-checkup.html)

<img src="docs/screenshots/style-c.png" width="760" />

---

## Quick Start

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

# Example: Xingquan Heyi 163417 — fetch → analyze → build report
.venv/bin/python scripts/fetch_fund.py 163417           # core fund data (NAV/holdings/manager/holders)
.venv/bin/python scripts/fetch_stock_klines.py 163417   # weekly K-lines of heavyweights (baostock + Sina)
.venv/bin/python scripts/fetch_pingzhong.py 163417      # Eastmoney pingzhongdata (flows/platform rating/photo)
.venv/bin/python scripts/fetch_house.py 163417          # sibling fund holdings (independence control group)
.venv/bin/python scripts/fetch_market_similar.py 163417 # market-wide collision board reverse lookup
.venv/bin/python scripts/fetch_top_funds.py 163417      # YTD top-10 funds sync rate
.venv/bin/python scripts/analyze_fund.py 163417         # behavior analysis: autopsy/scoring/forced-trim detection
.venv/bin/python scripts/analyze_house.py 163417        # divergence / market consensus
.venv/bin/python scripts/build_fund_report.py 163417    # build single-file report assets/fund-<code>.html
```

### Using It in Cursor / Claude Code / Codex

Drop the repo on your Agent and say:

> Read `skills/fund-manager-alpha/SKILL.md` and analyze fund 163417 following its workflow. Reference scripts are under `scripts/`.

The scripts are a **reference implementation from one real run**. APIs change; when analyzing another fund or another environment, follow the three-tier data acquisition model in `skills/fund-manager-alpha/SKILL.md` — the Agent fetches data and makes the qualitative calls (announcement reading, industry classification, fame-machine checks) itself. Scripts are references, not the pipeline.

---

## Methodology Hard Rules

All 16 rules live in [`SKILL.md`](skills/fund-manager-alpha/SKILL.md). The most important ones:

1. **Intuition is the supreme principle** — every raw number needs a subject and a definition; regression coefficients belong in small print only
2. **Tenure segmentation comes first** — mixing a predecessor's record into the current manager's evaluation voids the analysis
3. **Never sell Beta as Alpha** — style freebies must be stripped before crediting skill
4. **"Sold too early" only counts full active exits** — partial trims keep most of the position; forced trims (10% cap / redemptions) are not decisions and are excluded
5. **Every failed independent call must be recorded** — cherry-picking winners kills the report's credibility
6. **No fake precision** — if it can't be computed, write "not obtained"; never invent numbers
7. **Insufficient evidence gets a U (Unverified)** — treating "couldn't verify" as "bad manager" is friendly fire

Every design decision is documented in [`DESIGN.md`](DESIGN.md).

## Data Sources

All free, zero API keys:

| Data | Source |
|---|---|
| NAV / AUM / subscriptions & redemptions / holders / manager profile / platform rating | Eastmoney (fund.eastmoney.com) |
| Quarterly holdings / fund rankings | Eastmoney, via akshare |
| Market-wide holdings cross-section | CNINFO, via akshare |
| A-share weekly K-lines (forward-adjusted) | baostock |
| HK weekly K-lines | Sina Finance, via akshare |
| Charting library | TradingView Lightweight Charts (Apache-2.0) |

All raw data is cached under `.cache/` for evidence (not committed), with API name + parameters and fetch time recorded; no number enters the report without a traceable source. The report itself ends with a full data attribution table.

## Disclaimer

> ⚠️ For learning and research only. Everything is based on publicly disclosed data and **does not constitute investment advice**. Past fund performance does not predict future results; each verdict is valid only until the next holdings disclosure.
