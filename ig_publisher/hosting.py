"""카드 이미지를 공개 URL로 올리기.

GitHub 저장소(공개)의 전용 브랜치 `ig-cards`에 이번 게시물 이미지만 강제 푸시하고
raw.githubusercontent.com 주소를 돌려줍니다. 매번 브랜치를 덮어쓰므로 저장소 용량이 늘지 않습니다.
(인스타그램은 게시 시점에 이미지를 복사해 가므로, 다음 실행 때 지워져도 문제 없음)

필요 환경변수 (GitHub Actions)
  GITHUB_REPOSITORY  : 자동 설정 (owner/name)
  GITHUB_TOKEN       : 워크플로에서 secrets.GITHUB_TOKEN 전달, contents: write 권한
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import requests

BRANCH = os.environ.get("CARDS_BRANCH", "ig-cards")


def _git(*args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def publish_to_github(paths: list[Path]) -> list[str]:
    repo = os.environ["GITHUB_REPOSITORY"]
    token = os.environ["GITHUB_TOKEN"]
    stamp = time.strftime("%Y%m%d%H%M%S")
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp) / stamp
        folder.mkdir()
        names = []
        for p in paths:
            shutil.copy(p, folder / Path(p).name)
            names.append(f"{stamp}/{Path(p).name}")
        _git("init", "-q", cwd=tmp)
        _git("checkout", "-q", "-b", BRANCH, cwd=tmp)
        _git("config", "user.name", "ig-publisher-bot", cwd=tmp)
        _git("config", "user.email", "ig-publisher-bot@users.noreply.github.com", cwd=tmp)
        _git("add", ".", cwd=tmp)
        _git("commit", "-q", "-m", f"cards {stamp}", cwd=tmp)
        remote = f"https://x-access-token:{token}@github.com/{repo}.git"
        _git("push", "-q", "-f", remote, f"{BRANCH}:{BRANCH}", cwd=tmp)

    urls = [f"https://raw.githubusercontent.com/{repo}/{BRANCH}/{n}" for n in names]
    for u in urls:  # 공개 URL이 실제로 열리는지 확인 (최대 2분)
        for _ in range(24):
            try:
                r = requests.head(u, timeout=10)
                if r.status_code == 200:
                    break
            except requests.RequestException:
                pass
            time.sleep(5)
        else:
            raise RuntimeError(f"이미지 URL이 열리지 않습니다: {u}")
    return urls
