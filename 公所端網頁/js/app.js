/* 天相星 公所端：版面與路由 */
window.SA = window.SA || {};
SA.pages = SA.pages || {};
SA.state = { eventId: null, events: [], session: null };

(function () {
  const { h } = SA.ui;

  const NAV = [
    { group: '平時', items: [{ route: 'baseline', label: '災前基準確認' }] },
    { group: '災後', items: [
      { route: 'overview', label: '總覽' },
      { route: 'intake', label: '受理與文件核對' },
      { route: 'list', label: '分級清單' },
      { route: 'case', label: '案件審核' },
      { route: 'followup', label: '補件與無人機' },
      { route: 'audit', label: '抽查、封存、評等' },
      { route: 'report', label: '層報與復查' }
    ] },
    { group: '現場', items: [{ href: 'field.html', label: '現勘（公務手機）' }] }
  ];

  function parseHash() {
    const raw = (location.hash || '#/overview').replace(/^#\/?/, '');
    const [path, qs] = raw.split('?');
    const parts = path.split('/').filter(Boolean);
    const params = {};
    (qs || '').split('&').filter(Boolean).forEach((p) => { const [k, v] = p.split('='); params[decodeURIComponent(k)] = decodeURIComponent(v || ''); });
    return { route: parts[0] || 'overview', id: parts[1] ? decodeURIComponent(parts[1]) : null, params };
  }

  function renderNav(active) {
    const nav = document.getElementById('nav');
    nav.innerHTML = '';
    NAV.forEach((g) => {
      nav.appendChild(h('p', { class: 'nav-group' }, g.group));
      g.items.forEach((it) => {
        const href = it.href || '#/' + it.route;
        const on = it.route && (active === it.route);
        nav.appendChild(h('a', { class: 'nav-item' + (on ? ' on' : ''), href, 'aria-current': on ? 'page' : null }, it.label));
      });
    });
    const n = SA.api.outbox().length;
    nav.appendChild(h('div', { class: 'nav-foot' },
      h('p', null, '本機暫存區 ', h('strong', null, String(n)), ' 筆'),
      h('button', { class: 'linklike', onclick: showOutbox }, '查看')));
  }

  function showOutbox() {
    const box = SA.api.outbox();
    const body = box.length
      ? h('ol', { class: 'outbox' }, box.slice().reverse().map((b) => h('li', null, h('strong', null, b.type), ' ', SA.ui.datetime(b.at), h('code', null, JSON.stringify(b.payload).slice(0, 160)))))
      : h('p', null, '目前沒有暫存的操作。');
    SA.ui.confirmDialog('本機暫存區', h('div', null, h('p', { class: 'muted' }, '資料接口接上之前，所有送出的操作都先存在這台電腦。'), body), '清空暫存區', { danger: true })
      .then((ok) => { if (ok) { SA.api.clearOutbox(); renderNav(parseHash().route); SA.ui.toast('已清空本機暫存區'); } });
  }

  async function renderTop() {
    const top = document.getElementById('top-right');
    top.innerHTML = '';
    const s = SA.state.session;
    const sel = h('select', { id: 'event-select', 'aria-label': '災害事件', onchange: (e) => { SA.state.eventId = e.target.value || null; route(); } },
      SA.state.events.length
        ? SA.state.events.map((ev) => h('option', { value: ev.id, selected: ev.id === SA.state.eventId ? true : null }, ev.name))
        : h('option', { value: '' }, '尚無災害事件'));
    top.appendChild(h('label', { class: 'event-pick' }, h('span', null, '資料'),
      h('select', { 'aria-label': '資料來源', onchange: (e) => { SA.api.setMode(e.target.value); SA.state.trialAnnounce = null; boot(true); } },
        h('option', { value: 'test', selected: SA.api.mode() === 'test' ? true : null }, '測試資料庫'),
        h('option', { value: 'blank', selected: SA.api.mode() === 'blank' ? true : null }, '留白（未接入）'))));
    top.appendChild(h('label', { class: 'event-pick' }, h('span', null, '災害事件'), sel));
    top.appendChild(h('span', { class: 'who' }, (s && s.office) || '[公所名稱]', '　', (s && s.unit) || '農業課'));
    top.appendChild(h('span', { class: 'who-pill' }, ((s && s.role) || '承辦') + ' ' + ((s && s.officer) || '[姓名]')));
  }

  async function route() {
    const r = parseHash();
    renderNav(r.route);
    const main = document.getElementById('main');
    main.innerHTML = '';
    main.setAttribute('aria-busy', 'true');
    const page = SA.pages[r.route];
    try {
      if (!page) main.appendChild(SA.ui.empty('找不到這個畫面。', h('a', { href: '#/overview', class: 'btn' }, '回總覽')));
      else await page(main, r);
    } catch (e) {
      console.error(e);
      main.appendChild(SA.ui.empty('畫面載入失敗：' + e.message));
    }
    main.removeAttribute('aria-busy');
    main.focus({ preventScroll: true });
    window.scrollTo(0, 0);
  }
  SA.route = route;
  SA.refreshNav = () => renderNav(parseHash().route);

  async function boot(again) {
    const [session, events] = await Promise.all([SA.api.getSession(), SA.api.listEvents()]);
    SA.state.session = session;
    SA.state.events = events || [];
    SA.state.eventId = SA.state.events[0] ? SA.state.events[0].id : null;
    await renderTop();
    if (!again) window.addEventListener('hashchange', route);
    route();
  }
  document.addEventListener('DOMContentLoaded', () => boot(false));

  SA.currentEvent = () => SA.state.events.find((e) => e.id === SA.state.eventId) || null;
})();
