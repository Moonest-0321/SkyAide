/*
 * 補件與無人機
 * C 缺失一律先要求補件；補件期限過了仍未補，依公所實際量能處理：
 * 影像類（雲遮、影像不清楚）有無人機量能時計算航線、提交飛行申請、派飛；其餘與超出量能者排入到場。
 */
SA.pages.followup = async function (root, r) {
  const { h, val, num, card, table, kv } = SA.ui;
  const CFG = SA.config;
  const CAP_KEY = 'skyaide.office.capacity';
  const [all, supp, droneSt] = await Promise.all([SA.api.listCases(SA.state.eventId), SA.api.localSupplementStates(), SA.api.localDroneStates()]);
  let items = SA.rules.workItems(all || [], supp);
  let cap = Object.assign({}, CFG.capacity, (() => { try { return JSON.parse(localStorage.getItem(CAP_KEY)) || {}; } catch (e) { return {}; } })());

  const cs = () => items.filter((x) => x.kind === 'C');
  const ofState = (s) => cs().filter((x) => x.supplementState === s);

  root.appendChild(SA.ui.pageHead('C 缺失', '補件與無人機', SA.ui.notConnected()));
  root.appendChild(h('ol', { class: 'steps' },
    h('li', null, h('strong', null, '先要求補件'), h('span', null, 'C 缺失一律先通知申請人補件，原因碼以白話呈現。')),
    h('li', null, h('strong', null, '補件回來重新檢核'), h('span', null, '進入 S1 登錄，五項全過即重新分級。')),
    h('li', null, h('strong', null, '期限過了依公所量能處理'), h('span', null, '影像類（雲遮、影像不清楚）有無人機量能時計算航線、提交飛行申請、派飛；其餘與超出量能者排入到場。'))));

  const body = h('div');
  let tab = r.params.tab || 'supplement';
  function draw() {
    items = SA.rules.workItems(all || [], supp);
    body.innerHTML = '';
    const exp = ofState('expired');
    body.appendChild(h('div', { class: 'tiles tiles-4' },
      tile('補件中', ofState('pending').length, '已通知，等待申請人補件', 'chip-b'),
      tile('已補件', ofState('received').length, '重新檢核中', 'chip-info'),
      tile('期限已過・影像類', exp.filter((x) => x._route === 'drone').length, '無人機候選', 'chip-c'),
      tile('期限已過・非影像類', exp.filter((x) => x._route === 'visit').length, '到場候選', 'chip-c')));
    body.appendChild(SA.ui.tabs([
      { key: 'supplement', label: '① 補件', count: cs().length },
      { key: 'capacity', label: '② 依量能分配' },
      { key: 'drone', label: '③ 無人機任務' },
      { key: 'reasons', label: '原因碼對照' }
    ], tab, (k) => { tab = k; draw(); }));
    ({ supplement: supplementView, capacity: capacityView, drone: droneView, reasons: reasonView })[tab]();
  }
  function tile(label, n, sub, chip) {
    return h('div', { class: 'tile' }, h('span', { class: 'chip ' + chip }, label), h('p', { class: 'tile-n' }, (all || []).length ? String(n) : '—'), h('p', { class: 'tile-s' }, sub));
  }
  const caseLink = (c) => h('a', { href: '#/case/' + encodeURIComponent(c.id) }, val(c.caseNo));
  const need = (c) => (c.reasons || []).map((x) => (CFG.reasonRoute[x] || {}).supplement || x).filter((v, i, a) => a.indexOf(v) === i).join('；');

  // ---------- ① 補件 ----------
  function supplementView() {
    const list = cs().sort((a, b) => SA.rules.priority(b) - SA.rules.priority(a));
    body.appendChild(h('p', { class: 'muted' }, '乙等起，C 缺失申請人於申請期內收到補件提醒，可補 App 照片或更正申報。補件回來或期限過了，在這裡更新狀態。'));
    body.appendChild(h('div', { class: 'actions' }, h('button', { class: 'btn btn-primary', onclick: async () => {
      const p = list.filter((c) => c.supplementState === 'pending');
      if (!p.length) { SA.ui.toast('沒有補件中的案件', 'warn'); return; }
      const ok = await SA.ui.confirmDialog('發送補件提醒', '共 ' + p.length + ' 件，依原因碼以白話通知申請人。', '發送');
      if (ok) { await SA.api.sendNotice(p.map((c) => c.id), 'supplement', {}); SA.ui.queuedToast('補件提醒'); SA.refreshNav(); }
    } }, '發送補件提醒（補件中的案件）')));
    body.appendChild(table([
      { label: '申請案號', render: caseLink },
      { label: '地號', render: (c) => val(c.landNo) },
      { label: '類別', render: (c) => val(c.crop) + ' × ' + val(c.hazard) },
      { label: '等級', render: (c) => SA.ui.levelChip(c.level) },
      { label: '原因碼', render: (c) => (c.reasons || []).join('、') || '—' },
      { label: '要補的資料', render: (c) => need(c) || '—' },
      { label: '補件狀態', render: (c) => h('select', { 'aria-label': '補件狀態', onchange: async (e) => { supp[c.id] = e.target.value; await SA.api.setSupplementState(c.id, e.target.value); SA.refreshNav(); draw(); } },
        Object.entries(CFG.supplementStates).map(([k, t]) => h('option', { value: k, selected: c.supplementState === k ? true : null }, t))) },
      { label: '期限後', render: (c) => c.supplementState === 'received' ? '重新檢核' : SA.rules.isImagery(c.reasons) ? '影像類：無人機（依量能）' : '到場（依量能）' }
    ], list, { emptyText: (all || []).length ? '沒有 C 缺失案件' : '尚無案件（資料接口未接入）' }));
  }

  // ---------- ② 依量能分配 ----------
  function capacityView() {
    const inp = (key, label, step) => h('label', { class: 'field' }, label, h('input', { type: 'number', min: '0', step: step || '1', value: cap[key] || 0, 'aria-label': label, onchange: (e) => { cap[key] = Math.max(0, parseFloat(e.target.value) || 0); try { localStorage.setItem(CAP_KEY, JSON.stringify(cap)); } catch (er) { /* 無法保存 */ } draw(); } }));
    const a = SA.rules.allocate(items, cap);
    const count = (k) => items.filter((x) => x.kind === k).length;
    body.appendChild(h('div', { class: 'grid-1-2' },
      card('本期公所量能', h('div', { class: 'form' },
        inp('droneCases', '無人機可處理件數'),
        inp('personDays', '可投入現勘人日', '0.5'),
        inp('perPersonDay', '每人日可處理筆數'),
        h('p', { class: 'muted small' }, '每人日筆數起始值取 10 筆（B、C 為較難案件，表 68 取最保守值）。量能變動時重新分配即可。'))),
      card('分配結果', h('div', null,
        kv([
          ['無人機候選（期限已過・影像類）', String(a.drone.length + a.overflow.length) + ' 件'],
          ['派無人機', a.drone.length + ' 件（量能 ' + a.droneCapacity + '）'],
          ['超出無人機量能，轉到場', a.overflow.length + ' 件'],
          ['到場需求', (a.visit.length + a.over.length) + ' 件：B 邊緣 ' + count('B') + '、抽查 ' + count('sample') + '、申訴 ' + count('appeal') + '、C 缺失 ' + (items.filter((x) => x.kind === 'C' && x._route === 'visit').length + a.overflow.length) + '、乙丙等依現行 ' + count('current')],
          ['排入到場', a.visit.length + ' 件（量能 ' + a.visitCapacity + '）'],
          ['超出量能，排隊', h('span', { class: a.over.length ? 'bad' : null }, a.over.length + ' 件')]
        ]),
        h('div', { class: 'actions' },
          h('button', { class: 'btn btn-primary', onclick: () => {
            const route = a.visit.map((c) => ({ caseId: c.id, caseNo: c.caseNo, landNo: c.landNo, kind: c.kind, confirm: c.kind === 'C' ? (c.reasons || []).join('、') : c.kind === 'B' ? '損失率是否達 20%' : c.kind === 'sample' ? '抽查：現勘損失率' : c.kind === 'appeal' ? '申訴：到場確認' : '依現行規定勘查', center: c.center || null }));
            try { localStorage.setItem('skyaide.field.route', JSON.stringify({ at: new Date().toISOString(), eventId: SA.state.eventId, items: route })); SA.ui.toast('已存到本機，現勘頁可離線開啟（' + route.length + ' 筆）'); }
            catch (e) { SA.ui.toast('無法存到本機：' + e.message, 'warn'); }
          } }, '下載到場清單到公務手機'),
          h('button', { class: 'btn', onclick: () => { tab = 'drone'; draw(); } }, '前往無人機任務 →'))))));
    const cols = [
      { label: '#', cls: 'num', render: (c, i) => String(i + 1) },
      { label: '類型', render: (c) => ({ B: 'B 邊緣', sample: '抽查', appeal: '申訴', C: 'C 缺失', current: '依現行勘查' })[c.kind] },
      { label: '申請案號', render: caseLink },
      { label: '地號', render: (c) => val(c.landNo) },
      { label: '等級', render: (c) => SA.ui.levelChip(c.level) },
      { label: '原因碼', render: (c) => (c.reasons || []).join('、') || '—' }
    ];
    body.appendChild(card('排入到場（依 B 邊緣、抽查、申訴、C 缺失、依現行勘查排序）', table(cols, a.visit, { emptyText: '沒有排入的案件（請先設定現勘人日）' })));
    body.appendChild(card('超出量能，排隊', h('div', null, h('p', { class: 'muted small' }, '量能增加或其他案件完成後依序遞補；勘查期截止前仍未處理者，請評估調派支援人力。'), table(cols, a.over, { emptyText: '沒有超出量能的案件' }))));
  }

  // ---------- ③ 無人機任務 ----------
  function droneView() {
    const a = SA.rules.allocate(items, cap);
    const { groups, noLocation } = SA.rules.droneGroups(a.drone);
    const routes = groups.map((g) => { const rt = SA.rules.droneRoute(g); g.id = 'G-' + g.members.map((m) => m.id).sort().join('|').slice(0, 60); g.route = rt; return g; });
    body.appendChild(h('p', { class: 'muted' }, '只對分配到無人機的案件規劃。相距 ' + CFG.droneGroupRadiusM + ' 公尺內分為一組、共用起飛點（道路通阻資料未接入時以組內中心點暫代）。每組依序：計算航線 → 提交飛行申請 → 派飛 → 資料回傳；照片、正射影像與飛行紀錄回到 S1 登錄後重新檢核。'));
    if (!a.droneCapacity) body.appendChild(h('p', { class: 'banner warn' }, '尚未設定無人機量能，影像類案件全部轉到場。請到「② 依量能分配」設定。'));

    const colors = ['#2f6fdb', '#d9822b', '#2e8b57', '#9b59b6', '#c0392b', '#16a085', '#7f8c8d', '#b7950b'];
    const polys = [], points = [], lines = [];
    routes.forEach((g, gi) => {
      const col = colors[gi % colors.length];
      g.route.order.forEach((m) => { if (m.geometry && m.geometry.coordinates) polys.push({ ring: m.geometry.coordinates[0], fill: col, stroke: col, title: m.caseNo + ' ' + val(m.landNo) }); });
      points.push({ lat: g.takeoff.lat, lon: g.takeoff.lon, label: '起飛 ' + (gi + 1), fill: col, r: 8 });
      lines.push({ pts: [g.takeoff].concat(g.route.order.map((m) => m.center)).concat([g.takeoff]), stroke: col, dash: '6 4' });
    });
    body.appendChild(card('任務地圖（色塊示意）', h('div', null, SA.ui.mapSvg({ polys, points, lines, height: 420, empty: '尚無無人機任務' }), SA.ui.legend([['#2f6fdb', '目標坵塊（依組別上色）'], ['#15213b', '起飛點'], ['#2f6fdb', '航線', true]]))));

    const stepNames = [['route', '計算航線'], ['apply', '提交飛行申請'], ['dispatch', '派飛'], ['returned', '資料回傳']];
    const statusOf = (g) => droneSt[g.id] || {};
    const nextStep = (g) => stepNames.find(([k]) => !statusOf(g)[k]);
    body.appendChild(h('div', { class: 'actions' },
      h('button', { class: 'btn', onclick: () => SA.ui.download('C-無人機坵塊邊界.kml', SA.rules.kml(a.drone, '天相星 C-無人機'), 'application/vnd.google-earth.kml+xml') }, '匯出坵塊邊界檔（KML）'),
      h('button', { class: 'btn', onclick: () => {
        const rows = [];
        routes.forEach((g, gi) => g.route.order.forEach((m, j) => rows.push([gi + 1, j + 1, g.takeoff.lat.toFixed(6), g.takeoff.lon.toFixed(6), m.caseNo, m.landNo, m.center ? m.center.lat.toFixed(6) : '', m.center ? m.center.lon.toFixed(6) : '', (m.reasons || []).join('、')])));
        SA.ui.download('C-無人機航線.csv', SA.ui.csv(['組別', '航點順序', '起飛點緯度', '起飛點經度', '申請案號', '地號', '緯度', '經度', '原因碼'], rows), 'text/csv');
      } }, '匯出航線清單')));
    body.appendChild(table([
      { label: '組別', cls: 'num', render: (g, i) => String(i + 1) },
      { label: '件數', cls: 'num', render: (g) => String(g.members.length) },
      { label: '面積（公頃）', cls: 'num', render: (g) => num(g.route.areaHa, 2) },
      { label: '航程', cls: 'num', render: (g) => statusOf(g).route ? num(g.route.distM / 1000, 2) + ' 公里' : '—' },
      { label: '預估飛行', cls: 'num', render: (g) => statusOf(g).route ? Math.ceil(g.route.minutes) + ' 分・電池 ' + g.route.batteries + ' 顆' : '—' },
      { label: '進度', render: (g) => h('span', { class: 'prog-steps' }, stepNames.map(([k, t]) => h('span', { class: statusOf(g)[k] ? 'done' : null, title: statusOf(g)[k] ? SA.ui.datetime(statusOf(g)[k]) : '未完成' }, t))) },
      { label: '下一步', render: (g) => {
        const n = nextStep(g);
        if (!n) return h('span', { class: 'good' }, '已回傳，重新檢核');
        return h('button', { class: 'btn btn-sm' + (n[0] === 'route' ? '' : ' btn-primary'), onclick: async () => {
          if (n[0] === 'apply') { const ok = await SA.ui.confirmDialog('提交飛行申請', '第 ' + (routes.indexOf(g) + 1) + ' 組：起飛點 ' + g.takeoff.lat.toFixed(5) + ', ' + g.takeoff.lon.toFixed(5) + '，預估 ' + Math.ceil(g.route.minutes) + ' 分鐘。依空域與活動規定提交申請。', '提交'); if (!ok) return; }
          if (n[0] === 'dispatch') { const ok = await SA.ui.confirmDialog('派飛', '由合作的合格業者或縣府機隊執行。風速過大或空域受限時改排福衛八號取像或到場。', '派飛'); if (!ok) return; }
          await SA.api.droneStep(g.id, n[0], { takeoff: g.takeoff, caseIds: g.route.order.map((m) => m.id), distM: Math.round(g.route.distM), minutes: Math.ceil(g.route.minutes) });
          droneSt[g.id] = Object.assign({}, droneSt[g.id], { [n[0]]: new Date().toISOString() });
          SA.ui.queuedToast(n[1]); SA.refreshNav(); draw();
        } }, n[1]);
      } }
    ], routes, { emptyText: a.droneCapacity ? '沒有分配到無人機的案件' : '尚未設定無人機量能' }));
    if (noLocation) body.appendChild(h('p', { class: 'warn' }, noLocation + ' 件缺少坵塊中心座標，無法分組'));
  }

  // ---------- 原因碼對照 ----------
  function reasonView() {
    const rows = Object.keys(CFG.reasonRoute).map((k) => Object.assign({ reason: k, n: cs().filter((c) => (c.reasons || []).includes(k)).length }, CFG.reasonRoute[k]));
    body.appendChild(table([
      { label: '原因碼', key: 'reason' },
      { label: '說明', key: 'note' },
      { label: '先要求補件', key: 'supplement' },
      { label: '期限過了未補件', render: (x) => x.imagery ? '影像類：無人機（依量能），超出者到場' : '到場（依量能）' },
      { label: '件數', cls: 'num', render: (x) => (all || []).length ? String(x.n) : '—' }
    ], rows));
  }

  root.appendChild(body);
  draw();
};
