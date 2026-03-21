# OpenViking MCP Server

Claude Code から [OpenViking](https://github.com/volcengine/OpenViking) のコンテキストDBにアクセスするMCPサーバー。

L0/L1/L2の段階的ロードでトークンを大幅に節約します。

## 特徴

- **セマンティック検索** — 自然言語クエリで設計書・ドキュメントを横断検索
- **段階的ロード** — L0要約(~100tok) → L1概要(~2ktok) → L2全文。必要な粒度だけ読む
- **ローカル完結** — [OpenViking fork](https://github.com/yoshitetsu/OpenViking) の `local` provider と組み合わせればAPI課金ゼロ
- **7 tools** — find / read / ls / add / abstract / overview / grep

## 前提

- OpenVikingサーバーが `localhost:1933` で起動済み
- Python 3.10+

## セットアップ

```bash
# 1. 依存インストール
pip install -r requirements.txt

# 2. Claude Code settings.json に追加
```

```json
{
  "mcpServers": {
    "openviking": {
      "command": "python3",
      "args": ["/path/to/openviking-mcp/server.py"],
      "env": {
        "OPENVIKING_URL": "http://127.0.0.1:1933"
      }
    }
  }
}
```

```bash
# 3. Claude Codeを再起動
```

## Tools

| Tool | 説明 | トークンコスト |
|------|------|-------------|
| `viking_find` | セマンティック検索。L0要約付きで返す | 低 |
| `viking_abstract` | URIのL0要約を取得 | 最小 |
| `viking_overview` | URIのL1概要を取得 | 中 |
| `viking_read` | URIのL2全文を取得 | 高 |
| `viking_ls` | ディレクトリ一覧（L0要約付き） | 低 |
| `viking_add` | ローカルファイルをリソース追加 | — |
| `viking_grep` | テキストパターン検索 | 低 |

## 使い方のフロー

```
1. viking_find("古賀凛のGhost") → L0要約付きリスト
   → "キャラ設計の古賀Ghost形成過程" (score: 0.50)

2. L0で「場所は分かったけど詳細が欲しい」
   → viking_overview("viking://resources/characters/koga-rin") → L1概要

3. L1で「具体的な記述が必要」
   → viking_read("viking://resources/characters/koga-rin/ghost.md") → L2全文
```

Claude Codeは各toolのdescriptionに従い、L0 → L1 → L2の順で必要最小限だけ読みます。

## ローカルembedding（API課金ゼロ）

[OpenViking fork](https://github.com/yoshitetsu/OpenViking/tree/feature/local-embedding-provider) の `local` provider を使うと、embeddingもローカルで完結します。

```json
// ~/.openviking/ov.conf
{
  "embedding": {
    "dense": {
      "provider": "local",
      "model": "intfloat/multilingual-e5-large",
      "device": "mps"
    }
  }
}
```

## ライセンス

Apache-2.0
