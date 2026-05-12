import csv
import io
import os
import runpy

import streamlit as st

APP_SUBTITLE = "상시 디렉션 입력 · 추론 설계도 · 리서치 출처 · 카드뉴스 컨펌 후 확장"

_original_button = st.button


def _button_with_manual_confirm(label, *args, **kwargs):
    if label == "이 카드뉴스 내용 컨펌" and kwargs.get("disabled") is True:
        kwargs["disabled"] = False
        label = "현재 원고로 제작 확정"
        kwargs.setdefault("type", "primary")
        help_text = kwargs.get("help")
        kwargs["help"] = help_text or "품질 게이트가 수정 필요이어도 사용자가 현재 원고를 기준으로 제작 확정합니다."
    return _original_button(label, *args, **kwargs)


st.button = _button_with_manual_confirm

runpy.run_path(
    os.path.join(os.path.dirname(__file__), "pd_app_pipeline_v10.py"),
    init_globals={"APP_SUBTITLE": APP_SUBTITLE, "csv": csv, "io": io},
)
