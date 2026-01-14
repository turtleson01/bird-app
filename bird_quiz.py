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

# CSS: 이름과 삭제 버튼 사이의 적절한 간격 확보
hide_streamlit_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            .stApp {padding-top: 10px;}
            
            /* 수직 중앙 정렬 및 가로 배열 */
            div[data-testid="stHorizontalBlock"] {
                display: flex !important;
                flex-direction: row !important;
                flex-wrap: nowrap !important;
                align-items: center !important;
            }
            
            /* 컬럼 설정: 이름 컬럼에 최소 너비를 주어 버튼을 밀어냄 */
            div[data-testid="column"] {
                min-width: 0 !important;
                flex: 1 1 auto !important;
            }

            /* 삭제 버튼 스타일: 이름에서 적당히 떨어지도록 마진 설정 */
            button[kind="secondary"] {
                border: 1px solid #ffcccc;
                background-color: transparent;
                color: #ff4b4b;
                
                width: fit-content !important; 
                height: 32px !important;
                padding: 0 12px !important;
                margin-left: 20px !important; /* 이름과 최소 20px은 떨어지게 설정 */
                
                font-size: 0.8rem !important;
                border-radius: 8px;
                white-space: nowrap !important;
            }
            
            button[kind="secondary"]:hover {
                background-color: #fff0f0;
                border-color: #ff4b4b;
            }
            
            /* 목록 텍스트 스타일: 이름이 길어지면 잘리도록 설정 */
            .bird-name-text {
                font-weight: 500;
                font-size: 1rem;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
                max-width: 100%;
            }
            
            hr { margin: 0.4rem 0 !important; }
            </style>
            """
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

try:
    SHEET_URL = st.secrets["connections"]["gsheets"]["spreadsheet"]
    API_KEY = st.secrets["GOOGLE_API_KEY"]
except:
    st.error("🚨 Secrets 설정이 필요합니다.")
    st.stop()

# --- [2. 데이터 로드 및 족보 관리] ---
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
        if 'bird_name' in df.columns and bird_name in df['bird_name'].values: return "이미 등록된 새입니다."
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        real_no = BIRD_MAP.get(bird_name, 9999)
        new_row = pd.DataFrame({'No': [real_no], 'bird_name': [bird_name], 'date': [now]})
        updated_df = pd.concat([df, new_row], ignore_index=True)
        conn.update(spreadsheet=SHEET_URL, data=updated_df)
        return True
    except Exception as e: return str(e)

def delete_data(bird_name):
    try:
        df = get_data()
        df = df[df['bird_name'] != bird_name]
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

# --- [5. 하단: 전체 기록 보기] ---
st.divider()
with st.expander("📜 전체 기록 보기", expanded=True):
    if not df.empty:
        for index, row in df.iterrows():
            bird = row['bird_name']
            real_no = BIRD_MAP.get(bird, 9999)
            display_no = "??" if real_no == 9999 else real_no
            
            # ⭐️ 이름과 버튼 사이의 간격을 위해 비율 조정 (8:2)
            # 버튼은 자기 구역 안에서 여백(margin-left)을 가짐
            c1, c2 = st.columns([0.8, 0.2])
            with c1:
                st.markdown(f"<div class='bird-name-text'>{display_no}. {bird}</div>", unsafe_allow_html=True)
            with c2:
                if st.button("삭제", key=f"del_{index}_{bird}"):
                    if delete_data(bird) is True: st.toast(f"🗑️ {bird} 삭제됨"); st.rerun()
            st.markdown("<hr>", unsafe_allow_html=True)
    else:
        st.caption("기록이 없습니다.")
