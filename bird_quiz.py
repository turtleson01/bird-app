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

# --- [2. 원본 데이터(data.csv) 로드] ---
# 옛날 코드의 핵심 기능을 가져왔습니다. '족보'를 읽는 역할입니다.
@st.cache_data
def load_reference_data():
    file_path = "data.csv"
    if not os.path.exists(file_path):
        return {}
    
    encodings = ['utf-8-sig', 'cp949', 'euc-kr']
    for enc in encodings:
        try:
            # CSV 읽기 (옛날 코드 로직 그대로)
            df = pd.read_csv(file_path, skiprows=2, encoding=enc)
            bird_data = df.iloc[:, [4]].dropna() # 이름 컬럼
            bird_data.columns = ['name']
            bird_data['name'] = bird_data['name'].str.strip()
            bird_list = bird_data['name'].tolist()
            
            # { "참새": 1, "때까치": 256 ... } 형태로 맵핑 생성
            # enumerate는 0부터 시작하므로 +1 해줍니다.
            return {name: i + 1 for i, name in enumerate(bird_list)}
        except Exception: 
            continue
    return {}

# 족보(도감 번호표) 불러오기
BIRD_MAP = load_reference_data()

# --- [3. 구글 시트 연결 및 저장] ---
conn = st.connection("gsheets", type=GSheetsConnection)

def get_data():
    try:
        df = conn.read(spreadsheet=SHEET_URL, ttl=0)
        if df.empty:
            return pd.DataFrame(columns=['No', 'bird_name', 'date'])
        
        # 가져온 데이터를 'No' 번호 순서대로(오름차순) 정렬
        if 'No' in df.columns:
            df['No_Numeric'] = pd.to_numeric(df['No'], errors='coerce')
            df = df.sort_values(by='No_Numeric', ascending=True)
            
        return df
    except:
        return pd.DataFrame(columns=['No', 'bird_name', 'date'])

def save_data(bird_name):
    try:
        bird_name = bird_name.strip()
        df = get_data()
        
        # 이미 있는지 중복 체크
        if bird_name in df['bird_name'].values:
            return "이미 등록된 새입니다."

        # ⭐️ [핵심] 족보(data.csv)에서 진짜 번호 찾기
        if bird_name in BIRD_MAP:
            real_no = BIRD_MAP[bird_name] # 예: 때까치면 256
        else:
            # 족보에 없는 새(오타거나 희귀종)라면? 
            # 일단 가장 뒷번호(9000번대)로 임시 부여하거나, 기존 방식대로 마지막 번호+1
            # 여기서는 구분하기 쉽게 9000번부터 시작하게 했습니다.
            real_no = 9000 
            if 'No' in df.columns and not df.empty:
                max_val = pd.to_numeric(df['No'], errors='coerce').max()
                if max_val >= 9000:
                    real_no = int(max_val) + 1

        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        # 저장 (진짜 번호로 저장됨)
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
    st.warning("⚠️ 'data.csv' 파일을 찾지 못했습니다. 번호가 정확하지 않을 수 있습니다.")

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
            elif res == "이미 등록된 새입니다.":
                st.warning(f"이미 도감에 있는 새입니다.")
            else:
                st.error(f"저장 실패: {res}")

    st.text_input("새 이름 입력", key="input_bird", on_change=add_manual, placeholder="예: 때까치")

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
        # 이미 get_data()에서 번호순으로 정렬되어 넘어옵니다.
        for index, row in df.iterrows():
            bird = row['bird_name']
            
            if 'No' in df.columns and pd.notna(row['No']):
                try:
                    num = int(row['No'])
                except:
                    num = row['No']
            else:
                num = "??"
                
            st.markdown(f"**{num}. {bird}**")
            
    else:
        st.caption("아직 기록된 새가 없습니다.")
