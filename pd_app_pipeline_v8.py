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

APP_TITLE = "AI PD Studio V8"
APP_SUBTITLE = "정밀 점수 · 저장포인트 제거 · 카드뉴스 컨펌 후 제작 확장"
TABLE_NAME = "content_history"
HISTORY_LIMIT = 20

GENERIC_PATTERNS = [
    "노력만으로는 부족하다", "현실 판단이 답이다", "현실은 다르다", "반드시 필요하다", "성공은 어렵다",
    "명확히 파악", "시간만 낭비", "극한의 노력이 결과 차이를 만든다", "댓글로", "경험도 공유",
    "중요합니다", "살펴보겠습니다", "주목받고 있습니다", "성공 공식",
]
WEAK_HEADLINE_PATTERNS = [r"무엇이 더 중요", r"허와 실", r"착각에 빠졌다면", r"성공하려면", r"직접 밝힌", r"현실을 외면한다"]

CARD_SCHEMA = {
    "status": "draft",
    "auto_brief": {"topic": "", "target": "", "platform": "", "tone": "", "goal": "", "cta": "", "image_ratio": "", "risk_notes": []},
    "insight_board": {
        "surface_topic": "", "central_insight": "", "anti_cliche": "", "tension": "", "so_what": "",
        "proof_logic": "", "dangerous_reading": "", "sharp_reframe": "", "evidence_notes": [],
        "verification_todo": [], "must_use_lines": [], "must_not_use_lines": [], "card_flow": []
    },
    "card_news": [
        {"page": 1, "role": "hook", "headline": "", "body": "", "insight_device": "", "layout_hint": "", "design_mood": ""}
    ],
    "quality_gate": {},
    "improvement_report": {},
}

EXPANSION_SCHEMA = {
    "image_production": {"global_style_guide": "", "negative_prompt": "text, watermark, logo", "cards": []},
    "shorts": {"title": "", "core_claim": "", "scenes": []},
    "longform": {"title": "", "opening_hook": "", "script": "", "chapter_structure": [], "cta": ""},
    "titles": [], "thumbnail_copy": [], "hashtags": [], "production_checklist": []
}

st.set_page_config(page_title=APP_TITLE, page_icon="🎬", layout="wide", initial_sidebar_state="expanded")
st.markdown("""
<style>
.main .block-container { padding-top: 2rem; max-width: 1380px; }
.hero-card { padding: 1.2rem 1.4rem; border: 1px solid rgba(120,120,120,.18); border-radius: 20px; background: linear-gradient(135deg, rgba(120,120,255,.12), rgba(255,255,255,.03)); }
.small-muted { color: #888; font-size: .92rem; }
.warn-box { padding: 1rem 1.1rem; border: 1px solid rgba(255,80,80,.35); border-radius: 16px; background: rgba(255,80,80,.06); }
.ok-box { padding: 1rem 1.1rem; border: 1px solid rgba(80,200,120,.35); border-radius: 16px; background: rgba(80,200,120,.06); }
</style>
""", unsafe_allow_html=True)

INSIGHT_SYSTEM = """
너는 카드뉴스 업로드 전 기획을 만드는 인사이트 에디터다.
브랜드 관점 입력 없이 레퍼런스, 타깃, 톤에서 관점을 자동 추론한다.
권위자/유명인은 사용할 수 있다. 단, 권위자 발언을 받아쓰기하지 말고 그 말의 오해, 조건, 반전, 적용 기준을 뽑아라.

근거 처리 규칙:
- 실제 레퍼런스에 없는 외부 정보는 확정 사실처럼 쓰지 말고 evidence_notes에 '추론 확장' 또는 '검증 필요'로 표시한다.
- 출처가 없는 고유명사, 연도, 강연명, 수치가 나오면 verification_todo에 넣는다.
- 앱은 웹 리서치 도구가 연결되지 않은 상태에서는 실제 검색을 한 것처럼 쓰면 안 된다.

반드시 JSON만 출력한다.
"""

CARD_DRAFT_SYSTEM = """
너는 카드뉴스 원고를 만드는 콘텐츠 PD다. 이미지/영상/쇼츠/롱폼은 만들지 말고 카드뉴스 원고만 만든다.

강제 규칙:
- headline은 정보 제목이 아니라 주장형 문장이어야 한다.
- body는 설명문이 아니라 짧은 논리여야 한다.
- 저장문장, 저장포인트, save_point, save_line 필드는 만들지 마라.
- insight_device는 이 장이 독자를 설득하는 장치다. 예: 실제 인용 뒤집기, 착각 파괴, 숫자 비교, 실패 사례, 조건문, 자기검증 질문.
- layout_hint는 추후 이미지화할 때 필요한 시각 연출 메모다. 예: 실제 사진 강조, 비교형 인포그래픽, 빈 화면+한 문장, 대시보드, 노트, 타임라인.
- 각 장은 hook, cliche_break, contradiction, proof, reframe, comparison, checklist, final_question 중 역할을 가져야 한다.
- 마지막 장은 댓글 구걸 금지. 자기검증 질문으로 끝낸다.
- 뻔한 말 금지: 노력만으로는 부족하다, 현실 판단이 답이다, 현실은 다르다, 성공하려면 냉철해야 한다, 극한의 노력이 결과 차이를 만든다.

반드시 JSON만 출력한다.
"""

AUDIT_SYSTEM = """
너는 업로드 전 하드게이트 심사위원이다. 절대 후하게 평가하지 마라.
모든 score는 반드시 0~100 사이의 정수로 출력한다.
10점 만점으로 출력하지 마라. 5, 6, 7 같은 10점식 점수 금지.
점수는 1점 단위로 디테일하게 매긴다. 예: 43, 58, 67, 74, 81, 86, 92.
모든 점수가 10의 배수로만 나오면 실패다.
85점 미만이면 업로드 가능으로 판정하지 않는다.
업로드 불가 또는 수정 필요 판정을 내릴 때는 반드시 어떻게 고치면 업로드 가능해지는지까지 제시한다.

평가 기준:
- insight_score: 새 판단 기준과 해석이 있는가
- copy_score: 문장이 저장/공유 가치가 있는가
- logic_score: 메시지가 충돌하지 않는가
- authority_score: 권위자를 써도 받아쓰기로 끝나지 않는가
- risk_score: 과로 미화/성공팔이/검증 안 된 단정 위험이 낮은가
- generic_score: 뻔한 문장 비율. 낮을수록 좋다
- upload_ready_score: 카드뉴스 텍스트만 놓고 바로 업로드 가능한가

반환 JSON 형식:
{"verdict":"업로드 가능 | 수정 필요 | 폐기 후 재작성", "scores":{"insight_score":0,"copy_score":0,"logic_score":0,"authority_score":0,"risk_score":0,"generic_score":0,"upload_ready_score":0}, "weak_lines":[{"line":"", "reason":"", "fix_direction":""}], "critical_issues":[], "rewrite_actions":[], "setting_recommendations":{"tone_hint":"", "angle_shift":"", "card_count":"", "structure_change":"", "opening_strategy":""}, "upgrade_brief":""}
반드시 JSON만 출력한다.
"""

REWRITE_SYSTEM = """
너는 업로드 불가 판정을 받은 카드뉴스를 업로드 가능 수준으로 재설계하는 리라이트 디렉터다.
사용자 개선 방향이 있으면 그것을 최우선으로 반영한다.

목표:
- 모든 score는 0~100점 기준으로 생각한다.
- upload_ready_score 85 이상을 노린다.
- 약한 문장과 정보형 제목을 모두 제거한다.
- 저장문장, 저장포인트, save_point, save_line 필드는 만들지 마라.
- insight_device와 layout_hint는 반드시 유지한다.
- 권위자 인용은 가능하지만 매 장마다 해석과 판단 기준이 있어야 한다.
- 검증되지 않은 외부 정보는 evidence_notes와 verification_todo에 분리한다.

반환 JSON 형식:
{"revised_card_package": {}, "improvement_report": {"why_failed":"", "core_fix":"", "rewritten_strategy":"", "user_direction_reflected":"", "changed_lines":[{"before":"", "after":"", "reason":""}], "setting_recommendations":{"tone_hint":"", "angle_shift":"", "structure_change":""}}}
반드시 JSON만 출력한다.
"""

EXPAND_SYSTEM = """
너는 컨펌된 카드뉴스 원고를 제작물로 확장하는 콘텐츠 프로듀서다.
승인된 card_news의 메시지를 기준으로 선택된 제작물만 만든다.
image_production은 card_news의 insight_device와 layout_hint를 적극 활용해 카드별 이미지화 기준을 만든다.
이미지 프롬프트는 영어, 영상 프롬프트는 영어이며 반드시 카메라 움직임으로 시작한다.
카드뉴스 원고의 핵심 주장을 바꾸지 마라.
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

def normalize_score_value(value: Any) -> int:
    if value is None:
        return 0
    try:
        num = float(value)
    except (TypeError, ValueError):
        return 0
    return max(0, min(100, int(round(num))))

def normalize_scores(gate: Dict[str, Any]) -> Dict[str, Any]:
    scores = gate.get("scores", {}) or {}
    gate["scores"] = {key: normalize_score_value(value) for key, value in scores.items()}
    return gate

def clean_card_package(package: Dict[str, Any]) -> Dict[str, Any]:
    for card in package.get("card_news", []) or []:
        card.pop("save_point", None)
        card.pop("save_line", None)
        if "layout_type" in card and "layout_hint" not in card:
            card["layout_hint"] = card.pop("layout_type")
    return package

def all_card_text(package: Dict[str, Any]) -> str:
    chunks: List[str] = []
    for card in package.get("card_news", []) or []:
        chunks.extend([str(card.get("headline", "")), str(card.get("body", ""))])
    return "\n".join(chunks)

def deterministic_quality_gate(package: Dict[str, Any]) -> Dict[str, Any]:
    package = clean_card_package(package)
    text = all_card_text(package)
    weak_hits = []
    for phrase in GENERIC_PATTERNS:
        if phrase in text:
            weak_hits.append({"line": phrase, "reason": "뻔한 자기계발식 문장입니다.", "fix_direction": "조건, 반전, 판단 기준이 들어간 문장으로 바꾸세요."})
    for pattern in WEAK_HEADLINE_PATTERNS:
        if re.search(pattern, text):
            weak_hits.append({"line": pattern, "reason": "정보 요약형 헤드라인입니다.", "fix_direction": "주장형/반전형 헤드라인으로 바꾸세요."})
    for card in package.get("card_news", []) or []:
        if not str(card.get("insight_device", "")).strip():
            weak_hits.append({"line": f"{card.get('page', '?')}장 insight_device 빈칸", "reason": "설득 장치가 비어 있습니다.", "fix_direction": "이 장의 카피가 왜 먹히는지 장치를 명시하세요."})
        if not str(card.get("layout_hint", "")).strip():
            weak_hits.append({"line": f"{card.get('page', '?')}장 layout_hint 빈칸", "reason": "이미지화 힌트가 비어 있습니다.", "fix_direction": "추후 이미지화 가능한 시각 연출 메모를 넣으세요."})
    generic_score = min(100, len(weak_hits) * 18)
    return {"generic_score": generic_score, "weak_hits": weak_hits}

def merge_audit_with_local(audit: Dict[str, Any], package: Dict[str, Any]) -> Dict[str, Any]:
    local = deterministic_quality_gate(package)
    gate = normalize_scores(dict(audit or {}))
    gate.setdefault("scores", {})
    gate["scores"]["local_generic_score"] = local["generic_score"]
    gate["local_weak_hits"] = local["weak_hits"]
    if local["generic_score"] > 0:
        gate["verdict"] = "수정 필요"
        gate.setdefault("critical_issues", [])
        gate["critical_issues"].append("로컬 하드게이트: 약한 카피 또는 누락된 insight_device/layout_hint가 감지되어 업로드 가능 판정을 차단했습니다.")
    return gate

def is_upload_ready(package: Dict[str, Any], min_score: int) -> bool:
    gate = package.get("quality_gate", {}) or {}
    scores = gate.get("scores", {}) or {}
    if gate.get("verdict") != "업로드 가능":
        return False
    if scores.get("local_generic_score", 0) > 0:
        return False
    return int(scores.get("upload_ready_score", 0) or 0) >= min_score

def build_insight_prompt(reference_text: str, output_language: str, image_ratio: str, card_count: int, platform_hint: str, tone_hint: str, override_topic: str, source_mode: str) -> str:
    return f"""
레퍼런스를 분석해서 insight_board를 만들어라.
설정: 출력 언어={output_language}, 이미지 비율={image_ratio}, 카드뉴스 장수={card_count}, 플랫폼 힌트={platform_hint}, 톤 힌트={tone_hint}, 주제 덮어쓰기={override_topic}, 근거 처리={source_mode}
출력 스키마 예시:
{json.dumps(CARD_SCHEMA, ensure_ascii=False, indent=2)}
레퍼런스:
{reference_text}
"""

def build_card_prompt(insight_data: Dict[str, Any], card_count: int, image_ratio: str) -> str:
    return f"""
아래 insight_board를 기반으로 카드뉴스 원고만 만들어라.
카드뉴스는 {card_count}장, 이미지 비율은 {image_ratio}.
저장문장/save_point/save_line은 절대 만들지 마라.
출력 스키마 예시:
{json.dumps(CARD_SCHEMA, ensure_ascii=False, indent=2)}
insight_board:
{json.dumps(insight_data, ensure_ascii=False, indent=2)}
"""

def build_audit_prompt(card_package: Dict[str, Any]) -> str:
    return f"""
아래 카드뉴스 원고를 심사하라.
모든 score는 0~100 정수다. 10점 만점 금지. 1점 단위로 디테일하게 채점하라.
예: 45, 58, 67, 77, 83, 91처럼 구체 점수를 써라.
업로드 불가/수정 필요라면 어떻게 개선해야 하는지, 어떤 기획 설정으로 바꾸면 좋은지 반드시 제안하라.
카드뉴스 원고:
{json.dumps(card_package, ensure_ascii=False, indent=2)}
"""

def build_rewrite_prompt(card_package: Dict[str, Any], audit: Dict[str, Any], min_score: int, attempt: int, user_direction: str = "") -> str:
    return f"""
아래 카드뉴스는 업로드 가능 기준을 통과하지 못했다.
목표 점수: upload_ready_score {min_score} 이상. 모든 score는 0~100 기준이며 1점 단위로 판단한다.
재작성 회차: {attempt}
사용자 개선 방향:
{user_direction or '없음'}

기존 카드뉴스:
{json.dumps(card_package, ensure_ascii=False, indent=2)}

심사 결과:
{json.dumps(audit, ensure_ascii=False, indent=2)}

해야 할 일:
1. 실패 원인을 improvement_report에 명시한다.
2. 사용자 개선 방향이 있으면 최우선 반영한다.
3. 같은 소재를 업로드 가능한 카드뉴스로 다시 쓴다.
4. 약한 문장과 정보형 제목을 제거한다.
5. insight_device와 layout_hint를 반드시 채운다.
6. 저장문장/save_point/save_line은 만들지 않는다.
7. 카드뉴스 원고만 다시 만든다. 이미지/쇼츠/롱폼은 만들지 않는다.
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

def audit_and_improve(card_package: Dict[str, Any], model: str, min_score: int, max_rewrites: int, user_direction: str = "") -> Dict[str, Any]:
    attempts = []
    current = clean_card_package(card_package)
    for attempt in range(0, max_rewrites + 1):
        audit = call_llm(AUDIT_SYSTEM, build_audit_prompt(current), model, 0.15)
        gate = merge_audit_with_local(audit, current)
        current["quality_gate"] = gate
        attempts.append({"attempt": attempt, "verdict": gate.get("verdict"), "scores": gate.get("scores", {}), "critical_issues": gate.get("critical_issues", [])})
        if is_upload_ready(current, min_score):
            current.setdefault("improvement_report", {})
            current["improvement_report"]["attempts"] = attempts
            return clean_card_package(current)
        if attempt >= max_rewrites:
            current.setdefault("improvement_report", {})
            current["improvement_report"]["attempts"] = attempts
            current["improvement_report"]["next_action"] = "자동 재작성 한도에 도달했습니다. 개선 방향 직접 입력 후 '내 개선 방향으로 재작성'을 눌러주세요."
            return clean_card_package(current)
        rewrite = call_llm(REWRITE_SYSTEM, build_rewrite_prompt(current, gate, min_score, attempt + 1, user_direction), model, 0.35)
        revised = rewrite.get("revised_card_package") if isinstance(rewrite.get("revised_card_package"), dict) else current
        revised["improvement_report"] = rewrite.get("improvement_report", {})
        revised["improvement_report"]["previous_gate"] = gate
        current = clean_card_package(revised)
    return clean_card_package(current)

def stringify(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)

def save_history_item(package: Dict[str, Any]) -> None:
    supabase = get_supabase_client()
    if not supabase:
        st.warning("Supabase가 연결되지 않아 저장하지 못했습니다.")
        return
    package = clean_card_package(package)
    brief = package.get("auto_brief", {}) or {}
    gate = package.get("quality_gate", {}) or {}
    status = package.get("status", "draft")
    verdict = gate.get("verdict", "") if isinstance(gate, dict) else ""
    payload = {"topic": brief.get("topic") or "무제", "verdict": f"{status} | {verdict}".strip(" |"), "reference_preview": package.get("reference_preview", ""), "image_ratio": brief.get("image_ratio", ""), "package": package}
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
        return clean_card_package(package)
    except Exception as exc:
        st.error(f"히스토리 상세 조회 실패: {exc}")
        return None

def delete_history_item(row_id: str) -> None:
    supabase = get_supabase_client()
    if supabase:
        supabase.table(TABLE_NAME).delete().eq("id", row_id).execute()

def package_to_rows(package: Dict[str, Any]) -> List[Dict[str, Any]]:
    package = clean_card_package(package)
    rows: List[Dict[str, Any]] = []
    brief = package.get("auto_brief", {}) or {}
    for card in package.get("card_news", []) or []:
        rows.append({"type":"card_news", "index":card.get("page", ""), "headline":card.get("headline", ""), "body":card.get("body", ""), "role":card.get("role", ""), "insight_device":card.get("insight_device", ""), "layout_hint":card.get("layout_hint", ""), "prompt":"", "image_ratio":brief.get("image_ratio", "")})
    expansion = package.get("expansion", {}) or {}
    for item in (expansion.get("image_production", {}) or {}).get("cards", []) or []:
        rows.append({"type":"image_prompt", "index":item.get("page", ""), "headline":"", "body":item.get("korean_direction", ""), "role":"", "insight_device":"", "layout_hint":item.get("layout_direction", ""), "prompt":item.get("english_prompt", ""), "image_ratio":brief.get("image_ratio", "")})
    shorts = expansion.get("shorts", {}) or {}
    for idx, scene in enumerate(shorts.get("scenes", []) or [], 1):
        rows.append({"type":"shorts_scene", "index":idx, "headline":scene.get("caption", ""), "body":scene.get("narration", ""), "role":scene.get("time", ""), "insight_device":"", "layout_hint":scene.get("visual", ""), "prompt":stringify(scene.get("video_prompt", {})), "image_ratio":brief.get("image_ratio", "")})
    longform = expansion.get("longform", {}) or {}
    if longform:
        rows.append({"type":"longform_script", "index":1, "headline":longform.get("title", ""), "body":longform.get("script", ""), "role":"longform", "insight_device":"", "layout_hint":"", "prompt":"", "image_ratio":brief.get("image_ratio", "")})
    return rows

def to_csv(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return ""
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()

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

def render_card_package(package: Dict[str, Any], min_score: int) -> None:
    package = clean_card_package(package)
    gate = package.get("quality_gate", {}) or {}
    scores = gate.get("scores", {}) or {}
    verdict = gate.get("verdict", "")
    status = package.get("status", "draft")
    box_class = "ok-box" if is_upload_ready(package, min_score) else "warn-box"
    st.markdown(f"<div class='{box_class}'><b>상태:</b> {status} &nbsp; <b>판정:</b> {verdict or '판정 없음'} &nbsp; <b>기준:</b> {min_score}/100</div>", unsafe_allow_html=True)
    if verdict:
        cols = st.columns(4)
        for idx, key in enumerate(["insight_score", "copy_score", "local_generic_score", "upload_ready_score"]):
            with cols[idx]:
                st.metric(key, scores.get(key, "-"))
    tabs = st.tabs(["카드뉴스 원고", "개선 리포트", "근거/검증 메모", "인사이트 보드", "하드게이트", "확장 결과", "CSV/JSON"])
    with tabs[0]:
        for i, card in enumerate(package.get("card_news", []) or [], 1):
            with st.expander(f"{card.get('page', i)}장 · {card.get('role','')} · {card.get('headline','')}", expanded=i <= 2):
                st.markdown(f"**헤드라인**\n\n{card.get('headline','')}")
                st.markdown(f"**본문**\n\n{card.get('body','')}")
                st.markdown(f"**인사이트 장치**\n\n{card.get('insight_device','')}")
                st.markdown(f"**레이아웃 힌트**\n\n{card.get('layout_hint','')}")
    with tabs[1]:
        st.json(package.get("improvement_report", {}))
    with tabs[2]:
        board = package.get("insight_board", {}) or {}
        st.write("evidence_notes", board.get("evidence_notes", []))
        st.write("verification_todo", board.get("verification_todo", []))
    with tabs[3]:
        st.json(package.get("insight_board", {}))
    with tabs[4]:
        st.json(gate)
    with tabs[5]:
        expansion = package.get("expansion")
        if not expansion:
            st.info("카드뉴스 컨펌 후 제작 확장을 생성하면 여기에 표시됩니다.")
        else:
            render_expansion(expansion)
    with tabs[6]:
        csv_text = to_csv(package_to_rows(package))
        st.download_button("CSV 다운로드", csv_text, file_name="ai_pd_studio_v8_content.csv", mime="text/csv", use_container_width=True)
        st.download_button("JSON 다운로드", stringify(package), file_name="ai_pd_studio_v8_output.json", mime="application/json", use_container_width=True)

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
                st.success("상세를 불러왔습니다.")
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

st.markdown(f"""<div class='hero-card'><h1>{APP_TITLE}</h1><p>{APP_SUBTITLE}</p><p class='small-muted'>저장포인트를 제거하고, 점수는 45/67/77처럼 1점 단위 정밀 채점으로 유도합니다.</p></div>""", unsafe_allow_html=True)

st.sidebar.header("메인 메뉴")
menu = st.sidebar.radio("이동", ["카드뉴스 기획", "제작 확장", "히스토리"], key="menu")
st.sidebar.header("⚙️ 공통 설정")
model = st.sidebar.selectbox("OpenAI 모델", ["gpt-4.1", "gpt-4.1-mini", "gpt-4o", "gpt-4o-mini"], index=0)
temperature = st.sidebar.slider("창의성", 0.1, 1.2, 0.75, 0.05)
output_language = st.sidebar.selectbox("출력 언어", ["한국어", "영어", "한국어+영어"], index=0)
image_ratio = st.sidebar.selectbox("이미지 비율", ["1:1 square card news", "9:16 vertical shorts", "4:5 Instagram feed", "16:9 YouTube wide"], index=0)
card_count = st.sidebar.slider("카드뉴스 장수", 5, 12, 8, 1)
min_upload_score = st.sidebar.slider("업로드 가능 최소 점수", 0, 100, 85, 1)
max_rewrites = st.sidebar.slider("자동 개선 재시도 횟수", 0, 3, 2, 1)
source_mode = st.sidebar.selectbox("근거 처리", ["추론 확장 + 검증 필요 표시", "레퍼런스 안에서만 작성", "외부 근거처럼 쓰지 않기"], index=0)
with st.sidebar.expander("Secrets 확인"):
    st.code('OPENAI_API_KEY = "sk-..."\nSUPABASE_URL = "https://...supabase.co"\nSUPABASE_SERVICE_ROLE_KEY = "sb_secret_..."', language="toml")
    st.caption(f"현재 저장 방식: {storage_mode()}")

st.divider()

if menu == "카드뉴스 기획":
    left, right = st.columns([0.84, 1.16], gap="large")
    with left:
        st.subheader("Step 1. 카드뉴스 원고 생성")
        reference_text = st.text_area("레퍼런스 텍스트 / CSV 내용 / 대본 / 카드뉴스 문구", height=320, placeholder="여기에 레퍼런스를 붙여넣으세요.")
        with st.expander("기획 설정"):
            override_topic = st.text_input("주제 덮어쓰기", placeholder="비워두면 자동 추론")
            platform_hint = st.selectbox("플랫폼 힌트", ["AI가 판단", "Instagram 카드뉴스", "YouTube Shorts", "Instagram Reels", "TikTok", "혼합"], index=0)
            tone_hint = st.selectbox("톤 힌트", ["커뮤니티 인기글형", "전문가 정보형", "자극적 후킹형", "다큐멘터리형", "광고 카피형"], index=0)
        run_button = st.button("카드뉴스 원고 생성", type="primary", use_container_width=True)

        if st.session_state.current_package:
            st.divider()
            st.subheader("Step 2. 원고 개선/컨펌")
            ready = is_upload_ready(st.session_state.current_package, min_upload_score)
            if not ready:
                st.warning("현재 원고는 업로드 가능 기준을 통과하지 못했습니다. 개선 방향을 직접 입력해 재작성할 수 있습니다.")
            manual_direction = st.text_area("개선 방향 직접 입력", height=130, placeholder="예: 노동시간 이야기는 유지하되 과로 찬양이 아니라 '검증 없는 실행량은 실패 속도만 높인다'는 관점으로 바꿔. 6장은 비교형으로 살리고, 문장은 더 커뮤니티 인기글처럼 세게.")
            col_a, col_b = st.columns(2)
            with col_a:
                if st.button("자동 개선 다시 시도", use_container_width=True):
                    with st.spinner("자동 개선 재시도 중"):
                        improved = audit_and_improve(st.session_state.current_package, model, min_upload_score, max_rewrites, "")
                        st.session_state.current_package = improved
                        save_history_item(improved)
                        st.rerun()
            with col_b:
                if st.button("내 개선 방향으로 재작성", use_container_width=True):
                    with st.spinner("사용자 디렉션 반영 재작성 중"):
                        improved = audit_and_improve(st.session_state.current_package, model, min_upload_score, max_rewrites, manual_direction)
                        st.session_state.current_package = improved
                        save_history_item(improved)
                        st.rerun()
            if st.button("이 카드뉴스 내용 컨펌", use_container_width=True, disabled=not ready):
                approved = clean_card_package(dict(st.session_state.current_package))
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
            status.info("1/4 인사이트 보드 생성 중")
            insight_data = call_llm(INSIGHT_SYSTEM, build_insight_prompt(reference_text, output_language, image_ratio, card_count, platform_hint, tone_hint, override_topic, source_mode), model, 0.25)
            progress.progress(25)
            status.info("2/4 카드뉴스 원고 생성 중")
            card_package = call_llm(CARD_DRAFT_SYSTEM, build_card_prompt(insight_data, card_count, image_ratio), model, temperature)
            card_package["auto_brief"] = insight_data.get("auto_brief", card_package.get("auto_brief", {}))
            card_package["insight_board"] = insight_data.get("insight_board", card_package.get("insight_board", {}))
            card_package["status"] = "draft"
            card_package = clean_card_package(card_package)
            progress.progress(50)
            status.info("3/4 하드게이트 심사 및 자동 개선 중")
            card_package = audit_and_improve(card_package, model, min_upload_score, max_rewrites)
            progress.progress(85)
            status.info("4/4 저장 중")
            card_package["created_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            card_package["reference_preview"] = reference_text[:300]
            card_package.setdefault("auto_brief", {}).setdefault("image_ratio", image_ratio)
            st.session_state.current_package = card_package
            save_history_item(card_package)
            st.session_state.history_meta = load_history_meta(HISTORY_LIMIT)
            progress.progress(100)
            if is_upload_ready(card_package, min_upload_score):
                status.success("업로드 가능 기준을 통과한 카드뉴스 원고를 생성했습니다. 컨펌 후 제작 확장으로 넘어가세요.")
            else:
                status.warning("자동 개선 후에도 업로드 기준을 통과하지 못했습니다. 개선 방향을 직접 입력해 재작성하세요.")

    with right:
        st.subheader("결과")
        if not st.session_state.current_package:
            st.info("카드뉴스 원고를 생성하면 여기에 표시됩니다.")
        else:
            render_card_package(st.session_state.current_package, min_upload_score)

elif menu == "제작 확장":
    st.subheader("Step 3. 컨펌된 카드뉴스를 제작물로 확장")
    approved = st.session_state.approved_package
    if not approved:
        st.warning("먼저 카드뉴스 기획 메뉴에서 업로드 가능 원고를 컨펌해주세요.")
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
            longform_minutes = st.slider("롱폼 분량", 3, 20, 8, 1)
            expand_button = st.button("선택한 제작물 생성", type="primary", use_container_width=True)
        with col_b:
            st.markdown("### 컨펌된 카드뉴스 원고")
            render_card_package(approved, min_upload_score)
        if expand_button:
            options = {"make_images":make_images, "make_shorts":make_shorts, "make_longform":make_longform, "make_titles":make_titles, "visual_style":visual_style, "video_style":video_style, "longform_minutes":longform_minutes, "image_ratio":image_ratio}
            with st.spinner("컨펌된 카드뉴스를 기준으로 제작물을 확장 중입니다."):
                expansion = call_llm(EXPAND_SYSTEM, build_expand_prompt(clean_card_package(approved), options), model, min(1.0, temperature + 0.05))
                expanded = clean_card_package(dict(approved))
                expanded["status"] = "expanded"
                expanded["expanded_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                expanded["expansion_options"] = options
                expanded["expansion"] = expansion
                st.session_state.approved_package = expanded
                st.session_state.current_package = expanded
                save_history_item(expanded)
                st.session_state.history_meta = load_history_meta(HISTORY_LIMIT)
                st.success("제작 확장 완료.")
                render_card_package(expanded, min_upload_score)
else:
    render_history()
