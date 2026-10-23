/* Визуальные модели для объяснения тем (SVG/HTML, без внешних библиотек). */
(function (global) {
  "use strict";

  const PALETTE = ["#6366f1", "#ec4899", "#f59e0b", "#10b981", "#06b6d4", "#8b5cf6", "#ef4444", "#0ea5e9"];

  function esc(s) {
    return String(s === undefined || s === null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  function svgWrap(w, h, inner) {
    return `<svg viewBox="0 0 ${w} ${h}" width="${w}" height="${h}" role="img">${inner}</svg>`;
  }

  function text(x, y, str, opts) {
    const o = opts || {};
    const rotate = o.rotate ? ' transform="rotate(' + o.rotate + ' ' + x + ' ' + y + ')"' : '';
    return `<text x="${x}" y="${y}" font-family="Nunito, Segoe UI, sans-serif" font-size="${o.size || 16}"
      font-weight="${o.weight || 700}" fill="${o.fill || "#1f2a44"}" text-anchor="${o.anchor || "start"}"
      ${rotate}>${esc(str)}</text>`;
  }

  function rect(x, y, w, h, fill, opts) {
    const o = opts || {};
    const stroke = o.stroke || "none";
    const sw = o.sw || 0;
    const rx = o.rx === undefined ? 6 : o.rx;
    const op = o.opacity === undefined ? 1 : o.opacity;
    return `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${rx}" fill="${fill}"
      stroke="${stroke}" stroke-width="${sw}" opacity="${op}"/>`;
  }

  /* --------------------------------------------------------- разряды */
  function placeValue(spec) {
    const n = Math.abs(spec.number || 0);
    const h = Math.floor(n / 100);
    const t = Math.floor((n % 100) / 10);
    const o = n % 10;
    const parts = [];
    let y = 20;
    const rows = [
      { count: h, label: "сотни (100)", draw: "big" },
      { count: t, label: "десятки (10)", draw: "rod" },
      { count: o, label: "единицы (1)", draw: "small" },
    ];
    rows.forEach((row, ri) => {
      const rowY = y + ri * 74;
      parts.push(text(12, rowY + 26, row.label, { size: 14, fill: "#5b6785" }));
      let x = 150;
      for (let i = 0; i < row.count; i++) {
        if (row.draw === "big") {
          parts.push(rect(x, rowY, 30, 30, "#6366f1", { stroke: "#4338ca", sw: 2, rx: 5 }));
          parts.push(text(x + 15, rowY + 20, "100", { size: 9, fill: "#fff", anchor: "middle" }));
          x += 34;
        } else if (row.draw === "rod") {
          parts.push(rect(x, rowY, 12, 30, "#f59e0b", { stroke: "#d97706", sw: 2, rx: 3 }));
          x += 16;
        } else {
          parts.push(rect(x, rowY + 8, 16, 16, "#10b981", { stroke: "#059669", sw: 2, rx: 3 }));
          x += 20;
        }
      }
      if (row.count === 0) parts.push(text(x, rowY + 20, "—", { size: 16, fill: "#8b95b0" }));
    });
    const digits = String(n).padStart(3, " ").split("");
    digits.forEach((d, i) => {
      parts.push(rect(20 + i * 34, 240, 30, 40, i === 0 ? "#eef2ff" : "#f1f5f9", { rx: 8, stroke: "#e2e8f0", sw: 2 }));
      parts.push(text(35 + i * 34, 268, d.trim() === "" ? "" : d, { size: 24, anchor: "middle", fill: i === 0 ? "#4338ca" : "#1f2a44" }));
    });
    parts.push(text(130, 268, "= " + n, { size: 26, fill: "#4338ca", weight: 900 }));
    return svgWrap(430, 292, parts.join(""));
  }

  /* ------------------------------------------------------ числовая прямая */
  function numberLine(spec) {
    const from = spec.from !== undefined ? spec.from : 0;
    const to = spec.to !== undefined ? spec.to : 10;
    const w = 640, h = 140, left = 40, right = w - 40, y = 90;
    const parts = [];
    const steps = 10;
    const step = (right - left) / steps;
    parts.push(`<line x1="${left}" y1="${y}" x2="${right}" y2="${y}" stroke="#94a3b8" stroke-width="3" stroke-linecap="round"/>`);
    for (let i = 0; i <= steps; i++) {
      const x = left + i * step;
      const val = from + (to - from) * (i / steps);
      const isMark = (spec.marks || []).some((m) => Math.abs(m - val) < (to - from) / steps / 2);
      parts.push(`<line x1="${x}" y1="${y - 9}" x2="${x}" y2="${y + 9}" stroke="${isMark ? "#6366f1" : "#94a3b8"}" stroke-width="${isMark ? 4 : 2}"/>`);
      parts.push(text(x, y + 30, Math.round(val * 10) / 10, { size: 12, anchor: "middle", fill: isMark ? "#4338ca" : "#64748b" }));
      if (isMark) parts.push(text(x, y - 18, Math.round(val), { size: 13, anchor: "middle", fill: "#4338ca", weight: 900 }));
    }
    if (spec.jumps) {
      const count = spec.jumps.count || 0, size = spec.jumps.size || 1;
      for (let i = 0; i < count; i++) {
        const x1 = left + ((from + i * size - from) / (to - from)) * (right - left);
        const x2 = left + ((from + (i + 1) * size - from) / (to - from)) * (right - left);
        parts.push(`<path d="M ${x1} ${y - 12} Q ${(x1 + x2) / 2} ${y - 52} ${x2} ${y - 12}" fill="none" stroke="#ec4899" stroke-width="3"/>`);
        parts.push(text((x1 + x2) / 2, y - 44, "+" + size, { size: 12, anchor: "middle", fill: "#ec4899" }));
      }
    }
    if (spec.result !== undefined) {
      const x = left + ((spec.result - from) / (to - from)) * (right - left);
      parts.push(`<circle cx="${x}" cy="${y}" r="9" fill="#f59e0b" stroke="#d97706" stroke-width="3"/>`);
    }
    return svgWrap(w, h, parts.join(""));
  }

  /* ------------------------------------------------------------- группы */
  function groups(spec) {
    const rows = spec.rows || 1, cols = spec.cols || 1;
    const emoji = spec.emoji || "🔵";
    const extra = spec.extra || 0;
    const cell = 26, w = Math.max(240, cols * cell + 40), h = rows * cell + 46;
    const parts = [];
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        parts.push(text(20 + c * cell, 32 + r * cell, emoji, { size: 20 }));
      }
      parts.push(rect(14, 12 + r * cell, cols * cell, cell + 4, r % 2 ? "#f8fafc" : "#eef2ff", { rx: 8, stroke: "#e2e8f0", sw: 1, opacity: .55 }));
    }
    if (extra > 0) {
      parts.push(rect(14, 14 + rows * cell, extra * cell + 6, cell, "#fff7ed", { rx: 8, stroke: "#fdba74", sw: 2 }));
      for (let c = 0; c < extra; c++) parts.push(text(24 + c * cell, 32 + rows * cell, spec.extra_emoji || "🔴", { size: 20 }));
      if (!spec.hide_extra_label) {
        parts.push(text(24 + extra * cell, 32 + rows * cell, "← остаток", { size: 13, fill: "#c2410c" }));
      }
    }
    if (!spec.hide_count) {
      parts.push(text(14, h - 4, `${rows} ${rows === 1 ? "группа" : "групп"} по ${cols}`, { size: 14, fill: "#5b6785" }));
    }
    return svgWrap(w, h, parts.join(""));
  }

  /* ------------------------------------------------------------- массив */
  function array(spec) {
    const rows = spec.rows || 2, cols = spec.cols || 3;
    const cell = 30, w = cols * cell + 40, h = rows * cell + 46;
    const parts = [];
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        parts.push(rect(20 + c * cell, 20 + r * cell, cell - 4, cell - 4, (r + c) % 2 ? "#818cf8" : "#6366f1", { rx: 5 }));
      }
    }
    parts.push(text(20, h - 6, `${rows} рядов × ${cols} столбцов = ${rows * cols}`, { size: 15, fill: "#4338ca", weight: 900 }));
    return svgWrap(w, h, parts.join(""));
  }

  /* ---------------------------------------------------------- столбик */
  function column(spec) {
    const top = String(spec.top || ""), bottom = String(spec.bottom || ""), op = spec.op || "+";
    const len = Math.max(top.length, bottom.length);
    const cw = 40, w = len * cw + 90, h = 190;
    const parts = [];
    const right = w - 20;
    const drawNumber = (str, y, opts) => {
      const o = opts || {};
      for (let i = 0; i < str.length; i++) {
        const x = right - (str.length - i) * cw;
        parts.push(text(x + cw / 2, y, str[i], { size: 30, anchor: "middle", weight: 800, fill: o.fill || "#1f2a44" }));
        if (o.focus && o.focus === (["units", "tens", "hundreds"][str.length - 1 - i])) {
          parts.push(rect(x + 2, y - 26, cw - 4, 34, "#fde68a", { rx: 6, opacity: .55 }));
        }
      }
    };
    parts.push(text(right - len * cw - 24, 62, op, { size: 32, fill: "#4338ca", weight: 900 }));
    drawNumber(top, 62);
    drawNumber(bottom, 108);
    parts.push(`<line x1="${right - len * cw - 10}" y1="120" x2="${right}" y2="120" stroke="#1f2a44" stroke-width="3"/>`);
    if (spec.result) {
      for (let i = 0; i < String(spec.result).length; i++) {
        const x = right - (String(spec.result).length - i) * cw;
        parts.push(text(x + cw / 2, 160, String(spec.result)[i], { size: 30, anchor: "middle", weight: 900, fill: "#16a34a" }));
      }
    }
    return svgWrap(w, h, parts.join(""));
  }

  /* -------------------------------------------------------- дробный круг */
  function fractionCircle(spec) {
    const den = spec.den || 4, num = spec.num || 1;
    const size = 190, cx = size / 2, cy = size / 2, r = 76;
    const parts = [];
    for (let i = 0; i < den; i++) {
      const a0 = (i / den) * Math.PI * 2 - Math.PI / 2;
      const a1 = ((i + 1) / den) * Math.PI * 2 - Math.PI / 2;
      const x0 = cx + r * Math.cos(a0), y0 = cy + r * Math.sin(a0);
      const x1 = cx + r * Math.cos(a1), y1 = cy + r * Math.sin(a1);
      const large = a1 - a0 > Math.PI ? 1 : 0;
      const fill = i < num ? "#f59e0b" : "#e2e8f0";
      parts.push(`<path d="M ${cx} ${cy} L ${x0} ${y0} A ${r} ${r} 0 ${large} 1 ${x1} ${y1} Z" fill="${fill}" stroke="#fff" stroke-width="2"/>`);
    }
    parts.push(`<circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="#cbd5e1" stroke-width="2"/>`);
    parts.push(`<circle cx="${cx}" cy="${cy}" r="30" fill="#ffffff" opacity="0.92"/>`);
    parts.push(text(cx, cy + 7, `${num}/${den}`, { size: 22, anchor: "middle", weight: 900, fill: "#b45309" }));
    parts.push(text(cx, size - 6, `${den} равных частей, закрашено ${num}`, { size: 13, anchor: "middle", fill: "#5b6785" }));
    return svgWrap(size, size, parts.join(""));
  }

  /* ---------------------------------------------------- дробная полоска */
  function fractionBar(spec) {
    const den = spec.den || 4, num = spec.num || 1;
    const w = 420, bh = 54, y = 24;
    const seg = w / den;
    const parts = [];
    for (let i = 0; i < den; i++) {
      parts.push(rect(i * seg + 2, y, seg - 4, bh, i < num ? "#f59e0b" : "#e2e8f0", { rx: 6, stroke: "#cbd5e1", sw: 1 }));
      parts.push(text(i * seg + seg / 2, y + bh / 2 + 5, "1/" + den, { size: 11, anchor: "middle", fill: i < num ? "#ffffff" : "#64748b" }));
    }
    parts.push(text(w / 2, y + bh + 24, `${num} из ${den} — это ${num}/${den}`, { size: 16, anchor: "middle", fill: "#b45309", weight: 900 }));
    return svgWrap(w, y + bh + 34, parts.join(""));
  }

  /* ------------------------------------------------------------- весы */
  function balance(spec) {
    const w = 360, h = 190;
    const parts = [];
    const left = spec.left === undefined ? 0 : spec.left;
    const right = spec.right === undefined ? 0 : spec.right;
    parts.push(`<line x1="60" y1="110" x2="300" y2="110" stroke="#94a3b8" stroke-width="6" stroke-linecap="round"/>`);
    parts.push(`<line x1="180" y1="60" x2="180" y2="130" stroke="#64748b" stroke-width="6"/>`);
    parts.push(`<polygon points="180,130 140,170 220,170" fill="#cbd5e1"/>`);
    parts.push(rect(70, 70, 100, 40, "#eef2ff", { rx: 10, stroke: "#6366f1", sw: 2 }));
    parts.push(text(120, 96, String(left), { size: 22, anchor: "middle", fill: "#4338ca", weight: 900 }));
    parts.push(rect(190, 70, 100, 40, "#fef3c7", { rx: 10, stroke: "#f59e0b", sw: 2 }));
    parts.push(text(240, 96, String(right) + (spec.unknown ? " " + spec.unknown : ""), { size: 22, anchor: "middle", fill: "#b45309", weight: 900 }));
    parts.push(text(120, 52, "левая чаша", { size: 12, anchor: "middle", fill: "#64748b" }));
    parts.push(text(240, 52, "правая чаша", { size: 12, anchor: "middle", fill: "#64748b" }));
    return svgWrap(w, h, parts.join(""));
  }

  /* -------------------------------------------------------------- часы */
  function clock(spec) {
    const h = spec.h === undefined ? 12 : spec.h, m = spec.m || 0;
    const size = 190, cx = size / 2, cy = size / 2, r = 78;
    const parts = [];
    parts.push(`<circle cx="${cx}" cy="${cy}" r="${r}" fill="#fff" stroke="#6366f1" stroke-width="5"/>`);
    for (let i = 1; i <= 12; i++) {
      const a = (i / 12) * Math.PI * 2 - Math.PI / 2;
      const x = cx + (r - 18) * Math.cos(a), y = cy + (r - 18) * Math.sin(a);
      parts.push(text(x, y + 5, i, { size: 15, anchor: "middle", fill: "#475569" }));
    }
    const hourAngle = ((h % 12) + m / 60) / 12 * Math.PI * 2 - Math.PI / 2;
    const minAngle = (m / 60) * Math.PI * 2 - Math.PI / 2;
    parts.push(`<line x1="${cx}" y1="${cy}" x2="${cx + 42 * Math.cos(hourAngle)}" y2="${cy + 42 * Math.sin(hourAngle)}" stroke="#1f2a44" stroke-width="7" stroke-linecap="round"/>`);
    parts.push(`<line x1="${cx}" y1="${cy}" x2="${cx + 62 * Math.cos(minAngle)}" y2="${cy + 62 * Math.sin(minAngle)}" stroke="#ec4899" stroke-width="4" stroke-linecap="round"/>`);
    parts.push(`<circle cx="${cx}" cy="${cy}" r="6" fill="#1f2a44"/>`);
    return svgWrap(size, size, parts.join(""));
  }

  /* ----------------------------------------------------------- линейка */
  function ruler(spec) {
    const cm = Math.max(1, Math.min(120, spec.cm || 10));
    const w = 640, h = 110, left = 20;
    const scale = (w - 40) / Math.max(10, Math.ceil(cm / 10) * 10);
    const parts = [];
    parts.push(rect(left, 40, Math.min(cm, Math.ceil(cm / 10) * 10) * scale, 40, "#fef3c7", { rx: 6, stroke: "#d97706", sw: 2 }));
    for (let i = 0; i <= Math.min(cm, Math.ceil(cm / 10) * 10); i++) {
      const x = left + i * scale;
      const big = i % 10 === 0;
      parts.push(`<line x1="${x}" y1="40" x2="${x}" y2="${big ? 58 : 50}" stroke="#b45309" stroke-width="2"/>`);
      if (big) parts.push(text(x, 74, i, { size: 12, anchor: "middle", fill: "#92400e" }));
    }
    parts.push(text(left, 26, `${cm} см`, { size: 18, fill: "#b45309", weight: 900 }));
    return svgWrap(w, h, parts.join(""));
  }

  /* -------------------------------------------------------------- весы (масса) */
  function scale(spec) {
    const w = 320, h = 190;
    const parts = [];
    parts.push(`<path d="M40 120 L80 60 L120 120 Z" fill="#e2e8f0" stroke="#94a3b8" stroke-width="3"/>`);
    parts.push(`<path d="M200 120 L240 60 L280 120 Z" fill="#e2e8f0" stroke="#94a3b8" stroke-width="3"/>`);
    parts.push(rect(44, 40, 72, 50, "#dbeafe", { rx: 8, stroke: "#3b82f6", sw: 2 }));
    parts.push(text(80, 72, `${spec.kg || 0} кг`, { size: 16, anchor: "middle", fill: "#1d4ed8", weight: 900 }));
    parts.push(rect(204, 40, 72, 50, "#dcfce7", { rx: 8, stroke: "#16a34a", sw: 2 }));
    parts.push(text(240, 72, `${spec.g || 0} г`, { size: 16, anchor: "middle", fill: "#15803d", weight: 900 }));
    parts.push(text(160, 160, "1 кг = 1000 г", { size: 16, anchor: "middle", fill: "#334155", weight: 800 }));
    return svgWrap(w, h, parts.join(""));
  }

  /* ------------------------------------------------------------- фигуры */
  function shapes(spec) {
    const kind = spec.kind || "rect";
    const w = 380, h = 230;
    const parts = [];
    if (kind === "rect" || kind === "square") {
      const a = Math.min(spec.a || 10, 24), b = Math.min(spec.b || spec.a || 10, 24);
      const s = 13;
      const bw = a * s, bh = b * s;
      parts.push(rect((w - bw) / 2, (h - bh) / 2, bw, bh, "#dbeafe", { stroke: "#3b82f6", sw: 3, rx: 4 }));
      parts.push(text(w / 2, (h - bh) / 2 - 10, `${spec.a} см`, { size: 16, anchor: "middle", fill: "#1d4ed8", weight: 900 }));
      parts.push(text(w - 20, h / 2 + 5, `${spec.b} см`, { size: 16, anchor: "middle", fill: "#1d4ed8", weight: 900 }));
      if (spec.area) parts.push(text(w / 2, h / 2 + 6, `S = ${spec.a * spec.b} см²`, { size: 22, anchor: "middle", fill: "#15803d", weight: 900 }));
    } else if (kind === "composite") {
      const a = spec.a, b = spec.b, c = spec.c, s = 12;
      const bw = a * s, bh = b * s, cw = c * s;
      parts.push(rect(30, 60, bw, bh, "#dbeafe", { stroke: "#3b82f6", sw: 3, rx: 4 }));
      parts.push(rect(30 + bw, 60 + bh - cw, cw, cw, "#fde68a", { stroke: "#f59e0b", sw: 3, rx: 4 }));
      parts.push(text(30 + bw / 2, 50, `${a} × ${b}`, { size: 14, anchor: "middle", fill: "#1d4ed8", weight: 800 }));
      parts.push(text(30 + bw + cw / 2, 60 + bh - cw - 8, `${c} × ${c}`, { size: 14, anchor: "middle", fill: "#b45309", weight: 800 }));
    } else if (kind === "polygon") {
      const sides = spec.sides || [4, 5, 6];
      const pts = [[40, 170], [120, 60], [250, 80], [330, 170]];
      const poly = pts.map((p) => p.join(",")).join(" ");
      parts.push(`<polygon points="${poly}" fill="#dcfce7" stroke="#16a34a" stroke-width="3"/>`);
      sides.forEach((s, i) => {
        const p1 = pts[i], p2 = pts[(i + 1) % pts.length];
        const mx = (p1[0] + p2[0]) / 2, my = (p1[1] + p2[1]) / 2;
        parts.push(text(mx, my - 6, s + " см", { size: 14, anchor: "middle", fill: "#15803d", weight: 800 }));
      });
    }
    return svgWrap(w, h, parts.join(""));
  }

  /* -------------------------------------------------------- квадратики */
  function areaGrid(spec) {
    const n = Math.min(spec.n || 4, 8);
    const cell = 22, cols = n, rows = n;
    const w = cols * cell + 30, h = rows * cell + 44;
    const parts = [];
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        parts.push(rect(15 + c * cell, 15 + r * cell, cell - 2, cell - 2, "#a5b4fc", { rx: 3, stroke: "#6366f1", sw: 1 }));
      }
    }
    parts.push(text(w / 2, h - 6, `${n} × ${n} = ${n * n} кв. ед.`, { size: 14, anchor: "middle", fill: "#4338ca", weight: 900 }));
    return svgWrap(w, h, parts.join(""));
  }

  /* ------------------------------------------------------------ таблица */
  function tableWidget(spec) {
    const headers = spec.headers || [];
    const rows = spec.rows || [];
    let html = `<table class="table"><thead><tr>`;
    headers.forEach((h) => { html += `<th>${esc(h)}</th>`; });
    html += "</tr></thead><tbody>";
    rows.forEach((row) => {
      html += "<tr>";
      (Array.isArray(row) ? row : [row]).forEach((cell) => {
        html += `<td>${esc(cell)}</td>`;
      });
      html += "</tr>";
    });
    html += "</tbody></table>";
    return html;
  }

  /* ---------------------------------------------------------- диаграмма */
  function chart(spec) {
    const labels = spec.labels || [], values = spec.values || [];
    const max = Math.max.apply(null, values.concat([1]));
    const w = 460, h = 220, pad = 30, base = h - 34;
    const bw = (w - pad * 2) / values.length;
    const parts = [];
    parts.push(`<line x1="${pad}" y1="${base}" x2="${w - pad}" y2="${base}" stroke="#cbd5e1" stroke-width="2"/>`);
    values.forEach((v, i) => {
      const bh = (v / max) * (base - pad);
      const x = pad + i * bw + 8;
      parts.push(rect(x, base - bh, bw - 18, bh, PALETTE[i % PALETTE.length], { rx: 6 }));
      parts.push(text(x + (bw - 18) / 2, base - bh - 8, v, { size: 14, anchor: "middle", fill: "#1f2a44", weight: 900 }));
      parts.push(text(x + (bw - 18) / 2, base + 20, labels[i] || "", { size: 13, anchor: "middle", fill: "#64748b" }));
    });
    return svgWrap(w, h, parts.join(""));
  }

  /* -------------------------------------------------------------- деньги */
  function money(spec) {
    const coins = Math.min(spec.coins || 10, 40);
    const w = 420, h = 130;
    const parts = [];
    const perRow = 10;
    for (let i = 0; i < coins; i++) {
      const r = Math.floor(i / perRow), c = i % perRow;
      const x = 20 + c * 40, y = 20 + r * 46;
      parts.push(`<circle cx="${x + 16}" cy="${y + 16}" r="16" fill="#fbbf24" stroke="#d97706" stroke-width="3"/>`);
      parts.push(text(x + 16, y + 21, "1", { size: 13, anchor: "middle", fill: "#92400e", weight: 900 }));
    }
    parts.push(text(20, h - 4, `${coins} р.`, { size: 16, fill: "#b45309", weight: 900 }));
    return svgWrap(w, h, parts.join(""));
  }

  /* ----------------------------------------------------------- коробки */
  function packages(spec) {
    const boxes = Math.min(spec.boxes || 4, 8);
    const per = Math.min(spec.per_box || 3, 8);
    const target = spec.target_boxes || boxes;
    const w = 470, h = 150;
    const parts = [];
    for (let i = 0; i < boxes; i++) {
      const x = 20 + i * 54;
      const active = i < target;
      parts.push(rect(x, 24, 46, 62, active ? "#fef3c7" : "#f1f5f9", { rx: 8, stroke: active ? "#f59e0b" : "#cbd5e1", sw: 2 }));
      for (let k = 0; k < per; k++) {
        parts.push(`<circle cx="${x + 12 + (k % 2) * 20}" cy="${38 + Math.floor(k / 2) * 16}" r="5" fill="${active ? "#f59e0b" : "#cbd5e1"}"/>`);
      }
      parts.push(text(x + 23, 104, String(i + 1), { size: 12, anchor: "middle", fill: "#64748b" }));
    }
    parts.push(text(20, 134, `В каждой коробке по ${per}. Коробок: ${boxes}`, { size: 14, fill: "#475569", weight: 800 }));
    return svgWrap(w, h, parts.join(""));
  }

  /* -------------------------------------------------------------- путь */
  function pathWidget(spec) {
    const w = 470, h = 160;
    const parts = [];
    parts.push(rect(20, 90, w - 40, 26, "#e2e8f0", { rx: 13 }));
    parts.push(`<line x1="30" y1="103" x2="${w - 30}" y2="103" stroke="#94a3b8" stroke-width="3" stroke-dasharray="14 12"/>`);
    parts.push(text(30, 80, "A", { size: 20, fill: "#4338ca", weight: 900 }));
    parts.push(text(w - 30, 80, "B", { size: 20, fill: "#b45309", weight: 900, anchor: "end" }));
    const facts = [];
    if (spec.s !== undefined) facts.push("s = " + spec.s + " км");
    if (spec.v !== undefined) facts.push("v = " + spec.v + " км/ч");
    if (spec.t !== undefined) facts.push("t = " + spec.t + " ч");
    if (facts.length) parts.push(text(w / 2, 135, facts.join("   ·   "), { size: 15, anchor: "middle", fill: "#334155", weight: 800 }));
    if (spec.v2) {
      parts.push(text(w / 2, 40, `v₁ + v₂ = ${spec.v + spec.v2} км/ч`, { size: 15, anchor: "middle", fill: "#ec4899", weight: 800 }));
    }
    return svgWrap(w, h, parts.join(""));
  }

  /* -------------------------------------------------------------- нули */
  function shift(spec) {
    const n = spec.number || 0;
    const zeros = spec.zeros || 0;
    const shown = zeros >= 0 ? n + "0".repeat(zeros) : String(n).slice(0, zeros);
    const w = 320, h = 100;
    const parts = [];
    parts.push(rect(20, 20, w - 40, 58, "#eef2ff", { rx: 14, stroke: "#6366f1", sw: 2 }));
    parts.push(text(w / 2, 60, shown, { size: 30, anchor: "middle", fill: "#4338ca", weight: 900 }));
    parts.push(text(w / 2, 94, zeros >= 0 ? `приписали ${zeros} нулей` : `убрали ${Math.abs(zeros)} нулей`, { size: 13, anchor: "middle", fill: "#5b6785" }));
    return svgWrap(w, h, parts.join(""));
  }

  /* -------------------------------------------------- таблица умножения */
  function tableMult(spec) {
    const a = spec.a || 3, b = spec.b || 4;
    const size = 11, cell = 30;
    const w = (size + 1) * cell + 20, h = (size + 1) * cell + 40;
    const parts = [];
    for (let i = 0; i <= size; i++) {
      parts.push(rect(10 + i * cell, 10, cell, cell, i === 0 ? "#e0e7ff" : "#f1f5f9", { rx: 5 }));
      parts.push(rect(10, 10 + i * cell, cell, cell, i === 0 ? "#e0e7ff" : "#f1f5f9", { rx: 5 }));
      if (i > 0) {
        parts.push(text(10 + i * cell + cell / 2, 30, i, { size: 13, anchor: "middle", fill: "#475569" }));
        parts.push(text(10 + cell / 2, 10 + i * cell + cell / 2 + 4, i, { size: 13, anchor: "middle", fill: "#475569" }));
      }
    }
    for (let r = 1; r <= size; r++) {
      for (let c = 1; c <= size; c++) {
        const isTarget = r === a && c === b;
        parts.push(rect(10 + c * cell, 10 + r * cell, cell, cell, isTarget ? "#f59e0b" : (r % 2 ? "#fff" : "#f8fafc"), { rx: 4, stroke: "#e2e8f0", sw: 1 }));
        parts.push(text(10 + c * cell + cell / 2, 10 + r * cell + cell / 2 + 4, r * c, { size: 12, anchor: "middle", fill: isTarget ? "#ffffff" : "#64748b", weight: isTarget ? 900 : 600 }));
      }
    }
    parts.push(text(w / 2, h - 6, `${a} × ${b} = ${a * b}`, { size: 15, anchor: "middle", fill: "#b45309", weight: 900 }));
    return svgWrap(w, h, parts.join(""));
  }

  /* --------------------------------------------------------- выражение */
  function expression(spec) {
    const w = 420, h = 100;
    const a = spec.a || 0, b = spec.b || 0, c = spec.c || 0;
    const parts = [];
    parts.push(rect(20, 18, w - 40, 60, "#f8fafc", { rx: 14, stroke: "#e2e8f0", sw: 2 }));
    parts.push(text(w / 2, 58, `${a} + ${b} · ${c}`, { size: 30, anchor: "middle", fill: "#1f2a44", weight: 900 }));
    parts.push(text(w / 2, 92, "Сначала умножение и деление, потом сложение и вычитание", { size: 13, anchor: "middle", fill: "#5b6785" }));
    return svgWrap(w, h, parts.join(""));
  }

  /* ------------------------------------------------------------ лента */
  function timeline(spec) {
    const w = 420, h = 110;
    const parts = [];
    parts.push(`<line x1="30" y1="55" x2="${w - 30}" y2="55" stroke="#cbd5e1" stroke-width="6" stroke-linecap="round"/>`);
    parts.push(`<circle cx="60" cy="55" r="10" fill="#6366f1"/>`);
    parts.push(`<circle cx="${w - 60}" cy="55" r="10" fill="#f59e0b"/>`);
    parts.push(text(60, 34, `${spec.h || 0}:${String(spec.m || 0).padStart(2, "0")}`, { size: 14, anchor: "middle", fill: "#4338ca", weight: 900 }));
    parts.push(text(w - 60, 34, `+${spec.add || 0} мин`, { size: 14, anchor: "middle", fill: "#b45309", weight: 900 }));
    parts.push(text(w / 2, 88, "1 час = 60 минут", { size: 13, anchor: "middle", fill: "#5b6785" }));
    return svgWrap(w, h, parts.join(""));
  }

  /* ---------------------------------------------------------- календарь */
  function calendar(spec) {
    const days = spec.days || 30, month = spec.month || "";
    const cols = 7, rows = Math.ceil(days / cols);
    const cell = 34, w = cols * cell + 20, h = rows * cell + 60;
    const parts = [];
    ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"].forEach((d, i) => {
      parts.push(text(10 + i * cell + cell / 2, 24, d, { size: 12, anchor: "middle", fill: "#64748b" }));
    });
    for (let d = 1; d <= days; d++) {
      const idx = d - 1;
      const r = Math.floor(idx / cols), c = idx % cols;
      parts.push(rect(10 + c * cell, 32 + r * cell, cell - 4, cell - 4, "#f1f5f9", { rx: 6 }));
      parts.push(text(10 + c * cell + (cell - 4) / 2, 32 + r * cell + 20, d, { size: 13, anchor: "middle", fill: "#1f2a44" }));
    }
    parts.push(text(w / 2, h - 8, month + ": " + days + " дней", { size: 15, anchor: "middle", fill: "#4338ca", weight: 900 }));
    return svgWrap(w, h, parts.join(""));
  }

  const RENDERERS = {
    place_value: placeValue,
    number_line: numberLine,
    groups: groups,
    array: array,
    column: column,
    fraction_circle: fractionCircle,
    fraction_bar: fractionBar,
    balance: balance,
    clock: clock,
    ruler: ruler,
    scale: scale,
    shapes: shapes,
    area_grid: areaGrid,
    table: tableWidget,
    chart: chart,
    money: money,
    packages: packages,
    path: pathWidget,
    shift: shift,
    table_mult: tableMult,
    expression: expression,
    timeline: timeline,
    calendar: calendar,
  };

  function render(spec) {
    if (!spec || !spec.type) return "";
    const fn = RENDERERS[spec.type];
    if (!fn) return "";
    try {
      return fn(spec);
    } catch (e) {
      return "";
    }
  }

  global.Widgets = { render, types: Object.keys(RENDERERS) };
})(window);
