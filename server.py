#!/usr/bin/env python3
"""OpenViking MCP Server — Claude CodeからコンテキストDBにアクセスする薄いプロキシ。

L0/L1/L2の段階的ロードでトークンを節約:
  - viking_find → L0要約付きリスト
  - viking_overview → L1概要（必要な場合のみ）
  - viking_read → L2全文（必要な場合のみ）

前提: OpenVikingサーバーが起動済み（デフォルト: http://127.0.0.1:1933）
"""

import json
import os
from typing import Optional

import httpx
from mcp.server.fastmcp import FastMCP

OPENVIKING_URL = os.environ.get("OPENVIKING_URL", "http://127.0.0.1:1933")

server = FastMCP(name="openviking")


async def _get(path: str, params: Optional[dict] = None) -> dict:
    """GET request to OpenViking API."""
    async with httpx.AsyncClient(base_url=OPENVIKING_URL, timeout=30.0) as client:
        resp = await client.get(f"/api/v1{path}", params=params)
        resp.raise_for_status()
        return resp.json()


async def _post(path: str, body: dict) -> dict:
    """POST request to OpenViking API."""
    async with httpx.AsyncClient(base_url=OPENVIKING_URL, timeout=60.0) as client:
        resp = await client.post(f"/api/v1{path}", json=body)
        resp.raise_for_status()
        return resp.json()


async def _delete(path: str, params: Optional[dict] = None) -> dict:
    """DELETE request to OpenViking API."""
    async with httpx.AsyncClient(base_url=OPENVIKING_URL, timeout=30.0) as client:
        resp = await client.delete(f"/api/v1{path}", params=params)
        resp.raise_for_status()
        return resp.json()


def _format_error(e: Exception) -> str:
    if isinstance(e, httpx.ConnectError):
        return f"OpenViking server is not running at {OPENVIKING_URL}. Start it first."
    return f"OpenViking API error: {e}"


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@server.tool()
async def viking_find(query: str, top_k: int = 5) -> str:
    """セマンティック検索。結果にはL0要約が含まれる。

    L0で十分な情報があればそのまま使い、
    もう少し構造を知りたい場合のみviking_overviewでL1を取得し、
    全文が必要な場合のみviking_readでL2を取得すること。
    """
    try:
        data = await _post("/search/find", {"query": query, "top_k": top_k})
    except Exception as e:
        return _format_error(e)

    result = data.get("result", {})
    resources = result.get("resources", [])
    memories = result.get("memories", [])

    lines = []
    for item in memories + resources:
        uri = item.get("uri", "")
        score = item.get("score", 0)
        abstract = item.get("abstract", "")
        ctx_type = item.get("context_type", "")
        lines.append(f"[{ctx_type}] {uri} (score: {score:.3f})")
        if abstract:
            lines.append(f"  L0: {abstract[:200]}")
        lines.append("")

    if not lines:
        return "No results found."
    return "\n".join(lines)


@server.tool()
async def viking_read(uri: str) -> str:
    """URIの全文（L2）を取得する。

    トークンを多く消費するため、viking_findのL0やviking_overviewのL1で
    情報が不足する場合のみ使用すること。
    """
    try:
        data = await _get("/content/read", {"uri": uri})
    except Exception as e:
        return _format_error(e)
    return data.get("result", "")


@server.tool()
async def viking_ls(uri: str = "viking://resources/") -> str:
    """ディレクトリ一覧。各エントリにL0要約が含まれる。"""
    try:
        data = await _get("/fs/ls", {"uri": uri})
    except Exception as e:
        return _format_error(e)

    entries = data.get("result", [])
    lines = []
    for entry in entries:
        entry_uri = entry.get("uri", "")
        is_dir = entry.get("isDir", False)
        abstract = entry.get("abstract", "")
        icon = "/" if is_dir else ""
        lines.append(f"{entry_uri}{icon}")
        if abstract:
            lines.append(f"  {abstract[:150]}")
    return "\n".join(lines) if lines else "Empty directory."


@server.tool()
async def viking_add(path: str) -> str:
    """ローカルファイルをOpenVikingにリソースとして追加する。"""
    try:
        data = await _post("/resources", {"path": path})
    except Exception as e:
        return _format_error(e)

    result = data.get("result", {})
    status = result.get("status", "unknown")
    root_uri = result.get("root_uri", "")
    return f"Status: {status}, URI: {root_uri}"


@server.tool()
async def viking_abstract(uri: str) -> str:
    """URIのL0要約を取得する。最小コストで内容を把握できる。"""
    try:
        data = await _get("/content/abstract", {"uri": uri})
    except Exception as e:
        return _format_error(e)
    return data.get("result", "")


@server.tool()
async def viking_overview(uri: str) -> str:
    """URIのL1概要を取得する。L0より詳しいがL2より軽量。

    セクション構成や要点を把握したい場合に使う。
    viking_findのL0で不足し、viking_readのL2ほど詳細が不要な場合に最適。
    """
    try:
        data = await _get("/content/overview", {"uri": uri})
    except Exception as e:
        return _format_error(e)
    return data.get("result", "")


@server.tool()
async def viking_delete(uri: str) -> str:
    """リソースを削除する。旧バージョンの整理に使う。

    viking_lsで一覧を確認してから、不要なURIを指定して削除する。
    削除は不可逆なので注意。
    """
    try:
        data = await _delete("/fs", {"uri": uri, "recursive": True})
    except Exception as e:
        return _format_error(e)

    result = data.get("result", {})
    deleted_uri = result.get("uri", uri)
    return f"Deleted: {deleted_uri}"


@server.tool()
async def viking_grep(pattern: str, uri: str = "viking://resources/") -> str:
    """テキストパターン検索。正規表現対応。"""
    try:
        data = await _post("/search/grep", {"pattern": pattern, "uri": uri})
    except Exception as e:
        return _format_error(e)

    results = data.get("result", [])
    if not results:
        return "No matches found."

    lines = []
    for match in results:
        match_uri = match.get("uri", "")
        snippets = match.get("matches", [])
        lines.append(f"{match_uri}")
        for snippet in snippets[:3]:
            lines.append(f"  {snippet}")
    return "\n".join(lines)


if __name__ == "__main__":
    server.run(transport="stdio")
