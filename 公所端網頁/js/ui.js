/* 天相星 公所端：畫面小工具 */
window.SA = window.SA || {};

SA.ui = (function () {
  const BLANK = '—';

  // h('div', {class:'x', onclick:fn}, child, 'text', [children])
  function h(tag, attrs) {
    const el = document.createElement(tag);
    const a = attrs || {};
    for (const k in a) {
      const v = a[k];
      if (v === null || v === undefined || v === false) continue;
      if (k === 'class') el.className = v;
      else if (k === 'style' && typeof v === 'object') Object.assign(el.style, v);
      else if (k.startsWith('on') && typeof v === 'function') el.addEventListener(k.slice(2), v);
      else if (k === 'html') el.innerHTML = v; // 僅用於本程式內寫死的字串
      else if (v === true) el.setAttribute(k, '');
      else el.setAttribute(k, v);
    }
    for (let i = 2; i < arguments.length; i++) append(el, arguments[i]);
    return el;
  }
  function append(el, c) {
    if (c === null || c === undefined || c === false) return;
    if (Array.isArray(c)) return c.forEach((x) => append(el, x));
    el.appendChild(c instanceof Node ? c : document.createTextNode(String(c)));
  }

  const isNum = (v) => typeof v === 'number' && isFinite(v);
  const val = (v) => (v === null || v === undefined || v === '' ? BLANK : v);
  const num = (v, d) => (isNum(v) ? v.toLocaleString('zh-TW', { maximumFractionDigits: d ?? 0 }) : BLANK);
  const pct = (v, d) => (isNum(v) ? (v * 100).toFixed(d ?? 1) + '%' : BLANK);
  const pp = (v) => (isNum(v) ? v + '%' : BLANK);
  function date(d, withWeek) {
    if (!d) return BLANK;
    const x = d instanceof Date ? d : new Date(d);
    if (isNaN(x)) return BLANK;
    const s = (x.getMonth() + 1) + '/' + x.getDate();
    return withWeek ? s + '（' + '日一二三四五六'[x.getDay()] + '）' : s;
  }
  function datetime(d) {
    if (!d) return BLANK;
    const x = new Date(d); if (isNaN(x)) return BLANK;
    return (x.getMonth() + 1) + '/' + x.getDate() + ' ' + String(x.getHours()).padStart(2, '0') + ':' + String(x.getMinutes()).padStart(2, '0');
  }

  function gradeChip(g, opts) {
    const G = SA.config.grades[g];
    if (!G) return h('span', { class: 'chip chip-blank' }, '分級 ' + BLANK);
    return h('span', { class: 'chip chip-' + g.toLowerCase().replace(/_/g, '-') + (opts && opts.reference ? ' chip-ref' : '') }, G.label + (opts && opts.reference ? '（參考）' : ''));
  }
  function levelChip(l) {
    if (!l) return h('span', { class: 'lv lv-blank', title: '系統等級未提供' }, BLANK);
    return h('span', { class: 'lv lv-' + { '甲': 'a', '乙': 'b', '丙': 'c' }[l], title: SA.config.levels[l].name }, l);
  }

  function card(title, body, opts) {
    const o = opts || {};
    return h('section', { class: 'card' + (o.cls ? ' ' + o.cls : '') },
      title ? h('div', { class: 'card-head' }, h('h2', null, title), o.right || null) : null,
      o.sub ? h('p', { class: 'card-sub' }, o.sub) : null,
      body);
  }

  function empty(text, extra) {
    return h('div', { class: 'empty' }, h('p', null, text || '尚無資料'), extra || null);
  }

  function table(cols, rows, opts) {
    const o = opts || {};
    const thead = h('thead', null, h('tr', null, cols.map((c) => h('th', { class: c.cls || null, scope: 'col' }, c.label))));
    const tbody = h('tbody');
    if (!rows.length) {
      tbody.appendChild(h('tr', { class: 'empty-row' }, h('td', { colspan: cols.length }, o.emptyText || '尚無資料（資料接口未接入）')));
    } else {
      rows.forEach((r, i) => tbody.appendChild(h('tr', { class: o.rowClass ? o.rowClass(r) : null, onclick: o.onRow ? () => o.onRow(r) : null, tabindex: o.onRow ? '0' : null, onkeydown: o.onRow ? (e) => { if (e.key === 'Enter') o.onRow(r); } : null },
        cols.map((c) => h('td', { class: c.cls || null, 'data-label': c.label }, c.render ? c.render(r, i) : val(r[c.key]))))));
    }
    return h('div', { class: 'table-wrap' }, h('table', { class: 'tbl' + (o.onRow ? ' tbl-click' : '') }, thead, tbody));
  }

  // 損失區間條：0–100%，標出 10%、20%、40% 門檻
  function intervalBar(iv, crop) {
    const t = SA.rules.thresholds(crop);
    const T = SA.config.grade.lossThreshold;
    const ok = iv && isNum(iv.p10) && isNum(iv.p90);
    const bar = h('div', { class: 'ivbar', role: 'img', 'aria-label': ok ? '損失區間 ' + iv.p10 + '% 至 ' + iv.p90 + '%' : '損失區間未提供' },
      h('div', { class: 'ivbar-track' }),
      h('div', { class: 'ivbar-mark m-low', style: { left: t.aNotMetUpperMax + '%' }, title: 'A 未達標上限 ' + t.aNotMetUpperMax + '%' }),
      h('div', { class: 'ivbar-mark m-thr', style: { left: T + '%' }, title: '救助門檻 ' + T + '%' }),
      h('div', { class: 'ivbar-mark m-high', style: { left: t.aMetLowerMin + '%' }, title: 'A 達標下限 ' + t.aMetLowerMin + '%' }),
      ok ? h('div', { class: 'ivbar-range', style: { left: iv.p10 + '%', width: Math.max(1, iv.p90 - iv.p10) + '%' } }) : null,
      ok && isNum(iv.p50) ? h('div', { class: 'ivbar-mid', style: { left: iv.p50 + '%' } }) : null);
    return bar;
  }
  function intervalText(iv) {
    if (!iv || !isNum(iv.p10)) return BLANK;
    return iv.p10 + '–' + iv.p90 + '%';
  }

  // 提示訊息
  let toastTimer;
  function toast(msg, kind) {
    let el = document.getElementById('toast');
    if (!el) { el = h('div', { id: 'toast', role: 'status', 'aria-live': 'polite' }); document.body.appendChild(el); }
    el.textContent = msg;
    el.className = 'show ' + (kind || '');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { el.className = ''; }, 3600);
  }
  function queuedToast(what) {
    toast(what + '：已存入本機暫存區（資料接口未接入）', 'info');
  }

  // 確認對話框（不用瀏覽器 alert/confirm）
  function confirmDialog(title, body, okText, opts) {
    return new Promise((resolve) => {
      const o = opts || {};
      const close = (v) => { overlay.remove(); document.removeEventListener('keydown', onKey); resolve(v); };
      const onKey = (e) => { if (e.key === 'Escape') close(false); };
      const okBtn = h('button', { class: 'btn ' + (o.danger ? 'btn-danger' : 'btn-primary'), onclick: () => close(true) }, okText || '確認');
      const overlay = h('div', { class: 'overlay', onclick: (e) => { if (e.target === overlay) close(false); } },
        h('div', { class: 'dialog', role: 'dialog', 'aria-modal': 'true', 'aria-label': title },
          h('h3', null, title),
          typeof body === 'string' ? h('p', null, body) : body,
          h('div', { class: 'dialog-actions' }, h('button', { class: 'btn', onclick: () => close(false) }, '取消'), okBtn)));
      document.body.appendChild(overlay);
      document.addEventListener('keydown', onKey);
      okBtn.focus();
    });
  }

  function download(filename, text, mime) {
    const blob = new Blob([text], { type: (mime || 'text/plain') + ';charset=utf-8' });
    const a = h('a', { href: URL.createObjectURL(blob), download: filename });
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 2000);
  }
  function csv(headers, rows) {
    const q = (s) => { s = s === null || s === undefined ? '' : String(s); return /[",\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s; };
    return '﻿' + [headers.map(q).join(',')].concat(rows.map((r) => r.map(q).join(','))).join('\n');
  }

  function kv(pairs) {
    return h('dl', { class: 'kv' }, pairs.map(([k, v]) => [h('dt', null, k), h('dd', null, v === null || v === undefined || v === '' ? BLANK : v)]));
  }

  function pageHead(kicker, title, right) {
    return h('header', { class: 'page-head' }, h('div', null, kicker ? h('p', { class: 'kicker' }, kicker) : null, h('h1', null, title)), right || null);
  }

  function notConnected() {
    if (SA.api.CONNECTED) return null;
    if (SA.api.mode() === 'test') return h('p', { class: 'nc nc-test' }, h('span', { class: 'dot' }), '測試資料庫：案件與圖資皆為虛構，操作存入本機暫存區');
    return h('p', { class: 'nc' }, h('span', { class: 'dot' }), '資料接口未接入：數據留白，操作先存入本機暫存區');
  }

  /*
   * 色塊地圖（SVG，不需外部圖資）
   * spec = { polys:[{ ring:[[lon,lat],...], fill, stroke, dash, title, label }],
   *          points:[{ lat, lon, label, fill, r }], lines:[{ pts:[{lat,lon}], stroke }], height, empty }
   */
  function mapSvg(spec) {
    const NS = 'http://www.w3.org/2000/svg';
    const s = (tag, attrs, kids) => { const el = document.createElementNS(NS, tag); for (const k in attrs) if (attrs[k] !== null && attrs[k] !== undefined) el.setAttribute(k, attrs[k]); (kids || []).forEach((c) => c && el.appendChild(c)); return el; };
    const polys = spec.polys || [], pts = spec.points || [], lines = spec.lines || [];
    const all = [];
    polys.forEach((p) => p.ring.forEach(([lon, lat]) => all.push({ lon, lat })));
    pts.forEach((p) => all.push(p));
    lines.forEach((l) => l.pts.forEach((p) => all.push(p)));
    const W = 800, H = spec.height || 480;
    if (!all.length) return h('div', { class: 'map-ph', role: 'img', 'aria-label': '地圖' }, spec.empty || '尚無圖資');
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    const k = Math.cos(all[0].lat * Math.PI / 180);
    all.forEach((p) => { const x = p.lon * k, y = p.lat; minX = Math.min(minX, x); maxX = Math.max(maxX, x); minY = Math.min(minY, y); maxY = Math.max(maxY, y); });
    const pad = 28, sw = Math.max(maxX - minX, 1e-5), sh = Math.max(maxY - minY, 1e-5);
    const sc = Math.min((W - 2 * pad) / sw, (H - 2 * pad) / sh);
    const ox = (W - sw * sc) / 2, oy = (H - sh * sc) / 2;
    const X = (lon) => ox + (lon * k - minX) * sc, Y = (lat) => H - (oy + (lat - minY) * sc);
    const kids = [s('rect', { x: 0, y: 0, width: W, height: H, fill: '#eef0e8' })];
    polys.forEach((p) => {
      const d = p.ring.map(([lon, lat], i) => (i ? 'L' : 'M') + X(lon).toFixed(1) + ' ' + Y(lat).toFixed(1)).join(' ') + 'Z';
      const el = s('path', { d, fill: p.fill || 'none', stroke: p.stroke || '#1b2233', 'stroke-width': p.width || 1.2, 'stroke-dasharray': p.dash || null, 'fill-opacity': p.opacity ?? 0.85 });
      if (p.title) el.appendChild(s('title', {}, [document.createTextNode(p.title)]));
      kids.push(el);
    });
    lines.forEach((l) => kids.push(s('polyline', { points: l.pts.map((p) => X(p.lon).toFixed(1) + ',' + Y(p.lat).toFixed(1)).join(' '), fill: 'none', stroke: l.stroke || '#1f4fae', 'stroke-width': 2, 'stroke-dasharray': l.dash || null })));
    pts.forEach((p) => {
      const g = s('g', {}, [
        s('circle', { cx: X(p.lon), cy: Y(p.lat), r: p.r || 7, fill: p.fill || '#15213b', stroke: '#fff', 'stroke-width': 2 }),
        p.label ? s('text', { x: X(p.lon) + 10, y: Y(p.lat) + 4, 'font-size': 13, fill: '#1b2233', 'font-weight': 700 }, [document.createTextNode(p.label)]) : null
      ]);
      if (p.title) g.appendChild(s('title', {}, [document.createTextNode(p.title)]));
      kids.push(g);
    });
    polys.filter((p) => p.label).forEach((p) => {
      const cx = p.ring.reduce((a, q) => a + q[0], 0) / p.ring.length, cy = p.ring.reduce((a, q) => a + q[1], 0) / p.ring.length;
      kids.push(s('text', { x: X(cx), y: Y(cy) + 4, 'font-size': 12, 'text-anchor': 'middle', fill: '#1b2233' }, [document.createTextNode(p.label)]));
    });
    return s('svg', { viewBox: '0 0 ' + W + ' ' + H, class: 'map', role: 'img', 'aria-label': spec.ariaLabel || '色塊地圖（示意）' }, kids);
  }

  function legend(items) {
    return h('ul', { class: 'map-legend' }, items.map(([color, label, dash]) => h('li', null, h('span', { class: 'sw', style: { background: dash ? 'transparent' : color, borderColor: color, borderStyle: dash ? 'dashed' : 'solid' } }), label)));
  }

  function tabs(items, active, onChange) {
    return h('div', { class: 'tabs', role: 'tablist' }, items.map((t) => h('button', {
      class: 'tab' + (t.key === active ? ' on' : ''), role: 'tab', 'aria-selected': t.key === active ? 'true' : 'false',
      onclick: () => onChange(t.key)
    }, t.label, t.count !== undefined ? h('span', { class: 'tab-n' }, val(t.count)) : null)));
  }

  return { h, BLANK, val, num, pct, pp, date, datetime, gradeChip, levelChip, card, empty, table, intervalBar, intervalText, toast, queuedToast, confirmDialog, download, csv, kv, pageHead, notConnected, tabs, isNum, mapSvg, legend };
})();
