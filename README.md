# 粵台客 查詞

[github.com/trickster-2005/Dictionary-Hakka-Hokkien-Cantonese](https://github.com/trickster-2005/Dictionary-Hakka-Hokkien-Cantonese)

> 🚧 **尚在開發中**，功能與資料都還會持續調整。

輸入一個華語詞彙，同時查粵語（粵典 words.hk）、台語（教育部臺灣台語常用詞辭典）、
客語（教育部臺灣客語辭典，海陸腔／四縣腔可切換）的對應詞條。純前端靜態網站，資料
預先建成 SQLite，瀏覽器用 `sql.js`（WebAssembly）查詢，不需要後端伺服器。收藏、
搜尋紀錄與客語腔調偏好都存在瀏覽器 localStorage，每次查詢也有專屬網址可以分享。

線上版：<https://trickster-2005.github.io/Dictionary-Hakka-Hokkien-Cantonese/>

## 開發

```bash
npm install
npm run build:data   # 執行 data/etl 下的 ETL，產生 public/dictionary.sqlite
npm run dev
```

`npm install` 之後，`sql.js` 在瀏覽器端用的 wasm 檔要手動複製一次（package 更新版本
號可能會需要重做這步）：

```bash
cp node_modules/sql.js/dist/sql-wasm-browser.wasm public/sql-wasm-browser.wasm
```

`npm run build:data` 第一次執行會自動下載台語的 JSON、客語的 ODS 到 `data/raw/`
（之後重跑會直接使用本機快取）。**粵語的來源 CSV 需要自己到
[words.hk 的資料申請頁](https://words.hk/faiman/request_data/) 申請，下載後把
`粵典辭典資料.csv` 放進 `data/raw/` 才能跑粵語那段 ETL。**

## 搜尋比對邏輯（重點摘要）

除了直接比對各辭典自己的詞目，`aliases` 表還收錄「近義詞／對應國語」與「從釋義抽出
的短華語對譯詞」兩種額外搜尋鍵，依語言各自排序：

| 語言 | 詞目（rank 0） | 別名 rank 1 | 別名 rank 2 |
|---|---|---|---|
| 粵語 | 詞目 | *（不分，任何別名都算 rank 1）* | |
| 台語 | 詞目 | 近義詞 | 從釋義抽出的短華語對譯詞 |
| 客語 | 詞目 | 對應國語 | 近義詞 |

近義詞之間還會做跨詞條的同義詞鏈展開（例如查「抽煙」能經由「抽煙→吸煙→食煙」連到
「食煙」），但只在**同一語言內**展開——粵語、台語、客語各自獨立分組，不會互相牽連，
且為避免少數多義字把不相干的詞全部串在一起，分組人數設有上限。完整規則與判斷依據見
[IMPLEMENTATION_NOTES.md](IMPLEMENTATION_NOTES.md)。

## 資料授權

- **粵語（words.hk）**：詞典資料採
  [Non-Commercial Open Data License 1.0](https://words.hk/base/hoifong/) 授權，
  非商業用途下可以複製、修改、發佈、再分發。本專案完全非商業，只做個人語言學習與
  交流用途，屬於授權允許的範圍。原始 CSV 與建出來的 `dictionary.sqlite` 未進版控，
  純粹因為是可重新產生的大型檔案，與授權疑慮無關。
- **台語／客語（教育部）**：辭典本文採創用CC「姓名標示－禁止改作 3.0 台灣」，
  本專案僅重新排版供查詢使用，未更動釋義文字，且卡片上都附了原始出處連結。

## 已知限制

- 目前沒有任何發音音檔（客語官方音檔站已失效或無法組出可用網址，其餘語言尚未串接）
- 客語的「閱讀更多」只能連回辭典首頁，粵語／台語則有精準的搜尋結果頁連結
- 部分查詢仍找不到結果（定義是完整句子、用字差異太大等），比對規則持續調整中

完整的踩坑紀錄、暫時妥協寫法、資料夾結構與未來規劃，見
[IMPLEMENTATION_NOTES.md](IMPLEMENTATION_NOTES.md)。
