/* 災後總覽：法定期限倒數、各級案件數、各類別系統等級（表 21、表 24 C） */
SA.pages.overview = async function (root) {
  const { h, val, num, date, datetime, card, table, levelChip, kv } = SA.ui;
  const ev = SA.currentEvent();
  const [ov, cats] = await Promise.all([SA.api.getOverview(SA.state.eventId), SA.api.listCategories(SA.state.eventId)]);
  const o = ov || {};
  const counts = o.counts || {};
  const D = SA.config.deadlines;

  root.appendChild(SA.ui.pageHead(
    '農業部公告　' + val(ev && ev.area) + '　' + ((ev && ev.crops && ev.crops.join('、')) || '[公告品項]'),
    ((ev && ev.name) || '[災害名稱]') + ' 現金救助・總覽',
    SA.ui.notConnected()));

  // ---------- 時程 ----------
  let trial = SA.state.trialAnnounce || (ev && ev.announceDate) || '';
  const timelineBox = h('div');
  function drawTimeline() {
    timelineBox.innerHTML = '';
    const dl = SA.rules.deadlines(trial);
    const today = new Date();
    const dayOf = (start, end) => {
      if (!dl) return null;
      const d = SA.rules.daysBetween(start, today);
      if (d < 1) return '尚未開始';
      if (today > end) return '已截止';
      return '今天第 ' + d + ' 天';
    };
    const graded = ev && ev.radarAt && ev.gradedAt ? ((new Date(ev.gradedAt) - new Date(ev.radarAt)) / 3600000) : null;
    const steps = [
      { k: '警報', d: datetime(ev && ev.alertAt), s: '鎖定災前影像與程式版本、排定取像' },
      { k: '雷達到站', d: datetime(ev && ev.radarAt), s: '' },
      { k: '分級完成', d: datetime(ev && ev.gradedAt), s: graded !== null ? '費時 ' + graded.toFixed(1) + ' 小時（目標 ' + D.gradingHours + ' 小時內）' : '目標 ' + D.gradingHours + ' 小時內' },
      { k: '公告', d: dl ? date(dl.announce, true) : '—', s: '' },
      { k: '申請期', d: dl ? '至 ' + date(dl.applyEnd, true) : D.applyWorkdays + ' 個工作日', s: dl ? dayOf(dl.announce, dl.applyEnd) : '公告翌日起，逾期不受理', hot: dl && today <= dl.applyEnd && today > dl.announce },
      { k: '勘查期', d: dl ? '至 ' + date(dl.surveyEnd, true) : D.surveyDays + ' 日', s: dl ? dayOf(dl.announce, dl.surveyEnd) : '公告翌日起', hot: dl && today <= dl.surveyEnd && today > dl.applyEnd },
      { k: '報送縣府', d: dl ? '至 ' + date(dl.reportEnd) : D.reportDays + ' 日', s: '完成勘查後' },
      { k: '縣府抽查', d: dl ? '至 ' + date(dl.countyEnd) : D.countyAuditDays + ' 日', s: '' },
      { k: '農糧署審核', d: dl ? '至 ' + date(dl.afaEnd) : D.afaReviewDays + ' 日', s: '' }
    ];
    timelineBox.appendChild(h('ol', { class: 'timeline' }, steps.map((s) => h('li', { class: s.hot ? 'hot' : null },
      h('span', { class: 'tl-bar' }), h('strong', null, s.k), h('span', null, s.d), s.s ? h('small', null, s.s) : null))));
  }
  drawTimeline();
  const trialInput = h('input', { type: 'date', value: trial, 'aria-label': '公告日', onchange: (e) => { trial = e.target.value; SA.state.trialAnnounce = trial; drawTimeline(); } });
  root.appendChild(card('時程', h('div', null,
    timelineBox,
    h('div', { class: 'row-note' },
      h('label', { class: 'inline' }, '公告日', trialInput),
      h('span', { class: 'muted' }, '期限依公告日推算；工作日未扣國定假日，以公告為準。'),
      h('span', { class: 'muted' }, '天氣參數提示：', val(ev && ev.weatherParamHint), '（以公告為準）')))));

  // ---------- 案件數 ----------
  const bs = o.bySource || {};
  const tile = (chip, n, sub, cls) => h('div', { class: 'tile ' + (cls || '') }, chip, h('p', { class: 'tile-n' }, num(n)), h('p', { class: 'tile-s' }, sub));
  root.appendChild(h('div', { class: 'tiles' },
    tile(h('span', { class: 'chip chip-blank' }, '已申請'), o.applied, '本人 ' + num(bs.self) + '・農會 ' + num(bs.farmersAssoc) + '・委託 ' + num(bs.proxy)),
    tile(SA.ui.gradeChip('A_MET'), counts.A_MET, '證據完整，損失確定 ≥ 20%'),
    tile(SA.ui.gradeChip('A_NOT_MET'), counts.A_NOT_MET, '證據完整，損失確定 < 20%'),
    tile(SA.ui.gradeChip('B'), counts.B, '損失區間跨過 20%'),
    tile(SA.ui.gradeChip('C'), counts.C, '證據有缺，看原因碼'),
    tile(h('span', { class: 'chip chip-info' }, '已主動通知'), o.notifiedUnapplied, '受損明顯但申請期內未申請')));
  root.appendChild(h('div', { class: 'tiles tiles-4' },
    tile(h('span', { class: 'chip chip-blank' }, '登錄田區'), o.registeredParcels, '已鎖定災前基準'),
    tile(h('span', { class: 'chip chip-blank' }, '已送件'), o.submitted, '以 QR 碼送件'),
    tile(h('span', { class: 'chip chip-blank' }, '明顯受損未送件'), o.damagedUnsubmitted, '已通知可以申請'),
    tile(h('span', { class: 'chip chip-blank' }, 'App 照片已上傳'), o.appPhotos, '農業部現地照相 App')));

  // ---------- 類別系統等級 ----------
  const L = SA.config.levels;
  const catCard = card('各類別的系統等級：決定這一場結果怎麼用', h('div', null,
    table([
      { label: '類別（作物 × 災害）', render: (c) => val(c.crop) + ' × ' + val(c.hazard) },
      { label: '等級', render: (c) => levelChip(c.level) },
      { label: '件數', cls: 'num', render: (c) => num(c.count) },
      { label: '本所怎麼用', render: (c) => c.level ? L[c.level].office : '—' }
    ], cats || [], { emptyText: '尚無類別資料（資料接口未接入）' }),
    h('div', { class: 'legend' }, ['甲', '乙', '丙'].map((k) => h('p', null, levelChip(k), ' ', h('strong', null, L[k].name), '：', L[k].role, '。'))),
    h('p', { class: 'muted' }, '等級由每場災害後的 S8 評等決定，任一場 A 精確度下界未達 95% 即降一等；類別不得高於整體。見「抽查、封存、評等」。')));

  const w = o.workload || {};
  const wl = card('本場勘查工作量', h('div', null,
    kv([
      ['書面審核或通知', num(w.paper)],
      ['到場', h('span', null, num(w.visit), h('span', { class: 'muted' }, '（現行 ' + num(w.currentRuleVisit) + '）'))],
      ['　抽查 A 級 20%', num(w.sampleA)],
      ['　B 邊緣（甲等類別）', num(w.bVisit)],
      ['　C 須到場', num(w.cVisit)],
      ['　乙、丙等類別依現行勘查', num(w.currentRule)],
      ['無人機補拍', num(w.drone)],
      ['等候補件', num(w.waitingSupplement)]
    ]),
    h('p', { class: 'muted' }, '補拍與補件回來後重新檢核，五項全過即重新分級。')));
  root.appendChild(h('div', { class: 'grid-2-1' }, catCard, wl));

  // ---------- 資料交付、接下來 ----------
  const delivery = (o.delivery && o.delivery.length) ? o.delivery : [
    { label: '分級清冊與存證報告交本所（封存根雜湊）', done: null },
    { label: '分級清冊副本交縣市政府農業處，作為抽查參考', done: null },
    { label: 'B、C 清單離線下載至公務手機', done: null },
    { label: '熱區圖交縣府提報（與官方統計偏差 ±20% 內）', done: null }
  ];
  root.appendChild(h('div', { class: 'grid-2' },
    card('資料交付', h('ul', { class: 'checklist' }, delivery.map((d) => h('li', { class: d.done === true ? 'ok' : d.done === false ? 'no' : 'na' },
      h('span', { class: 'ck', 'aria-hidden': 'true' }), d.label, d.detail ? h('span', { class: 'muted' }, '：' + d.detail) : h('span', { class: 'muted' }, '：—'))))),
    card('接下來', h('ul', { class: 'links' },
      h('li', null, h('a', { href: '#/intake' }, '受理：掃描 QR 碼調閱預填資料 →')),
      h('li', null, h('a', { href: '#/list' }, '分級清單：書面審核 ' + num(w.paper) + ' 件 →')),
      h('li', null, h('a', { href: '#/followup' }, 'C 缺失：派無人機 ' + num(w.drone) + ' 件、追補件 ' + num(w.waitingSupplement) + ' 件 →')),
      h('li', null, h('a', { href: 'field.html' }, '現勘：今日路線 →'))))));
};
