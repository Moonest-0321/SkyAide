/* 平時：災前基準確認佇列與單筆範圍確認（表 24 A、B） */
SA.pages.baseline = async function (root, r) {
  if (r.id) return baselineItem(root, r.id);
  const { h, val, num, pct, table } = SA.ui;
  const CFG = SA.config;
  let status = r.params.status || 'pending';

  root.appendChild(SA.ui.pageHead('平時', '災前基準確認', SA.ui.notConnected()));
  root.appendChild(h('p', { class: 'lead' }, '每年 1 月綠色環境給付申報期一併確認農民登錄的田區範圍，確認一次即鎖定為災前基準，災後不再量面積。申報超過權利面積（本筆面積 × 持分）者由系統直接退回。'));

  const all = {};
  await Promise.all(CFG.baselineStatuses.map(async (s) => { all[s.key] = (await SA.api.listBaseline(s.key)) || []; }));
  const body = h('div');
  function draw() {
    body.innerHTML = '';
    body.appendChild(SA.ui.tabs(CFG.baselineStatuses.map((s) => ({ key: s.key, label: s.label, count: all[s.key].length })), status, (k) => { status = k; draw(); }));
    body.appendChild(table([
      { label: '申請人', render: (x) => val(x.applicant) },
      { label: '身分', render: (x) => val(x.identity) },
      { label: '地號', render: (x) => val(x.landNo) },
      { label: '作物', render: (x) => val(x.crop) },
      { label: '使用權文件', render: (x) => val(x.rightDoc) },
      { label: '申報／上限（公頃）', cls: 'num', render: (x) => num(x.declaredHa, 4) + ' / ' + num(x.capHa, 4) },
      { label: '農路水塘佔比', cls: 'num', render: (x) => pct(x.roadPondPct) },
      { label: '地籍與航照', render: (x) => x.cadastreMatch === true ? '相符' : x.cadastreMatch === false ? h('span', { class: 'bad' }, '不符') : '—' }
    ], all[status], { emptyText: '此分類沒有案件（資料接口未接入）', onRow: (x) => { location.hash = '#/baseline/' + encodeURIComponent(x.id); } }));
    body.appendChild(h('p', { class: 'muted' }, h('a', { href: '#/baseline/blank' }, '以空白範本開啟單筆範圍確認')));
  }
  root.appendChild(body);
  draw();

  async function baselineItem(root, id) {
    const { h, val, num, pct, card, kv } = SA.ui;
    const CFG = SA.config;
    const x = (id !== 'blank' && await SA.api.getBaseline(id)) || {};
    const locked = x.status === 'locked';
    root.appendChild(h('div', { class: 'case-head' },
      h('a', { href: '#/baseline', class: 'back' }, '← 災前基準確認'),
      h('h1', null, '單筆範圍確認　', val(x.landNo || '[地段地號]'), '　', val(x.crop || '[作物]'))));
    if (!SA.api.CONNECTED) root.appendChild(SA.ui.notConnected());

    const layers = [['cadastre', '地籍外框', '#15213b'], ['declared', '農民申報範圍', '#d9822b'], ['landuse', '國土利用調查（農業使用）', '#2e8b57'], ['neighbors', '鄰地', '#8a93a6']];
    const on = { cadastre: true, declared: true, landuse: true, neighbors: true };
    const mapBox = h('div');
    const L = x.layers || {};
    const ringOf = (g) => g && g.coordinates && g.coordinates[0];
    const drawMap = () => {
      mapBox.innerHTML = '';
      const polys = [];
      if (on.neighbors) (L.neighbors || []).forEach((g) => polys.push({ ring: ringOf(g), fill: '#d5d9e0', stroke: '#8a93a6', opacity: 0.7, title: '鄰地' }));
      if (on.landuse && L.landuse) polys.push({ ring: ringOf(L.landuse), fill: '#7fbf8e', stroke: '#2e8b57', opacity: 0.55, title: '國土利用調查：農業使用' });
      if (on.cadastre && L.cadastre) polys.push({ ring: ringOf(L.cadastre), fill: 'none', stroke: '#15213b', width: 2.5, title: '地籍外框' });
      if (on.declared && L.declared) polys.push({ ring: ringOf(L.declared), fill: 'none', stroke: '#d9822b', width: 2.5, dash: '8 5', title: '農民申報範圍' });
      mapBox.appendChild(SA.ui.mapSvg({ polys: polys.filter((p) => p.ring), height: 420, empty: '套疊圖（圖資未接入）' }));
      mapBox.appendChild(SA.ui.legend(layers.map(([k, t, c]) => [c, t, k === 'declared'])));
    };
    drawMap();
    const toggles = h('div', { class: 'layer-toggles' }, layers.map(([k, t]) => h('label', { class: 'inline' }, h('input', { type: 'checkbox', checked: true, onchange: (e) => { on[k] = e.target.checked; drawMap(); } }), t)));

    const checks = x.checks && x.checks.length ? x.checks : [
      { label: '申報面積未超過本筆面積 × 持分', ok: null }, { label: '扣除農路水塘後的種植範圍', ok: null }, { label: '地籍與航照相符', ok: null }, { label: '使用權文件有效期間涵蓋本期作', ok: null }
    ];
    const methodBox = h('div', { class: 'radios', role: 'radiogroup', 'aria-label': '確認方式' }, CFG.baselineConfirmMethods.map((m, i) => h('label', { class: 'radio' },
      h('input', { type: 'radio', name: 'bm', value: m.key, checked: i === 0 ? true : null, disabled: locked ? true : null }), h('span', null, h('strong', null, m.label), h('small', null, m.note)))));
    const note = h('textarea', { rows: '2', placeholder: '確認說明（修正範圍時註明扣除項目）', 'aria-label': '確認說明', disabled: locked ? true : null });

    root.appendChild(h('div', { class: 'case-grid' },
      h('div', { class: 'col' }, card('套疊（色塊示意）', h('div', null, toggles, mapBox))),
      h('div', { class: 'col' },
        card('申報資料', kv([['申請人', x.applicant], ['身分', x.identity], ['使用權文件', x.rightDoc], ['申報面積', x.declaredHa ? num(x.declaredHa, 4) + ' 公頃' : null], ['可申報上限（本筆面積 × 持分）', x.capHa ? num(x.capHa, 4) + ' 公頃' : null], ['農路水塘佔比', pct(x.roadPondPct)], ['佐證', x.proof]])),
        card('系統檢查結果', h('ul', { class: 'checks' }, checks.map((c) => h('li', { class: c.ok === true ? 'ok' : c.ok === false ? 'no' : 'na' }, h('span', { class: 'ck' }), h('div', null, h('strong', null, c.label), h('span', { class: 'muted' }, val(c.detail))))))),
        card('確認方式', h('div', { class: 'form' }, methodBox, note,
          h('button', { class: 'btn btn-go btn-block', disabled: locked ? true : null, onclick: async () => {
            const m = (methodBox.querySelector('input:checked') || {}).value;
            if (m === 'adjust' && !note.value.trim()) { SA.ui.toast('修正範圍後確認，請註明扣除項目', 'warn'); return; }
            if (x.declaredHa && x.capHa && x.declaredHa > x.capHa) { SA.ui.toast('申報超過權利面積，系統已擋下，不能鎖定', 'warn'); return; }
            const label = CFG.baselineConfirmMethods.find((y) => y.key === m).label;
            if (m === 'visit') { await SA.api.scheduleVisit('baseline:' + id, 'baseline'); SA.ui.queuedToast('排定到場確認'); SA.refreshNav(); return; }
            const ok = await SA.ui.confirmDialog('鎖定為災前基準', '確認方式：' + label + '。鎖定後災後不再量面積。', '鎖定');
            if (!ok) return;
            await SA.api.confirmBaseline(id, m, note.value.trim()); SA.ui.queuedToast('災前基準鎖定'); SA.refreshNav();
          } }, locked ? '已鎖定' : '確認並鎖定為災前基準'),
          h('p', { class: 'muted small' }, '範圍只租一部分或地籍對不上時列為「範圍需確認」。自填資料經公所確認後才算數，切結書不能當作證明。'))))));
  }
};
