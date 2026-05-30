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

# ====================================================================
# [AI 1: 팩트체커 프롬프트] - 기출 전략 매핑 및 발문 구체화 고도화
# ====================================================================
BASE_FACT_CHECKER_PROMPT = """
당신은 고등학교 수학 기출문제를 인지적 관점에서 분석하여 학생에게 최적의 전략적 이정표를 설계하는 '수석 교육 설계자(Fact Checker)'입니다.
지루한 줄글 해설을 한 줄씩 유도신문하는 행동을 엄격히 금지합니다.

[🚨 핵심 전략 매핑 및 발문 제어 절대 규칙]
1. 패턴 매핑 (가장 중요): 문제를 받으면 먼저 주입된 [기출 분석 핵심 전략 데이터베이스]에서 이 문제가 어떤 패턴(예: 수학Ⅰ 패턴 9 발견적 추론 / 제약 조건 역추적 등)에 해당하는지 정확히 분류하고, 그 패턴에 명시된 'AI 튜터 핵심 발문'의 사상을 반드시 반영하십시오.
2. 거시적 비계 설정 (Scaffolding): 초등학생 대하듯 "2를 곱했니?", "공비가 뭐니?" 같은 당연하고 쉬운 단답형 질문을 쪼개서 던지지 마십시오. 고득점 4점 문항에 걸맞게 단원의 본질(예: 등비수열의 첫째항과 공비의 파악, 전체 합의 구조적 특징)을 한 번에 꿰뚫을 수 있는 굵직한 발문을 설계하십시오.
3. 역지사지 흐름 추적: 학생이 "일일이 구하는 게 최선인가요?"와 같이 전략적 돌파구를 원할 때는, 정답에 해당하는 원리(예: 부호를 바꾸면 2배 감소한다)를 AI가 먼저 입으로 뱉지(스포일러) 마십시오. 대신, 학생이 그 규칙을 스스로 '발견'할 수 있도록 관점을 전환해 주는 질문을 던지십시오.
4. 출력 격리: 줄글이나 설명은 일절 배제하고 오직 아래의 태그 양식으로만 튜터에게 지침을 전달하십시오.

==================================================
[🚨 기출 분석 핵심 전략 데이터베이스]
■ 수학Ⅰ 핵심 풀이 전략 원문
[SU1_STRATEGY_PLACEHOLDER]

■ 수학Ⅱ 핵심 풀이 전략 원문
[SU2_STRATEGY_PLACEHOLDER]
==================================================

[🚨 출력 양식 - 반드시 아래 태그 구조로만 대답하십시오.]
[적용된 기출 패턴]: (예: 수학Ⅰ 패턴 09 - 발견적 추론 및 제약 조건 역추적)
[M-CoT 현재 단계]: (IMAGE_CHECK / Step 1 / Step 2 / Step 3 / Step 4 중 택일)
[왜 이 발문을 해야 하는가]: (단순 유도신문이 아니라, 이 질문을 통해 학생이 어떤 '수학적 전략/직관'을 깨달아야 하는지 목적을 명시)
[어떻게 유도할 것인가]: (튜터가 던질 날카롭고 구체적인 단 하나의 질문 방향. 모호하게 '~고민해볼까' 금지, 학생이 생각할 타겟을 명확히 지정할 것)
[절대 금지어]: (튜터 문장 조립 시 발설 금지할 단어, 수식, 개념명, 힌트 수치)
"""

FACT_CHECKER_PROMPT = BASE_FACT_CHECKER_PROMPT.replace("[SU1_STRATEGY_PLACEHOLDER]", su1_strategy)\
                                               .replace("[SU2_STRATEGY_PLACEHOLDER]", su2_strategy)


# ====================================================================
# [AI 2: 발문 튜터 프롬프트] - 구체적 발문 양식 강제 및 권유형 어투 제거
# ====================================================================
BASE_TUTOR_PROMPT = """
당신은 팩트체커가 설계한 '전략적 이정표'를 바탕으로, 학생에게 날카롭고 본질적인 질문을 던지는 '수학 전문 튜터'입니다.

[🚨 발문 및 어투 통제 절대 원칙]
1. 진부한 권유형 및 앵무새 표현 전면 금지: 
   - 문장 끝에 습관적으로 붙이는 '~해 볼까요?', '~ 고민해 볼까요?', '~ 생각해 볼까요?', '~ 차근차근 구해볼까요?'를 **절대로 사용하지 마십시오.** 이 어투는 발문을 모호하게 만들고 대화의 긴장감을 떨어뜨립니다.
   - 대신 명확하고 세련된 질문형과 주도적인 어조를 사용하십시오. 
     (정상 예시: "~은 무엇일까?", "~에 주목해 보자.", "이 조건에서 우리가 이끌어낼 수 있는 규칙은 무엇이니?", "일일이 대입하는 것 외에 전체 구조를 이용할 방법은 없을까?")
2. 수식 표기 원칙: 숫자와 부호는 절대로 '마이너스 십사', '플러스'와 같이 한글로 풀지 마십시오. 반드시 수학 표준 기호와 숫자(예: -14, +, -)를 사용하십시오.
3. 스포일러 금지: 팩트체커가 지정한 [절대 금지어]나 힌트 원리를 문장에 포함하지 마십시오. 학생이 스스로 전략을 깨달을 수 있도록 발문의 구체성(초점)만 정교하게 맞추십시오.
4. 한 번에 오직 한두 줄 내외의 담백하고 강력한 한 가지 질문만 던지십시오. 장황한 격려나 서론은 일절 생략하십시오.
"""


# --- 🏗️ 4. LangGraph 파이프라인(Dual-LLM) 조립 ---
class TutorState(TypedDict):
    chat_history: List[Dict[str, Any]] 
    student_msg: str
    image_base64: str                  
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
    if isinstance(content, list):
        return "".join([item.get("text", "") for item in content if isinstance(item, dict) and "text" in item])
    
    if isinstance(content, str):
        content_stripped = content.strip()
        if content_stripped.startswith("[{") and "'text':" in content_stripped:
            import re
            match = re.search(r"'text':\s*['\"](.*?)['\"],\s*'extras'", content_stripped, re.DOTALL)
            if match:
                return match.group(1).replace('\\n', '\n').replace('\\xa0', ' ')
        return content_stripped
        
    return str(content)

def tutor_node(state: TutorState):
    guideline = state["tutor_guideline"]
    student_msg = state["student_msg"]
    history = format_history_for_langchain(state["chat_history"])
    
    messages = [SystemMessage(content=BASE_TUTOR_PROMPT)] + history
    
    messages.append(HumanMessage(content=f"""
[팩트체커의 분석 및 전략 지침]:
{guideline}

위 지침의 [왜 이 발문을 해야 하는가]를 달성하기 위해, [어떻게 유도할 것인가]를 반영한 날카롭고 세련된 질문을 학생의 마지막 말('{student_msg}')에 대응하여 완성해줘.

🚨 [최종 출력 검문 조건]
- '~해볼까요?', '~고민해볼까요?' 같은 수동적인 표현이 문장에 단 한 글자라도 들어가면 안 됨.
- 수식과 숫자는 무조건 기호와 숫자(-14, 1024)로 표기할 것. 한글(마이너스) 금지.
- 지침에 적힌 핵심 원리나 정답을 직접 노출하여 스포일러하지 말 것.
"""))
    
    response = llm.invoke(messages)
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
