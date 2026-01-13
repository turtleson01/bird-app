import streamlit as st
import pandas as pd
import os

# 파일 이름 설정
DATA_FILE = "data.csv"
SAVE_FILE = "my_birds.txt"
MEMO_FILE = "memo.txt"

@st.cache_data
def load_data():
    if not os.path.exists(DATA_FILE):
        return None, None, None
    encodings = ['utf-8-sig', 'cp949', 'euc-kr']
    for enc in encodings:
        try:
            df = pd.read_csv(DATA_FILE, skiprows=2, encoding=enc)
            bird_data = df.iloc[:, [4, 14]].dropna()
            bird_data.columns = ['name', 'family_kor']
            bird_data['name'] = bird_data['name'].str.strip()
            bird_data['family_kor'] = bird_data['family_kor'].str.strip()
            bird_list = bird_data['name'].tolist()
            bird_order_map = {name: i for i, name in enumerate(bird_list)}
            families_in_order = bird_data['family_kor'].unique()
            family_group = {f_name: bird_data[bird_data['family_kor'] == f_name]['name'].tolist() for f_name in families_in_order}
            return bird_list, bird_order_map, family_group
        except Exception: continue
    return None, None, None

def load_list(file_path):
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            return [line.strip() for line in f.readlines() if line.strip()]
    return []

def save_list(file_path, items):
    with open(file_path, "w", encoding="utf-8") as f:
        for item in items: f.write(f"{item}\n")

st.set_page_config(page_title="나의 조류 도감", layout="wide")
birds, bird_order_map, family_group = load_data()

if birds is None:
    st.error("❌ 'data.csv' 파일을 찾을 수 없습니다.")
else:
    if 'found' not in st.session_state:
        st.session_state.found = load_list(SAVE_FILE)
    if 'memo' not in st.session_state:
        memo_content = load_list(MEMO_FILE)
        st.session_state.memo = "\n".join(memo_content)

    # --- [사이드바] 유틸리티 섹션 ---
    with st.sidebar:
        st.header("⚙️ 탐조 도구함")
        st.subheader("🔭 다음 목표 찾기")
        not_found_families = [f for f in family_group.keys() if any(b not in st.session_state.found for b in family_group[f])]
        selected_fam = st.selectbox("과를 선택해 보세요", ["선택 안 함"] + not_found_families)
        
        if selected_fam != "선택 안 함":
            missing = [b for b in family_group[selected_fam] if b not in st.session_state.found]
            st.info(f"**{selected_fam}**의 미발견 종:\n" + ", ".join(missing))

        st.divider()
        st.subheader("📝 탐조 메모")
        memo_input = st.text_area("관찰 장소나 특징을 적어두세요", value=st.session_state.memo, height=250)
        if memo_input != st.session_state.memo:
            st.session_state.memo = memo_input
            save_list(MEMO_FILE, [memo_input])
            st.toast("메모 저장됨!", icon="💾")

    # --- 메인 화면 ---
    st.title("📸 나의 조류 체크리스트")
    
    total = len(birds)
    found_count = len(st.session_state.found)
    percent = round(found_count/total*100, 1)

    # --- [수정] 숫자만 크게, "종입니다."는 일반 크기로 통일 ---
    st.markdown(f"""
        <div style="padding: 20px; border-radius: 10px; background-color: #f0f2f6; margin-bottom: 20px;">
            <span style="font-size: 1.1rem; color: #555;">현재까지 관찰한 새는 총</span><br>
            <span style="font-size: 3.5rem; font-weight: 800; color: #007BFF; line-height: 1;">{found_count}</span>
            <span style="font-size: 1.5rem; font-weight: 600; color: #333;"> 종입니다.</span>
            <span style="font-size: 1.1rem; color: #666; margin-left: 10px;">(전체 {total}종 중 {percent}%)</span>
        </div>
    """, unsafe_allow_html=True)
    
    st.progress(found_count / total if total > 0 else 0)

    # 입력창
    def handle_input():
        val = st.session_state.bird_input.strip()
        if val in birds:
            if val not in st.session_state.found:
                st.session_state.found.append(val)
                save_list(SAVE_FILE, st.session_state.found)
                st.toast(f"✅ {val} 등록 완료!")
            else: st.warning(f"'{val}'은(는) 이미 등록되어 있습니다.")
        elif val != "": st.error(f"'{val}'은(는) 목록에 없는 새 이름입니다.")
        st.session_state.bird_input = ""

    st.text_input("새 이름을 입력하고 엔터를 누르세요", key="bird_input", on_change=handle_input)

    st.divider()

    # 과별 수집 현황 대시보드
    st.subheader("📊 과별 수집 현황")
    cols = st.columns(4)
    for i, (fam_name, member_list) in enumerate(family_group.items()):
        fam_total = len(member_list)
        fam_found_count = len([b for b in member_list if b in st.session_state.found])
        with cols[i % 4]:
            if fam_found_count == fam_total:
                st.markdown(f"<div style='padding:10px; border-radius:10px; background-color:#e6f4ea; border:1px solid #28a745; margin-bottom:10px;'><span style='color:#28a745; font-weight:bold;'>{fam_name}</span><br><small>{fam_found_count}/{fam_total} 완료!</small></div>", unsafe_allow_html=True)
            elif fam_found_count > 0:
                st.markdown(f"<div style='padding:10px; border-radius:10px; background-color:#f8f9fa; border:1px solid #ddd; margin-bottom:10px;'><b>{fam_name}</b><br><small>{fam_found_count}/{fam_total}</small></div>", unsafe_allow_html=True)
            else:
                st.markdown(f"<div style='padding:10px; opacity:0.5; margin-bottom:10px;'>{fam_name} <small>(0/{fam_total})</small></div>", unsafe_allow_html=True)

    st.divider()

    # 상세 기록 숨김창
    with st.expander(f"📜 내가 관찰한 상세 기록 보기 ({found_count}종)", expanded=False):
        if st.session_state.found:
            sorted_found = sorted(st.session_state.found, key=lambda x: bird_order_map.get(x, 999))
            for bird_name in sorted_found:
                original_no = bird_order_map[bird_name] + 1
                c1, c2 = st.columns([0.9, 0.1])
                c1.write(f"{original_no}. {bird_name}")
                if c2.button("삭제", key=f"del_{bird_name}"):
                    st.session_state.found.remove(bird_name)
                    save_list(SAVE_FILE, st.session_state.found)
                    st.rerun()
        else:
            st.info("아직 등록된 새가 없습니다.")