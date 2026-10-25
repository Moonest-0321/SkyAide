/* 現勘公務手機：離線路線、受害率、照片與 GNSS 座標，恢復連線後回傳（表 21、三、4(11)、圖 42） */
(function () {
  const { h, val } = SA.ui;
  const ROUTE_KEY = 'skyaide.field.route';
  const QUEUE_KEY = 'skyaide.field.queue';
  const KIND = { B: 'B 邊緣', sample: '抽查', appeal: 'A 級異議', C: 'C 缺失' };

  const read = (k, f) => { try { const s = localStorage.getItem(k); return s ? JSON.parse(s) : f; } catch (e) { return f; } };
  const write = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); return true; } catch (e) { return false; } };

  const main = document.getElementById('field');
  let view = { name: 'route', item: null };

  function net() {
    const el = document.getElementById('net');
    const on = navigator.onLine;
    el.textContent = on ? '連線中' : '離線作業';
    el.className = 'net ' + (on ? 'on' : 'off');
  }

  async function syncQueue(manual) {
    const q = read(QUEUE_KEY, []);
    const pending = q.filter((r) => !r.uploaded);
    if (!pending.length) { if (manual) SA.ui.toast('沒有待回傳的紀錄'); return; }
    if (!navigator.onLine) { if (manual) SA.ui.toast('目前離線，恢復連線後自動回傳', 'warn'); return; }
    const res = await SA.api.uploadFieldRecords(pending);
    if (res && res.ok) { q.forEach((r) => { r.uploaded = true; }); write(QUEUE_KEY, q); SA.ui.toast('已回傳 ' + pending.length + ' 筆'); }
    else if (manual) SA.ui.toast('回傳失敗：' + ((res && res.reason) || '未知原因') + '，紀錄保留在手機', 'warn');
    render();
  }

  function routeView() {
    const route = read(ROUTE_KEY, null);
    const items = ((route && route.items) || []).slice().sort((a, b) => SA.rules.fieldOrder(a) - SA.rules.fieldOrder(b));
    const q = read(QUEUE_KEY, []);
    const pending = q.filter((r) => !r.uploaded).length;
    main.appendChild(h('section', { class: 'f-status' },
      h('p', null, '清單下載：', route ? SA.ui.datetime(route.at) : '尚未下載'),
      h('p', null, '待回傳：', h('strong', null, String(pending)), ' 筆'),
      h('div', { class: 'f-actions' },
        h('button', { class: 'btn btn-block', onclick: download }, '下載今日清單'),
        h('button', { class: 'btn btn-block', onclick: () => syncQueue(true) }, '立即回傳'))));
    main.appendChild(h('h1', { class: 'f-h' }, '今日路線'));
    main.appendChild(h('p', { class: 'muted small f-pad' }, '依 B 邊緣、抽查、A 級異議、C 缺失排序。災前與災後第一時間先下載，離線照常作業。'));
    if (!items.length) main.appendChild(SA.ui.empty('清單是空的（資料接口未接入）。可先下載清單，或手動新增紀錄。'));
    else main.appendChild(h('ol', { class: 'f-list' }, items.map((it, i) => {
      const done = q.some((r) => r.caseId === it.caseId);
      return h('li', null, h('button', { class: 'f-item' + (done ? ' done' : ''), onclick: () => { view = { name: 'record', item: it }; render(); } },
        h('span', { class: 'f-n' }, String(i + 1)),
        h('span', { class: 'f-body' }, h('strong', null, val(it.caseNo), '　', val(it.landNo)), h('small', null, (KIND[it.kind] || it.kind || '—') + '・' + val(it.confirm))),
        h('span', { class: 'f-go', 'aria-hidden': 'true' }, done ? '已記錄' : '›')));
    })));
    main.appendChild(h('div', { class: 'f-pad' }, h('button', { class: 'btn btn-primary btn-block', onclick: () => { view = { name: 'record', item: null }; render(); } }, '手動新增現勘紀錄')));
    if (q.length) {
      main.appendChild(h('h2', { class: 'f-h' }, '本機紀錄'));
      main.appendChild(h('ul', { class: 'f-rec' }, q.slice().reverse().map((r) => h('li', null,
        h('strong', null, val(r.caseNo)), '　受害率 ', val(r.rate !== null ? r.rate + '%' : null), '　', SA.ui.datetime(r.at), '　', h('span', { class: r.uploaded ? 'good' : 'muted' }, r.uploaded ? '已回傳' : '待回傳')))));
    }
  }

  async function download() {
    const list = await SA.api.downloadRoute(null);
    if (list && list.length) { write(ROUTE_KEY, { at: new Date().toISOString(), items: list }); SA.ui.toast('已下載 ' + list.length + ' 筆'); }
    else {
      const local = read(ROUTE_KEY, null);
      SA.ui.toast(local ? '資料接口未接入，沿用工作台離線下載的清單' : '資料接口未接入，沒有可下載的清單', 'warn');
    }
    render();
  }

  function shrink(file) {
    return new Promise((resolve) => {
      const img = new Image();
      const url = URL.createObjectURL(file);
      img.onload = () => {
        const s = Math.min(1, 1024 / Math.max(img.width, img.height));
        const c = document.createElement('canvas');
        c.width = Math.round(img.width * s); c.height = Math.round(img.height * s);
        c.getContext('2d').drawImage(img, 0, 0, c.width, c.height);
        URL.revokeObjectURL(url);
        resolve({ name: file.name, size: file.size, lastModified: file.lastModified, data: c.toDataURL('image/jpeg', 0.7) });
      };
      img.onerror = () => { URL.revokeObjectURL(url); resolve({ name: file.name, size: file.size, lastModified: file.lastModified, data: null }); };
      img.src = url;
    });
  }

  function recordView() {
    const it = view.item || {};
    const rec = { caseId: it.caseId || null, caseNo: it.caseNo || '', gnss: null, photos: { far: null, near: null } };
    main.appendChild(h('div', { class: 'f-pad' }, h('button', { class: 'linklike', onclick: () => { view = { name: 'route' }; render(); } }, '← 今日路線')));
    main.appendChild(h('h1', { class: 'f-h' }, '現勘紀錄'));
    const caseNo = h('input', { type: 'text', value: rec.caseNo, placeholder: '申請案號', 'aria-label': '申請案號' });
    const rate = h('input', { type: 'number', min: '0', max: '100', inputmode: 'numeric', 'aria-label': '受害率' });
    const gnssOut = h('p', { class: 'muted small' }, '尚未定位');
    const photoRow = (key, label) => {
      const prev = h('div', { class: 'f-thumb' }, '未拍攝');
      const inp = h('input', { type: 'file', accept: 'image/*', capture: 'environment', 'aria-label': label, onchange: async (e) => {
        const f = e.target.files[0]; if (!f) return;
        prev.textContent = '處理中…';
        rec.photos[key] = await shrink(f);
        prev.innerHTML = '';
        if (rec.photos[key].data) prev.appendChild(h('img', { src: rec.photos[key].data, alt: label }));
        else prev.textContent = f.name;
      } });
      return h('label', { class: 'f-photo' }, h('span', null, label), inp, prev);
    };
    const note = h('textarea', { rows: '3', placeholder: '現場說明', 'aria-label': '現場說明' });
    const warn = h('p', { class: 'warn', role: 'alert' });

    function locate() {
      if (!navigator.geolocation) { gnssOut.textContent = '這台裝置不支援定位'; return; }
      gnssOut.textContent = '定位中…';
      navigator.geolocation.getCurrentPosition((p) => {
        rec.gnss = { lat: p.coords.latitude, lon: p.coords.longitude, accuracy: p.coords.accuracy, at: new Date(p.timestamp).toISOString() };
        gnssOut.textContent = rec.gnss.lat.toFixed(6) + ', ' + rec.gnss.lon.toFixed(6) + '（誤差約 ' + Math.round(rec.gnss.accuracy) + ' 公尺）';
        if (it.center && SA.ui.isNum(it.center.lat)) {
          const d = SA.rules.haversine(rec.gnss, it.center);
          gnssOut.textContent += '，距坵塊中心 ' + Math.round(d) + ' 公尺';
        }
      }, (e) => { gnssOut.textContent = '定位失敗：' + e.message; }, { enableHighAccuracy: true, timeout: 20000 });
    }

    function save() {
      warn.textContent = '';
      const r = rate.value === '' ? null : Number(rate.value);
      if (!caseNo.value.trim()) { warn.textContent = '請填申請案號'; return; }
      if (r === null || isNaN(r) || r < 0 || r > 100) { warn.textContent = '受害率須介於 0–100%'; return; }
      if (!rec.photos.far || !rec.photos.near) { warn.textContent = '影像存證需遠拍與近拍各一張'; return; }
      if (!rec.gnss) { warn.textContent = '請先取得 GNSS 座標'; return; }
      const q = read(QUEUE_KEY, []);
      q.push({ caseId: rec.caseId, caseNo: caseNo.value.trim(), kind: it.kind || null, rate: r, photos: rec.photos, gnss: rec.gnss, note: note.value.trim(), at: new Date().toISOString(), uploaded: false });
      if (!write(QUEUE_KEY, q)) {
        q[q.length - 1].photos = { far: { name: rec.photos.far.name }, near: { name: rec.photos.near.name } };
        if (!write(QUEUE_KEY, q)) { warn.textContent = '手機儲存空間不足，無法保存'; return; }
        SA.ui.toast('儲存空間不足，照片只保留檔名；請保留手機原檔', 'warn');
      } else SA.ui.toast('已保存在手機，恢復連線後自動回傳');
      view = { name: 'route' }; render();
      syncQueue(false);
    }

    main.appendChild(h('div', { class: 'f-form' },
      it.kind ? h('p', { class: 'f-kind' }, KIND[it.kind] || it.kind, '・要確認：', val(it.confirm)) : null,
      h('label', { class: 'field' }, '申請案號', caseNo),
      h('label', { class: 'field' }, '受害率（%）', rate),
      h('div', { class: 'f-photos' }, photoRow('far', '遠拍'), photoRow('near', '近拍')),
      h('p', { class: 'muted small' }, '影像存證：遠拍與近拍各一張，可辨識日期與地段地號。'),
      h('div', { class: 'field' }, h('span', null, 'GNSS 座標'), h('button', { class: 'btn', type: 'button', onclick: locate }, '取得目前位置'), gnssOut),
      h('label', { class: 'field' }, '說明', note),
      warn,
      h('button', { class: 'btn btn-go btn-block', onclick: save }, '保存紀錄')));
  }

  function render() {
    main.innerHTML = '';
    if (!SA.api.CONNECTED) main.appendChild(h('p', { class: 'nc f-pad' }, h('span', { class: 'dot' }), '資料接口未接入：紀錄先保存在手機'));
    if (view.name === 'record') recordView(); else routeView();
    main.focus({ preventScroll: true });
  }

  window.addEventListener('online', () => { net(); syncQueue(false); });
  window.addEventListener('offline', net);
  document.addEventListener('DOMContentLoaded', () => { net(); render(); });
})();
