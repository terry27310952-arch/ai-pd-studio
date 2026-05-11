import csv
import io
import json
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

import streamlit as st
from openai import OpenAI
from supabase import create_client, Client

APP_TITLE = "AI PD Studio V3"
APP_SUBTITLE = "브랜드 관점 · 메시지 충돌 검사 · 카드뉴스 리듬까지 강제하는 콘텐츠 엔진"
TABLE_NAME = "content_history"
HISTORY_LIMIT = 20

st.set_page_config(page_title=APP_TITLE, page_icon="🎬", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
.main .block-container { padding-top: 2rem; max-width: 1360px; }
.hero-card { padding: 1.2rem 1.4rem; border: 1px solid rgba(120,120,120,.18); border-radius: 20px; background: linear-gradient(135deg, rgba(120,120,255,.12), rgba(255,255,255,.03)); }
.small-muted { color: #888; font-size: .92rem; }
</style>
""", unsafe_allow_html=True)

PACKAGE_SCHEMA = {
    "auto_brief": {
        "topic": "",
        "target": "",
        "platform": "",
        "tone": "",
        "goal": "",
        "cta": "",
        "image_ratio": "",
        "brand_pov": "",
        "risk_notes": []
    },
    "strategy_board": {
        "source_hook": "",
        "brand_point_of_view": "",
        "main_thesis": "",
        "misconception": "",
        "counter_claim": "",
        "message_conflict": "",
        "safe_reframe": "",
        "borrowed_authority_risk": "",
        "overwork_or_harm_risk": "",
        "evidence_bank": [],
        "card_flow": [],
        "visual_rhythm": [],
        "design_system": "",
        "final_question": ""
    },
    "card_news": [
        {
            "page": 1,
            "card_type": "hook | myth_busting | contrast | proof | formula | checklist | final_question",
            "intensity": "high | medium | low",
            "headline": "",
            "body": "",
            "key_caption": "",
            "brand_angle": "",
            "design_mood": "",
            "layout_type": "",
            "image_direction": "",
            "image_prompt_en": ""
        }
    ],
    "one_minute_shorts": {
        "title": "",
        "core_claim": "",
        "scenes": [
            {
                "time": "",
                "narration": "",
                "caption": "",
                "visual": "",
                "edit_point": "",
                "image_prompt": {"korean_direction": "", "english_prompt": "", "negative_prompt": "text, watermark, logo"},
                "video_prompt": {"korean_direction": "", "english_prompt": ""}
            }
        ]
    },
    "titles": [],
    "thumbnail_copy": [],
    "hashtags": [],
    "production_checklist": []
}

STRATEGY_SYSTEM = """
너는 카드뉴스 기획을 냉정하게 고치는 콘텐츠 전략가다.
레퍼런스를 그대로 요약하지 말고, 브랜드가 어떤 관점으로 해석할지 먼저 설계한다.

반드시 잡아라.
1. 유명인/권위자 인용이 중심을 잡아먹는지
2. 노동 미화, 과로 찬양, 성공팔이로 읽힐 위험이 있는지
3. 핵심 메시지가 서로 충돌하는지
4. 브랜드가 말하는 고유한 관점이 무엇인지
5. 독자가 저장할 한 줄 주장이 무엇인지
6. 카드뉴스 장별 리듬을 어떻게 줄 것인지
7. 디자인 강약을 어떻게 배치할 것인지

중요 원칙:
- 유명인은 주인공이 아니라 도입 장치다. 브랜드의 해석이 주인공이어야 한다.
- 창업/성공/생산성 콘텐츠에서 '많이 일하면 성공한다'로 단순화하지 마라.
- 장시간 노동 소재는 반드시 '검증된 방향 위에서만 의미 있다'로 안전하게 재해석하라.
- 좋은 카드뉴스는 사진+명언 반복이 아니라, hook/contrast/proof/formula/checklist/final question 구조를 가진다.
- 모든 장을 강하게 만들지 마라. 강한 장, 조용한 장, 비교 장, 공식 장을 섞어라.

금지 표현: 중요합니다, 살펴보겠습니다, 성공 공식, 대단하다, 놀랍다, 주목된다, 노력하면 됩니다, 열심히 하세요.
반드시 JSON만 출력한다.
"""

DRAFT_SYSTEM = """
너는 카드뉴스와 1분 쇼츠를 만드는 실무형 콘텐츠 PD다.
strategy_board를 기반으로 바로 제작 가능한 패키지를 만든다.

카드뉴스 강제 규칙:
- 1장만 권위자/유명인/강한 이미지 사용 가능. 이후는 브랜드 관점, 고객, 시장, 데이터, 검증 장면 중심.
- 각 장 card_type을 다르게 섞어라: hook, myth_busting, contrast, proof, formula, checklist, final_question.
- 1장과 6장만 high intensity 가능. 중간 장은 medium/low로 리듬을 만든다.
- 모든 장이 '사진 + 명언형 카피'가 되면 실패다.
- 반드시 브랜드 관점 문장 brand_angle을 넣어라.
- 마지막은 댓글 구걸이 아니라 체크 질문으로 끝내라.

쇼츠 강제 규칙:
- 첫 3초에 착각을 깨라.
- 인물 인용보다 브랜드 해석을 빠르게 세워라.
- 컷마다 긴장/이해/반전이 올라가야 한다.
- 마지막은 '당신의 아이디어는 믿음인가, 검증된 가설인가?' 같은 검증형 질문으로 끝내라.

반드시 JSON만 출력한다.
"""

CARD_DOCTOR_SYSTEM = """
너는 카드뉴스 닥터다. card_news만 다시 쓴다.
아래 문제를 반드시 고친다.
- 유명인 의존도 과다
- 과로 미화 위험
- 현실 판단과 장시간 노동의 메시지 충돌
- 교과서적 카피
- 모든 장이 같은 레이아웃인 문제
- 네온/HUD/강한 이미지 과잉

카피 방향:
- 창업자가 망하는 이유는 게을러서가 아니라, 틀린 걸 너무 열심히 해서다.
- 100시간을 일하라는 말이 아니다. 틀린 방향에 100시간 쓰면 실패도 2.5배 빨라진다.
- 창업은 열심히 하는 게임이 아니라, 틀렸는지 빨리 확인하는 게임이다.

디자인 방향:
- 1장 high, 2~5장 medium/low, 6장 infographic high, 7장 formula medium, 8장 quiet final.
- 1장만 유명인/권위자 분위기 허용. 나머지는 시장, 고객, 데이터, 검증, 노트, 대시보드, 회의 장면 중심.
- 인물 일관성 또는 비인물 데이터 오브젝트 중심으로 설계.

반환은 card_news와 quality_patch만 담은 JSON.
"""

QUALITY_SYSTEM = """
너는 업로드 전 최종 심사위원이다.
평가 기준:
- hook_score: 첫 장/첫 3초 멈춤력
- brand_score: 브랜드 관점이 유명인보다 앞서는가
- clarity_score: 메시지 충돌이 없는가
- risk_score: 노동 미화/성공팔이/단정 표현 위험이 낮은가
- rhythm_score: 카드별 강약과 레이아웃 변주가 있는가
- save_score: 저장하고 싶은 문장이 있는가
- upload_ready_score: 바로 업로드 가능한가

verdict는 업로드 가능, 수정 필요, 폐기 후 재작성 중 하나.
반드시 JSON만 출력한다.
"""

@st.cache_resource(show_spinner=False)
def get_supabase_client_cached(url: str, key: str) -> Client:
    return create_client(url, key)

@st.cache_resource(show_spinner=False)
def get_openai_client_cached(api_key: str) -> OpenAI:
    return OpenAI(api_key=api_key)


def get_secret(name: str) -> str:
    try:
        value = st.secrets.get(name, "")
    except Exception:
        value = ""
    return value or os.getenv(name, "")


def get_openai_client() -> OpenAI:
    api_key = get_secret("OPENAI_API_KEY")
    if not api_key:
        st.error("OPENAI_API_KEY가 없습니다. Streamlit Secrets에 추가해주세요.")
        st.stop()
    return get_openai_client_cached(api_key)


def get_supabase_client() -> Optional[Client]:
    url = get_secret("SUPABASE_URL")
    key = get_secret("SUPABASE_SERVICE_ROLE_KEY") or get_secret("SUPABASE_ANON_KEY")
    if not url or not key:
        return None
    try:
        return get_supabase_client_cached(url, key)
    except Exception as exc:
        st.warning(f"Supabase 연결 실패: {exc}")
        return None


def storage_mode() -> str:
    return "Supabase DB" if get_supabase_client() else "연결 안 됨"


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
    res = get_openai_client().chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
        temperature=temperature,
        response_format={"type": "json_object"},
    )
    return extract_json(res.choices[0].message.content or "{}")


def build_strategy_prompt(reference_text: str, brand_pov: str, output_language: str, image_ratio: str, card_count: int, platform_hint: str, tone_hint: str, override_topic: str) -> str:
    return f"""
레퍼런스를 분석해서 strategy_board를 만들어라.

설정:
- 출력 언어: {output_language}
- 이미지/영상 비율: {image_ratio}
- 카드뉴스 장수: {card_count}
- 플랫폼 힌트: {platform_hint}
- 톤 힌트: {tone_hint}
- 주제 덮어쓰기: {override_topic}
- 브랜드 관점 입력: {brand_pov}

반드시 아래 JSON 형식으로 출력:
{{
  "auto_brief": {{"topic":"", "target":"", "platform":"", "tone":"", "goal":"", "cta":"", "image_ratio":"{image_ratio}", "brand_pov":"", "risk_notes":[]}},
  "strategy_board": {{
    "source_hook":"레퍼런스에서 쓸 수 있는 도입 장치",
    "brand_point_of_view":"브랜드가 이 소재를 어떻게 해석하는지",
    "main_thesis":"저장하고 싶은 한 줄 주장",
    "misconception":"독자의 착각",
    "counter_claim":"착각을 깨는 반박",
    "message_conflict":"메시지 충돌 여부와 해결책",
    "safe_reframe":"위험한 표현을 안전하고 날카롭게 바꾼 해석",
    "borrowed_authority_risk":"유명인 의존도 진단",
    "overwork_or_harm_risk":"과로/노동 미화 위험 진단",
    "evidence_bank":["숫자/고유명사/사례"],
    "card_flow":["1장 역할", "2장 역할"],
    "visual_rhythm":["1장 high", "2장 low"],
    "design_system":"전체 디자인 원칙",
    "final_question":"마지막 체크 질문"
  }}
}}

레퍼런스:
{reference_text}
"""


def build_draft_prompt(strategy_data: Dict[str, Any], card_count: int, image_ratio: str) -> str:
    return f"""
strategy_board를 기반으로 전체 콘텐츠 패키지를 만들어라.
카드뉴스는 {card_count}장, 이미지/영상 비율은 {image_ratio}.
출력 JSON 스키마 예시:
{json.dumps(PACKAGE_SCHEMA, ensure_ascii=False, indent=2)}
strategy_board:
{json.dumps(strategy_data, ensure_ascii=False, indent=2)}
"""


def build_card_doctor_prompt(package: Dict[str, Any], card_count: int, image_ratio: str) -> str:
    return f"""
card_news만 업로드 가능한 수준으로 재작성해라.
카드뉴스 장수: {card_count}, 이미지 비율: {image_ratio}
반환 JSON: {{"card_news":[], "quality_patch":{{"rewrite_reason":[], "brand_score":0, "rhythm_score":0, "risk_score":0}}}}
패키지:
{json.dumps(package, ensure_ascii=False, indent=2)}
"""


def build_quality_prompt(package: Dict[str, Any]) -> str:
    return f"""
이 콘텐츠 패키지를 심사해라.
반환 JSON: {{"verdict":"업로드 가능 | 수정 필요 | 폐기 후 재작성", "scores":{{"hook_score":0, "brand_score":0, "clarity_score":0, "risk_score":0, "rhythm_score":0, "save_score":0, "upload_ready_score":0}}, "critical_issues":[], "rewrite_actions":[]}}
패키지:
{json.dumps(package, ensure_ascii=False, indent=2)}
"""


def stringify(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def package_to_rows(package: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    brief = package.get("auto_brief", {}) or {}
    for card in package.get("card_news", []) or []:
        rows.append({
            "type": "card_news",
            "index": card.get("page", ""),
            "card_type": card.get("card_type", ""),
            "intensity": card.get("intensity", ""),
            "headline": card.get("headline", ""),
            "body": card.get("body", ""),
            "key_caption": card.get("key_caption", ""),
            "brand_angle": card.get("brand_angle", ""),
            "layout_type": card.get("layout_type", ""),
            "image_prompt": card.get("image_prompt_en", ""),
            "image_ratio": brief.get("image_ratio", ""),
        })
    shorts = package.get("one_minute_shorts", {}) or {}
    for idx, scene in enumerate(shorts.get("scenes", []) or [], 1):
        rows.append({
            "type": "shorts_scene",
            "index": idx,
            "card_type": "",
            "intensity": "",
            "headline": scene.get("caption", ""),
            "body": scene.get("narration", ""),
            "key_caption": shorts.get("core_claim", ""),
            "brand_angle": "",
            "layout_type": scene.get("visual", ""),
            "image_prompt": json.dumps(scene.get("image_prompt", {}), ensure_ascii=False),
            "image_ratio": brief.get("image_ratio", ""),
        })
    return rows


def to_csv(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return ""
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def save_history_item(package: Dict[str, Any]) -> None:
    supabase = get_supabase_client()
    if not supabase:
        st.warning("Supabase가 연결되지 않아 저장하지 못했습니다.")
        return
    brief = package.get("auto_brief", {}) or {}
    gate = package.get("quality_gate", {}) or {}
    payload = {
        "topic": brief.get("topic") or "무제",
        "verdict": gate.get("verdict", ""),
        "reference_preview": package.get("reference_preview", ""),
        "image_ratio": brief.get("image_ratio", ""),
        "package": package,
    }
    try:
        supabase.table(TABLE_NAME).insert(payload).execute()
    except Exception as exc:
        st.error(f"Supabase 저장 실패: {exc}")


def load_history_meta(limit: int = HISTORY_LIMIT) -> List[Dict[str, Any]]:
    supabase = get_supabase_client()
    if not supabase:
        return []
    try:
        res = supabase.table(TABLE_NAME).select("id, created_at, topic, verdict, reference_preview, image_ratio").order("created_at", desc=True).limit(limit).execute()
        return res.data or []
    except Exception as exc:
        st.error(f"히스토리 목록 조회 실패: {exc}")
        return []


def load_history_package(row_id: str) -> Optional[Dict[str, Any]]:
    supabase = get_supabase_client()
    if not supabase:
        return None
    try:
        res = supabase.table(TABLE_NAME).select("id, created_at, package").eq("id", row_id).limit(1).execute()
        rows = res.data or []
        if not rows:
            return None
        package = rows[0].get("package") or {}
        if isinstance(package, str):
            package = json.loads(package)
        package.setdefault("db_id", rows[0].get("id"))
        package.setdefault("generated_at", rows[0].get("created_at"))
        return package
    except Exception as exc:
        st.error(f"히스토리 상세 조회 실패: {exc}")
        return None


def delete_history_item(row_id: str) -> None:
    supabase = get_supabase_client()
    if supabase:
        supabase.table(TABLE_NAME).delete().eq("id", row_id).execute()


def render_package(package: Dict[str, Any]) -> None:
    gate = package.get("quality_gate", {}) or {}
    scores = gate.get("scores", {}) or {}
    verdict = gate.get("verdict", "")
    if verdict:
        st.markdown(f"### 업로드 판정: {verdict}")
        cols = st.columns(4)
        for idx, key in enumerate(["hook_score", "brand_score", "risk_score", "upload_ready_score"]):
            with cols[idx]:
                st.metric(key, scores.get(key, "-"))

    tabs = st.tabs(["카드뉴스", "쇼츠", "전략 보드", "프롬프트", "CSV/JSON", "품질 심사"])
    with tabs[0]:
        for i, card in enumerate(package.get("card_news", []) or [], 1):
            title = f"{card.get('page', i)}장 · {card.get('card_type','')} · {card.get('intensity','')} · {card.get('headline','')}"
            with st.expander(title, expanded=i <= 2):
                st.markdown(f"**헤드라인**\n\n{card.get('headline','')}")
                st.markdown(f"**본문**\n\n{card.get('body','')}")
                st.markdown(f"**저장 문장**\n\n{card.get('key_caption','')}")
                st.markdown(f"**브랜드 관점**\n\n{card.get('brand_angle','')}")
                st.markdown(f"**레이아웃**\n\n{card.get('layout_type','')}")
                st.markdown(f"**디자인 톤**\n\n{card.get('design_mood','')}")
                st.text_area("이미지 프롬프트 EN", card.get("image_prompt_en", ""), height=120, key=f"card_{i}_{id(card)}")
    with tabs[1]:
        shorts = package.get("one_minute_shorts", {}) or {}
        st.markdown(f"### {shorts.get('title', '쇼츠 대본')}")
        st.markdown(f"**핵심 주장**: {shorts.get('core_claim', '')}")
        for i, scene in enumerate(shorts.get("scenes", []) or [], 1):
            with st.expander(f"컷 {i} · {scene.get('time', '')}", expanded=i <= 2):
                st.markdown(f"**내레이션**\n\n{scene.get('narration','')}")
                st.markdown(f"**자막**\n\n{scene.get('caption','')}")
                st.markdown(f"**화면**\n\n{scene.get('visual','')}")
                st.text_area("영상 프롬프트", stringify(scene.get("video_prompt", {})), height=100, key=f"vid_{i}_{id(scene)}")
    with tabs[2]:
        st.json(package.get("strategy_board", {}))
    with tabs[3]:
        prompt_text = []
        for card in package.get("card_news", []) or []:
            prompt_text.append(f"카드 {card.get('page','')} 이미지\n{card.get('image_prompt_en','')}\n")
        for i, scene in enumerate((package.get("one_minute_shorts", {}) or {}).get("scenes", []) or [], 1):
            prompt_text.append(f"컷 {i} 영상\n{stringify(scene.get('video_prompt', {}))}\n")
        st.text_area("프롬프트 모음", "\n".join(prompt_text), height=420)
    with tabs[4]:
        csv_text = to_csv(package_to_rows(package))
        st.download_button("CSV 다운로드", csv_text, file_name="ai_pd_studio_v3_content.csv", mime="text/csv", use_container_width=True)
        st.download_button("JSON 다운로드", stringify(package), file_name="ai_pd_studio_v3_output.json", mime="application/json", use_container_width=True)
    with tabs[5]:
        st.json(gate)


def render_history() -> None:
    st.subheader("히스토리")
    st.caption(f"현재 저장 방식: {storage_mode()} · 목록만 가볍게 불러오고, 상세는 선택한 1개만 로드합니다.")
    limit = st.slider("불러올 목록 수", 5, 50, HISTORY_LIMIT, 5)
    if st.button("히스토리 목록 새로고침", use_container_width=True) or "history_meta" not in st.session_state:
        st.session_state.history_meta = load_history_meta(limit)
    meta = st.session_state.history_meta
    if not meta:
        st.info("저장된 히스토리가 없거나 Supabase 연결이 없습니다.")
        return
    labels = [f"{i+1}. {row.get('created_at','')} · {row.get('verdict','')} · {row.get('topic','무제')}" for i, row in enumerate(meta)]
    selected = st.selectbox("생성 히스토리", labels)
    row = meta[labels.index(selected)]
    st.json({k: row.get(k) for k in ["id", "created_at", "topic", "verdict", "image_ratio", "reference_preview"]})
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("상세 불러오기", use_container_width=True):
            package = load_history_package(row.get("id"))
            if package:
                st.session_state.package = package
                st.success("상세를 불러왔습니다. 콘텐츠 생성 메뉴에서 확인하세요.")
    with col2:
        if st.button("선택 JSON 다운로드 준비", use_container_width=True):
            package = load_history_package(row.get("id"))
            if package:
                st.download_button("선택 JSON 다운로드", stringify(package), file_name="history_item.json", mime="application/json", use_container_width=True)
    with col3:
        if st.button("DB에서 삭제", use_container_width=True):
            delete_history_item(row.get("id"))
            st.session_state.history_meta = load_history_meta(limit)
            st.rerun()


if "package" not in st.session_state:
    st.session_state.package = None
if "menu" not in st.session_state:
    st.session_state.menu = "콘텐츠 생성"

st.markdown(f"""<div class='hero-card'><h1>{APP_TITLE}</h1><p>{APP_SUBTITLE}</p><p class='small-muted'>유명인 의존도, 노동 미화 위험, 메시지 충돌, 디자인 리듬을 생성 전에 검사합니다.</p></div>""", unsafe_allow_html=True)

st.sidebar.header("메인 메뉴")
menu = st.sidebar.radio("이동", ["콘텐츠 생성", "히스토리"], key="menu")
st.sidebar.header("⚙️ 생성 설정")
model = st.sidebar.selectbox("OpenAI 모델", ["gpt-4.1-mini", "gpt-4.1", "gpt-4o-mini", "gpt-4o"], index=0)
temperature = st.sidebar.slider("창의성", 0.1, 1.2, 0.75, 0.05)
output_language = st.sidebar.selectbox("출력 언어", ["한국어", "영어", "한국어+영어"], index=0)
image_ratio = st.sidebar.selectbox("이미지/영상 비율", ["9:16 vertical shorts", "1:1 square card news", "4:5 Instagram feed", "16:9 YouTube wide", "3:4 portrait"], index=1)
card_count = st.sidebar.slider("카드뉴스 장수", 5, 12, 8)
use_card_doctor = st.sidebar.checkbox("카드뉴스 닥터 사용", value=True)
use_quality_gate = st.sidebar.checkbox("품질 심사 사용", value=True)
with st.sidebar.expander("Secrets 확인"):
    st.code('OPENAI_API_KEY = "sk-..."\nSUPABASE_URL = "https://...supabase.co"\nSUPABASE_SERVICE_ROLE_KEY = "sb_secret_..."', language="toml")
    st.caption(f"현재 저장 방식: {storage_mode()}")

st.divider()

if menu == "히스토리":
    render_history()
else:
    left, right = st.columns([0.84, 1.16], gap="large")
    with left:
        st.subheader("1. 레퍼런스 입력")
        reference_text = st.text_area("레퍼런스 텍스트 / CSV 내용 / 대본 / 카드뉴스 문구", height=360, placeholder="여기에 레퍼런스를 붙여넣으세요.")
        with st.expander("브랜드/전략 입력"):
            brand_pov = st.text_area("브랜드 관점", height=120, placeholder="예: 우리는 창업을 감성이 아니라 검증 가능한 제작 시스템으로 본다.")
            override_topic = st.text_input("주제 덮어쓰기", placeholder="비워두면 자동 추론")
            platform_hint = st.selectbox("플랫폼 힌트", ["AI가 판단", "Instagram 카드뉴스", "YouTube Shorts", "Instagram Reels", "TikTok", "혼합"], index=0)
            tone_hint = st.selectbox("톤 힌트", ["커뮤니티 인기글형", "전문가 정보형", "자극적 후킹형", "다큐멘터리형", "광고 카피형"], index=0)
        run_button = st.button("브랜드 관점으로 콘텐츠 생성", type="primary", use_container_width=True)

    if run_button:
        if not reference_text.strip():
            st.warning("레퍼런스를 먼저 입력해주세요.")
        else:
            progress = st.progress(0)
            status = st.empty()
            status.info("1/4 전략 보드 생성 중: 유명인 의존도, 노동 미화 위험, 메시지 충돌 검사")
            strategy_data = call_llm(STRATEGY_SYSTEM, build_strategy_prompt(reference_text, brand_pov, output_language, image_ratio, card_count, platform_hint, tone_hint, override_topic), model, 0.3)
            progress.progress(25)

            status.info("2/4 콘텐츠 패키지 생성 중")
            package = call_llm(DRAFT_SYSTEM, build_draft_prompt(strategy_data, card_count, image_ratio), model, temperature)
            package["auto_brief"] = strategy_data.get("auto_brief", package.get("auto_brief", {}))
            package["strategy_board"] = strategy_data.get("strategy_board", package.get("strategy_board", {}))
            progress.progress(55)

            if use_card_doctor:
                status.info("3/4 카드뉴스 닥터 재작성 중")
                card_patch = call_llm(CARD_DOCTOR_SYSTEM, build_card_doctor_prompt(package, card_count, image_ratio), model, min(1.0, temperature + 0.05))
                if card_patch.get("card_news"):
                    package["card_news"] = card_patch["card_news"]
                package.setdefault("quality", {})["card_doctor"] = card_patch.get("quality_patch", {})
            progress.progress(78)

            if use_quality_gate:
                status.info("4/4 품질 심사 중")
                package["quality_gate"] = call_llm(QUALITY_SYSTEM, build_quality_prompt(package), model, 0.2)

            package["generated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            package["reference_preview"] = reference_text[:300]
            package.setdefault("auto_brief", {}).setdefault("image_ratio", image_ratio)
            st.session_state.package = package
            save_history_item(package)
            st.session_state.history_meta = load_history_meta(HISTORY_LIMIT)
            progress.progress(100)
            status.success("생성 완료. 브랜드 관점과 카드뉴스 리듬을 적용했습니다.")

    with right:
        st.subheader("2. 결과")
        if not st.session_state.package:
            st.info("레퍼런스를 입력하고 생성하면 결과가 여기에 표시됩니다.")
        else:
            render_package(st.session_state.package)
