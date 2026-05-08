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
.main .block-container { padding-top: 2rem; max-width: 1320px; }
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

FINAL_SCHEMA = {
    "auto_brief": {"topic":"", "target":"", "platform":"", "tone":"", "goal":"", "cta":"", "forbidden":[], "risk_notes":[]},
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

def build_pd_prompt(reference_text: str, output_language: str, generation_scope: str, platform_hint: str, tone_hint: str, override_topic: str, card_count: int) -> str:
    return f"""
아래 레퍼런스를 바탕으로 AI PD 사고루프를 실행하고 최종 제작 패키지를 만들어라.

사용자 선택값:
- 출력 언어: {output_language}
- 생성 범위: {generation_scope}
- 플랫폼 힌트: {platform_hint}
- 톤 힌트: {tone_hint}
- 주제 덮어쓰기: {override_topic}
- 카드뉴스 장수: {card_count}

강제 품질 기준:
1. 자동 브리프에서 주제/타겟/목표/CTA/금지표현을 레퍼런스 기반으로 추론한다.
2. pd_brain에 real_intent, viewer_desire, viewer_anxiety, conflict, contrarian_claim, comment_trigger를 반드시 채운다.
3. fact_angle_bank에는 구체명사를 많이 넣는다. 단, 확인되지 않은 사실은 needs_verification에 넣는다.
4. 1분 숏폼은 7~9컷으로 만들되, 각 컷은 정보 나열이 아니라 긴장 상승 구조여야 한다.
5. 내레이션은 짧고 강하게. '살펴보겠습니다' 같은 발표 말투 금지.
6. visual은 아이콘/다이어그램이 아니라 실제 장면으로 쓴다.
7. 영상 프롬프트는 영어로 쓰고 반드시 카메라 무빙으로 시작한다.
8. 마지막 quality 점수에서 85점 미만인 항목이 나오면 최종 결과를 스스로 한 번 재작성한 버전으로 출력한다.

출력 JSON 스키마 예시:
{json.dumps(FINAL_SCHEMA, ensure_ascii=False, indent=2)}

레퍼런스:
{reference_text}
"""

def stringify_output(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)

def render_auto_brief(auto_inputs: Dict[str, Any]) -> None:
    cols = st.columns(2)
    for idx, key in enumerate(["topic","target","platform","tone","goal","cta"]):
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
            st.text_area("이미지 프롬프트", stringify_output(scene.get("image_prompt", {})), height=170, key=f"image_{i}")
            st.text_area("영상 프롬프트", stringify_output(scene.get("video_prompt", {})), height=170, key=f"video_{i}")

def render_card_news(cards: List[Dict[str, Any]]) -> None:
    for idx, card in enumerate(cards, 1):
        with st.expander(f"카드뉴스 {card.get('page', idx)}장 · {card.get('headline','')}", expanded=idx <= 2):
            st.markdown(f"**헤드라인**\n\n{card.get('headline','')}")
            st.markdown(f"**본문**\n\n{card.get('body','')}")
            st.markdown(f"**디자인 톤**\n\n{card.get('design_mood','')}")
            st.markdown(f"**이미지 방향**\n\n{card.get('image_direction','')}")
            st.markdown(f"**강조 자막**\n\n{card.get('key_caption','')}")
            st.text_area("이미지 프롬프트 EN", card.get("image_prompt_en", ""), height=120, key=f"card_{idx}")

if "package" not in st.session_state:
    st.session_state.package = None

st.markdown(f"""<div class='hero-card'><h1>{APP_TITLE}</h1><p>{APP_SUBTITLE}</p><p class='small-muted'>요약봇 말고 PD 사고회로. 약한 결과는 스스로 버리고 다시 쓰게 설계했습니다.</p></div>""", unsafe_allow_html=True)

st.sidebar.header("⚙️ 생성 설정")
model = st.sidebar.selectbox("OpenAI 모델", ["gpt-4.1-mini", "gpt-4.1", "gpt-4o-mini", "gpt-4o"], index=0)
temperature = st.sidebar.slider("창의성", 0.1, 1.2, 0.85, 0.05)
output_language = st.sidebar.selectbox("출력 언어", ["한국어", "영어", "한국어+영어"], index=0)
generation_scope = st.sidebar.selectbox("생성 범위", ["숏폼+카드뉴스+이미지/영상 프롬프트", "숏폼 중심", "카드뉴스 중심", "이미지/영상 프롬프트 중심"], index=0)
card_count = st.sidebar.slider("카드뉴스 장수", 5, 12, 7)
with st.sidebar.expander("Streamlit Secrets 안내"):
    st.code('OPENAI_API_KEY = "sk-..."', language="toml")

st.divider()
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
        status.info("PD 사고루프 실행 중: 의도 분석 → 팩트 뱅크 → 후킹 전쟁실 → 장면화 → 재작성")
        st.session_state.package = call_llm(PD_BRAIN_SYSTEM, build_pd_prompt(reference_text, output_language, generation_scope, platform_hint, tone_hint, override_topic, card_count), model, temperature)
        progress.progress(100)
        status.success("생성 완료. 자동 브리프와 PD 사고 흔적까지 확인하세요.")

with right:
    st.subheader("2. 결과")
    package = st.session_state.package
    if not package:
        st.info("레퍼런스를 입력하고 생성 버튼을 누르면 결과가 여기에 표시됩니다.")
    else:
        tabs = st.tabs(["자동 브리프", "PD 사고회로", "숏폼 대본", "카드뉴스", "프롬프트", "제목/CTA", "검수", "전체 JSON"])
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
        with tabs[6]:
            st.json(package.get("quality", {}))
        with tabs[7]:
            output_text = stringify_output(package)
            st.download_button("JSON 다운로드", output_text, file_name="ai_pd_studio_output.json", mime="application/json", use_container_width=True)
            st.text_area("전체 복사용 JSON", output_text, height=520)
