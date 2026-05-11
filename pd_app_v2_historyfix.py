import csv
import io
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import streamlit as st
from openai import OpenAI

APP_TITLE = "AI PD Studio V2"
APP_SUBTITLE = "관점·착각 파괴·업로드 가능 점수까지 강제하는 카드뉴스/쇼츠 생성 엔진"
HISTORY_FILE = Path("history_store_v2.json")
LEGACY_HISTORY_FILES = [Path("history_store.json"), Path("history_store_v2.json")]
MAX_HISTORY = 100

st.set_page_config(page_title=APP_TITLE, page_icon="🎬", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
.main .block-container { padding-top: 2rem; max-width: 1400px; }
.hero-card { padding: 1.35rem 1.5rem; border: 1px solid rgba(120,120,120,.18); border-radius: 22px; background: linear-gradient(135deg, rgba(120,120,255,.14), rgba(255,255,255,.03)); }
.small-muted { color: #888; font-size: .92rem; }
</style>
""", unsafe_allow_html=True)

ANGLE_BOARD_SYSTEM = """
너는 콘텐츠 편집장이다. 레퍼런스를 받아서 바로 대본을 쓰지 말고, 먼저 업로드 가능한 관점을 설계한다.
목표는 정보 정리가 아니라 시청자가 멈추고, 저장하고, 댓글을 달게 만드는 관점 설계다.

반드시 찾아라.
1. 이 콘텐츠가 깨야 하는 독자의 착각
2. 그 착각을 깨는 반박 주장
3. 댓글이 갈릴 논쟁 지점
4. 저장/공유가 생기는 이유
5. 반드시 써야 하는 구체 숫자/고유명사/사례
6. 확인이 필요한 정보
7. 카드뉴스 감정 순서
8. 쇼츠 감정 순서
9. 업로드 불가 요소

죽은 표현 금지: 중요합니다, 살펴보겠습니다, 주목받고 있습니다, 영향이 있습니다, 신중한 접근, 미래가 기대됩니다, 첫걸음, 성공 공식.
반드시 JSON만 출력한다.
"""

DRAFT_SYSTEM = """
너는 카드뉴스와 1분 쇼츠를 동시에 설계하는 실무형 콘텐츠 PD다.
ANGLE BOARD를 기반으로 초안을 만든다.
단, 정보 나열 금지. 반드시 착각 파괴 → 증거 → 문제의 본질 → 반전/해석 → 행동 유도로 구성한다.

카드뉴스 규칙:
- 첫 장은 독자 착각을 찌르는 문장.
- 각 장은 한 감정만 담당한다.
- headline은 20자 내외, body는 2~3문장 이내.
- 저장하고 싶은 문장 key_caption을 반드시 만든다.

쇼츠 규칙:
- 0~3초는 질문보다 강한 주장/반전 우선.
- 7~9컷, 각 컷 내레이션은 짧게.
- 숫자/고유명사/구체 장면을 매 컷에 최대한 넣는다.
- visual은 아이콘/다이어그램이 아니라 실제 장면/오브젝트/스크린/인물/사건.
- video_prompt는 영어, 카메라 무빙으로 시작.

반드시 JSON만 출력한다.
"""

CARDNEWS_DOCTOR_SYSTEM = """
너는 한국 커뮤니티 인기글 감각을 가진 카드뉴스 전문 편집자다.
card_news만 재작성한다.
목표는 예쁜 요약본이 아니라 저장/공유가 생기는 카드뉴스다.

강제 기준:
- 헤드라인은 독자의 변명, 불안, 욕망, 자기합리화를 찔러야 한다.
- 각 장의 첫 문장은 주장 또는 반박이어야 한다.
- 추상어 대신 구체 장면, 숫자, 오브젝트를 넣는다.
- '대단하다/놀랍다/중요하다/필요하다' 제거.
- 마지막 장은 감성적 행동 유도. 흔한 구독/댓글 구걸 금지.

반환은 card_news와 quality_patch만 담은 JSON.
"""

SHORTS_DOCTOR_SYSTEM = """
너는 1분 쇼츠 리텐션 작가다. one_minute_shorts만 재작성한다.
목표는 정보 전달이 아니라 시청 지속이다.

강제 기준:
- 첫 3초에 착각을 깨라.
- 컷마다 긴장도가 올라가야 한다.
- '성공일까 실패일까?' 같은 느슨한 질문 금지.
- 마지막은 관점 있는 결론으로 끝내고, 댓글 유도는 논쟁 포인트로 한다.
- visual은 실제로 보이는 사건 중심.
- video_prompt는 영어, 카메라 무빙으로 시작.

반환은 one_minute_shorts와 quality_patch만 담은 JSON.
"""

QUALITY_GATE_SYSTEM = """
너는 업로드 전 최종 심사위원이자 재작성 편집자다.
입력된 패키지를 평가하고, 업로드 가능 여부를 결정한다.

점수 기준:
- hook_score: 첫 3초/첫 장의 멈춤력
- claim_score: 한 줄 주장의 선명도
- specificity_score: 숫자/고유명사/구체 장면 밀도
- retention_score: 쇼츠 컷 간 긴장 상승
- save_score: 카드뉴스 저장/공유 욕구
- scene_score: 이미지/영상 제작 가능성
- upload_ready_score: 바로 업로드 가능성

verdict는 반드시 셋 중 하나:
- 업로드 가능
- 수정 필요
- 폐기 후 재작성

upload_ready_score가 85 미만이면 final_package를 직접 재작성한 버전으로 반환한다.
반드시 JSON만 출력한다.
"""

PACKAGE_SCHEMA = {
    "auto_brief": {"topic":"", "target":"", "platform":"", "tone":"", "goal":"", "cta":"", "image_ratio":"", "risk_notes":[]},
    "angle_board": {"misconception":"", "counter_claim":"", "core_claim":"", "comment_trigger":"", "save_reason":"", "evidence_bank":[], "needs_verification":[], "card_emotion_order":[], "shorts_emotion_order":[], "upload_risks":[]},
    "one_minute_shorts": {"title":"", "core_claim":"", "scenes":[{"time":"", "narration":"", "caption":"", "visual":"", "edit_point":"", "image_prompt":{"korean_direction":"", "english_prompt":"", "negative_prompt":""}, "video_prompt":{"korean_direction":"", "english_prompt":""}}]},
    "card_news": [{"page":1, "emotion_role":"", "headline":"", "body":"", "key_caption":"", "design_mood":"", "image_direction":"", "image_prompt_en":""}],
    "thumbnail_copy": [], "titles": [], "hashtags": [], "production_checklist": []
}


def normalize_history_item(item: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(item, dict):
        return {}
    item.setdefault("generated_at", item.get("created_at", "unknown"))
    item.setdefault("auto_brief", item.get("auto_inputs", {}))
    if "final_output" in item and isinstance(item["final_output"], dict):
        final_output = item["final_output"]
        item.setdefault("one_minute_shorts", final_output.get("one_minute_shorts", {}))
        item.setdefault("card_news", final_output.get("card_news", []))
        item.setdefault("thumbnail_copy", final_output.get("thumbnail_copy", []))
        item.setdefault("titles", final_output.get("titles", []))
        item.setdefault("hashtags", final_output.get("hashtags", []))
    return item


def item_key(item: Dict[str, Any]) -> str:
    brief = item.get("auto_brief", {}) or {}
    return f"{item.get('generated_at','')}|{brief.get('topic','')}|{item.get('reference_preview','')}"


def read_history_file(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(raw, list):
            return [normalize_history_item(x) for x in raw if isinstance(x, dict)]
        if isinstance(raw, dict):
            return [normalize_history_item(raw)]
    except Exception:
        return []
    return []


def load_history() -> List[Dict[str, Any]]:
    merged: List[Dict[str, Any]] = []
    seen = set()
    for path in LEGACY_HISTORY_FILES:
        for item in read_history_file(path):
            key = item_key(item)
            if key not in seen:
                seen.add(key)
                merged.append(item)
    return merged[:MAX_HISTORY]


def save_history(history: List[Dict[str, Any]]) -> None:
    try:
        HISTORY_FILE.write_text(json.dumps(history[:MAX_HISTORY], ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as exc:
        st.warning(f"히스토리 저장 실패: {exc}")


def add_to_history(package: Dict[str, Any]) -> None:
    history = st.session_state.history
    history.insert(0, package)
    deduped = []
    seen = set()
    for item in history:
        key = item_key(item)
        if key not in seen:
            seen.add(key)
            deduped.append(item)
    st.session_state.history = deduped[:MAX_HISTORY]
    save_history(st.session_state.history)


def import_history_items(uploaded_file) -> int:
    try:
        content = uploaded_file.read().decode("utf-8-sig")
        data = json.loads(content)
        items = data if isinstance(data, list) else [data]
        imported = 0
        for item in items:
            if isinstance(item, dict):
                add_to_history(normalize_history_item(item))
                imported += 1
        return imported
    except Exception as exc:
        st.error(f"JSON 히스토리 가져오기 실패: {exc}")
        return 0


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
        messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
        temperature=temperature,
        response_format={"type": "json_object"},
    )
    return extract_json(res.choices[0].message.content or "{}")


def build_angle_prompt(reference_text: str, output_language: str, image_ratio: str, card_count: int, platform_hint: str, tone_hint: str, override_topic: str) -> str:
    return f"""
레퍼런스를 분석해서 ANGLE BOARD를 만들어라.

사용자 설정:
- 출력 언어: {output_language}
- 이미지/영상 비율: {image_ratio}
- 카드뉴스 장수: {card_count}
- 플랫폼 힌트: {platform_hint}
- 톤 힌트: {tone_hint}
- 주제 덮어쓰기: {override_topic}

출력 JSON 형식:
{{
  "auto_brief": {{"topic":"", "target":"", "platform":"", "tone":"", "goal":"", "cta":"", "image_ratio":"{image_ratio}", "risk_notes":[]}},
  "angle_board": {{
    "misconception":"독자가 가진 착각",
    "counter_claim":"착각을 깨는 반박",
    "core_claim":"콘텐츠 전체 한 줄 주장",
    "comment_trigger":"댓글이 갈릴 논쟁 지점",
    "save_reason":"저장/공유가 생기는 이유",
    "evidence_bank":["숫자/고유명사/사례"],
    "needs_verification":["확인 필요한 정보"],
    "card_emotion_order":["1장 감정", "2장 감정"],
    "shorts_emotion_order":["0-3초 감정", "4-10초 감정"],
    "upload_risks":["업로드 전 조심할 점"]
  }}
}}

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
카드뉴스 장수: {card_count}
이미지 비율: {image_ratio}
반환 JSON 형식:
{{"card_news":[{{"page":1,"emotion_role":"","headline":"","body":"","key_caption":"","design_mood":"","image_direction":"","image_prompt_en":""}}], "quality_patch":{{"cardnews_rewrite_reason":[], "cardnews_hook_score":0, "cardnews_save_score":0}}}}

패키지:
{json.dumps(package, ensure_ascii=False, indent=2)}
"""


def build_shorts_doctor_prompt(package: Dict[str, Any], image_ratio: str) -> str:
    return f"""
이 패키지의 one_minute_shorts만 업로드 가능한 수준으로 재작성해라.
이미지/영상 비율: {image_ratio}
반환 JSON 형식:
{{"one_minute_shorts":{{"title":"", "core_claim":"", "scenes":[{{"time":"0-3초", "narration":"", "caption":"", "visual":"", "edit_point":"", "image_prompt":{{"korean_direction":"", "english_prompt":"", "negative_prompt":"text, watermark, logo"}}, "video_prompt":{{"korean_direction":"", "english_prompt":""}}}}]}}, "quality_patch":{{"shorts_rewrite_reason":[], "shorts_hook_score":0, "shorts_retention_score":0}}}}

패키지:
{json.dumps(package, ensure_ascii=False, indent=2)}
"""


def build_quality_prompt(package: Dict[str, Any]) -> str:
    return f"""
이 콘텐츠 패키지를 심사하고, 85점 미만이면 final_package를 직접 개선해 반환해라.

반환 JSON 형식:
{{
  "verdict":"업로드 가능 | 수정 필요 | 폐기 후 재작성",
  "scores":{{"hook_score":0, "claim_score":0, "specificity_score":0, "retention_score":0, "save_score":0, "scene_score":0, "upload_ready_score":0}},
  "critical_issues":[],
  "rewrite_actions":[],
  "final_package": {{}}
}}

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


def package_to_rows(package: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    brief = package.get("auto_brief", {}) or {}
    shorts = package.get("one_minute_shorts", {}) or {}
    for idx, scene in enumerate(shorts.get("scenes", []) or [], 1):
        rows.append({
            "type": "shorts_scene",
            "index": idx,
            "title": shorts.get("title", ""),
            "core_claim": shorts.get("core_claim", ""),
            "time": scene.get("time", ""),
            "headline_or_caption": scene.get("caption", ""),
            "body_or_narration": scene.get("narration", ""),
            "visual": scene.get("visual", ""),
            "edit_point": scene.get("edit_point", ""),
            "image_prompt": json.dumps(scene.get("image_prompt", {}), ensure_ascii=False),
            "video_prompt": json.dumps(scene.get("video_prompt", {}), ensure_ascii=False),
            "image_ratio": brief.get("image_ratio", ""),
        })
    for idx, card in enumerate(package.get("card_news", []) or [], 1):
        rows.append({
            "type": "card_news",
            "index": card.get("page", idx),
            "title": "",
            "core_claim": package.get("angle_board", {}).get("core_claim", ""),
            "time": "",
            "headline_or_caption": card.get("headline", ""),
            "body_or_narration": card.get("body", ""),
            "visual": card.get("image_direction", ""),
            "edit_point": card.get("design_mood", ""),
            "image_prompt": card.get("image_prompt_en", ""),
            "video_prompt": "",
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


def stringify(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def render_package(package: Dict[str, Any]) -> None:
    gate = package.get("quality_gate", {}) or {}
    scores = gate.get("scores", {}) or {}
    verdict = gate.get("verdict", "")
    if verdict:
        st.markdown(f"### 업로드 판정: {verdict}")
        cols = st.columns(4)
        for idx, key in enumerate(["hook_score", "claim_score", "specificity_score", "upload_ready_score"]):
            with cols[idx % 4]:
                st.metric(key, scores.get(key, "-"))

    tabs = st.tabs(["자동 브리프", "관점 보드", "쇼츠", "카드뉴스", "프롬프트", "제목/CTA", "CSV/JSON", "품질 심사"])
    with tabs[0]:
        st.json(package.get("auto_brief", {}))
    with tabs[1]:
        st.json(package.get("angle_board", {}))
    with tabs[2]:
        shorts = package.get("one_minute_shorts", {}) or {}
        st.markdown(f"### {shorts.get('title', '쇼츠 대본')}")
        st.markdown(f"**핵심 주장**: {shorts.get('core_claim', '')}")
        for i, scene in enumerate(shorts.get("scenes", []) or [], 1):
            with st.expander(f"컷 {i} · {scene.get('time', '')}", expanded=i <= 2):
                st.markdown(f"**내레이션**\n\n{scene.get('narration','')}")
                st.markdown(f"**자막**\n\n{scene.get('caption','')}")
                st.markdown(f"**화면**\n\n{scene.get('visual','')}")
                st.markdown(f"**편집 포인트**\n\n{scene.get('edit_point','')}")
                st.text_area("이미지 프롬프트", stringify(scene.get("image_prompt", {})), height=150, key=f"img_{i}_{id(scene)}")
                st.text_area("영상 프롬프트", stringify(scene.get("video_prompt", {})), height=150, key=f"vid_{i}_{id(scene)}")
    with tabs[3]:
        for i, card in enumerate(package.get("card_news", []) or [], 1):
            with st.expander(f"{card.get('page', i)}장 · {card.get('headline','')}", expanded=i <= 2):
                st.markdown(f"**감정 역할**: {card.get('emotion_role','')}")
                st.markdown(f"**헤드라인**\n\n{card.get('headline','')}")
                st.markdown(f"**본문**\n\n{card.get('body','')}")
                st.markdown(f"**저장 문장**\n\n{card.get('key_caption','')}")
                st.markdown(f"**디자인 톤**\n\n{card.get('design_mood','')}")
                st.markdown(f"**이미지 방향**\n\n{card.get('image_direction','')}")
                st.text_area("이미지 프롬프트 EN", card.get("image_prompt_en", ""), height=120, key=f"card_{i}_{id(card)}")
    with tabs[4]:
        lines = []
        for i, scene in enumerate((package.get("one_minute_shorts", {}) or {}).get("scenes", []) or [], 1):
            lines.append(f"컷 {i} 이미지\n{stringify(scene.get('image_prompt', {}))}\n")
            lines.append(f"컷 {i} 영상\n{stringify(scene.get('video_prompt', {}))}\n")
        for i, card in enumerate(package.get("card_news", []) or [], 1):
            lines.append(f"카드 {i} 이미지\n{card.get('image_prompt_en', '')}\n")
        st.text_area("전체 프롬프트", "\n".join(lines), height=520)
    with tabs[5]:
        st.write("썸네일", package.get("thumbnail_copy", []))
        st.write("제목", package.get("titles", []))
        st.write("해시태그", " ".join(package.get("hashtags", [])))
        st.write("체크리스트", package.get("production_checklist", []))
    with tabs[6]:
        csv_text = to_csv(package_to_rows(package))
        json_text = stringify(package)
        st.download_button("CSV 다운로드", csv_text, file_name="ai_pd_studio_v2_content.csv", mime="text/csv", use_container_width=True)
        st.download_button("JSON 다운로드", json_text, file_name="ai_pd_studio_v2_output.json", mime="application/json", use_container_width=True)
        st.text_area("CSV 미리보기", csv_text, height=260)
    with tabs[7]:
        st.json(gate)


def render_history() -> None:
    st.subheader("히스토리")
    st.caption("기존 history_store.json과 V2 history_store_v2.json을 함께 읽어 자동 병합합니다. 그래도 안 보이면 기존 앱 서버가 달라진 상태일 수 있습니다.")
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("히스토리 다시 불러오기", use_container_width=True):
            st.session_state.history = load_history()
            save_history(st.session_state.history)
            st.rerun()
    with col2:
        if st.button("기존 히스토리 병합 저장", use_container_width=True):
            st.session_state.history = load_history()
            save_history(st.session_state.history)
            st.success(f"{len(st.session_state.history)}개 히스토리를 병합 저장했습니다.")
    with col3:
        if st.button("히스토리 전체 삭제", use_container_width=True):
            st.session_state.history = []
            save_history([])
            st.rerun()

    uploaded = st.file_uploader("JSON 히스토리 파일 가져오기", type=["json"])
    if uploaded is not None:
        count = import_history_items(uploaded)
        if count:
            st.success(f"{count}개 항목을 가져왔습니다.")
            st.rerun()

    if not st.session_state.history:
        st.info("아직 히스토리가 없습니다. 기존 앱과 서버가 달라졌다면 이전 서버의 파일 저장소에만 남아 있을 수 있습니다.")
        return
    labels = []
    for idx, item in enumerate(st.session_state.history):
        brief = item.get("auto_brief", {}) or {}
        verdict = (item.get("quality_gate", {}) or {}).get("verdict", "")
        labels.append(f"{idx+1}. {item.get('generated_at','')} · {verdict} · {brief.get('topic','무제')}")
    selected = st.selectbox("생성 히스토리", labels)
    item = st.session_state.history[labels.index(selected)]
    if st.button("현재 결과로 불러오기", use_container_width=True):
        st.session_state.package = item
        st.session_state.menu = "콘텐츠 생성"
        st.rerun()
    st.json({"generated_at": item.get("generated_at"), "auto_brief": item.get("auto_brief", {}), "quality_gate": item.get("quality_gate", {})})
    st.download_button("전체 히스토리 JSON 다운로드", stringify(st.session_state.history), file_name="all_history.json", mime="application/json", use_container_width=True)
    st.download_button("선택 JSON 다운로드", stringify(item), file_name="history_item.json", mime="application/json", use_container_width=True)
    st.download_button("선택 CSV 다운로드", to_csv(package_to_rows(item)), file_name="history_item.csv", mime="text/csv", use_container_width=True)


if "history" not in st.session_state:
    st.session_state.history = load_history()
    if st.session_state.history:
        save_history(st.session_state.history)
if "package" not in st.session_state:
    st.session_state.package = st.session_state.history[0] if st.session_state.history else None
if "menu" not in st.session_state:
    st.session_state.menu = "콘텐츠 생성"

st.markdown(f"""<div class='hero-card'><h1>{APP_TITLE}</h1><p>{APP_SUBTITLE}</p><p class='small-muted'>V2 히스토리 복구 버전. 기존 히스토리 파일까지 자동으로 같이 찾습니다.</p></div>""", unsafe_allow_html=True)

st.sidebar.header("메인 메뉴")
menu = st.sidebar.radio("이동", ["콘텐츠 생성", "히스토리"], key="menu")
st.sidebar.header("⚙️ 생성 설정")
model = st.sidebar.selectbox("OpenAI 모델", ["gpt-4.1", "gpt-4.1-mini", "gpt-4o", "gpt-4o-mini"], index=0)
temperature = st.sidebar.slider("창의성", 0.1, 1.2, 0.85, 0.05)
output_language = st.sidebar.selectbox("출력 언어", ["한국어", "영어", "한국어+영어"], index=0)
image_ratio = st.sidebar.selectbox("이미지/영상 비율", ["9:16 vertical shorts", "1:1 square card news", "4:5 Instagram feed", "16:9 YouTube wide", "3:4 portrait"], index=0)
card_count = st.sidebar.slider("카드뉴스 장수", 5, 12, 8)
with st.sidebar.expander("Streamlit Secrets 안내"):
    st.code('OPENAI_API_KEY = "sk-..."', language="toml")

st.divider()

if menu == "히스토리":
    render_history()
else:
    left, right = st.columns([0.84, 1.16], gap="large")
    with left:
        st.subheader("1. 레퍼런스 입력")
        reference_text = st.text_area("레퍼런스 텍스트 / CSV 내용 / 대본 / 카드뉴스 문구", height=430, placeholder="여기에 레퍼런스를 붙여넣으세요. 착각, 반박, 논쟁 포인트를 먼저 뽑습니다.")
        with st.expander("선택 입력"):
            override_topic = st.text_input("주제 덮어쓰기", placeholder="비워두면 자동 추론")
            platform_hint = st.selectbox("플랫폼 힌트", ["AI가 판단", "YouTube Shorts", "Instagram Reels", "TikTok", "카드뉴스", "혼합"], index=0)
            tone_hint = st.selectbox("톤 힌트", ["커뮤니티 인기글형", "전문가 정보형", "자극적 후킹형", "다큐멘터리형", "광고 카피형"], index=0)
        run_button = st.button("업로드 가능 콘텐츠 생성", type="primary", use_container_width=True)

    if run_button:
        if not reference_text.strip():
            st.warning("레퍼런스를 먼저 입력해주세요.")
        else:
            progress = st.progress(0)
            status = st.empty()
            status.info("1/5 관점 보드 생성 중: 착각 → 반박 → 논쟁 → 저장 이유")
            angle_data = call_llm(ANGLE_BOARD_SYSTEM, build_angle_prompt(reference_text, output_language, image_ratio, card_count, platform_hint, tone_hint, override_topic), model, 0.35)
            progress.progress(20)

            status.info("2/5 전체 초안 생성 중")
            package = call_llm(DRAFT_SYSTEM, build_draft_prompt(angle_data, card_count, image_ratio), model, temperature)
            package["auto_brief"] = angle_data.get("auto_brief", package.get("auto_brief", {}))
            package["angle_board"] = angle_data.get("angle_board", package.get("angle_board", {}))
            progress.progress(42)

            status.info("3/5 카드뉴스 닥터: 저장형 문장으로 재작성")
            card_patch = call_llm(CARDNEWS_DOCTOR_SYSTEM, build_card_doctor_prompt(package, card_count, image_ratio), model, min(1.0, temperature + 0.05))
            progress.progress(62)

            status.info("4/5 쇼츠 닥터: 리텐션 구조로 재작성")
            shorts_patch = call_llm(SHORTS_DOCTOR_SYSTEM, build_shorts_doctor_prompt(package, image_ratio), model, min(1.0, temperature + 0.05))
            package = merge_doctors(package, card_patch, shorts_patch)
            progress.progress(82)

            status.info("5/5 업로드 가능 점수 심사 및 자동 개선")
            gate = call_llm(QUALITY_GATE_SYSTEM, build_quality_prompt(package), model, 0.25)
            final_package = gate.get("final_package") if isinstance(gate.get("final_package"), dict) and gate.get("final_package") else package
            final_package["quality_gate"] = {k: v for k, v in gate.items() if k != "final_package"}
            final_package["generated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            final_package["reference_preview"] = reference_text[:300]
            final_package.setdefault("auto_brief", {}).setdefault("image_ratio", image_ratio)
            st.session_state.package = final_package
            add_to_history(final_package)
            progress.progress(100)
            status.success("생성 완료. 히스토리는 좌측 메뉴에서 확인할 수 있습니다.")

    with right:
        st.subheader("2. 결과")
        if not st.session_state.package:
            st.info("레퍼런스를 입력하고 생성하면 결과가 여기에 표시됩니다.")
        else:
            render_package(st.session_state.package)
