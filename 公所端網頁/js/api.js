/*
 * 天相星 公所端：資料接口
 *
 * 畫面只透過這個檔案取得與送出資料。目前全部「未接入」：
 *   - 讀取類一律回傳空值（null 或 []），畫面顯示「—」。
 *   - 寫入類先存進本機暫存區（outbox），讓操作流程可以走完；接上後端時改成呼叫 API 即可。
 *
 * 每個函式上方註明回傳格式與對應的構想書章節。欄位名稱沿用表 33 的 26 個核心欄位。
 */
window.SA = window.SA || {};

SA.api = (function () {
  const CONNECTED = false;
  const MODE_KEY = 'skyaide.office.mode'; // 'blank' 留白 | 'test' 測試資料庫
  const OUTBOX_KEY = 'skyaide.office.outbox';
  const STATE_KEY = 'skyaide.office.state';

  const wait = (v) => Promise.resolve(v);

  function readLS(key, fallback) {
    try { const s = localStorage.getItem(key); return s ? JSON.parse(s) : fallback; } catch (e) { return fallback; }
  }
  function writeLS(key, val) {
    try { localStorage.setItem(key, JSON.stringify(val)); return true; } catch (e) { return false; }
  }

  // 寫入：未接入時放進本機暫存區，回傳 { ok, queued, id }
  function queue(type, payload) {
    const box = readLS(OUTBOX_KEY, []);
    const item = { id: type + '-' + Date.now().toString(36) + Math.random().toString(36).slice(2, 6), type, payload, at: new Date().toISOString() };
    box.push(item);
    const saved = writeLS(OUTBOX_KEY, box);
    return wait({ ok: true, queued: true, saved, id: item.id });
  }

  // 本機操作狀態（例如：本機已核定、已封存），讓同一台電腦上重新整理後仍看得到
  function getLocal(ns, id) { const s = readLS(STATE_KEY, {}); return (s[ns] || {})[id] || null; }
  function setLocal(ns, id, val) { const s = readLS(STATE_KEY, {}); s[ns] = s[ns] || {}; s[ns][id] = val; writeLS(STATE_KEY, s); }

  const api = {
    CONNECTED,
    mode: () => { try { return localStorage.getItem(MODE_KEY) || 'test'; } catch (e) { return 'test'; } },
    setMode: (m) => { try { localStorage.setItem(MODE_KEY, m); } catch (e) { /* 無法保存 */ } },

    // ================= 基本資料 =================

    /** 承辦身分與公所 → { office:'○○鄉公所', unit:'農業課', officer:'姓名', role:'承辦'|'課長' } */
    getSession: () => wait(null),

    /** 災害事件清單 → [{ id, name, hazard, alertAt, radarAt, gradedAt, announceDate:'YYYY-MM-DD', crops:[], weatherParamHint }] */
    listEvents: () => wait([]),

    // ================= 災後總覽（表 24 C、表 21 總覽） =================

    /**
     * → { applied, bySource:{self,farmersAssoc,proxy}, counts:{A_MET,A_NOT_MET,B,C}, notifiedUnapplied,
     *     registeredParcels, submitted, damagedUnsubmitted, appPhotos,
     *     workload:{ paper, visit, sampleA, bVisit, cVisit, currentRuleVisit, drone, waitingSupplement },
     *     delivery:[{ label, done:boolean, detail }] }
     */
    getOverview: (eventId) => wait(null),

    /** 類別（作物 × 災害類型）與系統等級 → [{ id, crop, hazard, level:'甲'|'乙'|'丙'|null, count, note }] */
    listCategories: (eventId) => wait([]),

    // ================= 案件 =================

    /**
     * 分級清單 → [{ id, caseNo, landNo, crop, hazard, categoryId, level, interval:{p10,p50,p90},
     *   checks:{ imagery:{pass,reasons,detail}, completeness:{...}, consistency:{...}, declaration:{...}, production:{...,longterm:{L1..L4}} },
     *   grade, reasons:[], sampled, estAmount, center:{lat,lon}, geometry, supplementDone, appeal }]
     */
    listCases: (eventId) => wait([]),

    /**
     * 單一案件 → 上列欄位，另加：
     *   applicant, areaHa, baselineLocked, declaredCrop, satCrop, satCropProb,
     *   evidence:[{ kind:'pre'|'post'|'hotspot'|'app', label, date, source, url }],
     *   topFeatures:[文字], rchecks:{ R1:{status,source,note}, ... },
     *   report:{ no, hash, verifyCode, signature, timestamp, batchRoot },
     *   provenance:{ raw, process, inference, manual, mapping },
     *   photoDuplicate, officeDecision
     */
    getCase: (caseId) => wait(null),

    /** 不予救助的法定原因（由救助系統或作業要點提供） → [{ code, label }] */
    listRejectReasons: () => wait([]),

    /** S6 公所判定：以機關憑證簽章，判定指向報告雜湊，與系統結果並列、不覆蓋 */
    submitDecision: (caseId, decision) => { setLocal('decision', caseId, decision); return queue('decision', { caseId, decision }); },
    getLocalDecision: (caseId) => wait(getLocal('decision', caseId)),

    /** 改排到場 */
    scheduleVisit: (caseId, reason) => queue('visit', { caseId, reason }),

    /** 通知：kind = 'supplement'（補件提醒）| 'notMet'（A 未達標通知）| 'unapplied'（明顯受損未申請） */
    sendNotice: (caseIds, kind, content) => queue('notice', { caseIds, kind, content }),

    /** R1–R5 承辦確認結果回寫同一案件 */
    saveRCheck: (caseId, key, value) => { const cur = getLocal('rcheck', caseId) || {}; cur[key] = value; setLocal('rcheck', caseId, cur); return queue('rcheck', { caseId, key, value }); },
    getLocalRChecks: (caseId) => wait(getLocal('rcheck', caseId) || {}),

    // ================= 受理與文件核對（表 24 D） =================

    /** 以 QR、案號、查驗碼、地號或身分證查詢 → 同 getCase 的案件，另加 docs:[{ key, status:'已附'|'未附'|'免附', basis }] */
    findApplication: (query) => wait(null),

    /** 查驗存證報告（只需公開金鑰，不必連線） → { signature:boolean, timestamp:string, batch:boolean, inputs:[{file,sha256,official}] } */
    verifyReport: (verifyCode) => wait(null),

    /** 受理 */
    acceptApplication: (caseId, docs) => queue('accept', { caseId, docs }),

    // ================= 補件與無人機（三、4(11)） =================

    /** 道路通阻資料，用於選定起飛點 → [{ lat, lon, status }] */
    getRoadStatus: (eventId) => wait([]),

    /** C 缺失補件狀態：'pending' 補件中 | 'received' 已補件 | 'expired' 期限已過未補件 */
    setSupplementState: (caseId, state) => { setLocal('supp', caseId, state); return queue('supplement-state', { caseId, state }); },
    localSupplementStates: () => wait((readLS(STATE_KEY, {}).supp) || {}),

    /** 無人機任務：計算航線 → 提交飛行申請 → 派飛 → 資料回傳（進入 S1 登錄） */
    droneStep: (groupId, step, payload) => { const cur = getLocal('drone', groupId) || {}; cur[step] = new Date().toISOString(); setLocal('drone', groupId, cur); return queue('drone-' + step, { groupId, payload }); },
    localDroneStates: () => wait((readLS(STATE_KEY, {}).drone) || {}),

    // ================= 抽查、封存、評等（S7、S8） =================

    /** → { batchId, reportCount, merkleRoot, sealed:boolean, sealedAt } */
    getBatch: (eventId) => wait(getLocal('batch', eventId)),

    /** S7 封存：同批報告組成 Merkle 根交公所，封存後不得增刪報告 */
    sealBatch: (eventId) => { const v = { sealed: true, sealedAt: new Date().toISOString(), merkleRoot: null }; setLocal('batch', eventId, v); return queue('seal', { eventId }); },

    /** 甲等類別 20% 抽查案件與回填 → [{ caseId, caseNo, categoryId, grade, fieldLoss, correct }] */
    listSamples: (eventId) => wait([]),

    /** S8 評等輸入 → [{ id, crop, hazard, level, overallLevel, streak, govApproved, directTarget,
     *   samples:{ aMet:{correct,total}, aNotMet:{correct,total}, b:{confirmed,total}, applied, aCount } }] */
    listEvaluation: (eventId) => wait([]),

    // ================= 層報、抽查、復查（表 24 F） =================

    /** → { households, surveyed, total, statTableReady } */
    getReporting: (eventId) => wait(null),

    /** 復查、更正增撥、低利貸款受災證明 → [{ caseNo, kind:'appeal'|'correction'|'loan', receivedAt, noticeAt, status }] */
    listFollowups: (eventId) => wait([]),

    submitReport: (eventId, kind) => queue('report', { eventId, kind }),

    // ================= 平時：災前基準確認（表 24 A、B） =================

    /** → [{ id, applicant, identity, rightDoc, declaredHa, capHa, roadPondPct, cadastreMatch, status, landNo, crop }] */
    listBaseline: (status) => wait([]),

    /** → 上列欄位，另加 layers:{ cadastre, declared, landuse, neighbors }（GeoJSON）, checks:[{ label, ok, detail }] */
    getBaseline: (id) => wait(null),

    /** 確認一次即鎖定為災前基準 */
    confirmBaseline: (id, method, note) => { setLocal('baseline', id, { method, note, at: new Date().toISOString() }); return queue('baseline', { id, method, note }); },

    // ================= 現勘公務手機 =================

    /** 災前與災後第一時間下載 B、C 清單與路線 → [{ caseId, caseNo, landNo, kind:'B'|'sample'|'appeal'|'C', confirm, center }] */
    downloadRoute: (eventId) => wait([]),

    /** 回傳現勘紀錄（恢復連線後自動回傳） */
    uploadFieldRecords: (records) => wait({ ok: false, reason: '資料接口未接入' }),

    // ================= 本機暫存區 =================
    outbox: () => readLS(OUTBOX_KEY, []),
    clearOutbox: () => writeLS(OUTBOX_KEY, [])
  };

  // 測試資料庫：讀取類改由 SA.testdb 提供（js/testdb.js），寫入類照樣進本機暫存區
  const READERS = ['getSession', 'listEvents', 'getOverview', 'listCategories', 'listCases', 'getCase', 'listRejectReasons', 'findApplication', 'verifyReport',
    'getRoadStatus', 'listSamples', 'listEvaluation', 'getReporting', 'listFollowups', 'listBaseline', 'getBaseline', 'downloadRoute'];
  READERS.forEach((name) => {
    const blank = api[name];
    api[name] = function () {
      if (!CONNECTED && api.mode() === 'test' && SA.testdb && SA.testdb[name]) return Promise.resolve(SA.testdb[name].apply(null, arguments));
      return blank.apply(null, arguments);
    };
  });
  const blankBatch = api.getBatch;
  api.getBatch = (eventId) => {
    const local = getLocal('batch', eventId);
    if (!CONNECTED && api.mode() === 'test' && SA.testdb) return wait(Object.assign({}, SA.testdb.getBatch(eventId), local || {}));
    return blankBatch(eventId);
  };
  return api;
})();
