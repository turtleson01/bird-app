import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import google.generativeai as genai
from PIL import Image
import concurrent.futures 
from datetime import datetime
import math

# --- [1. 기본 설정] ---
st.set_page_config(page_title="탐조 도감", layout="wide", page_icon="🦅")

hide_streamlit_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            .stApp {padding-top: 10px;}
            </style>
            """
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

try:
    SHEET_URL = st.secrets["connections"]["gsheets"]["spreadsheet"]
    API_KEY = st.secrets["GOOGLE_API_KEY"]
except:
    st.error("🚨 Secrets 설정이 필요합니다.")
    st.stop()

# --- [2. 구글 시트 연결] ---
conn = st.connection("gsheets", type=GSheetsConnection)

def get_data():
    try:
        df = conn.read(spreadsheet=SHEET_URL, ttl=0)
        if df.empty:
            # 엑셀에 아무것도 없으면 기본 틀 생성 (No, bird_name, date)
            return pd.DataFrame(columns=['No', 'bird_name', 'date'])
        return df
    except:
        return pd.DataFrame(columns=['No', 'bird_name', 'date'])

def save_data(bird_name):
    try:
        df = get_data()
        
        # 1. 'No' 컬럼에서 가장 큰 숫자 찾기
        next_no = 1
        if 'No' in df.columns and not df.empty:
            # 숫자가 아닌 값이 있어도 에러 안 나게 처리
            max_val = pd.to_numeric(df['No'], errors='coerce').max()
            if not pd.isna(max_val):
                next_no = int(max_val) + 1
            
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        # 2. 'No' 컬럼에 번호 넣어서 저장
        new_row = pd.DataFrame({'No': [next_no], 'bird_name': [bird_name], 'date': [now]})
        updated_df = pd.concat([df, new_row], ignore_index=True)
        
        conn.update(spreadsheet=SHEET_URL, data=updated_df)
        return True
    except Exception as e:
        return str(e)

# --- [3. AI 분석 함수] ---
def analyze_bird_image(image):
    try:
        genai.configure(api_key=API_KEY)
        model = genai.GenerativeModel('gemini-2.5-flash') 
        prompt = "사진 속 새의 '한국어 국명'을 단어 하나로 답하시오. 새가 아니면 '새 아님'."
        response = model.generate_content([prompt, image])
        return response.text.strip()
    except:
        return "Error"

# --- [4. 메인 화면] ---
st.title("🦅 탐조 도감")

# 데이터 불러오기
df = get_data()
count = len(df)

# 통계 박스
st.markdown(f"""
    <div style="padding: 15px; border-radius: 12px; background-color: #e8f5e9; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
        <span style="font-size: 1.0rem; color: #2e7d32; font-weight: bold;">🌱 총 발견한 새</span><br>
        <span style="font-size: 2.2rem; font-weight: 800; color: #1b5e20; line-height: 1.2;">{count}</span>
        <span style="font-size: 1.2rem; font-weight: 600; color: #333;"> 마리</span>
    </div>
""", unsafe_allow_html=True)

tab1, tab2 = st.tabs(["✍️ 직접 입력", "📸 AI 분석"])

# ------------------------------------------------
# 탭 1: 직접 입력
# ------------------------------------------------
with tab1:
    st.write("##### 📝 발견한 새 이름을 기록하세요")
    
    def add_manual():
        name = st.session_state.input_bird.strip()
        if name:
            res = save_data(name)
            if res is True:
                st.toast(f"✅ {name} 저장 완료!")
                st.session_state.input_bird = ""
                st.rerun() # 저장 후 바로 목록 갱신
            else:
                st.error(f"저장 실패: {res}")

    st.text_input("새 이름 입력", key="input_bird", on_change=add_manual, placeholder="예: 직박구리")

# ------------------------------------------------
# 탭 2: AI 사진 분석
# ------------------------------------------------
with tab2:
    st.write("##### 📸 사진으로 새 이름 찾기")
    uploaded_files = st.file_uploader("", type=["jpg", "png", "jpeg"], accept_multiple_files=True)

    if uploaded_files:
        st.write(f"⚡️ **{len(uploaded_files)}장** 분석 중...")
        images = [Image.open(file) for file in uploaded_files]
        
        with st.spinner("AI가 분석 중..."):
            with concurrent.futures.ThreadPoolExecutor() as executor:
                results = list(executor.map(analyze_bird_image, images))

        for file, result in zip(uploaded_files, results):
            with st.container(border=True):
                c1, c2 = st.columns([1, 2])
                with c1: st.image(file, use_container_width=True)
                with c2:
                    if result == "새 아님" or "Error" in result:
                        st.error("새를 못 찾았어요.")
                    else:
                        st.markdown(f"### 👉 **{result}**")
                        if st.button(f"➕ 저장하기", key=f"btn_{file.name}"):
                            res = save_data(result)
                            if res is True:
                                st.toast(f"✅ {result} 도감에 영구 저장!")
                                st.rerun()
                            else:
                                st.error(f"저장 실패: {res}")

# --- [5. 하단: 전체 기록 보기] ---
st.divider()
with st.expander("📜 전체 기록 보기 (등록순)", expanded=True):
    if not df.empty and 'bird_name' in df.columns:
        # ⭐️ 엑셀의 'No' 컬럼을 찾아서 그대로 보여줍니다.
        
        # 목록 출력 (위에서 아래로 순서대로)
        for index, row in df.iterrows():
            bird = row['bird_name']
            
            # 'No' 컬럼 값 가져오기
            if 'No' in df.columns and pd.notna(row['No']):
                try:
                    # 1.0 처럼 소수점으로 나오는 걸 방지하기 위해 int로 변환
                    num = int(row['No'])
                except:
                    num = row['No'] # 숫자가 아니면 그대로 출력
            else:
                num = index + 1 # No가 없으면 그냥 순서대로
                
            st.markdown(f"**{num}. {bird}**")
            
    else:
        st.caption("아직 기록된 새가 없습니다.")
