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

# --- 메인 화면 ---
st.set_page_config(page_title="AI 조류 도감", layout="wide", page_icon="🐦")
birds, bird_order_map, family_group = load_bird_data()

st.title("📸 AI 조류 도감")

# 1. 닉네임 입력 (사이드바)
if 'user_name' not in st.session_state:
    st.session_state.user_name = ""

with st.sidebar:
    st.header("👤 사용자 설정")
    # 모바일 입력 오류 방지를 위해 폼 사용
    with st.form("login_sidebar"):
        input_name = st.text_input("닉네임을 입력하세요", value=st.session_state.user_name)
        if st.form_submit_button("로그인 / 변경"):
            st.session_state.user_name = input_name
            st.rerun()

    if st.session_state.user_name:
        st.success(f"✅ {st.session_state.user_name}님 환영합니다!")
    else:
        st.warning("👈 기록하려면 닉네임을 입력하세요!")

# 닉네임 없으면 멈춤
if not st.session_state.user_name:
    st.info("왼쪽 사이드바(모바일은 상단 화살표 >)를 열어 닉네임을 입력해주세요.")
    st.stop()

# 2. 메인 통계
my_birds = get_user_data(st.session_state.user_name)
found_count = len(my_birds)
total = len(birds)
percent = round(found_count/total*100, 1) if total > 0 else 0

st.markdown(f"""
    <div style="padding: 20px; border-radius: 10px; background-color: #f0f2f6; margin-bottom: 20px;">
        <span style="font-size: 1.2rem; color: #555;">{st.session_state.user_name}님의 관찰 기록</span><br>
        <span style="font-size: 3rem; font-weight: 800; color: #007BFF; line-height: 1;">{found_count}</span>
        <span style="font-size: 1.5rem; font-weight: 600; color: #333;"> 종</span>
        <span style="font-size: 1.1rem; color: #666; margin-left: 10px;">({percent}%)</span>
    </div>
""", unsafe_allow_html=True)

st.divider()

# --- [핵심 수정] AI 사진 동정 기능 ---
st.subheader("🤖 AI에게 물어보기")
with st.expander("📷 사진 업로드하여 검색하기", expanded=True):
    uploaded_file = st.file_uploader("새 사진을 올려주세요", type=["jpg", "jpeg", "png"])

    if uploaded_file is not None:
        image = Image.open(uploaded_file)
        st.image(image, caption='업로드된 사진', width=300)
        
        if st.button("이 새 이름이 뭐야?"):
            with st.spinner("AI가 도감을 뒤적이는 중..."):
                try:
                    genai.configure(api_key=API_KEY)
                    
                    # ✅ [여기 수정됨] 질문자님의 사용 가능한 모델로 변경!
                    model = genai.GenerativeModel('gemini-2.5-flash')
                    
                    prompt = "이 사진에 있는 새의 정확한 한국어 국명(Official Korean Name)만 딱 단어로 말해줘. 부가 설명 하지마. 만약 새가 아니라면 '새 아님'이라고 해."
                    response = model.generate_content([prompt, image])
                    ai_result = response.text.strip()
                    
                    st.info(f"AI의 답변: **{ai_result}**")
                    
                    # 도감 매칭 로직
                    if ai_result in birds:
                        if ai_result not in my_birds:
                            st.success(f"도감에 있는 새입니다! ({ai_result})")
                            if st.button(f"'{ai_result}' 등록하기", key=f"btn_{ai_result}"):
                                add_bird_to_sheet(st.session_state.user_name, ai_result)
                                st.toast("등록 완료!")
                                st.rerun()
                        else:
                            st.warning(f"이미 등록하신 새입니다. ({ai_result})")
                    elif ai_result == "새 아님":
                        st.error("사진에서 새를 찾을 수 없습니다.")
                    else:
                        st.warning(f"AI가 '{ai_result}'라고 했지만, 우리 도감 목록에는 없는 이름입니다.")
                        
                except Exception as e:
                    st.error(f"AI 오류: {e}")

st.divider()

# 3. 수동 입력
st.subheader("✍️ 직접 입력하기")
def handle_input():
    val = st.session_state.bird_input.strip()
    if val in birds:
        if val not in my_birds:
            add_bird_to_sheet(st.session_state.user_name, val)
            st.toast(f"✅ {val} 저장 완료!")
            st.rerun()
        else:
            st.warning("이미 등록된 새입니다.")
    elif val:
        st.error("목록에 없는 새 이름입니다.")
    st.session_state.bird_input = ""

st.text_input("새 이름을 입력하세요", key="bird_input", on_change=handle_input)

# 4. 리스트 보기
with st.expander(f"📜 상세 기록 보기 ({found_count}종)"):
    if my_birds:
        sorted_found = sorted(my_birds, key=lambda x: bird_order_map.get(x, 999))
        for b in sorted_found:
            st.write(f"- {b}")
    else:
        st.write("아직 기록이 없습니다.")
