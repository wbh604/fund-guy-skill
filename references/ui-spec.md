# 报告界面规范

设计语言参考 UZI-Skill 已验证的做法:**零图表库、纯 CSS 可视化、结论先给、巨型数字、野兽派金句。**

核心目标两个:**一眼看懂** + **值得截图转发**。

## 1. 设计系统 · 黑白双主题

两套主题都必须好看,不是深色做完顺手加个浅色。

```css
:root{                              /* 深色 · 默认 */
  --bg:#080a0d; --surface:#11151b; --raised:#171d25; --sunk:rgba(0,0,0,.4);
  --ink:#f2f5f8; --muted:#8b95a3; --ghost:#5a6472;
  --line:#1e242d; --line-hard:#2c343f;
  --accent:#c8ff2e;  --accent-ink:#0a0d10;  --indep:#a78bfa;
  --ok:#34d399; --danger:#f87171; --warn:#fbbf24;
  --brutal:var(--accent);              /* 野兽派投影色 */
  --grid-ink:rgba(255,255,255,.028);   /* 背景网格 */
  --radius:16px; --shadow-brutal:5px 5px 0 var(--brutal); --gap:20px;
}
[data-theme="light"]{
  --bg:#eef1f5; --surface:#fff; --raised:#f6f8fa; --sunk:rgba(15,23,42,.07);
  --ink:#0d1420; --muted:#4a5568; --ghost:#94a3b8;
  --line:#dfe5ec; --line-hard:#0d1420;
  --accent:#3f6212;  --accent-ink:#fff;  --indep:#6d28d9;   /* 压深保对比度 */
  --ok:#047857; --danger:#be123c; --warn:#b45309;
  --brutal:#0d1420;                    /* 浅色下投影用黑 */
  --grid-ink:rgba(13,20,32,.035);
}
```

三个关键点:

**荧光绿在浅色下必须换掉。** `#c8ff2e` 在白底上对比度只有 1.6:1,直接看不见。浅色主题压成 `#3f6212` 深橄榄绿,同一个语义位置换值,组件代码不用改。

**野兽派投影色抽成 `--brutal`。** 深色下用荧光绿,浅色下用黑 —— 都是"实心不透明投影"这个语气,但底色不同选择不同。

**`background-color` 不要写成 `background`。** `background` 简写会重置 `background-image`,叠了网格纹理后主题切换会失效:

```css
body{
  background-color: var(--bg);       /* ✅ */
  background-image: linear-gradient(var(--grid-ink) 1px, transparent 1px),
                    linear-gradient(90deg, var(--grid-ink) 1px, transparent 1px);
  background-size: 44px 44px;
}
```

44px 网格纹理很淡但很关键 —— 它让页面看起来像个工具,不像 Word 文档。

**禁止硬编码颜色。** 唯一例外是两张分享卡:它们永远深色(发出去要辨识度),所以 `#share-card` / `#war-report` 内部写死色值,不跟主题变。

### 主题切换

右上角固定一个圆按钮,`localStorage` 记住选择,hover 转 -18°:

```js
const paint = t => { root.dataset.theme = t; btn.textContent = t==='dark'?'🌙':'☀️'; };
paint(localStorage.getItem('fmTheme') || 'dark');
```

### 字号层级

| 用途 | 尺寸 | 字重 |
|---|---:|---:|
| 巨型分数 | 160px | 900 |
| 经理名 | 72px | 900 |
| 模块大数 | 48px | 800 |
| section-title | 32px | 800 |
| 金句 | 26px | 700 |
| 正文 | 15px | 400 |
| label | 11px | 600 + `letter-spacing:.25em` + uppercase |

### 卡片

```css
.card {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 28px;
}
```

section 分隔用 `.section-head`:编号标签(`05 / INDEPENDENCE`)+ 标题 + 1px 渐隐线(`linear-gradient(90deg, var(--accent), transparent)`)。

## 2. 导航

单页滚动 + 左侧固定锚点轨:

```css
.toc-rail { position: fixed; left: 16px; top: 50%;
            transform: translateY(-50%); z-index: 50; }
html { scroll-behavior: smooth; scroll-padding-top: 72px; }
```

六个锚点,当前段高亮 `--accent`。窄屏(<960px)折叠为顶部横向 chip 条。

## 3. 六个 Tab

| # | Tab | 用户真正想知道什么 | 核心内容 |
|---|---|---|---|
| 01 | **判决书** | 到底行不行 | 四重判决、分数区间、证据等级、最大本事、最大硬伤 |
| 02 | **这个人** | 他是什么类型的经理 | 职业路径、行为 DNA、嘴手一致、主驾度、司机负荷 |
| 03 | **独立战争** | 他跟别人不一样时有没有本事 | 公司门派图、双分数、战役(四象限)、先手、跟随嫌疑 |
| 04 | **拆穿运气** | 业绩到底是不是风口 | Alpha 尸检、机器人替身、ETF 三堂会审、拆台实验、成名衰减 |
| 05 | **你会怎么亏** | 买了以后最难受的时候什么样 | 十万元体验、翻车说明书、天气图、底牌、逃生门 |
| 06 | **怎么用** | 适合拿来干什么 | 产品纯度、底仓/卫星仓、持有期、费率份额、抄作业指数、改判条件 |

六个名字都没有金融术语 —— 用户顺着看完完成一次自然决策:行不行 → 为什么 → 是不是独立能力 → 是不是运气 → 我会怎么亏 → 最后该怎么用。

**Independence(独立战争)必须是独立 Tab,不能塞进 Manager 当小节。** 它是产品的差异化所在。

## 4. 首屏(结论先给)

三卡网格 `grid-template-columns: 2fr 1fr 1fr`:

```
┌──────────────────────────┬─────────┬─────────┐
│ 缪玮彬                    │   78    │  🟢     │
│ 金元顺安元启 004685        │  /100   │ 可以买   │
│                           │         │         │
│ Macro Allocator /         │   A-    │ 建议仓位 │
│ Diversified Small-Cap     │         │ 卫星仓   │
│                           │ 证据 🟢  │ ≤5%     │
│ [单人管理8年+]             │  High   │         │
│ [经理本人>100万份]         │         │         │
│ [低抱团][主动限购]         │         │         │
│ [Key Person Risk 高]      │         │         │
└──────────────────────────┴─────────┴─────────┘
```

### 巨型分数动画

```js
// 0 → target,1400ms,ease-out-cubic
const ease = t => 1 - Math.pow(1 - t, 3);
```

`.score-giant::after { content: '/100'; font-size: .22em; color: var(--muted); }`

### 判词(紧跟首屏)

```css
.punchline {
  background: var(--raised);
  border: 2px solid var(--line);
  border-left: 12px solid var(--accent);
  box-shadow: var(--shadow-brutal);
  padding: 28px 32px;
  font-size: 26px; font-weight: 700; line-height: 1.5;
}
```

判词必须含具体数字。例:

> 缪玮彬的核心能力不是集中选股,而是资产配置与小微盘非共识机会。过去五年 11 次重大非共识配置 7 次跑赢公司组合,分化期 Alpha +7.2% 对一致期 +1.3%。最大约束是策略容量。

**第二屏才是 Manager Profile。不要一上来给净值曲线。**

## 5. Independence Tab 组件(重点)

### 5.1 双分数对照条 —— 最该被记住的一屏

```html
<div class="indep-duo">
  <div class="duo-row">
    <span class="duo-label">Independent Thinking</span>
    <div class="duo-track"><div class="duo-fill" style="--v:88"></div></div>
    <span class="duo-num">88</span>
  </div>
  <div class="duo-row">
    <span class="duo-label">Independent Alpha</span>
    <div class="duo-track"><div class="duo-fill ok" style="--v:91"></div></div>
    <span class="duo-num">91</span>
  </div>
  <p class="duo-verdict ok">独立型 Alpha 经理</p>
</div>
```

```css
.duo-fill { width: calc(var(--v) * 1%); height: 14px;
            background: var(--indep); border-radius: 7px;
            transition: width 1.2s cubic-bezier(.22,1,.36,1); }
.duo-fill.ok     { background: var(--ok); }
.duo-fill.danger { background: var(--danger); }
```

四种判词按 `step5-independent-alpha.md` §7 的矩阵渲染:

| 情形 | 判词 | 颜色 |
|---|---|---|
| 高 + 高 | 独立型 Alpha 经理 | `--ok` |
| 高 + 低 | **有主见,但主见没价值** | `--danger` |
| 低 + 高 | 跟随中的精选者 | `--warn` |
| 低 + 低 | 平台跟随者 | `--muted` |

**两条永不合并成单一"独立性"分数。**

### 5.2 House vs Manager 双向横条

中轴对称,左公司共识、右经理主动权重。分歧 ≥5pp 的行业高亮 `--indep`,并在行末标 `↔ 21.3pp`。

```
       公司共识            行业          经理
  ████████████ 13.2   │  白酒   │  -8.1 ████████      ↔ 21.3pp
      ████████  8.1   │ 食品饮料 │  -4.2 ████         ↔ 12.3pp
         ████   4.8   │  医药   │  +1.3 █
            █   1.2   │ 新能源  │  +9.4 █████████     ↔  8.2pp
                -0.7  │ 半导体  │  +6.8 ███████       ↔  7.5pp
```

顶部两个 chip 切换 AUM 口径 / 经理等权口径。伪共识时(背离 >3pp)显示告警条:
`⚠️ AUM 口径的白酒超配主要由单一大基金贡献,经理等权口径下公司共识没那么极端`

### 5.3 Independent Calls 战役卡

```html
<article class="call-card win">
  <header>
    <span class="call-no">Independent Call #1</span>
    <span class="call-period">2020Q2</span>
    <span class="call-badge win">🟢 高价值独立判断</span>
  </header>
  <div class="call-body">
    <div class="call-side"><span class="lbl">House View</span>
      <p>白酒/消费明显超配</p></div>
    <div class="call-side"><span class="lbl">该经理</span>
      <p>白酒明显低配,新能源明显超配</p></div>
  </div>
  <div class="call-metrics">
    <div><span class="lbl">行业偏离</span><b>87</b></div>
    <div><span class="lbl">经理 12M</span><b class="ok">+56%</b></div>
    <div><span class="lbl">House 12M</span><b>+33%</b></div>
    <div><span class="lbl">Shadow 12M</span><b>+28%</b></div>
    <div class="hero"><span class="lbl">Independent Alpha</span>
      <b class="ok">+23%</b></div>
  </div>
</article>
```

`.call-card.win { border-left: 6px solid var(--ok); }`
`.call-card.loss { border-left: 6px solid var(--danger); }`

**硬规则:成功卡与失败卡的尺寸、字号、篇幅完全一致。** 不许把失败案例做小、折叠或放到页面底部。失败卡与成功卡按时间顺序混排。

`losses == 0` 时渲染一张说明卡,写明扫描范围与检索日志,不许留空。

### 5.4 Hit Rate + 赔率

并排大数,**禁止只显示 Hit Rate**:

```
Contrarian Hit Rate      赔率           期望值
      63.6%              2.34x         +5.9%
   7 胜 / 4 负        +12.4% / -5.3%
```

下方一句判读:`胜率不离谱,但赔率很好。`

### 5.5 Idea Lead 时间轴

横向时间线。经理首次显著超配 = `--accent` 实心大点,公司其他经理陆续跟进 = 灰色小点,点大小按跟进人数。

```
2020Q1 ●━━━━━━━○━━━━━━━━○━━━━━━━━━●
       张三     2人      9人    成为主要方向
       ↑ 领先 House Consensus 约 2-3 个季度
```

多行业叠加展示,右侧汇总 `Average House Lead 2.1 Quarters` + 三档判定徽章。

### 5.6 公司 vs 市场四象限

2×2 矩阵,当前位置打点:

```
                公司相对市场独立
                      ↑
   真正的独立经理  │  个人独立性无法识别
  ─────────────────┼─────────────────→
   在拥挤赛道里     │    双重抱团
   换了个车道       │    (最危险)
                      ↓
                公司相对市场抱团
```

落在"换车道"象限时必须显示告警,避免用户误以为独立 = 避开了市场拥挤。

### 5.7 对战擂台 —— 整个报告最"好玩"的一块

把"他 vs 公司其他人"做成格斗游戏的对战画面。三栏:红方(同事们)/ 中间黑色 VS 块 / 蓝方(这位经理),各带一条血条。

```html
<div class="arena">
  <div class="fighter house">
    <div class="f-who">红方 · 公司里其他人</div>
    <div class="f-name">同事们</div>
    <div class="f-desc">21 位基金经理的平均打法。大家一起重仓消费白酒,
      谁也不想第一个跳车。</div>
    <div class="hp">
      <div class="hp-lbl"><span>他们后来赚了</span><span>+1.3%</span></div>
      <div class="hp-bar"><div class="hp-fill lose" data-w="18"></div></div>
    </div>
  </div>
  <div class="vs"><span class="bolt">⚡</span><span class="t">VS</span></div>
  <div class="fighter mgr">…蓝方,血条 class 用 win…</div>
  <div class="arena-foot">
    <span class="k">判定</span>
    <span>蓝方胜 —— 他不一样的时候,每年比同事多赚 <b class="ok">5.9 个点</b></span>
  </div>
</div>
```

要点:外框 `3px solid var(--line-hard)` 硬边;赢家血条 `--ok` 加发光,输家 `--muted` 不发光;VS 块 `--line-hard` 实心底。

`f-desc` 必须用大白话写清双方在赌什么 —— "同事大概觉得他疯了",不是"该经理行业配置偏离度较高"。这一块的作用就是让完全不懂基金的人也能看懂发生了什么。

### 5.8 公司门派图(独立战争 Tab 核心)

判断"他到底是不是真的独立",先看公司有没有统一观点。公司内部可能本就分裂成多个门派。

```
┌──────────────┬──────────────┐
│ 消费派 8 人     │  科技派 5 人    │
│ 白酒+13% 一致  │  半导体+9% 一致 │
├──────────────┼──────────────┤
│ 均衡派 6 人     │  目标经理 ?     │
│ 分散配置        │  和谁都不像      │
└──────────────┴──────────────┘
```

门派分布(人数 + 核心持仓)、同门共识强度、目标经理属于哪个派(或都不属于)。

判词:
> 他不是跟公司唱反调,而是公司内部本来就有一支科技派。
> 或:公司有三个门派,他和谁都不像,是真正的独立决策者。

**关键区分:** 属于某派 ≠ 独立。只有"公司共识很强 + 他明显偏离"或"他与所有主要派系都不同"才算真独立。

### 5.9 三堂会审(拆穿运气 Tab)

三场对战,判断这份管理费值不值:

| 场次 | 他 vs 谁 | 判断什么 |
|---|---|---|
| 第一堂 | 公司其他人 | 是否具有独立决策能力 |
| 第二堂 | 同类经理 | 是否只是在差公司里显得优秀 |
| 第三堂 | 行业 ETF / 机器人替身 | 这份管理费到底值不值 |

复用对战擂台组件,加第三位选手"行业 ETF(机器人)"。第三堂判词:
> 他的钱主要来自押对了医药,不是医药里选股。直接买医药 ETF,省 1% 管理费。
> 或:他在医药里选股确实比医药 ETF 多赚 2.1%,这笔管理费值。

### 5.10 十万元灾难片(你会怎么亏 Tab)

不要只给最大回撤百分比,翻译成钱:

```
历史投入 10 万元
最差时账面剩 6.74 万元
最长连续亏损 14 个月
最长等待回本 29 个月
```

**金额滑块**:用户输入 5 万 / 10 万 / 50 万,所有数字同步变化。配上"十个人抽签买入":10 个随机买入时点,8 人三年后赚钱,5 人跑赢指数,2 人中途曾亏损超 30%。

### 5.11 Alpha 到手率(拆穿运气 Tab 底部)

"漏水管" —— 历史超额 → 刨掉风口 → 规模损耗 → 费率 → 行为损耗,层层漏:

```
历史主动超额        8.4%   ████████████████
刨掉行业风口        5.9%   ████████████
规模扩大损耗        4.6%   █████████
扣除费率成本        3.1%   ██████
普通持有人行为损耗后  1.7%   ███
```

判词:
> 基金五年赚了 68%,但典型持有人可能只赚了 24%。不是经理没赚钱,而是大部分钱都在涨完以后才进来。

### 5.12 抄作业指数(怎么用 Tab)

两只时钟对比:

| 时钟 | 起点 | 12M 超额 |
|---|---|---|
| 经理自己做 | 建仓时点 | +14% |
| 等季报披露后再跟 | 披露日 | +2% |

> 他有先手,但抄不到。

## 6. 其他 Tab 关键组件

**判决印章** —— 圆形双线边框 + `rotate(-11deg)`,像盖上去的公章。比一行"结论:建议买入"有力得多。

```css
.stamp{width:132px;height:132px;border-radius:50%;border:5px double var(--ok);
  transform:rotate(-11deg);background:var(--ok-tint);color:var(--ok)}
.stamp.no{border-color:var(--danger);color:var(--danger);background:var(--danger-tint)}
```

**半圆仪表** —— inline SVG 两条弧叠加,底弧 `--sunk`、值弧 `--accent`,用 `stroke-dasharray/offset` 做增长动画。放在评分卡下面显示 House Divergence。

**巨型段号水印** —— 每段右上角一个 150px 半透明数字(`02` `03` …),`z-index:0` 压在内容下。纯装饰,但让长页面有节奏感。


**Manager DNA 雷达** — inline SVG 十边形,双层(Career 虚线 / Recent 5Y 实线),同屏对照能直接看出能力衰减。

**Alpha 瀑布** — 纯 CSS 堆叠条。经理能力项(Allocation/Selection/Timing)用 `--accent`,Beta 项用 `--muted`,底部标注加总校验 `17.2% ✓`。

**Alpha Evidence 六检验** — 六个 chip,通过 `--ok` 打勾,未过 `--danger` 打叉。「剔除 Top3 仍为正」这一项字号放大,它是运气与能力的分水岭。

**Decision Lab** — 五个 A-F 等级块 + 一句具体弱点(`卖得偏早,历史卖出后 12M 标的平均继续上涨 14%`)。

**Mistake Ledger** — 时间线卡片,每张含初始逻辑 / 逻辑破坏 / 经理行为序列 / 损失 / 诊断 / Error Correction 等级。

**Capacity 利用率** — 进度条 + 颜色分档:<60% `--ok`,60-85% `--warn`,>85% `--danger`。

**资金徽章** — 8 个徽章,有证据点亮,无证据 `opacity:.25` 灰色。hover 显示证据来源与报告期。**禁止猜测点亮。**

**Career vs Recent 5Y 对照表** — 五行指标双列,Recent 明显差于 Career 时该行标 `--warn` 并加 `↓ 能力衰减` 标签。

**Regime Map** — 2×2 网格,四格底色按该象限历史表现深浅渲染,当前 regime 打点。

## 7. 传播卡片

Playwright 截图隐藏 DOM,`device_scale_factor=2`,截图前 `await page.evaluate("document.fonts.ready")`。

### `#share-card` 1080×1920 竖版

```
┌──────────────────────────┐
│ ── 品牌条(2px accent 下框) │
│                          │
│ 缪玮彬            72px    │
│ 金元顺安元启 · 004685      │
│                          │
│        78 /100           │  ← 巨型
│      🟢 可以买  A-        │
│                          │
│ // 独立决策取证            │  ← 差异化核心
│ House Divergence     83  │
│ Independent Alpha  +4.7% │
│ Contrarian Hit Rate  68% │
│                          │
│ // 五年战绩               │
│ 11 次非共识 · 7 胜 4 负    │
│ 分化期 +7.2% / 一致期 +1.3%│
│                          │
│ ┌ PUNCHLINE ───────────┐ │
│ │ 他最有价值的时候,      │ │
│ │ 恰恰是和公司所有人     │ │
│ │ 都不一样的时候。       │ │
│ └──────────────────────┘ │
│                          │
│ [二维码]   数据截止 XX-XX  │
│ 非个性化投资建议           │
└──────────────────────────┘
```

背景:双 radial-gradient 光晕叠 linear-gradient。小标题统一 `// xxx` 前缀。

**二维码必须本地生成**(`qrcode` 库 → base64 内嵌),不要调 `api.qrserver.com`,离线会拿到空白图。

### `#war-report` 1920×1080 横版

左 60% 信息区(经理名 / 基金 / 三条理由 / 战绩),右 40% `INDEPENDENT ALPHA` 大数字 + 判决印章。

## 8. 技术实现

**零图表库。** 所有可视化 = CSS gradient + `width`/`height` 过渡 + inline SVG(仅雷达图与四象限)。不引 echarts / chart.js。

**模板用 Jinja2**,不要 `str.replace` + `<!-- INJECT_XXX -->` anchor(UZI 那套已积累三层 anchor 兜底的技术债)。

**自包含**:CSS inline 在 `<style>`;字体优先系统栈(Inter / PingFang SC),不依赖 Google Fonts CDN;图片与二维码 base64 内嵌。产出单文件可直接发送。

## 9. 文案守则

### 面向谁写

**假设读者不知道"买基金要看基金经理"。** 这是这个产品的默认受众 —— 不是机构投研,是被推荐了一只基金、想知道该不该买的人。

所以界面上一律用中文,英文术语只在需要时括号补一下:

| ❌ 不要 | ✅ 要 |
|---|---|
| House Divergence 83 | 跟同事有多不一样 83 |
| Independent Alpha +4.7% | 靠自己判断多赚 4.7% |
| Contrarian Hit Rate 63.6% | 跟同事对着干 11 场 7 胜 4 负 |
| Idea Origination 91 | 是不是第一个发现的 91 |
| Average House Lead 2.1Q | 比同事早半年 |
| Alpha When Divergent | 跟同事不一样的时候 |
| Capacity Utilization 48% | 还能装多少钱 用了 48% |
| Error Correction B+ | 认错快不快 B+ |
| Key Person Risk 高 | 这只基金就是他一个人 |
| 剔除 Top3 赢家后仍为正 | 删掉最赚的三只股,还是赚 |

判词也一样。不要写"该经理行业配置偏离度显著高于公司均值",写"**他砍掉白酒去买当时没人要的半导体,同事大概觉得他疯了**"。

### 保留娱乐感

- 娱乐封号只能来自行为证据(`不抱团的孤狼` / `熊市不甩锅` / `公司里第一个买家` / `规模受害者`),不取笑外貌、地域、隐私
- emoji 用在判定位(👑 🟢 ❌ ⚠️),不要满屏撒
- 对战擂台、判决印章这类组件就是为了"好玩"存在的,不要因为显得不严肃而删掉 —— 严肃性由数字保证,不由排版保证

### 其他

- 先判,再证
- 一个模块 = 一个判词 + 三条证据 + 一条反证
- **禁用**:综合来看 / 值得关注 / 长期视角下 / 一方面另一方面 / 业绩优秀 / 前景广阔 / 需要观察
- 金句必须含具体数字
- 娱乐封号只能来自行为证据(`不抱团的孤狼` / `规模受害者` / `熊市保安` / `公司里的第一个买家`),不取笑外貌、地域、隐私
- 数据来源默认折叠,**关键缺口不许折叠隐藏**
- 每个估算值标 `估算`,不许伪精确

### 视觉优先(2026-08-11 起为最高优先级)

**文字越少越好,能画出来的绝不写出来。**

- 一个模块 = 一个短标签 + 一组图形 + 至多一行事实。超过这个配比就是没设计完
- **删除劝导**:不写"拿不住的人经理再优秀也没意义""能不能拿住比选不选他重要"这类替用户下结论的句子。事实摆出来(最大回撤 32.6%、最长 29 个月回本),判断留给用户
- **删除解说小字**:时间线节点只留"年份 + 事件",不写"这是后来 XX 的地基"这种画外音
- **删除 AI 腔连接词**:值得注意的是 / 换句话说 / 总的来说 / 换句话说
- 判词保留(产品的嗓子),但每屏至多一句,且必须含数字

**劝导句 → 图形的固定替换:**

| 原来的劝导段 | 替换成的组件 |
|---|---|
| "7 胜 4 负" | 战绩点阵(7 绿 4 红圆点) |
| "基金赚 68% 你只赚 24%" | 两个对比大数字块 |
| "表面 142 只实际押一件事" | 单条 100% 占比条(76% 红) |
| "踩踏时出口很少" | 142 → 3 大数字 + 清空天数徽章 |
| "仓位别超 5% / 拿 3 年" | 参数徽章行(不用句子) |
| "2022 和 2026 掉同一个坑" | 坑点时间轴(两面红旗) |
| "三堂会审胜平负" | 三张大字判定卡(胜/平/胜) |

**买卖复盘必须用真实 K 线**:baostock 周 K + B/S 圆点(B 红在下,S 绿在上)+ 卖价虚线参考线。图表库用本地内嵌的 lightweight-charts(`scripts/build_v2.py` 从模板注入库 + 数据,手画示意曲线禁止再出现)。K 线配色遵守 A 股习惯:红涨绿跌。

**买卖复盘的布局是「榜单 + 大图」主从结构**(2026-08-11 定稿):

- 顶部三个分类 Tab:`赚最多` / `亏最多` / `卖飞现场`
- 左侧排行列表:名次 + 股票名 + 代码·操作笔数 + 盈亏金额(赚绿亏红;卖飞 Tab 显示「卖后 +xx%」)
- 右侧详情面板**永远深色**(同分享卡规则,浅色主题下形成米白页面 + 深色面板的对比):第 N 名 + 股票名大字 + 盈亏巨型数字 + 图例 + 真实周K + 一行复盘 + 评级徽章 + 数据口径脚注
- K 线**聚焦交易窗口**(首笔前约半年 → 末笔后约一年半),不显示整段历史,买卖点标记带报告期(如 `买 19Q3`)
- K 线上必须画**成本线**(全部买入加权均价,绿色实线,轴上标价)与**卖出线**(每次清仓价,红色虚线,最多 3 条) —— "10 块买的 60 块卖的"要一眼可见
- 数据管线:`scripts/build_replay_data.py` 生成 `.cache/replay.json`(日K降采样周K + 盈亏估算 + 卖飞幅度),`scripts/build_v2.py` 注入

**机构视角模块**(真实数据报告必备,2026-08-11 定稿):

专业机构评价基金的标准口径,全部可由日净值 + 季报计算,禁止只给收益率:

| 指标组 | 内容 | 展示 |
|---|---|---|
| 风险调整收益 | 夏普 / 卡玛(年化÷最大回撤) / 索提诺 / **信息比率**(>0.5 优秀,高亮) | g4 大数字卡 |
| 上行/下行捕获 | 月度口径,同时 >100/<100 = 真本事 | 对比大数字 + 判读徽章 |
| 归因四件套 | 年化 Alpha(CAPM) / Beta / 跟踪误差 / R² | g4 卡 |
| 月度胜率 | vs 基准,标样本月数 | 大数字卡 |
| 持仓特征 | 前十大集中度(均值+最新,升降标色) / 持股数量(注明全持仓期) / 年化波动 | 小卡阵 |
| 风格箱 | 晨星 3×3(尺寸×风格),持仓推断,标"估算" | 九宫格高亮 |

每个指标的 sub 文案写"这个数回答什么问题",不写教科书定义。

## 10. 验收

- [ ] 六 Tab 齐全(判决书/这个人/独立战争/拆穿运气/你会怎么亏/怎么用),锚点导航可用
- [ ] 首屏是四重判决(人/产品/当前/你),不是单一"可以买"
- [ ] 巨型分数带可信区间(78 → 74-82)与置信度
- [ ] Independence 是独立 Tab
- [ ] **公司门派图存在**(至少显示门派人数组,目标经理归属)
- [ ] **三堂会审存在**(第三堂行业 ETF 对照,事前选定代码)
- [ ] **十万元灾难片存在**(金额滑块)
- [ ] **Alpha 到手率存在**(五层扣减漏水管)
- [ ] **抄作业指数存在**(经理时钟 vs 披露时钟)
- [ ] 战役卡带四象限判定
- [ ] Thinking / Alpha 双条同屏未合并
- [ ] 四种判词矩阵按数据正确渲染
- [ ] 失败战役卡与成功卡尺寸一致、混排、未折叠
- [ ] Hit Rate 旁有赔率与期望值
- [ ] 伪共识告警条在背离 >3pp 时出现
- [ ] Alpha 瀑布加总校验显示 ✓
- [ ] Career vs Recent 5Y 对照表存在
- [ ] 资金徽章无证据的保持灰色
- [ ] Evidence Confidence 在首屏可见
- [ ] share-card 二维码非空白
- [ ] 无 console error
- [ ] 单文件打开无外部依赖失败
- [ ] 全文搜不到禁用词
- [ ] **黑白两个主题都完整检查过一遍**,浅色下荧光绿已换成深绿
- [ ] 主题切换后 localStorage 记住,刷新不回弹
- [ ] 分享卡在浅色主题下仍是深色(不跟主题变)
- [ ] **界面上没有裸露的英文术语**,一律按 §9 对照表译成中文
- [ ] 对战擂台的双方描述是大白话,不是研报腔
- [ ] **视觉优先**:每个模块 = 短标签 + 图形 + 至多一行事实,全文无劝导句
- [ ] **买卖复盘是真实 K 线**(B/S 圆点 + 卖价虚线),不是手画示意图
- [ ] 劝导句替换组件齐全:战绩点阵 / 对比大数字 / 底牌占比条 / 逃生门大数字 / 参数徽章 / 坑点时间轴 / 三堂判定卡
