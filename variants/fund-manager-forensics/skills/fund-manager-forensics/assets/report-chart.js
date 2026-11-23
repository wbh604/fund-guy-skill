"use strict";

(function exposeReportChart(root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.FMFReportChart = api;
})(typeof globalThis === "object" ? globalThis : this, function createReportChart() {
  const SVG_NS = "http://www.w3.org/2000/svg";

  function normalizeTrade(item) {
    if (!item || typeof item !== "object") return {};
    if (!item.trade_record || typeof item.trade_record !== "object") return item;
    return {
      ...item.trade_record,
      identity_status: item.identity_status,
      manager_statement: item.manager_statement,
      mapping_basis: item.mapping_basis,
      source: item.source,
    };
  }

  function periodDate(period) {
    const match = String(period || "").match(/^(\d{4})(Q1|Q2|H1|Q3|Q4|FY)$/);
    if (!match) return null;
    const suffixes = {
      Q1: "03-31",
      Q2: "06-30",
      H1: "06-30",
      Q3: "09-30",
      Q4: "12-31",
      FY: "12-31",
    };
    return new Date(`${match[1]}-${suffixes[match[2]]}T00:00:00`);
  }

  function nearestRowIndex(rows, targetDate) {
    let bestIndex = -1;
    let bestDistance = Infinity;
    rows.forEach((row, index) => {
      const distance = targetDate - new Date(`${row.date}T00:00:00`);
      if (distance >= 0 && distance <= 6 * 86400000 && distance < bestDistance) {
        bestDistance = distance;
        bestIndex = index;
      }
    });
    return bestIndex;
  }

  function svgNode(documentNode, tag, attributes = {}) {
    const node = documentNode.createElementNS(SVG_NS, tag);
    Object.entries(attributes).forEach(([key, value]) => node.setAttribute(key, String(value)));
    return node;
  }

  function buildCandlestickSvg({ container, item, stockOhlc, human }) {
    if (!container?.ownerDocument) throw new Error("K线容器无效");
    const documentNode = container.ownerDocument;
    const trade = normalizeTrade(item);
    const events = Array.isArray(trade.events) ? trade.events : [];
    const series = stockOhlc?.series?.[String(trade.code)];
    const rows = Array.isArray(series?.rows) ? series.rows : [];
    container.replaceChildren();

    if (!rows.length) {
      const empty = documentNode.createElement("p");
      empty.className = "chart-empty";
      empty.textContent = "该股票行情缺失";
      container.appendChild(empty);
      return { candleCount: 0, markerCount: 0, provider: "行情未取得" };
    }

    const eventDates = events.map((event) => periodDate(event.period)).filter(Boolean);
    const firstEvent = eventDates.length
      ? new Date(Math.min(...eventDates.map((date) => date.getTime())))
      : new Date(`${rows[0].date}T00:00:00`);
    const lastEvent = eventDates.length
      ? new Date(Math.max(...eventDates.map((date) => date.getTime())))
      : new Date(`${rows.at(-1).date}T00:00:00`);
    const padBefore = new Date(firstEvent);
    const padAfter = new Date(lastEvent);
    padBefore.setMonth(padBefore.getMonth() - 4);
    padAfter.setMonth(padAfter.getMonth() + 4);
    const chartRows = rows.filter((row) => {
      const date = new Date(`${row.date}T00:00:00`);
      return date >= padBefore && date <= padAfter;
    });
    if (!chartRows.length) {
      container.textContent = "披露区间内没有行情";
      return { candleCount: 0, markerCount: 0, provider: "区间行情缺失" };
    }
    const width = Math.max(760, chartRows.length * 6.2 + 98);
    const height = 348;
    const margin = { top: 34, right: 58, bottom: 42, left: 42 };
    const chartWidth = width - margin.left - margin.right;
    const chartHeight = height - margin.top - margin.bottom;
    const minPrice = Math.min(...chartRows.map((row) => Number(row.low)));
    const maxPrice = Math.max(...chartRows.map((row) => Number(row.high)));
    const pricePad = Math.max((maxPrice - minPrice) * 0.08, maxPrice * 0.01, 0.01);
    const yMin = minPrice - pricePad;
    const yMax = maxPrice + pricePad;
    const xStep = chartWidth / chartRows.length;
    const candleWidth = Math.max(2.2, Math.min(5.2, xStep * 0.68));
    const xFor = (index) => margin.left + xStep * index + xStep / 2;
    const yFor = (price) => margin.top + ((yMax - Number(price)) / (yMax - yMin)) * chartHeight;
    const svg = svgNode(documentNode, "svg", {
      viewBox: `0 0 ${width} ${height}`,
      role: "img",
      "aria-label": `${trade.name}周K线与披露买卖点`,
    });

    for (let index = 0; index <= 4; index += 1) {
      const price = yMax - ((yMax - yMin) * index) / 4;
      const y = yFor(price);
      svg.appendChild(svgNode(documentNode, "line", {
        x1: margin.left,
        y1: y,
        x2: width - margin.right,
        y2: y,
        class: "chart-grid",
      }));
      const label = svgNode(documentNode, "text", {
        x: width - margin.right + 8,
        y: y + 4,
        class: "price-label",
      });
      label.textContent = price.toFixed(price >= 100 ? 0 : 2);
      svg.appendChild(label);
    }

    chartRows.forEach((row, index) => {
      const x = xFor(index);
      const stateClass = Number(row.close) >= Number(row.open) ? "is-up" : "is-down";
      const bodyTop = yFor(Math.max(Number(row.open), Number(row.close)));
      const bodyBottom = yFor(Math.min(Number(row.open), Number(row.close)));
      svg.appendChild(svgNode(documentNode, "line", {
        x1: x,
        y1: yFor(row.high),
        x2: x,
        y2: yFor(row.low),
        class: `candle-wick ${stateClass}`,
      }));
      svg.appendChild(svgNode(documentNode, "rect", {
        x: x - candleWidth / 2,
        y: bodyTop,
        width: candleWidth,
        height: Math.max(1.4, bodyBottom - bodyTop),
        class: `candle-body ${stateClass}`,
      }));
    });

    let markerCount = 0;
    events.forEach((event) => {
      const targetDate = periodDate(event.period);
      if (!targetDate) return;
      const rowIndex = nearestRowIndex(chartRows, targetDate);
      if (rowIndex < 0) return;
      const row = chartRows[rowIndex];
      const x = xFor(rowIndex);
      const isBuy = String(event.event).startsWith("B");
      const isSell = event.event === "S" || event.event === "EXIT";
      const y = isBuy
        ? Math.max(18, yFor(row.low) - 18)
        : isSell
          ? Math.min(height - 30, yFor(row.high) + 19)
          : yFor(row.close);
      const eventClass = isBuy ? "event-buy" : isSell ? "event-sell" : "event-hold";
      const marker = svgNode(documentNode, "g", { class: `event-node ${eventClass}` });
      marker.appendChild(svgNode(documentNode, "line", {
        x1: x,
        y1: yFor(row.close),
        x2: x,
        y2: y,
        class: "event-stem",
      }));
      marker.appendChild(svgNode(documentNode, "circle", { cx: x, cy: y, r: 11 }));
      const mark = svgNode(documentNode, "text", {
        x,
        y: y + 4,
        "text-anchor": "middle",
        class: "event-mark",
      });
      mark.textContent = human?.tradeEventLabel?.(event.event) || String(event.event || "？");
      marker.appendChild(mark);
      const period = svgNode(documentNode, "text", {
        x,
        y: isSell ? y + 26 : y - 18,
        "text-anchor": "middle",
        class: "event-period",
      });
      period.textContent = human?.periodLabel?.(event.period) || String(event.period || "");
      marker.appendChild(period);
      svg.appendChild(marker);
      markerCount += 1;
    });

    const firstDate = svgNode(documentNode, "text", {
      x: margin.left,
      y: height - 12,
      class: "date-label",
    });
    firstDate.textContent = chartRows[0].date.slice(0, 7);
    const lastDate = svgNode(documentNode, "text", {
      x: width - margin.right,
      y: height - 12,
      "text-anchor": "end",
      class: "date-label",
    });
    lastDate.textContent = chartRows.at(-1).date.slice(0, 7);
    svg.append(firstDate, lastDate);
    container.appendChild(svg);

    return {
      candleCount: chartRows.length,
      markerCount,
      provider: human?.providerLabel?.(series.provider) || String(series.provider || "公开行情数据"),
    };
  }

  return Object.freeze({ buildCandlestickSvg, normalizeTrade });
});
