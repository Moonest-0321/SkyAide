/*
 * 天相星 農民端（表 21、表 22、表 23、三、1(4)、三、4(8)）
 * 設計原則：每一步對應現行法定程序與文件；不顯示 A／B／C 代號，改用白話並說明原因與下一步；
 * 乙等時只收到補件提醒，其他結果等公所勘查後通知；大字級、大按鈕；每個畫面註明以公所認定為準。
 */
(function () {
  const { h, val, num, date, datetime } = SA.ui;
  const CFG = SA.config;
  const FKEY = 'skyaide.farmer.id';
  const main = document.getElementById('farmer');
  const S = { farmerId: null, farmer: null, cases: [], event: null, dl: null, drafts: {} };

  const readId = () => { try { return localStorage.getItem(FKEY); } catch (e) { return null; } };
  const saveId = (v) => { try { localStorage.setItem(FKEY, v); } catch (e) { /* 無法保存 */ } };
  const go = (hash) => { location.hash = hash; };
  const caseOf = (id) => S.cases.find((c) => c.id === id) || null;
  const fieldOf = (id) => (S.farmer && S.farmer.fields.find((f) => f.id === id || f.caseId === id)) || null;
  const officeName = () => '受災地公所';
  // 甲等類別的 A 級：系統依存證報告直接進入申報，農民不填受災率；農民或公所提出異議才改變
  const isAuto = (c) => !!c && c.level === '甲' && (c.grade === 'A_MET' || c.grade === 'A_NOT_MET');

  // ---------- 共用元件 ----------
  const page = (title, sub) => { main.appendChild(h('header', { class: 'fm-head' }, h('h1', null, title), sub ? h('p', null, sub) : null)); };
  const box = (...kids) => { const el = h('section', { class: 'fm-card' }, kids); main.appendChild(el); return el; };
  const back = (href, label) => main.appendChild(h('a', { class: 'fm-back', href }, '← ' + (label || '返回')));
  const big = (label, href, kind) => h('a', { class: 'fm-btn ' + (kind || ''), href }, label);
  const official = () => main.appendChild(h('p', { class: 'fm-official' }, '以上為衛星初步判讀，能不能領、領多少，以公所認定為準。'));
  const testBanner = () => (SA.api.mode() === 'test' ? h('p', { class: 'fm-test' }, '測試資料：人名、地號、影像都是虛構的') : h('p', { class: 'fm-test' }, '資料接口未接入：數據留白'));
  const daysLeft = (d) => (d ? SA.rules.daysBetween(new Date(), d) : null);

  // ---------- 白話結果（三、1(4)：四類結果各說明原因與下一步；乙、丙等不同） ----------
  async function plain(c, f) {
    if (f && f.unappliedDamaged) return { tone: 'met', title: '衛星看到明顯受損，可以申請', reason: '颱風前後影像比對，這塊田受損明顯，但還沒有申請。', next: [['確認預填申請', '#/apply/' + f.id]] };
    if (!c) return { tone: 'none', title: '—', reason: '', next: [] };
    const iv = c.interval || {};
    const ivt = SA.ui.isNum(iv.p10) ? iv.p10 + '%–' + iv.p90 + '%' : '—';
    const [app, dec, supp, ap] = await Promise.all([SA.api.getLocalApplication(c.id), SA.api.getLocalDecision(c.id), SA.api.getLocalSupplement(c.id), SA.api.getLocalAppeal(c.id)]);
    const nextApply = app ? ['看案件進度', '#/progress/' + c.id] : ['確認預填申請', '#/apply/' + c.id];
    const out = { app, dec };
    if (dec && dec.result !== 'visit') return Object.assign(out, { tone: dec.result === 'approve' ? 'met' : 'notmet', title: dec.result === 'approve' ? '公所已核定' : '公所判定不予救助', reason: dec.result === 'approve' ? '核定受害率 ' + val(dec.rate) + '%、面積 ' + val(dec.areaHa) + ' 公頃。' : '可在收到通知後 7 日內申請復查。', next: [['看核定結果與復查', '#/result/' + c.id]] });

    if (c.level === '丙') return Object.assign(out, { tone: 'none', title: '公所會依現行規定勘查', reason: '這類作物的衛星判讀還在收集資料階段，颱風前後的紀錄已經保存。', next: [nextApply] });
    if (c.grade === 'C') {
      const need = (c.reasons || []).map((r) => (CFG.reasonRoute[r] || {}).note || r).join('；');
      return Object.assign(out, { tone: 'c', title: supp ? '補充資料已送出' : '請補充資料', reason: supp ? '公所會重新檢核。' : '衛星影像不足以判斷：' + need + '。', next: [supp ? ['看補件內容', '#/supp/' + c.id] : ['補充資料', '#/supp/' + c.id], nextApply] });
    }
    if (c.level === '乙') return Object.assign(out, { tone: 'none', title: '等公所勘查後通知', reason: '這類作物目前由公所依現行規定勘查，衛星結果提供公所參考。', next: [nextApply] });
    if (isAuto(c) && ap && ap.kind === 'objection') return Object.assign(out, { tone: 'b', title: '已提出異議', reason: '公所會到田裡確認，結果以公所勘查為準。', next: [['看案件進度', '#/progress/' + c.id]] });
    if (c.grade === 'A_MET') return Object.assign(out, { tone: 'met', title: '受損明顯', reason: '颱風前後影像比對，損失估計 ' + ivt + '，超過 20% 門檻。系統已依存證報告自動申報，你不需要填受災率。', next: [['看申報內容', '#/auto/' + c.id], ['看案件進度', '#/progress/' + c.id]] });
    if (c.grade === 'A_NOT_MET') return Object.assign(out, { tone: 'notmet', title: '影像顯示未達 20%', reason: '颱風前後影像比對，損失估計 ' + ivt + '。系統已依存證報告自動申報，判定未達 20%。不同意可以提出異議。', next: [['看判定依據、提出異議', '#/notmet/' + c.id]] });
    if (c.grade === 'B') return Object.assign(out, { tone: 'b', title: '需公所到場確認', reason: '損失估計 ' + ivt + '，接近 20% 門檻，影像無法直接判定。送件後公所會到田裡確認。', next: [nextApply] });
    return Object.assign(out, { tone: 'none', title: '—', reason: '', next: [nextApply] });
  }

  function resultCard(f, p) {
    return h('article', { class: 'fm-result tone-' + p.tone },
      h('p', { class: 'fm-land' }, val(f.landNo), '　', val(f.crop), '　', f.areaHa ? num(f.areaHa, 2) + ' 公頃' : ''),
      h('h2', null, p.title),
      p.reason ? h('p', null, p.reason) : null,
      h('div', { class: 'fm-actions' }, p.next.map(([t, href], i) => big(t, href, i === 0 ? 'primary' : ''))));
  }

  // ---------- 我的田（平時紀錄） ----------
  async function home() {
    page('我的田', S.farmer ? val(S.farmer.name) : '');
    main.appendChild(testBanner());
    if (!S.farmer) { box(h('p', null, '還沒有登錄的田。'), big('登錄我的田', '#/register', 'primary')); return; }
    if (S.event) {
      const ph = phase();
      main.appendChild(h('a', { class: 'fm-banner', href: ph.href }, h('strong', null, ph.title), h('span', null, ph.sub)));
    }
    const reg = await SA.api.localRegistered(S.farmerId);
    const list = h('div', { class: 'fm-fields' });
    for (const f of S.farmer.fields) {
      const st = f.baselineLocked === true ? ['已鎖定災前基準', 'ok'] : f.baselineLocked === false ? ['待公所確認', 'wait'] : ['—', 'wait'];
      list.appendChild(h('a', { class: 'fm-field', href: '#/field/' + f.id },
        h('span', { class: 'fm-swatch', style: { background: f.crop === '水稻' ? '#b9c96a' : f.crop === '香蕉' ? '#7fae5a' : '#5d9154' }, 'aria-hidden': 'true' }),
        h('span', { class: 'fm-field-b' }, h('strong', null, val(f.landNo)), h('small', null, val(f.crop) + '・' + num(f.areaHa, 2) + ' 公頃')),
        h('span', { class: 'fm-chip ' + st[1] }, st[0])));
    }
    reg.forEach((r) => list.appendChild(h('div', { class: 'fm-field' },
      h('span', { class: 'fm-swatch', style: { background: '#c9cdd4' }, 'aria-hidden': 'true' }),
      h('span', { class: 'fm-field-b' }, h('strong', null, val(r.landNo)), h('small', null, val(r.crop) + '・' + val(r.declaredHa) + ' 公頃')),
      h('span', { class: 'fm-chip ' + (r.scopeCheck ? 'warn' : 'wait') }, r.scopeCheck ? '範圍需確認' : '待公所確認'))));
    main.appendChild(list);
    main.appendChild(big('登錄新的田', '#/register', ''));
    main.appendChild(h('p', { class: 'fm-note' }, '每年 1 月綠色環境給付申報時，公所會一併確認範圍。確認後鎖定為災前基準，颱風後不必再量面積。'));
  }

  function phase() {
    const now = new Date();
    if (!S.dl) return { title: '颱風警報', sub: '看哪幾塊田在風雨範圍內 →', href: '#/alert' };
    if (now <= S.dl.applyEnd) return { title: '現金救助申請中', sub: '申請截止 ' + date(S.dl.applyEnd, true) + '，還有 ' + daysLeft(S.dl.applyEnd) + ' 天 →', href: '#/disaster' };
    if (now <= S.dl.surveyEnd) return { title: '公所勘查中', sub: '勘查截止 ' + date(S.dl.surveyEnd, true) + ' →', href: '#/disaster' };
    return { title: '救助進度', sub: '看案件進度與結果 →', href: '#/disaster' };
  }

  async function fieldDetail(id) {
    const f = fieldOf(id);
    back('#/', '我的田');
    if (!f) { main.appendChild(SA.ui.empty('找不到這塊田')); return; }
    const head = h('header', { class: 'fm-head' }, h('h1', null, val(f.landNo)), h('p', null, val(f.crop) + '・' + num(f.areaHa, 2) + ' 公頃'));
    main.appendChild(head);
    main.appendChild(testBanner());
    box(h('h2', null, '災前基準'), h('p', null, f.baselineLocked ? '已由公所確認並鎖定。颱風後以這個範圍與面積為準。' : '等待公所確認。每年 1 月綠色環境給付申報時一併確認。'),
      f.geometry ? SA.ui.mapSvg({ polys: [{ ring: f.geometry.coordinates[0], fill: '#7fae5a', stroke: '#15213b', width: 2 }], height: 200, ariaLabel: '田區範圍（色塊示意）' }) : null,
      h('p', { class: 'fm-note' }, '田區範圍（色塊示意）'));
    const ser = f.series || [];
    const valid = ser.filter((p) => p.ndvi !== null);
    box(h('h2', null, '衛星累積紀錄'),
      h('p', null, '過去一年 ' + ser.length + ' 次經過，' + valid.length + ' 次看得清楚（其餘被雲遮）。這份紀錄你和系統營運者都無法回頭修改。'),
      spark(ser),
      h('p', { class: 'fm-note' }, '線越高代表植物越茂密；紅線為颱風警報。'),
      h('p', null, '作物異常提醒：', h('strong', null, '目前沒有')));
    if (S.event) {
      const c = caseOf(f.caseId);
      const p = await plain(c, f);
      main.appendChild(h('h2', { class: 'fm-sub' }, '這次颱風'));
      main.appendChild(resultCard(f, p));
      official();
    }
  }

  function spark(ser) {
    const W = 340, H = 110, pad = 8;
    const pts = ser.map((p, i) => ({ x: pad + i * (W - 2 * pad) / Math.max(1, ser.length - 1), y: p.ndvi === null ? null : H - pad - p.ndvi * (H - 2 * pad), d: p.date }));
    const NS = 'http://www.w3.org/2000/svg';
    const s = (t, a) => { const el = document.createElementNS(NS, t); for (const k in a) el.setAttribute(k, a[k]); return el; };
    const svg = s('svg', { viewBox: '0 0 ' + W + ' ' + H, class: 'fm-spark', role: 'img', 'aria-label': '植生時序' });
    svg.appendChild(s('rect', { x: 0, y: 0, width: W, height: H, fill: '#f3f5ef', rx: 8 }));
    let d = '', pen = false;
    pts.forEach((p) => { if (p.y === null) return; d += (pen ? 'L' : 'M') + p.x.toFixed(1) + ' ' + p.y.toFixed(1); pen = true; });
    svg.appendChild(s('path', { d, fill: 'none', stroke: '#2e7d4f', 'stroke-width': 2 }));
    pts.forEach((p) => { if (p.y !== null) svg.appendChild(s('circle', { cx: p.x, cy: p.y, r: 2, fill: '#2e7d4f' })); });
    if (S.event && ser.length) {
      const a = new Date(S.event.alertAt);
      const i = ser.findIndex((p) => new Date(p.date) > a);
      if (i > 0) { const x = pts[i].x; svg.appendChild(s('line', { x1: x, x2: x, y1: 4, y2: H - 4, stroke: '#b23b1e', 'stroke-width': 2 })); }
    }
    return svg;
  }

  // ---------- 五步登錄（表 22） ----------
  const IDENTITIES = [
    { k: '地主', docs: ['土地登記第二類謄本（任何人皆可申請）'] },
    { k: '三七五租約', docs: ['三七五租約', '土地登記第二類謄本'] },
    { k: '一般承租', docs: ['租約', '土地登記第二類謄本'] },
    { k: '借用親友的地', docs: ['使用同意書', '土地登記第二類謄本'] },
    { k: '承租公有地', docs: ['公有地租約', '土地登記第二類謄本'] },
    { k: '養殖魚塭', docs: ['養殖漁業登記證或放養申報', '土地登記第二類謄本'] }
  ];
  function register() {
    const st = S.drafts.reg || (S.drafts.reg = { step: 1, identity: null, files: [], declaredHa: '', crop: '', startYear: '', proofs: [], name: S.farmer ? S.farmer.name : '', idno: '', phone: '', consent: false });
    main.innerHTML = '';
    page('登錄我的田', '第 ' + st.step + ' 步，共 5 步');
    main.appendChild(h('ol', { class: 'fm-steps' }, ['身分', '使用權文件', '田區範圍', '作物', '個資同意'].map((t, i) => h('li', { class: i + 1 < st.step ? 'done' : i + 1 === st.step ? 'on' : null }, t))));
    const warn = h('p', { class: 'fm-warn', role: 'alert' });
    const nav = (canNext, onNext) => h('div', { class: 'fm-actions' },
      st.step > 1 ? h('button', { class: 'fm-btn', onclick: () => { st.step--; register(); } }, '上一步') : big('取消', '#/', ''),
      h('button', { class: 'fm-btn primary', onclick: async () => { const msg = canNext(); if (msg) { warn.textContent = msg; return; } if (onNext) await onNext(); else { st.step++; register(); } } }, st.step === 5 ? '送交公所確認' : '下一步'));

    if (st.step === 1) {
      box(h('h2', null, '你和這塊地的關係'), h('p', { class: 'fm-note' }, '不必是地主，只要能證明實際耕作。地籍圖由天相星向國土測繪中心取得。'),
        h('div', { class: 'fm-options' }, IDENTITIES.map((it) => h('label', { class: 'fm-opt' + (st.identity === it.k ? ' on' : '') },
          h('input', { type: 'radio', name: 'idt', checked: st.identity === it.k ? true : null, onchange: () => { st.identity = it.k; register(); } }),
          h('span', null, h('strong', null, it.k), h('small', null, '要準備：' + it.docs.join('、')))))));
      main.appendChild(warn); main.appendChild(nav(() => (st.identity ? '' : '請選擇身分')));
    }
    if (st.step === 2) {
      const it = IDENTITIES.find((x) => x.k === st.identity);
      const out = h('div');
      const showRead = () => { out.innerHTML = ''; if (!st.files.length) return; out.appendChild(SA.ui.kv([['地段地號', SA.api.mode() === 'test' ? '竹崎段 0455（測試）' : null], ['本筆面積 × 持分', SA.api.mode() === 'test' ? '0.9200 × 1/1 ＝ 0.9200 公頃（測試）' : null], ['所有權人', SA.api.mode() === 'test' ? '○○○（測試）' : null]])); out.appendChild(h('p', { class: 'fm-note' }, '系統自動讀出並比對；有錯可在下一步更正，由公所確認。')); };
      box(h('h2', null, '拍照上傳文件'), h('p', null, '要準備：' + it.docs.join('、')), h('p', { class: 'fm-note' }, '第二類謄本任何人都可以到地政事務所申請，不需要地主同意。文件和申請救助時相同，不必重複準備。'),
        h('label', { class: 'fm-file' }, '選擇或拍攝文件', h('input', { type: 'file', accept: 'image/*,application/pdf', multiple: true, onchange: (e) => { st.files = Array.from(e.target.files).map((f) => f.name); showRead(); } })),
        out);
      showRead();
      main.appendChild(warn); main.appendChild(nav(() => (st.files.length ? '' : '請上傳文件')));
    }
    if (st.step === 3) {
      const cap = 0.92, roadPond = 0.06, plant = +(cap * (1 - roadPond)).toFixed(4);
      const c = { lat: 23.526, lon: 120.549 };
      const r = (k) => { const dLat = 0.00045 * k, dLon = 0.0006 * k; return [[c.lon - dLon, c.lat - dLat], [c.lon + dLon, c.lat - dLat], [c.lon + dLon, c.lat + dLat], [c.lon - dLon, c.lat + dLat], [c.lon - dLon, c.lat - dLat]]; };
      const inp = h('input', { type: 'number', step: '0.0001', min: '0', inputmode: 'decimal', value: st.declaredHa || plant, 'aria-label': '申報種植面積' });
      box(h('h2', null, '確認田區範圍'),
        SA.ui.mapSvg({ polys: [{ ring: r(1), fill: 'none', stroke: '#15213b', width: 2.5, title: '地籍外框' }, { ring: r(0.94), fill: '#7fae5a', stroke: '#2e7d4f', title: '種植範圍' }, { ring: [[c.lon + 0.00042, c.lat + 0.0003], [c.lon + 0.0006, c.lat + 0.0003], [c.lon + 0.0006, c.lat + 0.00045], [c.lon + 0.00042, c.lat + 0.00045], [c.lon + 0.00042, c.lat + 0.0003]], fill: '#8fb7e3', stroke: '#2f6fdb', title: '水塘' }], height: 220, ariaLabel: '田區範圍（色塊示意）' }),
        SA.ui.legend([['#15213b', '地籍外框', true], ['#7fae5a', '種植範圍'], ['#8fb7e3', '農路、水塘（扣除）']]),
        SA.ui.kv([['可申報上限', cap + ' 公頃（本筆面積 × 持分）'], ['扣除農路水塘', (roadPond * 100) + '%'], ['種植範圍', plant + ' 公頃']]),
        h('label', { class: 'fm-field-in' }, '申報種植面積（公頃）', inp),
        h('label', { class: 'fm-check' }, h('input', { type: 'checkbox', checked: st.partial ? true : null, onchange: (e) => { st.partial = e.target.checked; } }), '只租其中一部分，或地籍對不上'));
      main.appendChild(warn);
      main.appendChild(nav(() => { const v = parseFloat(inp.value); if (!(v > 0)) return '請填申報面積'; if (v > cap) return '申報面積不得超過本筆面積 × 持分（' + cap + ' 公頃）'; st.declaredHa = v; st.landNo = '竹崎段 0455（測試）'; return ''; }));
    }
    if (st.step === 4) {
      const crop = h('select', { 'aria-label': '作物' }, h('option', { value: '' }, '選擇作物'), ['麻竹筍', '香蕉', '水稻', '木瓜', '竹', '其他'].map((x) => h('option', { value: x, selected: st.crop === x ? true : null }, x)));
      const yr = h('input', { type: 'number', min: '1950', max: String(new Date().getFullYear()), value: st.startYear, 'aria-label': '種植起始年' });
      const proofs = ['綠色環境給付收執聯', '上次救助申請表', '產銷履歷', '農業部 App 照片'];
      box(h('h2', null, '作物與佐證'),
        h('label', { class: 'fm-field-in' }, '作物', crop), h('label', { class: 'fm-field-in' }, '從哪一年開始種', yr),
        h('p', null, '有沒有文件可以證明？（可複選）'),
        h('div', { class: 'fm-options' }, proofs.map((p) => h('label', { class: 'fm-check' }, h('input', { type: 'checkbox', checked: st.proofs.includes(p) ? true : null, onchange: (e) => { st.proofs = e.target.checked ? st.proofs.concat([p]) : st.proofs.filter((x) => x !== p); } }), p))),
        h('p', { class: 'fm-note' }, '沒有文件也可以登錄，會標示「自行申報」，經公所確認後才算數。切結書不能當作證明。'));
      main.appendChild(warn);
      main.appendChild(nav(() => { if (!crop.value) return '請選擇作物'; st.crop = crop.value; st.startYear = yr.value; return ''; }));
    }
    if (st.step === 5) {
      const n = h('input', { type: 'text', value: st.name, 'aria-label': '姓名' });
      const id = h('input', { type: 'text', value: st.idno, 'aria-label': '身分證字號', autocomplete: 'off' });
      const ph = h('input', { type: 'tel', value: st.phone, 'aria-label': '手機' });
      const ok = h('input', { type: 'checkbox', checked: st.consent ? true : null });
      box(h('h2', null, '身分與個資同意'),
        h('label', { class: 'fm-field-in' }, '姓名', n), h('label', { class: 'fm-field-in' }, '身分證字號', id), h('label', { class: 'fm-field-in' }, '手機', ph),
        h('div', { class: 'fm-consent' },
          h('p', null, h('strong', null, '用途：'), '建立災前基準、颱風後判讀與預填救助申請。'),
          h('p', null, h('strong', null, '提供對象：'), '限受災地公所及縣市政府。'),
          h('p', null, h('strong', null, '你的權利：'), '可以查詢、更正或要求刪除。'),
          h('p', null, '系統不保存銀行或農會帳號。')),
        h('label', { class: 'fm-check' }, ok, '我已了解並同意'));
      main.appendChild(warn);
      main.appendChild(nav(() => { if (!n.value.trim() || !id.value.trim() || !ph.value.trim()) return '請填姓名、身分證字號與手機'; if (!ok.checked) return '請勾選同意'; return ''; }, async () => {
        await SA.api.registerField({ farmerId: S.farmerId, identity: st.identity, files: st.files, landNo: st.landNo, declaredHa: st.declaredHa, scopeCheck: !!st.partial, crop: st.crop, startYear: st.startYear, proofs: st.proofs, proofType: st.proofs.length ? '有文件佐證' : '自行申報' });
        S.drafts.reg = null;
        SA.ui.toast('已送交公所確認');
        go('#/');
      }));
    }
  }

  // ---------- 警報（表 23-1） ----------
  function alertPage() {
    back('#/disaster', '颱風過後');
    page('颱風警報', S.event ? val(S.event.name) + '・' + datetime(S.event.alertAt) : '');
    main.appendChild(testBanner());
    box(h('h2', null, '這幾塊田在風雨範圍內'), h('ul', { class: 'fm-list' }, (S.farmer ? S.farmer.fields : []).map((f) => h('li', null, val(f.landNo) + '　' + val(f.crop)))));
    box(h('h2', null, '安全的時候再拍照'),
      h('p', null, '風雨過後、確定安全時，用農業部「農產業天然災害現地照相 App」拍照：'),
      h('ul', { class: 'fm-list' }, h('li', null, '遠拍一張：看得到整塊田'), h('li', null, '近拍一張：看得到受損的作物'), h('li', null, '在 App 裡直接拍，不要從相簿匯入')),
      h('p', { class: 'fm-strong' }, '路沒通、坡地不穩時不要進田。颱風前的衛星紀錄已經保存。'));
  }

  // ---------- 災後：公告與期限、每塊田的結果（表 23-2、表 21） ----------
  async function disaster() {
    page('颱風過後', S.event ? val(S.event.name) : '目前沒有公告');
    main.appendChild(testBanner());
    if (!S.event) { box(h('p', null, '目前沒有颱風警報或救助公告。')); return; }
    const left = S.dl ? daysLeft(S.dl.applyEnd) : null;
    box(h('h2', null, '救助公告與期限'),
      SA.ui.kv([['公告地區與品項', val(S.event.area) + '　' + (S.event.crops || []).join('、')], ['申請截止', S.dl ? date(S.dl.applyEnd, true) + (left >= 0 ? '（還有 ' + left + ' 天）' : '（已截止）') : null], ['送件地點', officeName() + '農業課'], ['損失門檻', '損失 20% 以上']]),
      h('a', { class: 'fm-link', href: '#/alert' }, '颱風警報與拍照提醒 →'));
    main.appendChild(h('h2', { class: 'fm-sub' }, '每塊田的結果'));
    if (!S.farmer) { main.appendChild(SA.ui.empty('尚無資料')); return; }
    for (const f of S.farmer.fields) main.appendChild(resultCard(f, await plain(caseOf(f.caseId), f)));
    official();
  }

  // ---------- 補充資料（表 21） ----------
  async function supp(id) {
    const c = caseOf(id);
    back('#/disaster', '每塊田的結果');
    page('補充資料', c ? val(c.landNo) + '　' + val(c.crop) : '');
    main.appendChild(testBanner());
    if (!c) { main.appendChild(SA.ui.empty('找不到案件')); return; }
    const [done, drone, notice] = await Promise.all([SA.api.getLocalSupplement(c.id), SA.api.getLocalDroneCase(c.id), SA.api.getLocalNotice(c.id)]);
    if (drone) main.appendChild(h('p', { class: 'fm-alert' }, '公所已安排無人機補拍這塊田，請不要上山拍照。'));
    const reasons = c.reasons || [];
    box(h('h2', null, '為什麼要補'), h('ul', { class: 'fm-list' }, reasons.map((r) => h('li', null, (CFG.reasonRoute[r] || {}).note || r))),
      h('h2', null, '要補什麼'), h('ul', { class: 'fm-list' }, reasons.map((r) => (CFG.reasonRoute[r] || {}).supplement || r).filter((v, i, a) => a.indexOf(v) === i).map((x) => h('li', null, x))),
      notice && notice.content && notice.content.due ? h('p', { class: 'fm-strong' }, '請在 ' + date(notice.content.due, true) + ' 前補件') : h('p', { class: 'fm-note' }, '期限內沒有補件，公所會依人力安排無人機或到場確認。'));
    if (done) {
      box(h('h2', null, '已送出'), SA.ui.kv([['送出時間', datetime(done.at)], ['照片', (done.photos || []).join('、') || '—'], ['更正作物', done.crop || '—'], ['說明', done.note || '—']]), h('p', { class: 'fm-note' }, '公所會重新檢核。'));
      return;
    }
    const files = { far: null, near: null };
    const ph = (k, t) => h('label', { class: 'fm-file' }, t, h('input', { type: 'file', accept: 'image/*', capture: 'environment', onchange: (e) => { files[k] = e.target.files[0] ? e.target.files[0].name : null; } }));
    const crop = reasons.includes('作物不符') ? h('select', { 'aria-label': '更正作物' }, h('option', { value: '' }, '不更正'), ['麻竹筍', '香蕉', '水稻', '木瓜', '竹', '休耕'].map((x) => h('option', { value: x }, x))) : null;
    const note = h('textarea', { rows: '3', placeholder: '補充說明（例如：哪裡受損、田裡有沒有灌水）', 'aria-label': '補充說明' });
    const warn = h('p', { class: 'fm-warn', role: 'alert' });
    box(h('h2', null, '補件'),
      drone ? null : h('p', { class: 'fm-note' }, '請用農業部現地照相 App 在田裡拍攝後上傳；路沒通或坡地不穩時不要進田，告訴公所即可。'),
      drone ? null : h('div', { class: 'fm-two' }, ph('far', '遠拍'), ph('near', '近拍')),
      crop ? h('label', { class: 'fm-field-in' }, '更正申報作物', crop) : null,
      h('label', { class: 'fm-field-in' }, '說明', note), warn,
      h('button', { class: 'fm-btn primary', onclick: async () => {
        const photos = [files.far && '遠拍：' + files.far, files.near && '近拍：' + files.near].filter(Boolean);
        if (!photos.length && !(crop && crop.value) && !note.value.trim()) { warn.textContent = '請至少上傳照片、更正作物或填寫說明'; return; }
        await SA.api.uploadSupplement(c.id, { photos, crop: crop ? crop.value : null, note: note.value.trim() });
        SA.ui.toast('已送出，公所會重新檢核'); route();
      } }, '送出補件'));
  }

  // ---------- 確認預填申請（表 23-3） ----------
  async function apply(id) {
    const c = caseOf(id); const f = fieldOf(id);
    back('#/disaster', '每塊田的結果');
    page('確認預填申請', '現金救助申請表草稿');
    main.appendChild(testBanner());
    if (!c && !f) { main.appendChild(SA.ui.empty('找不到這塊田')); return; }
    const x = c || f;
    if (isAuto(c)) { go(c.grade === 'A_MET' ? '#/auto/' + id : '#/notmet/' + id); return; }
    const prev = await SA.api.getLocalApplication(id);
    if (prev) { box(h('p', null, '這筆已經送件。'), big('看案件進度', '#/progress/' + id, 'primary')); return; }
    const d = S.drafts[id] || (S.drafts[id] = { rate: '', confirm: false });
    const rate = h('input', { type: 'number', min: '0', max: '100', inputmode: 'numeric', value: d.rate, 'aria-label': '受災率' });
    const bank = h('input', { type: 'text', inputmode: 'numeric', autocomplete: 'off', 'aria-label': '帳號', placeholder: '自己填寫' });
    const ok = h('input', { type: 'checkbox', checked: d.confirm ? true : null });
    const warn = h('p', { class: 'fm-warn', role: 'alert' });
    const iv = c && c.interval;
    box(h('h2', null, '申請資料'),
      SA.ui.kv([['申請人', S.farmer && S.farmer.name], ['耕地標示', val(x.landNo) + '（來自謄本）'], ['作物', x.crop], ['作物面積', x.areaHa ? num(x.areaHa, 4) + ' 公頃' + (x.baselineLocked ? '（公所確認的災前基準）' : '（待公所確認）') : null]]),
      h('label', { class: 'fm-field-in' }, '受災率（%）　由你自己申報', rate),
      iv && SA.ui.isNum(iv.p10) && c.level !== '丙' ? h('p', { class: 'fm-note' }, '參考：存證報告估計 ' + iv.p10 + '%–' + iv.p90 + '%，只供參考。') : null,
      h('label', { class: 'fm-field-in' }, '存摺帳號', bank),
      h('p', { class: 'fm-note' }, '帳號只印在申請表上，系統不會保存。每一欄都可以改。'),
      h('p', { class: 'fm-strong' }, '申報不實者不予救助，已領取的須返還。'),
      h('label', { class: 'fm-check' }, ok, '以上資料屬實'), warn,
      h('button', { class: 'fm-btn primary', onclick: () => {
        const r = parseFloat(rate.value);
        if (rate.value === '' || isNaN(r) || r < 0 || r > 100) { warn.textContent = '請填受災率（0–100%）'; return; }
        if (!ok.checked) { warn.textContent = '請勾選「以上資料屬實」'; return; }
        d.rate = r; d.confirm = true; d.bankFilled = !!bank.value.trim();
        go('#/submit/' + id);
      } }, '下一步：附件與送件'));
  }

  // ---------- 自動申報（甲等 A 級） ----------
  async function auto(id) {
    const c = caseOf(id);
    back('#/disaster', '每塊田的結果');
    page('申報內容', c ? val(c.landNo) + '　' + val(c.crop) : '');
    main.appendChild(testBanner());
    if (!isAuto(c)) { main.appendChild(SA.ui.empty('這塊田不是自動申報')); return; }
    if (c.grade === 'A_NOT_MET') { go('#/notmet/' + id); return; }
    const ap = await SA.api.getLocalAppeal(c.id);
    const iv = c.interval || {};
    box(h('p', { class: 'fm-auto' }, '系統已依存證報告自動申報'),
      SA.ui.kv([['申請人', S.farmer && S.farmer.name], ['耕地標示', val(c.landNo)], ['作物', c.crop], ['作物面積', num(c.areaHa, 4) + ' 公頃（公所確認的災前基準）'], ['受災率', SA.ui.isNum(iv.p50) ? iv.p50 + '%（存證報告中間值；估計 ' + iv.p10 + '%–' + iv.p90 + '%）' : null], ['申報時間', S.event ? datetime(S.event.gradedAt) : null]]),
      h('p', { class: 'fm-note' }, '公所以存證報告書面審核；可能被抽中 20% 抽查，屆時公所會到田裡確認。'),
      big('看案件進度', '#/progress/' + id, 'primary'));
    if (ap && ap.kind === 'objection') { box(h('h2', null, '已提出異議'), h('p', null, datetime(ap.at) + '：' + val(ap.payload && ap.payload.note)), h('p', { class: 'fm-note' }, '公所會到田裡確認，結果以公所勘查為準。')); official(); return; }
    const note = h('textarea', { rows: '3', placeholder: '例如：實際損失比估計重、面積不對', 'aria-label': '異議說明' });
    const warn = h('p', { class: 'fm-warn', role: 'alert' });
    box(h('h2', null, '對申報內容有異議'), h('p', null, '提出異議後，這筆改由公所到田裡確認，結果以公所勘查為準。'),
      h('label', { class: 'fm-file' }, '補上 App 照片（選填）', h('input', { type: 'file', accept: 'image/*', capture: 'environment' })),
      h('label', { class: 'fm-field-in' }, '說明', note), warn,
      h('button', { class: 'fm-btn', onclick: async () => {
        if (!note.value.trim()) { warn.textContent = '請說明異議內容'; return; }
        const ok = await SA.ui.confirmDialog('提出異議', '提出後改由公所到田裡確認，可能比書面審核晚撥款。確定提出？', '提出異議');
        if (!ok) return;
        await SA.api.appeal(c.id, 'objection', { note: note.value.trim() }); SA.ui.toast('已提出異議'); route();
      } }, '提出異議'));
    official();
  }

  // ---------- 附件與送件（表 23-4） ----------
  async function submit(id) {
    const c = caseOf(id); const f = fieldOf(id); const x = c || f;
    back('#/apply/' + id, '確認預填申請');
    page('附件與送件');
    main.appendChild(testBanner());
    const d = S.drafts[id];
    const prev = await SA.api.getLocalApplication(id);
    if (!x || (!d && !prev)) { main.appendChild(SA.ui.empty('請先確認預填申請')); main.appendChild(big('確認預填申請', '#/apply/' + id, 'primary')); return; }
    if (prev) return showQR(x, prev);
    let by = '本人';
    const docsBox = h('div');
    const drawDocs = () => {
      docsBox.innerHTML = '';
      const rows = [['現金救助申請表', '已確認'], ['身分證明', '臨櫃出示'], ['存摺影本', d.bankFilled ? '帳號已自填' : '請攜帶'], ['土地證明', x.baselineLocked ? '免附（公所查得到地政資料）' : '請攜帶'],
        S.farmer && S.farmer.identity !== '地主' ? ['使用權文件', '登錄時已上傳'] : null, by === '委託' ? ['委託書', '請攜帶'] : null].filter(Boolean);
      docsBox.appendChild(h('ul', { class: 'fm-docs' }, rows.map(([t, s]) => h('li', null, h('span', null, t), h('strong', null, s)))));
    };
    drawDocs();
    const ok = h('input', { type: 'checkbox' });
    const warn = h('p', { class: 'fm-warn', role: 'alert' });
    box(h('h2', null, '應附文件'), docsBox);
    box(h('h2', null, '誰去送件'), h('div', { class: 'fm-options' }, ['本人', '農會協助', '委託'].map((t) => h('label', { class: 'fm-opt' }, h('input', { type: 'radio', name: 'by', checked: t === by ? true : null, onchange: () => { by = t; drawDocs(); } }), h('span', null, h('strong', null, t))))),
      h('label', { class: 'fm-check' }, ok, '我已確認預填資料與附件，產生送件 QR 碼'), warn,
      h('button', { class: 'fm-btn primary', onclick: async () => {
        if (!ok.checked) { warn.textContent = '請先勾選確認'; return; }
        const rec = { caseNo: c ? c.caseNo : null, fieldId: f ? f.id : null, declaredRate: d.rate, by };
        await SA.api.submitApplication(id, rec);
        SA.ui.toast('送件 QR 碼已產生'); route();
      } }, '產生送件 QR 碼'));
  }

  function qrSvg(text) {
    if (!window.qrcode) return h('p', { class: 'fm-code' }, text);
    const q = window.qrcode(0, 'M'); q.addData(text); q.make();
    const holder = h('div', { class: 'fm-qr', role: 'img', 'aria-label': '送件 QR 碼：' + text });
    holder.innerHTML = q.createSvgTag({ cellSize: 6, margin: 2, scalable: true }); // 程式產生的 SVG
    return holder;
  }
  function showQR(x, prev) {
    const code = prev.caseNo || ('NEW-' + x.id);
    box(h('h2', null, '送件 QR 碼'), qrSvg(code), h('p', { class: 'fm-code' }, code),
      h('p', null, '由' + prev.by + '帶著證件到' + officeName() + '農業課，出示這個 QR 碼。公所掃描後就能調閱預填資料與存證報告。'),
      !prev.caseNo ? h('p', { class: 'fm-note' }, '測試資料庫沒有這筆申請，公所端查不到。') : null,
      h('div', { class: 'fm-actions' }, big('看案件進度', '#/progress/' + x.id, 'primary'), big('查驗存證報告', '#/verify?case=' + x.id, '')));
  }

  // ---------- 案件進度（表 23-5） ----------
  async function progress(id) {
    const c = caseOf(id); const f = fieldOf(id);
    back('#/disaster', '每塊田的結果');
    page('案件進度', c ? val(c.landNo) + '　' + val(c.crop) : f ? val(f.landNo) : '');
    main.appendChild(testBanner());
    const [app, acc, dec, supp, ap] = await Promise.all([SA.api.getLocalApplication(id), SA.api.getLocalAccepted(id), SA.api.getLocalDecision(id), SA.api.getLocalSupplement(id), SA.api.getLocalAppeal(id)]);
    const autoAt = isAuto(c) && S.event ? datetime(S.event.gradedAt) : null;
    if (isAuto(c) && ap && ap.kind === 'objection') main.appendChild(h('p', { class: 'fm-alert' }, '你已提出異議，公所會到田裡確認。'));
    const steps = [
      [isAuto(c) ? '系統自動申報' : '送件', autoAt || (app ? datetime(app.at) : null)],
      ['公所受理', autoAt || (acc ? datetime(acc.at) : null)],
      ['公所勘查（30 日內）', dec && dec.result !== 'visit' ? datetime(dec.at) : dec && dec.result === 'visit' ? '已排到場' : S.dl ? '勘查截止 ' + date(S.dl.surveyEnd, true) : null],
      ['縣府抽查（7 日）', null], ['農業部審核（7 日）', null], ['入帳', null]
    ];
    const cur = steps.findIndex(([, v]) => !v || v.startsWith('勘查截止') || v === '已排到場');
    main.appendChild(h('ol', { class: 'fm-progress' }, steps.map(([t, v], i) => h('li', { class: i < cur ? 'done' : i === cur ? 'on' : null }, h('strong', null, t), h('span', null, v && i < cur ? v : i === cur ? (v || (i >= 3 ? '等候公所報送' : '進行中')) : '')))));
    if (c && c.grade === 'C' && c.level !== '丙' && !supp) main.appendChild(h('p', { class: 'fm-alert' }, '這塊田的衛星影像不足，補上 App 照片可以加快處理。'), big('補充資料', '#/supp/' + id, 'primary'));
    if (dec && dec.result !== 'visit') main.appendChild(big('看核定結果', '#/result/' + id, 'primary'));
    official();
  }

  // ---------- A 未達標通知（表 21、三、1(4)） ----------
  async function notmet(id) {
    const c = caseOf(id);
    back('#/disaster', '每塊田的結果');
    page('影像顯示未達 20%', c ? val(c.landNo) + '　' + val(c.crop) : '');
    main.appendChild(testBanner());
    if (!c || c.level !== '甲' || c.grade !== 'A_NOT_MET') { main.appendChild(SA.ui.empty('這塊田沒有這類通知')); return; }
    const [notice, ap] = await Promise.all([SA.api.getLocalNotice(c.id), SA.api.getLocalAppeal(c.id)]);
    const ev = c.evidence || [];
    const pre = (ev.find((e) => e.kind === 'pre') || {}), post = (ev.find((e) => e.kind === 'post') || {});
    const due = notice && notice.content && notice.content.due ? date(notice.content.due, true) : S.dl ? date(S.dl.surveyEnd, true) + ' 前（以公所通知為準）' : null;
    box(h('h2', null, '判定依據'),
      h('div', { class: 'fm-two' }, h('figure', null, pre.url ? h('img', { src: pre.url, alt: '災前影像' }) : null, h('figcaption', null, '災前 ' + val(pre.date))), h('figure', null, post.url ? h('img', { src: post.url, alt: '災後影像' }) : null, h('figcaption', null, '災後 ' + val(post.date)))),
      SA.ui.kv([['損失估計', SA.ui.intervalText(c.interval)], ['理由', c.notMetReason], ['補件或異議期限', due]]));
    box(h('p', { class: 'fm-auto' }, '系統已依存證報告自動申報，判定未達 20%'));
    if (ap) { box(h('h2', null, '已提出異議'), h('p', null, datetime(ap.at) + '，公所會到田裡確認，結果以公所勘查為準。')); return; }
    const note = h('textarea', { rows: '3', placeholder: '說明實際受損情形', 'aria-label': '異議說明' });
    const warn = h('p', { class: 'fm-warn', role: 'alert' });
    box(h('h2', null, '如果實際受損較重'), h('p', null, '可以補上 App 照片並提出異議，公所會到田裡確認。'),
      h('label', { class: 'fm-file' }, '補上 App 照片', h('input', { type: 'file', accept: 'image/*', capture: 'environment' })),
      h('label', { class: 'fm-field-in' }, '說明', note), warn,
      h('button', { class: 'fm-btn primary', onclick: async () => {
        if (!note.value.trim()) { warn.textContent = '請說明實際受損情形'; return; }
        await SA.api.appeal(c.id, 'objection', { note: note.value.trim() }); SA.ui.toast('已提出異議'); route();
      } }, '提出異議'));
    official();
  }

  // ---------- 結果與復查（表 23-6） ----------
  async function result(id) {
    const c = caseOf(id);
    back('#/disaster', '每塊田的結果');
    page('核定結果', c ? val(c.landNo) + '　' + val(c.crop) : '');
    main.appendChild(testBanner());
    const [dec, app, ap] = await Promise.all([SA.api.getLocalDecision(id), SA.api.getLocalApplication(id), SA.api.getLocalAppeal(id)]);
    if (!dec || dec.result === 'visit') { box(h('p', null, '公所還沒有核定。'), big('看案件進度', '#/progress/' + id, 'primary')); return; }
    const perHa = S.event && S.event.reliefPerHa;
    const amount = dec.result === 'approve' && perHa && SA.ui.isNum(dec.areaHa) ? Math.round(dec.areaHa * perHa) : null;
    box(h('h2', null, dec.result === 'approve' ? '公所已核定' : '公所判定不予救助'),
      h('table', { class: 'fm-cmp' }, h('thead', null, h('tr', null, h('th', null, ''), h('th', null, isAuto(c) ? '系統申報' : '你申報的'), h('th', null, '公所核定'))),
        h('tbody', null,
          h('tr', null, h('th', null, '面積'), h('td', null, c && c.areaHa ? num(c.areaHa, 4) + ' 公頃' : '—'), h('td', null, SA.ui.isNum(dec.areaHa) ? dec.areaHa + ' 公頃' : '—')),
          h('tr', null, h('th', null, '受災率'), h('td', null, isAuto(c) && c.interval && SA.ui.isNum(c.interval.p50) ? c.interval.p50 + '%' : app && SA.ui.isNum(app.declaredRate) ? app.declaredRate + '%' : '—'), h('td', null, SA.ui.isNum(dec.rate) ? dec.rate + '%' : '—')))),
      SA.ui.kv([['救助金額', amount !== null ? num(amount) + ' 元' + (SA.api.mode() === 'test' ? '（測試額度）' : '') : '依公告每公頃額度計算'], ['核定時間', datetime(dec.at)]]));
    const deadline = SA.rules.addDays(new Date(dec.at), CFG.deadlines.appealDays);
    const left = daysLeft(deadline);
    if (ap && ap.kind === 'review') box(h('h2', null, '已申請復查'), h('p', null, datetime(ap.at) + '，公所會再確認。'));
    else box(h('h2', null, '對結果有疑問'),
      h('p', null, '收到通知後 7 日內可以申請復查：', h('strong', null, date(deadline, true) + ' 截止' + (left >= 0 ? '（還有 ' + left + ' 天）' : '（已截止）'))),
      h('p', { class: 'fm-note' }, '系統會幫你整理附件：存證報告、災前災後影像日期、App 照片。'),
      left >= 0 ? h('button', { class: 'fm-btn primary', onclick: async () => { await SA.api.appeal(id, 'review', {}); SA.ui.toast('已申請復查'); route(); } }, '申請復查') : null);
    box(h('h2', null, '其他'),
      h('ul', { class: 'fm-list' }, h('li', null, '登錄資料有錯：4 個月內可以申請更正增撥。'), h('li', null, '需要低利貸款：可以向公所申請受災證明書。')),
      h('a', { class: 'fm-link', href: '#/verify?case=' + id }, '查驗存證報告 →'));
  }

  // ---------- 查驗報告（三、4(8)） ----------
  async function verify(params) {
    page('查驗存證報告', '確認報告由資料中心簽發、沒有被改過');
    main.appendChild(testBanner());
    const sel = h('select', { 'aria-label': '選擇我的報告' }, h('option', { value: '' }, '選擇我的田'), S.cases.map((c) => h('option', { value: c.id, selected: params.case === c.id ? true : null }, val(c.landNo) + '　' + val(c.crop))));
    const code = h('input', { type: 'text', placeholder: '或輸入查驗碼', 'aria-label': '查驗碼' });
    const out = h('div');
    let tampered = false;
    async function run() {
      out.innerHTML = '';
      const c = caseOf(sel.value) || S.cases.find((k) => k.report && code.value.trim() && k.report.verifyCode === code.value.trim());
      if (!c || !c.report || !c.report.content) { if (sel.value || code.value) out.appendChild(SA.ui.empty('找不到這份報告')); return; }
      const content = Object.assign({}, c.report.content);
      if (tampered) { const [a, b, d] = content['損失區間'].split('/').map(Number); content['損失區間'] = Math.min(100, a + 25) + '/' + Math.min(100, b + 25) + '/' + Math.min(100, d + 25); }
      const v = await SA.api.verifyReportContent(content);
      const dec = await SA.api.getLocalDecision(c.id);
      const mark = (ok) => (ok === true ? h('span', { class: 'fm-ok' }, '相符') : ok === false ? h('span', { class: 'fm-bad' }, '不符') : '—');
      out.appendChild(h('div', { class: 'fm-seg' },
        h('button', { class: 'fm-segb' + (!tampered ? ' on' : ''), onclick: () => { tampered = false; run(); } }, '原本的報告'),
        h('button', { class: 'fm-segb' + (tampered ? ' on' : ''), onclick: () => { tampered = true; run(); } }, '被改過的報告')));
      out.appendChild(h('section', { class: 'fm-card ' + (v && !v.signature ? 'bad' : 'good') },
        h('h2', null, v ? (v.signature ? '報告沒有被改過' : '報告內容與簽章不符') : '—'),
        SA.ui.kv([['資料中心簽章', mark(v && v.signature)], ['時戳', v && v.timestamp ? v.at : mark(v && v.timestamp)], ['封存批次', v ? h('span', null, mark(v.batch), '　' + val(v.batchId)) : null]]),
        v && !v.signature ? h('p', { class: 'fm-strong' }, '這份報告的內容算出來的雜湊和簽發時不同，表示簽發後有人改過內容。請以公所留存的報告為準。') : null,
        h('p', { class: 'fm-note' }, '查驗只用公開金鑰，不必連線到天相星。' + (SA.api.mode() === 'test' ? '（測試用假雜湊，非正式簽章）' : ''))));
      out.appendChild(h('section', { class: 'fm-card' }, h('h2', null, '報告內容'), SA.ui.kv(Object.entries(content).map(([k, x]) => [k, String(x)]))));
      out.appendChild(h('section', { class: 'fm-card' }, h('h2', null, '兩份紀錄'),
        SA.ui.kv([['系統判讀', c.level === '丙' ? '收集期，不提供' : (CFG.grades[c.grade] || {}).plain], ['公所判定', dec ? ({ approve: '核定', reject: '不予救助', visit: '改排到場' })[dec.result] + '（' + datetime(dec.at) + '）' : '尚未判定']]),
        h('p', { class: 'fm-note' }, '公所判定以機關憑證另行簽章，和系統判讀並列，不會覆蓋。')));
      out.appendChild(h('section', { class: 'fm-card' }, h('h2', null, '用了哪些輸入檔'), SA.ui.kv([['災前影像', content['災前影像']], ['災後影像', content['災後影像']], ['官方檢查碼', SA.api.mode() === 'test' ? '測試資料無官方檢查碼' : null]])));
    }
    sel.addEventListener('change', () => { code.value = ''; run(); });
    box(sel, h('div', { class: 'fm-two' }, code, h('button', { class: 'fm-btn', onclick: () => { sel.value = ''; run(); } }, '查驗')));
    main.appendChild(out);
    run();
  }

  // ---------- 簡訊版（表 23） ----------
  async function sms() {
    page('簡訊版', '沒有智慧型手機也收得到');
    main.appendChild(testBanner());
    const f = S.farmer && S.farmer.fields[0];
    const msgs = [
      '【天相星】颱風警報：你登錄的 ' + (S.farmer ? S.farmer.fields.length : 0) + ' 塊田在風雨範圍內。安全時再用農業部 App 拍照，路沒通不要進田。',
      '【天相星】救助公告：' + (S.event ? S.event.area : '') + ' 開放現金救助申請，' + (S.dl ? date(S.dl.applyEnd) + ' 截止' : '') + '。可到公所或農會辦理。',
      f ? '【天相星】' + f.landNo + ' 衛星影像不足，請補 App 照片或到公所說明。路沒通不要上山。' : null,
      '【天相星】你的申請已受理，公所勘查中。進度可洽' + officeName() + '農業課。',
      '【天相星】核定結果已通知，7 日內可申請復查。以公所認定為準。'
    ].filter(Boolean);
    main.appendChild(h('div', { class: 'fm-sms' }, msgs.map((m) => h('p', { class: 'fm-bubble' }, m))));
    main.appendChild(h('p', { class: 'fm-note' }, '高齡農民可由農會或公所協助登錄。簡訊內容以白話寫成，不出現分級代號。'));
  }

  // ---------- 路由 ----------
  async function route() {
    const raw = (location.hash || '#/').replace(/^#\/?/, '');
    const [path, qs] = raw.split('?');
    const [r, id] = path.split('/');
    const params = {}; (qs || '').split('&').filter(Boolean).forEach((p) => { const [k, v] = p.split('='); params[k] = decodeURIComponent(v || ''); });
    main.innerHTML = '';
    document.querySelectorAll('.fm-tab').forEach((a) => a.classList.toggle('on', a.dataset.r === (r || 'home') || (a.dataset.r === 'disaster' && ['apply', 'auto', 'submit', 'supp', 'progress', 'notmet', 'result', 'alert'].includes(r))));
    const map = { '': home, home, field: () => fieldDetail(id), register, alert: alertPage, disaster, supp: () => supp(id), apply: () => apply(id), auto: () => auto(id), submit: () => submit(id), progress: () => progress(id), notmet: () => notmet(id), result: () => result(id), verify: () => verify(params), sms };
    try { await (map[r || ''] || home)(); } catch (e) { console.error(e); main.appendChild(SA.ui.empty('畫面載入失敗：' + e.message)); }
    main.focus({ preventScroll: true }); window.scrollTo(0, 0);
  }

  async function load() {
    const farmers = await SA.api.listFarmers();
    S.farmerId = readId() || (farmers[0] && farmers[0].id) || null;
    if (farmers.length && !farmers.find((f) => f.id === S.farmerId)) S.farmerId = farmers[0].id;
    const [farmer, cases, events] = await Promise.all([S.farmerId ? SA.api.getFarmer(S.farmerId) : null, S.farmerId ? SA.api.listFarmerCases(S.farmerId) : [], SA.api.listEvents()]);
    S.farmer = farmer; S.cases = cases || []; S.event = (events || [])[0] || null;
    if (S.event && SA.api.mode() === 'test') S.event.reliefPerHa = 60000; // 測試額度
    S.dl = S.event ? SA.rules.deadlines(S.event.announceDate) : null;
    const top = document.getElementById('who');
    top.innerHTML = '';
    if (farmers.length) top.appendChild(h('select', { 'aria-label': '測試帳號', onchange: async (e) => { saveId(e.target.value); S.drafts = {}; await load(); route(); } }, farmers.map((f) => h('option', { value: f.id, selected: f.id === S.farmerId ? true : null }, f.name))));
  }

  window.addEventListener('hashchange', route);
  document.addEventListener('DOMContentLoaded', async () => { await load(); route(); });
})();
