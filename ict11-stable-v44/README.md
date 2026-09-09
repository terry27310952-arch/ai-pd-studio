# ICT11 v4.4 Smooth Native Stable

이 패치는 기존 `KIYOSAKI_ICT11_WEB_v4_3_ULTRALITE_24FPS` 압축을 푼 폴더의 `OPEN_DIRECT.html`을 자동으로 안정화합니다.

## 사용법
1. 기존 v4.3 ZIP 압축을 풉니다.
2. `PATCH_AND_RUN.bat`을 그 폴더 안에 넣습니다.
3. 더블클릭합니다.
4. 기존 `OPEN_DIRECT.html`은 자동 백업되고, 패치된 플레이어가 바로 실행됩니다.

## 바뀌는 점
- 24fps 메인 프레임 제한 제거
- 12fps B-roll transform 제한 제거
- 실제 B-roll은 브라우저 네이티브 FPS 그대로 재생
- 줌/팬은 CSS GPU transition으로 처리
- AI 시장 씬 30fps
- 현재 영상 + 다음 영상만 유지
- 다음 영상은 현재 컷 시작 즉시 `preload=auto`
- `canplay` 확인 후 컷 전환
- 자막 모션 7종과 transition FX 유지
- 기존 B-roll source_id 중복 0 유지

## 원복
같은 폴더에 자동 생성되는 `OPEN_DIRECT.v43.backup.YYYYMMDD_HHMMSS.html`을 `OPEN_DIRECT.html`로 이름 변경하면 됩니다.
