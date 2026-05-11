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

APP_TITLE = "AI PD Studio V2 Light"
APP_SUBTITLE = "히스토리 경량화 · Supabase 영구 저장 · 카드뉴스/쇼츠 생성 엔진"
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

ANGLE_BOARD_SYSTEM = """
너는 콘텐츠 편집장이다. 레퍼런스를 받아서 바로 대본을 쓰지 말고, 먼저 업로드 가능한 관점을 설계한다.
목표는 정보 정리가 아니라 시청자가 멈추고, 저장하고, 댓글을 달게 만드는 관점 설계다.
반드시 다음을 찾는다: 독자가 가진 착각, 그 착각을 깨는 반박, 댓글이 갈릴 논쟁 지점, 저장/공유 이유, 구체 숫자/고유명사/사례, 확인 필요 정보, 카드뉴스 감정 순서, 쇼츠 감정 순서, 업로드 리스크.
죽은 표현 금지: 중요합니다, 살펴보겠습니다, 주목받고 있습니다, 영향이 있습니다, 신중한 접근, 미래가 기대됩니다, 첫걸음, 성공 공식.
반드시 JSON만 출력한다.
"""

DRAFT_SYSTEM = """
너는 카드뉴스와 1분 쇼츠를 동시에 설계하는 실무형 콘텐츠 PD다.
ANGLE BOARD를 기반으로 전체 콘텐츠 패키지를 만든다.
정보 나열 금지. 반드시 착각 파괴 → 증거 → 문제의 본질 → 반전/해석 → 행동 유도로 구성한다.
카드뉴스: 첫 장은 독자 착각을 찌르는 문장, 각 장은 한 감정만 담당, headline은 20자 내외, body는 2~3문장 이내, 저장하고 싶은 key_caption 필수.
쇼츠: 0~3초는 질문보다 강한 주장/반전 우선, 7~9컷, 숫자/고유명사/구체 장면, visual은 실제 장면/오브젝트/스크린/인물/사건, video_prompt는 영어이며 카메라 무빙으로 시작.
반드시 JSON만 출력한다.
"""

CARDNEWS_DOCTOR_SYSTEM = """
너는 한국 커뮤니티 인기글 감각을 가진 카드뉴스 전문 편집자다. card_news만 재작성한다.
목표는 예쁜 요약본이 아니라 저장/공유가 생기는 카드뉴스다.
헤드라인은 독자의 변명, 불안, 욕망, 자기합리화를 찔러야 한다. 각 장 첫 문장은 주장 또는 반박이어야 한다. 추상어 대신 구체 장면, 숫자, 오브젝트를 넣는다. '대단하다/놀랍다/중요하다/필요하다' 제거.
반환은 card_news와 quality_patch만 담은 JSON.
"""

SHORTS_DOCTOR_SYSTEM = """
너는 1분 쇼츠 리텐션 작가다. one_minute_shorts만 재작성한다.
첫 3초에 착각을 깨고, 컷마다 긴장도가 올라가야 한다. 느슨한 질문 금지. 마지막은 관점 있는 결론으로 끝내고 댓글 유도는 논쟁 포인트로 한다. visual은 실제 사건 중심. video_prompt는 영어이며 카메라 무빙으로 시작.
반환은 one_minute_shorts와 quality_patch만 담은 JSON.
"""

QUALITY_GATE_SYSTEM = """
너는 업로드 전 최종 심사위원이다.
점수: hook_score, claim_score, specificity_score, retention_score, save_score, scene_score, upload_ready_score.
verdict는 업로드 가능, 수정 필요, 폐기 후 재작성 중 하나다.
반드시 JSON만 출력한다.
"""

PACKAGE_SCHEMA = {
    "auto_brief": {"topic":"", "target":"", "platform":"", "tone":"", "goal":"", "cta":"", "image_ratio":"", "risk_notes":[]},
    "angle_board": {"misconception":"", "counter_claim":"", "core_claim":"", "comment_trigger":"", "save_reason":"", "evidence_bank":[], "needs_verification":[], "card_emotion_order":[], "shorts_emotion_order":[], "upload_risks":[]},
    "one_minute_shorts": {"title":"", "core_claim":"", "scenes":[{"time":"", "narration":"", "caption":"", "visual":"", "edit_point":"", "image_prompt":{"korean_direction":"", "english_prompt":"", "negative_prompt":"text, watermark, logo"}, "video_prompt":{"korean_direction":"", "english_prompt":""}}]},
    "card_news": [{"page":1, "emotion_role":"", "headline":"", "body":"", "key_caption":"", "design_mood":"", "image_direction":"", "image_prompt_en":""}],
    "thumbnail_copy": [],
    "titles": [],
    "hashtags": [],
    "production_checklist": []
}

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
        st.error("OPENAI_API_KEY가 없습니다. Streamlit Secrets에 OPENAI_API_KEY를 추가해주세요.")
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


def load_history_meta(limit: int = HISTORY_LIMIT) -> List[Dict[str, Any]]:
    supabase = get_supabase_client()
    if not supabase:
        return []
    try:
        res = (
            supabase.table(TABLE_NAME)
            .select("id, created_at, topic, verdict, reference_preview, image_ratio")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
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


def delete_history_item(row_id: str) -> None:
    supabase = get_supabase_client()
    if not supabase:
        return
    try:
        supabase.table(TABLE_NAME).delete().eq("id", row_id).execute()
    except Exception as exc:
        st.error(f"삭제 실패: {exc}")


def build_angle_prompt(reference_text: str, output_language: str, image_ratio: str, card_count: int, platform_hint: str, tone_hint: str, override_topic: str) -> str:
    return f"""
레퍼런스를 분석해서 ANGLE BOARD를 만들어라.
설정: 출력 언어={output_language}, 이미지/영상 비율={image_ratio}, 카드뉴스 장수={card_count}, 플랫폼 힌트={platform_hint}, 톤 힌트={tone_hint}, 주제 덮어쓰기={override_topic}
출력 JSON: {{"auto_brief": {{"topic":"", "target":"", "platform":"", "tone":"", "goal":"", "cta":"", "image_ratio":"{image_ratio}", "risk_notes":[]}}, "angle_board": {{"misconception":"", "counter_claim":"", "core_claim":"", "comment_trigger":"", "save_reason":"", "evidence_bank":[], "needs_verification":[], "card_emotion_order":[], "shorts_emotion_order":[], "upload_risks":[]}}}}
레퍼런스:
{reference_text}
"""


def build_draft_prompt(angle_data: Dict[str, Any], card_count: int, image_ratio: str) -> str:
    return f"""
ANGLE BOARD를 기반으로 전체 콘텐츠 패키지를 만들어라.
카드뉴스는 {card_count}장, 이미지/영상 비율은 {image_ratio}.
출력 JSON 스키마 예시:
{json.dumps(PACKAGE_SCHEMA, ensure_ascii=False, indent=2)}
ANGLE BOARD:
{json.dumps(angle_data, ensure_ascii=False, indent=2)}
"""


def build_card_doctor_prompt(package: Dict[str, Any], card_count: int, image_ratio: str) -> str:
    return f"""
이 패키지의 card_news만 업로드 가능한 수준으로 재작성해라.
카드뉴스 장수: {card_count}, 이미지 비율: {image_ratio}
반환 JSON: {{"card_news":[{{"page":1,"emotion_role":"","headline":"","body":"","key_caption":"","design_mood":"","image_direction":"","image_prompt_en":""}}], "quality_patch":{{"cardnews_rewrite_reason":[], "cardnews_hook_score":0, "cardnews_save_score":0}}}}
패키지:
{json.dumps(package, ensure_ascii=False, indent=2)}
"""


def build_shorts_doctor_prompt(package: Dict[str, Any], image_ratio: str) -> str:
    return f"""
이 패키지의 one_minute_shorts만 업로드 가능한 수준으로 재작성해라.
이미지/영상 비율: {image_ratio}
반환 JSON: {{"one_minute_shorts":{{"title":"", "core_claim":"", "scenes":[{{"time":"0-3초", "narration":"", "caption":"", "visual":"", "edit_point":"", "image_prompt":{{"korean_direction":"", "english_prompt":"", "negative_prompt":"text, watermark, logo"}}, "video_prompt":{{"korean_direction":"", "english_prompt":""}}}}]}}, "quality_patch":{{"shorts_rewrite_reason":[], "shorts_hook_score":0, "shorts_retention_score":0}}}}
패키지:
{json.dumps(package, ensure_ascii=False, indent=2)}
"""


def build_quality_prompt(package: Dict[str, Any]) -> str:
    return f"""
이 콘텐츠 패키지를 심사해라. final_package는 만들지 말고 평가만 해라.
반환 JSON: {{"verdict":"업로드 가능 | 수정 필요 | 폐기 후 재작성", "scores":{{"hook_score":0, "claim_score":0, "specificity_score":0, "retention_score":0, "save_score":0, "scene_score":0, "upload_ready_score":0}}, "critical_issues":[], "rewrite_actions":[]}}
패키지:
{json.dumps(package, ensure_ascii=False, indent=2)}
"""


def merge_doctors(package: Dict[str, Any], card_patch: Dict[str, Any], shorts_patch: Dict[str, Any]) -> Dict[str, Any]:
    if card_patch.get("card_news"):
        package["card_news"] = card_patch["card_news"]
    if shorts_patch.get("one_minute_shorts"):
        package["one_minute_shorts"] = shorts_patch["one_minute_shorts"]
    package.setdefault("quality", {})
    package["quality"]["cardnews_doctor"] = card_patch.get("quality_patch", {})
    package["quality"]["shorts_doctor"] = shorts_patch.get("quality_patch", {})
    return package


def stringify(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def package_to_rows(package: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    brief = package.get("auto_brief", {}) or {}
    shorts = package.get("one_minute_shorts", {}) or {}
    for idx, scene in enumerate(shorts.get("scenes", []) or [], 1):
        rows.append({"type":"shorts_scene", "index":idx, "title":shorts.get("title", ""), "core_claim":shorts.get("core_claim", ""), "time":scene.get("time", ""), "headline_or_caption":scene.get("caption", ""), "body_or_narration":scene.get("narration", ""), "visual":scene.get("visual", ""), "edit_point":scene.get("edit_point", ""), "image_prompt":json.dumps(scene.get("image_prompt", {}), ensure_ascii=False), "video_prompt":json.dumps(scene.get("video_prompt", {}), ensure_ascii=False), "image_ratio":brief.get("image_ratio", "")})
    for idx, card in enumerate(package.get("card_news", []) or [], 1):
        rows.append({"type":"card_news", "index":card.get("page", idx), "title":"", "core_claim":package.get("angle_board", {}).get("core_claim", ""), "time":"", "headline_or_caption":card.get("headline", ""), "body_or_narration":card.get("body", ""), "visual":card.get("image_direction", ""), "edit_point":card.get("design_mood", ""), "image_prompt":card.get("image_prompt_en", ""), "video_prompt":"", "image_ratio":brief.get("image_ratio", "")})
    return rows


def to_csv(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return ""
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def render_package(package: Dict[str, Any]) -> None:
    gate = package.get("quality_gate", {}) or {}
    scores = gate.get("scores", {}) or {}
    verdict = gate.get("verdict", "")
    if verdict:
        st.markdown(f"### 업로드 판정: {verdict}")
        cols = st.columns(4)
        for idx, key in enumerate(["hook_score", "claim_score", "specificity_score", "upload_ready_score"]):
            with cols[idx]:
                st.metric(key, scores.get(key, "-"))

    tabs = st.tabs(["쇼츠", "카드뉴스", "관점 보드", "프롬프트", "CSV/JSON", "품질 심사"])
    with tabs[0]:
        shorts = package.get("one_minute_shorts", {}) or {}
        st.markdown(f"### {shorts.get('title', '쇼츠 대본')}")
        st.markdown(f"**핵심 주장**: {shorts.get('core_claim', '')}")
        for i, scene in enumerate(shorts.get("scenes", []) or [], 1):
            with st.expander(f"컷 {i} · {scene.get('time', '')}", expanded=i <= 2):
                st.markdown(f"**내레이션**\n\n{scene.get('narration','')}")
                st.markdown(f"**자막**\n\n{scene.get('caption','')}")
                st.markdown(f"**화면**\n\n{scene.get('visual','')}")
                st.markdown(f"**편집 포인트**\n\n{scene.get('edit_point','')}")
                st.text_area("이미지 프롬프트", stringify(scene.get("image_prompt", {})), height=130, key=f"img_{i}_{id(scene)}")
                st.text_area("영상 프롬프트", stringify(scene.get("video_prompt", {})), height=130, key=f"vid_{i}_{id(scene)}")
    with tabs[1]:
        for i, card in enumerate(package.get("card_news", []) or [], 1):
            with st.expander(f"{card.get('page', i)}장 · {card.get('headline','')}", expanded=i <= 2):
                st.markdown(f"**감정 역할**: {card.get('emotion_role','')}")
                st.markdown(f"**헤드라인**\n\n{card.get('headline','')}")
                st.markdown(f"**본문**\n\n{card.get('body','')}")
                st.markdown(f"**저장 문장**\n\n{card.get('key_caption','')}")
                st.markdown(f"**디자인 톤**\n\n{card.get('design_mood','')}")
                st.text_area("이미지 프롬프트 EN", card.get("image_prompt_en", ""), height=100, key=f"card_{i}_{id(card)}")
    with tabs[2]:
        st.json(package.get("angle_board", {}))
    with tabs[3]:
        prompt_text = []
        for i, scene in enumerate((package.get("one_minute_shorts", {}) or {}).get("scenes", []) or [], 1):
            prompt_text.append(f"컷 {i} 이미지\n{stringify(scene.get('image_prompt', {}))}\n")
            prompt_text.append(f"컷 {i} 영상\n{stringify(scene.get('video_prompt', {}))}\n")
        st.text_area("프롬프트 모음", "\n".join(prompt_text), height=420)
    with tabs[4]:
        csv_text = to_csv(package_to_rows(package))
        st.download_button("CSV 다운로드", csv_text, file_name="ai_pd_studio_content.csv", mime="text/csv", use_container_width=True)
        st.download_button("JSON 다운로드", stringify(package), file_name="ai_pd_studio_output.json", mime="application/json", use_container_width=True)
    with tabs[5]:
        st.json(gate)


def render_history() -> None:
    st.subheader("히스토리")
    st.caption(f"현재 저장 방식: {storage_mode()} · 목록은 가볍게 불러오고, 선택한 1개만 상세 로드합니다.")
    limit = st.slider("불러올 목록 수", 5, 50, HISTORY_LIMIT, 5)
    if st.button("히스토리 목록 새로고침", use_container_width=True):
        st.session_state.history_meta = load_history_meta(limit)
        st.rerun()
    if "history_meta" not in st.session_state:
        st.session_state.history_meta = load_history_meta(limit)
    meta = st.session_state.history_meta
    if not meta:
        st.info("저장된 히스토리가 없거나 Supabase 연결이 없습니다.")
        return
    labels = []
    for idx, row in enumerate(meta):
        labels.append(f"{idx+1}. {row.get('created_at','')} · {row.get('verdict','')} · {row.get('topic','무제')}")
    selected = st.selectbox("생성 히스토리", labels)
    row = meta[labels.index(selected)]
    st.json({"id": row.get("id"), "created_at": row.get("created_at"), "topic": row.get("topic"), "verdict": row.get("verdict"), "image_ratio": row.get("image_ratio"), "reference_preview": row.get("reference_preview")})
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("상세 불러오기", use_container_width=True):
            package = load_history_package(row.get("id"))
            if package:
                st.session_state.package = package
                st.success("상세를 불러왔습니다. 콘텐츠 생성 메뉴에서 확인하세요.")
    with col2:
        package = load_history_package(row.get("id")) if st.button("선택 JSON 준비", use_container_width=True) else None
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

st.markdown(f"""<div class='hero-card'><h1>{APP_TITLE}</h1><p>{APP_SUBTITLE}</p><p class='small-muted'>히스토리는 목록만 가볍게 조회하고, 상세는 클릭 시 1개만 불러옵니다.</p></div>""", unsafe_allow_html=True)

st.sidebar.header("메인 메뉴")
menu = st.sidebar.radio("이동", ["콘텐츠 생성", "히스토리"], key="menu")
st.sidebar.header("⚙️ 생성 설정")
model = st.sidebar.selectbox("OpenAI 모델", ["gpt-4.1-mini", "gpt-4.1", "gpt-4o-mini", "gpt-4o"], index=0)
temperature = st.sidebar.slider("창의성", 0.1, 1.2, 0.75, 0.05)
output_language = st.sidebar.selectbox("출력 언어", ["한국어", "영어", "한국어+영어"], index=0)
image_ratio = st.sidebar.selectbox("이미지/영상 비율", ["9:16 vertical shorts", "1:1 square card news", "4:5 Instagram feed", "16:9 YouTube wide", "3:4 portrait"], index=0)
card_count = st.sidebar.slider("카드뉴스 장수", 5, 12, 8)
use_doctor = st.sidebar.checkbox("고급 리라이트 사용", value=True)
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
        reference_text = st.text_area("레퍼런스 텍스트 / CSV 내용 / 대본 / 카드뉴스 문구", height=420, placeholder="여기에 레퍼런스를 붙여넣으세요.")
        with st.expander("선택 입력"):
            override_topic = st.text_input("주제 덮어쓰기", placeholder="비워두면 자동 추론")
            platform_hint = st.selectbox("플랫폼 힌트", ["AI가 판단", "YouTube Shorts", "Instagram Reels", "TikTok", "카드뉴스", "혼합"], index=0)
            tone_hint = st.selectbox("톤 힌트", ["커뮤니티 인기글형", "전문가 정보형", "자극적 후킹형", "다큐멘터리형", "광고 카피형"], index=0)
        run_button = st.button("콘텐츠 생성", type="primary", use_container_width=True)

    if run_button:
        if not reference_text.strip():
            st.warning("레퍼런스를 먼저 입력해주세요.")
        else:
            progress = st.progress(0)
            status = st.empty()
            status.info("1/4 관점 보드 생성 중")
            angle_data = call_llm(ANGLE_BOARD_SYSTEM, build_angle_prompt(reference_text, output_language, image_ratio, card_count, platform_hint, tone_hint, override_topic), model, 0.3)
            progress.progress(25)
            status.info("2/4 전체 초안 생성 중")
            package = call_llm(DRAFT_SYSTEM, build_draft_prompt(angle_data, card_count, image_ratio), model, temperature)
            package["auto_brief"] = angle_data.get("auto_brief", package.get("auto_brief", {}))
            package["angle_board"] = angle_data.get("angle_board", package.get("angle_board", {}))
            progress.progress(50)
            if use_doctor:
                status.info("3/4 카드뉴스/쇼츠 리라이트 중")
                card_patch = call_llm(CARDNEWS_DOCTOR_SYSTEM, build_card_doctor_prompt(package, card_count, image_ratio), model, min(1.0, temperature + 0.05))
                shorts_patch = call_llm(SHORTS_DOCTOR_SYSTEM, build_shorts_doctor_prompt(package, image_ratio), model, min(1.0, temperature + 0.05))
                package = merge_doctors(package, card_patch, shorts_patch)
            progress.progress(75)
            if use_quality_gate:
                status.info("4/4 품질 심사 중")
                gate = call_llm(QUALITY_GATE_SYSTEM, build_quality_prompt(package), model, 0.2)
                package["quality_gate"] = gate
            package["generated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            package["reference_preview"] = reference_text[:300]
            package.setdefault("auto_brief", {}).setdefault("image_ratio", image_ratio)
            st.session_state.package = package
            save_history_item(package)
            st.session_state.history_meta = load_history_meta(HISTORY_LIMIT)
            progress.progress(100)
            status.success("생성 완료. Supabase에 저장했습니다.")

    with right:
        st.subheader("2. 결과")
        if not st.session_state.package:
            st.info("레퍼런스를 입력하고 생성하면 결과가 여기에 표시됩니다.")
        else:
            render_package(st.session_state.package)
