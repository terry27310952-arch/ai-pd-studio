import os
import runpy

APP_SUBTITLE = "상시 디렉션 입력 · 추론 설계도 · 리서치 출처 · 카드뉴스 컨펌 후 확장"

runpy.run_path(
    os.path.join(os.path.dirname(__file__), "pd_app_pipeline_v10.py"),
    init_globals={"APP_SUBTITLE": APP_SUBTITLE},
)
