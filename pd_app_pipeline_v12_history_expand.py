import os

SOURCE_FILE = os.path.join(os.path.dirname(__file__), "pd_app_pipeline_v12_ref.py")
with open(SOURCE_FILE, "r", encoding="utf-8") as f:
    source = f.read()

source = source.replace(
    'if st.button("상세 불러오기", use_container_width=True):\n            item = load_history_item(row.get("id"))\n            if item:\n                st.session_state.current = item\n                if item.get("status") in ["approved", "expanded"]:\n                    st.session_state.approved = item\n                st.rerun()',
    '''col_h1, col_h2 = st.columns(2)
        with col_h1:
            if st.button("상세 불러오기", use_container_width=True):
                item = load_history_item(row.get("id"))
                if item:
                    st.session_state.current = item
                    if item.get("status") in ["approved", "expanded"]:
                        st.session_state.approved = item
                    st.rerun()
        with col_h2:
            if st.button("이 히스토리로 제작 확장", type="primary", use_container_width=True):
                item = load_history_item(row.get("id"))
                if item:
                    item = clean_package(item)
                    item["status"] = "approved"
                    item["approved_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    item.setdefault("approval_note", "히스토리에서 제작 확정")
                    st.session_state.current = item
                    st.session_state.approved = item
                    save_history(item)
                    st.session_state.menu_target = "제작 확장"
                    st.success("이 히스토리를 제작 확장 대상으로 설정했습니다. 왼쪽 메뉴에서 제작 확장으로 이동하세요.")'''
)

source = source.replace(
    'menu = st.sidebar.radio("메뉴", ["카드뉴스 기획", "제작 확장", "히스토리"])',
    'default_menu_index = 1 if st.session_state.get("menu_target") == "제작 확장" else 0\nmenu = st.sidebar.radio("메뉴", ["카드뉴스 기획", "제작 확장", "히스토리"], index=default_menu_index)\nst.session_state.menu_target = None'
)

exec(compile(source, SOURCE_FILE, "exec"), globals())
