# 브랜딩 개발 방향

## 1. 큰 방향

브랜딩은 앱 개발과 병행해 구체화한다. 초기에는 특정 이름을 고정하지 않고, 앱 설정값으로 브랜드명·캐릭터명·슬로건을 분리해 테스트 가능하게 둔다.

## 2. 유지할 감성

- 묘한 여자애
- 시크한 관찰자
- 커뮤니티 썰을 읽는 캐릭터
- 관계 패턴을 보는 캐릭터
- 사람들이 놓친 타이밍과 반복 구조를 잡아내는 해설자
- 사주와 점성술은 전면 브랜드가 아니라 숨은 인사이트 도구

## 3. 버릴 방향

- 대놓고 사주 사이트
- Fortune teller 채널
- Astrology girl 채널
- 점집 캐릭터
- 한국식 운세 풀이 사이트
- 원문 읽어주는 단순 사연 채널

## 4. 해외 시청자용 표현 전략

사주/점성술 표현을 직접 쓰지 않고, 아래 표현으로 치환한다.

```text
사주 → pattern
운 → timing
궁합 → emotional compatibility
도화 → attraction energy
대운 → life chapter
업보 → karma pattern
반복 선택 → repeating pattern
```

## 5. 핵심 브랜드 문장 후보

```text
She reads stories. She sees patterns.
```

```text
Most people saw drama. She saw the pattern.
```

```text
Every story leaves a signal.
```

```text
Stories have patterns.
```

## 6. 캐릭터명 후보

- Mira
- Vela
- Iris
- Nara
- Lyra
- Vera
- Sera
- Liora

현재 1차 후보는 Mira, Vela, Iris다.

## 7. 채널명 후보

- Mira Files
- Vela Reads
- Iris Files
- The Pattern Room
- Story Oracle
- The Story Decoder
- Hidden Pattern
- Red Flag Reader
- Karma Files
- The Story Vault
- She Saw the Pattern

## 8. 앱명 후보

- Story Pattern Lab
- Viral Story Lab
- Story Scanner
- Story Engine
- Pattern Lab
- StoryForge
- Red Flag Lab
- Drama Scanner

## 9. 임시 추천 조합

```text
앱명: Story Pattern Lab
채널명: Mira Files
캐릭터명: Mira
슬로건: She sees the pattern.
```

## 10. UI 톤

- 배경: 딥 네이비 / 블랙 퍼플
- 포인트: 보라색, 청록색
- 느낌: 심야 분석실, 사건 파일, 관계 패턴 실험실
- 캐릭터: 검은 머리, 보라 브릿지, 초록 눈을 가진 시크한 여성 관찰자

## 11. 대본 내 캐릭터 개입 방식

캐릭터는 사주를 설명하는 사람이 아니라, 사람들이 놓친 패턴을 말하는 사람이다.

예시:

```text
Most people will focus on the cheating.
But that is not the real pattern here.
The real pattern is how he made her doubt herself every time she noticed the truth.
```

## 12. 브랜딩 테스트 방식

MVP에서 브랜드 설정을 아래처럼 분리한다.

```json
{
  "brandName": "Story Pattern Lab",
  "channelName": "Mira Files",
  "characterName": "Mira",
  "tagline": "She sees the pattern.",
  "tone": "mysterious, sharp, friendly",
  "primaryColor": "dark-purple",
  "accentColor": "teal"
}
```

이 설정을 기반으로 앱 UI, 대본 생성 프롬프트, 결과 문구를 변경 가능하게 둔다.
