import streamlit as st
import google.generativeai as genai
from PIL import Image
import json
import os
from datetime import datetime

# 1. 페이지 설정
st.set_page_config(page_title="M-CoT AI 수학 튜터", page_icon="🧮", layout="centered")

# 💾 [연구대회 가산점 포인트] 파일 기반 대화 기록 저장/로드 함수 (새로고침 방어)
HISTORY_FILE = "chat_history.json"

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

# 2. Streamlit 금고(Secrets)에서 안전하게 API Key 로드
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
4. 학생이 문제 사진(이미지)이나 손글씨 풀이 사진을 업로드하면, 이미지 속 텍스트와 수식을 정확히 해독(OCR)한 후, 정답을 주지 말고 오답이 있는 부분을 짚어주거나 [Step 1: 언어적 해독] 단계의 첫 질문부터 시작하십시오.
"""

# 🚀 4. 데이터 초기화 (전체 대화 로드)
if "all_chats" not in st.session_state:
    st.session_state.all_chats = load_all_chats()

# 현재 선택된 대화방 ID 설정 (없으면 새로 생성)
if "current_chat_id" not in st.session_state:
    if st.session_state.all_chats:
        # 기존에 저장된 마지막 대화방을 불러옴
        st.session_state.current_chat_id = list(st.session_state.all_chats.keys())[-1]
    else:
        # 아예 처음 켠 경우 새 대화방 생성
        new_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        st.session_state.current_chat_id = new_id
        st.session_state.all_chats[new_id] = {
            "title": "💡 새로운 수학 탐구",
            "messages": [{"role": "assistant", "content": "반갑습니다! 오늘 함께 고민해볼 수학I 또는 수학II 문장제 문제를 사진으로 찍어 올리거나 텍스트로 입력해 주세요. 가장 먼저 주의 깊게 봐야 할 제약 조건부터 함께 찾아봅시다!"}]
        }
        save_all_chats(st.session_state.all_chats)

# 📱 5. 왼쪽 사이드바 (Gemini 스타일 기록창) 구현
st.sidebar.title("💬 대화 기록창")

# [새 대화 시작] 버튼
if st.sidebar.button("➕ 새 대화 시작", use_container_width=True):
    new_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    st.session_state.all_chats[new_id] = {
        "title": f"📝 수학 대화 ({datetime.now().strftime('%m/%d %H:%M')})",
        "messages": [{"role": "assistant", "content": "반갑습니다! 새로운 문제를 함께 해결해 봅시다. 질문이나 사진을 공유해 주세요!"}]
    }
    st.session_state.current_chat_id = new_id
    save_all_chats(st.session_state.all_chats)
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.subheader("지난 대화 목록")

# 과거 대화 리스트 버튼들 생성 (최신순 정렬)
for cid in reversed(list(st.session_state.all_chats.keys())):
    chat_title = st.session_state.all_chats[cid]["title"]
    # 현재 보고 있는 대화방은 강조 표시
    if cid == st.session_state.current_chat_id:
        chat_title = f"▶️ {chat_title}"
        
    if st.sidebar.button(chat_title, key=cid, use_container_width=True):
        st.session_state.current_chat_id = cid
        st.rerun()

# 6. 메인 화면 레이아웃 및 대화 출력
st.title("🧠 2026 수능형 문장제 완파! M-CoT AI 수학 튜터")
st.caption("정답은 알려주지 않아요! 사진을 찍어 올리거나 질문을 던져보세요.")

# 현재 활성화된 대화방의 메시지 가져오기
current_messages = st.session_state.all_chats[st.session_state.current_chat_id]["messages"]

# 대화 내용 화면에 출력
for msg in current_messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# 📌 이미지 업로드 버튼
uploaded_file = st.file_uploader("📸 문제 또는 풀이 사진을 업로드하려면 여기를 누르세요 (선택사항)", type=["jpg", "jpeg", "png"])

if uploaded_file is not None:
    st.image(uploaded_file, caption="업로드된 이미지", use_container_width=True)

# 7. 학생 입력 및 Gemini 3.5-flash 답변 처리
if prompt := st.chat_input("AI 튜터의 질문에 답하거나 추가 질문을 입력하세요!"):
    
    # 학생 입력 저장 및 출력
    with st.chat_message("user"):
        st.markdown(prompt)
    current_messages.append({"role": "user", "content": prompt})

    # 첫 질문 시 대화방 타이틀을 학생이 입력한 질문 요약으로 자동 변경
    if len(current_messages) == 3: # 안내문(1) + 유저(2) + 튜터(3) 직전 단계
        st.session_state.all_chats[st.session_state.current_chat_id]["title"] = f"🔍 {prompt[:12]}..."

    try:
        # 안정적이고 무제한인 gemini-3.5-flash 모델 사용
        model = genai.GenerativeModel(model_name="gemini-3.5-flash", system_instruction=SYSTEM_INSTRUCTION)
        
        # 대화 맥락 빌드
        chat_history = []
        for msg in current_messages[:-1]:
            role = "user" if msg["role"] == "user" else "model"
            chat_history.append({"role": role, "parts": [msg["content"]]})
        
        chat = model.start_chat(history=chat_history)
        
        # 이미지 포함 여부에 따른 전송
        if uploaded_file is not None:
            img = Image.open(uploaded_file)
            response = chat.send_message([prompt, img])
        else:
            response = chat.send_message(prompt)
        
        # 튜터 답변 저장 및 출력
        with st.chat_message("assistant"):
            st.markdown(response.text)
        current_messages.append({"role": "assistant", "content": response.text})
        
        # 💾 대화가 끝나면 로컬 파일에 즉시 영구 저장 (새로고침 완벽 방어)
        st.session_state.all_chats[st.session_state.current_chat_id]["messages"] = current_messages
        save_all_chats(st.session_state.all_chats)
        st.rerun()
        
    except Exception as e:
        st.error(f"오류가 발생했습니다: {e}")
