import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import google.generativeai as genai
from PIL import Image
from datetime import datetime
import os

# --- [1. 기본 설정] ---
st.set_page_config(page_title="탐조 도감", layout="wide", page_icon="📚")

# --- [2. 데이터 및 설정] ---
BADGE_INFO = {
    "🐣 탐조 입문": {"tier": "rare", "desc": "첫 번째 새를 기록했습니다! 시작이 반입니다.", "rank": 1},
    "🌱 새싹 탐조가": {"tier": "rare", "desc": "5마리의 새를 만났습니다.", "rank": 1.5},
    "🥉 아마추어 탐조가": {"tier": "rare", "desc": "20마리 수집! 동네 새들은 다 꿰뚫고 계시군요.", "rank": 2},
    "🥈 베테랑 탐조가": {"tier": "epic", "desc": "50마리 수집! 어디 가서 '새 좀 안다'고 하셔도 됩니다.", "rank": 3},
    "🥇 마스터 탐조가": {"tier": "unique", "desc": "100마리 수집! 진정한 고수의 반열에 올랐습니다.", "rank": 4},
    "💎 전설의 탐조가": {"tier": "legendary", "desc": "300마리 수집! 당신은 살아있는 도감 그 자체입니다.", "rank": 5},
    
    "🌈 다채로운 시선": {"tier": "unique", "desc": "15개 이상의 서로 다른 '과(Family)'를 기록했습니다. 편식 없는 탐조!", "rank": 4},
    "🦆 호수의 지배자": {"tier": "epic", "desc": "오리과 10마리 이상 수집", "rank": 3},
    "🦅 하늘의 제왕": {"tier": "unique", "desc": "맹금류(수리과/매과) 5마리 이상 수집. 하늘의 포식자들을 정복했습니다.", "rank": 4},
    "🦢 우아한 백로": {"tier": "epic", "desc": "백로/왜가리과 5마리 이상 수집", "rank": 3},
    "🌲 숲속의 드러머": {"tier": "epic", "desc": "딱따구리과 3마리 이상 수집", "rank": 3},
    "🦉 밤의 추적자": {"tier": "unique", "desc": "올빼미과(부엉이 등) 발견. 밤에도 탐조하는 열정!", "rank": 4},
    "🧠 똑똑한 새": {"tier": "rare", "desc": "까마귀과(까치, 어치 등) 3마리 이상 수집", "rank": 2},
    "👔 넥타이 신사": {"tier": "rare", "desc": "박새과 3마리 이상 수집", "rank": 2},
    "🏖️ 갯벌의 나그네": {"tier": "epic", "desc": "도요/물떼새과 5마리 이상 수집", "rank": 3},
    "🍀 럭키 탐조가": {"tier": "unique", "desc": "멸종위기종 첫 발견! 엄청난 행운입니다.", "rank": 4},
    "🛡️ 자연의 수호자": {"tier": "legendary", "desc": "멸종위기종 5마리 이상 기록. 당신은 자연의 지킴이입니다.", "rank": 5},
}

TIER_STYLE = {
    "rare":      {"color": "#1565C0", "bg": "#E3F2FD", "icon": "🔹", "label": "Rare"},
    "epic":      {"color": "#6A1B9A", "bg": "#F3E5F5", "icon": "🔮", "label": "Epic"},
    "unique":    {"color": "#EF6C00", "bg": "#FFF3E0", "icon": "🌟", "label": "Unique"},
    "legendary": {"color": "#2E7D32", "bg": "#E8F5E9", "icon": "🌿", "label": "Legendary"},
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

# CSS
hide_streamlit_style = """
<style>
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
.stApp {padding-top: 10px;}

.summary-box {
    padding: 20px; border-radius: 15px; 
    background: linear-gradient(135deg, #e8f5e9 0%, #c8e6c9 100%);
    margin-bottom: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); text-align: left;
}
.summary-text { font-size: 1.1rem; color: #2e7d32; font-weight: bold; }
.summary-count { font-size: 2rem; font-weight: 800; color: #1b5e20; }

.sidebar-badge-container { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom:
