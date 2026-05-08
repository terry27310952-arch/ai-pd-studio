import json
import os
import re
from datetime import datetime
from typing import Any, Dict, List

import streamlit as st
from openai import OpenAI


APP_TITLE = "AI PD Studio"
APP_SUBTITLE = "레퍼런스만 넣으면 주제·타겟·목표·CTA·주의사항까지 자동 분석하는 콘텐츠 생성기"

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
    background: linear-gradient(135deg, rgba(120, 120, 255, 0.12), rgba(255, 255, 255, 0.03));
}
.small-muted { color: #888; font-size: 0.92rem; }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


REFERENCE_ANALYZER_SYSTEM = """
너는 레퍼런스 기반 콘텐츠 기획 분석가다.
사용자가 제공한 레퍼런스를 보고 아래 항목을 자동 추론한다.
- 콘텐츠 주제
- 타겟
- 플랫폼
- 톤앤매너
- 콘텐츠 목적
- CTA
- 금지 표현/주의사항
- 콘텐츠 유형
- 후킹 구조
- 감정선
- 시각 문법
- 카드뉴스/숏폼으로 확장 가능한 구조

중요 규칙:
1. 레퍼런스의 고유 문장, 고유 캐릭터, 브랜드 표현은 복제하지 않는다.
2. 레퍼런스가 특정 상품/브랜드/업종을 포함하면 그 맥락을 유지하되 표현은 새롭게 재구성한다.
3. 사용자가 별도 주제를 입력하지 않아도 레퍼런스만으로 제작 가능한 프로젝트 정보를 추론한다.
4. 의학/건강/투자/금융/법률 주제는 단정적 효능, 수익 보장, 치료 보장, 법률 보장 표현을 금지 표현에 포함한다.
5. 반드시 JSON만 출력한다.
"""

STRATEGY_SYSTEM = """
너는 100만 구독자급 숏폼 PD이자 카드뉴스 기획자다.
레퍼런스 분석으로 추론된 프로젝트 정보를 바탕으로 콘텐츠 전략을 설계한다.
시청자가 3초 안에 멈추고, 15초 안에 납득하고, 끝에서 행동하도록 만든다.
반드시 JSON만 출력한다.
"""

FINAL_GENERATOR_SYSTEM = """
너는 실무형 AI 콘텐츠 제작 총괄 PD다.
레퍼런스 분석과 콘텐츠 전략을 바탕으로 바로 제작 가능한 결과물을 만든다.
결과물은 카드뉴스, 1분 숏폼 대본, 이미지 프롬프트, 영상 프롬프트, 제목, 썸네일 문구, 해시태그, CTA, 제작 체크리스트를 포함한다.
이미지/영상 프롬프트는 영어로 작성하고 한국어 제작 의도를 함께 제공한다.
영상 프롬프트는 반드시 카메라 무빙으로 시작한다.
레퍼런스 원문을 복제하지 말고, 성공 구조만 이식한다.
반드시 JSON만 출력한다.
"""

QUALITY_SYSTEM = """
너는 냉정한 콘텐츠 품질 심사위원이다.
실제 제작 가능성, 후킹, 명확성, 시각화 가능성, 플랫폼 적합성, 표절 위험, CTA 자연스러움을 점수화한다.
80점 미만 항목은 구체적인 수정 지시를 제시한다.
반드시 JSON만 출력한다.
"""

REFERENCE_SCHEMA = {
    "inferred_project": {
        "topic": "레퍼런스를 보고 추론한 콘텐츠 주제",
        "target": "추론한 핵심 타겟",
        "platform": "가장 적합한 플랫폼",
        "tone": "추론한 톤앤매너",
        "content_goal": "콘텐츠 목적",
        "cta": "자연스러운 CTA",
        "forbidden": ["금지 표현", "주의사항"],
        "content_type": "숏폼/카드뉴스/광고/블로그 등",
        "risk_category": "none | health | finance | legal | medical | other",
    },
    "content_dna": {
        "hook_type": "후킹 유형",
        "opening_pattern": "오프닝 구조",
        "emotional_curve": ["감정 흐름"],
        "script_rhythm": "문장 길이와 리듬",
        "visual_style": "시각 문법",
        "cta_style": "CTA 방식",
        "benchmarkable_patterns": ["차용 가능한 구조"],
        "do_not_copy": ["복제 금지 요소"],
    },
    "production_assumptions": ["생성 시 적용할 제작 가정"],
}

STRATEGY_SCHEMA = {
    "core_angle": "핵심 각도",
    "viewer_promise": "시청자에게 주는 약속",
    "first_3_seconds": "첫 3초 설계",
    "retention_devices": ["시청 지속 장치"],
    "story_flow": ["0-3초", "4-15초", "16-45초", "46-60초"],
    "card_news_flow": ["1장", "2장", "3장"],
    "visual_rules": ["시각화 규칙"],
    "cta_plan": "CTA 배치와 문구 방향",
    "risk_notes": ["주의할 표현"],
}

FINAL_SCHEMA = {
    "project_title": "콘텐츠 제목",
    "auto_brief": {
        "topic": "자동 분석 주제",
        "target": "자동 분석 타겟",
        "platform": "자동 분석 플랫폼",
        "goal": "자동 분석 목표",
        "cta": "자동 분석 CTA",
        "forbidden": ["자동 분석 주의사항"],
    },
    "one_minute_shorts": {
        "title": "숏폼 제목",
        "duration": "60초",
        "scenes": [
            {
                "time": "0-3초",
                "narration": "내레이션",
                "caption": "화면 자막",
                "visual": "화면 설명",
                "edit_point": "편집 포인트",
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
    "cta": "최종 CTA 문구",
    "production_checklist": ["제작 체크리스트"]
}


def now_label() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


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


def build_reference_prompt(reference_text: str, output_language: str, generation_scope: str, platform_hint: str, override_topic: str) -> str:
    return f"""
아래 레퍼런스를 분석해서 콘텐츠 제작에 필요한 프로젝트 브리프를 자동 추론해줘.

사용자는 주제/타겟/목표/CTA/금지 표현을 별도로 입력하지 않을 수 있다.
따라서 레퍼런스 안에 있는 맥락을 바탕으로 다음 항목을 반드시 추론해야 한다.
- topic
- target
- platform
- tone
- content_goal
- cta
- forbidden
- content_type
- risk_category

사용자 선택값:
- 출력 언어: {output_language}
- 생성 범위: {generation_scope}
- 플랫폼 힌트: {platform_hint}
- 주제 덮어쓰기 힌트: {override_topic}

분석 기준:
1. 이 콘텐츠가 사람을 멈추게 하는 방식
2. 첫 3초/첫 장에서 작동하는 후킹 구조
3. 감정 곡선
4. 문장 길이와 리듬
5. 시각화 문법
6. CTA 구조
7. 새 콘텐츠에 차용 가능한 구조
8. 절대 복제하면 안 되는 고유 표현
9. 자동 추론한 주제/타겟/목표/CTA/주의사항

출력 JSON 스키마 예시:
{json.dumps(REFERENCE_SCHEMA, ensure_ascii=False, indent=2)}

레퍼런스:
{reference_text}
"""


def apply_overrides(reference_analysis: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
    inferred = reference_analysis.get("inferred_project", {}) or {}
    return {
        "topic": overrides.get("override_topic") or inferred.get("topic", "레퍼런스 기반 자동 생성 콘텐츠"),
        "target": inferred.get("target", "레퍼런스 기반 추론 타겟"),
        "platform": overrides.get("platform_hint") if overrides.get("platform_hint") != "AI가 레퍼런스로 자동 판단" else inferred.get("platform", "혼합"),
        "tone": overrides.get("tone_hint") if overrides.get("tone_hint") != "AI가 레퍼런스로 자동 판단" else inferred.get("tone", "레퍼런스 기반 톤"),
        "content_goal": inferred.get("content_goal", "시청 지속률과 행동 유도"),
        "cta": inferred.get("cta", "콘텐츠 맥락에 맞는 자연스러운 행동 유도"),
        "forbidden": inferred.get("forbidden", []),
        "content_type": inferred.get("content_type", "숏폼+카드뉴스"),
        "risk_category": inferred.get("risk_category", "none"),
        "generation_scope": overrides.get("generation_scope", "숏폼+카드뉴스+이미지/영상 프롬프트"),
        "card_count": overrides.get("card_count", 7),
        "output_language": overrides.get("output_language", "한국어"),
        "created_at": now_label(),
    }


def build_strategy_prompt(auto_inputs: Dict[str, Any], reference_analysis: Dict[str, Any]) -> str:
    return f"""
다음 자동 분석 브리프와 레퍼런스 DNA를 바탕으로 콘텐츠 전략을 설계해줘.

자동 분석 브리프:
{json.dumps(auto_inputs, ensure_ascii=False, indent=2)}

레퍼런스 분석:
{json.dumps(reference_analysis, ensure_ascii=False, indent=2)}

전략 JSON 스키마 예시:
{json.dumps(STRATEGY_SCHEMA, ensure_ascii=False, indent=2)}
"""


def build_final_prompt(auto_inputs: Dict[str, Any], reference_analysis: Dict[str, Any], strategy: Dict[str, Any]) -> str:
    return f"""
아래 정보를 바탕으로 최종 콘텐츠 패키지를 생성해줘.

중요 규칙:
- 당장 제작자가 복사해서 쓸 수 있게 구체적으로 작성한다.
- 1분 숏폼은 8~12개 컷으로 구성한다.
- 카드뉴스는 {auto_inputs.get('card_count', 7)}장으로 구성한다.
- 이미지 프롬프트는 영어 프롬프트와 negative prompt를 포함한다.
- 영상 프롬프트는 반드시 카메라 무빙으로 시작한다.
- 각 컷은 앞뒤 컷 연결이 자연스러워야 한다.
- forbidden에 포함된 표현은 쓰지 않는다.
- 레퍼런스 원문을 복제하지 않는다.

자동 분석 브리프:
{json.dumps(auto_inputs, ensure_ascii=False, indent=2)}

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
  "platform_fit_score": 0,
  "cta_naturalness_score": 0,
  "copyright_risk": "low | medium | high",
  "revision_needed": true,
  "revision_notes": ["수정 지시"]
}}
"""


def stringify_output(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def render_auto_brief(auto_inputs: Dict[str, Any]) -> None:
    st.markdown("### AI 자동 분석 브리프")
    cols = st.columns(2)
    items = [
        ("주제", auto_inputs.get("topic", "")),
        ("타겟", auto_inputs.get("target", "")),
        ("플랫폼", auto_inputs.get("platform", "")),
        ("톤앤매너", auto_inputs.get("tone", "")),
        ("목표", auto_inputs.get("content_goal", "")),
        ("CTA", auto_inputs.get("cta", "")),
        ("콘텐츠 유형", auto_inputs.get("content_type", "")),
        ("주의 카테고리", auto_inputs.get("risk_category", "")),
    ]
    for idx, (label, value) in enumerate(items):
        with cols[idx % 2]:
            st.markdown(f"**{label}**")
            st.write(value)
    st.markdown("**금지 표현/주의사항**")
    st.write(auto_inputs.get("forbidden", []))


def render_scene_cards(scenes: List[Dict[str, Any]]) -> None:
    for i, scene in enumerate(scenes, 1):
        with st.expander(f"컷 {i} · {scene.get('time', '')}", expanded=i <= 2):
            st.markdown(f"**내레이션**\n\n{scene.get('narration', '')}")
            st.markdown(f"**자막**\n\n{scene.get('caption', '')}")
            st.markdown(f"**화면**\n\n{scene.get('visual', '')}")
            st.markdown(f"**편집 포인트**\n\n{scene.get('edit_point', '')}")
            st.text_area("이미지 프롬프트", stringify_output(scene.get("image_prompt", {})), height=170, key=f"image_{i}")
            st.text_area("영상 프롬프트", stringify_output(scene.get("video_prompt", {})), height=170, key=f"video_{i}")


def render_card_news(cards: List[Dict[str, Any]]) -> None:
    for idx, card in enumerate(cards, 1):
        page = card.get("page", idx)
        with st.expander(f"카드뉴스 {page}장 · {card.get('headline', '')}", expanded=idx <= 2):
            st.markdown(f"**헤드라인**\n\n{card.get('headline', '')}")
            st.markdown(f"**본문**\n\n{card.get('body', '')}")
            st.markdown(f"**디자인 톤**\n\n{card.get('design_mood', '')}")
            st.markdown(f"**이미지 방향**\n\n{card.get('image_direction', '')}")
            st.markdown(f"**강조 자막**\n\n{card.get('key_caption', '')}")
            st.text_area("이미지 프롬프트 EN", card.get("image_prompt_en", ""), height=120, key=f"card_{idx}")


def init_session() -> None:
    defaults = {
        "auto_inputs": None,
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
        <p class=\"small-muted\">입력은 가볍게, 분석은 깊게. 레퍼런스 하나로 제작용 패키지를 뽑습니다.</p>
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
generation_scope = st.sidebar.selectbox(
    "생성 범위",
    ["숏폼+카드뉴스+이미지/영상 프롬프트", "숏폼 중심", "카드뉴스 중심", "이미지/영상 프롬프트 중심"],
    index=0,
)
card_count = st.sidebar.slider("카드뉴스 장수", 5, 12, 7)
run_quality = st.sidebar.checkbox("품질 검수까지 실행", value=True)

with st.sidebar.expander("Streamlit Secrets 안내"):
    st.code('OPENAI_API_KEY = "sk-..."', language="toml")

st.divider()

left, right = st.columns([0.9, 1.1], gap="large")

with left:
    st.subheader("1. 레퍼런스 입력")
    reference_text = st.text_area(
        "벤치마크 레퍼런스 텍스트 / 대본 / 카드뉴스 문구 / 광고 카피",
        placeholder="여기에 레퍼런스를 붙여넣으세요. AI가 주제, 타겟, 목표, CTA, 금지 표현까지 자동으로 추론합니다.",
        height=390,
    )

    with st.expander("선택 입력: AI 분석을 살짝만 유도하기"):
        override_topic = st.text_input("주제 덮어쓰기", placeholder="비워두면 레퍼런스에서 자동 추론")
        platform_hint = st.selectbox(
            "플랫폼 힌트",
            ["AI가 레퍼런스로 자동 판단", "YouTube Shorts", "Instagram Reels", "TikTok", "카드뉴스", "블로그", "혼합"],
            index=0,
        )
        tone_hint = st.selectbox(
            "톤 힌트",
            ["AI가 레퍼런스로 자동 판단", "커뮤니티 인기글형", "전문가 정보형", "자극적 후킹형", "다큐멘터리형", "광고 카피형", "브랜드 필름형"],
            index=0,
        )

    run_button = st.button("레퍼런스 분석 후 콘텐츠 패키지 생성", type="primary", use_container_width=True)

if run_button:
    if not reference_text.strip():
        st.warning("레퍼런스를 먼저 입력해주세요.")
    else:
        overrides = {
            "override_topic": override_topic.strip(),
            "platform_hint": platform_hint,
            "tone_hint": tone_hint,
            "generation_scope": generation_scope,
            "card_count": card_count,
            "output_language": output_language,
        }
        progress = st.progress(0)
        status = st.empty()

        status.info("1/4 레퍼런스에서 주제·타겟·목표·CTA·주의사항 자동 분석 중")
        st.session_state.reference_analysis = call_llm(
            REFERENCE_ANALYZER_SYSTEM,
            build_reference_prompt(reference_text, output_language, generation_scope, platform_hint, override_topic),
            model,
            temperature=0.25,
        )
        st.session_state.auto_inputs = apply_overrides(st.session_state.reference_analysis, overrides)
        progress.progress(28)

        status.info("2/4 자동 분석 브리프 기반 콘텐츠 전략 설계 중")
        st.session_state.strategy = call_llm(
            STRATEGY_SYSTEM,
            build_strategy_prompt(st.session_state.auto_inputs, st.session_state.reference_analysis),
            model,
            temperature=temperature,
        )
        progress.progress(55)

        status.info("3/4 최종 제작 패키지 생성 중")
        st.session_state.final_output = call_llm(
            FINAL_GENERATOR_SYSTEM,
            build_final_prompt(st.session_state.auto_inputs, st.session_state.reference_analysis, st.session_state.strategy),
            model,
            temperature=temperature,
        )
        progress.progress(84)

        if run_quality:
            status.info("4/4 품질 점수 평가 중")
            st.session_state.quality = call_llm(
                QUALITY_SYSTEM,
                build_quality_prompt(st.session_state.final_output),
                model,
                temperature=0.2,
            )
        else:
            st.session_state.quality = {"skipped": True}
        progress.progress(100)
        status.success("생성 완료. 레퍼런스에서 자동 추론한 값까지 함께 확인하세요.")

with right:
    st.subheader("2. 결과")

    if not st.session_state.final_output:
        st.info("레퍼런스를 입력하고 생성 버튼을 누르면 AI가 브리프부터 결과물까지 자동으로 만듭니다.")
    else:
        tabs = st.tabs(["자동 브리프", "숏폼 대본", "카드뉴스", "프롬프트", "제목/CTA", "검수", "전체 JSON"])

        auto_inputs = st.session_state.auto_inputs or {}
        final_output = st.session_state.final_output or {}
        shorts = final_output.get("one_minute_shorts", {}) or {}
        scenes = shorts.get("scenes", []) or []
        cards = final_output.get("card_news", []) or []

        with tabs[0]:
            render_auto_brief(auto_inputs)
            st.markdown("### 레퍼런스 DNA")
            st.json(st.session_state.reference_analysis)
            st.markdown("### 콘텐츠 전략")
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
            st.write(final_output.get("cta", auto_inputs.get("cta", "")))
            st.markdown("### 제작 체크리스트")
            st.write(final_output.get("production_checklist", []))

        with tabs[5]:
            st.json(st.session_state.quality)

        with tabs[6]:
            full_package = {
                "auto_inputs": auto_inputs,
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
