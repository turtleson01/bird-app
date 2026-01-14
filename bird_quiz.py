import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import google.generativeai as genai
from PIL import Image
import concurrent.futures 
from datetime import datetime
import os

# --- [1. 기본 설정] ---
st.set_page_config(page_title="탐조 도감", layout="wide", page_icon="🦅")

# CSS: 목록 디자인을 아주 심플하게 정리
hide_streamlit_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            .stApp {padding-top: 10px;}
            
            /* 목록 텍스트 스타일 */
            .bird-item {
                font-size: 1.05rem;
                padding: 5px 0;
                font-weight: 500;
            }
            hr { margin: 0.3rem 0 !important; }
            </style>
            """
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

try:
    SHEET_URL = st.secrets["connections"]["gsheets"]["spreadsheet"]
    API_KEY = st.secrets["GOOGLE_API_KEY"]
except:
    st.error("🚨 Secrets 설정이 필요합니다.")
    st.stop()

# --- [2. 데이터 및 족보 관리] ---
@st.cache_data
def load_bird_map():
    file_path = "data.csv"
    if not os.path.exists(file_path): return {}
    encodings = ['utf-8-sig', 'cp949', 'euc-kr']
    for enc in encodings:
        try:
            df = pd.read_csv(file_path, skiprows=2, encoding=enc)
            bird_data = df.iloc[:, [4]].dropna() 
            bird_data.columns = ['name']
            bird_list = bird_data['name'].str.strip().tolist()
            return {name: i + 1 for i, name in enumerate(bird_list)}
        except: continue
    return {}

BIRD_MAP = load_bird_map()
conn = st.connection("gsheets", type=GSheetsConnection)

def get_data():
    try:
        df = conn.read(spreadsheet=SHEET_URL, ttl=0)
        if df.empty: return pd.DataFrame(columns=['No', 'bird_name', 'date'])
        if BIRD_MAP and 'bird_name' in df.columns:
            df['real_no'] = df['bird_name'].apply(lambda x: BIRD_MAP.get(str(x).strip(), 9999))
            df = df.sort_values(by='real_no', ascending=True)
        return df
    except: return pd.DataFrame(columns=['No', 'bird_name', 'date'])

def save_data(bird_name):
    try:
        bird_name = bird_name.strip()
        df = get_data()
        if bird_name in df['bird_name'].values: return "이미 등록된 새입니다."
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        real_no = BIRD_MAP.get(bird_name, 9999)
        new_row = pd.DataFrame({'No': [real_no], 'bird_name': [bird_name], 'date': [now]})
        updated_df = pd.concat([df, new_row], ignore_index=True)
        conn.update(spreadsheet=SHEET_URL, data=updated_df)
        return True
    except Exception as e: return str(e)

# 다중 삭제 기능 추가
def delete_birds(bird_names_to_delete):
    try:
        df = get_data()
        df = df[~df['bird_name'].isin(bird_names_to_delete)]
        conn.update(spreadsheet=SHEET_URL, data=df)
        return True
    except Exception as e: return str(e)

# --- [3. AI 분석] ---
def analyze_bird_image(image, user_doubt=None):
    try:
        genai.configure(api_key=API_KEY)
        model = genai.GenerativeModel('gemini-2.5-flash') 
        prompt = f"사용자 의심: {user_doubt}. " if user_doubt else ""
        prompt += "사진 속 새의 '한국어 국명'을 식별하고 그 이유를 짧게 설명하세요. 출력: 새이름 | 이유"
        response = model.generate_content([prompt, image])
        return response.text.strip()
    except: return "Error | 분석 오류"

# --- [4. 메인 화면] ---
st.title("🦅 탐조 도감")

df = get_data()
st.markdown(f"""
    <div style="padding: 15px; border-radius: 12px; background-color: #e8f5e9; margin-bottom: 20px;">
        <span style="font-size: 1.0rem; color: #2e7d32; font-weight: bold;">🌱 총 발견한 새: {len(df)} 마리</span>
    </div>
""", unsafe_allow_html=True)

# 삭제/수정 버튼 (목록 상단에 배치)
with st.expander("🛠️ 기록 관리 (삭제하기)"):
    if not df.empty:
        # 검색 기능이 포함된 멀티 셀렉트
        to_delete = st.multiselect("삭제할 새를 검색해서 선택하세요", df['bird_name'].tolist())
        if st.button("선택한 새 삭제 실행", type="primary"):
            if to_delete:
                if delete_birds(to_delete) is True:
                    st.success(f"{len(to_delete)}마리의 기록을 삭제했습니다.")
                    st.rerun()
            else:
                st.warning("삭제할 대상을 선택해주세요.")
    else:
        st.write("삭제할 기록이 없습니다.")

tab1, tab2 = st.tabs(["✍️ 직접 입력", "📸 AI 분석"])

with tab1:
    def add_manual():
        name = st.session_state.input_bird.strip()
        if name:
            res = save_data(name)
            if res is True: st.toast(f"✅ {name} 등록 완료!"); st.session_state.input_bird = ""
            else: st.error(res)
    st.text_input("새 이름 입력", key="input_bird", on_change=add_manual)

with tab2:
    uploaded_files = st.file_uploader("", type=["jpg", "png", "jpeg"], accept_multiple_files=True)
    if 'ai_results' not in st.session_state: st.session_state.ai_results = {}
    if 'dismissed_files' not in st.session_state: st.session_state.dismissed_files = set()

    if uploaded_files:
        active_files = [f for f in uploaded_files if f.name not in st.session_state.dismissed_files]
        for file in active_files:
            if file.name not in st.session_state.ai_results:
                with st.spinner(f"{file.name} 분석 중..."):
                    st.session_state.ai_results[file.name] = analyze_bird_image(Image.open(file))
            
            raw = st.session_state.ai_results[file.name]
            bird_name, reason = raw.split("|") if "|" in raw else (raw, "분석 완료")
            
            with st.container(border=True):
                c_top1, c_top2 = st.columns([0.9, 0.1])
                if c_top2.button("❌", key=f"cls_{file.name}"):
                    st.session_state.dismissed_files.add(file.name); st.rerun()
                
                c1, c2 = st.columns([1, 2])
                c1.image(file, use_container_width=True)
                c2.markdown(f"### {bird_name.strip()}")
                c2.caption(reason.strip())
                if c2.button("➕ 등록하기", key=f"reg_{file.name}"):
                    if save_data(bird_name.strip()) is True: st.toast(f"✅ {bird_name.strip()} 등록 완료!"); st.rerun()

# --- [5. 하단: 전체 기록 보기 (매우 심플)] ---
st.divider()
st.subheader("📜 전체 기록 보기")
if not df.empty:
    for index, row in df.iterrows():
        bird = row['bird_name']
        real_no = BIRD_MAP.get(bird, 9999)
        display_no = "??" if real_no == 9999 else real_no
        
        st.markdown(f"<div class='bird-item'>{display_no}. {bird}</div>", unsafe_allow_html=True)
        st.markdown("<hr>", unsafe_allow_html=True)
else:
    st.caption("기록이 없습니다.")
