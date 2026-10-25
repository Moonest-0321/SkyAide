/*
 * 天相星 公所端：規則參數
 * 每一項都對應構想書（完整版・母檔）的章節或表號，改規則時只改這裡。
 */
window.SA = window.SA || {};
SA.pages = SA.pages || {};

SA.config = {
  // ---- 案件分級（表 17）：40% 與 10% 為起始值，正式依作物以 Learn then Test 校準 ----
  grade: {
    lossThreshold: 20,      // 救助門檻：損失率 20%
    aMetLowerMin: 40,       // A 達標：第 10 百分位 ≥ 40%
    aNotMetUpperMax: 10,    // A 未達標：第 90 百分位 ≤ 10%
    perCrop: {}             // 依作物覆寫，例如 { "麻竹筍": { aMetLowerMin: 42, aNotMetUpperMax: 8 } }
  },

  // ---- 分級代號與農民端白話（三、1(4)） ----
  grades: {
    A_MET:     { code: 'A_MET',     label: 'A 達標',   plain: '受損明顯' },
    A_NOT_MET: { code: 'A_NOT_MET', label: 'A 未達標', plain: '影像顯示未達 20%' },
    B:         { code: 'B',         label: 'B 邊緣',   plain: '需公所到場確認' },
    C:         { code: 'C',         label: 'C 缺失',   plain: '請補充資料' }
  },

  // ---- 可信度五項檢核（表 39） ----
  checks: [
    { key: 'imagery',      label: '影像條件', pass: '坵塊內縮後像素足夠，地籍對位可靠',           reasons: ['像素不足', '對位不確定'] },
    { key: 'completeness', label: '觀測完整', pass: '光學未被雲遮過半，或雷達訊號強到可單獨判定', reasons: ['雲遮'] },
    { key: 'consistency',  label: '多源一致', pass: '雷達與光學對「是否受損」結論一致',             reasons: ['來源不一致', '疑似灌溉'] },
    { key: 'declaration',  label: '申報一致', pass: '衛星判釋作物與申報作物相同',                   reasons: ['作物不符'] },
    { key: 'production',   label: '生產事實', pass: '災前 6 期植生顯示有作物生長，並通過長時間對照 L1–L4', reasons: ['災前未見作物生長', 'L1 耕作物候', 'L2 作物年齡', 'L3 損失時點', 'L4 前次災損後恢復'] }
  ],

  // ---- 長時間對照（表 42） ----
  longterm: [
    { key: 'L1', label: 'L1 耕作物候',       desc: '過去 12 個月是否有申報作物應有的生長週期' },
    { key: 'L2', label: 'L2 作物年齡',       desc: '多年生作物自最近一次裸地起算的年數' },
    { key: 'L3', label: 'L3 損失時點',       desc: '災前植生下降幅度，扣除前兩年同時段的正常變化' },
    { key: 'L4', label: 'L4 前次災損後恢復', desc: '兩次災害之間是否恢復或補植' }
  ],

  // ---- 申請交叉檢核 R1–R5（表 18） ----
  rchecks: [
    { key: 'R1', label: 'R1 地號與範圍',     fields: '縣市、段小段、地號、坵塊及公告區域',             handle: '比對地籍版本與實際耕作範圍；差異列待確認' },
    { key: 'R2', label: 'R2 作物一致性',     fields: '申報作物、登記作物、衛星物候及播種日期',         handle: '改種、未登記或模型低信心時，先補紀錄或現地照片' },
    { key: 'R3', label: 'R3 面積與損失',     fields: '申報面積、使用範圍、受影響面積及損失區間',       handle: '扣除農路、水塘與重疊；分列受影響面積及作物損失率' },
    { key: 'R4', label: 'R4 實際經營人',     fields: '申請人、地主、租約或使用同意書有效期間',         handle: '由公所核對合法使用與實際經營；分析端僅使用代碼' },
    { key: 'R5', label: 'R5 重複與歷次案件', fields: '同災害、期作、地號、作物、申請人與空間交集',     handle: '提示重複送件；依法合併連續災害或保留不同救助項目' }
  ],
  rStatuses: ['一致', '待補件', '待確認'],

  /*
   * ---- C 缺失的處理（團隊 2026-10-25 定案） ----
   * 1. 一律先要求補件（原因碼以白話通知申請人）。
   * 2. 補件回來 → 重新檢核，五項全過即重新分級。
   * 3. 補件期限過了仍未補 → 依公所實際量能處理：
   *    影像類（imagery: true，雲遮或影像不清楚）→ 有無人機量能時計算航線、提交飛行申請、派飛；
   *    超出無人機量能者，以及非影像類 → 排入到場，依現勘量能與優先度排序。
   * supplement：通知申請人要補什麼
   */
  reasonRoute: {
    '像素不足':         { imagery: true,  supplement: '補 App 照片（遠拍、近拍各一張）', note: '小於 0.3 公頃小田，衛星解析度不足' },
    '雲遮':             { imagery: true,  supplement: '補 App 照片（遠拍、近拍各一張）', note: '颱風後雲遮，光學影像看不到' },
    '樹冠遮蔽或網室':   { imagery: true,  supplement: '補 App 照片（遠拍、近拍各一張）', note: '山區竹林、網室，衛星看不到單株或結構受損' },
    '對位不確定':       { imagery: false, supplement: '補範圍說明或使用權文件；必要時由地主申請鑑界', note: '地籍與影像對位誤差過大' },
    '來源不一致':       { imagery: false, supplement: '補 App 照片並說明受災情形', note: '雷達與光學結論不一致，需查明變化原因' },
    '疑似灌溉':         { imagery: false, supplement: '補 App 照片並說明田間是否灌水整地', note: '插秧期灌水與淹水難以區分' },
    '作物不符':         { imagery: false, supplement: '更正申報作物或補種植佐證', note: '衛星判釋作物與申報不同' },
    '災前未見作物生長': { imagery: false, supplement: '補種植佐證（綠色環境給付收執聯、產銷履歷、App 照片等）', note: '災前 6 期未見作物生長' },
    'L1 耕作物候':      { imagery: false, supplement: '補種植佐證', note: '過去 12 個月未見申報作物的生長週期' },
    'L2 作物年齡':      { imagery: false, supplement: '補種植佐證（種植起始年）', note: '作物年齡與申報不符' },
    'L3 損失時點':      { imagery: false, supplement: '補 App 照片並說明收成時間', note: '災前已有異常下降' },
    'L4 前次災損後恢復':{ imagery: false, supplement: '補復耕或補植佐證', note: '前次災損後未見恢復' },
    '面積不符':         { imagery: false, supplement: '補範圍說明', note: '地號內夾雜農路建物，差距過大' }
  },
  routeLabels: { supplement: '補件中', drone: '派無人機', visit: '到場', over: '超出量能，排隊' },
  supplementStates: { pending: '補件中', received: '已補件，重新檢核', expired: '期限已過未補件' },

  // ---- 公所量能（由承辦在「補件與無人機」設定） ----
  capacity: {
    droneCases: 0,        // 本期無人機可處理件數
    personDays: 0,        // 本期可投入現勘人日
    perPersonDay: 10      // 每人日可處理 B、C 筆數（表 68 取最保守 10 筆）
  },

  // ---- 無人機（表 55） ----
  droneGroupRadiusM: 500, // 相距 500 公尺內分為一組，共用起飛點
  drone: {
    cruiseMps: 8,          // 轉場速度（公尺／秒）
    scanHaPerMin: 0.1,     // 掃描效率（公頃／分鐘，30 公尺高度）
    batteryMin: 25         // 單顆電池可用飛行分鐘
  },

  // ---- 系統等級（表 19、表 67） ----
  levels: {
    '丙': { name: '丙　收集期',   role: '照常分級，結果不交公所使用', office: '全部依現行方式勘查；現勘結果回填，作為訓練與驗證資料' },
    '乙': { name: '乙　考察期',   role: 'A／B／C 與存證報告作為參考資料', office: '依現行規定勘查，系統結果不作免勘依據；可依分級排定現勘順序；現勘結果與系統判定比對' },
    '甲': { name: '甲　參與判定', role: 'A 級直接參與判定', office: 'A 達標書面審核、A 未達標通知，各抽查 20%；B 到場；C 補件或到場' }
  },
  upgrade: {
    aMetLB: 0.95, aNotMetLB: 0.95, accuracyLB: 0.90,
    directRate: 0.50,          // 乙等門檻；甲等依丙等實測 B 級比例訂定，不低於 50%
    bConfirmLB: 0.80,
    streakForA: 10,            // 連續達標場次
    confidence: 0.95,          // 95% 單側信賴下界
    downgradeLB: 0.95          // 兩種 A 精確度下界低於此值即降一等
  },
  sampleRate: 0.20,            // 甲等 A 級各抽查 20%

  // ---- 法定期限（表 5、表 64） ----
  deadlines: {
    applyWorkdays: 10,   // 公告翌日起 10 個工作日
    surveyDays: 30,      // 公告翌日起 30 日內完成勘查
    reportDays: 7,       // 完成勘查後 7 日內報送
    countyAuditDays: 7,  // 縣府收件翌日起 7 日內抽查
    afaReviewDays: 7,    // 農糧署收件翌日起 7 日內審核
    appealDays: 7,       // 接獲通知後 7 日內申請復查
    correctionMonths: 4, // 更正增撥 4 個月內
    gradingHours: 8,     // 雷達到站至分級完成 8 小時內（表 71）
    preImageMaxDays: 10  // 災前影像距災害 ≤ 10 日（S1）
  },

  // ---- 縣市抽查戶數級距（三、4(13)） ----
  countyAudit: [
    { maxExclusive: 100,      rule: '至少 5 戶（10 戶以下抽半數）' },
    { maxExclusive: 500,      rule: '抽 5%' },
    { maxExclusive: 1500,     rule: '至少 25 戶' },
    { maxExclusive: Infinity, rule: '至少 30 戶' }
  ],
  countyPassRate: 0.90,
  countyAuditMaxRounds: 2,

  // ---- 判定方式（表 7 三條路徑 + 甲等書面審核） ----
  decisionMethods: {
    paper:     { label: '書面審核（存證報告）',          note: '甲等類別的 A 達標，未被抽中 20% 抽查' },
    objective: { label: '客觀證明免勘',                  note: '達公告天氣參數或公告災損嚴重，且具種植客觀證明文件（救助辦法第 12 條、2025 年 4 月 18 日公告）' },
    appPhoto:  { label: 'App 照片＋公所認定',            note: '農民以農業部現地照相 App 拍攝上傳，公所依照片認定損失率超過 20%（作業要點）' },
    survey:    { label: '實地勘查',                      note: '依現行規定到場' },
    sample:    { label: '實地勘查（20% 抽查）',          note: '甲等 A 級抽查，結果同時作為 S8 評等樣本' }
  },

  // ---- 災前基準確認（表 24 A、B） ----
  baselineStatuses: [
    { key: 'pending',  label: '待確認' },
    { key: 'scope',    label: '範圍需確認' },
    { key: 'blocked',  label: '系統已擋下' },
    { key: 'locked',   label: '已鎖定' }
  ],
  baselineConfirmMethods: [
    { key: 'overlay', label: '依套疊結果確認',   note: '地籍外框、申報範圍與國土利用調查相符' },
    { key: 'adjust',  label: '修正範圍後確認',   note: '扣除農路、水塘或只租一部分時，承辦修正後鎖定' },
    { key: 'visit',   label: '排定到場確認',     note: '套疊無法判斷時到場，確認後鎖定' }
  ],

  // ---- 受理應附文件（表 61、表 63） ----
  requiredDocs: [
    { key: 'form',     label: '現金救助申請表（預填、申請人確認簽章）' },
    { key: 'id',       label: '身分證明' },
    { key: 'bankbook', label: '存摺影本（帳號由申請人自填，系統不保存）' },
    { key: 'land',     label: '土地證明（公所查得到地政資料時可免附）', canWaive: true },
    { key: 'right',    label: '使用權文件（租約、使用同意書等，非地主時）', optional: true },
    { key: 'proxy',    label: '委託書（委託送件時）', optional: true }
  ],

  reportLabel: {
    reference: '影像存證參考，尚非種植客觀證明文件；以公所認定為準',
    approved:  '本類別已經政府審核列入種植客觀證明；以公所認定為準'
  }
};
