/* 分級清單：類別等級、損失區間、可信度、分級、原因碼與處理方式；可離線下載、匯出（表 21、圖 28） */
SA.pages.list = async function (root, r) {
  const { h, val, num, table, levelChip, gradeChip, intervalBar, intervalText } = SA.ui;
  const [cases0, appeals] = await Promise.all([SA.api.listCases(SA.state.eventId), SA.api.localAppeals()]);
  const cases = cases0 || [];

  // 補上由規則算出的欄位（後端已給則沿用後端）
  cases.forEach((c) => {
    if (!c.grade) c.grade = SA.rules.grade(c);
    if (!c.reasons) c.reasons = SA.rules.reasonCodes(c.checks);
    c._cred = c.credibility || SA.rules.credibility(c.checks);
    c._hd = SA.rules.handling({ level: c.level, grade: c.grade, sampled: c.sampled, reasons: c.reasons, supplementState: c.supplementState, objection: !!(appeals[c.id] || c.appeal) });
    c._pri = SA.rules.priority(c);
    c._g = c.level === '丙' ? null : c.grade; // 丙等分級不提供給公所，也不參與分級篩選
  });

  const st = { grade: r.params.grade || 'all', level: 'all', q: '', sort: 'priority' };

  root.appendChild(SA.ui.pageHead('先看證據、再看損失', '分級清單', SA.ui.notConnected()));
  root.appendChild(h('p', { class: 'lead' }, '五項檢核未過者不進入損失判斷，直接列 C 並附原因碼；處理方式依該筆所屬類別的系統等級而定。丙等類別的分級不提供給公所。'));

  const countOf = (g) => cases.filter((c) => g === 'all' || c._g === g).length;
  const tabsBox = h('div');
  const tbl = h('div');
  const levelSel = h('select', { 'aria-label': '系統等級', onchange: (e) => { st.level = e.target.value; draw(); } },
    h('option', { value: 'all' }, '全部等級'), ['甲', '乙', '丙'].map((l) => h('option', { value: l }, l + '等')));
  const sortSel = h('select', { 'aria-label': '排序', onchange: (e) => { st.sort = e.target.value; draw(); } },
    h('option', { value: 'priority' }, '依優先度（預估金額 × 不確定程度）'), h('option', { value: 'caseNo' }, '依申請案號'));
  const search = h('input', { type: 'search', placeholder: '案號、地號、作物', 'aria-label': '搜尋', oninput: (e) => { st.q = e.target.value.trim(); draw(); } });

  function filtered() {
    let rows = cases.filter((c) => (st.grade === 'all' || c._g === st.grade) && (st.level === 'all' || c.level === st.level));
    if (st.q) rows = rows.filter((c) => [c.caseNo, c.landNo, c.crop].some((x) => x && String(x).includes(st.q)));
    rows.sort(st.sort === 'caseNo' ? (a, b) => String(a.caseNo).localeCompare(String(b.caseNo)) : (a, b) => b._pri - a._pri);
    return rows;
  }

  function draw() {
    tabsBox.innerHTML = '';
    tabsBox.appendChild(SA.ui.tabs([
      { key: 'all', label: '全部', count: cases.length },
      { key: 'A_MET', label: 'A 達標', count: countOf('A_MET') },
      { key: 'A_NOT_MET', label: 'A 未達標', count: countOf('A_NOT_MET') },
      { key: 'B', label: 'B 邊緣', count: countOf('B') },
      { key: 'C', label: 'C 缺失', count: countOf('C') }
    ], st.grade, (k) => { st.grade = k; draw(); }));
    tbl.innerHTML = '';
    tbl.appendChild(table([
      { label: '#', cls: 'num', render: (c, i) => String(i + 1) },
      { label: '申請案號', render: (c) => val(c.caseNo) },
      { label: '地號', render: (c) => val(c.landNo) },
      { label: '類別', render: (c) => val(c.crop) + ' × ' + val(c.hazard) },
      { label: '等級', render: (c) => levelChip(c.level) },
      { label: '損失區間', cls: 'w-iv', render: (c) => c._hd.gradeVisible ? h('div', null, intervalBar(c.interval, c.crop), h('small', null, intervalText(c.interval))) : h('span', { class: 'muted' }, '不提供') },
      { label: '可信度', render: (c) => c._hd.gradeVisible ? val(c._cred) : h('span', { class: 'muted' }, '不提供') },
      { label: '分級', render: (c) => c._hd.gradeVisible ? gradeChip(c.grade, { reference: c.level === '乙' }) : h('span', { class: 'muted' }, '不提供') },
      { label: '原因碼', render: (c) => c.reasons && c.reasons.length ? c.reasons.join('、') : '—' },
      { label: '處理方式', render: (c) => h('span', { class: 'hd hd-' + c._hd.tone }, c._hd.title.replace(/^.+?：/, '')) }
    ], filtered(), {
      emptyText: cases.length ? '沒有符合條件的案件' : '尚無案件（資料接口未接入）',
      onRow: (c) => { location.hash = '#/case/' + encodeURIComponent(c.id); }
    }));
  }

  // ---------- 匯出 ----------
  const gradeLabel = (c) => (c._hd.gradeVisible && SA.config.grades[c.grade] ? SA.config.grades[c.grade].label : '');
  function exportRoster() { // 表 63：A／B／C 分級清冊
    const rows = cases.map((c) => [c.caseNo, c.landNo, gradeLabel(c), (c.reasons || []).join('、'), c.interval ? intervalText(c.interval) : '', c.level || '']);
    SA.ui.download('分級清冊.csv', SA.ui.csv(['申請案號', '地號', '分級', '原因碼', '損失區間', '類別等級'], rows), 'text/csv');
  }
  function exportBC() { // 表 63：B、C 級清單，優先序、位置、原因碼、要確認的項目；匯入農災 App 調查專案
    const bc = cases.filter((c) => c._g === 'B' || c._g === 'C').sort((a, b) => b._pri - a._pri);
    const rows = bc.map((c, i) => [i + 1, c.caseNo, c.landNo, c.center ? c.center.lat : '', c.center ? c.center.lon : '', gradeLabel(c), (c.reasons || []).join('、'), c.grade === 'B' ? '損失率是否達 20%' : (c.reasons || []).map((x) => (SA.config.reasonRoute[x] || {}).note || x).join('；')]);
    SA.ui.download('B、C級清單.csv', SA.ui.csv(['優先序', '申請案號', '地號', '緯度', '經度', '分級', '原因碼', '要確認的項目'], rows), 'text/csv');
  }
  function offline() { // B、C 清單離線下載至公務手機
    const bc = cases.filter((c) => c._g === 'B' || c._g === 'C');
    try {
      localStorage.setItem('skyaide.field.route', JSON.stringify({ at: new Date().toISOString(), eventId: SA.state.eventId, items: bc.map((c) => ({ caseId: c.id, caseNo: c.caseNo, landNo: c.landNo, kind: c.grade, confirm: (c.reasons || []).join('、'), center: c.center || null })) }));
      SA.ui.toast('已存到本機，現勘頁可離線開啟（' + bc.length + ' 筆）');
    } catch (e) { SA.ui.toast('無法存到本機：' + e.message, 'warn'); }
  }

  root.appendChild(h('div', { class: 'toolbar' },
    h('div', { class: 'toolbar-l' }, levelSel, sortSel, search),
    h('div', { class: 'toolbar-r' },
      h('button', { class: 'btn', onclick: offline }, '離線下載 B、C 清單'),
      h('button', { class: 'btn', onclick: exportBC }, '匯出至農災 App 調查專案'),
      h('button', { class: 'btn', onclick: exportRoster }, '匯出分級清冊'))));
  root.appendChild(tabsBox);
  root.appendChild(tbl);
  root.appendChild(h('p', { class: 'muted' }, '救助系統尚未介接前，以分級清冊匯出檔銜接；縣市抽查參考名單只作參考，不取代救助系統隨機抽選。',
    ' ', h('a', { href: '#/case/blank' }, '以空白範本開啟案件審核')));
  draw();
};
