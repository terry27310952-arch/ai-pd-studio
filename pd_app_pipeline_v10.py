import json
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

import streamlit as st
from openai import OpenAI
from supabase import create_client, Client

APP_TITLE = "AI PD Studio V10"
TABLE_NAME = "content_history"
GENERIC_PATTERNS = ["노력만으로는 부족하다", "현실은 다르다", "성공 공식", "행동해야 한다", "성장의 시작", "기회가 늘어난다", "특별한 능력보다"]
WEAK_PATTERNS = [r"role.*main", r"차이는 의외로 단순", r"경험할 수 있다", r"기회는 늘어난다"]

st.set_page_config(page_title=APP_TITLE, page_icon="🎬", layout="wide")
st.markdown("""
<style>
.main .block-container{max-width:1400px;padding-top:2rem}.box{padding:1rem;border:1px solid rgba(120,120,120,.2);border-radius:16px}.ok{background:rgba(80,200,120,.08)}.warn{background:rgba(255,80,80,.08)}
</style>
""", unsafe_allow_html=True)

RESEARCH_SYSTEM = """너는 카드뉴스용 팩트체크 리서처다. 확인된 출처만 confirmed로 표시한다. 불확실하면 needs_verification으로 둔다. JSON만 출력한다.
반환: {"research_summary":"", "research_brief":[{"id":"S1","claim":"","source_title":"","source_name":"","source_url":"","source_date":"","source_context":"","source_confidence":"confirmed|inferred|needs_verification","usable_in_card":true,"display_text":""}], "research_warnings":[]} """

REASONING_SYSTEM = """너는 카드뉴스 추론 설계자다. 좋은 말 모음이 아니라 논리 설계도를 만든다.
반드시 surface_topic, core_problem, non_obvious_insight, opposing_cliche, causal_mechanism, reader_self_diagnosis, claim_ladder, no_repeat_rules, card_arc를 만든다.
얕은 문장 금지: 행동해야 한다, 성장한다, 기회가 늘어난다, 실패는 성장 과정이다.
role은 main 금지. hook, cliche_break, mechanism, proof, reframe, contrast, self_test, close만 사용한다.
JSON만 출력한다."""

CARD_SYSTEM = """너는 카드뉴스 원고 PD다. reasoning_blueprint와 research_brief를 기준으로 카드뉴스 원고만 만든다.
규칙: headline은 주장형, body는 짧은 논리. 저장문장/save_point/save_line 금지. role=main 금지. 모든 장은 다른 논리 기능을 가져야 한다.
insight_device는 설득 장치, layout_hint는 이미지화 연출 메모다. confirmed 출처만 source_refs에 넣고 source_display를 만든다.
출처 없는 '연구에 따르면' 금지. JSON만 출력한다.
스키마: {"status":"draft","auto_brief":{"topic":"","image_ratio":""},"reasoning_blueprint":{},"research_brief":[],"card_news":[{"page":1,"role":"hook","headline":"","body":"","insight_device":"","layout_hint":"","source_refs":[],"source_display":""}],"quality_gate":{},"improvement_report":{}}"""

AUDIT_SYSTEM = """너는 업로드 전 심사위원이다. 0~100 정수로 1점 단위 채점한다. 10점 만점 금지.
85점 미만은 업로드 가능 불가. 반복, 얕은 조언, role=main, 미검증 출처 각주는 강하게 감점한다.
반환 JSON: {"verdict":"업로드 가능|수정 필요|폐기 후 재작성","scores":{"reasoning_score":0,"insight_score":0,"copy_score":0,"progression_score":0,"source_integrity_score":0,"risk_score":0,"upload_ready_score":0},"weak_lines":[],"critical_issues":[],"rewrite_actions":[],"upgrade_brief":""}"""

REWRITE_SYSTEM = """너는 카드뉴스 리라이트 디렉터다. 사용자 개선 방향을 최우선 반영한다. reasoning_blueprint를 다시 짜도 된다.
반복되는 주장 제거, role=main 금지, 얕은 조언을 원인/메커니즘/판단 기준으로 변경, confirmed 출처만 사용. JSON만 출력한다.
반환: {"revised_card_package":{},"improvement_report":{"why_failed":"","core_fix":"","user_direction_reflected":"","changed_lines":[]}}"""

EXPAND_SYSTEM = """컨펌된 카드뉴스를 이미지/쇼츠/롱폼으로 확장한다. 카드뉴스의 핵심 주장을 바꾸지 않는다. JSON만 출력한다."""

@st.cache_resource(show_spinner=False)
def oa(key: str) -> OpenAI:
    return OpenAI(api_key=key)

@st.cache_resource(show_spinner=False)
def sb(url: str, key: str) -> Client:
    return create_client(url, key)

def secret(name: str) -> str:
    try:
        return st.secrets.get(name, "") or os.getenv(name, "")
    except Exception:
        return os.getenv(name, "")

def client() -> OpenAI:
    key = secret("OPENAI_API_KEY")
    if not key:
        st.error("OPENAI_API_KEY가 없습니다."); st.stop()
    return oa(key)

def supabase() -> Optional[Client]:
    url = secret("SUPABASE_URL"); key = secret("SUPABASE_SERVICE_ROLE_KEY") or secret("SUPABASE_ANON_KEY")
    if not url or not key: return None
    try: return sb(url, key)
    except Exception: return None

def jload(text: str) -> Dict[str, Any]:
    text = (text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).strip(); text = re.sub(r"```$", "", text).strip()
    try: return json.loads(text)
    except Exception:
        m = re.search(r"\{.*\}", text, re.S)
        return json.loads(m.group(0)) if m else {}

def llm(sys: str, usr: str, model: str, temp: float) -> Dict[str, Any]:
    r = client().chat.completions.create(model=model, messages=[{"role":"system","content":sys},{"role":"user","content":usr}], temperature=temp, response_format={"type":"json_object"})
    return jload(r.choices[0].message.content or "{}")

def web_research(query: str, model: str) -> Dict[str, Any]:
    try:
        r = client().responses.create(model=model, tools=[{"type":"web_search_preview"}], input=[{"role":"system","content":RESEARCH_SYSTEM},{"role":"user","content":query}], text={"format":{"type":"json_object"}})
        return jload(getattr(r, "output_text", "") or "{}")
    except Exception as e:
        return {"research_summary":"웹 검색 실패", "research_brief":[], "research_warnings":[str(e)]}

def clean(p: Dict[str, Any]) -> Dict[str, Any]:
    for c in p.get("card_news", []) or []:
        c.pop("save_point", None); c.pop("save_line", None); c.setdefault("source_refs", []); c.setdefault("source_display", "")
        if "layout_type" in c and "layout_hint" not in c: c["layout_hint"] = c.pop("layout_type")
    return p

def confirmed_ids(p: Dict[str, Any]) -> set:
    return {x.get("id") for x in p.get("research_brief", []) or [] if x.get("source_confidence") == "confirmed" and x.get("usable_in_card") is True}

def local_gate(p: Dict[str, Any]) -> Dict[str, Any]:
    p = clean(p); text = "\n".join([str(c.get("headline", ""))+"\n"+str(c.get("body", "")) for c in p.get("card_news", []) or []])
    hits = []
    for ph in GENERIC_PATTERNS:
        if ph in text: hits.append({"line": ph, "reason": "얕거나 뻔한 문장", "fix_direction": "원인/메커니즘/판단 기준으로 변경"})
    for pat in WEAK_PATTERNS:
        if re.search(pat, text): hits.append({"line": pat, "reason": "약한 패턴", "fix_direction": "구체 주장으로 변경"})
    ids = confirmed_ids(p); roles = []
    for c in p.get("card_news", []) or []:
        roles.append(c.get("role", ""))
        if c.get("role") == "main": hits.append({"line": "role=main", "reason": "카드 역할이 뭉뚱그려짐", "fix_direction": "mechanism/proof/reframe 등으로 변경"})
        if not c.get("insight_device"): hits.append({"line": f"{c.get('page')}장 insight_device", "reason": "설득 장치 누락", "fix_direction": "설득 장치 추가"})
        if not c.get("layout_hint"): hits.append({"line": f"{c.get('page')}장 layout_hint", "reason": "이미지화 힌트 누락", "fix_direction": "시각화 메모 추가"})
        for ref in c.get("source_refs", []) or []:
            if ref not in ids: hits.append({"line": f"미검증 출처 {ref}", "reason": "confirmed가 아닌 출처", "fix_direction": "각주 제거 또는 confirmed로 교체"})
    if roles.count("main") >= 2: hits.append({"line":"main 반복", "reason":"논리 전진 약함", "fix_direction":"카드별 역할 분리"})
    return {"score": min(100, len(hits)*18), "hits": hits}

def merge_gate(audit: Dict[str, Any], p: Dict[str, Any]) -> Dict[str, Any]:
    scores = audit.get("scores", {}) or {}
    audit["scores"] = {k: max(0, min(100, int(round(float(v))))) if str(v).replace('.','',1).isdigit() else 0 for k, v in scores.items()}
    lg = local_gate(p); audit["scores"]["local_generic_score"] = lg["score"]; audit["local_weak_hits"] = lg["hits"]
    if lg["score"] > 0:
        audit["verdict"] = "수정 필요"; audit.setdefault("critical_issues", []).append("로컬 하드게이트 감점 요소 발견")
    return audit

def ready(p: Dict[str, Any], min_score: int) -> bool:
    g = p.get("quality_gate", {}) or {}; s = g.get("scores", {}) or {}
    return g.get("verdict") == "업로드 가능" and s.get("local_generic_score", 0) == 0 and int(s.get("upload_ready_score", 0) or 0) >= min_score

def audit_loop(p: Dict[str, Any], model: str, min_score: int, max_rewrites: int, direction: str) -> Dict[str, Any]:
    cur = clean(p); attempts = []
    for i in range(max_rewrites + 1):
        aud = llm(AUDIT_SYSTEM, json.dumps(cur, ensure_ascii=False), model, 0.15)
        gate = merge_gate(aud, cur); cur["quality_gate"] = gate
        attempts.append({"attempt": i, "verdict": gate.get("verdict"), "scores": gate.get("scores", {})})
        if ready(cur, min_score): break
        if i == max_rewrites: break
        prompt = f"사용자 개선 방향:\n{direction}\n기존 원고:\n{json.dumps(cur, ensure_ascii=False)}\n심사:\n{json.dumps(gate, ensure_ascii=False)}"
        rw = llm(REWRITE_SYSTEM, prompt, model, 0.35)
        cur = clean(rw.get("revised_card_package", cur)); cur["improvement_report"] = rw.get("improvement_report", {})
    cur.setdefault("improvement_report", {})["attempts"] = attempts
    return cur

def save(p: Dict[str, Any]) -> None:
    db = supabase()
    if not db: return
    b = p.get("auto_brief", {}) or {}; g = p.get("quality_gate", {}) or {}
    db.table(TABLE_NAME).insert({"topic": b.get("topic") or p.get("reasoning_blueprint", {}).get("surface_topic") or "무제", "verdict": f"{p.get('status','draft')} | {g.get('verdict','')}", "reference_preview": p.get("reference_preview", ""), "image_ratio": b.get("image_ratio", ""), "package": p}).execute()

def history(limit=20):
    db = supabase()
    if not db: return []
    try: return db.table(TABLE_NAME).select("id,created_at,topic,verdict,reference_preview,image_ratio").order("created_at", desc=True).limit(limit).execute().data or []
    except Exception: return []

def load_item(row_id: str):
    db = supabase()
    if not db: return None
    rows = db.table(TABLE_NAME).select("package").eq("id", row_id).limit(1).execute().data or []
    return clean(rows[0].get("package")) if rows else None

def rows_csv(p: Dict[str, Any]) -> str:
    rows = []
    for c in p.get("card_news", []) or []:
        rows.append({"type":"card_news", "index":c.get("page"), "headline":c.get("headline"), "body":c.get("body"), "role":c.get("role"), "insight_device":c.get("insight_device"), "layout_hint":c.get("layout_hint"), "source_display":c.get("source_display")})
    exp = p.get("expansion", {}) or {}
    for c in (exp.get("image_production", {}) or {}).get("cards", []) or []:
        rows.append({"type":"image_prompt", "index":c.get("page"), "headline":"", "body":c.get("korean_direction",""), "role":"", "insight_device":"", "layout_hint":c.get("layout_direction",""), "source_display":c.get("english_prompt","")})
    out = io.StringIO();
    if rows:
        w = csv.DictWriter(out, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    return out.getvalue()

def render(p: Dict[str, Any], min_score: int):
    g = p.get("quality_gate", {}) or {}; s = g.get("scores", {}) or {}; cls = "ok" if ready(p, min_score) else "warn"
    st.markdown(f"<div class='box {cls}'><b>상태:</b> {p.get('status','draft')} &nbsp; <b>판정:</b> {g.get('verdict','-')} &nbsp; <b>기준:</b> {min_score}/100</div>", unsafe_allow_html=True)
    cols = st.columns(5)
    for i, k in enumerate(["reasoning_score", "insight_score", "progression_score", "local_generic_score", "upload_ready_score"]): cols[i].metric(k, s.get(k, "-"))
    tabs = st.tabs(["카드뉴스", "추론 설계도", "리서치", "개선 리포트", "하드게이트", "확장", "CSV/JSON"])
    with tabs[0]:
        for i, c in enumerate(p.get("card_news", []) or [], 1):
            with st.expander(f"{c.get('page', i)}장 · {c.get('role','')} · {c.get('headline','')}", expanded=i<=2):
                st.markdown(f"**헤드라인**\n\n{c.get('headline','')}")
                st.markdown(f"**본문**\n\n{c.get('body','')}")
                st.markdown(f"**인사이트 장치**\n\n{c.get('insight_device','')}")
                st.markdown(f"**레이아웃 힌트**\n\n{c.get('layout_hint','')}")
                if c.get("source_display"): st.caption(c.get("source_display"))
    with tabs[1]: st.json(p.get("reasoning_blueprint", {}))
    with tabs[2]: st.json({"research_summary":p.get("research_summary",""), "research_brief":p.get("research_brief", []), "research_warnings":p.get("research_warnings", [])})
    with tabs[3]: st.json(p.get("improvement_report", {}))
    with tabs[4]: st.json(g)
    with tabs[5]: st.json(p.get("expansion", {}))
    with tabs[6]:
        st.download_button("CSV 다운로드", rows_csv(p), "ai_pd_studio_v10.csv", "text/csv")
        st.download_button("JSON 다운로드", json.dumps(p, ensure_ascii=False, indent=2), "ai_pd_studio_v10.json", "application/json")

if "current" not in st.session_state: st.session_state.current = None
if "approved" not in st.session_state: st.session_state.approved = None

st.markdown(f"<div class='hero-card'><h1>{APP_TITLE}</h1><p>{APP_SUBTITLE}</p></div>", unsafe_allow_html=True)
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
        direction = st.text_area("개선 방향 / 제작 디렉션 직접 입력", height=150, placeholder="생성 전부터 반영됩니다. 생성 후에는 이 칸에 수정 방향을 적고 '내 개선 방향으로 재작성'을 누르세요.")
        topic = st.text_input("주제 덮어쓰기")
        platform = st.selectbox("플랫폼", ["AI가 판단", "Instagram 카드뉴스", "YouTube Shorts", "Instagram Reels", "TikTok", "혼합"])
        tone = st.selectbox("톤", ["커뮤니티 인기글형", "전문가 정보형", "자극적 후킹형", "다큐멘터리형", "광고 카피형"])
        run = st.button("리서치 + 추론 설계 + 카드뉴스 생성", type="primary", use_container_width=True)
        if st.session_state.current:
            st.divider(); st.subheader("개선/컨펌")
            if st.button("내 개선 방향으로 재작성", use_container_width=True):
                st.session_state.current = audit_loop(st.session_state.current, model, min_score, max_rewrites, direction); save(st.session_state.current); st.rerun()
            if st.button("자동 개선 다시 시도", use_container_width=True):
                st.session_state.current = audit_loop(st.session_state.current, model, min_score, max_rewrites, ""); save(st.session_state.current); st.rerun()
            if st.button("이 카드뉴스 내용 컨펌", disabled=not ready(st.session_state.current, min_score), use_container_width=True):
                p = dict(st.session_state.current); p["status"] = "approved"; p["approved_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S"); st.session_state.approved = p; st.session_state.current = p; save(p); st.success("컨펌 완료")
    if run:
        if not ref.strip(): st.warning("레퍼런스를 입력하세요")
        else:
            prog = st.progress(0); msg = st.empty()
            msg.info("리서치 중")
            if research_mode == "웹 검색으로 출처 확인": research = web_research(f"사용자 출처:\n{sources}\n레퍼런스:\n{ref}", research_model)
            elif research_mode == "레퍼런스 내부 근거만 사용": research = llm(RESEARCH_SYSTEM, f"사용자 출처:\n{sources}\n레퍼런스:\n{ref}", model, 0.1)
            else: research = {"research_summary":"리서치 사용 안 함", "research_brief":[], "research_warnings":[]}
            prog.progress(25); msg.info("추론 설계 중")
            bp = llm(REASONING_SYSTEM, f"사용자 디렉션:\n{direction}\n카드 수:{card_count}\n톤:{tone}\n주제:{topic}\n리서치:{json.dumps(research, ensure_ascii=False)}\n레퍼런스:{ref}", model, 0.25)
            blueprint = bp.get("reasoning_blueprint", bp)
            prog.progress(50); msg.info("원고 생성 중")
            p = llm(CARD_SYSTEM, f"비율:{ratio}\n카드 수:{card_count}\n플랫폼:{platform}\n톤:{tone}\n주제:{topic}\n사용자 디렉션:{direction}\n리서치:{json.dumps(research, ensure_ascii=False)}\n추론 설계도:{json.dumps(blueprint, ensure_ascii=False)}\n레퍼런스:{ref}", model, 0.72)
            p["research_summary"] = research.get("research_summary", ""); p["research_brief"] = research.get("research_brief", []); p["research_warnings"] = research.get("research_warnings", []); p["reasoning_blueprint"] = blueprint; p["status"] = "draft"
            prog.progress(75); msg.info("심사 및 개선 중")
            p = audit_loop(p, model, min_score, max_rewrites, direction); p["created_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S"); p["reference_preview"] = ref[:300]; p.setdefault("auto_brief", {}).setdefault("image_ratio", ratio)
            st.session_state.current = p; save(p); prog.progress(100); msg.success("완료")
    with right:
        st.subheader("결과")
        render(st.session_state.current, min_score) if st.session_state.current else st.info("생성 결과가 여기에 표시됩니다.")

elif menu == "제작 확장":
    if not st.session_state.approved: st.warning("먼저 카드뉴스를 컨펌하세요.")
    else:
        make_images = st.checkbox("이미지 프롬프트", True); make_shorts = st.checkbox("쇼츠", True); make_longform = st.checkbox("롱폼", False); make_titles = st.checkbox("제목/썸네일", True)
        if st.button("제작물 생성", type="primary"):
            opts = {"make_images":make_images,"make_shorts":make_shorts,"make_longform":make_longform,"make_titles":make_titles,"image_ratio":ratio}
            exp = llm(EXPAND_SYSTEM, json.dumps({"options":opts,"approved":st.session_state.approved}, ensure_ascii=False), model, 0.75)
            p = dict(st.session_state.approved); p["status"] = "expanded"; p["expansion"] = exp; st.session_state.approved = p; st.session_state.current = p; save(p); st.success("제작 확장 완료")
        render(st.session_state.approved, min_score)

else:
    rows = history(HISTORY_LIMIT)
    if not rows: st.info("히스토리가 없습니다.")
    else:
        labels = [f"{i+1}. {r.get('created_at')} · {r.get('verdict')} · {r.get('topic')}" for i, r in enumerate(rows)]
        sel = st.selectbox("히스토리", labels); row = rows[labels.index(sel)]
        if st.button("상세 불러오기"):
            item = load_item(row.get("id")); st.session_state.current = item
            if item and item.get("status") in ["approved", "expanded"]: st.session_state.approved = item
            st.rerun()
