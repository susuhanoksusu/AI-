import streamlit as st
from PIL import Image
import json
import os
import re
import base64
from io import BytesIO
from datetime import datetime
from supabase import create_client, Client

# --- 🆕 [LangGraph & LangChain 추가 부품] ---
from typing import TypedDict, List, Dict, Any
from langgraph.graph import StateGraph, END
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

# 1. 페이지 설정
st.set_page_config(page_title="M-CoT AI 수학 튜터", page_icon="🧮", layout="centered")

# --- 🌐 Supabase 클라우드 데이터베이스 연결 설정 ---
SUPABASE_URL = "https://jvwiwemizcvrbgjamuyu.supabase.co"
SUPABASE_KEY = "sb_publishable_r5TrFrkJjDxmX6dmn7uepw_9719X6yZ"

try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error(f"⚠️ 데이터베이스 연결 실패: {e}")

# ----------------------------------------------------
# 📂 학생 대화 기록 관리 필수 함수 (Supabase 클라우드 버전)
# ----------------------------------------------------

def load_all_chats():
    try:
        current_uid = st.session_state.get("user_id", "")
        response = supabase.table("student_chats").select("chats_data").eq("user_id", current_uid).execute()
        if response.data:
            return response.data[0]["chats_data"]
    except Exception as e:
        pass
    return {}

def save_all_chats(chats):
    try:
        current_uid = st.session_state.get("user_id", "")
        supabase.table("student_chats").upsert({
            "user_id": current_uid,
            "chats_data": chats
        }).execute()
    except Exception as e:
        st.error(f"💾 클라우드 저장 실패: {e}")

def create_new_chat():
    import datetime as dt
    kst_now = dt.datetime.now(dt.timezone(dt.timedelta(hours=9)))
    current_uid = st.session_state.get("user_id", "")
    
    new_id = kst_now.strftime("%Y%m%d_%H%M%S")
    st.session_state.all_chats[new_id] = {
        "title": f"📝 탐구 ({kst_now.strftime('%m/%d %H:%M')})",
        "messages": [{"role": "assistant", "content": f"반갑습니다 **{current_uid}** 학생! 새로운 문제를 함께 해결해 봅시다. 질문이나 사진을 올려주세요!"}]
    }
    st.session_state.current_chat_id = new_id

# --- 🔐 설정 파일 관리 (클라우드 DB 버전) ---
def load_settings():
    try:
        response = supabase.table("admin_settings").select("student_pw", "admin_pw").execute()
        if response.data:
            return response.data[0]
    except Exception as e:
        st.error(f"⚠️ DB에서 비밀번호를 불러오지 못했습니다: {e}")
    return {"student_pw": "1234", "admin_pw": "admin1234"}

def save_settings(settings_data):
    try:
        supabase.table("admin_settings").upsert({
            "id": 1, 
            "student_pw": settings_data["student_pw"],
            "admin_pw": settings_data["admin_pw"]
        }).execute()
        return True
    except Exception as e:
        st.error(f"💾 클라우드 비밀번호 동기화 실패: {e}")
        return False

app_settings = load_settings()

# --- 🔐 로그인 상태 관리 ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_id = ""
    st.session_state.is_admin = False

if not st.session_state.logged_in:
    st.title("👤 학생 로그인")
    st.markdown("자신의 학번/이름과 **비밀번호**를 입력해주세요.")
    
    user_id_input = st.text_input("학번/이름 (예: 20401김철수)")
    pw_input = st.text_input("비밀번호", type="password")
    
    if st.button("🚀 접속하기", use_container_width=True):
        user_input_clean = user_id_input.strip()
        
        if user_input_clean == "20000선생님":
            if pw_input == app_settings["admin_pw"]:
                st.session_state.user_id = "관리자"
                st.session_state.is_admin = True
                st.session_state.logged_in = True
                st.rerun()
            else:
                st.error("🚫 관리자 비밀번호가 틀렸습니다.")
        else:
            if not re.match(r'^\d{5}[가-힣]{2,4}$', user_input_clean):
                st.error("🚫 형식에 맞지 않습니다. (예: 20401김철수)")
            elif pw_input != app_settings["student_pw"]:
                st.error("🚫 학생 접속 비밀번호가 틀렸습니다. 선생님께 확인해주세요.")
            else:
                st.session_state.user_id = user_input_clean
                st.session_state.is_admin = False
                st.session_state.logged_in = True
                
                # 기존 클라우드 대화 기록 불러오기
                st.session_state.all_chats = load_all_chats()
                
                st.toast(f"✅ {user_input_clean} 학생, 환영합니다!")
                st.rerun()
    st.stop()

# --- 👑 관리자 전용 대시보드 ---
if st.session_state.is_admin:
    st.title("🛠️ 관리자 대시보드")
    
    st.subheader("🔑 접속 비밀번호 설정")
    col1, col2 = st.columns(2)
    with col1:
        new_student_pw = st.text_input("새로운 학생 접속 비밀번호", value=app_settings["student_pw"])
    with col2:
        new_admin_pw = st.text_input("새로운 관리자 비밀번호", value=app_settings["admin_pw"], type="password")
        
    if st.button("💾 비밀번호 변경 저장"):
        app_settings["student_pw"] = new_student_pw
        app_settings["admin_pw"] = new_admin_pw
        save_settings(app_settings)
        st.success("비밀번호가 성공적으로 변경되었습니다!")

    st.markdown("---")
    
    col_title, col_btn = st.columns([8, 2])
    with col_title:
        st.subheader("📡 학생 대화 기록 모니터링")
    with col_btn:
        if st.button("🔄 새로고침", use_container_width=True):
            st.rerun() 
            
    try:
        db_response = supabase.table("student_chats").select("user_id").execute()
        student_list = [row["user_id"] for row in db_response.data]
    except Exception as e:
        student_list = []
        st.error(f"학생 목록 로드 실패: {e}")
    
    if not student_list:
        st.info("아직 클라우드에 대화를 나눈 학생 기록이 없습니다.")
    else:
        selected_student = st.selectbox("👩‍🎓 기록을 열람할 학생을 선택하세요", options=student_list)

        if st.button(f"🚨 '{selected_student}' 학생 기록 영구 삭제", type="primary", use_container_width=True):
            st.session_state.show_confirm = selected_student

        if st.session_state.get("show_confirm") == selected_student:
            st.error(f"⚠️ **[최종 확인]** '{selected_student}' 학생의 모든 대화 기록이 데이터베이스에서 영구 삭제되며, 절대로 복구할 수 없습니다. 정말 진행하시겠습니까?")
            
            col_yes, col_no = st.columns(2)
            with col_yes:
                if st.button("🔥 네, 진짜로 삭제합니다", type="primary", use_container_width=True):
                    try:
                        supabase.table("student_chats").delete().eq("user_id", selected_student).execute()
                        st.session_state.show_confirm = None
                        st.toast(f"✅ {selected_student} 학생의 기록이 완전히 삭제되었습니다.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"⚠️ 삭제 실패: {e}")
            with col_no:
                if st.button("❌ 아니오, 취소합니다", use_container_width=True):
                    st.session_state.show_confirm = None
                    st.rerun()
            st.markdown("---")
        
        try:
            student_response = supabase.table("student_chats").select("chats_data").eq("user_id", selected_student).execute()
            student_chats = student_response.data[0]["chats_data"] if student_response.data else {}
        except Exception as e:
            student_chats = {}
            st.error(f"학생 데이터 로드 실패: {e}")
            
        if not student_chats:
            st.warning("이 학생은 아직 대화 기록이 비어있습니다.")
        else:
            chat_ids = list(student_chats.keys())
            selected_chat_id = st.selectbox(
                "💬 열람할 대화방 세션 선택",
                options=chat_ids,
                format_func=lambda x: student_chats[x].get("title", x)
            )
            
            st.markdown("---")
            st.markdown(f"### 💬 **{selected_student}** 학생의 대화방 실시간 모니터링")
            
            target_messages = student_chats[selected_chat_id].get("messages", [])
            for msg in target_messages:
                role = msg.get("role")
                content = msg.get("content")
                if role == "user":
                    with st.chat_message("user"):
                        st.markdown(content)
                else:
                    with st.chat_message("assistant", avatar="🧠"):
                        st.markdown(content)
                        
    st.markdown("---")
    if st.button("🚪 관리자 로그아웃", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.is_admin = False
        st.rerun()
    st.stop()


# 2. 구글 API 키 세팅 (LangChain용으로 전환)
try:
    api_key = st.secrets["GEMINI_API_KEY"]
    # 🚨 3.1 flash lite 모델 유지 (선생님 요청사항)
    llm = ChatGoogleGenerativeAI(model="gemini-3.1-flash-lite", google_api_key=api_key)
except Exception:
    st.error("⚙️ 관리자 설정 오류: Streamlit Cloud 세팅에서 GEMINI_API_KEY를 등록해주세요.")
    st.stop()

# --- 📂 마크다운 파일 원문 실시간 로드 ---
try:
    with open("8. 수학1_핵심 풀이 전략.md", "r", encoding="utf-8") as f:
        su1_strategy = f.read()
    with open("10. 수학2 문제풀이 핵심 전략 (최종 병합2).md", "r", encoding="utf-8") as f:
        su2_strategy = f.read()
except FileNotFoundError as e:
    st.error(f"⚠️ 기출 분석 마크다운 파일을 찾을 수 없습니다: {e.filename}. 파일 이름을 확인해 주세요.")
    st.stop()


# --- 🧠 3. [구조 분리] AI 1과 AI 2 프롬프트 (LangGraph 용) ---

# [AI 1: 팩트체커 프롬프트]
BASE_FACT_CHECKER_PROMPT = """
당신은 고등학교 수학Ⅰ 및 수학Ⅱ를 전담하는 무대 뒤의 '수학 팩트체커이자 수석 교육 설계자'입니다.
학생에게 직접 답변을 출력하지 않으므로, 친절한 어투를 쓸 필요 없이 냉정하고 정확하게 분석하여 다음 단계의 '발문 튜터'에게 보낼 '지침(tutor_guideline)'만 명확하게 작성하십시오.

[수행 임무]
1. 학생의 마지막 입력을 보고, 수학적 오류가 없는지 교차 검증하십시오. (멀티모달 이미지 조건도 철저히 분석)
2. 내장된 기출 전략을 바탕으로 최적의 경로를 찾되, 아래 [M-CoT 4단계] 및 [스캐폴딩 원칙]에 따라 학생의 현재 수준에 맞는 아주 작은 단위(Micro-step)의 지시를 내리십시오.
3. 튜터가 학생에게 던질 '단 하나의 질문(발문)'의 뼈대와 방향성을 guideline으로 작성하십시오.

[🚀 M-CoT 4단계 학습 프로세스 (현재 학생이 어느 단계인지 파악하여 지시할 것)]
- Step 1 (언어적 해독): 문장 속 제약 조건과 목표 파악 유도.
- Step 2 (수학적 모델링): 수식화, 그래프 개형, 케이스 분류 유도.
- Step 3 (단계별 추론): 연산, 역추적 수행. (막힐 때만 직관적이고 작은 단위의 힌트 제공)
- Step 4 (결과 검증): 구한 답을 초기 조건에 대입해 검증하도록 유도. (타협 불가)

[🚨 스캐폴딩 및 튜터 지시 절대 원칙 - 선생님의 핵심 노하우]
1. 맥락 유지: 직전 대화의 맥락을 끊고 뜬금없는 고급 기술(예: 갑자기 2로 나누어 홀짝성 보기)을 지시하지 마십시오. 학생이 어려워하면 가장 기초적인 관찰(예: 2의 거듭제곱 중 가장 큰 수의 부호부터 고민하기)부터 유도하십시오.
2. 스포일러 금지: 튜터에게 지시할 때, "학생에게 공식 명칭이나 변수를 먼저 주지 말고 스스로 떠올리게 질문해라"라고 엄격히 통제하십시오.
3. 답정너 금지: 학생이 제시한 수식이나 접근법이 수학적으로 타당하다면, AI의 최단 경로와 다르더라도 무조건 학생의 논리를 승계하여 다음 질문을 만들도록 지시하십시오.
4. 오류 즉시 교정: 학생의 아이디어가 맞아도 중간 수식(부호 등)에 오류가 있다면, 진도를 나가지 말고 "부호를 다시 확인하도록 질문해라"라고 튜터에게 지시하십시오.

==================================================
[🚨 기출 분석 핵심 전략 데이터베이스]
■ 수학Ⅰ 핵심 풀이 전략 원문
[SU1_STRATEGY_PLACEHOLDER]

■ 수학Ⅱ 핵심 풀이 전략 원문
[SU2_STRATEGY_PLACEHOLDER]
==================================================
"""
"""

FACT_CHECKER_PROMPT = BASE_FACT_CHECKER_PROMPT.replace("[SU1_STRATEGY_PLACEHOLDER]", su1_strategy)\
                                              .replace("[SU2_STRATEGY_PLACEHOLDER]", su2_strategy)

# [AI 2: 발문 튜터 프롬프트]
BASE_TUTOR_PROMPT = """
당신은 복잡한 팩트 체크를 직접 하지 않으며, 오직 무대 뒤 팩트체커가 전달해 준 '지침(tutor_guideline)'만 보고 문장을 부드럽고 다정하게 가공하십시오.

[🚨 출력 형식 절대 준수 규칙 - 가장 중요]
- 절대 JSON 구조, 파이썬 리스트, 딕셔너리 형태(예: [{'type': 'text', ...}])로 출력하지 마십시오.
- 'extras', 'signature', 'type' 같은 프로그래밍 언어나 시스템 코드를 절대로 대화에 포함하지 마십시오.
- 오직 친절한 선생님이 학생에게 말하듯 자연스러운 '순수 텍스트 문장'만 출력해야 합니다.

[⚠️ 절대 준수 대화 규칙]
1. 과도한 칭찬 및 텍스트 나열 절대 금지: 한 번에 반드시 '단 하나의 질문'만 던지고 출력을 멈추십시오. (자문자답 금지)
2. 팩트체커가 지시한 가이드라인 범위를 넘어서 정답이나 수식, 구체적인 공식 명칭을 먼저 스포일러하지 마십시오.
3. 맹목적 동의 및 '답정너'식 덮어쓰기 절대 금지: 학생의 수식이 맞다면 무조건 승계하십시오.
4. 속마음 노출 금지: 팩트체커의 분석 과정이나 [AI 내부 팩트 체크] 같은 문구를 절대로 화면에 출력하지 마십시오.
5. 인지적 마감: 학생이 최종 답을 맞히고 검증까지 완료했다면 칭찬 후 "다음 문제를 푸실 때는 꼭 '새 채팅방(New Chat)'을 열어서 질문해 주세요!"라고 안내하며 대화를 종료하십시오.
"""

# --- 🏗️ 4. LangGraph 파이프라인(Dual-LLM) 조립 ---
class TutorState(TypedDict):
    chat_history: List[Dict[str, Any]] # 이전 대화 기억용
    student_msg: str
    image_base64: str                  # 이미지 데이터
    tutor_guideline: str
    final_response: str

def format_history_for_langchain(history):
    formatted = []
    for msg in history:
        if msg["role"] == "user":
            formatted.append(HumanMessage(content=msg["content"]))
        else:
            formatted.append(AIMessage(content=msg["content"]))
    return formatted

def fact_checker_node(state: TutorState):
    student_msg = state["student_msg"]
    image_base64 = state["image_base64"]
    history = format_history_for_langchain(state["chat_history"])
    
    messages = [SystemMessage(content=FACT_CHECKER_PROMPT)] + history
    
    # 멀티모달(이미지) 처리 로직
    if image_base64:
        content = [
            {"type": "text", "text": f"학생의 현재 입력: {student_msg}"},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}}
        ]
        messages.append(HumanMessage(content=content))
    else:
        messages.append(HumanMessage(content=f"학생의 현재 입력: {student_msg}"))
        
    response = llm.invoke(messages)
    return {"tutor_guideline": response.content}

def extract_pure_text(content):
    # 1. AI 응답이 아예 파이썬 리스트 객체로 나온 경우
    if isinstance(content, list):
        return "".join([item.get("text", "") for item in content if isinstance(item, dict) and "text" in item])
    
    # 2. 문자열인데 "[{'type': 'text',..." 형태로 꼬여서 나온 경우
    if isinstance(content, str):
        content_stripped = content.strip()
        if content_stripped.startswith("[{") and "'text':" in content_stripped:
            import re
            # 'text': '진짜 내용', 'extras' 사이의 진짜 내용만 정밀하게 적출
            match = re.search(r"'text':\s*['\"](.*?)['\"],\s*'extras'", content_stripped, re.DOTALL)
            if match:
                # 추출 과정에서 깨진 줄바꿈 기호 복원
                return match.group(1).replace('\\n', '\n').replace('\\xa0', ' ')
        return content_stripped
        
    return str(content)

def tutor_node(state: TutorState):
    guideline = state["tutor_guideline"]
    student_msg = state["student_msg"]
    history = format_history_for_langchain(state["chat_history"])
    
    messages = [SystemMessage(content=TUTOR_PROMPT)] + history
    messages.append(HumanMessage(content=f"[팩트체커의 지시사항]: {guideline}\n\n위 지시사항을 바탕으로 학생의 마지막 말('{student_msg}')에 대답하는 단 하나의 발문을 생성해."))
    
    response = llm.invoke(messages)
    
    # 🚨 생성된 응답을 순수 텍스트 추출기에 한 번 통과시킨 후 저장 (분쇄기 작동!)
    clean_text = extract_pure_text(response.content)
    
    return {"final_response": clean_text}

workflow = StateGraph(TutorState)
workflow.add_node("FactChecker", fact_checker_node)
workflow.add_node("Tutor", tutor_node)
workflow.set_entry_point("FactChecker")
workflow.add_edge("FactChecker", "Tutor")
workflow.add_edge("Tutor", END)
app_graph = workflow.compile()


# --- 💾 데이터 초기화 및 사이드바 ---
if "all_chats" not in st.session_state:
    st.session_state.all_chats = load_all_chats()

if "current_chat_id" not in st.session_state:
    if st.session_state.all_chats:
        st.session_state.current_chat_id = list(st.session_state.all_chats.keys())[-1]
    else:
        create_new_chat()
        save_all_chats(st.session_state.all_chats)

def delete_chat(chat_id_to_delete):
    if chat_id_to_delete in st.session_state.all_chats:
        del st.session_state.all_chats[chat_id_to_delete]
        if st.session_state.current_chat_id == chat_id_to_delete:
            if st.session_state.all_chats: 
                st.session_state.current_chat_id = list(st.session_state.all_chats.keys())[-1]
            else: 
                create_new_chat()
        save_all_chats(st.session_state.all_chats)

if not st.session_state.get("all_chats"):
    st.session_state.all_chats = {}
    create_new_chat() 

with st.sidebar:
    st.markdown(f"### 👤 접속자: **{st.session_state.user_id}**")
    
    if st.button("🚪 로그아웃", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.user_id = ""
        st.session_state.all_chats = {} 
        st.session_state.is_admin = False
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


# --- 🖥️ 6. 메인 화면 출력 ---
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


# --- 🚀 7. 질문 입력 및 답변 처리 (수술 완료된 심장부) ---
if prompt := st.chat_input("AI 튜터의 질문에 답하거나 추가 질문을 입력하세요!"):
    
    with st.chat_message("user"):
        st.markdown(prompt)
    current_messages.append({"role": "user", "content": prompt})

    if len(current_messages) == 3:
        st.session_state.all_chats[st.session_state.current_chat_id]["title"] = f"🔍 {prompt[:10]}..."

    with st.spinner("AI 튜터가 구조를 분석하는 중입니다..."):
        try:
            # 1. 이미지 처리 (이미지를 Base64로 변환하여 LangGraph에 전달 준비)
            image_sent_key = f"image_sent_{st.session_state.current_chat_id}"
            img_base64 = ""
            
            if uploaded_file is not None and not st.session_state.get(image_sent_key, False):
                img = Image.open(uploaded_file)
                buffered = BytesIO()
                # 이미지를 RGB로 변환하여 JPEG 포맷 호환성 보장
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                img.save(buffered, format="JPEG")
                img_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
                st.session_state[image_sent_key] = True 
            
            # 2. LangGraph 실행 (과거 기록은 맨 마지막 질문을 제외하고 넘김)
            inputs = {
                "chat_history": current_messages[:-1], 
                "student_msg": prompt, 
                "image_base64": img_base64
            }
            
            # 컨베이어 벨트 가동! (FactChecker -> Tutor)
            result = app_graph.invoke(inputs)
            final_text = result["final_response"]
            
            # 3. 화면 출력 및 저장
            with st.chat_message("assistant"):
                st.markdown(final_text)
            current_messages.append({"role": "assistant", "content": final_text})
            
            st.session_state.all_chats[st.session_state.current_chat_id]["messages"] = current_messages
            save_all_chats(st.session_state.all_chats)
            st.rerun()
            
        except Exception as e:
            st.error(f"오류가 발생했습니다: {e}")
