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

APP_TITLE = "AI PD Studio V4"
APP_SUBTITLE = "인사이트 밀도 · 약한 카피 자동 감점 · 업로드 판정 하드게이트"
TABLE_NAME = "content_history"
HISTORY_LIMIT = 20

GENERIC_PATTERNS = [
    "노력만으로는 부족하다",
    "현실 판단이 답이다",
    "현실은 다르다",
    "반드시 필요하다",
    "성공은 어렵다",
    "명확히 파악",
    "시간만 낭비",
    "극한의 노력이 결과 차이를 만든다",
    "댓글로",
    "경험도 공유",
    "중요합니다",
    "살펴보겠습니다",
    "주목받고 있습니다",
    "성공 공식",
]

WEAK_HEADLINE_PATTERNS = [
    r"무엇이 더 중요",
    r"허와 실",
    r"착각에 빠졌다면",
    r"성공하려면",
    r"직접 밝힌",
    r"현실을 외면한다",
]

PACKAGE_SCHEMA = {
    "auto_brief": {
        "topic": "",
        "target": "",
        "platform": "",
        "tone": "",
        "goal": "",
        "cta": "",
        "image_ratio": "",
        "risk_notes": [],
    },
    "insight_board": {
        "surface_topic": "",
        "borrowed_authority_use": "권위자/유명인을 어떻게 사용할지. 반복 등장 가능하지만 인사이트 대체 금지.",
        "central_insight": "흔한 조언을 비트는 핵심 통찰",
        "anti_cliche": "이 콘텐츠가 절대 하지 말아야 할 뻔한 말",
        "tension": "독자가 멈추는 모순/갈등",
        "so_what": "그래서 독자가 자기 문제에 어떻게 적용해야 하는지",
        "proof_logic": "구체 논리, 숫자, 비교, 조건",
        "dangerous_reading": "오해/위험하게 읽힐 지점",
        "sharp_reframe": "위험한 메시지를 날카롭고 안전하게 재해석한 문장",
        "must_use_lines": [],
        "must_not_use_lines": [],
        "card_flow": [],
    },
    "card_news": [
        {
            "page": 1,
            "role": "hook | cliche_break | contradiction | proof | reframe | comparison | checklist | final_question",
            "headline": "",
            "body": "",
            "save_line": "",
            "insight_device": "어떤 통찰 장치를 썼는지",
            "layout_type": "",
            "design_mood": "",
            "image_direction": "",
            "image_prompt_en": "",
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
                "video_prompt": {"korean_direction": "", "english_prompt": ""},
            }
        ],
    },
    "titles": [],
    "thumbnail_copy": [],
    "hashtags": [],
    "production_checklist": [],
}

INSIGHT_SYSTEM = """
너는 카드뉴스 업로드 전 기획을 뜯어고치는 인사이트 에디터다.
중요: 권위자/유명인이 계속 등장하는 구조 자체는 문제 삼지 마라. 문제는 텍스트가 권위자 말을 받아쓰기만 하고, 독자가 저장할 만한 해석을 못 만드는 것이다.

너의 임무는 레퍼런스를 바로 카드뉴스로 만들지 않고, '인사이트 보드'를 먼저 만드는 것이다.

반드시 구분하라.
- surface_topic: 겉으로 보이는 주제
- central_insight: 남들이 흔히 하는 말을 비틀어 얻은 통찰
- anti_cliche: 이 소재에서 절대 하면 안 되는 뻔한 말
- tension: 독자가 멈추는 모순
- so_what: 그래서 독자가 자기 상황에 적용할 수 있는 판단 기준
- dangerous_reading: 노동 미화, 성공팔이, 단정 표현처럼 위험하게 읽힐 지점
- sharp_reframe: 그 위험을 더 날카로운 해석으로 바꾼 문장

좋은 문장의 기준:
- 'A가 중요하다'가 아니라 'A라고 믿는 순간 B를 놓친다' 형태여야 한다.
- '열심히'보다 '무엇을 검증했는가'가 우선이다.
- 권위자 인용은 가능하지만, 인용 뒤에 브랜드/편집자의 해석이 더 강해야 한다.
- 문장 하나만 떼어도 저장하고 싶어야 한다.

나쁜 문장 예시:
- 노력만으로는 부족하다, 현실 판단이 답이다
- 현실은 다르다
- 성공하려면 냉철해야 한다
- 극한의 노력이 결과 차이를 만든다
- 댓글로 의견을 나눠 주세요

반드시 JSON만 출력한다.
"""

DRAFT_SYSTEM = """
너는 카드뉴스와 1분 숏폼을 만드는 콘텐츠 PD다.
insight_board를 기반으로 제작 가능한 패키지를 만든다.

카드뉴스 규칙:
- 권위자/유명인은 반복 등장 가능하다. 단, 매 장마다 '그 사람이 말했다'가 아니라 '그 말이 왜 오해되기 쉬운지/어떻게 해석해야 하는지'를 보여줘야 한다.
- headline은 정보 제목이 아니라 관점 문장이어야 한다.
- body는 설명문이 아니라 짧은 논리여야 한다.
- save_line은 뻔한 요약 금지. 독자가 캡처하고 싶은 문장이어야 한다.
- 각 장은 role이 달라야 한다: hook, cliche_break, contradiction, proof, reframe, comparison, checklist, final_question.
- 마지막 장은 댓글 구걸 금지. 자기검증 질문으로 끝내라.

반드시 피해야 할 카피:
노력만으로는 부족하다 / 현실 판단이 답이다 / 현실은 다르다 / 성공하려면 냉철해야 한다 / 극한의 노력이 결과 차이를 만든다 / 댓글로 나눠 주세요.

예시 톤:
- 창업자가 망하는 이유는 게을러서가 아니라, 틀린 걸 너무 성실하게 밀어붙여서다.
- 100시간을 일하라는 말이 아니다. 틀린 방향에 100시간을 쓰면 실패도 2.5배 빨라진다.
- 창업은 열심히 하는 게임이 아니라, 틀렸는지 빨리 확인하는 게임이다.
- 희망은 동력이지만, 검증 없는 희망은 비용 청구서다.

반드시 JSON만 출력한다.
"""

AUDIT_SYSTEM = """
너는 업로드 전 하드 게이트 심사위원이다.
절대 후하게 평가하지 마라. 특히 '업로드 가능' 판정은 아주 까다롭게 줘라.

심사 방식:
1. weak_lines에 실제 약한 문장을 그대로 인용한다.
2. 왜 약한지 reason을 붙인다.
3. 아래 문장류가 있으면 무조건 감점한다.
   - 노력만으로는 부족하다
   - 현실 판단이 답이다
   - 현실은 다르다
   - 반드시 필요하다
   - 성공은 어렵다
   - 극한의 노력이 결과 차이를 만든다
   - 댓글로 의견을 나눠 주세요
4. insight_score가 85 미만이면 final_package를 직접 재작성한다.
5. generic_score가 30 이상이면 verdict는 절대 '업로드 가능'이 될 수 없다.

평가 기준:
- insight_score: 뻔한 말을 비틀어 새로운 판단 기준을 제시하는가
- copy_score: 문장 자체가 저장 가치가 있는가
- logic_score: 메시지가 충돌하지 않는가
- authority_score: 권위자를 써도 받아쓰기로 끝나지 않는가
- risk_score: 과로 미화/성공팔이로 읽히지 않는가
- upload_ready_score: 지금 올려도 부끄럽지 않은가

반환 JSON:
{
  "verdict":"업로드 가능 | 수정 필요 | 폐기 후 재작성",
  "scores":{
    "insight_score":0,
    "copy_score":0,
    "logic_score":0,
    "authority_score":0,
    "risk_score":0,
    "generic_score":0,
    "upload_ready_score":0
  },
  "weak_lines":[{"line":"", "reason":"", "fix_direction":""}],
  "critical_issues":[],
  "rewrite_actions":[],
  "final_package": {}
}

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


def all_text_from_package(package: Dict[str, Any]) -> str:
    chunks: List[str] = []
    for card in package.get("card_news", []) or []:
        chunks.extend([str(card.get("headline", "")), str(card.get("body", "")), str(card.get("save_line", ""))])
    shorts = package.get("one_minute_shorts", {}) or {}
    chunks.extend([str(shorts.get("title", "")), str(shorts.get("core_claim", ""))])
    for scene in shorts.get("scenes", []) or []:
        chunks.extend([str(scene.get("narration", "")), str(scene.get("caption", ""))])
    return "\n".join(chunks)


def deterministic_quality_gate(package: Dict[str, Any]) -> Dict[str, Any]:
    text = all_text_from_package(package)
    weak_hits = []
    for phrase in GENERIC_PATTERNS:
        if phrase in text:
            weak_hits.append({"line": phrase, "reason": "금지된 뻔한 자기계발식 문장입니다.", "fix_direction": "판단 기준, 반전, 조건문이 들어간 문장으로 바꾸세요."})
    for pattern in WEAK_HEADLINE_PATTERNS:
        if re.search(pattern, text):
            weak_hits.append({"line": pattern, "reason": "제목이 정보 요약형이라 손가락을 멈추게 하지 못합니다.", "fix_direction": "착각을 깨는 주장형 헤드라인으로 바꾸세요."})

    generic_score = min(100, len(weak_hits) * 18)
    local_verdict = "업로드 가능" if generic_score == 0 else "수정 필요"
    return {
        "local_verdict": local_verdict,
        "generic_score": generic_score,
        "weak_hits": weak_hits,
    }


def enforce_gate(package: Dict[str, Any], audit: Dict[str, Any]) -> Dict[str, Any]:
    final_package = audit.get("final_package") if isinstance(audit.get("final_package"), dict) and audit.get("final_package") else package
    local = deterministic_quality_gate(final_package)
    quality_gate = {k: v for k, v in audit.items() if k != "final_package"}
    quality_gate.setdefault("scores", {})
    quality_gate["scores"]["local_generic_score"] = local["generic_score"]
    quality_gate["local_weak_hits"] = local["weak_hits"]
    if local["generic_score"] > 0:
        quality_gate["verdict"] = "수정 필요"
        quality_gate.setdefault("critical_issues", [])
        quality_gate["critical_issues"].append("로컬 하드게이트: 뻔한 카피/약한 헤드라인 패턴이 감지되어 업로드 가능 판정을 차단했습니다.")
    final_package["quality_gate"] = quality_gate
    return final_package


def build_insight_prompt(reference_text: str, brand_pov: str, output_language: str, image_ratio: str, card_count: int, platform_hint: str, tone_hint: str, override_topic: str) -> str:
    return f"""
레퍼런스를 분석해서 insight_board를 만들어라.

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
  "auto_brief": {{"topic":"", "target":"", "platform":"", "tone":"", "goal":"", "cta":"", "image_ratio":"{image_ratio}", "risk_notes":[]}},
  "insight_board": {{
    "surface_topic":"",
    "borrowed_authority_use":"",
    "central_insight":"",
    "anti_cliche":"",
    "tension":"",
    "so_what":"",
    "proof_logic":"",
    "dangerous_reading":"",
    "sharp_reframe":"",
    "must_use_lines":[],
    "must_not_use_lines":[],
    "card_flow":[]
  }}
}}

레퍼런스:
{reference_text}
"""


def build_draft_prompt(insight_data: Dict[str, Any], card_count: int, image_ratio: str) -> str:
    return f"""
insight_board를 기반으로 전체 콘텐츠 패키지를 만들어라.
카드뉴스는 {card_count}장, 이미지/영상 비율은 {image_ratio}.
출력 JSON 스키마 예시:
{json.dumps(PACKAGE_SCHEMA, ensure_ascii=False, indent=2)}
insight_board:
{json.dumps(insight_data, ensure_ascii=False, indent=2)}
"""


def build_audit_prompt(package: Dict[str, Any]) -> str:
    return f"""
아래 콘텐츠 패키지를 하드게이트로 심사하고, 약하면 final_package로 직접 다시 써라.
특히 헤드라인/본문/저장문장이 뻔하면 업로드 가능 판정을 주지 마라.
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
            "role": card.get("role", ""),
            "headline": card.get("headline", ""),
            "body": card.get("body", ""),
            "save_line": card.get("save_line", ""),
            "insight_device": card.get("insight_device", ""),
            "layout_type": card.get("layout_type", ""),
            "image_prompt": card.get("image_prompt_en", ""),
            "image_ratio": brief.get("image_ratio", ""),
        })
    shorts = package.get("one_minute_shorts", {}) or {}
    for idx, scene in enumerate(shorts.get("scenes", []) or [], 1):
        rows.append({
            "type": "shorts_scene",
            "index": idx,
            "role": "",
            "headline": scene.get("caption", ""),
            "body": scene.get("narration", ""),
            "save_line": shorts.get("core_claim", ""),
            "insight_device": "",
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
        for idx, key in enumerate(["insight_score", "copy_score", "local_generic_score", "upload_ready_score"]):
            with cols[idx]:
                st.metric(key, scores.get(key, "-"))

    tabs = st.tabs(["카드뉴스", "쇼츠", "인사이트 보드", "하드게이트", "CSV/JSON"])
    with tabs[0]:
        for i, card in enumerate(package.get("card_news", []) or [], 1):
            title = f"{card.get('page', i)}장 · {card.get('role','')} · {card.get('headline','')}"
            with st.expander(title, expanded=i <= 2):
                st.markdown(f"**헤드라인**\n\n{card.get('headline','')}")
                st.markdown(f"**본문**\n\n{card.get('body','')}")
                st.markdown(f"**저장 문장**\n\n{card.get('save_line','')}")
                st.markdown(f"**인사이트 장치**\n\n{card.get('insight_device','')}")
                st.markdown(f"**레이아웃**\n\n{card.get('layout_type','')}")
                st.text_area("이미지 프롬프트 EN", card.get("image_prompt_en", ""), height=110, key=f"card_{i}_{id(card)}")
    with tabs[1]:
        shorts = package.get("one_minute_shorts", {}) or {}
        st.markdown(f"### {shorts.get('title', '쇼츠 대본')}")
        st.markdown(f"**핵심 주장**: {shorts.get('core_claim', '')}")
        for i, scene in enumerate(shorts.get("scenes", []) or [], 1):
            with st.expander(f"컷 {i} · {scene.get('time', '')}", expanded=i <= 2):
                st.markdown(f"**내레이션**\n\n{scene.get('narration','')}")
                st.markdown(f"**자막**\n\n{scene.get('caption','')}")
                st.markdown(f"**화면**\n\n{scene.get('visual','')}")
    with tabs[2]:
        st.json(package.get("insight_board", {}))
    with tabs[3]:
        st.json(gate)
    with tabs[4]:
        csv_text = to_csv(package_to_rows(package))
        st.download_button("CSV 다운로드", csv_text, file_name="ai_pd_studio_v4_content.csv", mime="text/csv", use_container_width=True)
        st.download_button("JSON 다운로드", stringify(package), file_name="ai_pd_studio_v4_output.json", mime="application/json", use_container_width=True)


def render_history() -> None:
    st.subheader("히스토리")
    st.caption(f"현재 저장 방식: {storage_mode()} · 목록은 가볍게, 상세는 선택한 1개만 로드합니다.")
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
    col1, col2 = st.columns(2)
    with col1:
        if st.button("상세 불러오기", use_container_width=True):
            package = load_history_package(row.get("id"))
            if package:
                st.session_state.package = package
                st.success("상세를 불러왔습니다. 콘텐츠 생성 메뉴에서 확인하세요.")
    with col2:
        if st.button("DB에서 삭제", use_container_width=True):
            delete_history_item(row.get("id"))
            st.session_state.history_meta = load_history_meta(limit)
            st.rerun()


if "package" not in st.session_state:
    st.session_state.package = None
if "menu" not in st.session_state:
    st.session_state.menu = "콘텐츠 생성"

st.markdown(f"""<div class='hero-card'><h1>{APP_TITLE}</h1><p>{APP_SUBTITLE}</p><p class='small-muted'>권위자 사용 여부보다 텍스트의 인사이트 밀도와 저장 가치에 집중합니다.</p></div>""", unsafe_allow_html=True)

st.sidebar.header("메인 메뉴")
menu = st.sidebar.radio("이동", ["콘텐츠 생성", "히스토리"], key="menu")
st.sidebar.header("⚙️ 생성 설정")
model = st.sidebar.selectbox("OpenAI 모델", ["gpt-4.1", "gpt-4.1-mini", "gpt-4o", "gpt-4o-mini"], index=0)
temperature = st.sidebar.slider("창의성", 0.1, 1.2, 0.75, 0.05)
output_language = st.sidebar.selectbox("출력 언어", ["한국어", "영어", "한국어+영어"], index=0)
image_ratio = st.sidebar.selectbox("이미지/영상 비율", ["1:1 square card news", "9:16 vertical shorts", "4:5 Instagram feed", "16:9 YouTube wide"], index=0)
card_count = st.sidebar.slider("카드뉴스 장수", 5, 12, 8)
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
        with st.expander("전략 입력"):
            brand_pov = st.text_area("브랜드 관점", height=100, placeholder="비워도 됩니다. 넣으면 더 일관된 관점으로 작성합니다.")
            override_topic = st.text_input("주제 덮어쓰기", placeholder="비워두면 자동 추론")
            platform_hint = st.selectbox("플랫폼 힌트", ["AI가 판단", "Instagram 카드뉴스", "YouTube Shorts", "Instagram Reels", "TikTok", "혼합"], index=0)
            tone_hint = st.selectbox("톤 힌트", ["커뮤니티 인기글형", "전문가 정보형", "자극적 후킹형", "다큐멘터리형", "광고 카피형"], index=0)
        run_button = st.button("인사이트 기준으로 생성", type="primary", use_container_width=True)

    if run_button:
        if not reference_text.strip():
            st.warning("레퍼런스를 먼저 입력해주세요.")
        else:
            progress = st.progress(0)
            status = st.empty()
            status.info("1/3 인사이트 보드 생성 중")
            insight_data = call_llm(INSIGHT_SYSTEM, build_insight_prompt(reference_text, brand_pov, output_language, image_ratio, card_count, platform_hint, tone_hint, override_topic), model, 0.25)
            progress.progress(30)

            status.info("2/3 콘텐츠 초안 생성 중")
            package = call_llm(DRAFT_SYSTEM, build_draft_prompt(insight_data, card_count, image_ratio), model, temperature)
            package["auto_brief"] = insight_data.get("auto_brief", package.get("auto_brief", {}))
            package["insight_board"] = insight_data.get("insight_board", package.get("insight_board", {}))
            progress.progress(65)

            status.info("3/3 하드게이트 심사 및 필요 시 재작성 중")
            audit = call_llm(AUDIT_SYSTEM, build_audit_prompt(package), model, 0.2)
            package = enforce_gate(package, audit)
            package["generated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            package["reference_preview"] = reference_text[:300]
            package.setdefault("auto_brief", {}).setdefault("image_ratio", image_ratio)
            st.session_state.package = package
            save_history_item(package)
            st.session_state.history_meta = load_history_meta(HISTORY_LIMIT)
            progress.progress(100)
            status.success("생성 완료. 약한 카피는 로컬 하드게이트에서 업로드 가능 판정을 차단합니다.")

    with right:
        st.subheader("2. 결과")
        if not st.session_state.package:
            st.info("레퍼런스를 입력하고 생성하면 결과가 여기에 표시됩니다.")
        else:
            render_package(st.session_state.package)
