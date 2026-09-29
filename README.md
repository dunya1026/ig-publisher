# 인스타그램 카드뉴스 자동 게시 (ig-publisher)

노션 "네이버 블로그 발행 큐"에 쌓이는 원고를 1080×1350 카드뉴스 캐러셀로 만들어 인스타그램에 자동 게시합니다.
GitHub Actions에서 돌아가므로 PC가 꺼져 있어도 되고, 비용은 무료입니다(공개 저장소 기준).

## 흐름

```
05:50  Claude 예약 작업: 블로그 원고 + '인스타슬라이드' 문구 작성 → 노션 (상태=발행대기, 인스타상태=인스타대기)
07/12/16시  Mac 매크로: 네이버 블로그 발행 → 상태=발행완료
매시 7분  GitHub Actions: 발행완료 + 인스타대기 + 오늘 작성 + 게시 시각 지난 원고
           → 카드 이미지 생성 → ig-cards 브랜치에 업로드(공개 URL) → Instagram Graph API 캐러셀 게시
           → 인스타상태=인스타완료, 인스타URL 기록 (실패 시 인스타실패 + 인스타오류)
```

기본 게시 시각: 부동산 08시, 금융 13시, 생활꿀팁 17시 (블로그 발행 1시간 뒤). `IG_SLOTS`로 바꿀 수 있습니다.

### 안전장치
- 블로그가 **발행완료**된 원고만 올립니다. 블로그에서 보류하면 인스타도 자동으로 안 나갑니다.
- **작성일이 오늘**인 원고만 올립니다. 밀린 원고가 한꺼번에 쏟아지지 않습니다.
- 한 번 실행에 1건, 하루 최대 3건(`IG_MAX_PER_DAY`).
- 인스타만 막고 싶으면 노션에서 '인스타상태'를 **인스타제외**로 바꾸세요.

## 노션 속성 (이미 추가됨)

| 속성 | 유형 | 설명 |
|---|---|---|
| 인스타상태 | 선택 | 인스타대기 / 인스타발행중 / 인스타완료 / 인스타실패 / 인스타제외 |
| 인스타슬라이드 | 텍스트 | 카드 문구 (아래 형식). 비어 있으면 블로그 본문의 목록에서 자동 추출 |
| 인스타캡션 | 텍스트 | 비워두면 자동 작성 (부제 + 핵심 4줄 + 안내 + 면책 + 해시태그 15개) |
| 인스타URL | URL | 게시 후 인스타 링크 |
| 인스타오류 | 텍스트 | 실패 사유 |

인스타슬라이드 형식:

```
표지: 앞줄 제목 / 뒷줄 제목
부제: 한 줄 요약
## 슬라이드 제목
- 항목: 내용
## 체크포인트
1. 항목: 설명
정리: 마지막 장 한 문장
```

---

## 설치 (처음 한 번, 약 30~40분)

### 1. GitHub 저장소 만들기
1. github.com → New repository → 이름 예: `ig-publisher` → **Public** 선택
   (카드 이미지를 인스타 서버가 가져갈 수 있어야 해서 공개여야 합니다. 토큰은 Secrets에 저장되어 공개되지 않습니다.)
2. 이 폴더의 파일을 전부 업로드합니다 (`.github/workflows/instagram.yml` 포함).
   웹에서 올릴 때 `.github` 폴더가 빠지기 쉬우니, Add file → Create new file에서 경로를 `.github/workflows/instagram.yml`로 입력해 내용을 붙여 넣어도 됩니다.
3. Settings → Actions → General → Workflow permissions → **Read and write permissions** 선택 → Save.

### 2. 노션 연동 토큰
1. https://www.notion.so/profile/integrations → 새 API 통합 → 이름 `ig-publisher` → 내부 통합으로 만들기 → **시크릿 복사**
   (블로그 매크로용 통합이 이미 있으면 그 토큰을 재사용해도 됩니다.)
2. 노션에서 "네이버 블로그 발행 큐" DB 열기 → 오른쪽 위 `···` → 연결 → 방금 만든 통합 추가.
3. Data source ID: `c3c17f02-2da9-47b3-ac6c-63eeedce32b9`

### 3. 인스타그램 토큰 (Meta 개발자)
전제: 인스타그램 **비즈니스/크리에이터 계정**이 **페이스북 페이지**에 연결되어 있어야 합니다.

1. https://developers.facebook.com → 내 앱 → 앱 만들기 → 유형 **비즈니스** (또는 사용 사례에서 "Instagram에서 메시지·콘텐츠 관리") → 앱 생성.
2. 앱 대시보드에서 **Instagram** 제품 추가 → "Facebook 로그인을 통한 API 설정" 선택.
3. **Graph API 탐색기**(도구 → Graph API Explorer) 열기
   - Meta App: 방금 만든 앱 선택
   - User or Page: 사용자 토큰 가져오기
   - 권한 추가: `instagram_basic`, `instagram_content_publish`, `pages_show_list`, `pages_read_engagement`, `business_management`
   - Generate Access Token → 로그인 창에서 인스타와 연결된 **페이지를 선택**하고 허용
4. **장기 토큰으로 바꾸기**: 액세스 토큰 디버거(도구 → Access Token Debugger)에 토큰 붙여넣기 → 아래 "Extend Access Token" → 새 토큰 복사(60일짜리 사용자 토큰).
5. 탐색기에서 방금 받은 장기 토큰으로 `GET me/accounts` 실행 → 결과의 페이지 `access_token`과 `id` 복사.
   → 이 **페이지 토큰은 만료되지 않습니다**. 디버거에서 "Expires: Never"인지 확인하세요. 이것이 `IG_ACCESS_TOKEN`입니다.
6. 탐색기에서 `GET {페이지id}?fields=instagram_business_account` 실행 → 나온 `id`가 `IG_USER_ID`입니다.

> 앱은 "개발 모드"로 두어도 됩니다. 앱 관리자 본인 계정에 게시하는 용도라 앱 검수가 필요 없습니다.

### 4. GitHub Secrets·Variables 등록
저장소 Settings → Secrets and variables → Actions

**Secrets** (New repository secret)

| 이름 | 값 |
|---|---|
| NOTION_TOKEN | 2단계 노션 시크릿 |
| NOTION_DATA_SOURCE_ID | c3c17f02-2da9-47b3-ac6c-63eeedce32b9 |
| IG_USER_ID | 3-6단계 id |
| IG_ACCESS_TOKEN | 3-5단계 페이지 토큰 |

**Variables** (Variables 탭, 선택)

| 이름 | 예시 | 설명 |
|---|---|---|
| IG_HANDLE | @내계정 | 카드 하단에 표시 |
| IG_SLOTS | 부동산=8,금융=13,생활꿀팁=17 | 분야별 게시 시각(KST 시) |
| IG_MAX_PER_DAY | 3 | 하루 최대 게시 수 |
| IG_HASHTAG_COUNT | 15 | 캡션 해시태그 수(최대 30) |

### 5. 테스트
1. Actions 탭 → instagram-publish → **Run workflow** → `dry_run` 체크 → 실행
   → 끝나면 실행 화면 아래 Artifacts의 `cards-preview`를 받아 이미지·caption.txt 확인.
   (dry-run도 오늘 발행완료 + 인스타대기 원고가 있어야 결과가 나옵니다. 특정 원고로 보려면 `page`에 노션 페이지 ID 입력)
2. 실제 게시 테스트: `page`에 원고 페이지 ID를 넣고 dry_run 해제 → 실행 → 인스타에 올라왔는지, 노션에 인스타완료·인스타URL이 찍혔는지 확인.
   노션 페이지 ID는 페이지 주소 끝의 32자리입니다.
3. 이후로는 매시 7분에 자동 실행됩니다.

## 매일 운영

| 하고 싶은 것 | 방법 |
|---|---|
| 인스타만 막기 | 인스타상태 → 인스타제외 |
| 카드 문구 고치기 | 게시 전에 인스타슬라이드 수정 |
| 지난 원고 올리기 | Actions → Run workflow → page에 ID 입력 |
| 실패 재시도 | 인스타오류 확인 → 인스타상태를 인스타대기로 → 다음 정시에 재시도 (오늘 작성분만) 또는 page 지정 실행 |

## 문제 해결

- **인스타오류에 code 190 / OAuthException**: 토큰 만료·권한 해제. 3단계를 다시 해서 IG_ACCESS_TOKEN 교체.
- **이미지를 가져오지 못함(2207052 등)**: 저장소가 Public인지, Workflow permissions가 Read and write인지 확인.
- **"게시할 원고 없음"만 반복**: 블로그 상태가 발행완료인지, 작성일이 오늘인지, 인스타상태가 인스타대기인지, 게시 시각(IG_SLOTS)이 지났는지 확인.
- **글자가 네모로 깨짐**: 워크플로의 "한글 폰트 설치" 단계가 실패하지 않았는지 확인.
- **게시 한도**: 인스타 API는 24시간에 100건까지(캐러셀 1건으로 계산). 이 설정(하루 3건)으로는 걸리지 않습니다.
- GitHub Actions 예약 실행은 몇 분~수십 분 늦어질 수 있습니다.

## 내 PC에서 미리보기 (선택)

```bash
pip install -r requirements.txt
export NOTION_TOKEN=... NOTION_DATA_SOURCE_ID=c3c17f02-2da9-47b3-ac6c-63eeedce32b9 IG_HANDLE=@내계정
python -m ig_publisher.main --dry-run            # out/ 폴더에 이미지·캡션 생성
python -m ig_publisher.main --dry-run --page <페이지ID>
```
Mac에서 한글 폰트는 Apple SD Gothic Neo를 자동으로 씁니다. Noto Sans KR을 쓰려면 `FONT_DIR`에 폰트 폴더를 지정하세요.

## 파일 구성

```
.github/workflows/instagram.yml   예약 실행(매시 7분, KST 08~19시)
ig_publisher/main.py              선정 규칙·캡션·전체 흐름
ig_publisher/slides.py            인스타슬라이드/블로그 본문 → 슬라이드 구성
ig_publisher/render.py            카드 이미지 그리기 (Pillow)
ig_publisher/hosting.py           ig-cards 브랜치 업로드 → 공개 URL
ig_publisher/instagram.py         Graph API 캐러셀 게시
ig_publisher/notion.py            노션 API
```
