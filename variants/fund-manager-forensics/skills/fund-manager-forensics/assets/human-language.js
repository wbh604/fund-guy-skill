"use strict";

(function exposeHumanLanguage(root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.FMFHumanLanguage = api;
})(typeof globalThis === "object" ? globalThis : this, function createHumanLanguage() {
  const STATUS_LABELS = Object.freeze({
    已证实: "公开资料确认",
    估算: "根据公开资料推算",
    未证明: "证据还不够",
    未发现可靠公开信息: "公开资料未找到",
  });

  const REVIEWER_LABELS = Object.freeze({
    people_investigator: "人物调查员",
    alpha_forensic: "收益调查员",
    portfolio_detective: "持仓调查员",
    institutional_skeptic: "机构质疑员",
    chief_underwriter: "首席裁决员",
  });

  const GRADE_LABELS = Object.freeze({
    A: "法定文件",
    B: "正式访谈",
    C: "专业数据",
    D: "公开线索",
  });

  const RARITY_LABELS = Object.freeze({
    N: "不推荐卡（N）",
    R: "普通卡（R）",
    SR: "稀有卡（SR）",
    SSR: "超稀有卡（SSR）",
    UR: "传说卡（UR）",
  });

  const EVENT_LABELS = Object.freeze({
    B: "买",
    "B+": "加",
    H: "持",
    S: "卖",
    EXIT: "卖",
  });

  const EVENT_DESCRIPTIONS = Object.freeze({
    B: "首次披露买入",
    "B+": "披露显示加仓",
    H: "继续披露持有",
    S: "披露显示减仓",
    EXIT: "完整报告确认退出",
  });

  const JARGON_REPLACEMENTS = Object.freeze([
    [/House Consensus/gi, "公司主流持仓"],
    [/Independent Thinking/gi, "敢不敢和同事不一样"],
    [/Independent Alpha/gi, "不一样时有没有赚到钱"],
    [/Idea Origination/gi, "先手发现"],
    [/Manager Evolution Map/gi, "能力形成时间线"],
    [/Manager Underwriting Profile/gi, "经理核保结论"],
    [/Career Incentive Profile/gi, "职业激励画像"],
    [/Manager\s*[×x]\s*Regime/gi, "经理与市场环境"],
    [/Key Person Risk/gi, "核心人物离任风险"],
    [/Behavioral DNA/gi, "行为模式"],
    [/Mistake Ledger/gi, "错误档案"],
    [/Circle of Competence/gi, "能力圈"],
    [/Conviction/gi, "重仓信念"],
    [/Investment-first/gi, "投资优先型"],
    [/People/gi, "基金经理本人"],
    [/Alpha/gi, "主动赚到的钱"],
    [/Beta/gi, "行情红利"],
    [/AUM/gi, "管理规模"],
    [/Agent/gi, "调查员"],
    [/\bTMT\b/g, "科技、传媒与通信（TMT）"],
    [/\bAI\b/g, "人工智能（AI）"],
    [/\bFOF\b/g, "基金中基金（FOF）"],
    [/\bCDMO\b/g, "医药合同研发生产（CDMO）"],
  ]);

  const GAP_LABELS = Object.freeze({
    缺公司持仓网络: "同公司基金历史持仓对比",
    需补同公司基金持仓: "同公司基金历史持仓对比",
    需补同公司交易序列: "同公司基金逐季买卖变化",
    需补基金经理持仓网络: "经理管理过的全部基金持仓",
    需补经理全部产品持仓: "经理管理过的全部基金持仓",
    需补行业指数历史: "同期行业指数历史",
    需逐期交易与收益归因: "逐期交易和收益归因",
    缺逐笔交易和复盘原文: "逐笔交易和经理复盘原文",
    缺自由流通市值与成交额压力测试: "自由流通市值和成交额压力测试",
    仅取得2025年末同口径数据: "更多年份的同口径数据",
  });

  function statusLabel(status) {
    return STATUS_LABELS[String(status || "")] || "证据状态未知";
  }

  function reviewerLabel(reviewer) {
    return REVIEWER_LABELS[String(reviewer || "")] || "审阅人员未标明";
  }

  function gradeLabel(grade) {
    return GRADE_LABELS[String(grade || "").toUpperCase()] || "来源类型未标明";
  }

  function rarityLabel(grade) {
    return RARITY_LABELS[String(grade || "").toUpperCase()] || "等级未评定";
  }

  function tradeEventLabel(event) {
    return EVENT_LABELS[String(event || "").toUpperCase()] || "？";
  }

  function tradeEventDescription(event) {
    return EVENT_DESCRIPTIONS[String(event || "").toUpperCase()] || "持仓变化未说明";
  }

  function periodLabel(period) {
    const value = String(period || "");
    const match = value.match(/^(\d{4})(Q1|Q2|H1|Q3|Q4|FY)$/);
    if (!match) return value;
    const suffix = {
      Q1: "年一季度",
      Q2: "年二季度",
      H1: "年半年报",
      Q3: "年三季度",
      Q4: "年四季度",
      FY: "年年报",
    }[match[2]];
    return `${match[1]}${suffix}`;
  }

  function humanizeJargon(value) {
    let output = String(value ?? "");
    JARGON_REPLACEMENTS.forEach(([pattern, replacement]) => {
      output = output.replace(pattern, replacement);
    });
    return output;
  }

  function sourceIndex(sources) {
    const index = new Map();
    (Array.isArray(sources) ? sources : []).forEach((source) => {
      if (source && source.id && source.title) index.set(String(source.id), String(source.title));
    });
    return index;
  }

  function unique(items) {
    return [...new Set(items.filter(Boolean))];
  }

  function normalizeEvidenceNote(value) {
    let note = String(value || "").trim();
    if (!note) return "";
    if (note.startsWith("ledger:")) return "见本报告对应的取证记录";
    if (GAP_LABELS[note]) return `还缺：${GAP_LABELS[note]}`;
    if (note.startsWith("缺")) return `还缺：${note.slice(1)}`;
    if (note.startsWith("需补")) return `还缺：${note.slice(2)}`;
    note = note.replace(/(\d{4})(Q1|Q2|H1|Q3|Q4|FY)/g, (match) => periodLabel(match));
    note = note.replace(/§([\d.]+(?:—§?[\d.]+)?)/g, "第$1节");
    note = note.replace("仅为公开采访观察", "采访只能证明他说过，不能证明实际做过");
    note = note.replace("FMF硬规则", "项目事实规则");
    note = note.replace("FMF证据规则", "项目证据规则");
    return humanizeJargon(note);
  }

  function evidenceSummary(status, refs, sources) {
    const raw = (Array.isArray(refs) ? refs.join("；") : String(refs || "")).trim();
    const index = sourceIndex(sources);
    const codes = unique(raw.match(/\b[A-D]\d{2}\b/g) || []);
    const titles = codes.map((code) => index.get(code)).filter(Boolean);
    let remainder = raw
      .replace(/\b[A-D]\d{2}\b/g, "")
      .replace(/[\/]+/g, "；")
      .replace(/^[\s·；，、]+|[\s·；，、]+$/g, "")
      .replace(/[；]{2,}/g, "；");
    const noteParts = unique(
      remainder
        .split("；")
        .map((part) => normalizeEvidenceNote(part.replace(/^[\s·]+/, "")))
        .filter(Boolean)
    );

    const prefix = statusLabel(status);
    if (titles.length) {
      const note = noteParts.length ? `；${noteParts.join("；")}` : "";
      return `${prefix}｜依据：${unique(titles).join("、")}${note}`;
    }
    if (noteParts.length) return `${prefix}｜${noteParts.join("；")}`;
    return prefix;
  }

  function safeHttpsUrl(value) {
    try {
      const url = new URL(String(value || ""));
      return url.protocol === "https:" ? url.href : null;
    } catch (_error) {
      return null;
    }
  }

  function providerLabel(provider) {
    const value = String(provider || "").toLowerCase();
    const labels = {
      sina: "新浪财经",
      akshare: "公开行情数据",
      eastmoney: "天天基金",
      tencent: "腾讯财经",
    };
    return labels[value] || "公开行情数据";
  }

  return Object.freeze({
    evidenceSummary,
    gradeLabel,
    humanizeJargon,
    periodLabel,
    providerLabel,
    rarityLabel,
    reviewerLabel,
    safeHttpsUrl,
    statusLabel,
    tradeEventDescription,
    tradeEventLabel,
  });
});
