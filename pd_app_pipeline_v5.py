import csv
import io
import json
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

import streamlit as st
from openai import OpenAI
from supabase import Client, create_client

APP_TITLE = "AI PD Studio V5"
APP_SUBTITLE = "카드뉴스 컨펌 → 이미지/쇼츠/롱폼 확장 파이프라인"
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

CARD_SCHEMA = {
    "status": "draft",
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
        "borrowed_authority_use": "",
        "central_insight": "",
        "anti_cliche": "",
        "tension": "",
        "so_what": "",
        "proof_logic": "",
        "dangerous_reading": "",
        "sharp_reframe": "",
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
            "insight_device": "",
            "layout_type": "",
            "design_mood": "",
        }
    ],
    "quality_gate": {},
    "created_at": "",
}

EXPANSION_SCHEMA = {
    "image_production": {
        "global_style_guide": "",
        "negative_prompt": "text, watermark, logo, distorted hands, low quality",
        "cards": [
            {
                "page": 1,
                "visual_goal": "",
                "layout_direction": "",
                "korean_direction": "",
                "english_prompt": "",
                "negative_prompt": "",
            }
        ],
    },
    "shorts": {
        "title": "",
        "core_claim": "",
        "scenes": [
            {
                "time": "0-3초",
                "narration": "",
                "caption": "",
                "visual": "",
                "edit_point": "",
                "image_prompt": {"korean_direction": "", "english_prompt": "", "negative_prompt": "text, watermark, logo"},
                "video_prompt": {"korean_direction": "", "english_prompt": ""},
            }
        ],
    },
    "longform": {
        "title": "",
        "opening_hook": "",
        "script": "",
        "chapter_structure": [],
        "cta": "",
    },
    "titles": [],
    "thumbnail_copy": [],
    "hashtags": [],
    "production_checklist": [],
}

st.set_page_config(page_title=APP_TITLE, page_icon="🎬", layout="wide", initial_sidebar_state="expanded")
st.markdown(
    """
<style>
.main .block-container { padding-top: 2rem; max-width: 1380px; }
.hero-card { padding: 1.2rem 1.4rem; border: 1px solid rgba(120,120,120,.18); border-radius: 20px; background: linear-gradient(135deg, rgba(120,120,255,.12), rgba(255,255,255,.03)); }
.small-muted { color: #888; font-size: .92rem; }
.step-box { padding: 1rem 1.1rem; border: 1px solid rgba(120,120,120,.18); border-radius: 16px; margin-bottom: .8rem; }
</style>
""",
    unsafe_allow_html=True,
)

INSIGHT_SYSTEM = """
너는 카드뉴스 업로드 전 기획을 뜯어고치는 인사이트 에디터다.
목표는 레퍼런스를 그대로 요약하는 것이 아니라, 먼저 업로드 가능한 카드뉴스 원본을 만드는 것이다.

중요:
- 권위자/유명인이 계속 등장하는 구조 자체는 문제 삼지 마라.
- 문제는 텍스트가 권위자 말을 받아쓰기만 하고, 독자가 저장할 만한 해석을 못 만드는 것이다.
- 브랜드 관점은 별도 입력 없이 레퍼런스, 타깃, 톤에서 자동 추론한다.
- 지금 단계에서는 이미지 프롬프트, 쇼츠, 롱폼을 만들지 마라. 카드뉴스 내용만 만든다.

좋은 문장의 기준:
- 'A가 중요하다'가 아니라 'A라고 믿는 순간 B를 놓친다' 형태여야 한다.
- 정보 제목이 아니라 관점 문장이어야 한다.
- 문장 하나만 떼어도 저장하고 싶어야 한다.
- 권위자 인용 뒤에는 반드시 편집자의 해석이 더 강해야 한다.

나쁜 문장 예시:
- 노력만으로는 부족하다, 현실 판단이 답이다
- 현실은 다르다
- 성공하려면 냉철해야 한다
- 극한의 노력이 결과 차이를 만든다
- 댓글로 의견을 나눠 주세요

반드시 JSON만 출력한다.
"""

CARD_DRAFT_SYSTEM = """
너는 카드뉴스 원고를 만드는 콘텐츠 PD다.
입력된 insight_board를 기반으로 카드뉴스 원고만 만든다.

강제 규칙:
- 이미지 프롬프트, 영상 프롬프트, 쇼츠 대본, 롱폼 대본은 만들지 마라.
- 카드뉴스 텍스트가 컨펌되기 전까지 제작 확장물을 만들면 안 된다.
- 각 장은 role이 달라야 한다: hook, cliche_break, contradiction, proof, reframe, comparison, checklist, final_question.
- headline은 제목이 아니라 주장이어야 한다.
- body는 설명문이 아니라 짧은 논리여야 한다.
- save_line은 독자가 캡처하고 싶은 문장이어야 한다.
- 마지막 장은 댓글 구걸 금지. 자기검증 질문으로 끝내라.

반드시 아래 JSON만 출력한다:
{
  "status":"draft",
  "auto_brief":{},
  "insight_board":{},
  "card_news":[],
  "production_note":"카드뉴스 내용 컨펌 후 이미지/쇼츠/롱폼 확장 가능"
}
"""

AUDIT_SYSTEM = """
너는 업로드 전 하드 게이트 심사위원이다.
절대 후하게 평가하지 마라. 카드뉴스 원고 자체가 약하면 '업로드 가능' 판정을 주면 안 된다.

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
4. insight_score가 85 미만이면 final_card_package를 직접 재작성한다.
5. generic_score가 30 이상이면 verdict는 절대 '업로드 가능'이 될 수 없다.

평가 기준:
- insight_score: 뻔한 말을 비틀어 새로운 판단 기준을 제시하는가
- copy_score: 문장 자체가 저장 가치가 있는가
- logic_score: 메시지가 충돌하지 않는가
- authority_score: 권위자를 써도 받아쓰기로 끝나지 않는가
- risk_score: 과로 미화/성공팔이로 읽히지 않는가
- upload_ready_score: 카드뉴스 텍스트만 놓고 바로 업로드 가능한가

반드시 JSON만 출력한다.
"""

EXPAND_SYSTEM = """
너는 컨펌된 카드뉴스 원고를 제작물로 확장하는 콘텐츠 프로듀서다.
이미 승인된 card_news의 메시지를 절대 약화시키지 말고, 선택된 제작물만 만든다.

확장 규칙:
- 카드뉴스 이미지 프롬프트는 카드별 headline/body/save_line을 시각화한다.
- 쇼츠는 카드뉴스 순서를 그대로 읽지 말고 1분 리텐션 구조로 재편집한다.
- 롱폼은 카드뉴스의 핵심 인사이트를 더 깊은 해설 구조로 확장한다.
- 영상 프롬프트는 영어이며 반드시 카메라 움직임으로 시작한다.
- 이미지 프롬프트는 영어이며 텍스트 삽입을 금지한다.
- 카드뉴스 원고가 기준 원본이다. 새로운 핵심 주장을 만들어 흐트러뜨리지 마라.

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


def all_card_text(package: Dict[str, Any]) -> str:
    chunks: List[str] = []
    for card in package.get("card_news", []) or []:
        chunks.extend([str(card.get("headline", "")), str(card.get("body", "")), str(card.get("save_line", ""))])
    return "\n".join(chunks)


def deterministic_quality_gate(package: Dict[str, Any]) -> Dict[str, Any]:
    text = all_card_text(package)
    weak_hits = []
    for phrase in GENERIC_PATTERNS:
        if phrase in text:
            weak_hits.append({"line": phrase, "reason": "금지된 뻔한 자기계발식 문장입니다.", "fix_direction": "판단 기준, 반전, 조건문이 들어간 문장으로 바꾸세요."})
    for pattern in WEAK_HEADLINE_PATTERNS:
        if re.search(pattern, text):
            weak_hits.append({"line": pattern, "reason": "정보 요약형 헤드라인이라 손가락을 멈추게 하지 못합니다.", "fix_direction": "착각을 깨는 주장형 헤드라인으로 바꾸세요."})
    generic_score = min(100, len(weak_hits) * 18)
    return {"generic_score": generic_score, "weak_hits": weak_hits}


def enforce_gate(card_package: Dict[str, Any], audit: Dict[str, Any]) -> Dict[str, Any]:
    final_package = audit.get("final_card_package") if isinstance(audit.get("final_card_package"), dict) and audit.get("final_card_package") else card_package
    local = deterministic_quality_gate(final_package)
    quality_gate = {k: v for k, v in audit.items() if k != "final_card_package"}
    quality_gate.setdefault("scores", {})
    quality_gate["scores"]["local_generic_score"] = local["generic_score"]
    quality_gate["local_weak_hits"] = local["weak_hits"]
    if local["generic_score"] > 0:
        quality_gate["verdict"] = "수정 필요"
        quality_gate.setdefault("critical_issues", [])
        quality_gate["critical_issues"].append("로컬 하드게이트: 뻔한 카피/약한 헤드라인 패턴이 감지되어 업로드 가능 판정을 차단했습니다.")
    final_package["quality_gate"] = quality_gate
    final_package.setdefault("status", "draft")
    return final_package


def build_insight_prompt(reference_text: str, output_language: str, image_ratio: str, card_count: int, platform_hint: str, tone_hint: str, override_topic: str) -> str:
    return f"""
레퍼런스를 분석해서 insight_board를 만들어라.

설정:
- 출력 언어: {output_language}
- 이미지 비율: {image_ratio}
- 카드뉴스 장수: {card_count}
- 플랫폼 힌트: {platform_hint}
- 톤 힌트: {tone_hint}
- 주제 덮어쓰기: {override_topic}

출력 JSON 형식:
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


def build_card_prompt(insight_data: Dict[str, Any], card_count: int, image_ratio: str) -> str:
    return f"""
아래 insight_board를 기반으로 카드뉴스 원고만 만들어라.
카드뉴스는 {card_count}장, 이미지 비율은 {image_ratio}.

출력 스키마 예시:
{json.dumps(CARD_SCHEMA, ensure_ascii=False, indent=2)}

insight_board:
{json.dumps(insight_data, ensure_ascii=False, indent=2)}
"""


def build_audit_prompt(card_package: Dict[str, Any]) -> str:
    return f"""
아래 카드뉴스 원고를 심사하고, 약하면 final_card_package로 카드뉴스 원고만 직접 다시 써라.
이미지/쇼츠/롱폼은 절대 만들지 마라.

카드뉴스 원고:
{json.dumps(card_package, ensure_ascii=False, indent=2)}
"""


def build_expand_prompt(approved_package: Dict[str, Any], options: Dict[str, Any]) -> str:
    return f"""
아래 컨펌된 카드뉴스 원고를 기준으로 선택된 제작물만 확장하라.

확장 옵션:
{json.dumps(options, ensure_ascii=False, indent=2)}

반환 스키마 예시:
{json.dumps(EXPANSION_SCHEMA, ensure_ascii=False, indent=2)}

컨펌된 카드뉴스:
{json.dumps(approved_package, ensure_ascii=False, indent=2)}
"""


def save_history_item(package: Dict[str, Any]) -> None:
    supabase = get_supabase_client()
    if not supabase:
        st.warning("Supabase가 연결되지 않아 저장하지 못했습니다.")
        return
    brief = package.get("auto_brief", {}) or {}
    gate = package.get("quality_gate", {}) or {}
    status = package.get("status", "draft")
    verdict = gate.get("verdict", "") if isinstance(gate, dict) else ""
    payload = {
        "topic": brief.get("topic") or "무제",
        "verdict": f"{status} | {verdict}".strip(" |"),
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


def stringify(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def package_to_rows(package: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    brief = package.get("auto_brief", {}) or {}
    for card in package.get("card_news", []) or []:
        rows.append({
            "type": "card_news",
            "index": card.get("page", ""),
            "headline": card.get("headline", ""),
            "body": card.get("body", ""),
            "save_line": card.get("save_line", ""),
            "role": card.get("role", ""),
            "layout_or_visual": card.get("layout_type", ""),
            "prompt": "",
            "image_ratio": brief.get("image_ratio", ""),
        })
    expansion = package.get("expansion", {}) or {}
    for item in (expansion.get("image_production", {}) or {}).get("cards", []) or []:
        rows.append({
            "type": "image_prompt",
            "index": item.get("page", ""),
            "headline": "",
            "body": item.get("korean_direction", ""),
            "save_line": "",
            "role": "",
            "layout_or_visual": item.get("layout_direction", ""),
            "prompt": item.get("english_prompt", ""),
            "image_ratio": brief.get("image_ratio", ""),
        })
    shorts = expansion.get("shorts", {}) or {}
    for idx, scene in enumerate(shorts.get("scenes", []) or [], 1):
        rows.append({
            "type": "shorts_scene",
            "index": idx,
            "headline": scene.get("caption", ""),
            "body": scene.get("narration", ""),
            "save_line": shorts.get("core_claim", ""),
            "role": scene.get("time", ""),
            "layout_or_visual": scene.get("visual", ""),
            "prompt": stringify(scene.get("video_prompt", {})),
            "image_ratio": brief.get("image_ratio", ""),
        })
    longform = expansion.get("longform", {}) or {}
    if longform:
        rows.append({
            "type": "longform_script",
            "index": 1,
            "headline": longform.get("title", ""),
            "body": longform.get("script", ""),
            "save_line": longform.get("opening_hook", ""),
            "role": "longform",
            "layout_or_visual": "",
            "prompt": "",
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


def render_card_package(package: Dict[str, Any]) -> None:
    gate = package.get("quality_gate", {}) or {}
    scores = gate.get("scores", {}) or {}
    verdict = gate.get("verdict", "")
    status = package.get("status", "draft")

    st.markdown(f"### 상태: `{status}`")
    if verdict:
        cols = st.columns(4)
        for idx, key in enumerate(["insight_score", "copy_score", "local_generic_score", "upload_ready_score"]):
            with cols[idx]:
                st.metric(key, scores.get(key, "-"))
        st.markdown(f"**업로드 판정:** {verdict}")

    tabs = st.tabs(["카드뉴스 원고", "인사이트 보드", "하드게이트", "확장 결과", "CSV/JSON"])
    with tabs[0]:
        for i, card in enumerate(package.get("card_news", []) or [], 1):
            with st.expander(f"{card.get('page', i)}장 · {card.get('role','')} · {card.get('headline','')}", expanded=i <= 2):
                st.markdown(f"**헤드라인**\n\n{card.get('headline','')}")
                st.markdown(f"**본문**\n\n{card.get('body','')}")
                st.markdown(f"**저장 문장**\n\n{card.get('save_line','')}")
                st.markdown(f"**인사이트 장치**\n\n{card.get('insight_device','')}")
                st.markdown(f"**레이아웃 힌트**\n\n{card.get('layout_type','')}")
    with tabs[1]:
        st.json(package.get("insight_board", {}))
    with tabs[2]:
        st.json(gate)
    with tabs[3]:
        expansion = package.get("expansion")
        if not expansion:
            st.info("카드뉴스 컨펌 후 제작 확장을 생성하면 여기에 표시됩니다.")
        else:
            render_expansion(expansion)
    with tabs[4]:
        csv_text = to_csv(package_to_rows(package))
        st.download_button("CSV 다운로드", csv_text, file_name="ai_pd_studio_v5_content.csv", mime="text/csv", use_container_width=True)
        st.download_button("JSON 다운로드", stringify(package), file_name="ai_pd_studio_v5_output.json", mime="application/json", use_container_width=True)


def render_expansion(expansion: Dict[str, Any]) -> None:
    exp_tabs = st.tabs(["이미지화 기준", "쇼츠", "롱폼", "제목/썸네일"])
    with exp_tabs[0]:
        image_prod = expansion.get("image_production", {}) or {}
        st.markdown(f"**Global Style Guide**\n\n{image_prod.get('global_style_guide','')}")
        st.markdown(f"**Negative Prompt**\n\n{image_prod.get('negative_prompt','')}")
        for item in image_prod.get("cards", []) or []:
            with st.expander(f"카드 {item.get('page','')} 이미지 프롬프트", expanded=False):
                st.markdown(f"**시각 목표**\n\n{item.get('visual_goal','')}")
                st.markdown(f"**레이아웃 방향**\n\n{item.get('layout_direction','')}")
                st.text_area("English Prompt", item.get("english_prompt", ""), height=130, key=f"img_prompt_{item.get('page','')}_{id(item)}")
    with exp_tabs[1]:
        shorts = expansion.get("shorts", {}) or {}
        st.markdown(f"### {shorts.get('title','')}")
        st.markdown(f"**핵심 주장**: {shorts.get('core_claim','')}")
        for i, scene in enumerate(shorts.get("scenes", []) or [], 1):
            with st.expander(f"컷 {i} · {scene.get('time','')}", expanded=i <= 2):
                st.markdown(f"**내레이션**\n\n{scene.get('narration','')}")
                st.markdown(f"**자막**\n\n{scene.get('caption','')}")
                st.markdown(f"**화면**\n\n{scene.get('visual','')}")
                st.markdown(f"**편집 포인트**\n\n{scene.get('edit_point','')}")
                st.text_area("이미지 프롬프트", stringify(scene.get("image_prompt", {})), height=120, key=f"scene_img_{i}_{id(scene)}")
                st.text_area("영상 프롬프트", stringify(scene.get("video_prompt", {})), height=120, key=f"scene_vid_{i}_{id(scene)}")
    with exp_tabs[2]:
        longform = expansion.get("longform", {}) or {}
        if not longform:
            st.info("롱폼 확장을 선택하지 않았습니다.")
        else:
            st.markdown(f"### {longform.get('title','')}")
            st.markdown(f"**오프닝 훅**\n\n{longform.get('opening_hook','')}")
            st.text_area("롱폼 대본", longform.get("script", ""), height=420)
    with exp_tabs[3]:
        st.write("제목", expansion.get("titles", []))
        st.write("썸네일", expansion.get("thumbnail_copy", []))
        st.write("해시태그", " ".join(expansion.get("hashtags", [])))
        st.write("제작 체크리스트", expansion.get("production_checklist", []))


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
                st.session_state.current_package = package
                if package.get("status") in ["approved", "expanded"]:
                    st.session_state.approved_package = package
                st.success("상세를 불러왔습니다. 카드뉴스 기획/제작 확장 메뉴에서 확인하세요.")
    with col2:
        if st.button("DB에서 삭제", use_container_width=True):
            delete_history_item(row.get("id"))
            st.session_state.history_meta = load_history_meta(limit)
            st.rerun()


if "current_package" not in st.session_state:
    st.session_state.current_package = None
if "approved_package" not in st.session_state:
    st.session_state.approved_package = None
if "menu" not in st.session_state:
    st.session_state.menu = "카드뉴스 기획"

st.markdown(
    f"""<div class='hero-card'><h1>{APP_TITLE}</h1><p>{APP_SUBTITLE}</p><p class='small-muted'>먼저 카드뉴스 원고를 컨펌하고, 그다음 이미지/쇼츠/롱폼으로 확장합니다.</p></div>""",
    unsafe_allow_html=True,
)

st.sidebar.header("메인 메뉴")
menu = st.sidebar.radio("이동", ["카드뉴스 기획", "제작 확장", "히스토리"], key="menu")
st.sidebar.header("⚙️ 공통 설정")
model = st.sidebar.selectbox("OpenAI 모델", ["gpt-4.1", "gpt-4.1-mini", "gpt-4o", "gpt-4o-mini"], index=0)
temperature = st.sidebar.slider("창의성", 0.1, 1.2, 0.75, 0.05)
output_language = st.sidebar.selectbox("출력 언어", ["한국어", "영어", "한국어+영어"], index=0)
image_ratio = st.sidebar.selectbox("이미지 비율", ["1:1 square card news", "9:16 vertical shorts", "4:5 Instagram feed", "16:9 YouTube wide"], index=0)
card_count = st.sidebar.slider("카드뉴스 장수", 5, 12, 8)
with st.sidebar.expander("Secrets 확인"):
    st.code('OPENAI_API_KEY = "sk-..."\nSUPABASE_URL = "https://...supabase.co"\nSUPABASE_SERVICE_ROLE_KEY = "sb_secret_..."', language="toml")
    st.caption(f"현재 저장 방식: {storage_mode()}")

st.divider()

if menu == "카드뉴스 기획":
    left, right = st.columns([0.84, 1.16], gap="large")
    with left:
        st.subheader("Step 1. 카드뉴스 원고 생성")
        reference_text = st.text_area("레퍼런스 텍스트 / CSV 내용 / 대본 / 카드뉴스 문구", height=360, placeholder="여기에 레퍼런스를 붙여넣으세요.")
        with st.expander("기획 설정"):
            override_topic = st.text_input("주제 덮어쓰기", placeholder="비워두면 자동 추론")
            platform_hint = st.selectbox("플랫폼 힌트", ["AI가 판단", "Instagram 카드뉴스", "YouTube Shorts", "Instagram Reels", "TikTok", "혼합"], index=0)
            tone_hint = st.selectbox("톤 힌트", ["커뮤니티 인기글형", "전문가 정보형", "자극적 후킹형", "다큐멘터리형", "광고 카피형"], index=0)
        run_button = st.button("카드뉴스 원고 생성", type="primary", use_container_width=True)

        if st.session_state.current_package:
            st.divider()
            st.subheader("Step 2. 원고 컨펌")
            current_verdict = (st.session_state.current_package.get("quality_gate", {}) or {}).get("verdict", "")
            st.caption(f"현재 판정: {current_verdict or '판정 없음'}")
            if st.button("이 카드뉴스 내용 컨펌", use_container_width=True):
                approved = dict(st.session_state.current_package)
                approved["status"] = "approved"
                approved["approved_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                st.session_state.approved_package = approved
                st.session_state.current_package = approved
                save_history_item(approved)
                st.success("컨펌 완료. 이제 제작 확장 메뉴에서 이미지/쇼츠/롱폼을 만들 수 있습니다.")

    if run_button:
        if not reference_text.strip():
            st.warning("레퍼런스를 먼저 입력해주세요.")
        else:
            progress = st.progress(0)
            status = st.empty()
            status.info("1/3 인사이트 보드 생성 중")
            insight_data = call_llm(INSIGHT_SYSTEM, build_insight_prompt(reference_text, output_language, image_ratio, card_count, platform_hint, tone_hint, override_topic), model, 0.25)
            progress.progress(30)

            status.info("2/3 카드뉴스 원고 생성 중")
            card_package = call_llm(CARD_DRAFT_SYSTEM, build_card_prompt(insight_data, card_count, image_ratio), model, temperature)
            card_package["auto_brief"] = insight_data.get("auto_brief", card_package.get("auto_brief", {}))
            card_package["insight_board"] = insight_data.get("insight_board", card_package.get("insight_board", {}))
            card_package["status"] = "draft"
            progress.progress(65)

            status.info("3/3 하드게이트 심사 중")
            audit = call_llm(AUDIT_SYSTEM, build_audit_prompt(card_package), model, 0.2)
            card_package = enforce_gate(card_package, audit)
            card_package["created_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            card_package["reference_preview"] = reference_text[:300]
            card_package.setdefault("auto_brief", {}).setdefault("image_ratio", image_ratio)
            st.session_state.current_package = card_package
            save_history_item(card_package)
            st.session_state.history_meta = load_history_meta(HISTORY_LIMIT)
            progress.progress(100)
            status.success("카드뉴스 원고 생성 완료. 내용 컨펌 후 제작 확장으로 넘어가세요.")

    with right:
        st.subheader("결과")
        if not st.session_state.current_package:
            st.info("카드뉴스 원고를 생성하면 여기에 표시됩니다.")
        else:
            render_card_package(st.session_state.current_package)

elif menu == "제작 확장":
    st.subheader("Step 3. 컨펌된 카드뉴스를 제작물로 확장")
    approved = st.session_state.approved_package
    if not approved:
        st.warning("먼저 카드뉴스 기획 메뉴에서 카드뉴스 내용을 컨펌해주세요.")
    else:
        col_a, col_b = st.columns([0.8, 1.2], gap="large")
        with col_a:
            st.markdown("### 확장 옵션")
            make_images = st.checkbox("카드뉴스 이미지화 기준/프롬프트 생성", value=True)
            make_shorts = st.checkbox("1분 쇼츠 대본 + 영상화 프롬프트 생성", value=True)
            make_longform = st.checkbox("롱폼용 대본 생성", value=False)
            make_titles = st.checkbox("제목/썸네일/해시태그 생성", value=True)
            visual_style = st.text_input("이미지 스타일 기준", value="clean editorial card news, high readability, controlled contrast")
            video_style = st.text_input("쇼츠 영상 스타일 기준", value="fast-paced editorial short-form, clear visual beats")
            longform_minutes = st.slider("롱폼 분량", 3, 20, 8)
            expand_button = st.button("선택한 제작물 생성", type="primary", use_container_width=True)
        with col_b:
            st.markdown("### 컨펌된 카드뉴스 원고")
            render_card_package(approved)

        if expand_button:
            options = {
                "make_images": make_images,
                "make_shorts": make_shorts,
                "make_longform": make_longform,
                "make_titles": make_titles,
                "visual_style": visual_style,
                "video_style": video_style,
                "longform_minutes": longform_minutes,
                "image_ratio": image_ratio,
            }
            with st.spinner("컨펌된 카드뉴스를 기준으로 제작물을 확장 중입니다."):
                expansion = call_llm(EXPAND_SYSTEM, build_expand_prompt(approved, options), model, min(1.0, temperature + 0.05))
                expanded = dict(approved)
                expanded["status"] = "expanded"
                expanded["expanded_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                expanded["expansion_options"] = options
                expanded["expansion"] = expansion
                st.session_state.approved_package = expanded
                st.session_state.current_package = expanded
                save_history_item(expanded)
                st.session_state.history_meta = load_history_meta(HISTORY_LIMIT)
                st.success("제작 확장 완료. 결과 탭에서 이미지/쇼츠/롱폼을 확인하세요.")
                render_card_package(expanded)

else:
    render_history()
