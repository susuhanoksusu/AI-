import streamlit as st
import google.generativeai as genai
from PIL import Image
import json
import os
import re
from datetime import datetime

# 1. 페이지 설정
st.set_page_config(page_title="M-CoT AI 수학 튜터", page_icon="🧮", layout="centered")

# --- 🔐 로그인 상태 관리 및 이어하기(Persistence) 시스템 ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_id = ""

if not st.session_state.logged_in:
    # 로그인 화면
    st.title("👤 학생 로그인")
    st.markdown("자신의 학번과 이름을 입력하고 **[🚀 시작하기]** 버튼을 눌러주세요.")
    
    user_id_input = st.text_input("학번/이름 입력 (예: 20401김철수)")
    
    if st.button("🚀 시작하기", use_container_width=True):
        user_input_clean = user_id_input.strip()
        
        # 형식 검사: 숫자 5자리 + 한글 2~4글자
        if not re.match(r'^\d{5}[가-힣]{2,4}$', user_input_clean):
            st.error("형식에 맞지 않습니다. 학번과 이름을 정확히 입력해주세요. (예: 20401김철수)")
        else:
            # [수정 포인트] 중복 차단 조건을 없애고, 기존 유저면 이어하기 처리
            st.session_state.user_id = user_input_clean
            st.session_state.logged_in = True
            
            # 기존 기록 파일이 있는지 미리 확인해서 안내 메시지 띄우기 준비
            check_file = f"chat_history_{user_input_clean}.json"
            if os.path.exists(check_file):
                st.toast(f"🔄 {user_input_clean} 학생, 이전 대화 기록을 불러왔습니다!")
                
            st.rerun()
    
    st.stop() # 로그인 전에는 이 아래의 챗봇 코드가 절대 실행되지 않음

# ----------------------------------------------------
# 로그인 성공한 사용자 메인 화면
# ----------------------------------------------------
user_id = st.session_state.user_id
HISTORY_FILE = f"chat_history_{user_id}.json"

def load_all_chats():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_all_chats(chats):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(chats, f, ensure_ascii=False, indent=4)

def create_new_chat():
    new_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    st.session_state.all_chats[new_id] = {
        "title": f"📝 탐구 ({datetime.now().strftime('%m/%d %H:%M')})",
        "messages": [{"role": "assistant", "content": f"반갑습니다 **{user_id}** 학생! 새로운 문제를 함께 해결해 봅시다. 질문이나 사진을 올려주세요!"}]
    }
    st.session_state.current_chat_id = new_id

# 2. 구글 API 키 세팅
try:
    api_key = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=api_key)
except Exception:
    st.error("⚙️ 관리자 설정 오류: Streamlit Cloud 세팅에서 GEMINI_API_KEY를 등록해주세요.")
    st.stop()

# 3. M-CoT 프롬프트 v2.0
SYSTEM_INSTRUCTION = """
당신은 고등학교 수학I 및 수학II를 전담하는 전문적인 'M-CoT(단계별 수학적 추론) 기반 AI 튜터'입니다.
목표는 학생이 정답을 맞히는 것이 아니라, 복잡한 조건의 문장제를 논리적으로 분해하고 스스로 사고하는 힘을 기르도록 돕는 것입니다.

[절대 준수 원칙]
1. 어떠한 경우에도 최종 정답이나 전체 풀이 과정을 한 번에 제공하지 마십시오.
2. 한 번의 답변에는 반드시 '단 하나의 질문'만 던지고 학생의 답변을 기다리십시오.
3. 학생이 틀리면 "틀렸어" 대신 인지적 힌트(비계)를 제공하십시오.
4. 학생이 문제 사진이나 손글씨 풀이 사진을 업로드하면, 이미지 속 수식을 정확히 해독하고 오류를 짚어주거나 [Step 1] 질문부터 시작하십시오.
"""

# 4. 데이터 초기화 (기존 유저면 HISTORY_FILE에서 대화 내역이 자동으로 로드됨)
if "all_chats" not in st.session_state:
    st.session_state.all_chats = load_all_chats()

if "current_chat_id" not in st.session_state:
    if st.session_state.all_chats:
        st.session_state.current_chat_id = list(st.session_state.all_chats.keys())[-1]
    else:
        create_new_chat()
        save_all_chats(st.session_state.all_chats)

# 대화방 개별 삭제 함수
def delete_chat(chat_id_to_delete):
    if chat_id_to_delete in st.session_state.all_chats:
        del st.session_state.all_chats[chat_id_to_delete]
        
        if st.session_state.current_chat_id == chat_id_to_delete:
            if st.session_state.all_chats: 
                st.session_state.current_chat_id = list(st.session_state.all_chats.keys())[-1]
            else: 
                create_new_chat()
                
        save_all_chats(st.session_state.all_chats)

# 5. 왼쪽 사이드바 (학생 전용 제어판)
with st.sidebar:
    st.markdown(f"### 👤 접속자: **{user_id}**")
    
    # 로그아웃 버튼 (누르면 서버에서 해당 학생 파일 완전 삭제 및 초기화)
    if st.button("🚪 로그아웃 (기록 완전 삭제)", use_container_width=True):
        if os.path.exists(HISTORY_FILE):
            os.remove(HISTORY_FILE) # 서버에서 파일 물리적 삭제
            
        st.session_state.logged_in = False
        st.session_state.user_id = ""
        st.session_state.all_chats = {} 
        st.rerun()

    st.markdown("---")
    
    if st.button("➕ 새 대화 시작", use_container_width=True):
        create_new_chat()
        save_all_chats(st.session_state.all_chats)
        st.rerun()

    st.markdown("---")
    st.subheader("💬 나의 대화 기록")

    for cid in reversed(list(st.session_state.all_chats.keys())):
        col1, col2 = st.columns([4, 1])
        
        chat_title = st.session_state.all_chats[cid]["title"]
        if cid == st.session_state.current_chat_id:
            chat_title = f"▶️ {chat_title}"
            
        with col1:
            if st.button(chat_title, key=f"btn_{cid}", use_container_width=True):
                st.session_state.current_chat_id = cid
                st.rerun()
        with col2:
            if st.button("❌", key=f"del_{cid}"):
                delete_chat(cid)
                st.rerun()

# 6. 메인 화면 출력
st.title("🧠 M-CoT AI 수학 튜터")

if st.session_state.current_chat_id not in st.session_state.all_chats:
    create_new_chat()

current_messages = st.session_state.all_chats[st.session_state.current_chat_id]["messages"]

for msg in current_messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

uploaded_file = st.file_uploader("📸 문제/풀이 사진 업로드 (선택사항)", type=["jpg", "jpeg", "png"])
if uploaded_file is not None:
    st.image(uploaded_file, caption="업로드 대기 중인 이미지", width=300)

# 7. 질문 입력 및 답변 처리
if prompt := st.chat_input("AI 튜터의 질문에 답하거나 추가 질문을 입력하세요!"):
    
    with st.chat_message("user"):
        st.markdown(prompt)
    current_messages.append({"role": "user", "content": prompt})

    if len(current_messages) == 3:
        st.session_state.all_chats[st.session_state.current_chat_id]["title"] = f"🔍 {prompt[:10]}..."

    with st.spinner("AI 튜터가 생각하는 중입니다..."):
        try:
            model = genai.GenerativeModel(model_name="gemini-2.5-flash", system_instruction=SYSTEM_INSTRUCTION)
            
            chat_history = []
            for msg in current_messages[:-1]:
                role = "user" if msg["role"] == "user" else "model"
                chat_history.append({"role": role, "parts": [msg["content"]]})
            
            chat = model.start_chat(history=chat_history)
            
            # 세션에 이번 대화방에서 이미지를 보낸 적이 있는지 기록하는 변수 추가
            image_sent_key = f"image_sent_{st.session_state.current_chat_id}"
            
            if uploaded_file is not None and not st.session_state.get(image_sent_key, False):
                # 이미지가 있고, 아직 이 방에서 보낸 적이 없을 때만 사진 묶어서 전송
                img = Image.open(uploaded_file)
                response = chat.send_message([prompt, img])
                st.session_state[image_sent_key] = True # 이제 보냈다고 체크!
            else:
                # 사진이 화면에 남아있어도, 이미 보낸 적이 있으면 텍스트만 가볍게 전송
                response = chat.send_message(prompt)
            
            with st.chat_message("assistant"):
                st.markdown(response.text)
            current_messages.append({"role": "assistant", "content": response.text})
            
            st.session_state.all_chats[st.session_state.current_chat_id]["messages"] = current_messages
            save_all_chats(st.session_state.all_chats)
            st.rerun()
            
        except Exception as e:
            st.error(f"오류가 발생했습니다: {e}")
