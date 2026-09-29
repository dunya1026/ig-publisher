"""노션 REST API 최소 클라이언트 (data source API, Notion-Version 2025-09-03)."""
from __future__ import annotations

import time

import requests

API = "https://api.notion.com/v1"
VERSION = "2025-09-03"


class Notion:
    def __init__(self, token: str):
        self.s = requests.Session()
        self.s.headers.update({
            "Authorization": f"Bearer {token}",
            "Notion-Version": VERSION,
            "Content-Type": "application/json",
        })

    def _req(self, method, path, **kw):
        for attempt in range(4):
            r = self.s.request(method, API + path, timeout=30, **kw)
            if r.status_code == 429:
                time.sleep(float(r.headers.get("Retry-After", 2)))
                continue
            if r.status_code >= 400:
                raise RuntimeError(f"Notion {method} {path} {r.status_code}: {r.text[:300]}")
            return r.json()
        raise RuntimeError("Notion rate limit 초과")

    def query(self, data_source_id: str, filter_: dict | None = None) -> list[dict]:
        results, cursor = [], None
        while True:
            body = {"page_size": 100}
            if filter_:
                body["filter"] = filter_
            if cursor:
                body["start_cursor"] = cursor
            data = self._req("POST", f"/data_sources/{data_source_id}/query", json=body)
            results += data["results"]
            if not data.get("has_more"):
                return results
            cursor = data["next_cursor"]

    def blocks(self, page_id: str) -> list[dict]:
        out, cursor = [], None
        while True:
            q = "?page_size=100" + (f"&start_cursor={cursor}" if cursor else "")
            data = self._req("GET", f"/blocks/{page_id}/children{q}")
            out += data["results"]
            if not data.get("has_more"):
                return out
            cursor = data["next_cursor"]

    def update(self, page_id: str, props: dict):
        return self._req("PATCH", f"/pages/{page_id}", json={"properties": props})


# ---- 속성 헬퍼 ---------------------------------------------------------------
def text(page: dict, name: str) -> str:
    p = page["properties"].get(name)
    if not p:
        return ""
    t = p["type"]
    if t in ("rich_text", "title"):
        return "".join(x.get("plain_text", "") for x in p[t])
    if t == "select":
        return (p["select"] or {}).get("name", "")
    if t == "url":
        return p["url"] or ""
    if t == "date":
        return (p["date"] or {}).get("start", "")
    return ""


def rich(value: str) -> dict:
    # 노션 rich_text 조각은 2000자 제한
    chunks = [value[i:i + 1900] for i in range(0, len(value), 1900)] or [""]
    return {"rich_text": [{"type": "text", "text": {"content": c}} for c in chunks]}


def select(name: str) -> dict:
    return {"select": {"name": name}}


def url(value: str | None) -> dict:
    return {"url": value or None}
