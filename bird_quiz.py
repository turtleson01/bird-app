import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import google.generativeai as genai
from PIL import Image
import concurrent.futures 

# --- [설정] ---
try:
    SHEET_URL = st.secrets["connections"]["gsheets"]["spreadsheet"]
    API_KEY = st.secrets["GOOGLE_API_KEY"]
except:
    st.error("Secrets 설정 오류: API Key나 시트 주소가 없습니다.")
    st.stop()

# --- 데이터 로드 ---
@st.cache_data
def load_bird_data():
    try:
        try:
            df = pd.read_csv("data.csv", skiprows=2, encoding='utf-8-sig')
        except:
            df = pd.read_csv("data.csv", skiprows=2, encoding='cp949')

        bird_data = df.iloc[:, [4, 14]].dropna()
        bird_data.columns = ['name', 'family_kor']
        
        bird_list = bird_data['name'].astype(str).str.strip().tolist()
        bird_order_map = {name: i for i, name in enumerate(bird_list)}
        
        return bird_list, bird_order_map
    except Exception as e:
        return [], {}

conn = st.connection("gsheets", type=GSheetsConnection)

# ⭐️ [변경] 닉네임 없이 무조건 '나의_도감'이라는 하나의 이름으로 저장합니다.
DEFAULT_USER = "나의_도감"

def get_user_data():
    try:
        df = conn.read(spreadsheet=SHEET_URL, ttl=0)
        if not df.empty and 'user_name' in df.columns:
            # 내 도감 데이터만 가져오기
            return df[df['user_name'] == DEFAULT_USER]['bird_name'].tolist()
        return []
    except:
        return []

def add_bird_to_sheet(bird_name):
    try:
        df = conn.read(spreadsheet=SHEET_URL, ttl=0)
        
        if df.empty or 'user_name' not in df.columns:
             df = pd.DataFrame(columns=['user_name', 'bird_name'])
        
        # 무조건 DEFAULT_USER로 저장
        new_row = pd.DataFrame({'user_name': [DEFAULT_USER], 'bird_name': [bird_name]})
        updated_df = pd.concat([df, new_row], ignore_index=True)
        
        conn.update(spreadsheet=SHEET_URL, data=updated_df)
        return True
    except Exception as e:
        return str(e) # 에러 메시지 반환

# AI 분석 함수 (2.5 Flash)
def analyze_bird_image(image):
    try:
        genai.configure(api_key=API_KEY)
        model = genai.GenerativeModel('gemini-2.5-flash') 
        
        prompt = """
        당신은 한국의 야생 조류 전문가입니다.
        사진 속의 새를 식별하여 '한국어 국명'을 단어 하나로 답하세요.
        한국 도심/공원에서 흔한 새(직박구리, 참새, 까치 등)일 확률을 우선 고려하세요.
        만약 새가 아니라면 '새 아님'이라고 하세요.
        """
        response = model.generate_content([prompt, image])
        return response.text.strip()
    except Exception as e:
        return f"Error: {str(e)}"

# --- 메인 화면 시작 ---
st.set_page_config(page_title="나만의 탐조 도감", layout="wide", page_icon="🦅")
birds, bird_order_map = load_bird_data()

# 임시 저장소
if 'local_updates' not in st.session_state:
    st.session_state.local_updates = []

# ⭐️ 로그인 화면 삭제됨! 바로 메인 화면 시작

st.title("🦅 나만의 탐조 도감")

# 통계 계산
db_birds = get_user_data()
my_birds = list(set(db_birds + st.session_state.local_updates))
found_count = len(my_birds)

st.markdown(f"""
    <div style="padding: 15px; border-radius: 10px; background-color: #e8f5e9; margin-bottom: 20px;">
        <span style="font-size: 1.1rem; color: #2e7d32;">현재까지 모은 새</span><br>
        <span style="font-size: 2.2rem; font-weight: 800; color: #1b5e20; line-height: 1;">{found_count}</span>
        <span style="font-size: 1.3rem; font-weight: 600; color: #333;"> 종</span>
    </div>
""", unsafe_allow_html=True)

# 1. 직접 기록하기
st.subheader("✍️ 직접 기록하기")

def handle_input():
    val = st.session_state.bird_input.strip()
    if val in birds:
        if val not in my_birds:
            res = add_bird_to_sheet(val)
            if res is True:
                st.session_state.local_updates.append(val)
                st.toast(f"✅ {val} 도감 등록!")
                st.rerun()
            else:
                st.error(f"❌ 저장 실패 (키 설정을 확인하세요): {res}")
        else:
            st.warning(f"'{val}'는 이미 있어요.")
    elif val:
        st.error(f"'{val}'... 도감에 없는 이름입니다.")
    st.session_state.bird_input = ""

st.text_input("새 이름을 입력하세요", key="bird_input", on_change=handle_input)

st.divider()

# 2. AI 분석
st.subheader("🤖 사진으로 찾기")

uploaded_files = st.file_uploader("사진을 올려주세요 (여러 장 가능)", type=["jpg", "jpeg", "png"], accept_multiple_files=True)

if uploaded_files:
    st.write(f"📸 **{len(uploaded_files)}장** 분석 중...")
    
    images = [Image.open(file) for file in uploaded_files]
    results = []

    with st.spinner("AI가 새를 찾고 있습니다..."):
        with concurrent.futures.ThreadPoolExecutor() as executor:
            results = list(executor.map(analyze_bird_image, images))

    for i, (file, ai_result) in enumerate(zip(uploaded_files, results)):
        with st.container(border=True):
            col1, col2 = st.columns([1, 2])
            
            with col1:
                st.image(file, use_container_width=True)
            
            with col2:
                st.subheader(f"👉 {ai_result}")
                
                if "Error" in ai_result:
                    st.error(f"오류: {ai_result}")
                elif ai_result == "새 아님":
                    st.error("새를 찾을 수 없습니다.")
                else:
                    if ai_result in birds:
                        if ai_result in my_birds:
                            st.info("👋 이미 등록된 새입니다.")
                        else:
                            st.success("🎉 새로운 종 발견!")
                            
                            unique_key = f"btn_{i}_{file.name}"
                            if st.button(f"➕ '{ai_result}' 추가하기", key=unique_key):
                                res = add_bird_to_sheet(ai_result)
                                if res is True:
                                    st.session_state.local_updates.append(ai_result)
                                    st.toast(f"✅ {ai_result} 저장 완료!")
                                    st.rerun()
                                else:
                                    st.error(f"❌ 저장 실패: {res}")
                    else:
                        st.error(f"⚠️ '{ai_result}'은(는) 도감에 없는 새입니다.")

st.divider()

with st.expander("📜 내 도감 목록"):
    st.write(my_birds)
