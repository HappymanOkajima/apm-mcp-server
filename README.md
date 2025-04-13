# apm-mcp-server: アジャイルプラクティスマップ MCPサーバー

## 概要

アジャイルプラクティスマップのデータと対話するためのMCPサーバーです。このサーバーは、大規模言語モデルを通じてアジャイルプラクティスマップ（※）のナレッジベースから情報をRAG検索します。

※ https://www.agile-studio.jp/agile-practice-map

## ツール

1. **apm_query**
   - アジャイルプラクティスマップ（Agile Practice Map）に関する質問に回答します
   - 入力:
     - `question` (文字列): アジャイルプラクティスに関するユーザーの質問
   - 戻り値: アジャイルプラクティスマップのナレッジベースに基づく回答

## インストール

### uvのインストール

まだインストールされていない場合、`uv`パッケージマネージャーをインストールする必要があります。

**Windows:**
```
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**macOS:**
```
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Linux:**
```
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### リポジトリのクローン

```
# リポジトリをクローンします。
git clone https://github.com/HappymanOkajima/apm-mcp-server.git
```

### OpenAIのAPIキーの設定

apm-mcp-server 配下に.envファイルを作成してください。

`.env` ファイルの例:
```
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxx
```

## 設定

### Claude Desktopでの使用方法

`claude_desktop_config.json`に以下を追加してください。※絶対パスで指定しないと動作しない場合が多いです。

```json
{
  "mcpServers": {
    "apm-mcp-server": {
      "disabled": false,
      "timeout": 60,
      "command": "c:\\YOUR_PATH\\uv",
      "args": [
        "--directory",
        "C:\\YOUR_PATH\\apm-mcp-server",
        "run",
        "-m",
        "apm_mcp_server"
      ],
      "transportType": "stdio"
    }
 }
}
```

Docker コンテナを使って MCP サーバーを実行する場合、以下のように設定します。

Dockerビルド:
```
docker build -t mcp/apm .
```

```json
{
  "mcpServers": {
    "apm": {
      "command": "docker",
      "args": [
        "run",
        "--rm",
        "-i",
        "-e", "OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxx",
        "mcp/apm"
      ]
    }
  }
}
```

### Clineでの使用方法

Clineチャットに相談しながらインストール、設定してください。

## プロジェクト構造

- `apm_mcp_server/`: メインサーバーコード
  - `main.py`: MCPサーバーのエントリーポイント
  - `rag_chroma/`: Chroma DBを使用したRAG実装
- `data/`: ソースデータとベクターデータベースを含む
  - `apm.txt`: アジャイルプラクティスマップのソーステキストデータ
  - `chroma_db/`: アジャイルプラクティスマップのデータ
- `tools/`: ユーティリティスクリプト
  - `populate_db.py`: ソースデータからベクターデータベースを作成するスクリプト

## データベース構築ツール

コンテンツのURLまたはテキストファイルからベクトルデータベースを構築するツールが同梱されています。

```
uv run -m tools.populate_db
```

これにより、`data/chroma_db/`にベクトルデータベースが作成されます。


## ライセンス

このMCPサーバーはMITライセンスの下で公開されています。これにより、MITライセンスの条件に従って、ソフトウェアを自由に使用、変更、配布することができます。詳細については、プロジェクトリポジトリ内のLICENSEファイルをご覧ください。