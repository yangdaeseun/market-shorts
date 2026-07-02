# 🌍 글로벌 야간 시황 숏츠 — 무인 자동 발행 시스템

밤사이 전 세계 시장(미국 3대 지수·비트코인·유가·금·환율·금리·뉴스)을
**자동 수집 → AI가 "왜 올랐고 왜 떨어졌나" 분석 → Toss 스타일 영상 →
유튜브 쇼츠 자동 업로드**. 한 번 세팅하면 매일 새벽 사람 손 없이 돕니다.

```
수집 → 분석 → [품질게이트·자동 재생성] → 슬라이드 렌더 → 더빙 → SEO → 영상 → 업로드 → 학습로그
```

---

## 핵심 설계 (왜 이렇게 만들었나)

전에 막혔던 4가지를 전부 구조로 해결했습니다.

| 예전 스트레스 | 이 시스템의 해결 |
|---|---|
| PIL로 그려서 퀄리티 한계 + 글자 길면 깨짐 | **HTML+CSS 고정 템플릿 + Playwright** — 내용 길이 무관 항상 같은 퀄리티 |
| 일회성 배치 → 매번 손으로 실행 | **GitHub Actions cron** — PC 꺼져 있어도 매일 자동 |
| 깨져도 알 수가 없음 | **품질게이트 자동 채점 + 텔레그램 알림** — 미달이면 재생성, 끝내 미달이면 비공개 보류 |
| 숫자만 나열 (차별점 없음) | **AI 인과 분석** — "왜?"를 짚는 시그니처 슬라이드 |

폰트(Pretendard)까지 패키지에 내장 → 어느 PC, 어느 서버에서 돌려도 **똑같은 결과**.

---

## 30분 세팅 (한 번만)

### 1. GitHub 저장소 만들기
이 폴더 전체를 새 저장소에 올립니다 (Private 권장).

### 2. Gemini API 키
[Google AI Studio](https://aistudio.google.com/apikey)에서 무료 키 발급.

### 3. 유튜브 업로드 토큰 (1회)
PC에서:
```bash
pip install google-auth-oauthlib
# auth/client_secret.json 준비 (auth/get_youtube_token.py 주석 참고)
python auth/get_youtube_token.py
```
출력된 `YT_CLIENT_ID / YT_CLIENT_SECRET / YT_REFRESH_TOKEN` 3개 값을 복사.

### 4. GitHub Secrets 등록
저장소 → **Settings → Secrets and variables → Actions → New repository secret**
- `GEMINI_API_KEY`
- `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN`
- (선택) `ELEVENLABS_API_KEY` — 더 좋은 음성 원할 때
- (선택) `TELEGRAM_TOKEN`, `TELEGRAM_CHAT` — 완료/실패 알림

### 5. 첫 테스트
Actions 탭 → `daily-market-shorts` → **Run workflow** 버튼으로 수동 실행.
처음엔 `config.yaml`의 `publish.privacy: private`로 두고 결과 확인 후 `public`으로.

끝. 이후엔 매일 새벽 자동 발행됩니다.

---

## 내 PC에서 직접 돌려보기 (선택)

```bash
pip install -r requirements.txt
python -m playwright install chromium

python run.py --mock        # 인터넷 없이 목데이터로 영상까지 (업로드 X)
python run.py --no-upload   # 실데이터로 생성만
python run.py               # 실데이터 → 생성 → 업로드 (토큰 필요)
```
결과물: `data/short.mp4`, 슬라이드 `data/slides/*.png`

---

## 매일 바꾸고 싶을 때는 `config.yaml` 만

- 발행 시각: `publish.hour_kst`
- 색/톤: `design.up_color` `down_color` `bg`
- 음성: `voice.edge_voice` (남=InJoon, 여=SunHi)
- 종목 추가/삭제: `markets.*`
- 슬라이드 길이: `video.seconds_per_slide`
- 품질 기준: `quality.min_score`

**코드는 건드릴 필요 없습니다.**

---

## 폴더 구조
```
config.yaml            모든 설정 (여기만 만짐)
run.py                 전체 실행 (오케스트레이터)
pipeline/
  collect.py           수집 (yfinance·CoinGecko·RSS)
  analyze.py           AI 인과 분석 (Gemini, 고정 스키마)
  render.py            슬라이드 PNG (HTML+CSS+Playwright)
  tts.py               더빙 (edge-tts 무료 / ElevenLabs)
  make_video.py        영상 합성 (ffmpeg, 줌·페이드·BGM)
  quality_gate.py      자동 채점
  seo.py               제목·설명·태그·고정댓글
  upload.py            유튜브 업로드
  learn.py             성과 로그·베스트 패턴
templates/             디자인 (base.css, slide.html, Pretendard 내장)
auth/                  유튜브 토큰 발급 헬퍼
assets/                bgm.mp3 (선택)
.github/workflows/     매일 자동 실행 cron
```

---

## 참고
- 영상에 자막이 따로 필요 없게, **슬라이드 자체가 큰 글씨 자막** 역할을 합니다.
- 데이터 일부가 수집 실패해도 'N/A'로 두고 나머지로 진행 (하루도 안 끊김).
- 투자 권유 아님 문구가 설명란에 자동 포함됩니다.
