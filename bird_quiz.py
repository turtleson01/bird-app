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
        df = pd.read_csv("data.csv", skiprows=2, encoding='utf-8-sig')
        bird_data = df.iloc[:, [4, 14]].dropna()
        bird_data.columns = ['name', 'family_kor']
        bird_list = bird_data['name'].str.strip().tolist()
        bird_order_map = {name: i for i, name in enumerate(bird_list)}
        families = bird_data['family_kor'].str.strip().unique()
        family_group = {f: bird_data[bird_data['family_kor'] == f]['name'].str.strip().tolist() for f in families}
        return bird_list, bird_order_map, family_group
    except:
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

# --- 메인 화면 설정 ---
st.set_page_config(page_title="AI 조류 도감", layout="wide", page_icon="🐦")
birds, bird_order_map, family_group = load_bird_data()

# --- 로그인 처리 ---
if 'user_name' not in st.session_state:
    st.session_state.user_name = ""

with st.sidebar:
    st.header("👤 사용자 설정")
    with st.form("login_sidebar"):
        input_name = st.text_input("닉네임을 입력하세요", value=st.session_state.user_name)
        if st.form_submit_button("로그인 / 변경"):
            st.session_state.user_name = input_name
            st.rerun()

    if st.session_state.user_name:
        st.success(f"✅ {st.session_state.user_name}님 기록 중")
    else:
        st.warning("👈 닉네임을 입력해주세요!")

if not st.session_state.user_name:
    st.info("👈 왼쪽 사이드바(모바일은 상단 화살표 >)를 열어 닉네임을 입력해주세요.")
    st.stop()

st.title("📸 AI 조류 도감")

# --- 통계 표시 ---
my_birds = get_user_data(st.session_state.user_name)
found_count = len(my_birds)
total = len(birds)
percent = round(found_count/total*100, 1) if total > 0 else 0

st.markdown(f"""
    <div style="padding: 15px; border-radius: 10px; background-color: #f0f2f6; margin-bottom: 20px;">
        <span style="font-size: 1.1rem; color: #555;">{st.session_state.user_name}님의 도감</span><br>
        <span style="font-size: 2.5rem; font-weight: 800; color: #007BFF; line-height: 1;">{found_count}</span>
        <span style="font-size: 1.2rem; font-weight: 600; color: #333;"> 종 발견</span>
        <span style="font-size: 1.0rem; color: #666;">({percent}%)</span>
    </div>
""", unsafe_allow_html=True)

# ==========================================
# 1. [순서 변경] 직접 입력하기 (맨 위로 이동)
# ==========================================
st.subheader("✍️ 직접 기록하기")
def handle_input():
    val = st.session_state.bird_input.strip()
    if val in birds:
        if val not in my_birds:
            add_bird_to_sheet(st.session_state.user_name, val)
            st.toast(f"✅ {val} 저장 완료!")
            st.rerun()
        else:
            st.warning(f"'{val}'는 이미 등록된 새입니다.")
    elif val:
        st.error("목록에 없는 새 이름입니다.")
    st.session_state.bird_input = ""

st.text_input("새 이름을 알고 있다면 바로 입력하세요", key="bird_input", on_change=handle_input)

st.divider()

# ==========================================
# 2. [기능 수정] AI 사진 분석 (버튼 삭제 & 자동 실행)
# ==========================================
st.subheader("🤖 AI에게 물어보기")
with st.expander("📷 사진 업로드하여 검색하기", expanded=True):
    uploaded_file = st.file_uploader("사진을 선택하면 자동으로 분석합니다", type=["jpg", "jpeg", "png"])

    if uploaded_file is not None:
        image = Image.open(uploaded_file)
        st.image(image, caption='분석 중...', width=300)
        
        # 버튼 없이 바로 실행
        with st.spinner("AI가 도감을 찾는 중입니다..."):
            try:
                genai.configure(api_key=API_KEY)
                
                # 아까 확인한 최신 모델 사용
                model = genai.GenerativeModel('gemini-2.5-flash')
                
                prompt = "이 사진에 있는 새의 정확한 한국어 국명(Official Korean Name)만 딱 단어로 말해줘. 부가 설명 하지마. 만약 새가 아니라면 '새 아님'이라고 해."
                response = model.generate_content([prompt, image])
                ai_result = response.text.strip()
                
                st.success(f"AI 결과: **{ai_result}**")
                
                # 결과 처리
                if ai_result in birds:
                    if ai_result not in my_birds:
                        # 등록 버튼
                        if st.button(f"➕ '{ai_result}' 도감에 등록하기", key=f"btn_{ai_result}"):
                            add_bird_to_sheet(st.session_state.user_name, ai_result)
                            st.toast("등록 완료!")
                            st.rerun()
                    else:
                        st.info(f"🎉 이미 찾은 새입니다! ({ai_result})")
                elif ai_result == "새 아님":
                    st.error("사진에서 새를 찾을 수 없습니다.")
                else:
                    st.warning(f"AI는 '{ai_result}'라고 하는데, 우리 도감 리스트엔 없네요. (이름이 다르거나 미등록 종)")
                    
            except Exception as e:
                st.error(f"분석 중 오류가 발생했습니다: {e}")

st.divider()

# --- 리스트 보기 ---
with st.expander(f"📜 전체 기록 보기 ({found_count}종)"):
    if my_birds:
        sorted_found = sorted(my_birds, key=lambda x: bird_order_map.get(x, 999))
        for b in sorted_found:
            st.write(f"- {b}")
    else:
        st.write("아직 기록이 없습니다.")
