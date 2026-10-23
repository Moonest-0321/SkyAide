# 2026 衛星數位應用創新大賽　創意構想書

| 選題名稱 | 題目六：偏鄉農林牧智慧連線與精準作業定位 |
|---|---|
| 參賽隊伍名稱 | 天相星 |
| 作品名稱 | 天相星 SkyAide：公所災後勘查衛星快篩平台 |
| 作品標語 | 天象天相，無相萬象。 |

## 一、作品摘要

農業天災救助卡在公所勘查：須現勘的案件平均 58 天撥款，免勘者只要 24–30 天，但免勘僅占 3.7%，因為公所缺少可以採信、事後經得起查核的證據〔1〕。

天相星 SkyAide 平時以衛星替每塊田累積紀錄，災後「先看證據、再看損失」：證據有缺失列 **C 缺失**（補件）；損失區間整個落在 20% 門檻同一側為 **A 達標／A 未達標**（直接判定）；跨過門檻為 **B 邊緣**（公所到場）。系統依實測結果分 **丙（收集）、乙（考察）、甲（參與判定）** 三等，逐作物、逐災害類型評等，精確度下界不足即降等。每份存證報告附數位簽章、時戳與查驗碼，可離線查驗、可重算。

- **衛星必要性**：災前狀態無法事後補拍；雷達可在颱風後穿雲取像；影像由第三方取得、附官方檢查碼，無人能改寫。
- **概念創新**：把衛星比對做成嵌入法定流程的分級清單、預填申請與存證報告；系統地位隨驗證結果升降。
- **技術可行**：Sentinel-1／2 為主、福衛八號與九號補強；作物、淹水、損失模型皆採已發表方法並列出規格；已以丹娜絲真實影像、模擬工況、通過 12 項竄改測試的流程原型與 12 個介面畫面驗證方向。
- **效益**：甲等、直接判定率 50% 時，一場大型災害實地現勘減少約 12.6 萬筆，約 6.7 萬件提早約 28 天完成審核，公所勘查需求由量能的 113% 降至 86%；新增支出約為增聘人力方案的二至四成。

<img src="charts/n0_overview_v8.png" width="88%">

**圖 1　計畫總覽。** 問題、八步標準作業流程、三個系統等級與甲等目標效果。

## 二、需求分析

### 1. 應用需求分析

**(1) 救助延遲卡在公所勘查**

近 10 年農作物天災損失平均每年 84.5 億元〔2〕；2025 年五起颱風豪雨農業損失 50.66 億元，另有漁產損失約 7.7 億元〔3〕〔4〕。丹娜絲災後 86 天，核撥僅占公所初勘合格金額的 59%，約三分之一停在「公所勘查至縣府提報」〔5〕。2021 年 8 月豪雨 209,189 件申請到撥款平均 55 天，超過法定 44 天（圖 2）〔1〕。救助流程中只有「公所勘查」仍須人力逐筆到場；本作品只在提報（熱區圖）與勘查（分級清單、存證報告）兩處介入，並預填申請表，其餘法定流程不變（圖 3）〔1〕〔6〕。

<img src="charts/fig2_days.png" width="45%"> <img src="charts/t1_relief_steps.png" width="50%">

**圖 2　不同勘查方式的申請到撥款平均天數（左）〔1〕；圖 3　現金救助流程與天相星的介入點（右）〔7〕〔6〕。**

**(2) 偏鄉與公所的困境**

**表 1　公所勘查工作的主要困境**

| 類型 | 具體事實 | 來源 |
|---|---|---|
| 量能不足 | 農業課平均 4 人，大型災害每人約 370 筆；雲林單一品項曾逾 10,000 件；撥款最長 100 天 | 〔9〕〔1〕 |
| 人到不了 | 現勘只看得到災後的田；古坑竹林無法存證被判不合格；勘災人員曾於山區受傷 | 〔9〕〔8〕 |
| 訊號中斷 | 颱風後停電斷網，清單與照片無法傳遞；農災 App 須有人到場、定位約 ±20 公尺 | 〔10〕〔11〕 |
| 判定困難 | 山陀兒平均損害 20%、凱米 28%，大量案件落在門檻附近；未達標準仍獲救助 2.615 億元 | 〔9〕〔12〕〔13〕〔1〕 |

**(3) 制度接點：不需修法即可起步**

救助辦法已明定「勘查得以科學技術輔助之」。現行三條免勘路徑為：達天氣參數且具種植客觀證明、App 照片＋公所認定、其餘抽樣或實地勘查〔14〕〔15〕。本作品不改變這三條路徑（圖 4）：丙、乙等時存證報告只是參考資料；達甲等前，須以逐類別精確度報告申請列入種植客觀證明或作業要點，並取得「A 未達標不到場即通知」的作業依據。

<img src="charts/n12_pathways.png" width="72%">

**圖 4　現行免勘路徑與天相星的對應。** 依救助辦法第 12 條與作業要點整理〔7〕〔6〕。

**(4) 證據可信度與防偽的需求**

2015 年竹塘案中，承辦把停耕裸地上的枯藤雜草認定為受災香瓜，一審以圖利罪判 5 年 2 個月，法院則以空照圖認定災前即為裸地〔16〕。公所要放心採信，證據必須說得出來源、證明沒被改過、換人計算結果相同；《電子簽章法》與《人工智慧基本法》也提高了可驗證與可問責的要求〔18〕〔19〕。

**表 2　證據可信度的缺口與本作品的對應**

| 需要回答的問題 | 現況 | 天相星的做法 |
|---|---|---|
| 災前確實有種嗎 | 災後只看得到災後的田 | 災前時序加多年紀錄；未見作物生長列 C |
| 是否本田、本次災害 | App 照片定位約 ±20 公尺〔11〕 | 照片座標、時間對照坵塊與衛星變化 |
| 證據是否重複使用 | 未見重複照片檢核 | 感知雜湊比對歷次照片 |
| 報告是否被改、由誰簽發 | 電子檔可編輯；衛星影像可被偽造〔17〕 | 數位簽章、時戳、查驗碼 |
| 換人計算是否相同 | 判斷過程多未留存 | 輸入、程式、參數記錄雜湊，可重算 |
| 系統與人工分得清嗎 | 同一份紀錄 | 公所判定另行簽章，與系統結果並列 |

**(5) 題目定位**

**表 3　題目六要素與本作品對應**

| 題目六要素 | 本作品對應 |
|---|---|
| 偏鄉場域、通訊涵蓋不足 | 人到不了的田以衛星存證；B、C 清單離線下載；定位樁經衛星通訊回傳 |
| 範圍廣、巡檢成本高 | 甲等時 A 級書面審核或通知，現勘集中於 B；C 級解析度不足者派無人機 |
| 衛星遙測、AI 影像辨識 | 雷達與光學時序判讀；作物、淹水、倒伏、埋沒；分位數損失區間 |
| 作物種類與生長狀態 | 災前時序作物判釋與物候檢核，對照申報 |
| 作物異常、災損監測 | 災後分級、延遲性災損追蹤、平時異常提醒、魚塭停電與池水變化 |
| GNSS、IoT、衛星通訊 | e-GNSS 坡面定位樁；照片 GNSS 存證；魚塭溶氧與電箱紀錄 |

### 2. 國內外現況分析

**表 4　現有方案與本作品比較**

| 方案 | 能證明 | 災前紀錄 | 公所須到場 | 主要限制 | 來源 |
|---|---|---|---|---|---|
| 災損天氣參數 | 損失（推論） | 無 | 否 | 測站盲區；約 40 種品項 | 〔20〕 |
| 農災 App | 輔助佐證 | 無 | 是 | 須有人到場 | 〔21〕 |
| 無人機判釋 | 損失 | 無 | 是 | 補助 2,050 萬元全數未執行 | 〔22〕〔1〕 |
| 雲林 NDVI 試算 | 疑似受損範圍 | 部分 | 是 | 只用光學、未綁地號；與核定區範圍重疊約 64% | 〔9〕 |
| 歐盟面積監測系統 | 是否依申報耕作 | 有 | 紅燈才需 | 事前稽核，不處理災後損失 | 〔23〕〔24〕 |
| **天相星** | **種植＋損失** | **有** | **甲等時僅 B 與部分 C** | 依丙、乙、甲三等逐步取得判定地位 | — |

最值得參考的是歐盟：2023 年起所有面積型給付須以 Sentinel 時序逐塊判讀，只對不確定者到場〔24〕；奧地利約 300 萬塊田每月自動處理〔25〕，義大利實地檢查降至 3%–5%〔26〕。歐盟查的是整季耕作、本作品處理 30 日內的災後損失，因此借鑑流程與治理（表 5），不借門檻數值。

**表 5　歐盟作法與本作品借鑑**

| 歐盟作法 | 本作品借鑑 |
|---|---|
| 分綠、黃、紅燈，2019 年需到場者最多 1%〔27〕 | A 達標、A 未達標、B 邊緣、C 缺失四類 |
| 守規農民被判不符不得超過 5%〔27〕 | 兩種 A 精確度下界皆須 ≥ 95%，逐類別評定 |
| 先通知、可修正，愛爾蘭約 91% 如期回覆〔24〕〔28〕 | A 未達標附理由通知、C 缺失補件提醒 |
| 預填申請、地理標記照片等值證據〔24〕〔29〕 | 預填申請表；照片分即時拍攝與相簿匯入 |
| 年度品質評估〔24〕 | S8 每場災害後逐類別評等 |
| 多訊號同時出現才採信；周邊同作物田比較〔30〕〔31〕 | 雷達光學互相印證；植生以周邊同作物田為基準 |

## 三、創意構想提案內容

### 1. 創意構想使用情境

**(1) 使用對象與場域**

| 角色 | 對象 | 使用方式 |
|---|---|---|
| 主要使用者 | 全國 368 個鄉鎮市區公所農業課 | 確認災前基準；受理、分級審核、現勘、報送 |
| 次要使用者 | 農民與養殖戶；縣市政府農業處 | App、簡訊或農會協助；分級清冊副本作抽查參考 |
| 延伸使用者 | 防檢單位、農會、產險公司 | 異常提醒、協助登錄、理賠佐證 |

場域以颱風常襲的偏鄉農區與沿海魚塭為主，優先為雲林、嘉義、屏東、臺南、高雄、臺東、南投〔32〕〔12〕〔13〕。農民登錄採自願，未登錄者仍依現行程序申請。

**(2) 運作流程**

平時農民五步登錄，公所於 1 月綠色環境給付申報期確認範圍、鎖定災前基準。災後警報時鎖定災前影像與程式版本，雷達到站 8 小時內完成分級；公告後預填申請，並主動通知受損但未申請者。勘查期依系統等級處理（圖 5）；現勘回填後 S8 逐類別重新評等。

<img src="charts/n3_swimlane_v8.png" width="100%">

**圖 5　農民、天相星與公所三方的運作流程。** 勘查期以甲等為例。

**(3) 案件分級與系統等級**

勘查拆成兩個衛星可回答的問題：**證據夠不夠**（災前在生產、影像可用、申報相符）與**損失是否達 20%**（第 10、50、90 百分位損失區間）。可信度五項檢核任一未過即列 C，即使損失看起來很明顯也一樣；五項全過才依區間分級（表 6、圖 6）。C 的意思是「要補資料」，B 的意思是「資料夠了，但數字太接近」。沒申請的田不列入分級，看到明顯受損者主動通知可以申請。農民端以「受損明顯」「影像顯示未達 20%」「需公所到場確認」「請補充資料」呈現，並註明以公所認定為準。

**表 6　案件分級**

| 分級 | 判定條件 | 甲等時的處理 |
|---|---|---|
| A 達標 | 五項全過，區間下限 ≥ 40% | 書面審核、撥款；抽查 20% |
| A 未達標 | 五項全過，區間上限 ≤ 10% | 勘查期內通知，附影像日期與理由，可補件或申訴；抽查 20% |
| B 邊緣 | 五項全過，區間跨過 20% | 公所到場確認 |
| C 缺失 | 任一項未過（雲遮、對位、作物不符、災前未見生長、疑似灌溉等） | 依原因碼補件或派無人機，必要時到場 |

40%、10% 為起始值，依作物以 Learn then Test 校準；判讀元件未達使用門檻時，用它判出的案件歸 B 或 C。

<img src="charts/n6_grades_v8.png" width="100%">

**圖 6　案件分級與各系統等級下的處理方式。**

**表 7　系統等級**

| 等級 | 條件 | 系統的角色 | 公所的作業 |
|---|---|---|---|
| 丙 收集期 | 未達乙等條件 | 照常分級，結果不交公所 | 全部依現行方式勘查，結果回填 |
| 乙 考察期 | 各項指標達標，但連續場次不足或未通過政府審核 | A／B／C 與存證報告作參考 | 依現行規定勘查；依分級排定順序 |
| 甲 參與判定 | 乙等條件＋連續 10 場達標＋政府審核 | A 級直接參與判定 | A 達標書面審核、A 未達標通知，各抽查 20% |

等級先評整體，整體達乙等後再逐類別（作物 × 災害類型）評定，類別不得高於整體。丙等時每一筆都現勘，A、B、C 都有標準答案；甲等時以抽查與 B、C 回填持續驗證。

**A 未達標的制度設計。** 不到場即認定未達標，與公所依財稅資料判定低收入戶資格、申請人不服再申復的結構相同〔110〕。因農損證據會消失，通知須在 30 日勘查期內送達並給補件期限，附影像日期與理由；A 未達標與 A 達標一樣抽查 20%，因為「該給的沒給」若無人申訴就不會被發現。

**(4) 介面與情境示例**

兩端已完成 12 個可互動畫面（農民端：平時、颱風過後、補件、送件、A 未達標通知、查驗；公所端：總覽、分級清單、審核、補件與無人機、評等、現勘手機）。每一步對應現行法定文件；每類結果都說明原因與下一步；乙等時農民只收到補件提醒；採大字級與白話用語，並有簡訊版與農會協助。

<img src="charts/ui_farmer_v8.png" width="76%">

**圖 7　農民端原型（甲等情境）。** 由左至右：每塊田的結果、補充資料、確認送件、A 未達標通知。資料為示意。

<img src="charts/ui_office_review_v8.png" width="80%">

**圖 8　公所端案件審核。** 左為證據、五項檢核與損失區間；右為系統判定與本所判定（以機關憑證另行簽章）。上方可切換乙、甲等。資料為示意。

陳大明的竹崎段 0418 平地麻竹筍園，雷達驟變、熱區高解析影像確認整片倒伏，五項全過，區間 52%–68%，判 A 達標，甲等時書面審核即可撥款。他的香蕉田區間 14%–33% 列 B，公所路通後到場核定 25%；山坡竹林樹冠遮蔽列 C，派無人機。鄰田林先生的香蕉區間 0%–6%，判 A 未達標，勘查期第 12 天收到附理由的通知，補 App 照片申訴後公所到場。

### 2. 衛星必要性分析

**表 8　採用的衛星與地面技術**

| 技術 | 規格 | 用途 |
|---|---|---|
| Sentinel-1 SAR | C 波段 VV＋VH、10 米像素（解析度約 20 × 22 米）、6 天、免費〔34〕〔35〕 | 颱風後第一手：倒伏、淹水、埋沒、魚塭 |
| Sentinel-2 光學 | 10–20 米、約 5 天〔36〕 | 植生、作物時序、多年紀錄 |
| 福衛八號（自主） | 1 米（處理後 0.7 米）；對臺一日最多三次〔37〕〔38〕 | 小於 0.3 公頃的田、魚塭水車、熱區確認 |
| 福衛九號（自主） | 雷達，2028、2030 年發射〔39〕 | 自主穿雲來源 |
| 商業高解析 | ICEYE 聚束雷達、Pléiades Neo 0.3 米〔40〕〔41〕 | 熱區確認倒伏、堤岸、埋沒 |
| VIIRS 夜間燈光 | 約 500 米、每日〔42〕 | 魚塭區停電天數 |
| e-GNSS、衛星通訊 | 平面精度優於 5 公分；約 700 個衛星備援站點〔43〕〔44〕 | 坡面定位樁、斷網回傳、座標存證 |

衛星不可取代的理由有五：災前紀錄無法事後補拍；一次過境涵蓋整個鄉鎮、同一標準；雷達可於颱風後穿雲取像〔45〕；不受道路中斷限制〔8〕；量體只有衛星處理得了，凱米受害 21,712 公頃〔12〕，以無人機飛完丹娜絲受害面積僅飛行費即約 48.6 萬至 68 萬元〔46〕〔47〕。分工是：衛星判斷證據夠不夠，無人機看清小田，公所做最後認定。

### 3. 概念創新性分析

**表 9　概念創新點**

| 創新點 | 說明 |
|---|---|
| 嵌入流程而非監測圖 | 分級清單、審核畫面、預填申請表，銜接農災 App |
| 由監測轉為存證 | 存證報告對準種植客觀證明；災前基準借綠色環境給付申報時程確認 |
| 先看證據、再看損失 | 「要補資料」與「數字太接近」分開，公所知道每筆該做什麼 |
| 損失區間 | 達標與未達標都能直接判定；逐筆列出影響判定的特徵 |
| 系統分等、逐類別升降 | 丙、乙、甲三等；下界不足即降等，降等只會讓更多案件到場 |
| 長時間對照 | 以多年紀錄檢查物候、作物年齡、損失時點、前次災損恢復 |
| 可查驗、可重算 | 簽章、時戳、查驗碼、雜湊鏈，任何人可離線查驗〔48〕〔49〕〔50〕 |
| 魚塭在養證明 | 不估魚隻數，證明災前在養與受災方式〔51〕 |

### 4. 技術可行性分析

**以下為正式系統的規格與目標；示範只用來驗證方向，規模與精度不代表正式系統。**

**(1) 系統架構、資料與運算規格**

系統分資料、處理、判讀、案件、應用五層，現勘回填形成閉環（圖 9）。坵塊化置於判讀之前，模型處理「一塊田的一條時序」，運算量與坵塊數成正比、與影像面積無關；地號與實際耕作對不上者列 C。雲端常駐 2 台 L4 GPU、每年約 500 小時 A100 重新訓練、儲存約 15 TB，年費約 70 萬元〔54〕〔55〕；全國約 200 萬筆坵塊跑一輪作物判釋，單張 GPU 約 27 分鐘〔56〕。算力不是瓶頸，出件時間取決於雷達到站。

<img src="charts/t6_layers.png" width="45%"> <img src="charts/n19_damage_model.png" width="50%">

**圖 9　系統架構（左）；圖 10　損失率模型的輸入、融合與輸出（右）〔33〕。**

**表 10　前處理與坵塊特徵**

| 資料 | 前處理 | 坵塊特徵 |
|---|---|---|
| Sentinel-1 | 精密軌道、熱雜訊、輻射校正；Lee 斑點濾波、地形正規化〔52〕；同調性；陰影與疊置遮罩 | VV、VH、VH／VV、同調性 |
| Sentinel-2 | L2A；Cloud Score+ 去雲，門檻 0.60〔53〕；補值日期加旗標，不作災後證據 | NDVI、NDRE、NDWI、MNDWI |
| 福衛八號 | 正射、融合 0.7 米、與地籍套疊 | 水車、倒伏與埋沒範圍 |
| VIIRS | VNP46A2，以災前 30 天中位數為基準〔42〕 | 停電天數 |
| 坵塊化 | 內縮 10 米；排除水面與非農地；少於 5 格改用高解析影像，否則「影像條件」不過 | 每坵塊每日期一列，含雲與補值旗標 |

**(2) 判讀模型規格與目標**

八項任務都採已發表、可取得程式或權重的方法，以公所回填資料微調；原則是小樣本可用、能說明理由、能輸出不確定度。目標一律以 95% 單側信賴下界判斷，未達時該任務只作排序或原因碼。

**表 11　判讀模型規格與目標**

| 任務 | 模型 | 輸入 → 輸出 | 目標（依據） |
|---|---|---|---|
| 作物判釋 | 時序 Transformer〔56〕；Presto 預訓練模型微調（2 層、8 頭、128 維、約 40 萬參數）〔57〕 | 災前 12 個月 S1／S2、氣象、地形 → 各作物機率 | 各作物準確率 ≥ 80%（60 萬坵塊基準最高 0.80〔56〕） |
| 水稻 | 同上＋插秧灌水雷達下降規則 | 全年 VV、VH → 水稻、插秧日 | 準確率 ≥ 80%；鄉鎮面積偏差 ±20%〔58〕 |
| 淹水 | Otsu、時序異常、微調 Prithvi 三法投票；插秧期遮罩 | 災前災後 VV、VH → 淹水比例 | 區域 CSI ≥ 70%；單一來源支撐 A 須精確度 ≥ 95%（單一門檻 IoU 0.29、Prithvi 0.83〔59〕〔60〕） |
| 倒伏 | VH 對數比值＋隱馬可夫隨機場〔61〕〔62〕；高解析語意分割 | VH、VH／VV、1 米影像 → 三級與面積比 | Sentinel 精確度 ≥ 80% 作佐證；1 米影像 ≥ 95% 支撐 A（雷達研究僅有資料組合間一致率 64%–88%〔63〕；小麥倒伏 F1 85.3%〔64〕） |
| 埋沒、流失 | 同調性 < 0.5 且降 > 0.3 | 同調性 → 全面改變與否 | 精確度 ≥ 95%（與聯合國獨立判圖吻合 93%〔65〕） |
| 植生受損 | 相對自身往年與周邊同作物田的標準分數〔30〕 | NDVI、NDRE → 偏離程度 | 排序與佐證，不單獨支撐 A |
| 損失區間 | LightGBM 分位數迴歸〔66〕＋保形校準〔67〕，與半經驗損傷函數堆疊 | 上列輸出、天氣、作物、地形 → P10／50／90 | 每作物均方根誤差 ≤ 10 個百分點（文獻 8.2–12.3〔68〕） |
| 魚塭 | VH 中位數＋Otsu；水車偵測；夜間燈光 | S1、福衛八號、VIIRS → 坵塊、在養、停電 | 與養殖登記一致 ≥ 80%；池水流失 ≥ 95%（91.9%〔69〕） |

**表 12　主要參數起始值（災害開始時鎖定並記錄雜湊）**

| 參數 | 起始值 | 校正 |
|---|---|---|
| 判 A 達標下限／A 未達標上限 | 40%／10% | Learn then Test 依作物，兩種誤判各 ≤ 5%〔70〕 |
| 淹水 | Otsu 上限 −15 dB；較前兩期暗 3 dB；低於 6 期平均 3σ | 回溯驗證 |
| 倒伏／埋沒 | VH 變化 2.5 dB／同調性 < 0.5 且降 > 0.3 | 回溯驗證 |
| 水稻插秧下降 | 2 dB | 鄉鎮稻作面積 |
| 植生明顯下降 | 較往年同期多降 0.2、連片 0.2 公頃 | 回溯驗證 |
| 停電／照片重複／災前影像 | 燈光低於中位數一半／dHash ≤ 16 位元／≤ 10 日 | 台電紀錄／真實 App 照片 |

模型升級沿三條路：以臺灣標註微調 Prithvi-EO-2.0（3–6 億參數）〔71〕或 Presto；以 1 米以下影像語意分割圈出倒伏與埋沒（2 米影像判香蕉園 F1 0.86〔72〕）；多源融合，任一來源結論相反即列 C。魚塭方面，衛星看不到魚，只證明在養（以放養申報為主）、以溢淹與停電排序，證據明確時（池水流失或高解析確認潰堤，且有放養申報、無收成申報）才判 A 達標。

**(3) 標準作業流程：資料輸入、模型計算與輸出**

每筆案件依三段八步處理，每步寫入一筆作業日誌，每筆記下前一筆的雜湊，刪改任何一筆其後鏈結即斷開（圖 11、表 13）。

<img src="charts/v8_sop.png" width="92%">

**圖 11　天相星標準作業流程。** 下方為貫穿全程的作業日誌（雜湊鏈）。

**表 13　標準作業流程各步驟**

| 步驟 | 做什麼 | 檢核點（未通過的處理） |
|---|---|---|
| S1 輸入登錄與檢核 | 登錄影像、地籍、申報、照片的來源、產品編號與 SHA-256 | 比對官方檢查碼〔73〕；有效像素；災前影像 ≤ 10 日（停止、補件） |
| S2 計算環境鎖定 | 凍結程式、參數、套件版本 | 只用通過前次評等的版本 |
| S3 判讀與損失區間 | 前處理、坵塊化、六項判讀、損失區間 | 計算前重比輸入雜湊（不符即中止） |
| S4 證據檢核與分級 | 五項檢核、L1–L4、R1–R5；依區間分 A 達標、A 未達標、B | 任一未過即 C；元件未達門檻歸 B 或 C |
| S5 簽發與通知 | 雜湊、簽章、時戳、查驗碼；預填申請 | 乙等起發 C 補件提醒，甲等才通知 A 級結果 |
| S6 公所判定 | 核定面積與受害率 | 機關憑證簽章，與系統結果並列 |
| S7 封存與回填 | 同批報告組成 Merkle 根；現勘回填 | 封存後不得增刪 |
| S8 檢討與評等 | 逐類別算各指標下界；重訓、校準、偏差與缺失分析 | 下界未達 95% 即降一等 |

S3、S4 的影像處理細節見圖 12，橘色為團隊以丹娜絲真實影像或模擬工況實際跑出的結果。整場災害用同一版本，新版本只用於下一場，舊案件可依當時版本重現；來源以 STAC 與 W3C PROV 記錄〔48〕〔49〕。S4 的結果直接成為公所端分級清單（圖 13）。

<img src="v8_image_flow.png" width="86%">

**圖 12　影像處理與判讀流程（S1–S8）〔80〕〔81〕〔82〕。**

<img src="charts/ui_office_list_v8.png" width="78%">

**圖 13　公所端分級清單。** 每筆列出類別等級、損失區間、可信度、分級、原因碼與處理方式。資料為示意。

**(4) 可信度檢核與防偽**

可信度只評證據品質、不評損失：五項全過為「高」，一項未過為「中」，生產事實未過或兩項以上為「低」；只有「高」進入 A、B 的判斷，其餘列 C 並以未過項目作原因碼（表 14）。可信度等級不是機率。模擬 769 筆坵塊中，「高」落在門檻錯邊的比例為 2.2%、「中」為 11.9%，平均誤差卻相近（5.4 與 5.5 個百分點），可見它辨識的正是「會不會判錯邊」〔74〕。區間縮窄一半時覆蓋率降至 51.3%，保形校準後回到 82.6%〔67〕。

**表 14　可信度五項檢核**

| 檢核 | 通過條件 | 對應風險 | 原因碼 |
|---|---|---|---|
| 影像條件 | 內縮後像素足夠、對位可靠 | 小田混合像素、圖解地籍偏移 | 像素不足、對位不確定 |
| 觀測完整 | 光學未雲遮過半，或雷達可單獨判定 | 颱風後雲遮 | 雲遮 |
| 多源一致 | 雷達與光學結論一致 | 倒伏未積水、灌水整地 | 來源不一致、疑似灌溉 |
| 申報一致 | 判釋作物與申報相同 | 改種、不實申報 | 作物不符 |
| 生產事實 | 災前 6 期有作物生長，且通過 L1–L4 | 未種植仍申請（竹塘案） | 災前未見作物生長 |

防偽的目標是讓竄改「會被發現」並指出環節。報告以 SHA-256 雜湊、憑證機構憑證簽章並取得 RFC 3161 時戳〔50〕；同批報告組成 Merkle 根交公所，原理同 C2PA〔75〕。查驗分三層：掃查驗碼、縣府比對 Merkle 根、審計重算；前兩層只需公鑰（圖 14）。公所以政府機關憑證簽章〔77〕，具《電子簽章法》推定本人簽章效力〔18〕；照片格式預留 Galileo OSNMA 欄位〔78〕。

**表 15　防偽對象與措施**

| 對象 | 可能的偽造 | 措施 |
|---|---|---|
| 衛星影像 | 替換、偽造 | 只用官方平台、比對檢查碼；與前後期不連續即標出 |
| App 照片 | 舊照、他田照、改定位 | 感知雜湊〔76〕；即時拍攝與相簿匯入分級；對照衛星紀錄 |
| 申報資料 | 未種植、作物不符、已收割 | 生產事實、申報一致、L1–L4 |
| 模型與參數 | 私改門檻 | 鎖定並記錄雜湊；版本不符即標示 |
| 存證報告 | 改數字、偽造、抽換 | 簽章、時戳、查驗碼、Merkle 根 |
| 公所判定 | 事後改核定 | 機關憑證簽章，與系統結果並列 |

<img src="charts/ui_verify_v8.png" width="24%">

**圖 14　農民端查驗存證報告。** 可切換原本與被改過的報告。資料為示意。

**(5) 長時間對照**

災前 6 期影像看不出休耕雜草或新植果苗。四項長時間對照併入「生產事實」檢核，不通過者列 C 交公所確認（表 16）；L3 與這塊田自己的往年同期比，避免把正常成熟的稻田誤判為已收割。模擬 3 年、35% 雲遮，400 筆誠實申請誤標 2%，「已收割」的漏標由雷達補足〔74〕。

**表 16　長時間對照與模擬標出率**

| 檢核 | 比對內容 | 可發現 | 只看災前 6 期 → 加上對照 |
|---|---|---|---|
| L1 耕作物候 | 過去 12 個月的生長週期 | 長期休耕 | 0% → 100% |
| L2 作物年齡 | 自最近一次裸地起算年數 | 新植冒充成樹 | 0% → 100% |
| L3 損失時點 | 災前下降扣除往年同期 | 颱風前已收割 | 2% → 78% |
| L4 前次恢復 | 兩次災害之間是否恢復 | 重複申請 | 72% → 100% |

**(6) 方向驗證：真實影像、模擬工況與原型測試**

**表 17　示範與正式系統的對照**

| 面向 | 示範（驗證方向） | 正式系統 |
|---|---|---|
| 範圍 | 丹娜絲約 25,450 公頃；模擬 83 坵塊、40 口魚塭 | 全國約 200 萬坵塊、368 個公所 |
| 影像與解析度 | S1 7 期、S2 4 期；10–20 米 | 2015 年起全時序、福衛八號與九號、熱區 0.25–1 米、無人機 |
| 標註 | 無官方標註 | 回溯 2–3 場核定清冊；丙、乙等全部現勘回填 |
| 作物／損失 | 雷達粗分水稻；標出變化面積 | 逐作物判釋；逐坵塊損失區間 |
| 運算／防偽 | 單機 CPU；示範金鑰 | 雲端 GPU；憑證、時戳服務、硬體安全模組 |

**丹娜絲真實影像。** 以 Sentinel-1 RTC 與 Sentinel-2 L2A〔79〕比對登陸點周邊約 25,450 公頃〔80〕，標出約 480 公頃植生較往年同期明顯下降、約 157 公頃雷達疑似積水（圖 15）。帶出三條規則：颱風後光學可比面積僅約三分之一，第一手須靠雷達；不扣除往年同期時植生下降為 899 公頃，近半是正常收割，故一律相對往年同期；疑似積水約 55% 在水稻田、正值插秧灌水，故新增原因碼「疑似灌溉」〔81〕。水稻面積隨插秧門檻在 1,592–4,381 公頃間變動，準備期以鄉鎮稻作面積校正。

<img src="charts/n25_danas_result.png" width="47%"> <img src="charts/n26_danas_vegetation.png" width="47%">

**圖 15　丹娜絲判讀總圖（左）與放大區植生變化（右）。** 紅：植生下降；藍：疑似積水；紫：兩者皆有；淺灰：雲遮。Contains modified Copernicus Sentinel data 2024–2025, processed by Microsoft Planetary Computer〔80〕〔79〕。

**模擬工況與流程原型。** 約 850 行 Python 模擬 83 坵塊與 40 口魚塭，完整跑過前處理到存證報告〔82〕：10 個工況中直接判定案件無一錯邊，覆蓋率平均 87%，三法投票 IoU 0.857 高於任一單法；未能直接判定者約八成是 B 邊緣。模擬與規則同一套物理假設，只證明流程可行，真實精度由丙等現勘量測。作業流程原型以 83 坵塊簽發 49 份報告，全程約 0.4 秒，單核每秒約 2 萬份；12 項測試結果如表 18〔74〕。

**表 18　防偽與可重現測試**

| 編號 | 竄改方式 | 系統反應 |
|---|---|---|
| T1 | 同一輸入重算 | 49／49 份雜湊相同 |
| T2–T4 | 改區間；改後自行重算雜湊；以非信任金鑰偽造 | 簽章與時戳驗證失敗，不在封存批次內 |
| T5 | 改第 10 筆、刪第 21 筆日誌 | 指出內容不符、序號斷開 |
| T6–T7 | 雷達 1 像素調亮 0.1 dB；私改門檻 | 計算前中止；標示版本不一致 |
| T8–T9 | 抽掉 1 份報告；改公所核定 | Merkle 根不符；公所簽章失敗 |
| T10 | 裸地以果樹申請（竹塘案型） | 列 C，附「災前未見作物生長」 |
| T11 | 24 份變造重複照片 | 24／24 標出，不同影像 0／15 誤標 |
| T12 | 水稻 A 級現勘改為 12% | 下界低於 95%，水稻下一場降一等 |

**(7) 天地整合：無人機、GNSS 與衛星通訊**

C 缺失中「影像條件」「觀測完整」未過的小田、雲遮田、香蕉、竹林、網室改派無人機：4,800 萬畫素機型 30 米高每像素約 0.5 公分〔83〕；系統匯出坵塊邊界檔自動規劃航線，500 米內分一組共用起飛點，照片回到 S1 重新檢核。B 邊緣與使用權、申報爭議仍由公所到場（圖 16）。

**表 19　天地整合元件**

| 元件 | 做法 | 補足的缺口 |
|---|---|---|
| 無人機 | 非大陸廠牌〔84〕、民航局註冊〔85〕；照片含 GNSS 與時間，優先自帶簽章 | 小田、竹林、網室解析度 |
| GNSS 定位樁 | 遮蔽與雷達陰影坡地，以 e-GNSS 量坡面位移〔86〕〔43〕，太陽能供電 | 陡坡陰影、樹冠 |
| 衛星通訊 | 無地面網路時經衛星備援站點回傳〔44〕；手機直連衛星商轉後供農民回報〔87〕 | 深山與災後斷網 |
| 離線清單與座標存證 | B、C 清單預先下載；照片記錄 GNSS 座標與時間 | 停電；現場證據 |
| 魚塭感測 | 溶氧與停電切換電箱紀錄 | 衛星看不到魚 |

<img src="charts/ui_c_drone_v8.png" width="76%">

**圖 16　公所端 C 缺失處理（左）與離線現勘手機（右）。** 資料為示意。

**(8) 門檻與系統等級：從參考資料到參與判定**

精確度不必等新災害：準備期以過去 2–3 場災害的核定清冊與 2015 年起的 Sentinel 影像回溯驗證，結果併入丙等樣本；颱風後只對候選 A 級集中的熱區下單 1 米以下影像確認，比照歐盟框架契約採購〔88〕；甲等以法定 20% 抽查持續監測。只有 A 級有對錯可言，B、C 交給人處理；所有比例一律看 95% 單側信賴下界——抽查 20 件全對，下界只有 86%〔89〕。

**表 20　評等指標**

| 指標 | 定義 |
|---|---|
| A 達標／A 未達標精確度 | 判該類的案件中，現勘確實 ≥ 20%／< 20% 的比例（逐類別） |
| 判定正確率 | 全部 A 級中現勘與系統一致的比例 |
| 直接判定率 | A 級占全部申請的比例，決定省下多少現勘 |
| B 邊緣確認率 | 判 B 者現勘確實落在 10%–30% 的比例，檢查「說不準」是否真的說不準 |
| B、C 級比例 | C 不算精確度，只追蹤比例與原因碼，找出最常缺的資料 |

判定正確率要和直接判定率一起看：只判最明顯的少數案件，正確率很高卻幫不了公所。

**表 21　系統升等條件**

| 條件 | 丙 → 乙 | 乙 → 甲 | 依據 |
|---|---|---|---|
| A 達標、A 未達標精確度（下界） | ≥ 95% | ≥ 95% | 歐盟誤判上限 5%〔27〕；該給的沒給和溢領一樣嚴重 |
| 判定正確率（下界） | ≥ 90% | ≥ 90% | 起始值；某類件數少時的整體下限 |
| 直接判定率 | ≥ 50% | 依丙等實測 B 級比例訂定，不低於 50% | 公所量能推導（表 22） |
| B 邊緣確認率（下界） | ≥ 80% | ≥ 80% | 起始值 |
| 連續達標場次 | — | ≥ 10 場 | 災害間差異大，GFM 12 事件僅 8 個達標〔90〕 |
| 政府審核 | — | 列入種植客觀證明或作業要點，含 A 未達標通知依據 | 救助辦法第 12 條〔7〕 |

起始值於丙等累積一年後依實測校正。連續場次自試辦起以鎖定版本計算，以每年 2–3 場可驗證的災害計約 3–5 年，甲等約自第 4–5 年起逐類別進入；若各場差異小，以累積精確度報告申請縮短。

**直接判定率的下限。** 以 2021 年 8 月豪雨規模（須現勘 315,266 筆、全國公所 30 日量能 18,564 人日），A 級書面每人日 200 筆、抽查 15 筆、B／C 每人日 c 筆，30 日內處理完須滿足 315,266 ×〔a÷200 ＋ 0.2a÷15 ＋（1−a）÷c〕≤ 18,564。上限則由損失分布決定：剛好受損 10%–30% 的田，模型再準也只能判 B，所以甲等目標依實測訂定。

**表 22　30 日內處理完所需的直接判定率**

| B、C 每人日 | 15 筆 | 12 筆 | 10 筆（取此保守值） |
|---|---|---|---|
| 直接判定率至少 | 16.1% | 37.6% | 50.3% |

**整體與類別、降等。** 件數多的類別會掩蓋件數少的：水稻 950 筆精確度 98%、香蕉 50 筆 70%，整體 96.6% 達標，香蕉卻每 10 筆錯 3 筆；分類別後香蕉留在丙等，不影響水稻。任一場後某類別任一種 A 的下界低於 95%，下一場即降一等、連續場次歸零；降等只會讓更多案件到場，不會產生錯誤的免勘或駁回（圖 17）。

<img src="charts/ui_office_eval_v8.png" width="72%">

**圖 17　公所端抽查、封存與評等。** 「香蕉 × 倒伏」本場抽出 1 件 A 未達標判錯，下界 93.6%，下一場降為乙等。資料為示意。

**表 23　以 95% 信心證明達標所需件數（Clopper–Pearson）**

| 要證明的比例 | 0 件判錯 | 1 件 | 3 件 | 10 件 |
|---|---|---|---|---|
| 80% | 14 | 22 | 37 | 82 |
| 90% | 29 | 46 | 76 | 167 |
| 95% | 59 | 93 | 153 | 336 |

丙、乙等每筆都現勘，一類別一場有 59 筆 A 全對即達 95%。甲等只有抽查是樣本，抽 20% 須 295 筆 A；不足時同類別、同版本跨場合併，或提高抽查比例。

**表 24　各判讀元件支撐 A 級的條件（未達時歸 B 或 C）**

| 元件 | 可支撐 A 級的條件 |
|---|---|
| 水稻判釋 | 準確率下界 ≥ 80%，鄉鎮面積偏差 ≤ ±20%；未達時作物以申報為準 |
| 其他作物 | 各作物準確率下界 ≥ 80% |
| 淹水 | 單一來源精確度下界 ≥ 95%，否則須雷達光學一致或有 App 照片；插秧期稻田歸 C |
| 倒伏 | Sentinel 只作佐證（≥ 80%）；1 米以下影像精確度下界 ≥ 95% |
| 埋沒、流失 | 精確度下界 ≥ 95%；未達時須 App 照片 |
| 損失模型／區間 | 每作物均方根誤差 ≤ 10 個百分點；P10–P90 覆蓋率在接受範圍（100 件時 72%–88%） |
| 魚塭 | 在養須放養申報；池水流失或潰堤須無收成申報，潰堤須高解析確認堤岸被淹 ≥ 80% |
| 竹林、網室／落果、寒害 | 衛星不支撐 A，派無人機／損失由天氣參數判定，衛星只證明種植 |
| 長時間對照 L1–L4 | 誠實申請誤標 ≤ 5%，否則只列原因碼 |

**校驗原則。** 誤差近似常態時，均方根誤差 10 個百分點、以下限 40% 判 A 達標的誤判機率約 2.3%（加拿大冰雹研究 8.2–12.3〔68〕）；A 未達標的 10% 距門檻僅 1σ，必須同時以實測精確度收緊，10% 只是起始值。區域總量（熱區圖、縣市提報）看偏差、個別案件看精確度，丙等時區域偏差在 ±20% 內熱區圖即可使用。現勘本身也有誤差，丙等抽部分案件由兩位承辦分別勘查，量出現勘一致率。驗證以整場災害留出。

**表 25　作業指標**

| 指標 | 目標 |
|---|---|
| 出件時間（雷達到站至分級完成） | 8 小時內 |
| 區域偏差（與官方統計比對） | ±20% 以內 |
| 可信度有效性 | 「高」的錯邊比例明顯低於「中」 |
| 查驗與重算 | 重算一致 100%；查驗失敗 0 件 |
| 現勘排序（乙等） | B、C 清單前 30% 涵蓋實際受損 ≥ 60% |

**(9) 資料權責、風險與發展路徑**

衛星影像與夜間燈光免費取得〔42〕〔91〕，福衛八號向授權經銷商訂購〔92〕〔93〕；救助申請、申報、照片與現勘結果含個資，本作品以公所或縣府「受託者」身分使用，地籍亦由試辦縣府申請〔94〕〔95〕。根本原則：系統只提供分級與存證，最終認定由公所做出。

**表 26　風險與對策**

| 風險 | 對策 |
|---|---|
| 誤判責任 | 甲等前只作參考；非「高」一律列 C；下界不足即降等 |
| A 未達標判錯無人發現 | 與 A 達標同抽 20%；通知附理由，可補件申訴 |
| A 未達標通知的法規依據 | 列為甲等政府審核的必要內容；勘查期內送達並給補件期限 |
| 承辦負擔、農民誤解 | 基準併入綠色環境給付申報；清單匯入農災 App；每畫面註明以公所認定為準 |
| 個資 | 受託處理；告知用途；不保存帳號 |
| 政府審核延後 | 停在乙等運作，熱區圖、排序、預填申請、補件提醒照常 |
| 小田、雲遮、斷網 | 無人機；雷達光學融合；離線清單；衛星備援回傳 |
| 偽造竄改、未介接 | 簽章與 Merkle 根離線查驗；以公所匯出檔銜接 |

<img src="charts/n7_roadmap_v8.png" width="86%">

**圖 18　準備期至甲等的發展路徑。**

## 四、預期效益：社會與商業價值

本作品不以減少公所人員為目的，而是減少超出量能的工作，把時間留給邊緣案件。丙等起可提供熱區圖與縣市提報，乙等起可排序現勘、預填申請與補件提醒，甲等起書面審核與提早結案。

**表 27　各方得到的價值（每場大型災害，甲等）**

| 對象 | 價值 | 指標 |
|---|---|---|
| 公所 | 回到量能以內；難案有更多時間 | 實地現勘 315,266 → 約 18.9 萬筆；需求 113% → 86%；每筆難案 32 → 40 分鐘 |
| 農民與養殖戶 | 結果更快；少跑、少冒險 | 約 6.7 萬件提早約 28 天完成審核 |
| 縣府與審計 | 抽查有依據、可重算 | 不當給付可避免約 2,615 萬至 7,845 萬元（推估） |
| 農業部、產業 | 田區級數據；自主衛星與無人機需求 | 福衛八號、九號進入農業行政 |

### 1. 公所人力與成本效益

以大肚區公所預算書推算每人日勘查成本約 4,773 元〔96〕〔97〕。一場大型災害須現勘 315,266 筆，每人日 15 筆需 21,018 人日，達全國農業課 30 日量能（18,564 人日）的 113%〔1〕〔98〕。甲等、直接判定率 50% 時，公所工作改為 A 級書面審核或通知、20% 抽查與 B／C 到場；B／C 每人日 12 筆的基準情境降至 16,026 人日（86%），即使只有 10 筆也恰在量能內（圖 19、表 28）。

**表 28　導入前後的公所勘查人力**

| 指標 | 現行 | B／C 15 筆 | 12 筆（基準） | 10 筆 |
|---|---|---|---|---|
| 勘查人日 | 21,018 | 13,399 | 16,026 | 18,653 |
| 占 30 日量能 | 113% | 72% | 86% | 100% |
| 釋出人日 | 不足 2,454 | 7,619 | 4,992 | 2,364 |

資料中心常設 37 人，年度總成本約 8,430 萬至 1.00 億元，人事占四至五成，雲端算力因坵塊化每年僅約 70 萬元；每場另計熱區商業雷達與無人機約 390 萬至 570 萬元〔99〕〔54〕〔100〕〔101〕〔46〕。合併公所人力後，每年三場大型災害時總成本較現行高 4%–10%（圖 20），五場以上才降低。因此本作品不主張省錢，而是以相近成本換取不超量能與災前證據；若改以每個公所增聘 1 人，每年約需 2.59 億元，本作品新增支出約為其二至四成。

<img src="charts/fig8_workload_v8.png" width="47%"> <img src="charts/fig9_total_v7.png" width="47%">

**圖 19　一場大型災害的公所勘查人日（左）；圖 20　含公所人力的年度總成本，每年三場（右）。**

直接判定的案件每件約縮短 28 天（58 → 30 天）〔1〕；直接判定率 30%、50%、70% 時全體平均結案天數為 49.6、46.0、42.4 天。直接判定率僅 30% 且 B／C 每人日 12 筆時公所仍達 108%，這也是乙等門檻訂在 50% 的原因。若田區證據使 2.615 億元不當給付中 10%–30% 被正確複核，單場可避免約 2,615 萬至 7,845 萬元（推估）。

### 2. 社會效益

**表 29　社會效益**

| 效益 | 指標或依據 |
|---|---|
| 救助更快 | 直接判定案件提早約 28 天；全體平均提早 5.4–12.6 天〔1〕 |
| 少跑、少冒險 | 預填申請、QR 送件；路不通不必進田；通知與補件都附理由 |
| 偏鄉公平與安全 | 人到不了的田也有證據；山區先以衛星與無人機處理〔9〕〔8〕 |
| 爭議減少 | 影像對照與可重算紀錄；溪州初勘未通過率 12.7%〔102〕 |
| 漁業可證明 | 魚塭在養證據；丹娜絲漁產損失約 7.7 億元〔3〕 |
| 財政紀律與承辦保障 | 救助經費六年五年超支〔1〕〔103〕；書面審核有可查驗證據〔16〕 |

2026 年 3 月救助額度上調，香菇及木耳由每公頃 7.15 萬元提高至 112.5 萬元〔104〕，每筆認定錯誤的代價隨之提高。

### 3. 商業模式與推廣

價值來自替代增聘（每年約 2.59 億元）、減少加班（每場最多約 499 萬元）、減少不當給付與提早結案；建議以資料中心營運成本約 0.84–1.00 億元為基礎版年費底價。救助金額與資格不因版本改變〔105〕。

**表 30　版本與收益模式**

| 版本 | 採購者 | 內容 |
|---|---|---|
| 基礎版 | 農業部或縣市政府統一採購，公所與農民免費 | 災前基準、分級、存證報告、預填申請、工作台、報表 |
| 進階版 | 縣市政府、農會、產險公司 | 異常提醒、魚塭在養證明、無人機、定位樁、田區資料授權、報告查驗介面 |

推廣方向：公所端擴展至全國 368 個鄉鎮市區〔1〕；漁業端延伸至約 4.3 萬公頃養殖魚塭〔107〕；保險端協助開發田區級保單（氣象參數型目前僅 29 品項）〔106〕；海外結合福衛影像延伸中美洲作物監測經驗〔108〕。甲等並經公告認可後可發展為「衛星災損參數」；試辦期間可送數位發展部 AI 評測中心作第三方評測〔109〕。福衛八號、九號影像直接進入農業行政，為自主衛星創造穩定需求〔39〕〔38〕。

## 名詞解釋

**表 31　本構想書用語**

| 用語 | 意思 |
|---|---|
| A 達標／A 未達標 | 證據完整，損失區間整個在 20% 以上（下限 ≥ 40%）或以下（上限 ≤ 10%），可直接判定 |
| B 邊緣／C 缺失 | 證據完整但區間跨過 20%，公所到場／五項檢核任一未過，須補資料 |
| 丙／乙／甲等 | 系統等級：收集、結果不交公所／作參考／A 級參與判定；逐「作物 × 災害類型」評定 |
| 可信度等級 | 證據品質的高、中、低，不是機率；只有「高」進入 A、B 判斷 |
| 損失區間 | 每塊田損失率的第 10、50、90 百分位 |
| 精確度／準確率 | 判為某類者中確實如此的比例／全部案件判對的比例（只用於作物判釋） |
| 直接判定率 | A 級占全部申請的比例 |
| 95% 單側信賴下界 | 依樣本有 95% 把握真實值至少這麼高；所有達標判斷都看下界 |
| 覆蓋率 | 現勘損失率落在系統損失區間內的比例 |
| 均方根誤差／偏差 | 損失率與現勘差多少個百分點／整體多估或少估，用於區域總量 |

## 參考資料

1. [監察院調查報告：農業天然災害現金救助撥款逾期等問題（依審計部 110 年度決算審核報告）](https://cybsbox.cy.gov.tw/CYBSBoxSSL/edoc/download/61399)
2. [農業部：近 10 年農業天然災害損失統計](https://www.moa.gov.tw/ws.php?id=2513662)
3. [農業部統計處：丹娜絲颱風及 0708 豪雨農業災情報告](https://www.moa.gov.tw/theme_data.php?theme=news&sub_theme=agri&id=9818)
4. 農業部統計處災情報告：[樺加沙](https://www.moa.gov.tw/redirect_files.php?id=58194)、[楊柳](https://www.moa.gov.tw/theme_data.php?id=9863&sub_theme=agri&theme=news)、[0728 豪雨](https://www.moa.gov.tw/redirect_files.php?id=57397)；[鳳凰（工商時報）](https://wantrich.chinatimes.com/news/20251114900646-420501)
5. [經濟日報：丹娜絲、0708 豪雨救助經費 71.23 億元與撥付進度](https://money.udn.com/money/story/7307/9066040)
6. [農產業天然災害救助作業要點（農業部主管法規共用系統，2025/3/10 修正）](https://law.moa.gov.tw/LawContent.aspx?id=GL000268)
7. [農業天然災害救助辦法（現行條文）](https://6laws.net/6law/law3/農業天然災害救助辦法.htm)
8. [公視：古坑竹林勘災不易被判不合格](https://news.pts.org.tw/article/639374)
9. [iThome：雲林農損勘查、審計室衛星植生指標](https://www.ithome.com.tw/news/179527)
10. [公視（2025）：丹娜絲停電、增氧機停擺與發電機補助](https://news.pts.org.tw/article/761566)
11. [農業部：農災 App、天氣參數與農地覆蓋物資料庫](https://www.moa.gov.tw/ws.php?id=2517236)
12. [中央社：凱米颱風農業損失](https://www.cna.com.tw/news/aipl/202407310233.aspx)
13. [新頭殼：山陀兒颱風農業損失](https://newtalk.tw/news/view/2024-10-07/939291)
14. [2025 年 5 月農業部公告：種植客觀證明免勘與抽樣勘查 20%](https://files.chcg.gov.tw/files/71_20250502104232659_農業部　公告.pdf)
15. [農業部 2025 年 4 月 18 日農糧字第 1141108673 號公告：種植客觀證明文件](https://gazette.nat.gov.tw/EG_FileManager/eguploadpub/eg031071/ch07/type3/gov88/num27/Eg.pdf)
16. [中央社（2018-10-11）：彰化竹塘裸地申請颱風災損救助，公所承辦判圖利](https://www.cna.com.tw/news/asoc/201810110391.aspx)
17. [University of Washington (2021). Zhao et al., deepfake geography: how AI falsifies satellite images. Cartography and Geographic Information Science](https://www.washington.edu/news/2021/04/21/a-growing-problem-of-deepfake-geography-how-ai-falsifies-satellite-images/)
18. [理律法律事務所（2024）：電子簽章法修正重點](https://www.leeandli.com/TW/Newsletters/7256.htm)
19. [科技新報（2025-12-23）：人工智慧基本法三讀通過](https://technews.tw/2025/12/23/artificial-intelligence-basic-law/)
20. [農業部：災害性與災損天氣參數](https://www.moa.gov.tw/ws.php?id=2513431)
21. [農業部：農災 App 多點勘災與本機調查專案](https://www.moa.gov.tw/ws.php?id=2517321)
22. [農業部電子報：農試所 UAV 災損判釋](https://www.moa.gov.tw/office_epaper/epaper/infoexplorer/online/52/content_1.html)
23. [愛爾蘭農業部：AMS](https://www.gov.ie/ga/an-roinn-talmha%C3%ADochta-bia-agus-mara/foilseachain/area-monitoring-system-ams)
24. [Commission Implementing Regulation (EU) 2022/1173（IACS 與面積監測系統，第 2、5、7、10、11 條）](https://eur-lex.europa.eu/eli/reg_impl/2022/1173/oj/eng/pdf)
25. [AMA (2024). Austria's area monitoring for CAP（ESA Φ-lab 簡報）](https://philab.esa.int/wp-content/uploads/sites/3/2024/12/20241127_ESA_EO_Comm_Austrias_area_monitoring_for_CAP.pdf)
26. [ESPI: Impact case studies – AGEA](https://space-economy.esa.int/documents/ESPI%20Impact%20Case%20Studies%20-%20AGEA_6a3a9e1358da1.pdf)
27. [European Court of Auditors (2020). Special report 04/2020: Using new imaging technologies to monitor the Common Agricultural Policy](https://op.europa.eu/webpub/eca/special-reports/new-tech-in-agri-monitoring-4-2020/en/index.html)
28. [Agriland：DAFM 表示逾 90% 農民回覆衛星監測通知（2023）](https://agriland.ie/farming-news/dafm-over-90-of-farmers-reply-to-satellite-inspection-notices)
29. [Planet / Sentinel Hub Area Monitoring：Geotagged Photo Application 說明](https://docs.planet.com/data/area-monitoring/applications/geotagged-photo-application/)
30. [Copernicus Data Space Ecosystem (2023). CAP monitoring at national scale in Slovenia based on Copernicus data](https://dataspace.copernicus.eu/node/791)
31. [European Commission JRC：Checks by Monitoring — Overview of the marker detection tool](https://jrc-cbm.readthedocs.io/en/latest/md_overview.html)
32. [新頭殼：嘉義縣丹娜絲災損統計](https://newtalk.tw/news/view/2025-07-08/980593)
33. 天相星團隊（2026）。團隊原型（團隊demo）設計資料：花蓮光復影像比對、土地建檔、作物查驗、R1–R5 作業及模型設計。團隊內部專案文件。
34. [Copernicus SentiWiki：Sentinel-1 產品、空間解析度與像素間距](https://sentiwiki.copernicus.eu/web/s1-products)
35. [Copernicus (2026). Sentinel-1D user data opening and future plans](https://dataspace.copernicus.eu/node/3176)
36. [Planet: Sentinel-2 L1C & L2A](https://docs.planet.com/data/public-data/copernicus/sentinel-2)
37. [工商時報（2026）：福衛八號對臺一日三次取像](https://www.ctee.com.tw/news/20260211701988-431401)
38. [公視（2026）：福衛八號 2031 年前 8 顆升空](https://news.pts.org.tw/article/808282)
39. [聯合報：福衛九號雷達衛星發射規劃](https://udn.com/news/story/7266/9227232)
40. [Airbus：Pléiades Neo](https://space-solutions.airbus.com/imagery/our-optical-and-radar-satellite-imagery/pleiades-neo/)
41. [UP42：ICEYE 取像模式與規格](https://docs.up42.com/data/iceye)
42. [NASA Black Marble product](https://viirsland.gsfc.nasa.gov/Products/NASA/BlackMarble.html)
43. [臺中市政府地政局：e-GNSS 即時動態定位應用研究](https://rdnet.taichung.gov.tw/media/428383/61201875458.pdf)
44. [iThome（2024）：數發部非同步軌道衛星備援站點建置進度](https://www.ithome.com.tw/news/163833)
45. [學位論文：衛星影像淹水辨識](https://www.airitilibrary.com/Publication/Index/U0002-2707201110231500)
46. [PRO360：空拍攝影價格](https://www.pro360.com.tw/price/aerial_photography)
47. [DJI：Phantom 4 RTK specs](https://dji.com/phantom-4-rtk/info)
48. [STAC: SpatioTemporal Asset Catalogs](https://stacspec.org/en)
49. [W3C (2013). PROV-Overview](https://www.w3.org/TR/prov-overview/)
50. [Adams et al. (2001). RFC 3161: Internet X.509 PKI Time-Stamp Protocol. IETF](https://www.rfc-editor.org/rfc/rfc3161)
51. [中央社（2021）：台南虱目魚寒害現金救助](https://www.cna.com.tw/news/aloc/202101140060.aspx)
52. [Mullissa et al. (2021). Sentinel-1 SAR backscatter analysis ready data preparation in Google Earth Engine. Remote Sensing 13(10)](https://doaj.org/article/103f5e1094994facba05434cdd914e81)
53. [Pasquarella et al. (2023). Cloud Score+](https://developers.google.com/earth-engine/datasets/catalog/GOOGLE_CLOUD_SCORE_PLUS_V1_S2_HARMONIZED)
54. [Google Cloud：Accelerator-optimized machine pricing](https://cloud.google.com/products/compute/pricing/accelerator-optimized?hl=en)
55. [AWS S3 價格整理（2026）](https://upstash.com/blog/aws-s3-pricing-explained-2026)
56. [Rußwurm et al. (2020). BreizhCrops: A time series dataset for crop type mapping](https://arxiv.org/abs/1905.11893)
57. [Tseng, G., et al. (2023). Lightweight, Pre-trained Transformers for Remote Sensing Timeseries（Presto）](https://arxiv.org/abs/2304.14065)
58. [Mapping of paddy field by Sentinel-1 SAR images and cadastre data. International Journal of Remote Sensing 46(12), 2025](https://scholars.ncu.edu.tw/en/publications/mapping-of-paddy-field-by-sentinel-1-sar-images-and-cadastre-data/)
59. [Bonafilia et al. (2020). Sen1Floods11. CVPR Workshops](https://openaccess.thecvf.com/content_CVPRW_2020/papers/w11/Bonafilia_Sen1Floods11_A_Georeferenced_Dataset_to_Train_and_Test_Deep_Learning_CVPRW_2020_paper.pdf)
60. [Jakubik et al. (2023). Foundation models for generalist geospatial artificial intelligence](https://arxiv.org/abs/2310.18660)
61. [Ajadi et al. (2020). Landscape-scale crop lodging assessment using SAR images. Remote Sensing 12](https://mdpi-res.com/d_attachment/remotesensing/remotesensing-12-03885/article_deploy/remotesensing-12-03885.pdf)
62. [Chauhan et al. (2020). Understanding wheat lodging using multi-temporal Sentinel-1 and Sentinel-2 data. RSE 243](https://research.utwente.nl/en/publications/understanding-wheat-lodging-using-multi-temporal-sentinel-1-and-s/)
63. [Wu, W., et al. (2019). Cloud-based typhoon-derived paddy rice flooding and lodging detection using multi-temporal Sentinel-1&2. Frontiers of Earth Science 13(4), 682–694](https://agris.fao.org/search/en/records/65dfe0c10f3e94b9e5dd2ea3)
64. [Winter wheat lodging area extraction using deep learning with GaoFen-2 satellite imagery. Remote Sensing (2022)](https://doaj.org/article/2008f5ddad924901921c13d4096d20b2)
65. [Meneses & Blanco (2022). Rapid mapping of damages due to Typhoon Rai using Sentinel-1](https://philsa.gov.ph/journal/rapid-mapping-and-assessment-of-damages-due-to-typhoon-rai-using-sentinel-1-synthetic-aperture-radar-data/)
66. [Ke et al. (2017). LightGBM. NeurIPS](https://proceedings.neurips.cc/paper/2017/file/6449f44a102fde848669bdd9eb6b76fa-Paper.pdf)
67. [Romano, Patterson & Candès (2019). Conformalized quantile regression. arXiv:1905.03222](https://arxiv.org/abs/1905.03222)
68. [Ha et al. (2022). Quantifying hail damage in crops using Sentinel-2 imagery. Remote Sensing 14(4), 951](https://mdpi-res.com/d_attachment/remotesensing/remotesensing-14-00951/article_deploy/remotesensing-14-00951.pdf)
69. [Ottinger et al. (2022). Mapping aquaculture ponds for the coastal zone of Asia. Remote Sensing 14(1)](https://opus.bibliothek.uni-wuerzburg.de/files/25220/remotesensing-14-00153.pdf)
70. [Angelopoulos et al. (2021). Learn then Test: Calibrating predictive algorithms to achieve risk control](https://arxiv.org/abs/2110.01052)
71. [Szwarcman et al. (2024). Prithvi-EO-2.0: A versatile multi-temporal foundation model for Earth observation applications](https://arxiv.org/abs/2412.02732)
72. [U-Net for mapping banana crops using CBERS-4A imagery. ISPRS Archives XLIX-B3-2026, 907](https://isprs-archives.copernicus.org/articles/XLIX-B3-2026/907/2026/isprs-archives-XLIX-B3-2026-907-2026.pdf)
73. [Copernicus Data Space Ecosystem (2025). Re-tracing and checksum recalculation for Sentinel products（MD5、BLAKE3）](https://dataspace.copernicus.eu/node/2490)
74. 天相星團隊（2026）。標準作業流程原型：sop_pipeline.py、verify.py、tamper_tests.py、credibility_eval.py、longterm_check.py 與測試結果。專案內部文件。
75. [C2PA (2025). Content Credentials: C2PA Technical Specification 2.2](https://spec.c2pa.org/specifications/specifications/2.2/specs/C2PA_Specification)
76. [Biswas & Blanco-Medina (2021). State of the art: image hashing. arXiv:2108.11794](https://arxiv.org/abs/2108.11794)
77. [政府憑證管理中心：政府機關公開金鑰基礎建設（GPKI）憑證及憑證廢止清冊格式剖繪](https://grca.nat.gov.tw/download/modify-GPKI_Cert_and_CRL_Profiles_v2.4.pdf)
78. [EUSPA (2025). Transforming agricultural monitoring: space-based smart tech（捷克 SZIF 地理標記照片試辦）](https://www.euspa.europa.eu/newsroom-events/success-stories/transforming-agricultural-monitoring-space-based-smart-tech)
79. [Microsoft Planetary Computer：Sentinel-1 RTC 與 Sentinel-2 L2A 資料集（Contains modified Copernicus Sentinel data 2024–2025）](https://planetarycomputer.microsoft.com/catalog)
80. 天相星團隊（2026）。《衛星測試示範：丹娜絲衛星影像分析報告》。專案內部文件，含 Sentinel-1／Sentinel-2 處理程式與結果圖。
81. 天相星團隊（2026）。《衛星測試示範：作物判釋測試》。專案內部文件，含 fetch_s1_year.py、crop_classify_v2.py、crop_figures.py。
82. 天相星團隊（2026）。《衛星測試示範：程式報告與解析》。專案內部文件，含 skyaide_demo.py 與 run_multi_seeds.py 測試結果。
83. [Parrot ANAFI Ai 技術規格與測繪功能（48 MP、digitally signed pictures、30 m 高 GSD 0.46 cm）](https://www.parrot.com/us/drones/anafi-ai/technical-documentation/photogrammetry)
84. [iThome：行政院要求公務機關原則上禁止採購及使用大陸廠牌資通訊產品](https://www.ithome.com.tw/news/159731)
85. [數位時代（2024）：民航局遙控無人機檢驗、註冊與資安檢測規劃](https://www.bnext.com.tw/article/79949/drone-regulations-revision)
86. [陳清福（2020）：衛星定位技術應用於潛在大規模崩塌之地表位移研究](https://etds.lib.ntnu.edu.tw/thesis/detail/3e4c7c8580d9657c296743fe6a8cdfbe)
87. [INSIDE（2024）：台灣大哥大完成國內首次手機直連衛星測試](https://www.inside.com.tw/article/36904-taiwan-mobile-validates-space-base-station-marks-taiwans-first-successful-direct-satellite-to-phone-test)
88. [European Space Imaging (2021). €20.5 million agriculture framework contract by European Commission](https://www.euspaceimaging.com/european-space-imaging-awarded-e20-5-million-agriculture-framework-contract-by-european-commission/)
89. [Clopper & Pearson (1934). The use of confidence or fiducial limits illustrated in the case of the binomial. Biometrika 26(4)](https://doi.org/10.1093/biomet/26.4.404)
90. [Copernicus EMS (2024). Global Flood Monitoring: Annual Product and Service Quality Assessment Report 2023](https://civil-protection-knowledge-network.europa.eu/system/files/2024-12/global-flood-monitoring-annual-product-and-service-quality-assessment-report-2023.pdf)
91. [European Commission: Copernicus Sentinel data licence](https://ads.atmosphere.copernicus.eu/licences/ec-sentinel)
92. [中央社：福衛八號第 2 顆明年第 1 季升空、三家經銷商（2026/10/15）](https://www.cna.com.tw/news/ait/202610150339.aspx)
93. [國家太空中心：福衛影像經銷服務](https://www.tasa.org.tw/zh-TW/service-and-tech/formosat-images/purchase)
94. [個人資料保護法全文（國發會）](https://ws.ndc.gov.tw/001/administrator/30/laws/4/1e71c611-d58c-4ff4-8d1e-405987f5a5e4.pdf)
95. [國土測繪中心：地籍圖檔申請書](https://ws.moi.gov.tw/001/Upload/OldFile_NLSC/uploadfile/1070301/1070301%E6%B5%81%E9%80%9A%E4%BD%9C%E6%A5%AD%E8%A6%81%E9%BB%9E_%E9%99%84%E8%A1%A8%E5%85%AD_%E5%9C%B0%E7%B1%8D%E5%9C%96%E6%AA%94%E7%94%B3%E8%AB%8B%E6%9B%B8.pdf)
96. [臺中市大肚區公所 115 年度單位預算書](https://www.dadu.taichung.gov.tw/media/1268844/02070臺中市大肚區公所單位預算-上傳官網版-1-71-修.pdf)
97. [行政院修正國內出差旅費報支要點對照表（2025/1/1 生效）](https://tsps.chc.edu.tw/storage/074691/open_files/11會計室/法令規章/國內出差旅費/1130523行政院修正國內出差旅費報支要點部分規定(1140101生效)/1130523國內出差旅費部分規定修正對照%20表.pdf)
98. [臺中市豐原區公所：各機關加班費支給辦法與實務案例](https://www.hfengyuan.taichung.gov.tw/media/1113520/各機關加班費支給辦法與實務案例.pdf)
99. [1111 人力銀行（2026）：行業薪資差距](https://www.1111.com.tw/news/jobns/164013)
100. [LAND INFO（2026）：Satellite imagery pricing](https://landinfo.com/satellite-imagery-pricing.html)
101. [SkyFi (2025). Pricing, August 2025（ICEYE SAR 與 30–50 公分光學影像單價）](https://skyfi.com/files/SkyFi_Pricing_August_2025.pdf)
102. [工商時報：溪州鄉農損勘查爭議](https://www.ctee.com.tw/news/20250905701005-431401)
103. [監察院調查報告：農業部農特基金及農再基金管理營運不當案（2025/9/2）](https://cybsbox.cy.gov.tw/CYBSBoxSSL/edoc/download/72762)
104. [農業部：2026 年 3 月修正農業天然災害救助辦法](https://www.moa.gov.tw/ws.php?id=2517258)
105. [農業保險法](https://6laws.net/6law/law/農業保險法.htm)
106. [中央社：巴威颱風氣象參數型保單理賠](https://www.cna.com.tw/postwrite/chi/438842)
107. [農業部（2017）：農業及農地資源盤查成果](https://www.moa.gov.tw/ws.php?id=2508388)
108. [Taiwan News：福衛五號中美洲香蕉病害監測](https://www.taiwannews.com.tw/news/5954502)
109. [科技新報（2023-12-07）：數位部 AI 產品與系統評測中心啟動，十項評測項目](https://technews.tw/2023/12/07/ai-product-and-system-evaluation-center-launch/)
110. [臺北市政府訴願決定書：低收入戶資格審核案（依財稅資料認定、申請人不服申復）](https://laws.gov.taipei/law/LawDecision/ContentPrint?id=701-001)
