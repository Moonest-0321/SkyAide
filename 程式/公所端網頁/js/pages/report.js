/* 層報、抽查、復查：勘查進度、救助統計表、縣府抽查戶數級距試算、復查與更正增撥、低利貸款受災證明書（表 24 F、表 64） */
SA.pages.report = async function (root) {
  const { h, val, num, pct, card, table, kv } = SA.ui;
  const CFG = SA.config;
  const ev = SA.currentEvent();
  const dl = SA.rules.deadlines(SA.state.trialAnnounce || (ev && ev.announceDate));
  const [rep, fus] = await Promise.all([SA.api.getReporting(SA.state.eventId), SA.api.listFollowups(SA.state.eventId)]);
  const r = rep || {};

  root.appendChild(SA.ui.pageHead('報送與抽查（各 7 日）', '層報與復查', SA.ui.notConnected()));

  const prog = SA.ui.isNum(r.surveyed) && SA.ui.isNum(r.total) && r.total > 0 ? r.surveyed / r.total : null;
  root.appendChild(h('div', { class: 'grid-2' },
    card('勘查進度', h('div', null,
      h('div', { class: 'progress', role: 'progressbar', 'aria-valuenow': prog !== null ? Math.round(prog * 100) : null, 'aria-valuemin': '0', 'aria-valuemax': '100' }, h('span', { style: { width: prog !== null ? (prog * 100) + '%' : '0' } })),
      kv([['已完成', num(r.surveyed) + ' / ' + num(r.total) + ' 件'], ['完成比例', pct(prog)], ['勘查截止', dl ? SA.ui.date(dl.surveyEnd, true) : null], ['報送截止', dl ? SA.ui.date(dl.reportEnd, true) + '（完成勘查後 7 日內）' : '完成勘查後 7 日內']]))),
    card('救助統計表', h('div', null,
      h('p', { class: 'muted' }, '系統產出救助統計表草稿；A／B／C 分級清冊作為附件。公所確認後報送縣府。'),
      h('div', { class: 'actions' },
        h('button', { class: 'btn', onclick: () => SA.ui.download('救助統計表草稿.csv', SA.ui.csv(['鄉鎮市區', '作物', '申請戶數', '申請面積（公頃）', '核定面積（公頃）', '平均受害率（%）', '救助金額（元）'], []), 'text/csv') }, '下載草稿'),
        h('button', { class: 'btn btn-primary', onclick: async () => {
          const ok = await SA.ui.confirmDialog('報送縣府', '將救助統計表與分級清冊附件報送縣市政府。', '報送');
          if (ok) { await SA.api.submitReport(SA.state.eventId, 'statTable'); SA.ui.queuedToast('報送縣府'); SA.refreshNav(); }
        } }, '報送縣府'))))));

  // 縣府抽查戶數
  const hh = h('input', { type: 'number', min: '1', value: SA.ui.isNum(r.households) ? r.households : '', placeholder: '申請總戶數', 'aria-label': '申請總戶數' });
  const out = h('div', { 'aria-live': 'polite' });
  function calc() {
    out.innerHTML = '';
    const res = SA.rules.countyAuditSize(parseInt(hh.value, 10));
    if (!res) { out.appendChild(h('p', { class: 'muted' }, '輸入申請總戶數即可試算。')); return; }
    out.appendChild(kv([['級距', res.rule], ['抽查戶數', res.sample + ' 戶'], ['合格標準', '符合率達 ' + pct(res.passRate, 0)], ['抽查次數', '以 ' + res.maxRounds + ' 次為限']]));
  }
  hh.addEventListener('input', calc); calc();
  root.appendChild(h('div', { class: 'grid-2' },
    card('縣府抽查戶數級距試算', h('div', null,
      h('label', { class: 'field' }, '申請總戶數', hh), out,
      table([{ label: '申請總戶數', key: 'a' }, { label: '抽查戶數', key: 'b' }], [
        { a: '未達 100 戶', b: '至少 5 戶（10 戶以下抽半數）' }, { a: '100 至未達 500 戶', b: '5%' }, { a: '500 至未達 1,500 戶', b: '至少 25 戶' }, { a: '1,500 戶以上', b: '至少 30 戶' }
      ]))),
    card('交縣府的抽查參考', h('div', null,
      h('p', { class: 'muted' }, '分級清冊副本與依異常程度排序的戶別名單交縣市政府，作為抽查參考；縣市抽查始終以救助系統隨機抽選，本名單不取代隨機抽選。'),
      h('button', { class: 'btn', onclick: async () => { await SA.api.submitReport(SA.state.eventId, 'countyReference'); SA.ui.queuedToast('抽查參考名單'); SA.refreshNav(); } }, '送出分級清冊副本與參考名單')))));

  // 復查、更正、低利貸款
  const K = { appeal: '復查', correction: '更正增撥', loan: '低利貸款受災證明書' };
  const dueOf = (f) => {
    const base = SA.rules.parseDate(f.kind === 'appeal' ? f.noticeAt : f.noticeAt);
    if (!base) return null;
    if (f.kind === 'appeal') return SA.ui.date(SA.rules.addDays(base, CFG.deadlines.appealDays), true);
    if (f.kind === 'correction') { const d = new Date(base); d.setMonth(d.getMonth() + CFG.deadlines.correctionMonths); return SA.ui.date(d, true); }
    return null;
  };
  root.appendChild(card('復查、更正增撥與受災證明', h('div', null,
    h('p', { class: 'muted' }, '農民接獲通知後 7 日內可申請復查；登錄錯誤者 4 個月內可申請更正增撥；另可核發低利貸款受災證明書。結果畫面同時顯示申報值與核定值。'),
    table([
      { label: '申請案號', render: (f) => val(f.caseNo) },
      { label: '類型', render: (f) => K[f.kind] || val(f.kind) },
      { label: '收件', render: (f) => SA.ui.date(f.receivedAt) },
      { label: '期限', render: (f) => val(dueOf(f)) },
      { label: '狀態', render: (f) => val(f.status) }
    ], fus || [], { emptyText: '尚無復查或更正申請（資料接口未接入）' }))));
};
