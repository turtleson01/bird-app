import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import google.generativeai as genai
from PIL import Image
from datetime import datetime
import os
import time

# --- [1. 기본 설정 & CSS] ---
st.set_page_config(page_title="탐조 도감", layout="wide", page_icon="🦅")

# CSS: 배지 스타일 (버튼처럼 보이게 커서 변경)
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
            
            /* ⭐️ 배지 스타일 (클릭 가능하게 변경) */
            /* Streamlit 버튼 스타일 덮어쓰기 */
            div.stButton > button.badge-btn {
                border-radius: 20px !important;
                padding: 4px 12px !important;
                font-size: 0.85rem !important;
                font-weight: 800 !important;
                margin: 2px !important;
                height: auto !important;
                line-height: 1.2 !important;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1) !important;
                border-width: 2px !important;
                transition: transform 0.1s !important;
            }
            div.stButton > button.badge-btn:active { transform: scale(0.95); }
            div.stButton > button.badge-btn:focus { outline: none; box-shadow: none; }

            /* 등급별 색상 (버튼 텍스트/배경/테두리 강제 적용) */
            /* Rare (파랑) */
            div.stButton > button.badge-rare { 
                background-color: #E3F2FD !important; color: #1565C0 !important; border-color: #90CAF9 !important; 
            }
            /* Epic (보라) */
            div.stButton > button.badge-epic { 
                background-color: #F3E5F5 !important; color: #7B1FA2 !important; border-color: #CE93D8 !important; 
            }
            /* Unique (노랑) */
            div.stButton > button.badge-unique { 
                background-color: #FFFDE7 !important; color: #F9A825 !important; border-color: #FFF59D !important; 
            }
            /* Legendary (초록) */
            div.stButton > button.badge-legendary { 
                background-color: #E8F5E9 !important; color: #2E7D32 !important; border-color: #A5D6A7 !important; 
            }

            /* 희귀종 태그 */
            .rare-tag { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: bold; margin-left: 8px; vertical-align: middle; }
            .tag-class1 { background-color: #ffebee; color: #c62828; border: 1px solid #ef9a9a; }
            .tag-class2 { background-color: #fff3e0; color: #ef6c00; border: 1px solid #ffcc80; }
            .tag-natural { background-color: #e8f5e9; color: #2e7d32; border: 1px solid #a5d6a7; }

            /* 기타 UI */
            .sidebar-card { background-color: white; border: 1px solid #e0e0e0; border-radius: 8px; padding: 12px 15px; margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
            .stat-highlight { color: #2e7d32; font-weight: 700; }
            
            /* 일반 버튼 (등록 버튼 등) */
            div.stButton > button[kind="primary"] { background: linear-gradient(45deg, #64B5F6, #90CAF9); color: white !important; border: none; border-radius: 12px; padding: 0.6rem 1rem; font-weight: 700; width: 100%; box-shadow: 0 3px 5px rgba(0,0,0,0.1); }
            
            [data-testid="stFileUploaderDropzone"] button { display: none !important; }
            [data-testid="stFileUploaderDropzone"] section { cursor: pointer; }
            
            /* 버튼 컨테이너 정렬 */
            .element-container:has(> .stButton) { display: inline-block; width: auto !important; margin-right: 5px; }
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

BADGE_INFO = {
    "🐣 탐조 입문": {"tier": "rare", "desc": "첫 번째 새를 기록했습니다!", "rank": 1},
    "🥉 초보 탐조가": {"tier": "rare", "desc": "10마리 이상 수집", "rank": 2},
    "🥈 중급 탐조가": {"tier": "epic", "desc": "30마리 이상 수집", "rank": 3},
    "🥇 마스터 탐조가": {"tier": "unique", "desc": "50마리 이상 수집", "rank": 4},
    "💎 전설의 탐조가": {"tier": "legendary", "desc": "100마리 이상 수집", "rank": 5},
    "🦆 오리 박사": {"tier": "epic", "desc": "오리과 5마리 이상 수집", "rank": 3},
    "🦅 하늘의 제왕": {"tier": "unique", "desc": "맹금류(수리과) 3마리 이상 수집", "rank": 4},
    "🦢 우아한 백로": {"tier": "epic", "desc": "백로과 3마리 이상 수집", "rank": 3},
    "🌲 숲속의 드러머": {"tier": "epic", "desc": "딱따구리과 2마리 이상 수집", "rank": 3},
    "🍀 럭키 탐조가": {"tier": "unique", "desc": "멸종위기종 첫 발견!", "rank": 4},
    "🛡️ 자연의 수호자": {"tier": "legendary", "desc": "멸종위기종 5마리 이상 발견", "rank": 5},
}

RARE_BIRDS = {
    "황새": "class1", "저어새": "class1", "노랑부리백로": "class1", "매": "class1", "흰꼬리수리": "class1",
    "참수리": "class1", "검독수리": "class1", "두루미": "class1", "넓적부리도요": "class1", "청다리도요사촌": "class1",
    "크낙새": "class1", "혹고니": "class1", "호사비오리": "class1", "먹황새": "class1",
    "개리": "class2", "큰기러기": "class2", "흑기러기": "class2", "고니": "class2", "큰고니": "class2",
    "가창오리": "class2", "붉은가슴흰죽지": "class2", "검은머리물떼새": "class2", "알락꼬리마도요": "class2",
    "뿔쇠오리": "class2", "흑비둘기": "class2", "섬개개비": "class2", "붉은배새매": "class2",
    "수리부엉이": "class2", "참매": "class2", "까막딱따구리": "class2", "팔색조": "class2",
    "솔개": "class2", "큰말똥가리": "class2", "독수리": "class2", "새호리기": "class2", "물수리": "class2",
    "잿빛개구리매": "class2", "긴점박이올빼미": "class2", "쇠부엉이": "class2", "올빼미": "class2",
    "조롱이": "class2", "털발말똥가리": "class2", "흰목물떼새": "class2", "뜸부기": "class2",
    "재두루미": "class2", "흑두루미": "class2", "검은머리갈매기": "class2", "무당새": "class2",
    "긴꼬리딱새": "class2", "삼광조": "class2", "양비둘기": "class2", "따오기": "class2", "붉은해오라기": "class2",
    "원앙": "natural", "황조롱이": "natural", "소쩍새": "natural", "솔부엉이": "natural",
    "큰소쩍새": "natural", "어치": "natural" 
}
RARE_LABEL = { "class1": "👑 멸종위기 1급", "class2": "⭐ 멸종위기 2급", "natural": "🌿 천연기념물" }

@st.cache_data
def load_bird_map():
    file_path = "data.csv"
    if not os.path.exists(file_path): return {}, {}, 0, {}
    encodings = ['utf-8-sig', 'cp949', 'euc-kr']
    for enc in encodings:
        try:
            df = pd.read_csv(file_path, skiprows=2, header=None, encoding=enc)
            if df.shape[1] < 15: continue
            bird_data = df.iloc[:, [4, 14]].copy()
            bird_data.columns = ['name', 'family']
            bird_data = bird_data.dropna()
            bird_data['name'] = bird_data['name'].astype(str).str.strip()
            bird_data['family'] = bird_data['family'].astype(str).str.strip()
            filter_keywords = ['대표국명', '국명', 'Name', 'Family', '과']
            bird_data = bird_data[~bird_data['family'].isin(filter_keywords)]
            total_species_count = len(bird_data)
            bird_list = bird_data['name'].tolist()
            name_to_no = {name: i + 1 for i, name in enumerate(bird_list)}
            name_to_family = dict(zip(bird_data['name'], bird_data['family']))
            family_total_counts = bird_data['family'].value_counts().to_dict()
            return name_to_no, name_to_family, total_species_count, family_total_counts
        except Exception as e: continue
    return {}, {}, 0, {}

BIRD_MAP, FAMILY_MAP, TOTAL_SPECIES_COUNT, FAMILY_TOTAL_COUNTS = load_bird_map()
conn = st.connection("gsheets", type=GSheetsConnection)

def get_data():
    try:
        df = conn.read(spreadsheet=SHEET_URL, ttl=0)
        expected_cols = ['No', 'bird_name', 'sex', 'date']
        if df.empty: return pd.DataFrame(columns=expected_cols)
        if 'sex' not in df.columns: df['sex'] = '미구분'
        if BIRD_MAP and 'bird_name' in df.columns:
            df['real_no'] = df['bird_name'].apply(lambda x: BIRD_MAP.get(str(x).strip(), 9999))
            df = df.sort_values(by='real_no', ascending=True)
        return df
    except: return pd.DataFrame(columns=['No', 'bird_name', 'sex', 'date'])

def save_data(bird_name, sex, current_df):
    bird_name = bird_name.strip()
    if bird_name not in BIRD_MAP: return f"⚠️ '{bird_name}'은(는) 목록에 없습니다."
    if not current_df.empty and bird_name in current_df['bird_name'].values: return "이미 등록된 새입니다."
    try:
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        real_no = BIRD_MAP.get(bird_name)
        new_row = pd.DataFrame({'No': [real_no], 'bird_name': [bird_name], 'sex': [sex], 'date': [now]})
        updated_df = pd.concat([current_df, new_row], ignore_index=True)
        conn.update(spreadsheet=SHEET_URL, data=updated_df)
        return True
    except Exception as e: return str(e)

def delete_birds(bird_names_to_delete, current_df):
    try:
        df = current_df[~current_df['bird_name'].isin(bird_names_to_delete)]
        conn.update(spreadsheet=SHEET_URL, data=df)
        return True
    except Exception as e: return str(e)

def calculate_badges(df):
    badges = []
    count = len(df)
    if count >= 1: badges.append("🐣 탐조 입문")
    if count >= 10: badges.append("🥉 초보 탐조가")
    if count >= 30: badges.append("🥈 중급 탐조가")
    if count >= 50: badges.append("🥇 마스터 탐조가")
    if count >= 100: badges.append("💎 전설의 탐조가")
    
    if not df.empty and FAMILY_MAP:
        df['family'] = df['bird_name'].map(FAMILY_MAP)
        fam_counts = df['family'].value_counts()
        if fam_counts.get('오리과', 0) >= 5: badges.append("🦆 오리 박사")
        if fam_counts.get('수리과', 0) >= 3: badges.append("🦅 하늘의 제왕")
        if fam_counts.get('백로과', 0) >= 3: badges.append("🦢 우아한 백로")
        if fam_counts.get('딱다구리과', 0) >= 2: badges.append("🌲 숲속의 드러머")
    
    rare_count = 0
    for name in df['bird_name']:
        if name in RARE_BIRDS: rare_count += 1
    if rare_count >= 1: badges.append("🍀 럭키 탐조가")
    if rare_count >= 5: badges.append("🛡️ 자연의 수호자")
    return badges

# --- [3. AI 분석] ---
def analyze_bird_image(image, user_doubt=None):
    try:
        genai.configure(api_key=API_KEY)
        model = genai.GenerativeModel('gemini-2.5-flash') 
        system_instruction = "당신은 조류 전문가입니다. 사진을 분석하여 '종명 | 판단근거' 형식으로 답하세요. 구체적인 종을 모르면 '새 아님'이라고 하세요."
        prompt = f"{system_instruction}"
        if user_doubt: prompt += f"\n사용자 반론: '{user_doubt}'. 재분석하세요."
        response = model.generate_content([prompt, image])
        return response.text.strip()
    except: return "Error | 분석 오류"

# --- [4. 메인 화면] ---
st.title("🦅 탐조 도감")

df = get_data()

# 배지 계산 및 축하 로직
current_badges = calculate_badges(df)

if 'my_badges' not in st.session_state:
    st.session_state['my_badges'] = current_badges

new_badges = [b for b in current_badges if b not in st.session_state['my_badges']]
if new_badges:
    st.balloons()
    for nb in new_badges:
        st.toast(f"🏆 새로운 배지 획득! : {nb}", icon="🎉")
    st.session_state['my_badges'] = current_badges

# 사이드바
with st.sidebar:
    st.header("🏆 나의 배지")
    
    if current_badges:
        sorted_badges = sorted(current_badges, key=lambda x: BADGE_INFO.get(x, {}).get('rank', 0), reverse=True)
        top_badges = sorted_badges[:3]
        other_badges = sorted_badges[3:]
        
        # ⭐️ 배지를 버튼으로 그리는 함수
        def draw_badge_button(badge_name, key_suffix):
            info = BADGE_INFO.get(badge_name, {"tier": "rare", "desc": "설명 없음"})
            tier = info['tier']
            # 각 배지를 버튼으로 생성
            if st.button(badge_name, key=f"btn_{badge_name}_{key_suffix}", help="클릭하여 설명 보기"):
                # 클릭 시 토스트 메시지로 설명 출력
                st.toast(f"**{badge_name}**\n\n✅ 달성 조건: {info['desc']}", icon="🏅")

            # 버튼에 색상 클래스 입히기 (JS 사용)
            # Streamlit 버튼은 class를 직접 못 넣으므로 JS로 후처리하는 트릭 대신
            # 그냥 type="secondary"를 쓰고 위에 정의한 CSS Selector(:has)로 색을 입히는게 안전하지만
            # 여기서는 버튼 텍스트를 인식하여 CSS class를 매핑하는 방식을 위해
            # 각 버튼 생성 직후에 해당 버튼을 꾸미는 스타일을 주입하는 방식 사용
            
            # (CSS로 버튼 스타일 강제 적용을 위해 위쪽 style 태그에서 정의한 클래스 사용)
            # 다만 Streamlit Python 코드만으로는 특정 버튼에 클래스를 1:1로 매핑하기 어려우므로
            # 여기서는 버튼의 '텍스트'를 기반으로 색상을 입히는 CSS를 동적으로 생성하지 않고
            # 위에서 정의한 .stButton button[...innerText...] 트릭 대신
            # 간단하게 버튼을 누르면 반응하는 기능에 집중하고,
            # 색상은 "모든 버튼에 적용" 되거나 "순서대로 적용"되는 한계가 있어
            # 커스텀 HTML 버튼 대신 Streamlit Native Button을 사용하되
            # 최대한 깔끔하게 보이도록 CSS에서 `div.stButton > button` 전역 스타일을 잡았습니다.
            
            # ⭐️ 등급별 색상을 개별 적용하기 위한 트릭 (data-testid 등 활용 불가하므로)
            # 여기서는 복잡도를 낮추기 위해 'Javascript' 주입 없이
            # CSS의 :nth-child 등을 쓰기도 어려우므로
            # **HTML/CSS로 배지를 그리고, 클릭 기능은 포기**하거나
            # **버튼으로 만들고 색상은 통일**하거나 해야 하는데
            # 요청하신 "클릭 시 설명"을 위해 **버튼**을 택했습니다.
            # (등급별 색상은 버튼 텍스트에 따라 CSS로 입히기 까다로워 약간의 JS가 필요하지만
            # Streamlit Cloud 호환성을 위해 JS 제외하고, 대신 CSS에서
            # '모든 배지 버튼'을 예쁘게 꾸미는 것으로 타협하거나
            # st.markdown(HTML) + JavaScript로 구현해야 완벽합니다.)
            
            # **[타협안]**: 현재 코드는 버튼 기능(클릭 시 설명)에 집중하고,
            # 색상은 CSS 상단에서 정의한 `badge-rare` 등이 적용되지 않습니다 (Native Button이라서).
            # 대신 버튼에 이모지(🥇, 🥈)가 있어서 등급 구분이 됩니다.
            pass

        # 실제 버튼 그리기 (버튼 위 CSS 적용을 위해 컨테이너 사용)
        # ⭐️ 자바스크립트 없이 버튼별 색상을 입히는 건 불가능하므로
        # 여기서는 HTML 태그(모양+색상) + 투명 버튼(클릭용)을 겹치는 고급 기술 대신
        # **가장 확실한 방법: st.button을 쓰되, 색상은 통일하고 등급은 이모지로 구분**합니다.
        # (아까 CSS에서 .badge-rare 등을 정의했지만 st.button에는 적용이 안 됩니다.)
        
        st.write("*(배지를 클릭하면 설명이 나옵니다)*")
        st.write("---")
        
        for b in top_badges:
            draw_badge_button(b, "top")
            
        if other_badges:
            with st.expander("🔽 보유 배지 전체 보기"):
                for b in other_badges:
                    draw_badge_button(b, "other")
    else:
        st.caption("아직 배지가 없습니다.")

    st.divider()
    
    st.header("📊 과별 수집 현황")
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
            </div>""", unsafe_allow_html=True)

total_collected = len(df)
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

tab1, tab2, tab3 = st.tabs(["✍️ 종 추가하기", "📸 AI 분석", "🛠️ 기록 관리"])

with tab1:
    st.subheader("종 추가하기")
    sex_selection = st.radio("성별", ["미구분", "수컷", "암컷"], horizontal=True, key="manual_sex")
    def add_manual():
        name = st.session_state.input_bird.strip()
        sex = st.session_state.manual_sex 
        st.session_state.input_bird = ""
        if name:
            res = save_data(name, sex, df)
            if res is True: 
                msg = f"✅ {name}({sex}) 등록 완료!"
                if name in RARE_BIRDS: msg += f" ({RARE_LABEL.get(RARE_BIRDS[name])} 발견!)"
                st.toast(msg); st.rerun()
            else: st.toast(f"🚫 {res}")
    st.text_input("새 이름을 입력하세요", key="input_bird", on_change=add_manual, placeholder="예: 참새")

with tab2:
    st.subheader("사진으로 이름 찾기")
    uploaded_files = st.file_uploader("새 사진 업로드", type=["jpg", "png", "jpeg"], accept_multiple_files=True)
    
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
            if bird_name in invalid_keywords: bird_name = "판독 불가"
            is_valid_bird = True
            if bird_name in ["새 아님", "Error", "판독 불가"] or "오류" in bird_name: is_valid_bird = False

            with st.container(border=True):
                c1, c2 = st.columns([1, 1.5])
                with c1: st.image(file, use_container_width=True)
                with c2:
                    if is_valid_bird:
                        display_name = bird_name
                        if bird_name in RARE_BIRDS:
                            rarity_code = RARE_BIRDS[bird_name]
                            tag_text = RARE_LABEL.get(rarity_code, "")
                            display_name += f" <span style='color:#e65100; font-size:0.9em;'>{tag_text}</span>"
                        
                        st.markdown(f"### **{display_name}**", unsafe_allow_html=True)
                        st.markdown(f"**🔍 판단 이유**")
                        st.info(reason)
                        
                        col_sex, col_btn = st.columns([1, 1])
                        with col_sex:
                            ai_sex = st.radio("성별", ["미구분", "수컷", "암컷"], horizontal=True, key=f"sex_{file.name}", label_visibility="collapsed")
                        with col_btn:
                            if st.button(f"도감에 등록하기", key=f"reg_{file.name}", type="primary", use_container_width=True):
                                res = save_data(bird_name, ai_sex, df)
                                if res is True: 
                                    st.toast(f"🎉 {bird_name}({ai_sex}) 등록 성공!"); st.rerun()
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
                if delete_birds(to_delete, df) is True:
                    st.success("삭제되었습니다."); st.rerun()
    else: st.info("등록된 기록이 없습니다.")

st.divider()
st.subheader("📜 나의 탐조 목록")
if not df.empty:
    for index, row in df.iterrows():
        bird = row['bird_name']
        real_no = BIRD_MAP.get(bird, 9999)
        display_no = "??" if real_no == 9999 else real_no
        sex_info = row.get('sex', '미구분')
        sex_icon = ""
        if sex_info == '수컷': sex_icon = " <span style='color:blue; font-size:1rem;'>(♂)</span>"
        elif sex_info == '암컷': sex_icon = " <span style='color:red; font-size:1rem;'>(♀)</span>"
        
        rare_tag = ""
        if bird in RARE_BIRDS:
            rarity_code = RARE_BIRDS[bird]
            tag_class = f"tag-{rarity_code}"
            tag_text = RARE_LABEL.get(rarity_code, "").replace("👑 ", "").replace("⭐ ", "").replace("🌿 ", "")
            rare_tag = f"<span class='rare-tag {tag_class}'>{tag_text}</span>"
        
        st.markdown(f"""
        <div style="display:flex; align-items:center; justify-content:flex-start; gap:12px; padding:8px 0; border-bottom:1px solid #eee;">
            <span style="font-size:1.1rem; font-weight:600; color:#555; min-width:30px;">{display_no}.</span>
            <span style="font-size:1.2rem; font-weight:bold; color:#333;">{bird}{sex_icon}</span>
            {rare_tag}
        </div>
        """, unsafe_allow_html=True)
else: st.caption("기록이 없습니다.")
