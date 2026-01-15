import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import google.generativeai as genai
from PIL import Image
from datetime import datetime
import os

# --- [1. 기본 설정] ---
st.set_page_config(page_title="나의 탐조 도감", layout="wide", page_icon="🦅")

# CSS: 디자인 설정
hide_streamlit_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            .stApp {padding-top: 10px;}
            
            /* 요약 박스 */
            .summary-box {
                padding: 20px; 
                border-radius: 15px; 
                background: linear-gradient(135deg, #e8f5e9 0%, #c8e6c9 100%);
                margin-bottom: 10px;
                box-shadow: 0 4px 6px rgba(0,0,0,0.05);
                text-align: left;
            }
            .summary-text { font-size: 1.1rem; color: #2e7d32; font-weight: bold; }
            .summary-count { font-size: 2rem; font-weight: 800; color: #1b5e20; }
            
            /* 진행바 */
            .progress-container {
                width: 100%;
                background-color: #f1f3f5;
                border-radius: 10px;
                margin-bottom: 30px;
                height: 12px;
                overflow: hidden;
            }
            .progress-bar {
                height: 100%;
                background-color: #66bb6a;
                border-radius: 10px;
                transition: width 0.5s ease-in-out;
            }
            
            /* 사이드바 카드 */
            .sidebar-card {
                background-color: white;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                padding: 12px 15px;
                margin-bottom: 8px;
                display: flex;
                justify-content: space-between;
                align-items: center;
                box-shadow: 0 1px 3px rgba(0,0,0,0.05);
                transition: transform 0.2s;
            }
            .sidebar-card:hover {
                transform: translateX(3px);
                border-color: #81c784;
            }
            .card-title {
                font-size: 0.95rem;
                font-weight: 600;
                color: #333;
            }
            .card-stat {
                font-size: 0.9rem;
                color: #666;
                font-weight: 500;
            }
            .stat-highlight {
                color: #2e7d32;
                font-weight: 700;
            }
            
            /* 파일 업로더 버튼 숨기기 (X버튼은 살림) */
            [data-testid="stFileUploaderDropzone"] button { display: none !important; }
            [data-testid="stFileUploaderDropzone"] section { cursor: pointer; }

            /* 목록 스타일 */
            .bird-item { font-size: 1.1rem; padding: 12px 5px; font-weight: 500; color: #333; }
            hr { margin: 0 !important; border-top: 1px solid #eee !important; }

            /* 버튼 스타일 */
            div.stButton > button[kind="primary"] {
                background: linear-gradient(45deg, #64B5F6, #90CAF9); 
                color: white !important;
                border: none;
                border-radius: 12px;
                padding: 0.6rem 1rem;
                font-weight: 700;
                width: 100%;
                box-shadow: 0 3px 5px rgba(0,0,0,0.1);
            }
            div.stButton > button[kind="secondary"] {
                background-color: white;
                color: #ff4b4b;
                border: 1px solid #ffcccc;
                border-radius: 8px;
            }
            [data-testid="stSidebar"] {
                background-color: #fafafa;
                border-right: 1px solid #eee;
            }
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
    if not os.path.exists(file_path): return {}, {}, 0, {}
    
    encodings = ['utf-8-sig', 'cp949', 'euc-kr']
    for enc in encodings:
        try:
            # ⭐️ [핵심 수정] 14번째 열(O열)을 직접 조준해서 읽습니다.
            # skiprows=2: 헤더가 2줄이므로 데이터가 시작되는 3번째 줄부터 읽기 위해
            # header=None: 컬럼 이름을 자동으로 잡지 않고 인덱스(0, 1, 2...)로 쓰기 위해
            
            df = pd.read_csv(file_path, skiprows=2, header=None, encoding=enc)
            
            # 컬럼 개수가 충분한지 확인 (적어도 15개 이상이어야 함)
            if df.shape[1] < 15: continue

            # 4번 열(Index 4): 대표국명 (새 이름)
            # 14번 열(Index 14): Family 국명 (과 이름 - 한글)
            bird_data = df.iloc[:, [4, 14]].copy()
            bird_data.columns = ['name', 'family']
            
            # 결측치 제거
            bird_data = bird_data.dropna()
            
            # 데이터 정제 (공백 제거)
            bird_data['name'] = bird_data['name'].astype(str).str.strip()
            bird_data['family'] = bird_data['family'].astype(str).str.strip()
            
            # 혹시 모를 헤더 찌꺼기 제거
            filter_keywords = ['대표국명', '국명', 'Name', 'Family', '과']
            bird_data = bird_data[~bird_data['family'].isin(filter_keywords)]

            # 전체 종 수 (중복 포함 엑셀 줄 수)
            total_rows_count = len(bird_data)

            # 매핑 데이터 생성
            bird_list = bird_data['name'].tolist()
            name_to_no = {name: i + 1 for i, name in enumerate(bird_list)}
            name_to_family = dict(zip(bird_data['name'], bird_data['family']))
            family_total_counts = bird_data['family'].value_counts().to_dict()
            
            return name_to_no, name_to_family, total_rows_count, family_total_counts
        except Exception as e:
            continue
        
    return {}, {}, 0, {}

BIRD_MAP, FAMILY_MAP, TOTAL_SPECIES_COUNT, FAMILY_TOTAL_COUNTS = load_bird_map()
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
    bird_name = bird_name.strip()
    if bird_name not in BIRD_MAP:
        return f"⚠️ '{bird_name}'은(는) 족보에 없는 이름입니다."
    try:
        df = get_data()
        if bird_name in df['bird_name'].values: return "이미 등록된 새입니다."
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        real_no = BIRD_MAP.get(bird_name)
        new_row = pd.DataFrame({'No': [real_no], 'bird_name': [bird_name], 'date': [now]})
        updated_df = pd.concat([df, new_row], ignore_index=True)
        conn.update(spreadsheet=SHEET_URL, data=updated_df)
        return True
    except Exception as e: return str(e)

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
        system_instruction = """
        당신은 조류 전문가입니다. 사진을 분석하여 결과를 다음 형식으로 출력하세요:
        정답형식: 종명 | 판단근거
        [규칙]
        1. '새이름', '종명', '이름' 같은 단어를 정답 자리에 절대 쓰지 마세요.
        2. 구체적인 새의 이름(예: 참새, 까치)을 모른다면 차라리 '새 아님'이라고 하세요.
        3. 새가 아닌 사진이면 '새 아님 | 새를 찾을 수 없습니다'라고 출력하세요.
        """
        prompt = f"{system_instruction}"
        if user_doubt:
            prompt += f"\n사용자 반론: '{user_doubt}'. 이를 참고하여 다시 분석하세요."
        response = model.generate_content([prompt, image])
        return response.text.strip()
    except: return "Error | 분석 오류"

# --- [4. 메인 화면] ---
st.title("🦅 나의 탐조 도감")

df = get_data()

# ⭐️ [사이드바] 과별 수집 현황 (한글 데이터 직접 사용)
with st.sidebar:
    st.header("📊 과별 수집 현황")
    st.caption("전체 도감 대비 내가 모은 새")
    st.write("") 
    
    if FAMILY_TOTAL_COUNTS:
        my_family_counts = {}
        if not df.empty and FAMILY_MAP:
            df['family'] = df['bird_name'].map(FAMILY_MAP)
            my_family_counts = df['family'].value_counts().to_dict()
        
        sorted_families = sorted(FAMILY_TOTAL_COUNTS.keys())
        
        for family in sorted_families:
            total = FAMILY_TOTAL_COUNTS[family]
            count = my_family_counts.get(family, 0)
            
            highlight_class = "stat-highlight" if count > 0 else ""
            
            st.markdown(f"""
            <div class="sidebar-card">
                <div class="card-title">{family}</div>
                <div class="card-stat">
                    <span class="{highlight_class}">{count}</span> / {total}
                </div>
            </div>
            """, unsafe_allow_html=True)
            
    else:
        st.warning("⚠️ 족보 파일(data.csv)을 읽는 중 문제가 발생했습니다.")

# 메인 요약 박스 + 진행바
total_collected = len(df)
# 전체 종 수 (엑셀 행 개수)
total_species = TOTAL_SPECIES_COUNT if TOTAL_SPECIES_COUNT > 0 else 1
progress_percent = min((total_collected / total_species) * 100, 100)

st.markdown(f"""
    <div class="summary-box">
        <span class="summary-text">🌱 현재까지 모은 도감</span><br>
        <span class="summary-count">{total_collected}</span>
        <span class="summary-text"> 종 / 전체 {total_species}종</span>
    </div>
    <div class="progress-container">
        <div class="progress-bar" style="width: {progress_percent}%;"></div>
    </div>
""", unsafe_allow_html=True)

tab1, tab2, tab3 = st.tabs(["✍️ 직접 입력", "📸 AI 분석", "🛠️ 기록 관리"])

with tab1:
    st.subheader("새 이름 직접 기록")
    def add_manual():
        name = st.session_state.input_bird.strip()
        if name:
            res = save_data(name)
            if res is True: 
                st.toast(f"✅ {name} 등록 완료!")
                st.session_state.input_bird = ""
            else: st.error(res)
    st.text_input("새 이름을 입력하세요", key="input_bird", on_change=add_manual, placeholder="예: 참새")

with tab2:
    st.subheader("사진으로 이름 찾기")
    uploaded_files = st.file_uploader("새 사진 업로드 (터치 또는 클릭)", type=["jpg", "png", "jpeg"], accept_multiple_files=True)
    
    if 'ai_results' not in st.session_state: st.session_state.ai_results = {}
    
    if uploaded_files:
        for file in uploaded_files:
            if file.name not in st.session_state.ai_results:
                with st.spinner(f"🔍 {file.name} 분석 중..."):
                    st.session_state.ai_results[file.name] = analyze_bird_image(Image.open(file))
            
            raw = st.session_state.ai_results[file.name]
            if "|" in raw:
                parts = raw.split("|", 1)
                bird_name = parts[0].strip()
                reason = parts[1].strip()
            else:
                bird_name = raw.strip()
                reason = "상세 이유를 가져오지 못했습니다."
            
            invalid_keywords = ["새이름", "종명", "이름", "새 이름", "모름", "알수없음"]
            if bird_name in invalid_keywords:
                bird_name = "판독 불가"
                reason = "AI가 식별하지 못했습니다."

            is_valid_bird = True
            if bird_name in ["새 아님", "Error", "판독 불가"] or "오류" in bird_name:
                is_valid_bird = False

            with st.container(border=True):
                c1, c2 = st.columns([1, 1.5])
                with c1: st.image(file, use_container_width=True)
                with c2:
                    if is_valid_bird:
                        st.markdown(f"### **{bird_name}**")
                        st.markdown(f"**🔍 판단 이유**")
                        st.info(reason)
                        if st.button(f"도감에 등록하기", key=f"reg_{file.name}", type="primary", use_container_width=True):
                            res = save_data(bird_name)
                            if res is True: 
                                st.balloons()
                                st.toast(f"🎉 {bird_name} 등록 성공!")
                                st.rerun()
                            else: st.error(res)
                    else:
                        st.warning(f"⚠️ **{bird_name}**")
                        st.write(reason)

                    st.divider()
                    c_ask1, c_ask2 = st.columns([0.7, 0.3])
                    user_opinion = c_ask1.text_input("의견", key=f"doubt_{file.name}", placeholder="예: 말똥가리 아냐?", label_visibility="collapsed")
                    if c_ask2.button("재분석", key=f"ask_{file.name}", use_container_width=True):
                        if user_opinion:
                            with st.spinner("재분석 중..."):
                                st.session_state.ai_results[file.name] = analyze_bird_image(Image.open(file), user_opinion)
                                st.rerun()

with tab3:
    st.subheader("데이터 관리")
    if not df.empty:
        to_delete = st.multiselect("삭제할 기록 선택", options=df['bird_name'].tolist(), placeholder="도감에서 삭제할 새 이름을 입력하세요")
        if to_delete:
            if st.button(f"🗑️ 선택한 {len(to_delete)}개 삭제하기", type="primary"):
                if delete_birds(to_delete) is True:
                    st.success("삭제되었습니다."); st.rerun()
    else: st.info("등록된 기록이 없습니다.")

st.divider()
st.subheader("📜 나의 탐조 목록")
if not df.empty:
    for index, row in df.iterrows():
        bird = row['bird_name']
        real_no = BIRD_MAP.get(bird, 9999)
        display_no = "??" if real_no == 9999 else real_no
        st.markdown(f"""
        <div style="display:flex; align-items:center; justify-content:flex-start; gap:12px; padding:8px 0; border-bottom:1px solid #eee;">
            <span style="font-size:1.1rem; font-weight:600; color:#555; min-width:30px;">{display_no}.</span>
            <span style="font-size:1.2rem; font-weight:bold; color:#333;">{bird}</span>
        </div>
        """, unsafe_allow_html=True)
else: st.caption("기록이 없습니다.")
