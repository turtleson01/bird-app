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

# --- 데이터 로드 함수 ---
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
        
        return bird_list, bird_order_map, family_group, df.head(5)
    except Exception as e:
        return [], {}, {}, str(e)

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
birds, bird_order_map, family_group, debug_data = load_bird_data()

# 로그인
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

if not st.session_state.user_name:
    st.info("👈 왼쪽 사이드바(모바일은 상단 화살표 >)를 열어 닉네임을 입력해주세요.")
    st.stop()

st.title("📸 AI 조류 도감")

# 통계
my_birds = get_user_data(st.session_state.user_name)
found_count = len(my_birds)
st.markdown(f"""
    <div style="padding: 15px; border-radius: 10px; background-color: #f0f2f6; margin-bottom: 20px;">
        <span style="font-size: 1.1rem; color: #555;">{st.session_state.user_name}님의 도감</span><br>
        <span style="font-size: 2.0rem; font-weight: 800; color: #007BFF; line-height: 1;">{found_count}</span>
        <span style="font-size: 1.2rem; font-weight: 600; color: #333;"> 종 발견</span>
    </div>
""", unsafe_allow_html=True)

# ==========================================
# 1. [수정됨] 직접 기록하기 (에러 해결!)
# ==========================================
st.subheader("✍️ 직접 기록하기")

def handle_input():
    val = st.session_state.bird_input.strip()
    if val in birds:
        if val not in my_birds:
            add_bird_to_sheet(st.session_state.user_name, val)
            st.toast(f"✅ {val} 저장 완료!")
            # ⭐️ [핵심 수정] 여기서 st.rerun()을 지웠습니다!
            # 함수가 끝나면 자동으로 화면이 갱신됩니다.
        else:
            st.warning(f"'{val}'는 이미 등록된 새입니다.")
    elif val:
        st.error(f"'{val}'... 목록에 없는 이름입니다.")
    # 입력창 비우기
    st.session_state.bird_input = ""

st.text_input("새 이름을 입력하세요", key="bird_input", on_change=handle_input)

st.divider()

# ==========================================
# 2. AI 분석 (직박구리, 참새 등 텃새 강화)
# ==========================================
st.subheader("🤖 AI에게 물어보기")
with st.expander("📷 사진 업로드하여 검색하기", expanded=True):
    uploaded_file = st.file_uploader("사진을 선택하면 자동으로 분석합니다", type=["jpg", "jpeg", "png"])

    if uploaded_file is not None:
        image = Image.open(uploaded_file)
        st.image(image, caption='분석 중...', width=300)
        
        with st.spinner("AI가 눈을 크게 뜨고 확인 중입니다..."):
            try:
                genai.configure(api_key=API_KEY)
                model = genai.GenerativeModel('gemini-2.5-flash') 
                
                prompt = """
                당신은 한국의 야생 조류 전문가입니다.
                사진 속의 새를 식별하여 '한국어 국명'을 단어 하나로 답하세요.
                
                [규칙]
                1. ⭐️가장 중요: 한국 도심/공원에서 흔한 새(직박구리, 참새, 까치, 비둘기, 박새 등)일 확률을 먼저 고려하세요.
                2. 흐릿하다면 실루엣과 자세를 보고 가장 흔한 새를 추측하세요.
                3. 동고비 같은 특정 종은 특징이 명확할 때만 답하세요.
                4. 부가 설명 없이 이름만 말하세요. (예: 직박구리)
                """
                
                response = model.generate_content([prompt, image])
                ai_result = response.text.strip()
                
                st.info(f"AI의 판단: **{ai_result}**")
                
                if ai_result == "새 아님":
                     st.error("새를 찾을 수 없습니다.")
                else:
                    if ai_result in birds:
                        st.success("📚 도감 목록에 있는 새입니다!")
                        if st.button(f"➕ '{ai_result}' 등록하기", key=f"ai_btn_{ai_result}"):
                             if ai_result not in my_birds:
                                 add_bird_to_sheet(st.session_state.user_name, ai_result)
                                 st.toast("저장 완료!")
                                 st.rerun()
                             else:
                                 st.warning("이미 등록된 새입니다.")
                    else:
                        st.warning(f"⚠️ 도감 리스트엔 '{ai_result}'가 없네요.")
                        if st.button(f"그래도 '{ai_result}' 등록할래", key=f"force_btn_{ai_result}"):
                            add_bird_to_sheet(st.session_state.user_name, ai_result)
                            st.toast("강제 저장 완료!")
                            st.rerun()
                            
            except Exception as e:
                st.error(f"오류: {e}")

st.divider()

# ==========================================
# 🛠️ 데이터 진단 (필요할 때만 열어보세요)
# ==========================================
with st.expander("🛠️ 데이터 확인용 (문제가 생기면 열어보세요)"):
    st.write(f"총 새 이름 개수: {len(birds)}")
    st.write(birds[:10])
