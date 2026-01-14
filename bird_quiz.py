import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import google.generativeai as genai
from PIL import Image

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
        families = bird_data['family_kor'].astype(str).str.strip().unique()
        family_group = {f: bird_data[bird_data['family_kor'] == f]['name'].str.strip().tolist() for f in families}
        
        return bird_list, bird_order_map, family_group
    except Exception as e:
        return [], {}, {}

conn = st.connection("gsheets", type=GSheetsConnection)

def get_user_data(user_name):
    try:
        df = conn.read(spreadsheet=SHEET_URL, ttl=0)
        if not df.empty and 'user_name' in df.columns:
            return df[df['user_name'] == user_name]['bird_name'].tolist()
        return []
    except:
        return []

def add_bird_to_sheet(user_name, bird_name):
    try:
        df = conn.read(spreadsheet=SHEET_URL, ttl=0)
        new_row = pd.DataFrame({'user_name': [user_name], 'bird_name': [bird_name]})
        updated_df = pd.concat([df, new_row], ignore_index=True)
        conn.update(spreadsheet=SHEET_URL, data=updated_df)
        return True
    except:
        return False

# --- 메인 화면 시작 ---
st.set_page_config(page_title="AI 조류 도감", layout="wide", page_icon="🐦")
birds, bird_order_map, family_group = load_bird_data()

# 임시 저장소 (즉시 반응용)
if 'local_updates' not in st.session_state:
    st.session_state.local_updates = []

# 로그인 화면
if 'user_name' not in st.session_state:
    st.session_state.user_name = ""

with st.sidebar:
    st.header("👤 사용자 설정")
    with st.form("login_sidebar"):
        input_name = st.text_input("닉네임", value=st.session_state.user_name)
        if st.form_submit_button("로그인"):
            st.session_state.user_name = input_name
            st.session_state.local_updates = [] 
            st.rerun()
    
    if st.session_state.user_name:
        st.success(f"✅ {st.session_state.user_name}님 기록 중")

if not st.session_state.user_name:
    st.info("👈 닉네임을 먼저 입력해주세요.")
    st.stop()

st.title("📸 AI 조류 도감")

# 통계 계산
db_birds = get_user_data(st.session_state.user_name)
my_birds = list(set(db_birds + st.session_state.local_updates))
found_count = len(my_birds)

st.markdown(f"""
    <div style="padding: 15px; border-radius: 10px; background-color: #f0f2f6; margin-bottom: 20px;">
        <span style="font-size: 1.1rem; color: #555;">{st.session_state.user_name}님의 도감</span><br>
        <span style="font-size: 2.0rem; font-weight: 800; color: #007BFF; line-height: 1;">{found_count}</span>
        <span style="font-size: 1.2rem; font-weight: 600; color: #333;"> 종 발견</span>
    </div>
""", unsafe_allow_html=True)

# 1. 직접 기록하기
st.subheader("✍️ 직접 기록하기")

def handle_input():
    val = st.session_state.bird_input.strip()
    if val in birds:
        if val not in my_birds:
            add_bird_to_sheet(st.session_state.user_name, val)
            st.session_state.local_updates.append(val)
            st.toast(f"✅ {val} 저장 완료!")
        else:
            st.warning(f"'{val}'는 이미 있어요.")
    elif val:
        st.error(f"'{val}'... 목록에 없어요.")
    st.session_state.bird_input = ""

st.text_input("새 이름을 입력하세요", key="bird_input", on_change=handle_input)

st.divider()

# ==========================================
# 2. [업그레이드] AI 사진 분석 (여러 장 동시 업로드)
# ==========================================
st.subheader("🤖 AI에게 물어보기")

# accept_multiple_files=True 로 변경!
uploaded_files = st.file_uploader("사진을 여러 장 선택해도 됩니다", type=["jpg", "jpeg", "png"], accept_multiple_files=True)

if uploaded_files:
    st.write(f"📂 총 **{len(uploaded_files)}장**의 사진을 분석합니다.")
    
    # 여러 장을 하나씩 반복하며 처리
    for i, file in enumerate(uploaded_files):
        # 각각의 사진을 깔끔한 상자(Container)에 담아서 보여줌
        with st.container(border=True):
            col1, col2 = st.columns([1, 2]) # 왼쪽: 사진, 오른쪽: 결과
            
            with col1:
                image = Image.open(file)
                st.image(image, use_container_width=True)
            
            with col2:
                with st.spinner(f"{i+1}번째 사진 분석 중..."):
                    try:
                        genai.configure(api_key=API_KEY)
                        model = genai.GenerativeModel('gemini-2.5-flash') # 속도 중요하므로 Flash 추천
                        
                        prompt = """
                        당신은 한국의 야생 조류 전문가입니다.
                        사진 속의 새를 식별하여 '한국어 국명'을 단어 하나로 답하세요.
                        한국 도심/공원에서 흔한 새(직박구리, 참새, 까치 등)일 확률을 우선 고려하세요.
                        """
                        
                        response = model.generate_content([prompt, image])
                        ai_result = response.text.strip()
                        
                        st.subheader(f"👉 {ai_result}")
                        
                        if ai_result == "새 아님":
                            st.caption("새를 찾을 수 없습니다.")
                        else:
                            is_in_book = ai_result in birds
                            if is_in_book:
                                st.caption("📚 도감에 있는 새입니다.")
                            else:
                                st.caption("⚠️ 도감 목록엔 없지만 등록 가능합니다.")
                            
                            # 버튼 키(key)를 사진마다 다르게 설정해야 에러가 안 남
                            unique_key = f"btn_{i}_{file.name}"
                            
                            if st.button(f"➕ '{ai_result}' 등록", key=unique_key):
                                if ai_result not in my_birds:
                                    add_bird_to_sheet(st.session_state.user_name, ai_result)
                                    st.session_state.local_updates.append(ai_result)
                                    st.toast(f"{ai_result} 저장 완료!")
                                    st.rerun()
                                else:
                                    st.warning("이미 등록된 새입니다.")
                                    
                    except Exception as e:
                        st.error(f"오류: {e}")

st.divider()

with st.expander("📜 전체 기록 보기"):
    st.write(f"총 {len(my_birds)}마리 발견")
    st.write(my_birds)
