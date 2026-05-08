import json
import os
import re
from datetime import datetime
from typing import Any, Dict, List

import streamlit as st
from openai import OpenAI


APP_TITLE = "AI PD Studio"
APP_SUBTITLE = "레퍼런스 분석 기반 카드뉴스 · 1분 숏폼 · 이미지/영상 프롬프트 생성기"
DEFAULT_MODEL = "gpt-4.1-mini"


st.set_page_config(
    page_title=APP_TITLE,
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
)


CUSTOM_CSS = """
<style>
.main .block-container { padding-top: 2rem; max-width: 1280px; }
.hero-card {
    padding: 1.35rem 1.5rem;
    border: 1px solid rgba(120, 120, 120, 0.18);
    border-radius: 22px;
    background: linear-gradient(135deg, rgba(120, 120, 255, 0.10), rgba(255, 255, 255, 0.03));
}
.small-muted { color: #888; font-size: 0.92rem; }
.output-card {
    padding: 1rem;
    border-radius: 16px;
    border: 1px solid rgba(120, 120, 120, 0.18);
    background: rgba(120, 120, 120, 0.04);
    margin-bottom: 0.8rem;
}
.copy-block textarea { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


REFERENCE_ANALYZER_SYSTEM = """
너는 바이럴 콘텐츠 분석가다. 사용자가 제공한 레퍼런스를 표절하지 않고 구조만 분석한다.
분석 대상은 후킹 방식, 감정 곡선, 문장 리듬, 시각 문법, CTA 배치, 플랫폼 적합성이다.
고유 문장, 고유 캐릭터, 브랜드 표현, 독창적 비유는 복제하지 않는다.
반드시 JSON만 출력한다.
"""

STRATEGY_SYSTEM = """
너는 100만 구독자급 숏폼 PD이자 카드뉴스 기획자다.
레퍼런스의 성공 문법을 새 주제에 이식하되 표절하지 않는다.
시청자가 3초 안에 멈추고, 15초 안에 납득하고, 끝에서 행동하도록 설계한다.
반드시 JSON만 출력한다.
"""

FINAL_GENERATOR_SYSTEM = """
너는 실무형 AI 콘텐츠 제작 총괄 PD다.
입력된 레퍼런스 분석과 콘텐츠 전략을 바탕으로 실제 제작자가 바로 복사해서 쓸 수 있는 결과물을 만든다.
결과물은 카드뉴스, 1분 숏폼 대본, 이미지 프롬프트, 영상 프롬프트, 제목, 썸네일 문구, 해시태그, CTA, 제작 체크리스트를 포함한다.
이미지/영상 프롬프트는 영어로 작성하고, 한국어 제작 의도를 함께 제공한다.
영상 프롬프트는 항상 카메라 무빙으로 시작한다.
의학/금융/투자/건강 주제는 단정적 효능, 수익 보장, 치료 보장 표현을 피하고 일반 정보/교육성 톤으로 작성한다.
반드시 JSON만 출력한다.
"""

QUALITY_SYSTEM = """
너는 냉정한 콘텐츠 품질 심사위원이다.
실제 제작 가능성, 후킹, 명확성, 시각화 가능성, 플랫폼 적합성, 표절 위험, CTA 자연스러움을 점수화한다.
80점 미만 항목은 구체적인 수정 지시를 제시한다.
반드시 JSON만 출력한다.
"""


REFERENCE_SCHEMA = {
    "content_type": "레퍼런스 유형",
    "target_audience": "예상 타겟",
    "hook_type": "후킹 유형",
    "opening_pattern": "오프닝 구조",
    "emotional_curve": ["감정1", "감정2", "감정3"],
    "script_rhythm": "문장 길이와 리듬",
    "visual_style": "시각 문법",
    "cta_style": "CTA 방식",
    "benchmarkable_patterns": ["차용 가능한 구조"],
    "do_not_copy": ["복제 금지 요소"],
}

STRATEGY_SCHEMA = {
    "core_angle": "새 콘텐츠 핵심 각도",
    "viewer_promise": "시청자에게 주는 약속",
    "hook_candidates": ["첫 문장 후보"],
    "story_flow": ["0-3초", "4-15초", "16-45초", "46-60초"],
    "visual_rules": ["시각화 규칙"],
    "cta_plan": "CTA 배치와 문구 방향",
    "risk_notes": ["주의할 표현"],
}

FINAL_SCHEMA = {
    "project_title": "콘텐츠 제목",
    "one_minute_shorts": {
        "title": "숏폼 제목",
        "duration": "60초",
        "scenes": [
            {
                "time": "0-3초",
                "narration": "내레이션",
                "caption": "화면 자막",
                "visual": "화면 설명",
                "image_prompt": {
                    "korean_direction": "한국어 이미지 의도",
                    "english_prompt": "English image generation prompt",
                    "negative_prompt": "text, watermark, logo"
                },
                "video_prompt": {
                    "korean_direction": "한국어 영상 의도",
                    "english_prompt": "Camera movement first, then subject/action/style"
                }
            }
        ]
    },
    "card_news": [
        {
            "page": 1,
            "headline": "카드 제목",
            "body": "본문",
            "design_mood": "디자인 톤",
            "image_direction": "이미지 방향",
            "image_prompt_en": "English image prompt",
            "key_caption": "강조 자막"
        }
    ],
    "thumbnail_copy": ["썸네일 문구"],
    "titles": ["제목 후보"],
    "hashtags": ["#태그"],
    "cta": "CTA 문구",
    "production_checklist": ["제작 체크리스트"]
}


@st.cache_data(show_spinner=False)
def now_label() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def get_secret(name: str) -> str:
    if name in st.secrets:
        return st.secrets[name]
    return os.getenv(name, "")


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


def call_llm(system_prompt: str, user_prompt: str, model: str, temperature: float = 0.7) -> Dict[str, Any]:
    client = get_client()
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
        response_format={"type": "json_object"},
    )
    content = response.choices[0].message.content or "{}"
    return extract_json(content)


def build_reference_prompt(reference_text: str, platform: str, output_language: str) -> str:
    return f"""
아래 레퍼런스를 분석해줘.
출력 언어: {output_language}
플랫폼: {platform}

분석 기준:
1. 이 콘텐츠가 사람을 멈추게 하는 방식
2. 첫 3초/첫 장에서 작동하는 후킹 구조
3. 감정 곡선
4. 문장 길이와 리듬
5. 시각화 문법
6. CTA 구조
7. 새 콘텐츠에 차용 가능한 구조
8. 절대 복제하면 안 되는 고유 표현

출력 JSON 스키마 예시:
{json.dumps(REFERENCE_SCHEMA, ensure_ascii=False, indent=2)}

레퍼런스:
{reference_text}
"""


def build_strategy_prompt(inputs: Dict[str, Any], reference_analysis: Dict[str, Any]) -> str:
    return f"""
다음 입력값과 레퍼런스 분석을 바탕으로 콘텐츠 전략을 설계해줘.

사용자 입력:
{json.dumps(inputs, ensure_ascii=False, indent=2)}

레퍼런스 분석:
{json.dumps(reference_analysis, ensure_ascii=False, indent=2)}

전략 JSON 스키마 예시:
{json.dumps(STRATEGY_SCHEMA, ensure_ascii=False, indent=2)}
"""


def build_final_prompt(inputs: Dict[str, Any], reference_analysis: Dict[str, Any], strategy: Dict[str, Any]) -> str:
    return f"""
아래 정보를 바탕으로 최종 콘텐츠 패키지를 생성해줘.

중요 규칙:
- 당장 제작자가 복사해서 쓸 수 있게 구체적으로 작성
- 1분 숏폼은 8~12개 컷으로 구성
- 카드뉴스는 사용자가 선택한 장수에 맞춰 구성
- 이미지 프롬프트는 영어 프롬프트와 negative prompt 포함
- 영상 프롬프트는 카메라 무빙으로 시작
- 각 컷은 앞뒤 컷 연결이 자연스러워야 함
- 사용자가 금지한 표현은 쓰지 말 것
- 레퍼런스 원문을 복제하지 말 것

사용자 입력:
{json.dumps(inputs, ensure_ascii=False, indent=2)}

레퍼런스 분석:
{json.dumps(reference_analysis, ensure_ascii=False, indent=2)}

콘텐츠 전략:
{json.dumps(strategy, ensure_ascii=False, indent=2)}

최종 출력 JSON 스키마 예시:
{json.dumps(FINAL_SCHEMA, ensure_ascii=False, indent=2)}
"""


def build_quality_prompt(final_output: Dict[str, Any]) -> str:
    return f"""
아래 최종 콘텐츠 패키지를 평가해줘.
각 점수는 0~100으로 작성해줘.

평가 대상:
{json.dumps(final_output, ensure_ascii=False, indent=2)}

출력 형식:
{{
  "hook_score": 0,
  "clarity_score": 0,
  "visual_score": 0,
  "viral_score": 0,
  "production_ready_score": 0,
  "copyright_risk": "low | medium | high",
  "revision_needed": true,
  "revision_notes": ["수정 지시"]
}}
"""


def stringify_output(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def render_scene_cards(scenes: List[Dict[str, Any]]) -> None:
    for i, scene in enumerate(scenes, 1):
        with st.expander(f"컷 {i} · {scene.get('time', '')}", expanded=i <= 2):
            st.markdown(f"**내레이션**\n\n{scene.get('narration', '')}")
            st.markdown(f"**자막**\n\n{scene.get('caption', '')}")
            st.markdown(f"**화면**\n\n{scene.get('visual', '')}")
            image_prompt = scene.get("image_prompt", {})
            video_prompt = scene.get("video_prompt", {})
            st.text_area("이미지 프롬프트", stringify_output(image_prompt), height=170, key=f"image_{i}")
            st.text_area("영상 프롬프트", stringify_output(video_prompt), height=170, key=f"video_{i}")


def render_card_news(cards: List[Dict[str, Any]]) -> None:
    for card in cards:
        page = card.get("page", "")
        with st.expander(f"카드뉴스 {page}장 · {card.get('headline', '')}", expanded=int(page or 1) <= 2 if str(page).isdigit() else False):
            st.markdown(f"**헤드라인**\n\n{card.get('headline', '')}")
            st.markdown(f"**본문**\n\n{card.get('body', '')}")
            st.markdown(f"**디자인 톤**\n\n{card.get('design_mood', '')}")
            st.markdown(f"**이미지 방향**\n\n{card.get('image_direction', '')}")
            st.text_area("이미지 프롬프트 EN", card.get("image_prompt_en", ""), height=120, key=f"card_{page}")


def init_session() -> None:
    defaults = {
        "reference_analysis": None,
        "strategy": None,
        "final_output": None,
        "quality": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


init_session()

st.markdown(
    f"""
    <div class=\"hero-card\">
        <h1>{APP_TITLE}</h1>
        <p>{APP_SUBTITLE}</p>
        <p class=\"small-muted\">레퍼런스의 성공 구조를 추출해서 바로 제작 가능한 콘텐츠 패키지로 변환합니다.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

st.sidebar.header("⚙️ 생성 설정")
model = st.sidebar.selectbox(
    "OpenAI 모델",
    ["gpt-4.1-mini", "gpt-4.1", "gpt-4o-mini", "gpt-4o"],
    index=0,
)
temperature = st.sidebar.slider("창의성", 0.1, 1.2, 0.75, 0.05)
output_language = st.sidebar.selectbox("출력 언어", ["한국어", "영어", "한국어+영어"], index=0)

with st.sidebar.expander("Streamlit Secrets 안내"):
    st.code('OPENAI_API_KEY = "sk-..."', language="toml")

st.divider()

left, right = st.columns([0.9, 1.1], gap="large")

with left:
    st.subheader("1. 프로젝트 입력")
    topic = st.text_input("콘텐츠 주제", placeholder="예: 당뇨인이 곤약면을 먹기 전에 알아야 할 것")
    target = st.text_input("타겟", placeholder="예: 40~60대 당뇨 관리 관심층")
    platform = st.selectbox("플랫폼", ["YouTube Shorts", "Instagram Reels", "TikTok", "카드뉴스", "블로그", "혼합"], index=0)
    tone = st.selectbox(
        "톤앤매너",
        ["커뮤니티 인기글형", "전문가 정보형", "자극적 후킹형", "다큐멘터리형", "광고 카피형", "브랜드 필름형"],
        index=0,
    )
    content_goal = st.text_input("목표", placeholder="예: 저장, 공유, 댓글, 구매 전환, 상담 문의")
    cta = st.text_input("CTA", placeholder="예: 프로필 링크 10번째에서 확인하세요")
    forbidden = st.text_area("금지 표현 / 주의사항", placeholder="예: 치료 보장 표현 금지, 특정 브랜드명 언급 금지", height=90)
    card_count = st.slider("카드뉴스 장수", 5, 12, 7)

    st.subheader("2. 레퍼런스 입력")
    reference_text = st.text_area(
        "벤치마크 레퍼런스 텍스트 / 대본 / 카드뉴스 문구 / 광고 카피",
        placeholder="여기에 레퍼런스 내용을 붙여넣으세요. URL만 넣기보다는 핵심 문장이나 대본을 함께 넣으면 훨씬 정확합니다.",
        height=260,
    )

    run_button = st.button("콘텐츠 패키지 생성", type="primary", use_container_width=True)

inputs = {
    "topic": topic,
    "target": target,
    "platform": platform,
    "tone": tone,
    "content_goal": content_goal,
    "cta": cta,
    "forbidden": forbidden,
    "card_count": card_count,
    "output_language": output_language,
    "created_at": now_label(),
}

if run_button:
    if not topic or not reference_text:
        st.warning("콘텐츠 주제와 레퍼런스는 반드시 입력해야 합니다.")
    else:
        progress = st.progress(0)
        status = st.empty()

        status.info("1/4 레퍼런스 구조 분석 중")
        st.session_state.reference_analysis = call_llm(
            REFERENCE_ANALYZER_SYSTEM,
            build_reference_prompt(reference_text, platform, output_language),
            model,
            temperature=0.35,
        )
        progress.progress(25)

        status.info("2/4 콘텐츠 전략 설계 중")
        st.session_state.strategy = call_llm(
            STRATEGY_SYSTEM,
            build_strategy_prompt(inputs, st.session_state.reference_analysis),
            model,
            temperature=temperature,
        )
        progress.progress(50)

        status.info("3/4 최종 콘텐츠 패키지 생성 중")
        st.session_state.final_output = call_llm(
            FINAL_GENERATOR_SYSTEM,
            build_final_prompt(inputs, st.session_state.reference_analysis, st.session_state.strategy),
            model,
            temperature=temperature,
        )
        progress.progress(82)

        status.info("4/4 품질 점수 평가 중")
        st.session_state.quality = call_llm(
            QUALITY_SYSTEM,
            build_quality_prompt(st.session_state.final_output),
            model,
            temperature=0.2,
        )
        progress.progress(100)
        status.success("생성 완료. 이제 복사해서 제작 들어가면 됩니다.")

with right:
    st.subheader("3. 결과")

    if not st.session_state.final_output:
        st.info("왼쪽 입력값을 채우고 생성 버튼을 누르면 결과가 여기에 표시됩니다.")
    else:
        tabs = st.tabs(["요약", "숏폼 대본", "카드뉴스", "프롬프트", "제목/CTA", "검수", "전체 JSON"])

        final_output = st.session_state.final_output
        shorts = final_output.get("one_minute_shorts", {})
        scenes = shorts.get("scenes", [])
        cards = final_output.get("card_news", [])

        with tabs[0]:
            st.markdown(f"### {final_output.get('project_title', '콘텐츠 패키지')}")
            st.markdown("#### 레퍼런스 분석")
            st.json(st.session_state.reference_analysis)
            st.markdown("#### 콘텐츠 전략")
            st.json(st.session_state.strategy)

        with tabs[1]:
            st.markdown(f"### {shorts.get('title', '1분 숏폼 대본')}")
            render_scene_cards(scenes)

        with tabs[2]:
            render_card_news(cards)

        with tabs[3]:
            st.markdown("### 이미지/영상 프롬프트 모아보기")
            prompt_lines = []
            for idx, scene in enumerate(scenes, 1):
                prompt_lines.append(f"컷 {idx} 이미지 프롬프트\n{stringify_output(scene.get('image_prompt', {}))}\n")
                prompt_lines.append(f"컷 {idx} 영상 프롬프트\n{stringify_output(scene.get('video_prompt', {}))}\n")
            st.text_area("전체 프롬프트", "\n".join(prompt_lines), height=520)

        with tabs[4]:
            st.markdown("### 썸네일 문구")
            st.write(final_output.get("thumbnail_copy", []))
            st.markdown("### 제목 후보")
            st.write(final_output.get("titles", []))
            st.markdown("### 해시태그")
            st.write(" ".join(final_output.get("hashtags", [])))
            st.markdown("### CTA")
            st.write(final_output.get("cta", ""))
            st.markdown("### 제작 체크리스트")
            st.write(final_output.get("production_checklist", []))

        with tabs[5]:
            st.json(st.session_state.quality)

        with tabs[6]:
            full_package = {
                "inputs": inputs,
                "reference_analysis": st.session_state.reference_analysis,
                "strategy": st.session_state.strategy,
                "final_output": st.session_state.final_output,
                "quality": st.session_state.quality,
            }
            output_text = stringify_output(full_package)
            st.download_button(
                "JSON 다운로드",
                output_text,
                file_name="ai_pd_studio_output.json",
                mime="application/json",
                use_container_width=True,
            )
            st.text_area("전체 복사용 JSON", output_text, height=520)
