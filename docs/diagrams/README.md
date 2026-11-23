# 圖表原始檔

`*.mmd` 是 Mermaid 原始碼，`../images/*.png` 由它們產生，文件中的圖片與摺疊的原始碼都來自這裡。

重新產生（使用本機 Chrome 與繁體中文字型）：

```bash
npx -y @mermaid-js/mermaid-cli@12.2.0 -i docs/diagrams/architecture.mmd -o docs/images/architecture.png \n  -s 2 -b white -c docs/diagrams/mermaid-config.json -p <puppeteer-config.json>
```

`puppeteer-config.json` 只需指定本機瀏覽器，例如 `{"executablePath": "C:/Program Files/Google/Chrome/Application/chrome.exe"}`。
