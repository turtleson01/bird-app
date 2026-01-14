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

# --- [2. 족보(data.csv) 로드 함수] ---
@st.cache_data
def load_bird_map():
    file_path = "data.csv"
    # 파일이 없으면 빈 딕셔너리 반환
    if not os.path.exists(file_path):
        return {}
    
    encodings = ['utf-8-sig', 'cp949', 'euc-kr']
    for enc in encodings:
        try:
            df = pd.read_csv(file_path, skiprows=2, encoding=enc)
            # 4번째 컬럼이 이름이라고 가정 (옛날 코드 기준)
            # 만약 에러나면 컬럼 인덱스 조절 필요
            bird_data = df.iloc[:, [4]].dropna() 
            bird_data.columns = ['name']
            bird_data['name'] = bird_data['name'].str.strip()
            bird_list = bird_data['name'].tolist()
            
            # { "참새": 1, "때까치": 256 ... } 맵핑 만들기
            return {name: i + 1 for i, name in enumerate(bird_list)}
        except:
            continue
    return {}

# 앱 시작할 때 족보 로딩
BIRD_MAP = load_bird_map()

# --- [3. 구글 시트 데이터 로드 & 번호 자동 수정] ---
conn = st.connection("gsheets", type=GSheetsConnection)

def get_data():
    try:
        df = conn.read(spreadsheet=SHEET_URL, ttl=0)
        if df.empty:
            return pd.DataFrame(columns=['No', 'bird_name', 'date'])
        
        # ⭐️ [핵심] 시트에 저장된 번호가 틀릴 수 있으니, 족보(BIRD_MAP)보고 다시 매깁니다.
        if BIRD_MAP and 'bird_name' in df.columns:
            # 족보에 있으면 그 번호, 없으면 9999번
            df['real_no'] = df['bird_name'].apply(lambda x: BIRD_MAP.get(str(x).strip(), 9999))
            
            # 진짜 번호 순서대로 정렬 (1번부터 ...)
            df = df.sort_values(by='real_no', ascending=True)
            return df
        else:
            return df
    except:
        return pd.DataFrame(columns=['No', 'bird_name', 'date'])

def save_data(bird_name):
    try:
        bird_name = bird_name.strip()
        df = get_data()
        
        # 중복 체크
        if 'bird_name' in df.columns and bird_name in df['bird_name'].values:
            return "이미 등록된 새입니다."

        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        # 저장할 때는 'No' 컬럼에 일단 0으로 넣어도 됩니다. 
        # (어차피 불러올 때 BIRD_MAP 보고 다시 계산하니까요)
        real_no = BIRD_MAP.get(bird_name, 9999)
        
        new_row = pd.DataFrame({'No': [real_no], 'bird_name': [bird_name], 'date': [now]})
        updated_df = pd.concat([df, new_row], ignore_index=True)
        
        conn.update(spreadsheet=SHEET_URL, data=updated_df)
        return True
    except Exception as e:
        return str(e)

# --- [4. AI 분석 함수] ---
def analyze_bird_image(image):
    try:
        genai.configure(api_key=API_KEY)
        model = genai.GenerativeModel('gemini-2.5-flash') 
        prompt = "사진 속 새의 '한국어 국명'을 단어 하나로 답하시오. 새가 아니면 '새 아님'."
        response = model.generate_content([prompt, image])
        return response.text.strip()
    except:
        return "Error"

# --- [5. 메인 화면] ---
st.title("🦅 탐조 도감")

if not BIRD_MAP:
    st.error("⚠️ 'data.csv' 파일을 찾을 수 없습니다! 프로젝트 폴더에 파일을 넣어주세요.")

# 데이터 불러오기 (여기서 번호 교정 & 정렬 완료됨)
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
            elif res == "이미 등록된 새입니다.":
                st.warning("이미 도감에 있는 새입니다.")
            else:
                st.error(f"저장 실패: {res}")

    st.text_input("새 이름 입력", key="input_bird", on_change=add_manual, placeholder="예: 참새")

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
                        # 족보에서 번호 찾아서 미리 보여주기
                        bird_no = BIRD_MAP.get(result, "??")
                        st.markdown(f"### 👉 **{result}**")
                        st.caption(f"도감 번호: {bird_no}번")
                        
                        if st.button(f"➕ 저장하기", key=f"btn_{file.name}"):
                            res = save_data(result)
                            if res is True:
                                st.toast(f"✅ {result} 도감에 영구 저장!")
                                st.rerun()
                            elif res == "이미 등록된 새입니다.":
                                st.warning("이미 저장된 새입니다.")
                            else:
                                st.error(f"저장 실패: {res}")

# --- [6. 하단: 전체 기록 보기] ---
st.divider()
with st.expander("📜 전체 기록 보기 (도감 번호순)", expanded=True):
    if not df.empty and 'bird_name' in df.columns:
        
        # BIRD_MAP을 이용해서 번호를 다시 표시
        for index, row in df.iterrows():
            bird = row['bird_name']
            
            # 족보에서 진짜 번호 가져오기
            real_no = BIRD_MAP.get(bird, 9999)
            
            if real_no == 9999:
                display_no = "??" # 족보에 없는 새
            else:
                display_no = real_no
                
            st.markdown(f"**{display_no}. {bird}**")
            
    else:
        st.caption("아직 기록된 새가 없습니다.")
