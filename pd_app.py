import csv
import io
import json
import os
import re
from datetime import datetime
from typing import Any, Dict, List

import streamlit as st
from openai import OpenAI

APP_TITLE = "AI PD Studio"
APP_SUBTITLE = "레퍼런스의 흥행 문법을 분해하고, AI PD 사고루프로 다시 쓰는 콘텐츠 생성기"

st.set_page_config(page_title=APP_TITLE, page_icon="🎬", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
.main .block-container { padding-top: 2rem; max-width: 1360px; }
.hero-card { padding: 1.35rem 1.5rem; border: 1px solid rgba(120,120,120,.18); border-radius: 22px; background: linear-gradient(135deg, rgba(120,120,255,.12), rgba(255,255,255,.03)); }
.small-muted { color: #888; font-size: .92rem; }
</style>
""", unsafe_allow_html=True)

PD_BRAIN_SYSTEM = """
너는 단순 생성기가 아니라 한국어 숏폼/카드뉴스 콘텐츠 총괄 PD 사고엔진이다.
너의 임무는 레퍼런스를 요약하는 것이 아니라, 레퍼런스의 흥행 문법을 해부하고 새 콘텐츠를 끝까지 보게 만드는 것이다.

반드시 내부적으로 다음 사고 절차를 거친 뒤 JSON으로만 출력한다.
1. 입력값 의심: 레퍼런스가 실제로 팔고 싶은 감정, 욕망, 불안, 논쟁을 찾는다.
2. 팩트/앵글 뱅크: 추상어 대신 구체명사, 이해관계, 충돌, 사례, 체크포인트를 만든다. 실시간 사실확인은 하지 못하므로 불확실한 것은 '확인 필요'로 표시한다.
3. 후킹 전쟁실: 약한 오프닝 10개를 버리고 가장 강한 후킹 구조를 고른다.
4. 내러티브 설계: 정보 나열 금지. 갈등 → 반전 → 해석 → 체크포인트 → 행동 구조로 배열한다.
5. 장면 감독: 아이콘/다이어그램/미래도시 같은 추상 화면 금지. 실제 촬영 가능하거나 AI 영상으로 구체화 가능한 장면으로 쓴다.
6. 비평과 재작성: 발표자료 말투, 추상어, 뻔한 CTA, 시청 포기 구간을 제거하고 다시 쓴다.

금지 표현:
- 살펴보겠습니다
- 주목받고 있습니다
- 중요한 영향을 미칠 것입니다
- 균형 잡힌 시각이 필요합니다
- 미래 산업에 기회가 있습니다
- 최신 정보를 확인하세요
- 관련 아이콘
- 깔끔한 다이어그램
- 미래 도시 이미지
- 그래픽 아이콘

숏폼 원칙:
- 첫 문장은 질문보다 주장/충격/반전이어야 한다.
- 매 컷에는 구체명사 하나 이상이 있어야 한다.
- 시청자가 댓글 달 만한 논쟁 지점을 포함한다.
- CTA는 자연스러운 다음 행동이어야지 구독 구걸이 되면 안 된다.
- 영상 화면은 '무엇이 보이는지'가 아니라 '무슨 일이 벌어지는지'로 쓴다.

반드시 JSON만 출력한다.
"""

SHORTS_DOCTOR_SYSTEM = """
너는 1분 숏폼 전문 작가이자 숏폼 리텐션 PD다.
입력된 패키지의 one_minute_shorts만 냉정하게 갈아엎는다.
카드뉴스식 설명, 발표자료식 문장, 추상적 화면, 약한 CTA를 모두 제거한다.

반드시 지켜라.
1. 0-3초 첫 문장은 강한 주장, 반전, 충격적 해석 중 하나여야 한다. 질문으로 시작해도 되지만 매우 날카로워야 한다.
2. 7~9컷으로 구성한다. 각 컷은 앞 컷보다 더 구체적이어야 한다.
3. 각 컷의 내레이션은 1~2문장, 구어체, 짧은 호흡으로 쓴다.
4. '살펴보겠습니다', '중요합니다', '영향을 미칠 것입니다', '신중한 접근' 같은 말은 금지한다.
5. visual은 아이콘/다이어그램이 아니라 실제 장면, 오브젝트, 인물, 화면, 사건으로 쓴다.
6. edit_point에는 실제 편집자가 쓸 수 있는 줌, 컷인, 사운드, 자막 타이밍을 쓴다.
7. image_prompt와 video_prompt에는 사용자가 선택한 image_ratio를 반영한다.
8. video_prompt.english_prompt는 반드시 camera movement로 시작한다.
9. 투자/건강/의학/법률 주제는 확정적 보장 표현을 피하고, 대신 시나리오/체크포인트로 말한다.
10. 반드시 JSON만 출력한다.
"""

CARDNEWS_DOCTOR_SYSTEM = """
너는 한국 커뮤니티 인기글 감각을 가진 카드뉴스 전문 편집자다.
입력된 패키지의 card_news만 냉정하게 다시 쓴다.
목표는 예쁜 정리본이 아니라, 독자가 첫 장에서 멈추고 저장하거나 공유하고 싶게 만드는 카드뉴스다.

반드시 지켜라.
1. 정보 요약체, 강의체, 보고서체를 금지한다.
2. 각 장의 헤드라인은 독자의 변명, 불안, 욕망, 자기합리화 중 하나를 찌른다.
3. 본문은 짧고 날카롭게 쓴다. 한 장에는 한 감정만 넣는다.
4. '중요합니다', '필요합니다', '성공 공식', '첫걸음', '핵심입니다'처럼 죽은 표현을 금지한다.
5. 레퍼런스의 고유 표현을 무조건 살리지 말고, 약하면 버린다.
6. 1장은 공감/충격 후킹, 2장은 문제 정의, 중반은 구체적 원인/구조, 후반은 전환/해결, 마지막 장은 행동 유도로 구성한다.
7. headline은 20자 내외로 강하게 쓴다. body는 2~3문장 이내로 쓴다.
8. image_direction은 추상 그래픽보다 실제 장면/오브젝트/감정 장면 중심으로 쓴다.
9. image_prompt_en에는 사용자가 선택한 image_ratio를 반영한다.
10. 반드시 JSON만 출력한다.
"""

FINAL_SCHEMA = {
    "auto_brief": {"topic":"", "target":"", "platform":"", "tone":"", "goal":"", "cta":"", "image_ratio":"", "forbidden":[], "risk_notes":[]},
    "pd_brain": {
        "real_intent":"", "viewer_desire":"", "viewer_anxiety":"", "conflict":"", "contrarian_claim":"", "comment_trigger":"",
        "fact_angle_bank":{"concrete_entities":[], "stakes":[], "tensions":[], "questions":[], "checkpoints":[], "needs_verification":[]},
        "hook_war_room":{"rejected_hooks":[], "selected_hook":"", "why_selected":""},
        "weakness_removed":[]
    },
    "one_minute_shorts": {"title":"", "core_claim":"", "scenes":[{"time":"", "narration":"", "caption":"", "visual":"", "edit_point":"", "image_prompt":{"korean_direction":"", "english_prompt":"", "negative_prompt":""}, "video_prompt":{"korean_direction":"", "english_prompt":""}}]},
    "card_news": [{"page":1, "headline":"", "body":"", "design_mood":"", "image_direction":"", "image_prompt_en":"", "key_caption":""}],
    "thumbnail_copy": [], "titles": [], "hashtags": [], "production_checklist": [],
    "quality": {"hook_score":0, "specificity_score":0, "conflict_score":0, "scene_score":0, "production_ready_score":0, "revision_notes":[]}
}

def get_secret(name: str) -> str:
    try:
        value = st.secrets.get(name, "")
    except Exception:
        value = ""
    return value or os.getenv(name, "")

def get_client() -> OpenAI:
    api_key = get_secret("OPENAI_API_KEY")
    if not api_key:
        st.error("OPENAI_API_KEY가 없습니다. Streamlit Secrets에 OPENAI_API_KEY를 추가해주세요.")
        st.stop()
    return OpenAI(api_key=api_key)

def extract_json(text: str) -> Dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).strip()
        text = re.sub(r"```$", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise

def call_llm(system_prompt: str, user_prompt: str, model: str, temperature: float) -> Dict[str, Any]:
    res = get_client().chat.completions.create(
        model=model,
        messages=[{"role":"system","content":system_prompt}, {"role":"user","content":user_prompt}],
        temperature=temperature,
        response_format={"type":"json_object"},
    )
    return extract_json(res.choices[0].message.content or "{}")

def build_pd_prompt(reference_text: str, output_language: str, generation_scope: str, platform_hint: str, tone_hint: str, override_topic: str, card_count: int, image_ratio: str) -> str:
    return f"""
아래 레퍼런스를 바탕으로 AI PD 사고루프를 실행하고 최종 제작 패키지를 만들어라.

사용자 선택값:
- 출력 언어: {output_language}
- 생성 범위: {generation_scope}
- 플랫폼 힌트: {platform_hint}
- 톤 힌트: {tone_hint}
- 주제 덮어쓰기: {override_topic}
- 카드뉴스 장수: {card_count}
- 이미지/영상 비율: {image_ratio}

강제 품질 기준:
1. 자동 브리프에서 주제/타겟/목표/CTA/금지표현을 레퍼런스 기반으로 추론한다.
2. auto_brief.image_ratio에 반드시 {image_ratio}를 넣는다.
3. pd_brain에 real_intent, viewer_desire, viewer_anxiety, conflict, contrarian_claim, comment_trigger를 반드시 채운다.
4. fact_angle_bank에는 구체명사를 많이 넣는다. 단, 확인되지 않은 사실은 needs_verification에 넣는다.
5. 1분 숏폼은 7~9컷으로 만들되, 각 컷은 정보 나열이 아니라 긴장 상승 구조여야 한다.
6. 내레이션은 짧고 강하게. '살펴보겠습니다' 같은 발표 말투 금지.
7. visual은 아이콘/다이어그램이 아니라 실제 장면으로 쓴다.
8. image_prompt와 video_prompt에는 {image_ratio}에 맞는 composition을 반드시 포함한다.
9. 영상 프롬프트는 영어로 쓰고 반드시 카메라 무빙으로 시작한다.
10. 마지막 quality 점수에서 85점 미만인 항목이 나오면 최종 결과를 스스로 한 번 재작성한 버전으로 출력한다.

출력 JSON 스키마 예시:
{json.dumps(FINAL_SCHEMA, ensure_ascii=False, indent=2)}

레퍼런스:
{reference_text}
"""

def build_shorts_doctor_prompt(package: Dict[str, Any], image_ratio: str) -> str:
    return f"""
아래 패키지의 one_minute_shorts만 숏폼 전문 버전으로 재작성해라.
나머지 카드뉴스, 제목, 해시태그 구조는 참고만 한다.

이미지/영상 비율: {image_ratio}

반환 JSON 형식:
{{
  "one_minute_shorts": {{
    "title": "",
    "core_claim": "",
    "scenes": [
      {{
        "time": "0-3초",
        "narration": "",
        "caption": "",
        "visual": "",
        "edit_point": "",
        "image_prompt": {{"korean_direction":"", "english_prompt":"", "negative_prompt":"text, watermark, logo"}},
        "video_prompt": {{"korean_direction":"", "english_prompt":""}}
      }}
    ]
  }},
  "quality_patch": {{
    "shorts_rewrite_reason": [],
    "shorts_hook_score": 0,
    "shorts_retention_score": 0,
    "shorts_scene_score": 0
  }}
}}

패키지:
{json.dumps(package, ensure_ascii=False, indent=2)}
"""

def build_cardnews_doctor_prompt(package: Dict[str, Any], image_ratio: str, card_count: int) -> str:
    return f"""
아래 패키지의 card_news만 카드뉴스 전문 버전으로 재작성해라.
목표는 정보 정리가 아니라 저장/공유 욕구가 생기는 카드뉴스다.

이미지 비율: {image_ratio}
카드뉴스 장수: {card_count}

반환 JSON 형식:
{{
  "card_news": [
    {{
      "page": 1,
      "headline": "",
      "body": "",
      "design_mood": "",
      "image_direction": "",
      "image_prompt_en": "",
      "key_caption": ""
    }}
  ],
  "quality_patch": {{
    "cardnews_rewrite_reason": [],
    "cardnews_hook_score": 0,
    "cardnews_save_score": 0,
    "cardnews_emotion_score": 0
  }}
}}

패키지:
{json.dumps(package, ensure_ascii=False, indent=2)}
"""

def merge_shorts_doctor(package: Dict[str, Any], doctor_result: Dict[str, Any]) -> Dict[str, Any]:
    if doctor_result.get("one_minute_shorts"):
        package["one_minute_shorts"] = doctor_result["one_minute_shorts"]
    quality = package.get("quality", {}) or {}
    quality["shorts_doctor"] = doctor_result.get("quality_patch", {})
    package["quality"] = quality
    return package

def merge_cardnews_doctor(package: Dict[str, Any], doctor_result: Dict[str, Any]) -> Dict[str, Any]:
    if doctor_result.get("card_news"):
        package["card_news"] = doctor_result["card_news"]
    quality = package.get("quality", {}) or {}
    quality["cardnews_doctor"] = doctor_result.get("quality_patch", {})
    package["quality"] = quality
    return package

def stringify_output(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)

def to_csv(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return ""
    output = io.StringIO()
    fieldnames = list(rows[0].keys())
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        writer.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v for k, v in row.items()})
    return output.getvalue()

def package_to_rows(package: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    brief = package.get("auto_brief", {}) or {}
    shorts = package.get("one_minute_shorts", {}) or {}
    for idx, scene in enumerate(shorts.get("scenes", []) or [], 1):
        rows.append({
            "type": "shorts_scene",
            "index": idx,
            "title": shorts.get("title", ""),
            "core_claim": shorts.get("core_claim", ""),
            "time": scene.get("time", ""),
            "headline_or_caption": scene.get("caption", ""),
            "body_or_narration": scene.get("narration", ""),
            "visual": scene.get("visual", ""),
            "edit_point": scene.get("edit_point", ""),
            "image_prompt": scene.get("image_prompt", {}),
            "video_prompt": scene.get("video_prompt", {}),
            "image_ratio": brief.get("image_ratio", ""),
        })
    for idx, card in enumerate(package.get("card_news", []) or [], 1):
        rows.append({
            "type": "card_news",
            "index": card.get("page", idx),
            "title": "",
            "core_claim": "",
            "time": "",
            "headline_or_caption": card.get("headline", ""),
            "body_or_narration": card.get("body", ""),
            "visual": card.get("image_direction", ""),
            "edit_point": card.get("design_mood", ""),
            "image_prompt": card.get("image_prompt_en", ""),
            "video_prompt": "",
            "image_ratio": brief.get("image_ratio", ""),
        })
    return rows

def render_auto_brief(auto_inputs: Dict[str, Any]) -> None:
    cols = st.columns(2)
    for idx, key in enumerate(["topic","target","platform","tone","goal","cta","image_ratio"]):
        with cols[idx % 2]:
            st.markdown(f"**{key}**")
            st.write(auto_inputs.get(key, ""))
    st.markdown("**금지/주의사항**")
    st.write(auto_inputs.get("forbidden", []))
    st.markdown("**리스크 노트**")
    st.write(auto_inputs.get("risk_notes", []))

def render_scene_cards(scenes: List[Dict[str, Any]]) -> None:
    for i, scene in enumerate(scenes, 1):
        with st.expander(f"컷 {i} · {scene.get('time','')}", expanded=i <= 2):
            st.markdown(f"**내레이션**\n\n{scene.get('narration','')}")
            st.markdown(f"**자막**\n\n{scene.get('caption','')}")
            st.markdown(f"**화면**\n\n{scene.get('visual','')}")
            st.markdown(f"**편집 포인트**\n\n{scene.get('edit_point','')}")
            st.text_area("이미지 프롬프트", stringify_output(scene.get("image_prompt", {})), height=170, key=f"image_{i}_{id(scene)}")
            st.text_area("영상 프롬프트", stringify_output(scene.get("video_prompt", {})), height=170, key=f"video_{i}_{id(scene)}")

def render_card_news(cards: List[Dict[str, Any]]) -> None:
    for idx, card in enumerate(cards, 1):
        with st.expander(f"카드뉴스 {card.get('page', idx)}장 · {card.get('headline','')}", expanded=idx <= 2):
            st.markdown(f"**헤드라인**\n\n{card.get('headline','')}")
            st.markdown(f"**본문**\n\n{card.get('body','')}")
            st.markdown(f"**디자인 톤**\n\n{card.get('design_mood','')}")
            st.markdown(f"**이미지 방향**\n\n{card.get('image_direction','')}")
            st.markdown(f"**강조 자막**\n\n{card.get('key_caption','')}")
            st.text_area("이미지 프롬프트 EN", card.get("image_prompt_en", ""), height=120, key=f"card_{idx}_{id(card)}")

def render_history_page() -> None:
    st.subheader("히스토리")
    if not st.session_state.history:
        st.info("아직 생성 히스토리가 없습니다. 콘텐츠 생성 메뉴에서 먼저 생성해주세요.")
        return
    labels = []
    for idx, item in enumerate(st.session_state.history):
        brief = item.get("auto_brief", {}) or {}
        labels.append(f"{idx+1}. {item.get('generated_at','')} · {brief.get('topic','무제')}")
    selected = st.selectbox("생성 히스토리", labels)
    selected_idx = labels.index(selected)
    selected_package = st.session_state.history[selected_idx]
    brief = selected_package.get("auto_brief", {}) or {}
    st.markdown(f"### {brief.get('topic', '무제')}")
    st.json({
        "generated_at": selected_package.get("generated_at"),
        "auto_brief": brief,
        "reference_preview": selected_package.get("reference_preview", ""),
    })
    history_csv = to_csv(package_to_rows(selected_package))
    st.download_button("선택 히스토리 CSV 다운로드", history_csv, file_name="ai_pd_studio_history_item.csv", mime="text/csv", use_container_width=True)
    st.download_button("선택 히스토리 JSON 다운로드", stringify_output(selected_package), file_name="ai_pd_studio_history_item.json", mime="application/json", use_container_width=True)
    if st.button("선택 히스토리를 현재 결과로 불러오기", use_container_width=True):
        st.session_state.package = selected_package
        st.session_state.menu = "콘텐츠 생성"
        st.rerun()

if "package" not in st.session_state:
    st.session_state.package = None
if "history" not in st.session_state:
    st.session_state.history = []
if "menu" not in st.session_state:
    st.session_state.menu = "콘텐츠 생성"

st.markdown(f"""<div class='hero-card'><h1>{APP_TITLE}</h1><p>{APP_SUBTITLE}</p><p class='small-muted'>요약봇 말고 PD 사고회로. 쇼츠와 카드뉴스 모두 별도 전문 리라이트를 거쳐 죽은 문장을 제거합니다.</p></div>""", unsafe_allow_html=True)

st.sidebar.header("메인 메뉴")
menu = st.sidebar.radio("이동", ["콘텐츠 생성", "히스토리"], key="menu")

st.sidebar.header("⚙️ 생성 설정")
model = st.sidebar.selectbox("OpenAI 모델", ["gpt-4.1-mini", "gpt-4.1", "gpt-4o-mini", "gpt-4o"], index=0)
temperature = st.sidebar.slider("창의성", 0.1, 1.2, 0.85, 0.05)
output_language = st.sidebar.selectbox("출력 언어", ["한국어", "영어", "한국어+영어"], index=0)
generation_scope = st.sidebar.selectbox("생성 범위", ["숏폼+카드뉴스+이미지/영상 프롬프트", "숏폼 중심", "카드뉴스 중심", "이미지/영상 프롬프트 중심"], index=0)
image_ratio = st.sidebar.selectbox("이미지/영상 비율", ["9:16 vertical shorts", "1:1 square card news", "4:5 Instagram feed", "16:9 YouTube wide", "3:4 portrait"], index=0)
card_count = st.sidebar.slider("카드뉴스 장수", 5, 12, 7)
run_shorts_doctor = st.sidebar.checkbox("쇼츠 대본 전문 리라이트 실행", value=True)
run_cardnews_doctor = st.sidebar.checkbox("카드뉴스 전문 리라이트 실행", value=True)
with st.sidebar.expander("Streamlit Secrets 안내"):
    st.code('OPENAI_API_KEY = "sk-..."', language="toml")

st.divider()

if menu == "히스토리":
    render_history_page()
else:
    left, right = st.columns([0.86, 1.14], gap="large")
    with left:
        st.subheader("1. 레퍼런스 입력")
        reference_text = st.text_area("레퍼런스 텍스트 / 대본 / 카드뉴스 / 광고 카피", placeholder="여기에 레퍼런스를 붙여넣으세요. AI가 의도, 갈등, 욕망, 불안, 후킹 구조까지 분해합니다.", height=420)
        with st.expander("선택 입력: 방향만 살짝 유도"):
            override_topic = st.text_input("주제 덮어쓰기", placeholder="비워두면 레퍼런스에서 자동 추론")
            platform_hint = st.selectbox("플랫폼 힌트", ["AI가 레퍼런스로 자동 판단", "YouTube Shorts", "Instagram Reels", "TikTok", "카드뉴스", "블로그", "혼합"], index=0)
            tone_hint = st.selectbox("톤 힌트", ["AI가 레퍼런스로 자동 판단", "커뮤니티 인기글형", "전문가 정보형", "자극적 후킹형", "다큐멘터리형", "광고 카피형", "브랜드 필름형"], index=0)
        run_button = st.button("PD 사고루프로 콘텐츠 패키지 생성", type="primary", use_container_width=True)

    if run_button:
        if not reference_text.strip():
            st.warning("레퍼런스를 먼저 입력해주세요.")
        else:
            progress = st.progress(0)
            status = st.empty()
            status.info("1/3 PD 사고루프 실행 중: 의도 분석 → 팩트 뱅크 → 후킹 전쟁실 → 장면화")
            package = call_llm(PD_BRAIN_SYSTEM, build_pd_prompt(reference_text, output_language, generation_scope, platform_hint, tone_hint, override_topic, card_count, image_ratio), model, temperature)
            progress.progress(45)

            if run_shorts_doctor:
                status.info("2/3 쇼츠 대본 전문 리라이트 중: 카드뉴스식 문장 제거 → 리텐션 재설계")
                doctor_result = call_llm(SHORTS_DOCTOR_SYSTEM, build_shorts_doctor_prompt(package, image_ratio), model, min(1.0, temperature + 0.05))
                package = merge_shorts_doctor(package, doctor_result)
            progress.progress(70)

            if run_cardnews_doctor:
                status.info("3/3 카드뉴스 전문 리라이트 중: 정리본 제거 → 저장형 문장 재설계")
                card_doctor_result = call_llm(CARDNEWS_DOCTOR_SYSTEM, build_cardnews_doctor_prompt(package, image_ratio, card_count), model, min(1.0, temperature + 0.05))
                package = merge_cardnews_doctor(package, card_doctor_result)
            progress.progress(100)

            if "auto_brief" not in package:
                package["auto_brief"] = {}
            package["auto_brief"]["image_ratio"] = image_ratio
            package["generated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            package["reference_preview"] = reference_text[:240]
            st.session_state.package = package
            st.session_state.history.insert(0, package)
            st.session_state.history = st.session_state.history[:20]
            status.success("생성 완료. 히스토리는 좌측 메인 메뉴에서 확인할 수 있습니다.")

    with right:
        st.subheader("2. 결과")
        package = st.session_state.package
        if not package:
            st.info("레퍼런스를 입력하고 생성 버튼을 누르면 결과가 여기에 표시됩니다.")
        else:
            tabs = st.tabs(["자동 브리프", "PD 사고회로", "숏폼 대본", "카드뉴스", "프롬프트", "제목/CTA", "CSV/JSON"])
            with tabs[0]:
                render_auto_brief(package.get("auto_brief", {}))
            with tabs[1]:
                st.json(package.get("pd_brain", {}))
            shorts = package.get("one_minute_shorts", {}) or {}
            scenes = shorts.get("scenes", []) or []
            cards = package.get("card_news", []) or []
            with tabs[2]:
                st.markdown(f"### {shorts.get('title','1분 숏폼 대본')}")
                st.markdown(f"**핵심 주장**: {shorts.get('core_claim','')}")
                render_scene_cards(scenes)
            with tabs[3]:
                render_card_news(cards)
            with tabs[4]:
                lines = []
                for idx, scene in enumerate(scenes, 1):
                    lines.append(f"컷 {idx} 이미지 프롬프트\n{stringify_output(scene.get('image_prompt', {}))}\n")
                    lines.append(f"컷 {idx} 영상 프롬프트\n{stringify_output(scene.get('video_prompt', {}))}\n")
                st.text_area("전체 프롬프트", "\n".join(lines), height=520)
            with tabs[5]:
                st.markdown("### 썸네일 문구")
                st.write(package.get("thumbnail_copy", []))
                st.markdown("### 제목 후보")
                st.write(package.get("titles", []))
                st.markdown("### 해시태그")
                st.write(" ".join(package.get("hashtags", [])))
                st.markdown("### 제작 체크리스트")
                st.write(package.get("production_checklist", []))
                st.markdown("### 품질 점수")
                st.json(package.get("quality", {}))
            with tabs[6]:
                rows = package_to_rows(package)
                csv_text = to_csv(rows)
                json_text = stringify_output(package)
                st.download_button("CSV 다운로드", csv_text, file_name="ai_pd_studio_content.csv", mime="text/csv", use_container_width=True)
                st.download_button("JSON 다운로드", json_text, file_name="ai_pd_studio_output.json", mime="application/json", use_container_width=True)
                st.text_area("CSV 미리보기", csv_text, height=280)
