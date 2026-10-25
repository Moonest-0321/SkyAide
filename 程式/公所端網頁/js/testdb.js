/*
 * 天相星 公所端：測試資料庫
 * 固定亂數種子產生一場虛構災害，所有人名、地號、圖資、數字都是假的，只用來測試畫面與流程。
 * 圖資用色塊表示，位置大致在嘉義縣竹崎鄉一帶，不代表真實地籍。
 * 分級一律由 rules.js 依構想書規則計算，不在這裡寫死。
 */
window.SA = window.SA || {};

SA.testdb = (function () {
  // ---------- 亂數 ----------
  function rng(seed) { return function () { seed |= 0; seed = seed + 0x6D2B79F5 | 0; let t = Math.imul(seed ^ seed >>> 15, 1 | seed); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
  const R = rng(20260706);
  const pick = (a) => a[Math.floor(R() * a.length)];
  const between = (a, b) => a + R() * (b - a);
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  const gauss = () => { let u = 0, v = 0; while (!u) u = R(); while (!v) v = R(); return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v); };
  function fakeHash(s) { // 測試用假雜湊（不是 SHA-256）
    let h1 = 0x811c9dc5, out = '';
    for (let k = 0; k < 8; k++) { for (let i = 0; i < s.length; i++) { h1 ^= s.charCodeAt(i) + k; h1 = Math.imul(h1, 16777619); } out += (h1 >>> 0).toString(16).padStart(8, '0'); }
    return out;
  }
  const iso = (d) => d.toISOString();
  const ymd = (d) => d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
  const md = (d) => (d.getMonth() + 1) + '/' + d.getDate();
  const addD = (d, n) => { const x = new Date(d); x.setDate(x.getDate() + n); return x; };

  // ---------- 災害事件：公告日設為 12 天前，勘查期進行中 ----------
  const today = new Date(); today.setHours(0, 0, 0, 0);
  const announce = addD(today, -12);
  const alertAt = addD(announce, -5); alertAt.setHours(14, 30);
  const radarAt = addD(announce, -2); radarAt.setHours(6, 10);
  const gradedAt = new Date(radarAt); gradedAt.setHours(13, 40);
  const EVENT = {
    id: 'TEST-01', name: '［測試］颱風測試一號', hazard: '颱風', area: '嘉義縣竹崎鄉（測試）',
    crops: ['麻竹筍', '香蕉', '水稻', '竹', '木瓜'], alertAt: iso(alertAt), radarAt: iso(radarAt), gradedAt: iso(gradedAt), announceDate: ymd(announce),
    weatherParamHint: '測試站累積雨量可能達公告參數'
  };
  const preDate = addD(alertAt, -8), postDate = addD(radarAt, 0), hotDate = addD(radarAt, 1), appDate = addD(alertAt, 2);

  // ---------- 類別與系統等級 ----------
  const CATS = [
    { id: 'c1', crop: '麻竹筍', hazard: '倒伏', level: '甲', n: 30 },
    { id: 'c2', crop: '香蕉', hazard: '倒伏', level: '甲', n: 26 },
    { id: 'c3', crop: '水稻', hazard: '淹水', level: '乙', n: 22 },
    { id: 'c4', crop: '竹（山坡）', hazard: '倒伏', level: '乙', n: 8, forceReason: '樹冠遮蔽或網室' },
    { id: 'c5', crop: '木瓜', hazard: '倒伏', level: '丙', n: 8 }
  ];

  // ---------- 位置：6 個聚落，每個聚落內的田相距數百公尺 ----------
  const BASE = { lat: 23.523, lon: 120.552 };
  const clusters = Array.from({ length: 6 }, () => ({ lat: BASE.lat + between(-0.02, 0.02), lon: BASE.lon + between(-0.025, 0.025) }));
  function rect(center, areaHa) {
    const side = Math.sqrt(areaHa * 10000); // 公尺
    const ratio = between(0.6, 1.6);
    const w = side * Math.sqrt(ratio), hgt = side / Math.sqrt(ratio);
    const dLat = hgt / 2 / 111320, dLon = w / 2 / (111320 * Math.cos(center.lat * Math.PI / 180));
    return { type: 'Polygon', coordinates: [[[center.lon - dLon, center.lat - dLat], [center.lon + dLon, center.lat - dLat], [center.lon + dLon, center.lat + dLat], [center.lon - dLon, center.lat + dLat], [center.lon - dLon, center.lat - dLat]]] };
  }

  // ---------- 案件 ----------
  const SURNAMES = ['陳', '林', '黃', '張', '李', '王', '吳', '劉', '蔡', '楊', '許', '鄭', '謝', '郭', '洪'];
  const cases = [];
  let seq = 0;
  CATS.forEach((cat) => {
    for (let i = 0; i < cat.n; i++) {
      seq++;
      const first = seq === 1;
      const id = 'T' + String(seq).padStart(4, '0');
      const cl = pick(clusters);
      const center = first ? { lat: clusters[0].lat, lon: clusters[0].lon } : { lat: cl.lat + between(-0.004, 0.004), lon: cl.lon + between(-0.004, 0.004) };
      const areaHa = first ? 0.62 : +(R() < 0.18 ? between(0.08, 0.29) : between(0.3, 1.6)).toFixed(4);

      // 真實損失（測試用，代表日後現勘的結果）
      const m = R();
      const trueLoss = first ? 61 : Math.round(m < 0.5 ? between(45, 92) : m < 0.8 ? between(0, 6) : between(12, 34));

      // 五項檢核
      const ck = (pass, reasons, detail) => ({ pass, reasons: pass ? [] : reasons, detail });
      const imgFail = !first && ((areaHa < 0.3 && R() < 0.6) ? '像素不足' : R() < 0.03 ? '對位不確定' : cat.forceReason || null);
      const cloud = !first && R() < 0.1;
      const consFail = !first && (cat.crop === '水稻' && R() < 0.14 ? '疑似灌溉' : R() < 0.04 ? '來源不一致' : null);
      const declFail = !first && R() < 0.04;
      const prodFail = !first && R() < 0.04 ? pick(['災前未見作物生長', 'L1 耕作物候', 'L3 損失時點']) : null;
      const longterm = { L1: prodFail !== 'L1 耕作物候', L2: true, L3: prodFail !== 'L3 損失時點', L4: true };
      const px = Math.round(areaHa * 100 * 0.7);
      const prob = +between(0.8, 0.97).toFixed(2);
      const checks = {
        imagery: ck(!imgFail, [imgFail], imgFail ? (imgFail === '像素不足' ? '內縮 10 米後 ' + px + ' 個像素，不足判讀' : imgFail === '樹冠遮蔽或網室' ? '樹冠遮蔽，衛星看不到單株倒伏' : '地籍與正射影像偏移 ' + between(6, 14).toFixed(1) + ' 公尺') : '內縮 10 米後 ' + px + ' 個像素；地籍與正射影像偏移 ' + between(0.5, 2.5).toFixed(1) + ' 公尺'),
        completeness: ck(!cloud, ['雲遮'], cloud ? '光學 ' + md(postDate) + ' 雲遮 ' + Math.round(between(55, 90)) + '%，雷達訊號不足以單獨判定' : '雷達訊號可單獨判定；光學雲遮 ' + Math.round(between(5, 30)) + '%'),
        consistency: ck(!consFail, [consFail], consFail === '疑似灌溉' ? '雷達變暗，但正值插秧前灌水整地期' : consFail ? '雷達顯示受損、光學未見變化' : '雷達與光學皆顯示' + (cat.hazard === '淹水' ? '積水' : '倒伏')),
        declaration: ck(!declFail, ['作物不符'], declFail ? '衛星判釋為' + pick(['休耕', '雜作', '果樹']) + '，與申報不同' : '衛星判釋' + cat.crop + '（機率 ' + prob + '），與申報相同'),
        production: Object.assign(ck(!prodFail, [prodFail], prodFail ? '長時間對照未通過：' + prodFail : '災前 6 期有生長；長時間對照 L1–L4 全過'), { longterm })
      };

      // 損失區間（估計 = 真實 + 誤差）
      const est = clamp(Math.round(trueLoss + gauss() * 6), 0, 100);
      const half = Math.round(between(5, 10));
      const interval = first ? { p10: 52, p50: 60, p90: 68 } : { p10: clamp(est - half, 0, 100), p50: est, p90: clamp(est + half, 0, 100) };

      const c = {
        id, caseNo: 'T-' + EVENT.id.slice(-2) + '-' + String(seq).padStart(4, '0'),
        landNo: first ? '竹崎段 0418' : pick(['竹崎段', '內埔段', '灣橋段', '鹿麻產段', '金獅段']) + ' ' + String(Math.floor(between(100, 2400))).padStart(4, '0'),
        crop: cat.crop, hazard: cat.hazard, categoryId: cat.id, level: cat.level,
        applicant: first ? '陳大明（測試）' : pick(SURNAMES) + '○○（測試）',
        areaHa, declaredCrop: cat.crop, satCrop: declFail ? '不同作物' : cat.crop, satCropProb: declFail ? null : prob,
        baselineLocked: first ? true : R() < 0.8, checks, interval, _trueLoss: trueLoss,
        center, geometry: rect(center, areaHa),
        estAmount: Math.round(areaHa * (interval.p50 / 100) * 120000), // 測試用金額
        hasApp: R() < 0.55
      };
      c.grade = SA.rules.grade(c);
      c.reasons = SA.rules.reasonCodes(checks);
      c.sampled = c.level === '甲' && (c.grade === 'A_MET' || c.grade === 'A_NOT_MET') && !first && R() < 0.2;
      c.appeal = c.grade === 'A_NOT_MET' && c.level === '甲' && !c.sampled && R() < 0.25;
      if (c.grade === 'C') c.supplementState = pick(['pending', 'pending', 'received', 'expired', 'expired', 'expired']);
      cases.push(c);
    }
  });

  // ---------- 農民帳號（情境示例：三、1(7)） ----------
  // 陳大明：麻竹筍 A 達標、香蕉 B 邊緣、山坡竹林 C 缺失；林先生：A 未達標；另設乙等、丙等農民各一位
  const firstOf = (fn) => cases.find(fn);
  const chen = [cases[0], firstOf((c) => c.crop === '香蕉' && c.grade === 'B') || firstOf((c) => c.level === '甲' && c.grade === 'B'), firstOf((c) => c.categoryId === 'c4')].filter(Boolean);
  const lin = [firstOf((c) => c.level === '甲' && c.grade === 'A_NOT_MET' && !c.sampled) || firstOf((c) => c.grade === 'A_NOT_MET')].filter(Boolean);
  const huang = [firstOf((c) => c.level === '乙' && c.grade === 'C' && c.categoryId === 'c3') || firstOf((c) => c.level === '乙' && c.categoryId === 'c3'), firstOf((c) => c.level === '乙' && c.categoryId === 'c3' && c.grade === 'A_MET')].filter(Boolean);
  const wu = [firstOf((c) => c.level === '丙')].filter(Boolean);
  const FARMERS = [
    { id: 'F1', name: '陳大明（測試）', phone: '09xx-xxx-001', identity: '一般承租', cases: chen },
    { id: 'F2', name: '林○○（測試）', phone: '09xx-xxx-002', identity: '地主', cases: lin },
    { id: 'F3', name: '黃○○（測試）', phone: '09xx-xxx-003', identity: '三七五租約', cases: huang },
    { id: 'F4', name: '吳○○（測試）', phone: '09xx-xxx-004', identity: '借用親友的地', cases: wu }
  ];
  FARMERS.forEach((f) => { f.cases = f.cases.filter((c, i, a) => a.indexOf(c) === i); f.cases.forEach((c) => { c.applicant = f.name; c.farmerId = f.id; }); });
  if (chen[1]) chen[1].landNo = '竹崎段 0422';
  if (chen[2]) { chen[2].landNo = '金獅段 1107'; chen[2].supplementState = 'pending'; }
  // 陳大明另有一塊未申請、但衛星看到明顯受損的田（主動通知）
  const unapplied = { id: 'U1', farmerId: 'F1', landNo: '竹崎段 0431', crop: '麻竹筍', areaHa: 0.35, baselineLocked: true, center: { lat: clusters[0].lat + 0.0012, lon: clusters[0].lon - 0.0009 } };
  unapplied.geometry = rect(unapplied.center, unapplied.areaHa);

  // ---------- 衛星時序（每 6 天一筆，35% 被雲遮） ----------
  function series(crop, loss, seed) {
    const r2 = rng(seed);
    const out = [];
    const start = addD(alertAt, -360);
    for (let i = 0; i <= 62; i++) {
      const d = addD(start, i * 6);
      const doy = (d - new Date(d.getFullYear(), 0, 1)) / 86400000;
      let v;
      if (crop === '水稻') { const ph = ((doy - 60 + 365) % 182) / 182; v = 0.2 + 0.6 * Math.max(0, Math.sin(Math.PI * ph)); }
      else if (crop === '木瓜') v = 0.55 + 0.05 * Math.sin(doy / 58);
      else v = 0.68 + 0.05 * Math.sin(doy / 40);
      if (d > alertAt) v = v * (1 - (loss || 0) / 100 * 0.8);
      v += (r2() - 0.5) * 0.05;
      out.push({ date: ymd(d), ndvi: r2() < 0.35 ? null : +clamp(v, 0, 0.95).toFixed(3) });
    }
    return out;
  }

  // ---------- 單一案件的完整欄位 ----------
  function swatch(fill, label, pattern) {
    const pat = pattern ? '<defs><pattern id="p" width="14" height="14" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="14" height="14" fill="' + fill + '"/><rect width="6" height="14" fill="' + pattern + '"/></pattern></defs><rect width="200" height="200" fill="url(#p)"/>' : '<rect width="200" height="200" fill="' + fill + '"/>';
    const svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200">' + pat + '<text x="100" y="186" font-size="14" text-anchor="middle" fill="#fff" font-family="sans-serif">' + label + '</text></svg>';
    return 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg);
  }
  function lossColor(loss) { // 綠 → 土黃 → 褐
    const t = clamp(loss / 100, 0, 1);
    const a = [78, 140, 64], b = [140, 110, 60], c = [110, 70, 40];
    const mix = (x, y, k) => x.map((v, i) => Math.round(v + (y[i] - v) * k));
    const col = t < 0.5 ? mix(a, b, t * 2) : mix(b, c, (t - 0.5) * 2);
    return 'rgb(' + col.join(',') + ')';
  }
  // 存證報告內容：固定格式序列化後計算雜湊（正式系統為 SHA-256＋憑證簽章＋RFC 3161 時戳）
  function canonical(o) { return JSON.stringify(o, Object.keys(o).sort()); }
  function reportContent(c) {
    return {
      '報告編號': 'SKY-TEST-' + c.id.slice(1), '地號': c.landNo, '坵塊': c.id, '面積_公頃': c.areaHa, '申報作物': c.crop,
      '損失區間': c.interval.p10 + '/' + c.interval.p50 + '/' + c.interval.p90,
      '可信度': SA.rules.credibility(c.checks), '原因碼': (c.reasons || []).join('、'),
      '災前影像': 'S1A_IW_GRDH_TEST_' + ymd(preDate).replace(/-/g, ''), '災後影像': 'S1A_IW_GRDH_TEST_' + ymd(postDate).replace(/-/g, ''),
      '版本': 'skyaide-test-0.1', '效力說明': c.level === '甲' ? SA.config.reportLabel.approved : SA.config.reportLabel.reference
    };
  }
  const SIGNED = {}; // 測試：簽發時的雜湊，代表資料中心簽章與 Merkle 樹所綁定的內容
  function signedHash(c) { if (!SIGNED[c.id]) SIGNED[c.id] = fakeHash(canonical(reportContent(c))); return SIGNED[c.id]; }

  function full(c) {
    const loss = c._trueLoss;
    const cloud = c.checks.completeness.pass === false;
    const content = reportContent(c);
    const rep = { no: content['報告編號'], hash: fakeHash(canonical(content)), content };
    rep.verifyCode = rep.no + '-' + rep.hash.slice(0, 16);
    rep.signature = true; rep.timestamp = SA.ui.datetime(gradedAt) + '（測試時戳）'; rep.batchRoot = true;
    const feats = c.hazard === '淹水'
      ? ['雷達淹水投票：' + Math.round(between(60, 100)) + '% 像素至少兩法判為淹水', 'VV 較災前下降 ' + between(3, 8).toFixed(1) + ' dB', '植生較往年同期多降 ' + between(0.05, 0.3).toFixed(2)]
      : ['VH 較災前最近兩期下降 ' + between(1, 5).toFixed(1) + ' dB', '倒伏面積比例 ' + Math.round(clamp(loss + between(-8, 8), 0, 100)) + '%（熱區高解析）', '植生較往年同期多降 ' + between(0.05, 0.4).toFixed(2)];
    const rs = (ok, st) => ({ status: ok ? '一致' : st, source: ok ? '救助系統、地政資料（測試）' : '系統比對（測試）' });
    return Object.assign({}, c, {
      evidence: [
        { kind: 'pre', date: md(preDate), source: 'Sentinel-1', url: swatch(lossColor(0), '災前') },
        { kind: 'post', date: md(postDate), source: 'Sentinel-1', url: swatch(lossColor(loss), '災後') },
        { kind: 'hotspot', date: md(hotDate), source: '福衛八號', url: cloud ? swatch('#c9cdd4', '雲遮') : swatch(lossColor(loss), '熱區', lossColor(0)) },
        { kind: 'app', date: c.hasApp ? md(appDate) : null, source: c.hasApp ? '農民 App 即時拍攝' : '未上傳', url: c.hasApp ? swatch('#9fb49a', 'App') : null }
      ],
      topFeatures: c.grade === 'C' ? [] : feats,
      rchecks: {
        R1: rs(c.checks.imagery.pass || c.checks.imagery.reasons[0] !== '對位不確定', '待確認'),
        R2: rs(c.checks.declaration.pass, '待補件'),
        R3: rs(true), R4: rs(true), R5: rs(true)
      },
      report: rep,
      notMetReason: c.grade === 'A_NOT_MET' ? '五項檢核全過；損失區間 ' + c.interval.p10 + '–' + c.interval.p90 + '%，上限未超過 10%' : null,
      provenance: {
        raw: 'S1A_IW_GRDH_TEST_' + ymd(preDate).replace(/-/g, '') + '、S1A_IW_GRDH_TEST_' + ymd(postDate).replace(/-/g, '') + '（測試編號）',
        process: '前處理 v0.1：輻射校正、地形校正、坵塊內縮 10 米',
        inference: '判讀 skyaide-test-0.1；損失區間 ' + c.interval.p10 + '/' + c.interval.p50 + '/' + c.interval.p90,
        manual: '尚無',
        mapping: c.landNo + ' ↔ 坵塊 ' + c.id + ' ↔ ' + c.caseNo
      },
      photoDuplicate: c.hasApp ? '與歷次案件無相似照片' : '無照片',
      submitBy: pick(['本人', '本人', '農會協助', '委託']),
      declaredRate: Math.round(clamp(loss + between(-10, 15), 0, 100)),
      docs: [
        { key: 'form', status: '已附', basis: '預填申請表，申請人已勾選屬實' },
        { key: 'id', status: '已附', basis: '臨櫃核對' },
        { key: 'bankbook', status: pick(['已附', '未附']), basis: '申請人自填帳號' },
        { key: 'land', status: '免附', basis: '公所以地政資訊查詢系統查得' },
        { key: 'right', status: pick(['已附', '']), basis: '租約（測試）' },
        { key: 'proxy', status: '', basis: '' }
      ]
    });
  }

  // ---------- 災前基準 ----------
  const baseline = [];
  const bStatus = ['pending', 'pending', 'pending', 'pending', 'scope', 'scope', 'scope', 'blocked', 'blocked', 'locked', 'locked', 'locked', 'locked', 'locked'];
  bStatus.forEach((st, i) => {
    const center = { lat: BASE.lat + between(-0.02, 0.02), lon: BASE.lon + between(-0.02, 0.02) };
    const cap = +between(0.3, 1.5).toFixed(4);
    const declared = st === 'blocked' ? +(cap * between(1.1, 1.4)).toFixed(4) : +(cap * between(0.7, 1)).toFixed(4);
    const road = st === 'scope' ? between(0.12, 0.3) : between(0.01, 0.08);
    baseline.push({
      id: 'B' + String(i + 1).padStart(3, '0'), applicant: pick(SURNAMES) + '○○（測試）', identity: pick(['地主', '三七五租約', '一般承租', '借用親友的地']),
      rightDoc: pick(['第二類謄本', '租約＋第二類謄本', '使用同意書＋第二類謄本']), declaredHa: declared, capHa: cap, roadPondPct: road,
      cadastreMatch: st === 'scope' ? false : true, status: st, landNo: pick(['竹崎段', '內埔段', '灣橋段']) + ' ' + String(Math.floor(between(100, 2400))).padStart(4, '0'),
      crop: pick(['麻竹筍', '香蕉', '水稻', '木瓜']), center, proof: pick(['綠色環境給付收執聯', '產銷履歷', 'App 照片', '自行申報'])
    });
  });
  function baselineFull(b) {
    const cad = rect(b.center, b.capHa / 0.95);
    const shrink = (g, k, dx, dy) => { const ring = g.coordinates[0]; const cx = b.center.lon, cy = b.center.lat; return { type: 'Polygon', coordinates: [ring.map(([x, y]) => [cx + (x - cx) * k + (dx || 0), cy + (y - cy) * k + (dy || 0)])] }; };
    const declared = shrink(cad, b.status === 'blocked' ? 1.12 : 0.92, b.status === 'scope' ? 0.00012 : 0, 0);
    const landuse = shrink(cad, 0.85, -0.00005, 0.00004);
    const nb = [[1, 0], [-1, 0], [0, 1], [0, -1]].map(([sx, sy]) => { const ring = cad.coordinates[0]; const w = ring[1][0] - ring[0][0], hh = ring[2][1] - ring[1][1]; return { type: 'Polygon', coordinates: [ring.map(([x, y]) => [x + sx * w * 1.02, y + sy * hh * 1.02])] }; });
    return Object.assign({}, b, {
      layers: { cadastre: cad, declared, landuse, neighbors: nb },
      checks: [
        { label: '申報面積未超過本筆面積 × 持分', ok: b.declaredHa <= b.capHa, detail: b.declaredHa + ' / ' + b.capHa + ' 公頃' },
        { label: '扣除農路水塘後的種植範圍', ok: b.roadPondPct < 0.1, detail: '農路水塘佔 ' + (b.roadPondPct * 100).toFixed(1) + '%' },
        { label: '地籍與航照相符', ok: b.cadastreMatch, detail: b.cadastreMatch ? '偏移 < 2 公尺' : '偏移約 9 公尺，圖解地籍區' },
        { label: '使用權文件有效期間涵蓋本期作', ok: true, detail: '至 ' + (today.getFullYear() + 2) + ' 年（測試）' }
      ]
    });
  }

  // ---------- 評等（跨場累積的測試數字） ----------
  const EVALS = [
    { id: 'c1', crop: '麻竹筍', hazard: '倒伏', level: '甲', overallLevel: '甲', streak: 11, govApproved: true, samples: { aMet: { correct: 120, total: 120 }, aNotMet: { correct: 64, total: 64 }, b: { confirmed: 52, total: 58 }, applied: 900, aCount: 560 } },
    { id: 'c2', crop: '香蕉', hazard: '倒伏', level: '甲', overallLevel: '甲', streak: 10, govApproved: true, samples: { aMet: { correct: 98, total: 98 }, aNotMet: { correct: 72, total: 73 }, b: { confirmed: 40, total: 46 }, applied: 700, aCount: 420 } },
    { id: 'c3', crop: '水稻', hazard: '淹水', level: '乙', overallLevel: '甲', streak: 6, govApproved: false, samples: { aMet: { correct: 140, total: 140 }, aNotMet: { correct: 90, total: 90 }, b: { confirmed: 61, total: 70 }, applied: 520, aCount: 300 } },
    { id: 'c4', crop: '竹（山坡）', hazard: '倒伏', level: '乙', overallLevel: '甲', streak: 0, govApproved: false, samples: { aMet: { correct: 12, total: 12 }, aNotMet: { correct: 0, total: 0 }, b: { confirmed: 3, total: 4 }, applied: 80, aCount: 12 } },
    { id: 'c5', crop: '木瓜', hazard: '倒伏', level: '丙', overallLevel: '甲', streak: 0, govApproved: false, samples: { aMet: { correct: 66, total: 66 }, aNotMet: { correct: 61, total: 61 }, b: { confirmed: 22, total: 26 }, applied: 230, aCount: 127 } }
  ];

  // ---------- 對外：與 api.js 讀取函式同名 ----------
  const visibleGrade = (c) => c.level !== '丙';
  const fieldOf = (c) => ({ id: c.id, caseId: c.id, landNo: c.landNo, crop: c.crop, areaHa: c.areaHa, baselineLocked: c.baselineLocked, center: c.center, geometry: c.geometry, level: c.level });
  return {
    fakeHash, canonical,
    // ---------- 農民端 ----------
    listFarmers: () => FARMERS.map((f) => ({ id: f.id, name: f.name })),
    getFarmer: (id) => {
      const f = FARMERS.find((x) => x.id === id) || FARMERS[0];
      const fields = f.cases.map(fieldOf);
      if (f.id === 'F1') fields.push(Object.assign({ unappliedDamaged: true, level: '甲' }, unapplied));
      fields.forEach((x, i) => { const c = cases.find((k) => k.id === x.caseId); x.series = series(x.crop, c ? c._trueLoss : 72, 100 + i + f.id.charCodeAt(1)); });
      return { id: f.id, name: f.name, phone: f.phone, identity: f.identity, fields };
    },
    listFarmerCases: (id) => { const f = FARMERS.find((x) => x.id === id) || FARMERS[0]; return f.cases.map((c) => full(c)); },
    // 查驗：比對報告內容的雜湊與簽發時綁定的雜湊（測試用假雜湊）
    verifyContent: (content) => {
      const c = cases.find((x) => 'SKY-TEST-' + x.id.slice(1) === (content && content['報告編號']));
      if (!c) return null;
      const h = fakeHash(canonical(content)), sh = signedHash(c);
      const ok = h === sh;
      return { hash: h, signedHash: sh, signature: ok, timestamp: ok, batch: ok, at: SA.ui.datetime(gradedAt) + '（測試時戳）', batchId: EVENT.id + '-B1' };
    },

    getSession: () => ({ office: '嘉義縣竹崎鄉公所（測試）', unit: '農業課', officer: '測試承辦', role: '承辦' }),
    listEvents: () => [EVENT],
    listCategories: () => CATS.map((c) => ({ id: c.id, crop: c.crop, hazard: c.hazard, level: c.level, count: cases.filter((x) => x.categoryId === c.id).length })),
    listCases: () => cases.map((c) => Object.assign({}, c)),
    getCase: (id) => { const c = cases.find((x) => x.id === id); return c ? full(c) : null; },
    getOverview: () => {
      const vis = cases.filter(visibleGrade);
      const cnt = (g) => vis.filter((c) => c.grade === g).length;
      const items = SA.rules.workItems(cases);
      const k = (x) => items.filter((i) => i.kind === x).length;
      const jia = cases.filter((c) => c.level === '甲');
      return {
        applied: cases.length, bySource: { self: Math.round(cases.length * 0.82), farmersAssoc: Math.round(cases.length * 0.12), proxy: cases.length - Math.round(cases.length * 0.82) - Math.round(cases.length * 0.12) },
        counts: { A_MET: cnt('A_MET'), A_NOT_MET: cnt('A_NOT_MET'), B: cnt('B'), C: cnt('C') },
        notifiedUnapplied: 9, registeredParcels: 214, submitted: cases.length, damagedUnsubmitted: 9, appPhotos: cases.filter((c) => c.hasApp).length,
        workload: {
          paper: jia.filter((c) => (c.grade === 'A_MET' || c.grade === 'A_NOT_MET') && !c.sampled).length,
          visit: k('B') + k('sample') + k('appeal') + k('current') + items.filter((i) => i.kind === 'C').length,
          currentRuleVisit: cases.length,
          sampleA: k('sample'), bVisit: k('B'), cVisit: items.filter((i) => i.kind === 'C').length, currentRule: k('current'),
          drone: items.filter((i) => i.kind === 'C' && SA.rules.isImagery(i.reasons)).length,
          waitingSupplement: items.filter((i) => i.kind === 'C' && i.supplementState === 'pending').length
        },
        delivery: [
          { label: '分級清冊與存證報告交本所（封存根雜湊）', done: true, detail: fakeHash('root').slice(0, 4) + '…' + fakeHash('root').slice(-4) },
          { label: '分級清冊副本交縣市政府農業處，作為抽查參考', done: true, detail: SA.ui.datetime(gradedAt) },
          { label: 'B、C 清單離線下載至公務手機', done: false, detail: '尚未下載' },
          { label: '熱區圖交縣府提報（與官方統計偏差 ±20% 內）', done: true, detail: '偏差 +6%（測試）' }
        ]
      };
    },
    listRejectReasons: () => [
      { code: 'T1', label: '［測試］損失率未達 20%' },
      { code: 'T2', label: '［測試］非實際從事生產者' },
      { code: 'T3', label: '［測試］申報不實' }
    ],
    findApplication: (q) => {
      q = String(q || '').trim();
      const c = cases.find((x) => x.caseNo === q || x.landNo === q || x.id === q || q.startsWith('SKY-TEST-' + x.id.slice(1)));
      return c ? full(c) : null;
    },
    verifyReport: (code) => {
      const c = cases.find((x) => String(code || '').startsWith('SKY-TEST-' + x.id.slice(1)) || x.caseNo === code);
      if (!c) return null;
      const f = full(c);
      const ok = String(code) === f.report.verifyCode || code === c.caseNo;
      return { signature: ok, timestamp: f.report.timestamp, batch: ok, inputs: [] };
    },
    getRoadStatus: () => [],
    getBatch: () => ({ batchId: EVENT.id + '-B1', reportCount: cases.filter(visibleGrade).length, merkleRoot: fakeHash('root'), sealed: false }),
    listSamples: () => cases.filter((c) => c.sampled).map((c, i) => ({ caseId: c.id, caseNo: c.caseNo, category: c.crop + ' × ' + c.hazard, grade: c.grade, fieldLoss: i % 4 === 3 ? null : c._trueLoss })),
    listEvaluation: () => EVALS.map((e) => JSON.parse(JSON.stringify(e))),
    getReporting: () => ({ households: Math.round(cases.length * 0.85), surveyed: Math.round(cases.length * 0.4), total: cases.length }),
    listFollowups: () => [
      { caseNo: cases[3].caseNo, kind: 'appeal', receivedAt: ymd(addD(today, -2)), noticeAt: ymd(addD(today, -4)), status: '待處理' },
      { caseNo: cases[8].caseNo, kind: 'correction', receivedAt: ymd(addD(today, -1)), noticeAt: ymd(addD(today, -6)), status: '審核中' },
      { caseNo: cases[12].caseNo, kind: 'loan', receivedAt: ymd(today), noticeAt: null, status: '待核發' }
    ],
    listBaseline: (status) => baseline.filter((b) => b.status === status).map((b) => Object.assign({}, b)),
    getBaseline: (id) => { const b = baseline.find((x) => x.id === id); return b ? baselineFull(b) : null; },
    downloadRoute: () => {
      const items = SA.rules.workItems(cases).filter((i) => i.kind !== 'C' || i._route === 'visit');
      return items.map((c) => ({ caseId: c.id, caseNo: c.caseNo, landNo: c.landNo, kind: c.kind, confirm: c.kind === 'C' ? c.reasons.join('、') : c.kind === 'B' ? '損失率是否達 20%' : '到場確認', center: c.center }));
    }
  };
})();
