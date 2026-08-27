# 粵台客 查詞

[github.com/trickster-2005/Dictionary-Hakka-Hokkien-Cantonese](https://github.com/trickster-2005/Dictionary-Hakka-Hokkien-Cantonese)

> 🚧 **尚在開發中**,功能與資料都還會持續調整,見文末 TODO。

輸入一個華語詞彙,同時查粵語(粵典 words.hk)、台語(教育部臺灣台語常用詞辭典)、
客語(教育部臺灣客語辭典,海陸腔/四縣腔可切換)的對應詞條。純前端靜態網站,資料
預先建成 SQLite,瀏覽器用 `sql.js`(WebAssembly)查詢,不需要後端伺服器。收藏與
客語腔調偏好存在瀏覽器 localStorage。

## 開發

```bash
npm install
npm run build:data   # 執行 data/etl 下的 ETL,產生 public/dictionary.sqlite
npm run dev
```

`npm install` 之後,`sql.js` 在瀏覽器端用的 wasm 檔要手動複製一次(package 更新版本
號可能會需要重做這步):

```bash
cp node_modules/sql.js/dist/sql-wasm-browser.wasm public/sql-wasm-browser.wasm
```

`npm run build:data` 第一次執行會自動下載台語的 JSON、客語的 ODS 到 `data/raw/`
(之後重跑會直接使用本機快取,不會重複下載;要強制更新可以刪掉 `data/raw/` 底下對應
檔案再重跑,或呼叫 `fetch_moedict.fetch(force=True)`)。**粵語的來源 CSV 需要自己到
[words.hk 的資料申請頁](https://words.hk/faiman/request_data/) 申請,下載後把
`粵典辭典資料.csv` 放進 `data/raw/` 才能跑粵語那段 ETL。**

客語用的是 [g0v/moedict-data-hakka](https://github.com/g0v/moedict-data-hakka) repo
裡的原始 `ods/客語典文字資料.ods`,不是該 repo 自己轉出的 `dict-hakka.json`——後者
在轉換過程中把「對應國語」「近義詞」欄位、以及六腔的純文字調值標音都拿掉了,前者才是
完整資料。

## 資料授權

- **粵語(words.hk)**:詞典資料採
  [Non-Commercial Open Data License 1.0](https://words.hk/base/hoifong/) 授權,
  非商業用途下可以複製、修改、發佈、再分發。本專案完全非商業,只做個人語言學習與
  交流用途,屬於授權允許的範圍。

  > 版權聲明:粵語資料版權持有人以《Non-Commercial Open Data License》授權發佈
  > (<https://words.hk/base/hoifong/>),原始資料來自
  > [words.hk 粵典](https://words.hk/)。本專案為非商業性質,僅供個人學習交流
  > 使用,不涉及任何營利行為。

  原始 CSV 與建出來的 `dictionary.sqlite` 沒有進版控,單純是因為屬於可以重新產生
  的大型檔案(CSV 依 words.hk 的流程要各自申請取得、sqlite 是 build 產物),跟授權
  疑慮無關。
- **台語 / 客語(教育部)**:辭典本文採創用CC「姓名標示-禁止改作 3.0 台灣」,
  本專案僅重新排版供查詢使用,未更動釋義文字,且卡片上都附了 `source_url` 連回
  官方辭典頁面。

## 專案結構

```
data/
  schema.sql        # SQLite schema,前端與 ETL 共用同一份定義
  raw/               # gitignore —— 來源 CSV/JSON/ODS 都放這裡,不進版控
  etl/
    _common.py         # extract_glosses / UnionFind / 例句標記解析,三個 parser 共用
    fetch_moedict.py    # 下載台語 JSON、客語 ODS
    parse_yue.py         # 解析 words.hk CSV
    parse_nan.py          # 解析台語 JSON
    parse_hak.py           # 解析客語 ODS(對應國語/近義詞/六腔調值標音)
    build_db.py             # 整合以上 + 別名的 union-find 展開,輸出 public/dictionary.sqlite
public/
  dictionary.sqlite  # gitignore —— 由 build_db.py 產生
  sql-wasm-browser.wasm
src/
  db/client.ts        # sql.js 初始化 + 查詢 + 結果排序
  components/          # SearchBox / LanguageCard / HakkaVariantSelect / FavoriteStar / ThemeToggle / PlayButton
  hooks/                 # useFavorites / useHakkaVariant / useTheme(皆存 localStorage)
```

## 搜尋比對邏輯

除了直接比對各辭典自己的 headword,`aliases` 表還收錄兩種額外的搜尋鍵,每筆都有
`kind`(`synonym` 或 `gloss`)決定排序優先度:

| 語言 | 詞目(rank 0) | 別名 rank 1(`kind='synonym'`) | 別名 rank 2(`kind='gloss'`) |
|---|---|---|---|
| 粵語 | headword | *(不分,任何別名都算 rank 1)* | |
| 台語 | 詞目 | `synonyms` 欄位(近義詞) | 從釋義抽出的短華語對譯詞 |
| 客語 | 詞目 | 對應國語 | 近義詞 |

「從釋義抽出短華語對譯詞」是 `data/etl/_common.py` 的 `extract_glosses`(例如台語
「昨昏」的釋義第一義項是「昨天。」,定義夠短、夠乾淨才會建別名,頓號/逗號/分號分隔
的多義項會各自拆開)。

`kind='synonym'` 的別名還會在 build 階段做 union-find 分組(`build_db.py`):A 的
對應國語/synonyms 標到 C、B 也標到 C,則 A、B、C 三者互相可以用彼此的字找到,即使
兩兩之間沒有直接標注。例如查「抽菸」除了直接命中「抽煙/抽菸」,還會經由「同義詞
鏈」(抽煙→吸煙→食煙)一路找到「食煙」;查「爸爸」也能經由「阿爸→爸爸←老豆」這條
跨語言的鏈找到粵語的「老豆/老竇」。為避免少數多義字(例如「金」同時是黃金/金錢/
姓氏,會把不相干的詞全部串在一起,實測最誇張的兩組分別混進了 184 跟 297 個不相干
詞條)把整組搜尋結果污染,分組成員數超過 80 的一律退回只做直接別名,不展開——這個
門檻是實際攤開幾十組分組人工看過內容才定的(80 以下都還算主題一致,184 起才是真的
亂七八糟),不是隨便猜的數字。

同語言底下若有多個相關詞條(直接命中+多個別名命中),每個詞條各自成一張卡片,依
上面的 rank 排序,同順位內粵語再依 `register_tag` 把口語排在書面語之前。

前端另外對「菸/煙」「臺/台」這兩組極常見的異體字做查詢時的雙向展開
(`src/db/client.ts` 的 `VARIANT_PAIRS`),這只是一張很短的白名單,不是完整異體字
轉換,存進資料庫的文字本身不會被改寫。

## 已知限制(MVP 範圍)

- **目前沒有任何發音音檔**(單字或例句都沒有——客語 ODS 的釋義欄位裡雖然內嵌了
  「例：...」文字並拆成獨立例句顯示,但沒有對應錄音)。單字音檔原本接的是 g0v 資料裡的
  `hakka.dict.edu.tw`,已確認這個網域完全連不上(DNS 解析得到但每次連線都逾時,
  應該是舊站已經關掉);現在的 `hakkadict.moe.edu.tw` 雖然真的有語音,但音檔網址是
  透過每個詞條的動態編號組出來的,而這個編號沒有出現在 g0v 的 JSON 匯出裡,目前沒
  有辦法從我們手上的資料建出正確網址,所以先整個拿掉,不要留著會 404 的連結。
- **粵語/台語的「閱讀更多」是搜尋結果頁,不是精準的單詞頁**:words.hk
  (`https://words.hk/zidin/{詞}`)、sutian.moe.edu.tw
  (`?lui=tai_su&tsha={詞}`)都有支援用詞彙查詢的網址格式,已確認可用。**客語則只
  能連回首頁**——`hakkadict.moe.edu.tw` 的搜尋是前端 JS 送 POST 做的,已經逐一測試
  過 GET query string(`?word=`/`?keyword=`等)完全被忽略,頁面內容不變,沒有找到
  任何可以直接帶查詢字串生效的網址格式。
- **台語卡片額外附一個 iTaigi 愛台語(`https://itaigi.tw/k/{詞}`)連結**,是社群
  共筆的口語用法補充,非官方資料,品質不一定跟教育部辭典一致。

## TODO

- **UI 設計**:整體排版、配色、手機版體驗都還在調整,目前是功能優先的陽春版面
- **查詢比對**:三語都已經是「詞目/近義詞/對應國語/解釋」多欄位比對,但還是常有
  查不到的情況(定義是完整句子、用字差太多等),持續在補
- **排序**:三語都已經有 rank 0/1/2 的多層排序(見上面「搜尋比對邏輯」的表格),
  品質仍待更多實際查詢驗證,分組上限(80)也可能需要再調整
- 日語資料串接(先移除,未來視情況再議)
- 客語/台語/粵語單字與例句發音音檔來源
- 粵語資料公開部署前的授權確認
