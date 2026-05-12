import os

SOURCE_FILE = os.path.join(os.path.dirname(__file__), "pd_app_pipeline_v12.py")
with open(SOURCE_FILE, "r", encoding="utf-8") as f:
    source = f.read()

source = source.replace(
    'APP_TITLE = "AI PD Studio V12"',
    'APP_TITLE = "AI PD Studio V12 Ref"',
)
source = source.replace(
    'APP_SUBTITLE = "카드뉴스 원고 확정 → 텍스트 포함 카드 프롬프트 → 쇼츠/롱폼 내레이션 + 클린 이미지 프롬프트"',
    'APP_SUBTITLE = "레퍼런스형 1:1 카드뉴스 커버 · 쇼츠/롱폼 내레이션 · 클린 이미지 프롬프트"',
)

insert = """

카드뉴스 첫 장 레퍼런스 디자인 방향:
- 모든 카드뉴스 이미지 프롬프트는 1:1 square ratio를 기본 전제로 한다.
- 첫 장은 릴스/인스타 카드뉴스 커버처럼 강한 한 문장 중심으로 설계한다.
- 참고 스타일 A: 강한 단색 배경, 흑백 인물 사진, 초대형 굵은 산세리프 한글 헤드라인, 밑줄/구분선, 작은 보조 문장, 하단 출처 표기.
- 참고 스타일 B: 인물 클로즈업 혹은 반신 사진 위에 어두운 그라데이션을 얹고, 흰색 대형 헤드카피와 일부 강조색 블록을 사용한다.
- 참고 스타일 C: 자료사진/인터뷰컷/빈티지 사진처럼 보이는 현실감 있는 이미지 위에 2~4줄의 큼직한 한글 카피를 배치한다.
- 헤드카피는 화면의 35~55%를 차지할 정도로 크게, 바디카피는 짧게, 출처는 작고 흐리게 배치한다.
- 브랜드 로고가 필요하면 임의 생성하지 말고 작은 텍스트 라벨 또는 빈 영역 지시만 사용한다.
- 인물은 고품질 사진 느낌으로 표현할 수 있다. 사람 표현을 일부러 만화화하거나 흐리게 만들지 않는다.
- 카드뉴스 negative_prompt에는 watermark, broken Korean text, random logo, distorted hands, low quality 위주로만 넣는다.
- 카드뉴스 negative_prompt에 human realism 자체를 막는 문구를 넣지 않는다.
"""

source = source.replace(
    "카드뉴스 이미지 프롬프트 규칙:\n- full_card_prompt_with_text에는 실제 카드에 들어갈 한국어 헤드카피, 바디카피, 출처 각주 텍스트까지 포함한다.",
    "카드뉴스 이미지 프롬프트 규칙:\n- 카드뉴스 이미지는 항상 1:1 square ratio로 제작한다.\n- full_card_prompt_with_text에는 실제 카드에 들어갈 한국어 헤드카피, 바디카피, 출처 각주 텍스트까지 포함한다." + insert,
)
source = source.replace(
    "- 단, 워터마크, 깨진 글자, 임의 로고, 실존 인물 정확한 얼굴 재현은 피한다.",
    "- 단, 워터마크, 깨진 글자, 임의 로고, 왜곡된 손, 저품질 표현은 피한다. 인물은 고품질 사진 느낌으로 표현할 수 있다.",
)
source = source.replace('"image_ratio": ratio,', '"image_ratio": "1:1 square card news",')
source = source.replace("비율:{ratio}", "비율:1:1 square card news")
source = source.replace(
    "카드뉴스는 텍스트 포함 이미지 프롬프트, 쇼츠/롱폼은 내레이션과 클린 이미지 프롬프트만 산출합니다.",
    "카드뉴스는 1:1 커버형 텍스트 포함 이미지 프롬프트, 쇼츠/롱폼은 내레이션과 클린 이미지 프롬프트만 산출합니다.",
)

exec(compile(source, SOURCE_FILE, "exec"), globals())
