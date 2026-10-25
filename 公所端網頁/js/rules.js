/*
 * 天相星 公所端：判定規則（純函式，不碰畫面）
 * 接上真實資料後，畫面上的分級、處理方式、期限、下界都由這裡算出。
 */
window.SA = window.SA || {};

SA.rules = (function () {
  const C = () => SA.config;
  const isNum = (v) => typeof v === 'number' && isFinite(v);

  // ---------- 可信度（表 39）：五項全過高；生產事實未過或兩項以上未過低；一項未過中 ----------
  function credibility(checks) {
    if (!checks) return null;
    const keys = C().checks.map((c) => c.key);
    const vals = keys.map((k) => checks[k] && checks[k].pass);
    if (vals.some((v) => v === null || v === undefined)) return null;
    const failed = keys.filter((k, i) => vals[i] === false);
    if (failed.length === 0) return '高';
    if (failed.includes('production') || failed.length >= 2) return '低';
    return '中';
  }

  function reasonCodes(checks) {
    if (!checks) return [];
    const out = [];
    C().checks.forEach((c) => {
      const r = checks[c.key];
      if (r && r.pass === false) (r.reasons && r.reasons.length ? r.reasons : [c.label + '未過']).forEach((x) => out.push(x));
    });
    return out;
  }

  // ---------- 分級（表 17）：先看證據、再看損失 ----------
  function thresholds(crop) {
    const g = C().grade;
    return Object.assign({ aMetLowerMin: g.aMetLowerMin, aNotMetUpperMax: g.aNotMetUpperMax }, (crop && g.perCrop[crop]) || {});
  }

  function grade(c) {
    if (!c) return null;
    const cred = credibility(c.checks);
    if (cred === null) return null;
    if (cred !== '高') return 'C';
    if (c.componentBelowThreshold) return c.componentFallback === 'C' ? 'C' : 'B'; // 判讀元件未達使用門檻，歸 B 或 C
    const iv = c.interval || {};
    if (!isNum(iv.p10) || !isNum(iv.p90)) return null;
    const t = thresholds(c.crop);
    if (iv.p10 >= t.aMetLowerMin) return 'A_MET';
    if (iv.p90 <= t.aNotMetUpperMax) return 'A_NOT_MET';
    return 'B';
  }

  // ---------- C 缺失：先補件，期限過了再看是不是影像類 ----------
  function isImagery(reasons) {
    const map = C().reasonRoute;
    return !!(reasons && reasons.length) && reasons.every((r) => map[r] && map[r].imagery);
  }
  // supplementState: 'pending' | 'received' | 'expired'
  // 回傳 'supplement'（補件中）| 'recheck'（已補件，重新檢核）| 'drone'（無人機候選）| 'visit'（到場候選）
  function routeOf(reasons, supplementState) {
    if (supplementState === 'received') return 'recheck';
    if (supplementState !== 'expired') return 'supplement';
    return isImagery(reasons) ? 'drone' : 'visit';
  }

  /*
   * ---------- 依公所量能分配（到場與無人機） ----------
   * 無人機：影像類、補件期限已過者，依優先度取前 droneCases 件；其餘轉到場。
   * 到場：依 B 邊緣、抽查、申訴、C 缺失的順序，每類內依優先度，取前（人日 × 每人日筆數）件；其餘排隊。
   */
  function allocate(items, cap) {
    const c = Object.assign({}, C().capacity, cap || {});
    const byPri = (a, b) => priority(b) - priority(a);
    const droneCand = items.filter((x) => x.kind === 'C' && x._route === 'drone').sort(byPri);
    const nDrone = Math.max(0, Math.floor(c.droneCases || 0));
    const drone = droneCand.slice(0, nDrone);
    const overflow = droneCand.slice(nDrone);
    const visitKinds = ['B', 'sample', 'appeal', 'C', 'current']; // 乙、丙等類別依現行規定勘查者排在最後，可依分級排序
    const visitCand = [];
    visitKinds.forEach((k) => {
      const list = items.filter((x) => x.kind === k && (k !== 'C' || x._route === 'visit')).concat(k === 'C' ? overflow : []).sort(byPri);
      list.forEach((x) => visitCand.push(x));
    });
    const nVisit = Math.max(0, Math.floor((c.personDays || 0) * (c.perPersonDay || 0)));
    return {
      drone, overflow,
      visit: visitCand.slice(0, nVisit),
      over: visitCand.slice(nVisit),
      visitCapacity: nVisit, droneCapacity: nDrone
    };
  }

  // ---------- 無人機航線：起飛點出發，最近鄰排序，估飛行時間 ----------
  /*
   * 把案件轉成「需要人或無人機處理」的工作項目
   * 甲等：B → B；A 抽中 → sample；A 未達標申訴 → appeal；C → C
   * 乙等：C → C（先補件）；其餘 → current（依現行規定勘查）
   * 丙等：全部 → current
   */
  function workItems(cases, suppStates) {
    const out = [];
    (cases || []).forEach((c0) => {
      const c = Object.assign({}, c0);
      c.grade = c.grade || grade(c);
      c.reasons = c.reasons || reasonCodes(c.checks);
      c.supplementState = (suppStates && suppStates[c.id]) || c.supplementState || 'pending';
      if (c.grade === 'C' && c.level !== '丙') { c.kind = 'C'; c._route = routeOf(c.reasons, c.supplementState); out.push(c); return; }
      if (c.level === '甲') {
        if (c.grade === 'B') c.kind = 'B';
        else if ((c.grade === 'A_MET' || c.grade === 'A_NOT_MET') && c.sampled) c.kind = 'sample';
        else if (c.grade === 'A_NOT_MET' && c.appeal) c.kind = 'appeal';
        else return;
      } else if (c.level === '乙' || c.level === '丙') c.kind = 'current';
      else return;
      out.push(c);
    });
    return out;
  }

  function droneRoute(group) {
    const D = C().drone;
    const start = group.takeoff;
    const left = group.members.slice();
    const order = [];
    let cur = start, dist = 0;
    while (left.length) {
      let bi = 0, bd = Infinity;
      left.forEach((m, i) => { const d = haversine(cur, m.center); if (d < bd) { bd = d; bi = i; } });
      dist += bd; cur = left[bi].center; order.push(left.splice(bi, 1)[0]);
    }
    dist += haversine(cur, start);
    const area = order.reduce((s, m) => s + (isNum(m.areaHa) ? m.areaHa : 0), 0);
    const minutes = dist / D.cruiseMps / 60 + area / D.scanHaPerMin;
    return { order, distM: dist, areaHa: area, minutes, batteries: Math.max(1, Math.ceil(minutes / D.batteryMin)) };
  }

  /*
   * ---------- 處理方式（表 17、表 19） ----------
   * 輸入：等級（甲乙丙）、分級、是否被救助系統抽中 20%、原因碼、是否已補件
   * 輸出：{ title, action, methods（可用的判定方式）, notices（可發的通知）, gradeVisible }
   */
  function handling({ level, grade: g, sampled, reasons, supplementState }) {
    const m = C().decisionMethods;
    const base = { gradeVisible: true, notices: [], methods: [], action: '', title: '', tone: 'neutral' };
    if (!level) return Object.assign(base, { title: '類別等級未提供', action: '—', methods: ['survey', 'appPhoto', 'objective'] });

    if (level === '丙') {
      return Object.assign(base, {
        gradeVisible: false,
        title: '丙等收集期：系統結果不交公所使用',
        action: '依現行規定勘查；現勘結果回填，作為訓練與驗證資料',
        methods: ['survey', 'appPhoto', 'objective']
      });
    }

    if (level === '乙') {
      const notices = g === 'C' ? ['supplement'] : []; // 乙等起發 C 級補件提醒（S5）
      return Object.assign(base, {
        title: '乙等考察期：分級與存證報告為參考資料',
        action: '依現行規定勘查，系統結果不作免勘依據；可依分級排定現勘順序' + (g === 'C' ? '。C 缺失先要求補件，期限過後依公所量能處理' : ''),
        methods: ['survey', 'appPhoto', 'objective'],
        notices
      });
    }

    // 甲等
    if (g === 'A_MET') {
      if (sampled) return Object.assign(base, { title: '甲等：A 達標，抽中 20% 抽查', action: '到場抽查；結果回填作為 S8 評等樣本', methods: ['sample'], tone: 'visit' });
      return Object.assign(base, { title: '甲等：A 達標可書面審核', action: '以存證報告書面審核後核定、撥款', methods: ['paper', 'appPhoto', 'objective', 'survey'], tone: 'ok' });
    }
    if (g === 'A_NOT_MET') {
      if (sampled) return Object.assign(base, { title: '甲等：A 未達標，抽中 20% 抽查', action: '到場抽查；結果回填作為 S8 評等樣本', methods: ['sample'], tone: 'visit' });
      return Object.assign(base, {
        title: '甲等：A 未達標，勘查期內通知',
        action: '30 日勘查期內送達通知，附災前災後影像日期與判定理由，給補件期限；申請人補件或申訴時改排到場',
        methods: ['survey', 'appPhoto'], notices: ['notMet'], tone: 'notice'
      });
    }
    if (g === 'B') return Object.assign(base, { title: '甲等：B 邊緣，到場確認', action: '公所到場確認損失率', methods: ['survey', 'appPhoto'], tone: 'visit' });
    if (g === 'C') {
      const r = routeOf(reasons, supplementState);
      const t = {
        supplement: ['甲等：C 缺失，先要求補件', '依原因碼通知申請人補件；補件回來後重新檢核，五項全過即重新分級'],
        recheck: ['甲等：C 缺失，已補件', '補件資料回到 S1 登錄後重新檢核，五項全過即重新分級'],
        drone: ['甲等：C 缺失，補件期限已過（影像類）', '依公所量能處理：有無人機量能時計算航線、提交飛行申請後派飛；超出量能者排入到場'],
        visit: ['甲等：C 缺失，補件期限已過', '依公所量能與優先度排入到場']
      }[r];
      return Object.assign(base, { title: t[0], action: t[1], methods: ['survey', 'appPhoto'], notices: r === 'supplement' ? ['supplement'] : [], tone: 'warn' });
    }
    return Object.assign(base, { title: '甲等：分級未提供', action: '—', methods: ['survey', 'appPhoto'] });
  }

  // ---------- B、C 排序（三、4(6)：依預估救助金額與不確定程度） ----------
  function priority(c) {
    if (!c) return 0;
    const amt = isNum(c.estAmount) ? c.estAmount : 0;
    let u = 0.5;
    const iv = c.interval || {};
    if (c.grade === 'B' && isNum(iv.p10) && isNum(iv.p90)) u = 1; // 損失區間跨過門檻
    if (c.grade === 'A_MET' || c.grade === 'A_NOT_MET') u = 0.4;
    if (c.grade === 'C') u = isImagery(c.reasons) ? 0.2 : 0.6; // 只是解析度不足或雲遮者排後段
    return amt * u;
  }

  // ---------- 期限（表 5、表 64） ----------
  function parseDate(s) {
    if (!s) return null;
    const d = new Date(s + (s.length === 10 ? 'T00:00:00' : ''));
    return isNaN(d) ? null : d;
  }
  function addDays(d, n) { const x = new Date(d); x.setDate(x.getDate() + n); return x; }
  function addWorkdays(d, n) { // 未扣國定假日，以公告為準
    let x = new Date(d), k = 0;
    while (k < n) { x = addDays(x, 1); const w = x.getDay(); if (w !== 0 && w !== 6) k++; }
    return x;
  }
  function deadlines(announceDate) {
    const a = parseDate(announceDate);
    if (!a) return null;
    const D = C().deadlines;
    const applyEnd = addWorkdays(a, D.applyWorkdays);     // 公告翌日起 10 個工作日
    const surveyEnd = addDays(a, D.surveyDays);            // 公告翌日起 30 日
    const reportEnd = addDays(surveyEnd, D.reportDays);
    const countyEnd = addDays(reportEnd, D.countyAuditDays);
    const afaEnd = addDays(countyEnd, D.afaReviewDays);
    return { announce: a, applyEnd, surveyEnd, reportEnd, countyEnd, afaEnd };
  }
  function daysBetween(a, b) { return Math.round((startOfDay(b) - startOfDay(a)) / 86400000); }
  function startOfDay(d) { const x = new Date(d); x.setHours(0, 0, 0, 0); return x; }

  // ---------- 縣市抽查戶數（三、4(13)） ----------
  function countyAuditSize(households) {
    if (!isNum(households) || households <= 0) return null;
    const h = Math.floor(households);
    let n, rule;
    if (h < 100) { n = h <= 10 ? Math.ceil(h / 2) : Math.min(5, h); rule = h <= 10 ? '10 戶以下抽半數' : '未達 100 戶至少 5 戶'; }
    else if (h < 500) { n = Math.ceil(h * 0.05); rule = '100 至未達 500 戶抽 5%'; }
    else if (h < 1500) { n = 25; rule = '500 至未達 1,500 戶至少 25 戶'; }
    else { n = 30; rule = '1,500 戶以上至少 30 戶'; }
    return { households: h, sample: n, rule, passRate: C().countyPassRate, maxRounds: C().countyAuditMaxRounds };
  }

  // ---------- Clopper–Pearson 95% 單側下界 ----------
  function lgamma(z) { // Lanczos
    const g = 7, p = [0.99999999999980993, 676.5203681218851, -1259.1392167224028, 771.32342877765313, -176.61502916214059, 12.507343278686905, -0.13857109526572012, 9.9843695780195716e-6, 1.5056327351493116e-7];
    if (z < 0.5) return Math.log(Math.PI / Math.sin(Math.PI * z)) - lgamma(1 - z);
    z -= 1; let x = p[0];
    for (let i = 1; i < g + 2; i++) x += p[i] / (z + i);
    const t = z + g + 0.5;
    return 0.5 * Math.log(2 * Math.PI) + (z + 0.5) * Math.log(t) - t + Math.log(x);
  }
  function upperTail(n, k, p) { // P(X >= k)
    if (k <= 0) return 1;
    if (p <= 0) return 0; if (p >= 1) return 1;
    const lc = lgamma(n + 1);
    let s = 0;
    for (let i = k; i <= n; i++) s += Math.exp(lc - lgamma(i + 1) - lgamma(n - i + 1) + i * Math.log(p) + (n - i) * Math.log(1 - p));
    return Math.min(1, s);
  }
  function lowerBound(successes, n, conf) {
    conf = conf || C().upgrade.confidence;
    if (!isNum(n) || !isNum(successes) || n <= 0 || successes < 0 || successes > n) return null;
    if (successes === 0) return 0;
    const alpha = 1 - conf;
    if (successes === n) return Math.pow(alpha, 1 / n);
    let lo = 0, hi = successes / n;
    for (let i = 0; i < 80; i++) { const mid = (lo + hi) / 2; if (upperTail(n, successes, mid) < alpha) lo = mid; else hi = mid; }
    return (lo + hi) / 2;
  }
  function requiredN(target, errors, conf) { // 表 69
    if (!isNum(target) || !isNum(errors) || target <= 0 || target >= 1 || errors < 0) return null;
    for (let n = errors + 1; n <= 20000; n++) { const lb = lowerBound(n - errors, n, conf); if (lb !== null && lb >= target) return n; }
    return null;
  }

  // ---------- S8 逐類別評等（表 66、表 67、降等規則） ----------
  function ratio(c, n) { return isNum(c) && isNum(n) && n > 0 ? { k: c, n } : null; }
  function evaluate(cat) {
    // cat.samples: { aMet:{correct,total}, aNotMet:{correct,total}, b:{confirmed,total}, applied, aCount }
    const U = C().upgrade, s = (cat && cat.samples) || {};
    const lb = (o, kk) => (o && isNum(o[kk]) && isNum(o.total) && o.total > 0 ? lowerBound(o[kk], o.total) : null);
    const aMetLB = lb(s.aMet, 'correct');
    const aNotMetLB = lb(s.aNotMet, 'correct');
    const accN = (s.aMet && s.aMet.total || 0) + (s.aNotMet && s.aNotMet.total || 0);
    const accK = (s.aMet && s.aMet.correct || 0) + (s.aNotMet && s.aNotMet.correct || 0);
    const accuracyLB = accN > 0 ? lowerBound(accK, accN) : null;
    const directRate = isNum(s.applied) && s.applied > 0 && isNum(s.aCount) ? s.aCount / s.applied : null;
    const bConfirmLB = lb(s.b, 'confirmed');

    const cur = cat && cat.level;
    const meetsB = [aMetLB, aNotMetLB, accuracyLB, directRate, bConfirmLB].every(isNum) &&
      aMetLB >= U.aMetLB && aNotMetLB >= U.aNotMetLB && accuracyLB >= U.accuracyLB && directRate >= (cat && isNum(cat.directTarget) ? cat.directTarget : U.directRate) && bConfirmLB >= U.bConfirmLB;
    const insufficient = !isNum(aMetLB) || !isNum(aNotMetLB);

    let next = cur || null, streak = isNum(cat && cat.streak) ? cat.streak : 0, why = '';
    if (!cur) { why = '類別等級未提供'; }
    else if (insufficient) { why = '樣本不足：同一類別、同一模型版本的抽查結果跨場合併計算，或提高抽查比例'; }
    else if ((cur === '甲' || cur === '乙') && (aMetLB < U.downgradeLB || aNotMetLB < U.downgradeLB)) {
      next = cur === '甲' ? '乙' : '丙'; streak = 0; why = 'A 精確度下界低於 95%，下一場降一等，連續場次歸零';
    } else if (meetsB) {
      streak += 1;
      if (cur === '丙') { next = '乙'; why = '達乙等條件'; }
      else if (cur === '乙') {
        if (streak >= U.streakForA && cat.govApproved) { next = '甲'; why = '連續 ' + U.streakForA + ' 場達標並通過政府審核'; }
        else { why = '達標；連續 ' + streak + ' 場' + (cat.govApproved ? '' : '，尚未通過政府審核'); }
      } else { why = '維持甲等'; }
    } else { streak = 0; why = '未全數達標，連續場次歸零'; }

    // 類別不得高於整體
    const order = { '丙': 0, '乙': 1, '甲': 2 };
    if (next && cat && cat.overallLevel && order[next] > order[cat.overallLevel]) { next = cat.overallLevel; why += '；類別不得高於整體（' + cat.overallLevel + '等）'; }

    return { aMetLB, aNotMetLB, accuracyLB, directRate, bConfirmLB, streak, next, why };
  }

  // ---------- 無人機分組（表 55：相距 500 公尺內分為一組，共用起飛點） ----------
  function haversine(a, b) {
    const R = 6371000, toR = Math.PI / 180;
    const dLat = (b.lat - a.lat) * toR, dLon = (b.lon - a.lon) * toR;
    const x = Math.sin(dLat / 2) ** 2 + Math.cos(a.lat * toR) * Math.cos(b.lat * toR) * Math.sin(dLon / 2) ** 2;
    return 2 * R * Math.asin(Math.sqrt(x));
  }
  function droneGroups(targets) {
    const R = C().droneGroupRadiusM;
    const pts = (targets || []).filter((t) => t.center && isNum(t.center.lat) && isNum(t.center.lon));
    const left = pts.slice().sort((a, b) => priority(b) - priority(a));
    const groups = [];
    while (left.length) {
      const seed = left.shift();
      const g = [seed];
      for (let i = left.length - 1; i >= 0; i--) if (g.every((m) => haversine(m.center, left[i].center) <= R)) g.push(left.splice(i, 1)[0]);
      const lat = g.reduce((s, m) => s + m.center.lat, 0) / g.length;
      const lon = g.reduce((s, m) => s + m.center.lon, 0) / g.length;
      groups.push({ members: g, takeoff: { lat, lon } });
    }
    return { groups, noLocation: (targets || []).length - pts.length };
  }

  function kml(targets, title) {
    const esc = (s) => String(s == null ? '' : s).replace(/[<>&"]/g, (ch) => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;', '"': '&quot;' }[ch]));
    const marks = (targets || []).map((t) => {
      const ring = t.geometry && t.geometry.type === 'Polygon' && t.geometry.coordinates && t.geometry.coordinates[0];
      if (!ring) return '';
      const coords = ring.map((p) => p[0] + ',' + p[1] + ',0').join(' ');
      return '<Placemark><name>' + esc(t.caseNo || t.id) + '</name><description>' + esc((t.landNo || '') + ' ' + (t.reasons || []).join('、')) + '</description><Polygon><outerBoundaryIs><LinearRing><coordinates>' + coords + '</coordinates></LinearRing></outerBoundaryIs></Polygon></Placemark>';
    }).join('');
    return '<?xml version="1.0" encoding="UTF-8"?>\n<kml xmlns="http://www.opengis.net/kml/2.2"><Document><name>' + esc(title || '天相星 C-無人機') + '</name>' + marks + '</Document></kml>';
  }

  // ---------- 現勘路線排序（圖 42：B 邊緣、抽查、申訴、C 缺失） ----------
  function fieldOrder(item) {
    const k = item && item.kind;
    return { B: 0, sample: 1, appeal: 2, C: 3, current: 4 }[k] ?? 5;
  }

  return { credibility, reasonCodes, grade, thresholds, routeOf, isImagery, allocate, workItems, droneRoute, handling, priority, deadlines, daysBetween, addDays, parseDate, countyAuditSize, lowerBound, requiredN, evaluate, droneGroups, kml, fieldOrder, haversine };
})();
