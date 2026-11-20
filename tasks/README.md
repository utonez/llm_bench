# 題庫來源與授權

本題庫**不含任何自行編造的題目**。每一題都在 YAML 的 `source` 欄位註明出處、授權與在原始資料中的位置（`locator`），
題目文字與標準答案皆逐字取自原始來源。程式層面也強制要求：沒有 `source` 的題目無法載入（見 `app/bench/models.py`）。

| 檔案 | 題數 | 類別 | 來源 | 授權 |
|---|---|---|---|---|
| `banking77.yaml` | 10 | 意圖分類 | [Banking77](https://github.com/PolyAI-LDN/task-specific-datasets)（PolyAI）真實銀行客服提問 | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) |
| `financial_phrasebank.yaml` | 6 | 情緒分類 | [Financial PhraseBank v1.0](https://huggingface.co/datasets/takala/financial_phrasebank)（Aalto University）財經新聞句 | [CC BY-NC-SA 3.0](https://creativecommons.org/licenses/by-nc-sa/3.0/) ⚠️ |
| `tw_gov_press.yaml` | 11 | 抽取、摘要、說明 | 金融監督管理委員會、中央銀行新聞稿 | 公文，依著作權法第 9 條不受著作權保護 |

## 選題方式

- **Banking77**：從 `test.csv` 選 5 個與台灣銀行業務相關的意圖（卡片遺失/被竊、不明刷卡、匯率、轉帳未入帳、卡片未寄達），
  每個意圖取該類別在檔案中出現的前幾筆、排除語意模糊者，共 2 筆。標準答案為資料集原始標籤。
- **Financial PhraseBank**：只取 `Sentences_AllAgree.txt`（所有標註者意見一致的句子），正面、負面、中性各 2 句。
  保留資料集原始斷詞（例如 `5.2 %`）以便與原檔逐字比對。
- **政府新聞稿**：金管會 2026 年 3 則裁罰新聞稿與中央銀行 2026-09-17 理監事會決議新聞稿。
  抽取題的標準答案只取原文明載內容，唯一的轉換是把「萬元／億元」換算成「元」（例如 1億164萬元 → 101640000）。
  摘要與說明題不評分，但題目所附原文可供人工檢查模型輸出是否忠於原文。

## 驗證

題目建立時以腳本比對每一題的引文與下載的原始檔，27 題全部逐字相符（2026-11-20）。

## 引用

- Casanueva, I., Temčinas, T., Gerz, D., Henderson, M., Vulić, I. (2020). *Efficient Intent Detection with Dual Sentence Encoders.* — Banking77
- Malo, P., Sinha, A., Korhonen, P., Wallenius, J., Takala, P. (2014). *Good debt or bad debt: Detecting semantic orientations in economic texts.* JASIST. — Financial PhraseBank

## ⚠️ Financial PhraseBank 授權注意

`financial_phrasebank.yaml` 含 Financial PhraseBank 內容，**該檔案以 CC BY-NC-SA 3.0 授權**：
限非商業用途、需標示出處、衍生作品須採相同授權。若本專案用於商業用途，應移除此檔或向原作者取得授權。
