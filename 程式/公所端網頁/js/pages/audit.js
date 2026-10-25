/* 抽查、封存、評等：20% 抽查結果、Merkle 根、逐類別下界與下一場等級（表 21、S7、S8、三、4(14)） */
SA.pages.audit = async function (root) {
  const { h, val, num, pct, card, table, kv, levelChip, gradeChip } = SA.ui;
  const CFG = SA.config, U = CFG.upgrade;
  const evId = SA.state.eventId || 'none';
  const [samples, evals, batch] = await Promise.all([SA.api.listSamples(SA.state.eventId), SA.api.listEvaluation(SA.state.eventId), SA.api.getBatch(evId)]);

  root.appendChild(SA.ui.pageHead('S7 封存、S8 評等', '抽查、封存、評等', SA.ui.notConnected()));
  root.appendChild(h('p', { class: 'lead' }, '丙、乙等以全部現勘為樣本；甲等使用現行法定的 20% 抽查樣本，不另增加現勘。所有比例一律看 95% 單側信賴下界，未達即降等。'));

  // ---------- 20% 抽查 ----------
  const T = CFG.grade.lossThreshold;
  const judged = (s) => {
    if (!SA.ui.isNum(s.fieldLoss)) return null;
    if (s.grade === 'A_MET') return s.fieldLoss >= T;
    if (s.grade === 'A_NOT_MET') return s.fieldLoss < T;
    return null;
  };
  root.appendChild(card('甲等類別 20% 抽查', h('div', null,
    h('p', { class: 'muted' }, 'A 達標與 A 未達標各抽查 20%：A 達標判錯是溢領，A 未達標判錯是該給的沒給。抽查結果同時作為 S8 評等樣本。縣市抽查另由救助系統隨機抽選。'),
    table([
      { label: '申請案號', render: (s) => h('a', { href: '#/case/' + encodeURIComponent(s.caseId) }, val(s.caseNo)) },
      { label: '類別', render: (s) => val(s.category) },
      { label: '系統分級', render: (s) => gradeChip(s.grade) },
      { label: '現勘損失率', cls: 'num', render: (s) => SA.ui.pp(s.fieldLoss) },
      { label: '判定', render: (s) => { const j = s.correct ?? judged(s); return j === true ? '判對' : j === false ? h('span', { class: 'bad' }, '判錯') : '待回填'; } }
    ], samples || [], { emptyText: '尚無抽查案件（資料接口未接入）' }))));

  // ---------- S7 封存 ----------
  const b = batch || {};
  const sealBox = h('div');
  function drawSeal() {
    sealBox.innerHTML = '';
    sealBox.appendChild(kv([['批次', b.batchId], ['存證報告數', num(b.reportCount)], ['Merkle 根', b.merkleRoot], ['狀態', b.sealed ? '已封存 ' + SA.ui.datetime(b.sealedAt) : '未封存']]));
    sealBox.appendChild(h('p', { class: 'muted small' }, '同一批報告的雜湊組成 Merkle 樹，根雜湊交公所留存；事後抽換、刪除或補入任何一份，根雜湊即不符。縣府抽查時比對同批報告與公所留存的根。'));
    sealBox.appendChild(h('button', { class: 'btn btn-primary', disabled: b.sealed ? true : null, onclick: async () => {
      const ok = await SA.ui.confirmDialog('封存本批存證報告', '封存後不得增刪報告。確定要封存？', '封存', { danger: true });
      if (!ok) return;
      await SA.api.sealBatch(evId);
      Object.assign(b, { sealed: true, sealedAt: new Date().toISOString() });
      SA.ui.queuedToast('封存'); SA.refreshNav(); drawSeal();
    } }, b.sealed ? '已封存' : '封存本批'));
  }
  drawSeal();

  // ---------- S8 評等 ----------
  const rows = (evals || []).map((c) => Object.assign({ cat: c }, SA.rules.evaluate(c)));
  const lbCell = (v, min) => (SA.ui.isNum(v) ? h('span', { class: v >= min ? 'good' : 'bad' }, pct(v)) : '—');
  const evalCard = card('S8 逐類別評等：決定下一場的等級', h('div', null,
    table([
      { label: '類別', render: (x) => val(x.cat.crop) + ' × ' + val(x.cat.hazard) },
      { label: '本場', render: (x) => levelChip(x.cat.level) },
      { label: 'A 達標精確度下界', cls: 'num', render: (x) => lbCell(x.aMetLB, U.aMetLB) },
      { label: 'A 未達標精確度下界', cls: 'num', render: (x) => lbCell(x.aNotMetLB, U.aNotMetLB) },
      { label: '判定正確率下界', cls: 'num', render: (x) => lbCell(x.accuracyLB, U.accuracyLB) },
      { label: '直接判定率', cls: 'num', render: (x) => lbCell(x.directRate, U.directRate) },
      { label: 'B 邊緣確認率下界', cls: 'num', render: (x) => lbCell(x.bConfirmLB, U.bConfirmLB) },
      { label: '連續場次', cls: 'num', render: (x) => String(x.streak) },
      { label: '下一場', render: (x) => levelChip(x.next) },
      { label: '說明', render: (x) => x.why }
    ], rows, { emptyText: '尚無評等資料（資料接口未接入）' }),
    h('p', { class: 'muted small' }, '同一類別、同一模型版本的抽查結果跨場合併計算；模型改版後舊樣本不併入。降等只會讓更多案件到場，不會產生錯誤的免勘或駁回。')));

  root.appendChild(h('div', { class: 'grid-1-2' }, card('S7 批次封存', sealBox), evalCard));

  // ---------- 下界試算 ----------
  const nIn = h('input', { type: 'number', min: '1', value: '59', 'aria-label': '件數' });
  const eIn = h('input', { type: 'number', min: '0', value: '0', 'aria-label': '判錯件數' });
  const out = h('p', { class: 'calc-out', 'aria-live': 'polite' });
  function calc() {
    const n = parseInt(nIn.value, 10), e = parseInt(eIn.value, 10);
    if (!(n > 0) || !(e >= 0) || e > n) { out.textContent = '請輸入有效的件數'; return; }
    const lb = SA.rules.lowerBound(n - e, n);
    out.innerHTML = '';
    out.appendChild(document.createTextNode('觀察值 ' + pct((n - e) / n) + '，95% 單側下界 '));
    out.appendChild(h('strong', { class: lb >= 0.95 ? 'good' : 'bad' }, pct(lb)));
    out.appendChild(document.createTextNode(lb >= 0.95 ? '，達 95%' : '，未達 95%'));
  }
  nIn.addEventListener('input', calc); eIn.addEventListener('input', calc); calc();

  const targets = [0.8, 0.9, 0.95, 0.98, 0.99], errs = [0, 1, 3, 10];
  const reqTable = table(
    [{ label: '要證明的比例', render: (t) => pct(t, 0) }].concat(errs.map((e) => ({ label: e + ' 件判錯', cls: 'num', render: (t) => num(SA.rules.requiredN(t, e)) }))),
    targets);

  root.appendChild(h('div', { class: 'grid-2' },
    card('下界試算（Clopper–Pearson）', h('div', null,
      h('div', { class: 'two' }, h('label', { class: 'field' }, '樣本件數', nIn), h('label', { class: 'field' }, '判錯件數', eIn)),
      out,
      h('p', { class: 'muted small' }, '樣本少時觀察值會高估：抽查 20 件全對，觀察值 100%，下界只有 86%。'))),
    card('以 95% 信心證明比例達標所需的件數', h('div', null, reqTable,
      h('p', { class: 'muted small' }, '甲等抽查 20% 時，某類別要有 295 筆以上 A 級才能在一場災害內驗證 95%；件數不足時跨場合併或提高抽查比例。')))));

  // ---------- 升等條件 ----------
  root.appendChild(card('系統升等條件', table([
    { label: '條件', key: 'k' }, { label: '丙 → 乙', key: 'a' }, { label: '乙 → 甲', key: 'b' }
  ], [
    { k: 'A 達標精確度（下界）', a: '≥ 95%', b: '≥ 95%' },
    { k: 'A 未達標精確度（下界）', a: '≥ 95%', b: '≥ 95%' },
    { k: '判定正確率（下界）', a: '≥ 90%', b: '≥ 90%' },
    { k: '直接判定率', a: '≥ 50%', b: '依丙等實測的 B 級比例訂定，不低於 50%' },
    { k: 'B 邊緣確認率（下界）', a: '≥ 80%', b: '≥ 80%' },
    { k: '連續達標的災害場次', a: '—', b: '≥ 10 場' },
    { k: '政府審核', a: '—', b: '通過，列入種植客觀證明或作業要點，並含 A 未達標通知的依據' }
  ])));
};
