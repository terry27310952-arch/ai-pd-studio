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

APP_TITLE = "AI PD Studio V12"
APP_SUBTITLE = "카드뉴스 원고 확정 → 텍스트 포함 카드 프롬프트 → 쇼츠/롱폼 내레이션 + 클린 이미지 프롬프트"
TABLE_NAME = "content_history"
HISTORY_LIMIT = 30

GENERIC_PATTERNS = [
    "노력만으로는 부족하다", "현실은 다르다", "성공 공식", "행동해야 한다", "성장의 시작",
    "기회가 늘어난다", "특별한 능력보다", "결정적인 차이를 만든다", "실패는 성장",
]
WEAK_PATTERNS = [r"차이는 의외로 단순", r"경험할 수 있다", r"기회는 늘어난다"]

st.set_page_config(page_title=APP_TITLE, page_icon="🎬", layout="wide")
st.markdown(
    """
<style>
.main .block-container{max-width:1440px;padding-top:2rem}
.hero{padding:1.1rem 1.3rem;border:1px solid rgba(120,120,120,.22);border-radius:18px;background:linear-gradient(135deg,rgba(120,120,255,.12),rgba(255,255,255,.03))}
.box{padding:1rem;border:1px solid rgba(120,120,120,.22);border-radius:16px;margin-bottom:.8rem}
.ok{background:rgba(80,200,120,.08)}.warn{background:rgba(255,80,80,.08)}.info{background:rgba(120,120,120,.07)}
.small{font-size:.9rem;color:#777}
textarea{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace!important}
</style>
""",
    unsafe_allow_html=True,
)

RESEARCH_SYSTEM = """
너는 카드뉴스용 팩트체크 리서처다.
확인된 출처만 confirmed로 표시한다. 불확실하면 needs_verification으로 둔다.
카드 하단 각주로 노출 가능한 것은 source_confidence=confirmed, usable_in_card=true 뿐이다.
반드시 JSON만 출력한다.
반환 형식:
{"research_summary":"", "research_brief":[{"id":"S1","claim":"","source_title":"","source_name":"","source_url":"","source_date":"","source_context":"","source_confidence":"confirmed|inferred|needs_verification","usable_in_card":true,"display_text":""}], "research_warnings":[]}
"""

REASONING_SYSTEM = """
너는 카드뉴스 추론 설계자다. 좋은 말 모음이 아니라 논리 설계도를 만든다.
반드시 surface_topic, core_problem, non_obvious_insight, opposing_cliche, causal_mechanism, reader_self_diagnosis, claim_ladder, no_repeat_rules, card_arc를 만든다.
얕은 문장 금지: 행동해야 한다, 성장한다, 기회가 늘어난다, 실패는 성장 과정이다.
role은 main 금지. hook, cliche_break, mechanism, proof, reframe, contrast, self_test, close만 사용한다.
JSON만 출력한다.
"""

CARD_SYSTEM = """
너는 카드뉴스 원고 PD다. reasoning_blueprint와 research_brief를 기준으로 카드뉴스 원고만 만든다.
규칙:
- headline은 주장형, body는 짧은 논리.
- 저장문장/save_point/save_line 금지.
- role=main 금지. 모든 장은 다른 논리 기능을 가져야 한다.
- insight_device는 설득 장치, layout_hint는 이미지화 연출 메모다.
- confirmed 출처만 source_refs에 넣고 source_display를 만든다. 없으면 빈 배열/빈 문자열.
- 출처 없는 '연구에 따르면' 금지.
JSON만 출력한다.
반환 형식:
{"status":"draft","auto_brief":{"topic":"","image_ratio":""},"reasoning_blueprint":{},"research_brief":[],"card_news":[{"page":1,"role":"hook","headline":"","body":"","insight_device":"","layout_hint":"","source_refs":[],"source_display":""}],"quality_gate":{},"improvement_report":{}}
"""

AUDIT_SYSTEM = """
너는 업로드 전 심사위원이다. 0~100 정수로 1점 단위 채점한다. 10점 만점 금지.
85점 미만은 업로드 가능 불가. 반복, 얕은 조언, role=main, 미검증 출처 각주는 강하게 감점한다.
JSON만 출력한다.
반환 형식:
{"verdict":"업로드 가능|수정 필요|폐기 후 재작성","scores":{"reasoning_score":0,"insight_score":0,"copy_score":0,"progression_score":0,"source_integrity_score":0,"risk_score":0,"upload_ready_score":0},"weak_lines":[],"critical_issues":[],"rewrite_actions":[],"upgrade_brief":""}
"""

REWRITE_SYSTEM = """
너는 카드뉴스 리라이트 디렉터다. 사용자 개선 방향을 최우선 반영한다.
반복되는 주장 제거, role=main 금지, 얕은 조언을 원인/메커니즘/판단 기준으로 변경, confirmed 출처만 사용.
저장문장/save_point/save_line 금지. JSON만 출력한다.
반환: {"revised_card_package":{},"improvement_report":{"why_failed":"","core_fix":"","user_direction_reflected":"","changed_lines":[]}}
"""

EXPAND_SYSTEM = """
너는 컨펌된 카드뉴스를 실제 제작 산출물로 확장하는 제작 디렉터다.
반드시 JSON만 출력한다.

생성해야 하는 것은 정확히 5종이다.
1. card_image_prompts: 카드뉴스 이미지 프롬프트. 텍스트 포함 최종 카드 이미지 생성용이다.
2. shorts_script: 쇼츠용 대본. 내레이션만 산출한다.
3. shorts_image_prompts_clean: 쇼츠용 이미지 프롬프트. 텍스트 없는 클린 이미지 소스만 산출한다.
4. longform_script: 롱폼용 대본. 내레이션만 산출한다.
5. longform_image_prompts_clean: 롱폼용 이미지 프롬프트. 텍스트 없는 클린 이미지 소스만 산출한다.

카드뉴스 이미지 프롬프트 규칙:
- full_card_prompt_with_text에는 실제 카드에 들어갈 한국어 헤드카피, 바디카피, 출처 각주 텍스트까지 포함한다.
- typography_rules에는 서체 조합(세리프/산세리프 등), 헤드/바디 크기 비율, 자간, 행간, 굵기 규칙을 넣는다.
- layout_rules에는 헤드카피 위치, 바디카피 위치, 이미지 영역, 여백, 그리드, 각주 위치를 넣는다.
- design_style에는 3개 스타일 기준점 중 하나의 이름과 시각 성격을 넣는다.
- 카드뉴스 이미지는 텍스트 포함 최종 이미지용이므로 no text를 넣으면 안 된다.
- 단, 워터마크, 깨진 글자, 임의 로고, 실존 인물 정확한 얼굴 재현은 피한다.

쇼츠/롱폼 이미지 프롬프트 규칙:
- clean_image_prompt에는 절대 텍스트, 자막, 타이포그래피, 로고를 넣지 않는다.
- 대본 맥락에 맞는 장면, 인물, 공간, 감정, 카메라 구도만 만든다.
- negative_prompt에는 text, subtitle, caption, typography, logo, watermark를 반드시 포함한다.

디자인 기준점:
- design_systems를 3개 만든다.
- 각 design_system은 서체 조합, 크기 비율, 자간, 행간, 레이아웃, 컬러, 질감, 그래픽 규칙을 포함한다.
- 3개는 서로 충분히 달라야 한다. 예: 에디토리얼 매거진형, 테크 다큐형, 커뮤니티 밈에세이형.

반환 스키마:
{
  "design_systems": [
    {"id":"STYLE_A","name":"","personality":"","type_pairing":{"headline":"","body":"","caption":""},"typography_rules":{"headline_size_ratio":"","body_size_ratio":"","letter_spacing":"","line_height":"","weight":""},"layout_rules":{"grid":"","safe_margin":"","headline_position":"","body_position":"","image_zone":"","footer_source_position":""},"visual_rules":{"palette":"","contrast":"","texture":"","graphic_elements":"","photo_treatment":""}}
  ],
  "card_image_prompts": [
    {"page":1,"full_card_prompt_with_text":"","typography_rules":"","layout_rules":"","design_style":"","negative_prompt":""}
  ],
  "shorts_script": [
    {"scene":1,"narration":""}
  ],
  "shorts_image_prompts_clean": [
    {"scene":1,"clean_image_prompt":"","negative_prompt":"text, subtitle, caption, typography, logo, watermark, distorted hands, low quality"}
  ],
  "longform_script": [
    {"chapter":1,"narration":""}
  ],
  "longform_image_prompts_clean": [
    {"chapter":1,"clean_image_prompt":"","negative_prompt":"text, subtitle, caption, typography, logo, watermark, distorted hands, low quality"}
  ],
  "titles":[],
  "thumbnail_copy":[],
  "hashtags":[],
  "production_checklist":[]
}
"""

@st.cache_resource(show_spinner=False)
def openai_cached(key: str) -> OpenAI:
    return OpenAI(api_key=key)

@st.cache_resource(show_spinner=False)
def supabase_cached(url: str, key: str) -> Client:
    return create_client(url, key)


def get_secret(name: str) -> str:
    try:
        return st.secrets.get(name, "") or os.getenv(name, "")
    except Exception:
        return os.getenv(name, "")


def get_openai() -> OpenAI:
    key = get_secret("OPENAI_API_KEY")
    if not key:
        st.error("OPENAI_API_KEY가 없습니다.")
        st.stop()
    return openai_cached(key)


def get_db() -> Optional[Client]:
    url = get_secret("SUPABASE_URL")
    key = get_secret("SUPABASE_SERVICE_ROLE_KEY") or get_secret("SUPABASE_ANON_KEY")
    if not url or not key:
        return None
    try:
        return supabase_cached(url, key)
    except Exception:
        return None


def json_load(text: str) -> Dict[str, Any]:
    text = (text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).strip()
        text = re.sub(r"```$", "", text).strip()
    try:
        return json.loads(text)
    except Exception:
        match = re.search(r"\{.*\}", text, re.S)
        return json.loads(match.group(0)) if match else {}


def llm(system: str, user: str, model: str, temp: float) -> Dict[str, Any]:
    res = get_openai().chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=temp,
        response_format={"type": "json_object"},
    )
    return json_load(res.choices[0].message.content or "{}")


def web_research(query: str, model: str) -> Dict[str, Any]:
    try:
        res = get_openai().responses.create(
            model=model,
            tools=[{"type": "web_search_preview"}],
            input=[{"role": "system", "content": RESEARCH_SYSTEM}, {"role": "user", "content": query}],
            text={"format": {"type": "json_object"}},
        )
        return json_load(getattr(res, "output_text", "") or "{}")
    except Exception as exc:
        return {"research_summary": "웹 검색 실패", "research_brief": [], "research_warnings": [str(exc)]}


def clean_package(pkg: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(pkg, dict):
        return {}
    for card in pkg.get("card_news", []) or []:
        if isinstance(card, dict):
            card.pop("save_point", None)
            card.pop("save_line", None)
            if "layout_type" in card and "layout_hint" not in card:
                card["layout_hint"] = card.pop("layout_type")
            card.setdefault("source_refs", [])
            card.setdefault("source_display", "")
    return pkg


def confirmed_ids(pkg: Dict[str, Any]) -> set:
    return {
        item.get("id")
        for item in pkg.get("research_brief", []) or []
        if item.get("source_confidence") == "confirmed" and item.get("usable_in_card") is True
    }


def local_gate(pkg: Dict[str, Any]) -> Dict[str, Any]:
    pkg = clean_package(pkg)
    text = "\n".join([f"{c.get('headline','')}\n{c.get('body','')}" for c in pkg.get("card_news", []) or []])
    hits = []
    for phrase in GENERIC_PATTERNS:
        if phrase in text:
            hits.append({"line": phrase, "reason": "얕거나 뻔한 문장", "fix_direction": "원인/메커니즘/판단 기준으로 변경"})
    for pattern in WEAK_PATTERNS:
        if re.search(pattern, text):
            hits.append({"line": pattern, "reason": "약한 패턴", "fix_direction": "구체 주장으로 변경"})
    ids = confirmed_ids(pkg)
    roles = []
    for card in pkg.get("card_news", []) or []:
        role = card.get("role", "")
        roles.append(role)
        if role == "main":
            hits.append({"line": "role=main", "reason": "카드 역할이 뭉뚱그려짐", "fix_direction": "mechanism/proof/reframe 등으로 변경"})
        if not card.get("insight_device"):
            hits.append({"line": f"{card.get('page')}장 insight_device", "reason": "설득 장치 누락", "fix_direction": "설득 장치 추가"})
        if not card.get("layout_hint"):
            hits.append({"line": f"{card.get('page')}장 layout_hint", "reason": "이미지화 힌트 누락", "fix_direction": "시각화 메모 추가"})
        for ref in card.get("source_refs", []) or []:
            if ref not in ids:
                hits.append({"line": f"미검증 출처 {ref}", "reason": "confirmed가 아닌 출처", "fix_direction": "각주 제거 또는 confirmed로 교체"})
    if roles.count("main") >= 2:
        hits.append({"line": "main 반복", "reason": "논리 전진 약함", "fix_direction": "카드별 역할 분리"})
    return {"score": min(100, len(hits) * 18), "hits": hits}


def normalize_audit(audit: Dict[str, Any]) -> Dict[str, Any]:
    scores = audit.get("scores", {}) or {}
    out = {}
    for key, value in scores.items():
        try:
            out[key] = max(0, min(100, int(round(float(value)))))
        except Exception:
            out[key] = 0
    audit["scores"] = out
    return audit


def merge_gate(audit: Dict[str, Any], pkg: Dict[str, Any]) -> Dict[str, Any]:
    audit = normalize_audit(audit or {})
    local = local_gate(pkg)
    audit.setdefault("scores", {})
    audit["scores"]["local_generic_score"] = local["score"]
    audit["local_weak_hits"] = local["hits"]
    if local["score"] > 0:
        audit["verdict"] = "수정 필요"
        audit.setdefault("critical_issues", []).append("로컬 하드게이트 감점 요소 발견")
    return audit


def is_ready(pkg: Dict[str, Any], min_score: int) -> bool:
    gate = pkg.get("quality_gate", {}) or {}
    scores = gate.get("scores", {}) or {}
    return gate.get("verdict") == "업로드 가능" and scores.get("local_generic_score", 0) == 0 and int(scores.get("upload_ready_score", 0) or 0) >= min_score


def audit_loop(pkg: Dict[str, Any], model: str, min_score: int, max_rewrites: int, direction: str) -> Dict[str, Any]:
    current = clean_package(pkg)
    attempts = []
    for idx in range(max_rewrites + 1):
        audit = llm(AUDIT_SYSTEM, json.dumps(current, ensure_ascii=False), model, 0.15)
        gate = merge_gate(audit, current)
        current["quality_gate"] = gate
        attempts.append({"attempt": idx, "verdict": gate.get("verdict"), "scores": gate.get("scores", {})})
        if is_ready(current, min_score) or idx == max_rewrites:
            break
        prompt = f"사용자 개선 방향:\n{direction}\n기존 원고:\n{json.dumps(current, ensure_ascii=False)}\n심사:\n{json.dumps(gate, ensure_ascii=False)}"
        rewrite = llm(REWRITE_SYSTEM, prompt, model, 0.35)
        current = clean_package(rewrite.get("revised_card_package", current))
        current["improvement_report"] = rewrite.get("improvement_report", {})
    current.setdefault("improvement_report", {})["attempts"] = attempts
    return current


def save_history(pkg: Dict[str, Any]) -> None:
    db = get_db()
    if not db:
        return
    pkg = clean_package(pkg)
    brief = pkg.get("auto_brief", {}) or {}
    gate = pkg.get("quality_gate", {}) or {}
    payload = {
        "topic": brief.get("topic") or pkg.get("reasoning_blueprint", {}).get("surface_topic") or "무제",
        "verdict": f"{pkg.get('status','draft')} | {gate.get('verdict','')}".strip(" |"),
        "reference_preview": pkg.get("reference_preview", ""),
        "image_ratio": brief.get("image_ratio", ""),
        "package": pkg,
    }
    try:
        db.table(TABLE_NAME).insert(payload).execute()
    except Exception as exc:
        st.warning(f"자동 저장 실패: {exc}")


def load_latest() -> Optional[Dict[str, Any]]:
    db = get_db()
    if not db:
        return None
    try:
        rows = db.table(TABLE_NAME).select("package").order("created_at", desc=True).limit(1).execute().data or []
        return clean_package(rows[0].get("package")) if rows else None
    except Exception:
        return None


def load_history_meta(limit: int = HISTORY_LIMIT) -> List[Dict[str, Any]]:
    db = get_db()
    if not db:
        return []
    try:
        return db.table(TABLE_NAME).select("id,created_at,topic,verdict,reference_preview,image_ratio").order("created_at", desc=True).limit(limit).execute().data or []
    except Exception:
        return []


def load_history_item(row_id: str) -> Optional[Dict[str, Any]]:
    db = get_db()
    if not db:
        return None
    try:
        rows = db.table(TABLE_NAME).select("package").eq("id", row_id).limit(1).execute().data or []
        return clean_package(rows[0].get("package")) if rows else None
    except Exception:
        return None


def make_csv(rows: List[Dict[str, Any]]) -> str:
    output = io.StringIO()
    if rows:
        writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return output.getvalue()


def rows_card_news(pkg: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [
        {
            "page": c.get("page"),
            "role": c.get("role"),
            "headline": c.get("headline"),
            "body": c.get("body"),
            "insight_device": c.get("insight_device"),
            "layout_hint": c.get("layout_hint"),
            "source_display": c.get("source_display"),
        }
        for c in pkg.get("card_news", []) or []
    ]


def rows_card_image(pkg: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [
        {
            "page": item.get("page"),
            "full_card_prompt_with_text": item.get("full_card_prompt_with_text"),
            "typography_rules": item.get("typography_rules"),
            "layout_rules": item.get("layout_rules"),
            "design_style": item.get("design_style"),
            "negative_prompt": item.get("negative_prompt"),
        }
        for item in (pkg.get("expansion", {}) or {}).get("card_image_prompts", []) or []
    ]


def rows_shorts_script(pkg: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [
        {"scene": item.get("scene"), "narration": item.get("narration")}
        for item in (pkg.get("expansion", {}) or {}).get("shorts_script", []) or []
    ]


def rows_shorts_image(pkg: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [
        {"scene": item.get("scene"), "clean_image_prompt": item.get("clean_image_prompt"), "negative_prompt": item.get("negative_prompt")}
        for item in (pkg.get("expansion", {}) or {}).get("shorts_image_prompts_clean", []) or []
    ]


def rows_longform_script(pkg: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [
        {"chapter": item.get("chapter"), "narration": item.get("narration")}
        for item in (pkg.get("expansion", {}) or {}).get("longform_script", []) or []
    ]


def rows_longform_image(pkg: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [
        {"chapter": item.get("chapter"), "clean_image_prompt": item.get("clean_image_prompt"), "negative_prompt": item.get("negative_prompt")}
        for item in (pkg.get("expansion", {}) or {}).get("longform_image_prompts_clean", []) or []
    ]


def render_downloads(pkg: Dict[str, Any]) -> None:
    downloads = [
        ("카드뉴스 CSV", "card_news.csv", rows_card_news(pkg)),
        ("카드뉴스 이미지 프롬프트 CSV", "card_image_prompts.csv", rows_card_image(pkg)),
        ("쇼츠용 대본 CSV", "shorts_script.csv", rows_shorts_script(pkg)),
        ("쇼츠용 이미지 프롬프트 클린 CSV", "shorts_image_prompts_clean.csv", rows_shorts_image(pkg)),
        ("롱폼용 대본 CSV", "longform_script.csv", rows_longform_script(pkg)),
        ("롱폼용 이미지 프롬프트 클린 CSV", "longform_image_prompts_clean.csv", rows_longform_image(pkg)),
    ]
    cols = st.columns(2)
    for idx, (label, filename, rows) in enumerate(downloads):
        with cols[idx % 2]:
            st.download_button(label, make_csv(rows), filename, "text/csv", use_container_width=True, disabled=not bool(rows))
    st.download_button("전체 JSON 다운로드", json.dumps(pkg, ensure_ascii=False, indent=2), "ai_pd_studio_v12.json", "application/json", use_container_width=True)


def render_expansion_console(pkg: Dict[str, Any]) -> None:
    exp = pkg.get("expansion", {}) or {}
    if not exp:
        st.info("제작 확장을 생성하면 여기에 표시됩니다.")
        return
    tabs = st.tabs(["디자인 시스템 3안", "카드 이미지 프롬프트", "쇼츠 대본", "쇼츠 클린 이미지", "롱폼 대본", "롱폼 클린 이미지", "제목/썸네일", "원본 JSON"])
    with tabs[0]:
        for sys in exp.get("design_systems", []) or []:
            with st.expander(f"{sys.get('id','STYLE')} · {sys.get('name','')}", expanded=False):
                st.markdown(f"**성격**\n\n{sys.get('personality','')}")
                st.json(sys)
    with tabs[1]:
        for item in exp.get("card_image_prompts", []) or []:
            with st.expander(f"{item.get('page')}장 · {item.get('design_style','')}", expanded=str(item.get("page")) in ["1", "2"]):
                st.text_area("Full Card Prompt With Text", item.get("full_card_prompt_with_text", ""), height=180, key=f"card_prompt_{item.get('page')}")
                st.text_area("Typography Rules", item.get("typography_rules", ""), height=90, key=f"typo_{item.get('page')}")
                st.text_area("Layout Rules", item.get("layout_rules", ""), height=90, key=f"layout_{item.get('page')}")
                st.text_area("Negative Prompt", item.get("negative_prompt", ""), height=70, key=f"card_neg_{item.get('page')}")
    with tabs[2]:
        for item in exp.get("shorts_script", []) or []:
            with st.expander(f"쇼츠 scene {item.get('scene')}", expanded=int(item.get("scene", 9)) <= 2 if str(item.get("scene", "")).isdigit() else False):
                st.text_area("Narration", item.get("narration", ""), height=140, key=f"short_nar_{item.get('scene')}")
    with tabs[3]:
        for item in exp.get("shorts_image_prompts_clean", []) or []:
            with st.expander(f"쇼츠 클린 이미지 scene {item.get('scene')}", expanded=False):
                st.text_area("Clean Image Prompt", item.get("clean_image_prompt", ""), height=140, key=f"short_img_{item.get('scene')}")
                st.text_area("Negative Prompt", item.get("negative_prompt", ""), height=70, key=f"short_neg_{item.get('scene')}")
    with tabs[4]:
        for item in exp.get("longform_script", []) or []:
            with st.expander(f"롱폼 chapter {item.get('chapter')}", expanded=int(item.get("chapter", 9)) <= 2 if str(item.get("chapter", "")).isdigit() else False):
                st.text_area("Narration", item.get("narration", ""), height=220, key=f"long_nar_{item.get('chapter')}")
    with tabs[5]:
        for item in exp.get("longform_image_prompts_clean", []) or []:
            with st.expander(f"롱폼 클린 이미지 chapter {item.get('chapter')}", expanded=False):
                st.text_area("Clean Image Prompt", item.get("clean_image_prompt", ""), height=140, key=f"long_img_{item.get('chapter')}")
                st.text_area("Negative Prompt", item.get("negative_prompt", ""), height=70, key=f"long_neg_{item.get('chapter')}")
    with tabs[6]:
        st.write("제목", exp.get("titles", []))
        st.write("썸네일", exp.get("thumbnail_copy", []))
        st.write("해시태그", " ".join(exp.get("hashtags", [])))
        st.write("체크리스트", exp.get("production_checklist", []))
    with tabs[7]:
        st.json(exp)


def render_package(pkg: Optional[Dict[str, Any]], min_score: int) -> None:
    if not pkg:
        st.info("생성 결과가 여기에 표시됩니다.")
        return
    pkg = clean_package(pkg)
    gate = pkg.get("quality_gate", {}) or {}
    scores = gate.get("scores", {}) or {}
    status_class = "ok" if is_ready(pkg, min_score) else "warn"
    st.markdown(f"<div class='box {status_class}'><b>상태:</b> {pkg.get('status','draft')} &nbsp; <b>판정:</b> {gate.get('verdict','-')} &nbsp; <b>기준:</b> {min_score}/100</div>", unsafe_allow_html=True)
    cols = st.columns(5)
    for idx, key in enumerate(["reasoning_score", "insight_score", "progression_score", "local_generic_score", "upload_ready_score"]):
        cols[idx].metric(key, scores.get(key, "-"))
    tabs = st.tabs(["카드뉴스", "추론 설계도", "리서치", "개선 리포트", "하드게이트", "제작 확장 콘솔", "CSV/JSON"])
    with tabs[0]:
        for i, card in enumerate(pkg.get("card_news", []) or [], 1):
            with st.expander(f"{card.get('page', i)}장 · {card.get('role','')} · {card.get('headline','')}", expanded=i <= 2):
                st.markdown(f"**헤드라인**\n\n{card.get('headline','')}")
                st.markdown(f"**본문**\n\n{card.get('body','')}")
                st.markdown(f"**인사이트 장치**\n\n{card.get('insight_device','')}")
                st.markdown(f"**레이아웃 힌트**\n\n{card.get('layout_hint','')}")
                if card.get("source_display"):
                    st.caption(card.get("source_display"))
    with tabs[1]:
        st.json(pkg.get("reasoning_blueprint", {}))
    with tabs[2]:
        st.json({"research_summary": pkg.get("research_summary", ""), "research_brief": pkg.get("research_brief", []), "research_warnings": pkg.get("research_warnings", [])})
    with tabs[3]:
        st.json(pkg.get("improvement_report", {}))
    with tabs[4]:
        st.json(gate)
    with tabs[5]:
        render_expansion_console(pkg)
    with tabs[6]:
        render_downloads(pkg)


if "current" not in st.session_state:
    st.session_state.current = None
if "approved" not in st.session_state:
    st.session_state.approved = None
if "auto_loaded" not in st.session_state:
    latest = load_latest()
    if latest:
        st.session_state.current = latest
        if latest.get("status") in ["approved", "expanded"]:
            st.session_state.approved = latest
    st.session_state.auto_loaded = True

st.markdown(f"<div class='hero'><h1>{APP_TITLE}</h1><p>{APP_SUBTITLE}</p><p class='small'>카드뉴스는 텍스트 포함 이미지 프롬프트, 쇼츠/롱폼은 내레이션과 클린 이미지 프롬프트만 산출합니다.</p></div>", unsafe_allow_html=True)

menu = st.sidebar.radio("메뉴", ["카드뉴스 기획", "제작 확장", "히스토리"])
model = st.sidebar.selectbox("OpenAI 모델", ["gpt-4.1", "gpt-4.1-mini", "gpt-4o", "gpt-4o-mini"], 0)
research_model = st.sidebar.selectbox("리서치 모델", ["gpt-4.1", "gpt-4o"], 0)
min_score = st.sidebar.slider("업로드 가능 최소 점수", 0, 100, 85, 1)
max_rewrites = st.sidebar.slider("자동 개선 재시도", 0, 3, 2, 1)
card_count = st.sidebar.slider("카드 수", 5, 12, 8, 1)
ratio = st.sidebar.selectbox("비율", ["1:1 square card news", "9:16 vertical shorts", "4:5 Instagram feed", "16:9 YouTube wide"], 0)
research_mode = st.sidebar.selectbox("리서치 방식", ["웹 검색으로 출처 확인", "레퍼런스 내부 근거만 사용", "리서치 사용 안 함"], 0)

if menu == "카드뉴스 기획":
    left, right = st.columns([0.85, 1.15], gap="large")
    with left:
        st.subheader("입력")
        ref = st.text_area("레퍼런스", height=240)
        sources = st.text_area("사용자 제공 출처/링크/메모", height=80)
        direction = st.text_area("개선 방향 / 제작 디렉션 직접 입력", height=150, placeholder="생성 전부터 반영됩니다. 생성 후에는 이 칸에 수정 방향을 적고 재작성하세요.")
        topic = st.text_input("주제 덮어쓰기")
        platform = st.selectbox("플랫폼", ["AI가 판단", "Instagram 카드뉴스", "YouTube Shorts", "Instagram Reels", "TikTok", "혼합"])
        tone = st.selectbox("톤", ["커뮤니티 인기글형", "전문가 정보형", "자극적 후킹형", "다큐멘터리형", "광고 카피형"])
        run = st.button("리서치 + 추론 설계 + 카드뉴스 생성", type="primary", use_container_width=True)
        if st.session_state.current:
            st.divider()
            st.subheader("개선/컨펌")
            st.caption("점수가 부족해도 '현재 원고로 제작 확정'을 누르면 제작 확장 단계로 넘어갑니다.")
            if st.button("내 개선 방향으로 재작성", use_container_width=True):
                st.session_state.current = audit_loop(st.session_state.current, model, min_score, max_rewrites, direction)
                save_history(st.session_state.current)
                st.rerun()
            if st.button("자동 개선 다시 시도", use_container_width=True):
                st.session_state.current = audit_loop(st.session_state.current, model, min_score, max_rewrites, "")
                save_history(st.session_state.current)
                st.rerun()
            if st.button("현재 원고로 제작 확정", type="primary", use_container_width=True):
                pkg = clean_package(dict(st.session_state.current))
                pkg["status"] = "approved"
                pkg["approved_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                pkg.setdefault("approval_note", "사용자가 현재 원고로 제작 확정")
                st.session_state.approved = pkg
                st.session_state.current = pkg
                save_history(pkg)
                st.success("제작 확정 완료. 왼쪽 메뉴에서 제작 확장으로 이동하세요.")
        if st.button("Supabase 최신 저장본 불러오기", use_container_width=True):
            latest = load_latest()
            if latest:
                st.session_state.current = latest
                if latest.get("status") in ["approved", "expanded"]:
                    st.session_state.approved = latest
                st.rerun()
            else:
                st.warning("불러올 저장본이 없습니다.")
    if run:
        if not ref.strip():
            st.warning("레퍼런스를 입력하세요")
        else:
            progress = st.progress(0)
            msg = st.empty()
            msg.info("리서치 중")
            if research_mode == "웹 검색으로 출처 확인":
                research = web_research(f"사용자 출처:\n{sources}\n레퍼런스:\n{ref}", research_model)
            elif research_mode == "레퍼런스 내부 근거만 사용":
                research = llm(RESEARCH_SYSTEM, f"사용자 출처:\n{sources}\n레퍼런스:\n{ref}", model, 0.1)
            else:
                research = {"research_summary": "리서치 사용 안 함", "research_brief": [], "research_warnings": []}
            progress.progress(25)
            msg.info("추론 설계 중")
            blueprint_raw = llm(REASONING_SYSTEM, f"사용자 디렉션:\n{direction}\n카드 수:{card_count}\n톤:{tone}\n주제:{topic}\n리서치:{json.dumps(research, ensure_ascii=False)}\n레퍼런스:{ref}", model, 0.25)
            blueprint = blueprint_raw.get("reasoning_blueprint", blueprint_raw)
            progress.progress(50)
            msg.info("원고 생성 중")
            pkg = llm(CARD_SYSTEM, f"비율:{ratio}\n카드 수:{card_count}\n플랫폼:{platform}\n톤:{tone}\n주제:{topic}\n사용자 디렉션:{direction}\n리서치:{json.dumps(research, ensure_ascii=False)}\n추론 설계도:{json.dumps(blueprint, ensure_ascii=False)}\n레퍼런스:{ref}", model, 0.72)
            pkg["research_summary"] = research.get("research_summary", "")
            pkg["research_brief"] = research.get("research_brief", [])
            pkg["research_warnings"] = research.get("research_warnings", [])
            pkg["reasoning_blueprint"] = blueprint
            pkg["status"] = "draft"
            progress.progress(75)
            msg.info("심사 및 개선 중")
            pkg = audit_loop(pkg, model, min_score, max_rewrites, direction)
            pkg["created_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            pkg["reference_preview"] = ref[:300]
            pkg.setdefault("auto_brief", {}).setdefault("image_ratio", ratio)
            st.session_state.current = pkg
            save_history(pkg)
            progress.progress(100)
            msg.success("완료 및 자동 저장")
    with right:
        st.subheader("결과")
        render_package(st.session_state.current, min_score)

elif menu == "제작 확장":
    if not st.session_state.approved and st.session_state.current:
        st.session_state.approved = st.session_state.current
    if not st.session_state.approved:
        st.warning("먼저 카드뉴스 기획에서 '현재 원고로 제작 확정'을 눌러주세요.")
    else:
        left, right = st.columns([0.7, 1.3], gap="large")
        with left:
            st.subheader("제작 확장 옵션")
            make_card_images = st.checkbox("카드뉴스 이미지 프롬프트", True)
            make_shorts = st.checkbox("쇼츠 대본/클린 이미지", True)
            make_longform = st.checkbox("롱폼 대본/클린 이미지", True)
            make_titles = st.checkbox("제목/썸네일", True)
            style_direction = st.text_area("디자인 스타일 추가 지시", height=120, placeholder="예: 3안 중 하나는 세리프 헤드라인+산세리프 바디의 고급 매거진 스타일, 하나는 테크 다큐, 하나는 커뮤니티 밈에세이처럼.")
            if st.button("제작물 생성", type="primary", use_container_width=True):
                options = {
                    "make_card_images": make_card_images,
                    "make_shorts": make_shorts,
                    "make_longform": make_longform,
                    "make_titles": make_titles,
                    "image_ratio": ratio,
                    "style_direction": style_direction,
                }
                expansion = llm(EXPAND_SYSTEM, json.dumps({"options": options, "approved": st.session_state.approved}, ensure_ascii=False), model, 0.75)
                pkg = clean_package(dict(st.session_state.approved))
                pkg["status"] = "expanded"
                pkg["expanded_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                pkg["expansion"] = expansion
                st.session_state.approved = pkg
                st.session_state.current = pkg
                save_history(pkg)
                st.success("제작 확장 완료 및 자동 저장")
        with right:
            render_package(st.session_state.approved, min_score)

else:
    rows = load_history_meta(HISTORY_LIMIT)
    if not rows:
        st.info("히스토리가 없거나 Supabase 연결이 없습니다.")
    else:
        labels = [f"{i+1}. {row.get('created_at')} · {row.get('verdict')} · {row.get('topic')}" for i, row in enumerate(rows)]
        selected = st.selectbox("히스토리", labels)
        row = rows[labels.index(selected)]
        st.json(row)
        if st.button("상세 불러오기", use_container_width=True):
            item = load_history_item(row.get("id"))
            if item:
                st.session_state.current = item
                if item.get("status") in ["approved", "expanded"]:
                    st.session_state.approved = item
                st.rerun()
