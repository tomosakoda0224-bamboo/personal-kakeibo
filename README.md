# わたしの家計簿（Googleスプレッドシート版）

Streamlitから入力した支出をGoogleスプレッドシートに保存します。
初回接続時に「支出」と「カテゴリー」の2シートを自動作成します。

## 1. Google側の準備

1. Google Cloudでプロジェクトを作成し、Google Sheets APIを有効にします。
2. サービスアカウントを作成し、JSONキーを取得します。
3. 空のGoogleスプレッドシートを1つ作成します。
4. スプレッドシートの「共有」から、サービスアカウントの
   `client_email` を編集者として追加します。

## 2. 接続情報の設定

`.streamlit/secrets.toml.example` を同じ場所に `secrets.toml` という名前で
コピーします。JSONキーの各値と、作成したスプレッドシートのURLを入力してください。

`secrets.toml` には秘密鍵が含まれるため、他人へ渡したりGitへ登録したりしないでください。

## 3. 起動

```powershell
cd outputs\kakeibo_streamlit
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

接続に成功すると、スプレッドシートに次の2シートが作られます。

- `支出`：日付、購入品、金額、カテゴリー、登録日時
- `カテゴリー`：カテゴリー名とアイコン

カテゴリーシートを直接編集した内容も、次回のアプリ表示に反映されます。
