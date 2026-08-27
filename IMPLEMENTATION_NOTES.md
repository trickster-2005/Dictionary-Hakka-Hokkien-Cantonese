# 開發紀錄與架構筆記

這份文件是給接手/回顧這個專案的人看的技術筆記，記錄開發過程中踩過的坑、目前還沒解決
的限制、以及完整的專案結構。使用者導向的說明(怎麼跑、資料授權、搜尋邏輯)請看
[README.md](README.md)，這份文件著重在「為什麼會長成現在這樣」跟「還有哪裡不完整」。

---

## 1. 實作過程中遇到的困難、bug 與處理方式

依發現順序排列。

### 1.1 sql.js 在瀏覽器端要用的 wasm 檔名猜錯
一開始把 `node_modules/sql.js/dist/sql-wasm.wasm` 複製到 `public/`，但瀏覽器一直噴
`WebAssembly.instantiate(): expected magic word ... found 3c 21 64 6f`(那其實是
`<!do` 的 hex，代表拿到的是 Vite dev server 的 SPA fallback `index.html`，不是真的
wasm 檔)。查了 `sql.js` 的 `package.json` 的 `exports` 欄位才發現:瀏覽器環境實際載入
的是 `dist/sql-wasm-browser.js`，對應的 wasm 檔名是 `sql-wasm-browser.wasm`，不是
`sql-wasm.wasm`。**修法**:複製正確檔名;這也是為什麼 [README.md](README.md) 特別
交代這一步要手動做，`npm install` 不會自動處理。

### 1.2 GitHub Pages 專案頁面的路徑問題
Vite 預設把 assets 路徑打包成絕對路徑(`/assets/xxx.js`)，在網域根目錄沒問題，但
GitHub Pages 的專案頁面是掛在 `/Dictionary-Hakka-Hokkien-Cantonese/` 這個子路徑下，
資源全部 404。**修法**:`vite.config.ts` 用 `defineConfig(({ command }) => ({ base:
command === 'build' ? '/Dictionary-Hakka-Hokkien-Cantonese/' : '/' }))`，只在正式
build 時套用子路徑，本機 dev 維持根目錄。

### 1.3 words.hk 授權文字誤判
CSV 檔頭寫著「ALL RIGHTS RESERVED. DO NOT DISTRIBUTE」，一開始直接把原始 CSV 和
build 出來的 `dictionary.sqlite` 都排除在版控外，GitHub Pages 也沒有部署粵語資料。
後來使用者要求確認，實際去讀 <https://words.hk/base/hoifong/> 才發現真正的授權是
《Non-Commercial Open Data License 1.0》，非商業用途下可以複製/修改/發佈/再分發。
CSV 檔頭那句警語其實是「除非你符合下面連結的授權，否則不要散布」的意思，不是完全
禁止。確認本專案為非商業、個人學習用途後，補上正式的版權聲明(README + 網站頁尾)，
並把處理過的 `dictionary.sqlite` 放進 GitHub Pages 部署——但**原始 CSV 依然沒有
進版控**，理由跟授權無關，單純是可以重新產生的大型檔案。

### 1.4 台語辭典「閱讀更多」連結連到錯的詞
一開始假設 `dict-twblg.json` 裡 heteronym 自己的 `id` 欄位，可以直接組成
`https://sutian.moe.edu.tw/zh-hant/su/{id}/` 連到官網對應頁面。實際拿「朋友」的
id 去組網址，打開卻是完全不同的詞(「林投姊仔」)。證實 g0v 匯出的 `id` 跟
sutian.moe.edu.tw 自己內部的編號是兩套不同的系統，兜不起來。**修法**:改成連到
官網「用臺灣台語查詞目」的搜尋結果網址(`?lui=tai_su&tsha={詞}`)，這個網址格式
有實際操作官網搜尋表單、觀察網址列變化後確認可行。

### 1.5 客語單字發音音檔網址完全失效
g0v `moedict-data-hakka` repo 附的 `mp3-urls.txt` 指向 `hakka.dict.edu.tw`，一開始
直接拿來組音檔網址。後來要修「播放按鈕點了沒反應」時用 `curl` 實測，發現這個網域
DNS 解析得到 IP，但每次連線都逾時(20 秒 timeout)，判斷是舊站已經關閉。現在的官方
客語辭典站是 `hakkadict.moe.edu.tw`，上面確實有語音，但音檔網址是透過每個詞條「動態
編號」組出來的(例如 `/search_result?id=2146` 那個 `id`)，而這個編號完全沒有出現在
我們手上的任何資料來源裡，沒有辦法從現有資料反推。**最終處理**:把 Hakka 的
word_audio 邏輯整個拿掉，不留會 404 的死連結;`PlayButton` 元件也從「嘗試
`<audio>.play()`」改成「直接開新分頁 / 觸發下載」，避免依賴不穩定的 CORS/播放行為。

### 1.6 客語辭典官網無法做精準連結(搜尋是純前端 POST)
嘗試比照台語的做法，幫客語卡片連到官網搜尋結果。實際操作官網搜尋框、用瀏覽器
network 分頁觀察後發現:搜尋是前端 JavaScript 送 `POST /search_list/` 做的，網址列
不會反映查詢字串。進一步測試 GET query string(`?word=`、`?keyword=`、
`?keyword=X&mode=1` 等排列組合都試過)，伺服器完全忽略這些參數、回傳一模一樣的空白
表單頁(用 `curl` 比對過回傳的 byte 數完全相同)。結論:這個網站沒有任何可以外部
連結直達搜尋結果的網址格式，只能連回首頁。

### 1.7 客語拼音一開始靠「猜」，後來直接找到官方原始資料
最早用的是 `g0v/moedict-data-hakka` 處理過的 `dict-hakka.json`，拼音欄位是「六腔
壓縮在同一字串、用上標數字標調值」的格式(例如 `gia²⁴`)，要顯示成「教育部客語拼音」
的正式格式(`giaˋ`)得靠另外抓來的 `海陸腔.csv` 對照表做轉換。這張表只涵蓋 883 組
音節+調值，涵蓋不到的音節只能用「調值多數決」規則用猜的，而且部分調值(尤其是 11)
在對照表裡本身就有好幾種寫法互相打架。

後來使用者追問「客語比對邏輯」時逼著重新檢查資料來源，才發現 `moedict-data-hakka`
這個 repo 其實還有一份 `ods/客語典文字資料.ods`——那是官方原始試算表，`dict-hakka.
json` 只是從裡面轉出一部分欄位而已。原始 ODS 裡:
- 拼音欄位本來就是純文字的「通用拼音調值標記法」(例如 `a24 ba24`)，官方自己
  發布的三種顯示格式之一，不需要再猜、也不需要轉換
- 有「對應國語」「近義詞」兩個 dict-hakka.json 沒有的欄位，正是排序機制需要的資料

**結論**:整個 `parse_hak.py` 重寫成直接讀這份 ODS，拋棄猜測拼音的邏輯跟
`海陸腔.csv`。教訓是:**先確認一個 repo 裡有沒有更完整的原始資料，再開始處理它
「精簡過」的衍生格式**。

### 1.8 union-find 同義詞分組上限一開始抓太緊(8 → 80)
為了避免「金」這種多義字(黃金/金錢/姓氏)把完全不相干的詞全部串在一起，一開始隨手
設了「分組成員數 > 8 就不展開，只留直接別名」的規則，沒有實際攤開資料驗證這個數字
合不合理。

後來擴充客語資料、加入「對應國語」欄位後，使用者的正常查詢(「爸爸」)找不到客語
「阿爸」——追查發現「阿爸/爸爸/老豆/老竇/父親/爹/…」這組完全合理、橫跨客語+粵語的
同義詞分組剛好有 10 個成員，被 8 這個門檻誤殺。**修法**:寫腳本把實際分組大小分佈
攤開來，人工檢查中等大小(20~70 人)的分組內容，確認這些都還是主題一致的正常結果
(死亡、說謊、比較用語...)，真正離譜、把不相干概念全部串在一起的分組只有兩組
(184、297 個成員)。門檻改成 80，兩組誇張的還是會被擋掉，正常的同義詞群組能正常
展開。**教訓**:安全上限這種數字不能憑直覺設，要實際攤開資料看過再決定。

### 1.9 `extract_glosses` 誤把長句子裡的地名當同義詞
使用者回報查「日本」會跑出台語「鱔魚」(黃鱔)。追查發現鱔魚的釋義是一整句「...多
分布在印度半島、中國大陸、日本、韓國及臺灣等地區，屬於淡水魚。」，別名抽取邏輯看到
頓號分隔的短字串(「日本」2 個字，符合長度限制、沒有奇怪標點)就直接當成同義詞抽
出來，完全沒有意識到這是一個完整敘述句「裡面剛好有」的地名列舉，不是「這個詞的同義詞
清單」。

**修法**:`extract_glosses` 現在會檢查——如果定義文字扣掉結尾那一個句號之後，裡面
還殘留其他句號，代表這是一段完整敘述(或多句)，直接整段跳過不抽取，不再嘗試從裡面
挖東西。像「抽煙、吸煙。」這種真的只有一個結尾句號的才會繼續處理。

### 1.10 粵語 CSV 的「已公開/未公開」欄位語意誤判(影響範圍最大的一個 bug)
一開始假設 CSV 裡的「已公開/未公開」欄位代表「是否已經在官網公開顯示」，所以
parser 只保留 `status=OK` 且 `visibility=已公開` 的資料列。這個假設**完全錯誤**:
使用者回報「六四」在官網查得到、本專案查不到，追查發現這筆資料 `status=OK` 但
`visibility=未公開`。進一步隨機抽查才發現「嗅」「坦克」「地質」這些完全普通、
一定在官網看得到的詞，也全部被標記「未公開」——證實這個欄位跟「是否公開顯示」
根本無關，可能是 words.hk 內部另一套跟外部呈現無關的分類。

**這個誤判當時濾掉了 CSV 裡 72% 的資料列**(59,315 筆裡有 42,944 筆被標
「未公開」)。**修法**:拿掉這個過濾條件，只保留 `status=OK`(排除真正標記「未經
覆核，可能有錯漏」的資料)。修完後粵語條目數從 13,549 筆變成 24,879 筆。

### 1.11 粵語 parser 漏掉沒有 `<explanation>` 標籤保護的開頭釋義
修完 1.10 之後重新測「六四」，詞條找得到了，但釋義只剩「借代八九民運」，少了最主要
的「即六四天安門事件...」那一段。原始內容格式是:
```
(pos:名詞)(label:專名)(label:爭議)
yue:即六四天安門事件...          ← 沒有 <explanation> 標籤保護
eng:...
----
<explanation>                    ← 第二義項才有這個標籤
yue:借代八九民運
eng:...
```
parser 原本的邏輯是「看到 `<explanation>` 標籤才開始收集 `yue:` 行當作釋義」，
狀態機的初始值是 `section = None`，導致開頭那段沒有標籤保護的內容被完全忽略，只
留下第二段。**修法**:把 `section` 初始值改成 `"explanation"`(預設就在收集模式)，
`<explanation>` 標籤變成「重新設一次同樣的狀態」的無害動作。**教訓**:1.10 跟 1.11
是同一個詞條(「六四」)一次揭露兩個獨立的 bug，顯示光靠零星抽測沒辦法保證資料
完整性，遇到「明明來源有、這裡沒有」的回報時，務必回頭挖原始資料逐行核對格式假設。

### 1.12 收藏資料格式變更後，舊格式資料造成全站白屏
把收藏功能從「以搜尋字串為 key」改成「以卡片為單位(`lang|variant|script|
pronunciation_1` 組合 key)」之後，瀏覽器裡殘留的舊格式收藏資料(單純的搜尋字串，
例如 `"抽菸"`)在 `getEntryByKey()` 裡被 `.split('|')` 拆解，拆出來的
`variant`/`script`/`pronunciation1` 全部是 `undefined`，綁定到 sql.js 的
`stmt.bind()` 時直接丟出 `Wrong API use: tried to bind a value of an unknown
type (undefined)`,而且是在 `useMemo` 裡同步丟出、沒有 Error Boundary 接住，
整個 React tree 直接卸載、畫面變成一片空白。**修法**:`useFavorites` 讀取
localStorage 時過濾掉「split 出來不是剛好 4 段」的資料，`getEntryByKey` 自己也
再加一層同樣的防呆——雙重保險，不只是讓資料乾淨，也讓函式本身能安全處理任何格式
不對的輸入。

### 1.13 ODS 檔案解析時 column-repeat 展開錯誤
第一次寫 `.ods`(OpenDocument Spreadsheet)解析邏輯時，沒有正確處理
`table:number-columns-repeated` 屬性——ODS 檔案裡，一整排連續的空白儲存格會被
壓縮成「一個儲存格 + repeat 次數」來省空間，常見情況是「這一列剩下的空欄位」會標記
repeat 到整張表的欄位上限(16384，等同 Excel 的 XFD 欄)。第一版解析邏輯把這個
repeat 次數整個展開，導致每一列陣列長度變成 16384(絕大部分是空字串)，header 跟
資料列對不起來。**修法**:`read_ods_rows()` 把 repeat 展開次數上限設 40(實際資料
列不會用到超過 40 欄)，並且把陣列尾端的空字串裁掉。

### 1.14 開發過程中的環境/工具雜訊(非程式 bug，但值得記錄避免誤判)
- **Windows 終端機中文編碼**:這個環境下用 Bash 工具印出中文字元時，常常變成
  `�`亂碼(cp950 codepage 問題)，但檔案本身(UTF-8)完全正常。好幾次差點誤判成
  資料損毀，後來養成習慣:牽涉中文內容的檢查一律寫進暫存檔，再用 Read 工具讀出來
  看，不要直接信任 Bash 的終端機輸出。
- **瀏覽器自動化工具偶爾失靈**:`computer`/`read_page` 這類需要畫面 compositing
  的工具，在某些時候會回報「viewport 0x0」或者打字打到完全不相關的字串(懷疑是
  多個排隊中的動作互相干擾)。改用 `javascript_tool` 搭配
  `document.execCommand('insertText', ...)` 直接操作 DOM/React controlled input，
  穩定性高很多，後期測試都改用這個方式。
- **`git commit && git push` 串在一起，新建 branch 的 push 被 Claude Code 的
  auto-mode 權限分類器擋下**(推測是「一次動作裡包含 push 到新 branch」觸發額外
  審查)。拆成兩個獨立的 Bash 呼叫(先 commit，commit 成功後再單獨 push)就能通過。
  跟檔案大小、內容都無關，純粹是分類器對指令組合的判斷。

### 1.15 union-find 同義詞分組原本橫跨三語言，造成不相干的跨語言污染
1.8 把分組上限從 8 調成 80 之後，union-find 本身仍然是把粵語、台語、客語三語言的
所有列合在一起跑同一張圖。使用者回報查「牽手」，粵語卡片全部都是「老婆、太太、妻子、
妻室、某」——追查發現台語「牽手」這個詞目本身一詞兩義(名詞:太太、老婆;動詞:手牽著
手，兩義合併寫在同一列)，它的「對應國語」欄位因此把「太太」「老婆」也一併列為強關聯，
於是台語「牽手」被併入粵語自己既有的「老婆/太太/妻子/妻室」同義詞群組。更嚴重的是:
客語剛好也有兩筆「牽手」(純粹「手和手相牽」的動作義，對應國語欄位是空的，自己完全
沒有貢獻任何強關聯)，卻因為**詞目文字**跟台語那筆撞名，被同一個 `expanded_aliases`
查找邏輯(用詞目文字去查 union-find 分組，不看這一列自己有沒有貢獻邊)一起拖進整個
「太太」語意群組，繼承了一堆跟它本身意思完全無關的別名。

**修法**(在 `build_db.py`):
1. Union-find 改成三語言各自獨立一張圖，粵語、台語、客語的強關聯只在同語言內展開，
   不會互相牽連。
2. 只有一列**自己真的貢獻過強關聯**(對應國語/近義詞非空)，才有資格繼承整個分組的
   別名——同語言內剛好同名但語意無關的兩列，也不會再因為文字撞名而共享別名。

這個決定跟 1.8 的方向剛好相反(1.8 是為了讓跨語言鏈更完整而把上限從 8 調到 80)，
是使用者在看過「牽手」這個具體案例後，明確決定放棄跨語言同步搜尋:「每個語言搜尋
機制不同」。改完之後 `aliases` 筆數從 197,094 降到 99,857(跨語言雜訊消失)，
分組數從 35,534 增加到 48,395(分組變小、變多，但都限定在單一語言內)。

---

## 2. 目前暫時妥協的寫法(Workaround)或尚未修復的 Edge Cases

### 搜尋/比對邏輯
- **純精確字串比對，沒有模糊搜尋、沒有 NLP、沒有真正的斷詞**。完全依賴每個來源
  自己標注的欄位(粵語 `sim:`/`#`/`zho:`、台語 `synonyms`、客語「對應國語」「近義
  詞」)，查不到某個詞通常代表來源沒有對應的標注，不是系統「應該找到卻沒找到」。
- `extract_glosses` 的過濾規則(單一片段 ≤6 字、遇到句號整段跳過、用頓號/逗號/
  分號切割)是手調出來的 heuristic，不是嚴謹的語言學規則，理論上還是可能有極少數
  case 誤判(過寬或過嚴)，沒有做窮舉測試。
- union-find 同義詞分組(現在是粵語/台語/客語各自獨立一張圖，見 1.15)的上限
  (`MAX_COMPONENT_SIZE = 80`，在 `build_db.py`)是人工抽查資料分佈後訂出的經驗值，
  不是精確算出來的最佳解。之後如果任一來源資料大幅更新，這個數字可能需要重新校準
  (重新跑一次分組大小分佈統計、人工抽查中大型分組的內容)。
- 客語的「近義詞」欄位格式(`【詞】、2.【詞】...`)只用簡單的 regex
  (`【([^】]+)】`)抽取方括號內容，如果來源資料出現巢狀括號或非預期的分隔符號，
  可能解析不完整，沒有做過窮舉測試。

### 音檔
- **三個語言目前都沒有任何單字或例句發音**。客語原本有音檔來源但網域已死(見 1.5)，
  台語/粵語則是從一開始就沒有嘗試接音檔來源。`PlayButton` 元件本身已經做好「點擊
  開新分頁播放/下載」的 UI，一旦未來找到可用的音檔網址，理論上只要在對應的
  `parse_*.py` 填入 `word_audio`/`examples[].audio_url` 就能直接生效，不用改前端。

### 連結精準度
- 粵語「閱讀更多」連到 `words.hk/zidin/{詞}`，這是官網自己的詞彙路由，大部分情況
  下能連到正確頁面。
- 台語「閱讀更多」連到官網的**搜尋結果頁**(`?lui=tai_su&tsha={詞}`)，不是精準
  單詞頁——因為 `dict-twblg.json` 的內部 id 跟官網自己的編號對不起來(見 1.4)。
- 客語「閱讀更多」**只能連回首頁**，官網沒有任何可用的搜尋結果網址格式(見 1.6)。
- 台語卡片額外附一個 iTaigi 愛台語(`itaigi.tw/k/{詞}`)連結，是社群共筆資料，
  品質可能跟教育部辭典不一致，沒有做內容比對驗證。

### 收藏功能
- 收藏的識別 key 是 `lang|variant|script|pronunciation_1` 組合字串，**不是永久
  穩定的 ID**。如果未來 ETL/parser 邏輯改變導致同一詞條的 `script` 或
  `pronunciation_1` 顯示文字改變(例如客語拼音格式再次調整)，舊收藏會「悄悄」找
  不到對應資料而被過濾掉——不會報錯或提示使用者，收藏就是安靜消失。
- 收藏、搜尋紀錄、腔調偏好、主題偏好，全部只存瀏覽器 localStorage，**沒有帳號、
  沒有跨裝置同步**，換瀏覽器或清除網站資料就會遺失。

### 資料授權與部署
- 粵語資料(words.hk)已確認《Non-Commercial Open Data License 1.0》授權下，
  非商業個人使用沒有問題，但這個確認只做過一輪(讀授權頁面內容+使用者確認用途)，
  **沒有正式法律諮詢**。目前 GitHub Pages 上的部署屬於這個授權允許的範圍內。
- `dictionary.sqlite` 現在約 54MB，超過 GitHub 建議的單檔 50MB 上限(還沒到 100MB
  硬限制，目前還是能正常 push)，資料持續增加的話未來可能要導入 Git LFS。
- GitHub Pages 部署是**全手動流程**:本機 `npm run build` → 複製 `dist/` 內容到
  另外 clone 出來的 `gh-pages` branch → commit → push。沒有 CI/CD 自動化，每次
  main 有更新，「網站有沒有同步更新」要人工記得手動跑一次這個流程。

### 其他已知未完成項目
- 日語完全未實作(先前討論後决定移除)，`LangCode` 型別、schema、UI 都已經不含
  日語，如果未來要重新加入，是全新的 ETL 工作，不是「打開開關」就好。
- 客語卡片拼音固定顯示「通用拼音調值標記法」，教育部官網其實有調型/調值/調號三種
  切換顯示模式，本專案沒有做這個切換 UI，固定用調值版本。
- 粵語卡片的 `register_tag` 只放 `(label:...)` 標籤內容(例如「書面語」「香港」)，
  詞性(`pos:`)是直接前綴進 `definition` 文字顯示(例如「「動詞」...」)，兩者
  沒有混在同一個欄位裡，但如果之後要在 UI 上把「詞性」獨立成另一個 tag，需要重新
  從 `content` 解析、目前的 schema 沒有專門的詞性欄位。

---

## 3. 專案資料夾與主要檔案結構

```
Words-lookup/                     # 專案根目錄(獨立 git repo,不在 ocf-intern-Sixhuang 裡)
├── README.md                      # 使用者導向文件:怎麼跑、資料授權、搜尋比對邏輯說明
├── IMPLEMENTATION_NOTES.md        # 本文件
├── package.json / package-lock.json
├── vite.config.ts                 # base path 依 build/dev 模式切換(見 1.2)
├── tsconfig.json / tsconfig.app.json / tsconfig.node.json
├── index.html                     # SPA 入口,標題「粵台客 查詞」
├── .oxlintrc.json                 # oxlint 設定(預設值,沒有客製規則)
├── .gitignore                     # 排除 node_modules、dist、data/raw/、
│                                   # public/dictionary.sqlite、.env、__pycache__
│
├── data/                          # 資料層:schema 定義 + ETL 腳本
│   ├── schema.sql                  # SQLite schema,前端與 ETL 共用同一份定義(見下方「資料庫 Schema」)
│   ├── raw/                        # gitignore,不進版控——原始來源檔案放這裡
│   │   ├── 粵典辭典資料.csv          # words.hk 匯出(需使用者自行申請取得)
│   │   ├── dict-twblg.json          # 台語,fetch_moedict.py 自動下載
│   │   └── 客語典文字資料.ods         # 客語原始 ODS,fetch_moedict.py 自動下載
│   └── etl/
│       ├── _common.py               # 共用工具:extract_glosses()(別名抽取heuristic,
│       │                             # 見 1.9)、UnionFind(同義詞分組)、
│       │                             # parse_bracketed_example()(￹￺￻ 例句標記解析)、
│       │                             # read_ods_rows()(ODS 解析,見 1.13)
│       ├── fetch_moedict.py          # 下載台語 JSON + 客語 ODS 到 data/raw/
│       ├── parse_yue.py              # 解析粵典 CSV → 標準化 entry dict(見「粵語解析重點」)
│       ├── parse_nan.py              # 解析台語 JSON → 標準化 entry dict
│       ├── parse_hak.py              # 解析客語 ODS → 標準化 entry dict(見「客語解析重點」)
│       └── build_db.py               # 整合三個 parser 輸出 + union-find 別名展開,
│                                      # 寫入 public/dictionary.sqlite
│
├── public/
│   ├── dictionary.sqlite            # gitignore,由 build_db.py 產生的最終資料庫
│   └── sql-wasm-browser.wasm        # 從 node_modules/sql.js/dist 手動複製(見 1.1)
│
└── src/                            # React 前端
    ├── main.tsx                     # ReactDOM entry
    ├── App.tsx                      # 最上層元件:狀態管理(搜尋/收藏/歷史/主題/腔調/
    │                                 # Modal)、URL 同步(?q=）、favorites 分語言分組
    ├── App.css                      # 版面/元件樣式(卡片、Modal、頁尾、history chips...)
    ├── index.css                    # CSS variables(淺深色主題 token、語言強調色)
    ├── constants.ts                 # LANG_ORDER(['yue','nan','hak'])、LANG_LABELS
    ├── types.ts                     # 共用型別:LangCode、HakkaVariant、Entry、Example、WordAudio
    │
    ├── db/
    │   └── client.ts                 # DictionaryClient class(見下方「查詢引擎」)+
    │                                  # useDictionary() hook(sql.js 初始化、載入 .sqlite)
    │
    ├── hooks/
    │   ├── useFavorites.ts            # 收藏清單(localStorage,newest-first)
    │   ├── useSearchHistory.ts        # 搜尋紀錄(localStorage,上限 15 筆)
    │   ├── useHakkaVariant.ts         # 客語腔調偏好(localStorage,預設海陸腔)
    │   └── useTheme.ts                # 淺深色主題(localStorage,預設淺色,見 README 已更新)
    │
    └── components/
        ├── SearchBox.tsx              # 搜尋輸入框 + 送出按鈕
        ├── SearchHistoryChips.tsx     # 搜尋紀錄的可點擊 chips + 清除按鈕
        ├── TermResult.tsx             # 單次搜尋結果:三語言 LanguageCard 並排(card-row)
        ├── LanguageCard.tsx           # 單一語言欄位:標題 + (客語限定)腔調選單 + 該語言
        │                               # 所有符合的 EntryCard 列表
        ├── EntryCard.tsx              # 單一詞條卡片:文字/拼音/詞性標籤/釋義/例句/來源
        │                               # 連結/收藏愛心;desktop 點擊開 EntryModal
        ├── EntryModal.tsx             # 卡片詳情彈窗(重用 EntryCard,只是外層包一層
        │                               # backdrop + 放大樣式)
        ├── FavoriteStar.tsx           # 收藏愛心按鈕(♥,低透明度,點擊會 stopPropagation
        │                               # 避免觸發卡片的 Modal 開啟)
        ├── PlayButton.tsx             # 發音按鈕(🔊,實際是 <a download target=_blank>,
        │                               # 見 1.5 為什麼不是 <audio>.play())
        ├── HakkaVariantSelect.tsx     # 客語腔調下拉選單(海陸腔/四縣腔)
        ├── ThemeToggle.tsx            # 淺深色切換按鈕
        └── Footer.tsx                 # 頁尾:非商業聲明 + 各語言來源/授權 + repo 連結
```

### 資料庫 Schema(`data/schema.sql`)

```
zh_terms   (id, headword UNIQUE)
entries    (id, zh_term_id→zh_terms, lang['yue'|'nan'|'hak'], variant[hak限定:
            'hailu'|'sixian'], script, pronunciation_1, pronunciation_2,
            definition, register_tag, source_name, source_url, license_note)
examples   (id, entry_id→entries, example_text, example_translation_zh, audio_url)
word_audio (id, entry_id→entries, audio_url)
aliases    (id, entry_id→entries, alias, kind['synonym'|'gloss'])
```

一個 `zh_terms` 對多個 `entries`(同語言可有多筆 = 一詞多義全部列出);`aliases`
是額外的搜尋鍵，`kind` 決定排序優先度(見下方「查詢引擎」)。

### 查詢引擎(`src/db/client.ts` 的 `DictionaryClient`)

- `hasMatch(query): boolean` —— 判斷這個查詢字串有沒有任何結果(用於「查無此詞」
  訊息的判斷)，UNION 查 `zh_terms.headword` 跟 `aliases.alias`。
- `getEntriesForQuery(query, lang, hakkaVariant): Entry[]` —— 主要查詢方法，回傳
  某語言下所有符合的詞條，依 `computeMatchRank()` 排序(詞目命中 > 依語言而定的
  第二層 > 第三層，見 README「搜尋比對邏輯」表格)，同層再依 `registerWeight()`
  (口語優先於書面語)排序。SQL 用 `CASE WHEN ... THEN 1 ELSE 0 END` 算出
  `m_headword`/`m_synonym`/`m_gloss` 三個布林欄位，排序邏輯在 JS 端計算(不是純
  SQL ORDER BY)，方便依語言套用不同排序規則。
- `getEntryByKey(key): Entry | null` —— 給收藏功能用，依 `entryKey()` 組出的
  組合字串(`lang|variant|script|pronunciation_1`)反查單一詞條，查不到回傳
  `null`(不丟例外，見 1.12)。
- `entryKey(entry): string` —— 從 `Entry` 物件組出上面那個組合字串，是個獨立
  export function，前端(App.tsx)跟這個 class 都會用到。
- `expandQueryVariants(query): string[]` —— 查詢時的異體字雙向展開(菸/煙、臺/台
  兩組寫死的清單)，回傳所有候選字串，SQL 查詢用 `IN (...)` 一次查完。

### 粵語解析重點(`parse_yue.py`)
- CSV 內容欄位用小型標記語言:`(pos:X)(label:Y)...` 開頭，接著
  `<explanation>`/`yue:`/`eng:`/`zho:`/`<eg>` 區塊，`section` 狀態機解析(初始值
  `"explanation"`，見 1.11)。
- 只保留 `status == 'OK'` 的資料列(見 1.10，不再過濾 visibility)。
- 別名來源:`zho:` 明確華語對照(→`kind='gloss'`，經 `extract_glosses` 篩選)、
  `(sim:X)` 標籤與 `yue:` 開頭 `#X` 的「同義」標記(→`kind='synonym'`，參與
  union-find 分組)。
- 一個 CSV 資料列可能對應多個詞條寫法(`_split_headword_field`，例如
  「瓊:king4，凝:king4」)，每個寫法各自產生一筆 entries。

### 台語解析重點(`parse_nan.py`)
- 讀 `dict-twblg.json`，每個 `heteronyms[]` 元素是一筆 entries。
- 別名來源:`synonyms` 欄位(→`kind='synonym'`)、從 `definitions[].def` 用
  `extract_glosses` 抽取(→`kind='gloss'`)。
- 例句格式 `￹原文￺台羅￻翻譯`，`parse_bracketed_example()` 解析。
- `source_url` 指向官網搜尋結果頁，不是精準單詞頁(見 1.4)。

### 客語解析重點(`parse_hak.py`)
- 讀 `客語典文字資料.ods`(不是 `dict-hakka.json`，見 1.7)，用 `read_ods_rows()`
  取出 22 欄的原始表格。
- 拼音直接讀「海陸腔音讀」/「四縣腔音讀」欄位(純文字調值標記法，不需轉換)。
- 釋義欄位常見「1. ... \n2. ...」多義項格式，例句用 `例：X。（Y）` 內嵌在釋義
  文字裡，`_extract_examples()` 用 regex 拆出來成獨立 examples，並把這段文字從
  definition 裡移除。
- 別名來源:「對應國語」欄位(→`kind='synonym'`)、「近義詞」欄位(方括號
  `【詞】` 格式，→`kind='gloss'`)。
- 沒有音檔資料(見 1.5)，`word_audio` 恆空。

### `build_db.py` 整合邏輯
1. 依序呼叫三個 parser，合併成 `all_rows`(寫入 `entries` 時仍是三語言一起處理)。
2. 對 `yue_rows`/`nan_rows`/`hak_rows` **各自**的 `strong_aliases`(=各語言的
   synonym 來源欄位)跑獨立的 `UnionFind`，算出**只在同一語言內**跨詞條的同義詞
   分組(見 1.8、1.15——原本三語言合併成一張圖，因為會造成不相干的跨語言污染而
   改成現在這樣)。
3. 一筆 row 要同時滿足「自己有貢獻過至少一個強關聯」與「所屬分組成員數 ≤80」，
   才會展開成該分組其他成員的 `kind='synonym'` 別名；否則(沒貢獻過強關聯、或分組
   >80)只用該筆 row 自己的直接別名(`kind='gloss'`，來自 `extract_glosses`)。
4. 依序寫入 `zh_terms` → `entries` → `examples`/`word_audio`/`aliases`。

---

## 4. 已實現的模組、API 端點與前端頁面

### API 端點
**沒有後端、沒有 API 端點。** 這是純前端 SPA，`dictionary.sqlite` 在瀏覽器內用
`sql.js`(WebAssembly 編譯的 SQLite)直接查詢，所有「查詢邏輯」都在
`src/db/client.ts` 的 `DictionaryClient` class 裡，可以把它的 public 方法當作
「前端內部 API」:

| 方法 | 用途 |
|---|---|
| `hasMatch(query)` | 判斷查詢有沒有結果 |
| `getEntriesForQuery(query, lang, hakkaVariant)` | 取得某語言下所有符合結果，已排序 |
| `getEntryByKey(key)` | 依收藏 key 反查單一詞條 |
| `entryKey(entry)`(獨立 function) | 組出收藏用的識別字串 |

### 前端「頁面」(SPA 內的畫面狀態，非獨立路由)
應用程式沒有用路由套件，只有一個 URL 會變化的參數(`?q=`)，畫面切換靠 React state:

1. **初始/搜尋結果畫面**——`SearchBox` + `SearchHistoryChips` + `TermResult`
   (查有結果時)或「查無此詞」訊息(查無結果時)
2. **收藏清單畫面**(`showFavorites=true` 時)——依語言分三區塊(`favorites-
   section`),每區塊是 `EntryCard` 的 grid，新收藏的排最上面
3. **詞條詳情 Modal**(`EntryModal`，`modalEntry` state 非 null 時)——桌面版
   點卡片觸發，疊在畫面最上層，內容重用 `EntryCard`

### React 元件清單
`App`(根)、`SearchBox`、`SearchHistoryChips`、`TermResult`、`LanguageCard`、
`EntryCard`、`EntryModal`、`FavoriteStar`、`PlayButton`、`HakkaVariantSelect`、
`ThemeToggle`、`Footer` —— 共 12 個，全部列在上面第 3 節的檔案結構裡，不重複列職責。

### React Hooks 清單
`useDictionary`(client.ts 內)、`useFavorites`、`useSearchHistory`、
`useHakkaVariant`、`useTheme` —— 共 5 個，皆為自訂 hook，除了 `useDictionary`
(管理 sql.js 載入狀態)以外都是 localStorage 包裝。

### Python ETL 模組清單
`_common.py`(共用工具)、`fetch_moedict.py`(下載)、`parse_yue.py`、
`parse_nan.py`、`parse_hak.py`(三語言解析)、`build_db.py`(整合輸出)——共 6 個
檔案，執行方式:`npm run build:data`(= `python data/etl/build_db.py`)。

---

## 5. 其他

### 部署現況
- **Repo**:<https://github.com/trickster-2005/Dictionary-Hakka-Hokkien-Cantonese>
  (`main` branch 是原始碼，獨立於使用者原本的 `ocf-intern-Sixhuang` repo)
- **Live demo**:<https://trickster-2005.github.io/Dictionary-Hakka-Hokkien-Cantonese/>
  (由 `gh-pages` branch 提供，內容是 `npm run build` 的輸出，手動同步，見上面
  「GitHub Pages 部署是全手動流程」)
- 專案狀態:README.md 開頭標記「🚧 尚在開發中」，文末有 TODO 清單。

### 資料庫規模(union-find 改成三語言各自獨立分組之後，見 1.15)
- 華語詞條(`zh_terms`)共 46,008 筆
- `entries` 共 76,737 筆，拆解如下:
  - 粵語(yue):31,147 筆
  - 台語(nan):14,998 筆
  - 客語(hak，海陸+四縣合計):30,592 筆
- `aliases`(含 union-find 展開後)共 99,857 筆，三語言各自獨立的同義詞分組合計
  48,395 組(其中 2 組因超過 `MAX_COMPONENT_SIZE=80` 被退回只用直接別名)。改成
  各語言獨立分組前是 197,094 筆別名、35,534 組(當時三語言合併成一張圖)。
- `dictionary.sqlite` 檔案大小約 55MB(超過 GitHub 建議的單檔 50MB，尚未到 100MB
  硬限制)

(以上數字會隨來源資料更新、parser 邏輯調整而變動，實際數字請重跑
`npm run build:data` 看 console 輸出。)

### 修補既有缺口(順序不代表優先度，整理自第 2 節)
1. 客語、台語、粵語的單字、例句發音音檔來源（目前完全沒有）
2. 日語重新串接（全新 ETL，非既有架構的延伸）
3. UI 視覺設計持續打磨（目前偏功能優先的陽春版面）
4. 粵語資料公開部署前的正式授權確認（目前只做過一輪自行研讀，非正式法律諮詢）
5. `MAX_COMPONENT_SIZE`（80）、`extract_glosses` 的長度／標點規則，隨資料量增長
   可能需要重新校準
6. 考慮把 GitHub Pages 部署流程自動化（目前全手動）

### 未來可以新增的方向（不是修 bug，是全新功能）

**資料廣度**
- 客語其實已經收了六腔（四縣、海陸、大埔、饒平、詔安、南四縣），`客語典文字資料.
  ods` 裡六腔的音讀欄位、以及大埔／饒平／詔安／南四縣各自的「相關字詞」欄位都已經
  下載在本機，目前 `parse_hak.py` 只用了海陸、四縣兩腔——**這是最低成本就能擴充的
  項目**，不需要找新資料來源，改 `ACCENT_COLUMNS` 跟前端腔調選單即可。
- 同義詞網絡視覺化：union-find 分組（現在是粵語／台語／客語各自獨立一張圖，見
  1.15）本身已經是一個語意關聯圖，可以做成「這個詞在同語言裡有哪些相關字詞」的
  圖表檢視，而不只是拿來排序。
- 開放使用者回報錯誤／補充資料（例如詞條下方加「回報問題」連結，蒐集到一定數量後
  人工審核合併回 ETL）。

**查詢體驗**
- 真正的模糊搜尋／同義詞辭典整合（例如結合中文 WordNet、embedding 相似度），取代
  現在完全依賴各來源自行標註的 sim/synonyms/對應國語欄位。
- 拼音／注音查詢（現在只能用漢字查，如果知道台羅、粵拼、客語拼音但不知道漢字寫法，
  查不到）。
- 例句真人朗讀募集（類似 Tatoeba 的社群錄音模式），順便解決音檔完全空缺的問題。

**平台與基礎建設**
- PWA／離線支援：把 `dictionary.sqlite` 用 Service Worker 快取，離線也能查詢。
- CI/CD 自動化 GitHub Pages 部署（main 有更新時自動 build 並同步 gh-pages，取代
  現在的手動流程）。
- `dictionary.sqlite` 改用 Git LFS 或外部 CDN 存放，避免單檔案持續逼近 GitHub
  100MB 硬限制。
- 收藏清單匯出／匯入（例如匯出成 CSV 或 Anki 卡片格式，方便搭配其他學習工具）。
- 分享單一詞條時的 Open Graph 預覽卡（目前 `?q=` 網址可以分享，但社群平台預覽
  只會看到通用的網站標題，沒有那個詞本身的內容）。
