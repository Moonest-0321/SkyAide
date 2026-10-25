/* 案件審核：證據、五項檢核、損失區間與影響判定最多的特徵；系統判定與本所判定並列（表 21、三、1(7)） */
SA.pages.case = async function (root, r) {
  const { h, val, num, card, kv, levelChip, gradeChip, intervalBar, intervalText } = SA.ui;
  const CFG = SA.config;
  const id = r.id && r.id !== 'blank' ? r.id : null;
  const data = (id && await SA.api.getCase(id)) || {};
  const blank = !id || !Object.keys(data).length;
  const caseKey = id || 'blank';
  const [rejectReasons, localDecision, localR] = await Promise.all([SA.api.listRejectReasons(), SA.api.getLocalDecision(caseKey), SA.api.getLocalRChecks(caseKey)]);
  const ev = SA.currentEvent();
  const dl = SA.rules.deadlines(SA.state.trialAnnounce || (ev && ev.announceDate));

  // 原型示範：資料留白時用來切換情境，有資料時以資料為準
  const demo = {
    level: data.level || null,
    grade: data.grade || SA.rules.grade(data) || null,
    sampled: !!data.sampled,
    reasons: data.reasons || SA.rules.reasonCodes(data.checks),
    supplementState: data.supplementState || 'pending'
  };

  root.appendChild(h('div', { class: 'case-head' },
    h('a', { href: '#/list', class: 'back' }, '← 分級清單'),
    h('h1', null, val(data.landNo || '[地段地號]'), '　', val(data.crop || '[作物]'), '　', data.areaHa ? num(data.areaHa, 4) + ' 公頃' : '[面積] 公頃'),
    h('span', { id: 'head-chips' }),
    h('p', { class: 'case-meta' }, '申請人 ', val(data.applicant), '・申請案號 ', val(data.caseNo), '・勘查截止 ', dl ? SA.ui.date(dl.surveyEnd, true) : '—')));
  if (!SA.api.CONNECTED) root.appendChild(SA.ui.notConnected());

  const demoBar = h('div', { class: 'demo-bar' });
  root.appendChild(demoBar);

  const grid = h('div', { class: 'case-grid' });
  const left = h('div', { class: 'col' });
  const right = h('div', { class: 'col' });
  grid.appendChild(left); grid.appendChild(right);
  root.appendChild(grid);

  // ---------- 原型示範列 ----------
  function drawDemo() {
    demoBar.innerHTML = '';
    const seg = (label, opts, cur, onPick) => h('div', { class: 'seg', role: 'group', 'aria-label': label }, h('span', { class: 'seg-l' }, label),
      opts.map(([v, t]) => h('button', { class: 'seg-b' + (cur === v ? ' on' : ''), 'aria-pressed': cur === v ? 'true' : 'false', onclick: () => { onPick(v); drawAll(); } }, t)));
    demoBar.appendChild(h('p', { class: 'demo-title' }, '原型示範', h('span', { class: 'muted' }, blank ? '（資料留白，切換情境檢查各等級的操作）' : '（以資料為準，切換僅供比較）')));
    demoBar.appendChild(seg('類別等級', [['丙', '丙等'], ['乙', '乙等'], ['甲', '甲等']], demo.level, (v) => { demo.level = v; }));
    demoBar.appendChild(seg('分級', [['A_MET', 'A 達標'], ['A_NOT_MET', 'A 未達標'], ['B', 'B 邊緣'], ['C', 'C 缺失']], demo.grade, (v) => { demo.grade = v; }));
    if (demo.grade === 'A_MET' || demo.grade === 'A_NOT_MET') {
      demoBar.appendChild(h('label', { class: 'inline' }, h('input', { type: 'checkbox', checked: demo.sampled ? true : null, onchange: (e) => { demo.sampled = e.target.checked; drawAll(); } }), '救助系統抽中 20% 抽查'));
    }
    if (demo.grade === 'C') {
      const sel = h('select', { 'aria-label': '原因碼', onchange: (e) => { demo.reasons = e.target.value ? [e.target.value] : []; drawAll(); } },
        h('option', { value: '' }, '選擇原因碼'), Object.keys(CFG.reasonRoute).map((k) => h('option', { value: k, selected: demo.reasons[0] === k ? true : null }, k)));
      demoBar.appendChild(h('label', { class: 'inline' }, '原因碼', sel));
      demoBar.appendChild(seg('補件', Object.entries(CFG.supplementStates), demo.supplementState, (v) => { demo.supplementState = v; }));
    }
  }

  // ---------- 左欄 ----------
  function drawLeft(hd) {
    left.innerHTML = '';
    const rep = data.report || {};
    const approved = demo.level === '甲';
    left.appendChild(card('存證報告', h('div', null,
      kv([['報告編號', rep.no], ['查驗碼', rep.verifyCode], ['報告雜湊', rep.hash ? rep.hash.slice(0, 16) + '…' : null],
        ['簽章', statusText(rep.signature)], ['時戳', rep.timestamp || null], ['封存批次', statusText(rep.batchRoot)]]),
      h('p', { class: 'stamp' + (approved ? ' ok' : '') }, approved ? CFG.reportLabel.approved : CFG.reportLabel.reference))));

    const ev = data.evidence || [];
    const evOf = (k) => ev.find((e) => e.kind === k) || {};
    const tiles = [['pre', '災前', 'Sentinel-1'], ['post', '災後', 'Sentinel-1'], ['hotspot', '熱區', '福衛八號'], ['app', 'App 照片', '農民上傳']];
    left.appendChild(card('證據', h('div', null,
      h('div', { class: 'ev-grid' }, tiles.map(([k, t, src]) => {
        const e = evOf(k);
        return h('figure', { class: 'ev' }, e.url ? h('img', { src: e.url, alt: t + '影像' }) : h('div', { class: 'ev-ph', 'aria-hidden': 'true' }, '影像'),
          h('figcaption', null, t + ' ' + val(e.date) + ' ' + (e.source || src)));
      })),
      h('p', { class: 'muted' }, '照片重複檢核：', val(data.photoDuplicate), '　App 內即時拍攝與相簿匯入分開標示'),
      data.geometry ? h('div', { class: 'parcel-map' }, SA.ui.mapSvg({ polys: [{ ring: data.geometry.coordinates[0], fill: '#8fa9dd', stroke: '#15213b', width: 2, title: '坵塊 ' + val(data.landNo) }], points: data.center ? [{ lat: data.center.lat, lon: data.center.lon, r: 4, title: '坵塊中心' }] : [], height: 220, ariaLabel: '坵塊位置（色塊示意）' }), h('p', { class: 'muted small' }, '坵塊範圍（色塊示意）　中心 ', data.center ? data.center.lat.toFixed(5) + ', ' + data.center.lon.toFixed(5) : '—')) : null)));

    // 五項檢核
    const checks = data.checks || {};
    const cred = data.credibility || SA.rules.credibility(data.checks);
    left.appendChild(card('可信度五項檢核', h('div', null,
      h('ul', { class: 'checks' }, CFG.checks.map((c) => {
        const x = checks[c.key] || {};
        const st = x.pass === true ? 'ok' : x.pass === false ? 'no' : 'na';
        return h('li', { class: st },
          h('span', { class: 'ck', 'aria-label': st === 'ok' ? '通過' : st === 'no' ? '未通過' : '未提供' }),
          h('div', null, h('strong', null, c.label), h('span', { class: 'muted' }, x.detail || c.pass),
            x.pass === false && x.reasons ? h('p', { class: 'reason' }, '原因碼：', x.reasons.join('、')) : null,
            c.key === 'production' ? h('ul', { class: 'sub' }, CFG.longterm.map((l) => {
              const v = x.longterm && x.longterm[l.key];
              return h('li', { class: v === true ? 'ok' : v === false ? 'no' : 'na' }, h('span', { class: 'ck' }), l.label, h('span', { class: 'muted' }, '　' + l.desc));
            })) : null));
      })),
      h('p', null, '可信度：', h('strong', null, val(cred)), h('span', { class: 'muted' }, '　五項全過為高；一項未過為中；生產事實未過或兩項以上未過為低。只有「高」進入 A、B 的判斷。')))));

    // 損失區間
    const iv = data.interval || {};
    const t = SA.rules.thresholds(data.crop);
    left.appendChild(card('損失區間', h('div', null,
      hd.gradeVisible ? intervalBar(iv, data.crop) : h('p', { class: 'muted' }, '丙等類別不提供損失區間。'),
      hd.gradeVisible ? h('div', { class: 'iv-nums' }, h('span', null, '第 10 百分位 ', h('strong', null, SA.ui.pp(iv.p10))), h('span', null, '中間值 ', h('strong', null, SA.ui.pp(iv.p50))), h('span', null, '第 90 百分位 ', h('strong', null, SA.ui.pp(iv.p90)))) : null,
      h('p', { class: 'muted' }, '下限 ≥ ' + t.aMetLowerMin + '% → A 達標；上限 ≤ ' + t.aNotMetUpperMax + '% → A 未達標；跨過 ' + CFG.grade.lossThreshold + '% → B 邊緣（起始值，依作物校準）'),
      h('p', null, h('strong', null, '影響判定最多的特徵')),
      data.topFeatures && data.topFeatures.length ? h('ul', null, data.topFeatures.map((f) => h('li', null, f))) : h('p', { class: 'muted' }, '—'))));

    // R1–R5
    left.appendChild(card('申請交叉檢核 R1–R5', h('div', { class: 'rlist' }, CFG.rchecks.map((rc) => {
      const srv = (data.rchecks || {})[rc.key] || {};
      const loc = localR[rc.key] || {};
      const cur = loc.status || srv.status || '';
      const note = h('input', { type: 'text', placeholder: '原因碼或說明', value: loc.note || srv.note || '', 'aria-label': rc.label + ' 說明' });
      const sel = h('select', { 'aria-label': rc.label + ' 結果' }, h('option', { value: '' }, '—'), CFG.rStatuses.map((s) => h('option', { value: s, selected: cur === s ? true : null }, s)));
      const save = h('button', { class: 'btn btn-sm', onclick: async () => {
        localR[rc.key] = { status: sel.value, note: note.value };
        await SA.api.saveRCheck(caseKey, rc.key, localR[rc.key]); SA.ui.queuedToast(rc.label + ' 已回寫'); SA.refreshNav();
      } }, '回寫');
      return h('div', { class: 'rrow' },
        h('div', null, h('strong', null, rc.label), h('p', { class: 'muted' }, rc.fields), h('p', { class: 'muted small' }, '證據來源：', val(srv.source), '　', rc.handle)),
        h('div', { class: 'rctl' }, sel, note, save));
    }))));

    const pv = data.provenance || {};
    left.appendChild(card('可溯源資料', kv([
      ['原始影像', pv.raw], ['處理過程', pv.process], ['判讀結果', pv.inference], ['人工處理', pv.manual], ['對應關係', pv.mapping]
    ]), { sub: '五層紀錄，格式採用 STAC 與 W3C PROV；審計或申覆時可依同一批影像與同一版模型重算。' }));
  }

  function statusText(v) {
    if (v === true) return '相符';
    if (v === false) return h('span', { class: 'bad' }, '不符');
    return v || null;
  }

  // ---------- 右欄 ----------
  function drawRight(hd) {
    right.innerHTML = '';
    right.appendChild(card('系統判定', kv([
      ['分級', hd.gradeVisible ? (demo.grade ? gradeChip(demo.grade, { reference: demo.level === '乙' }) : null) : h('span', { class: 'muted' }, '丙等不提供')],
      ['類別', h('span', null, val(data.crop) + ' × ' + val(data.hazard) + ' ', levelChip(demo.level))],
      ['原因碼', demo.grade === 'C' && demo.reasons.length ? demo.reasons.join('、') : null],
      ['衛星判釋作物', data.satCrop ? data.satCrop + (data.satCropProb ? '（機率 ' + data.satCropProb + '）' : '') : null],
      ['災前基準', data.baselineLocked === true ? '已鎖定' : data.baselineLocked === false ? '未鎖定（缺公所確認的災前基準）' : null]
    ])));

    // 處理方式
    const items = [];
    if (demo.level === '甲' && (demo.grade === 'A_MET' || demo.grade === 'A_NOT_MET')) items.push(demo.sampled ? '本案被救助系統抽中 20% 抽查' : '本案未被救助系統抽中 20% 抽查');
    if (demo.level === '甲' && demo.grade === 'A_MET' && !demo.sampled) items.push('書面依據：存證報告、App 照片');
    if (demo.grade === 'C' && demo.reasons.length) {
      demo.reasons.forEach((x) => { const m = CFG.reasonRoute[x]; items.push(x + '：' + (m ? m.note + '（' + (m.imagery ? '影像類' : '非影像類') + '）' : '依原因碼處理')); });
      items.push('補件狀態：' + CFG.supplementStates[demo.supplementState]);
    }
    right.appendChild(h('section', { class: 'card card-strong tone-' + hd.tone },
      h('h2', null, hd.title),
      h('p', null, hd.action),
      items.length ? h('ul', { class: 'checklist compact' }, items.map((x) => h('li', { class: 'ok' }, h('span', { class: 'ck' }), x))) : null));

    // 通知
    if (hd.notices.includes('notMet')) right.appendChild(noticeCard('notMet'));
    if (hd.notices.includes('supplement') && demo.grade === 'C') right.appendChild(noticeCard('supplement'));

    right.appendChild(decisionCard(hd));
  }

  function noticeCard(kind) {
    const due = h('input', { type: 'date', 'aria-label': '補件期限', value: dl ? isoDate(SA.rules.addDays(new Date(), 7) < dl.surveyEnd ? SA.rules.addDays(new Date(), 7) : dl.surveyEnd) : '' });
    if (kind === 'notMet') {
      const ev = data.evidence || [];
      const pre = (ev.find((e) => e.kind === 'pre') || {}).date, post = (ev.find((e) => e.kind === 'post') || {}).date;
      return card('A 未達標通知', h('div', null,
        h('p', { class: 'muted' }, '30 日勘查期內送達，並給補件期限，讓公所還來得及到場。'),
        kv([['災前影像日期', pre], ['災後影像日期', post], ['損失區間', intervalText(data.interval)], ['判定理由', data.notMetReason]]),
        h('label', { class: 'field' }, '補件或申訴期限', due),
        h('button', { class: 'btn btn-primary', onclick: async () => {
          if (dl && due.value && new Date(due.value) > dl.surveyEnd) { SA.ui.toast('補件期限不得晚於勘查期截止日', 'warn'); return; }
          const ok = await SA.ui.confirmDialog('送出 A 未達標通知', '通知將附災前災後影像日期、損失區間與判定理由。申請人可在期限內補件或申訴，屆時改排到場。', '送出');
          if (!ok) return;
          await SA.api.sendNotice([caseKey], 'notMet', { due: due.value }); SA.ui.queuedToast('A 未達標通知'); SA.refreshNav();
        } }, '送出 A 未達標通知')), { cls: 'card-notice' });
    }
    const plain = demo.reasons.map((x) => ((CFG.reasonRoute[x] || {}).supplement || x)).join('；');
    return card('補件提醒', h('div', null,
      h('p', { class: 'muted' }, 'C 缺失一律先要求補件，原因碼以白話傳給申請人。補件回來後重新檢核，五項全過即重新分級；期限過了未補件者，依公所量能派無人機或到場。'),
      kv([['需補的資料', plain || null]]),
      h('label', { class: 'field' }, '補件期限', due),
      h('button', { class: 'btn', onclick: async () => {
        await SA.api.sendNotice([caseKey], 'supplement', { due: due.value, reasons: demo.reasons }); SA.ui.queuedToast('補件提醒'); SA.refreshNav();
      } }, '發送補件提醒')));
  }

  function isoDate(d) { const x = new Date(d); return x.getFullYear() + '-' + String(x.getMonth() + 1).padStart(2, '0') + '-' + String(x.getDate()).padStart(2, '0'); }

  function decisionCard(hd) {
    const M = CFG.decisionMethods;
    const method = h('select', { id: 'd-method', 'aria-label': '判定方式' }, hd.methods.map((k) => h('option', { value: k }, M[k].label)));
    const methodNote = h('p', { class: 'muted small' });
    const syncNote = () => { methodNote.textContent = M[method.value] ? M[method.value].note : ''; };
    method.addEventListener('change', syncNote); syncNote();
    const cropOk = h('input', { type: 'checkbox', id: 'd-crop' });
    const area = h('input', { type: 'number', id: 'd-area', step: '0.0001', min: '0', inputmode: 'decimal', value: data.areaHa || '' });
    const rate = h('input', { type: 'number', id: 'd-rate', step: '1', min: '0', max: '100', inputmode: 'numeric' });
    const warn = h('p', { class: 'warn', role: 'alert' });
    const rejectSel = h('select', { 'aria-label': '不予救助的法定原因' }, h('option', { value: '' }, rejectReasons.length ? '選擇法定原因' : '法定原因清單未接入'), rejectReasons.map((x) => h('option', { value: x.code }, x.label)));

    function check() {
      warn.textContent = '';
      const a = parseFloat(area.value), rt = parseFloat(rate.value);
      if (area.value && (isNaN(a) || a <= 0)) return (warn.textContent = '核定面積須大於 0'), false;
      if (data.areaHa && a > data.areaHa) return (warn.textContent = '核定面積不得超過災前基準面積 ' + data.areaHa + ' 公頃'), false;
      if (rate.value && (isNaN(rt) || rt < 0 || rt > 100)) return (warn.textContent = '受害率須介於 0–100%'), false;
      if (rate.value && rt < CFG.grade.lossThreshold) warn.textContent = '受害率未達 ' + CFG.grade.lossThreshold + '%，依規定不予救助，請選擇法定原因。';
      return true;
    }
    area.addEventListener('input', check); rate.addEventListener('input', check);

    async function sign(result) {
      if (!check()) return;
      if (result === 'approve') {
        if (!area.value || !rate.value) { warn.textContent = '請填核定面積與受害率'; return; }
        if (parseFloat(rate.value) < CFG.grade.lossThreshold) { warn.textContent = '受害率未達 ' + CFG.grade.lossThreshold + '%，不能核定救助'; return; }
        if (!cropOk.checked) { warn.textContent = '請確認作物與申報相符；不符者改排到場或不予救助'; return; }
      }
      if (result === 'reject' && !rejectSel.value) { warn.textContent = rejectReasons.length ? '不予救助須選擇法定原因' : '法定原因清單尚未接入，無法送出不予救助'; return; }
      const label = { approve: '以機關憑證簽章核定', reject: '不予救助', visit: '改排到場' }[result];
      const ok = await SA.ui.confirmDialog(label, h('div', null,
        kv([['判定方式', result === 'visit' ? '實地勘查' : M[method.value].label], ['核定面積', area.value ? area.value + ' 公頃' : null], ['核定受害率', rate.value ? rate.value + '%' : null], ['指向報告雜湊', (data.report && data.report.hash) || null]]),
        h('p', { class: 'muted' }, '本所判定以機關憑證另行簽章，與系統結果並列保存、不覆蓋；回填後用於災後評等。')), '確認送出', { danger: result === 'reject' });
      if (!ok) return;
      const rec = { result, method: result === 'visit' ? 'survey' : method.value, cropMatch: cropOk.checked, areaHa: area.value ? +area.value : null, rate: rate.value ? +rate.value : null, rejectReason: result === 'reject' ? rejectSel.value : null, reportHash: (data.report && data.report.hash) || null, systemGrade: demo.grade, level: demo.level, at: new Date().toISOString() };
      if (result === 'visit') await SA.api.scheduleVisit(caseKey, 'office');
      await SA.api.submitDecision(caseKey, rec);
      SA.ui.queuedToast(label); SA.refreshNav();
      drawAll(rec);
    }

    return card('本所判定', h('div', { class: 'form' },
      h('label', { class: 'field' }, '判定方式', method), methodNote,
      h('label', { class: 'inline' }, cropOk, '作物與申報相符'),
      h('div', { class: 'two' }, h('label', { class: 'field' }, '核定面積（公頃）', area), h('label', { class: 'field' }, '核定受害率（%）', rate)),
      warn,
      h('button', { class: 'btn btn-go btn-block', onclick: () => sign('approve') }, '以機關憑證簽章核定'),
      h('div', { class: 'two' },
        h('button', { class: 'btn btn-block', onclick: () => sign('visit') }, '改排到場'),
        h('button', { class: 'btn btn-danger-o btn-block', onclick: () => sign('reject') }, '不予救助')),
      h('label', { class: 'field' }, '不予救助的法定原因', rejectSel),
      h('p', { class: 'muted small' }, '本所判定另行簽章，與系統結果並列保存、不覆蓋；回填後用於災後評等。不予救助須選法定原因。')));
  }

  function drawRecord(rec) {
    if (!rec) return;
    const R = { approve: '核定', reject: '不予救助', visit: '改排到場' };
    right.appendChild(card('判定紀錄（本機）', h('div', { class: 'pair' },
      h('div', null, h('p', { class: 'kicker' }, '系統結果'), kv([['分級', rec.systemGrade ? CFG.grades[rec.systemGrade].label : null], ['類別等級', rec.level], ['報告雜湊', rec.reportHash]])),
      h('div', null, h('p', { class: 'kicker' }, '本所判定'), kv([['結果', R[rec.result]], ['判定方式', CFG.decisionMethods[rec.method] ? CFG.decisionMethods[rec.method].label : rec.method], ['核定面積', rec.areaHa !== null ? rec.areaHa + ' 公頃' : null], ['受害率', rec.rate !== null ? rec.rate + '%' : null], ['時間', SA.ui.datetime(rec.at)], ['機關憑證簽章', '未接入']]))
    ), { cls: 'card-record' }));
  }

  let lastRec = localDecision;
  function drawAll(rec) {
    if (rec) lastRec = rec;
    const hd = SA.rules.handling(demo);
    const chips = document.getElementById('head-chips');
    chips.innerHTML = '';
    if (hd.gradeVisible && demo.grade) chips.appendChild(gradeChip(demo.grade, { reference: demo.level === '乙' }));
    const cred = data.credibility || SA.rules.credibility(data.checks);
    if (hd.gradeVisible) chips.appendChild(h('span', { class: 'chip chip-blank' }, '可信度 ' + val(cred)));
    drawDemo(); drawLeft(hd); drawRight(hd); drawRecord(lastRec);
  }
  drawAll();
};
