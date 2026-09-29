"""Instagram Graph API 캐러셀 게시.

공식 문서: https://developers.facebook.com/docs/instagram-platform/content-publishing
- 이미지는 JPEG, 공개 URL이어야 함 (Meta 서버가 직접 내려받음)
- 캐러셀 최대 10장, 24시간 동안 API 게시 100건 제한(캐러셀은 1건)
"""
from __future__ import annotations

import time

import requests


class InstagramError(RuntimeError):
    pass


class Instagram:
    def __init__(self, ig_user_id: str, token: str, version: str = "v25.0",
                 host: str = "graph.facebook.com"):
        self.base = f"https://{host}/{version}"
        self.ig = ig_user_id
        self.token = token

    def _post(self, path, **params):
        params["access_token"] = self.token
        r = requests.post(f"{self.base}/{path}", data=params, timeout=60)
        data = r.json()
        if r.status_code >= 400 or "error" in data:
            raise InstagramError(f"POST {path}: {data.get('error', data)}")
        return data

    def _get(self, path, **params):
        params["access_token"] = self.token
        r = requests.get(f"{self.base}/{path}", params=params, timeout=60)
        data = r.json()
        if r.status_code >= 400 or "error" in data:
            raise InstagramError(f"GET {path}: {data.get('error', data)}")
        return data

    def _wait(self, container_id, timeout=180):
        end = time.time() + timeout
        while time.time() < end:
            st = self._get(container_id, fields="status_code,status").get("status_code")
            if st == "FINISHED":
                return
            if st in ("ERROR", "EXPIRED"):
                raise InstagramError(f"컨테이너 {container_id} 상태 {st}")
            time.sleep(4)
        raise InstagramError(f"컨테이너 {container_id} 처리 시간 초과")

    def publish_carousel(self, image_urls: list[str], caption: str) -> tuple[str, str]:
        if not 2 <= len(image_urls) <= 10:
            raise InstagramError(f"캐러셀은 2~10장이어야 합니다(현재 {len(image_urls)}장)")
        children = []
        for u in image_urls:
            c = self._post(f"{self.ig}/media", image_url=u, is_carousel_item="true")
            children.append(c["id"])
        for c in children:
            self._wait(c)
        parent = self._post(f"{self.ig}/media", media_type="CAROUSEL",
                            children=",".join(children), caption=caption)
        self._wait(parent["id"])
        media = self._post(f"{self.ig}/media_publish", creation_id=parent["id"])
        permalink = self._get(media["id"], fields="permalink").get("permalink", "")
        return media["id"], permalink

    def quota_usage(self) -> int:
        """최근 24시간 API 게시 건수."""
        data = self._get(f"{self.ig}/content_publishing_limit", fields="quota_usage")
        return (data.get("data") or [{}])[0].get("quota_usage", 0)
