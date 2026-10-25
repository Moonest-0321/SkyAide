/* 受理與文件核對：掃描 QR 碼或以地號、身分證查詢；應附文件狀態；查驗存證報告（表 24 D、三、4(8)） */
SA.pages.intake = async function (root) {
  const { h, val, card, kv } = SA.ui;
  const CFG = SA.config;
  const ev = SA.currentEvent();
  const dl = SA.rules.deadlines(SA.state.trialAnnounce || (ev && ev.announceDate));

  root.appendChild(SA.ui.pageHead('申請期', '受理與文件核對', SA.ui.notConnected()));
  if (dl) {
    const late = new Date() > dl.applyEnd;
    root.appendChild(h('p', { class: late ? 'banner warn' : 'banner' }, late ? '申請期已於 ' + SA.ui.date(dl.applyEnd, true) + ' 截止，逾期不受理。' : '申請截止：' + SA.ui.date(dl.applyEnd, true) + '（公告翌日起 10 個工作日）'));
  }

  const result = h('div');
  const q = h('input', { type: 'search', id: 'q', placeholder: '申請案號、查驗碼、地號或身分證字號', 'aria-label': '查詢', onkeydown: (e) => { if (e.key === 'Enter') find(q.value); } });
  const camBox = h('div', { class: 'cam' });

  async function find(text) {
    text = (text || '').trim();
    result.innerHTML = '';
    if (!text) { SA.ui.toast('請輸入或掃描查詢內容', 'warn'); return; }
    const app = await SA.api.findApplication(text);
    renderApp(app, text);
  }

  async function scan() {
    camBox.innerHTML = '';
    if (!('BarcodeDetector' in window) || !navigator.mediaDevices) {
      camBox.appendChild(h('p', { class: 'muted' }, '這台裝置的瀏覽器不支援掃描，請手動輸入 QR 碼下方的案號或查驗碼。'));
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } });
      const video = h('video', { autoplay: true, playsinline: true, muted: true, 'aria-label': '相機畫面' });
      video.srcObject = stream;
      const stop = () => stream.getTracks().forEach((t) => t.stop());
      camBox.appendChild(video);
      camBox.appendChild(h('button', { class: 'btn btn-sm', onclick: () => { stop(); camBox.innerHTML = ''; } }, '關閉相機'));
      const det = new BarcodeDetector({ formats: ['qr_code'] });
      const tick = async () => {
        if (!video.isConnected) { stop(); return; }
        try { const codes = await det.detect(video); if (codes.length) { stop(); camBox.innerHTML = ''; q.value = codes[0].rawValue; find(codes[0].rawValue); return; } } catch (e) { /* 繼續 */ }
        requestAnimationFrame(tick);
      };
      video.addEventListener('playing', tick, { once: true });
    } catch (e) {
      camBox.appendChild(h('p', { class: 'muted' }, '無法開啟相機：' + e.message));
    }
  }

  async function renderApp(app, text) {
    const a = Object.assign({}, app || {});
    const local = a.id ? await SA.api.getLocalApplication(a.id) : null; // 農民端送件的資料（同一台電腦測試時）
    if (local) { a.declaredRate = local.declaredRate; a.submitBy = local.by; }
    const autoA = a.level === '甲' && (a.grade === 'A_MET' || a.grade === 'A_NOT_MET'); // 甲等 A 級由系統自動申報
    if (autoA) { a.submitBy = '系統依存證報告自動申報'; a.declaredRate = a.interval && SA.ui.isNum(a.interval.p50) ? a.interval.p50 : null; }
    const level = a.level || null;
    const docs = a.docs || [];
    const docOf = (k) => docs.find((d) => d.key === k) || {};
    const state = {};
    const rows = CFG.requiredDocs.map((d) => {
      const cur = docOf(d.key);
      const sel = h('select', { 'aria-label': d.label, onchange: (e) => { state[d.key] = e.target.value; } },
        ['', '已附', '未附'].concat(d.canWaive || d.optional ? ['免附'] : []).map((s) => h('option', { value: s, selected: cur.status === s ? true : null }, s || '—')));
      state[d.key] = cur.status || '';
      return h('li', { class: 'docrow' }, h('div', null, h('strong', null, d.label), h('p', { class: 'muted small' }, '依據：', val(cur.basis))), sel);
    });

    const verifyBox = h('div');
    async function verify() {
      verifyBox.innerHTML = '';
      const code = (a.report && a.report.verifyCode) || text;
      const v = await SA.api.verifyReport(code);
      const s = (x) => (x === true ? '相符' : x === false ? h('span', { class: 'bad' }, '不符') : null);
      verifyBox.appendChild(kv([['簽章', s(v && v.signature)], ['時戳', v && v.timestamp], ['封存批次', s(v && v.batch)]]));
      verifyBox.appendChild(h('p', { class: 'muted small' }, '查驗只用公開金鑰，不必連線至天相星。查驗碼含報告編號與雜湊前 16 碼。'));
    }

    result.appendChild(h('div', { class: 'grid-2' },
      card('預填申請資料', h('div', null,
        !app ? h('p', { class: 'banner' }, '查無「' + text + '」的資料（資料接口未接入）。以下為受理畫面範本。') : null,
        autoA ? h('p', { class: 'banner' }, '甲等 A 級：系統已依存證報告自動申報，申請人不必填受災率。農民或公所提出異議時改排到場。') : null,
        kv([['申請案號', a.caseNo], ['申請人', a.applicant], ['送件方式', a.submitBy], ['耕地標示（來自謄本）', a.landNo], ['作物', a.crop], ['作物面積（來自災前基準）', a.areaHa ? a.areaHa + ' 公頃' : null], [autoA ? '受災率（存證報告中間值）' : '申報受災率', SA.ui.isNum(a.declaredRate) ? a.declaredRate + '%' : null], ['存證報告估計區間（參考）', SA.ui.intervalText(a.interval)]]),
        h('p', { class: 'muted small' }, '受災率由農民申報，存證報告區間僅供參考；帳號由申請人自填，系統不保存。'))),
      card('存證報告', h('div', null,
        kv([['報告編號', a.report && a.report.no], ['查驗碼', a.report && a.report.verifyCode]]),
        h('p', { class: 'stamp' + (level === '甲' ? ' ok' : '') }, level === '甲' ? CFG.reportLabel.approved : CFG.reportLabel.reference),
        h('button', { class: 'btn', onclick: verify }, '查驗簽章、時戳與封存批次'),
        verifyBox))));

    result.appendChild(card('應附文件', h('div', null,
      h('ul', { class: 'docs' }, rows),
      h('div', { class: 'actions' },
        h('button', { class: 'btn', onclick: async () => {
          const missing = CFG.requiredDocs.filter((d) => state[d.key] === '未附').map((d) => d.label.replace(/（.*/, ''));
          if (!missing.length) { SA.ui.toast('沒有標為「未附」的文件', 'warn'); return; }
          await SA.api.sendNotice([a.id || text], 'supplement', { docs: missing }); SA.ui.queuedToast('補件通知'); SA.refreshNav();
        } }, '通知補件'),
        h('button', { class: 'btn btn-primary', onclick: async () => {
          if (dl && new Date() > dl.applyEnd) { SA.ui.toast('申請期已截止，逾期不受理', 'warn'); return; }
          const need = CFG.requiredDocs.filter((d) => !d.optional && !(d.canWaive && state[d.key] === '免附') && state[d.key] !== '已附');
          if (need.length) { SA.ui.toast('尚有必附文件未確認：' + need.map((d) => d.label.replace(/（.*/, '')).join('、'), 'warn'); return; }
          await SA.api.acceptApplication(a.id || text, state); SA.ui.queuedToast('受理'); SA.refreshNav();
        } }, '受理')))));
  }

  root.appendChild(card('調閱申請', h('div', null,
    h('div', { class: 'searchrow' }, q, h('button', { class: 'btn btn-primary', onclick: () => find(q.value) }, '查詢'), h('button', { class: 'btn', onclick: scan }, '掃描 QR 碼')),
    camBox,
    h('p', { class: 'muted small' }, '農民確認預填資料並勾選屬實後產生送件 QR 碼，可由本人、農會或受託人送件。公所查得到地政資料時，土地證明可免附。'))));
  root.appendChild(result);
};
