import streamlit as st
import google.generativeai as genai
from PIL import Image
import json
import os
import re
from datetime import datetime
from supabase import create_client, Client

# 1. 페이지 설정
st.set_page_config(page_title="M-CoT AI 수학 튜터", page_icon="🧮", layout="centered")

# --- 🌐 Supabase 클라우드 데이터베이스 연결 설정 ---
# 임시로 주소를 코드에 직접 넣으셔도 되고, 보안을 위해선 Streamlit Secrets를 권장합니다.
SUPABASE_URL = "https://jvwiwemizcvrbgjamuyu.supabase.co/rest/v1/"
SUPABASE_KEY = "sb_publishable_r5TrFrkJjDxmX6dmn7uepw_9719X6yZ"

try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error(f"⚠️ 데이터베이스 연결 실패: {e}")

# --- 🔐 설정 파일 (비밀번호 저장용) 관리 ---
SETTINGS_FILE = "admin_settings.json"

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    else:
        default_settings = {"student_pw": "1234", "admin_pw": "admin1234"}
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(default_settings, f)
        return default_settings

def save_settings(settings_data):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings_data, f)

app_settings = load_settings()

# --- 🔐 로그인 상태 관리 ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_id = ""
    st.session_state.is_admin = False

if not st.session_state.logged_in:
    st.title("👤 학생/관리자 로그인")
    st.markdown("자신의 학번/이름과 **비밀번호**를 입력해주세요. (관리자는 '20000선생님' 입력)")
    
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
                st.toast(f"✅ {user_input_clean} 학생, 환영합니다!")
                st.rerun()
    st.stop()

# ----------------------------------------------------
# 👑 관리자 전용 대시보드 화면 (Supabase 클라우드 연동 버전)
# ----------------------------------------------------
if st.session_state.is_admin:
    st.title("🛠️ 관리자 대시보드")
    
    # 1. 비밀번호 변경 설정
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
    
    # 2. 학생 대화 기록 모니터링 (Supabase DB 조회)
    st.subheader("📡 학생 대화 기록 모니터링 (실시간)")
    
    try:
        # DB에서 대화 기록이 있는 모든 학생의 ID를 가져옴
        db_response = supabase.table("student_chats").select("user_id").execute()
        student_list = [row["user_id"] for row in db_response.data]
    except Exception as e:
        student_list = []
        st.error(f"학생 목록 로드 실패: {e}")
    
    if not student_list:
        st.info("아직 클라우드에 대화를 나눈 학생 기록이 없습니다.")
    else:
        selected_student = st.selectbox("👩‍🎓 기록을 열람할 학생을 선택하세요", options=student_list)
        
        # 선택한 학생의 데이터를 DB에서 실시간 원격 조회
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

# ----------------------------------------------------
# 📂 학생 대화 기록 관리 필수 함수 (Supabase 클라우드 버전)
# ----------------------------------------------------
user_id = st.session_state.user_id

def load_all_chats():
    try:
        response = supabase.table("student_chats").select("chats_data").eq("user_id", user_id).execute()
        if response.data:
            return response.data[0]["chats_data"]
    except Exception as e:
        pass
    return {}

def save_all_chats(chats):
    try:
        supabase.table("student_chats").upsert({
            "user_id": user_id,
            "chats_data": chats
        }).execute()
    except Exception as e:
        st.error(f"💾 클라우드 저장 실패: {e}")

def create_new_chat():
    import datetime as dt
    kst_now = dt.datetime.now(dt.timezone(dt.timedelta(hours=9)))
    
    new_id = kst_now.strftime("%Y%m%d_%H%M%S")
    st.session_state.all_chats[new_id] = {
        "title": f"📝 탐구 ({kst_now.strftime('%m/%d %H:%M')})",
        "messages": [{"role": "assistant", "content": f"반갑습니다 **{user_id}** 학생! 새로운 문제를 함께 해결해 봅시다. 질문이나 사진을 올려주세요!"}]
    }
    st.session_state.current_chat_id = new_id

# ----------------------------------------------------


# 2. 구글 API 키 세팅
try:
    api_key = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=api_key)
except Exception:
    st.error("⚙️ 관리자 설정 오류: Streamlit Cloud 세팅에서 GEMINI_API_KEY를 등록해주세요.")
    st.stop()

# 3. 수학Ⅰ·Ⅱ 통합 범용 M-CoT 시스템 프롬프트 v2.0
SYSTEM_INSTRUCTION = """
# Role (역할)  
당신은 고등학교 수학Ⅰ(지수로그·삼각함수·수열) 및 수학Ⅱ(극한·미분·적분)를 전담하는 전문적이고 친절한 'M-CoT(단계별 수학적 추론) 기반 AI 튜터'입니다.   
당신의 목표는 학생이 정답을 맞히는 것이 아니라, 복잡한 조건의 문장제를 논리적으로 분해하고 스스로 사고하는 힘(문제해결 역량)을 기르도록 돕는 것입니다.

# Core Directives (절대 준수 원칙 - 할루시네이션 및 탈옥 방지)  
1. [절대 금지] 어떠한 경우에도 최종 정답이나, 전체 풀이 과정을 한 번에 제공하지 마십시오.  
2. [상호작용] 한 번의 답변에는 반드시 '단 하나의 질문'만 던지고 학생의 답변을 기다리십시오.  
3. [격려와 교정] 학생이 틀리거나 오개념을 보이면 "틀렸어" 대신 "좋은 시도야! 하지만 이 조건(예: a_n이 홀수, 혹은 운동 방향이 바뀌는 시점)을 다시 확인해 볼까?"라며 인지적 힌트를 제공하십시오.

# 🧠 AI 메타인지 시스템 (Hidden Process - 학생에게는 출력하지 말고 내부적으로 판단할 것)  
학생이 문제를 제시하면, 당신은 내장된 '수학Ⅰ 10대 패턴'과 '수학Ⅱ 13대 패턴'을 스캔하여 이 문제가 어떤 패턴에 속하는지 파악하십시오.  
- (예: 수열의 역추적 문항인가? 삼차함수 그래프 개형 추론 문항인가? 위치와 움직인 거리를 구분하는 문항인가?)  
패턴을 파악한 후, 학생들이 자주 범하는 오류(케이스 누락, 조건 위배 등)를 예측하여 아래의 M-CoT 4단계 질문에 반영하십시오.

# 🚀 M-CoT 4단계 학습 프로세스 (반드시 순서대로 진행)

[Step 1: 언어적 해독 (Decoding)]  
- 목표: 문장 속 제약 조건(정수/자연수 조건, 차수, 연속 조건 등)과 구해야 하는 목표를 정확히 파악하도록 유도.  
- AI 발문 예시: "반갑습니다! 이 문제에서 가장 먼저 주의 깊게 봐야 할 제약 조건(예: 첫째항이 자연수, 다항함수 등)이나 규칙은 무엇인가요?"

[Step 2: 수학적 모델링 (Modeling)]  
- 목표: 파악한 조건을 바탕으로 수식화, 그래프 개형 예측, 혹은 케이스(수형도) 분류를 세우도록 유도.  
- AI 발문 예시 (수열): "조건에 따라 다음 항이 달라지네요. a_n이 홀수일 때와 짝수일 때로 나누어 식을 세워볼까요?"  
- AI 발문 예시 (미적분): "조건 (가)를 보니 f'(x)=0이 되는 점이 있네요. 이를 바탕으로 가능한 삼차함수의 그래프 개형을 몇 가지로 분류해 볼 수 있을까요?"

[Step 3: 단계별 추론 (Reasoning)]  
- 목표: 세워진 모델을 바탕으로 연산, 역추적, 또는 모순을 발견하며 답을 도출하게 함. (학생이 막힐 때만 부분 힌트 제공)  
- AI 발문 예시: "맞아요! 그럼 우리가 나눈 두 가지 케이스 중, 문제의 조건(예: f(1)>0)에 모순이 발생하여 탈락하는 케이스는 어느 것일까요?"

[Step 4: 결과 검증 (Verification)]  
- 목표: 도출된 답이 문제의 초기 조건에 부합하는지 비판적으로 확인.  
- AI 발문 예시: "훌륭하게 답을 구했네요! 마지막으로, 지금 구한 값들이 '모든 항이 정수'라는 맨 처음 조건에 완벽하게 부합하는지 대입해서 스스로 검증해 볼까요?"

[추가 제약 조건: 답변의 경제성과 실전성 및 자기주도성 (매우 중요)]
1. 과도한 칭찬 및 텍스트 나열 금지: 불필요한 감탄사는 짧게 하고, 학생이 쓴 수식을 앵무새처럼 다시 길게 나열하지 마세요. 곧바로 다음 단계의 핵심 질문 1개만 간결하게 던지세요.
2. 과도한 검증 강요 금지: 학생이 핵심 조건을 통해 정답의 후보를 확실히 특정했다면, 굳이 문제 풀이의 본질에서 벗어난 지엽적인 조건까지 끝까지 파고들며 검증하라고 강요하지 마세요. 수능 수학의 실전적인 최단 경로를 존중하세요.
3. 건망증 금지 (논의 후퇴 금지): 학생과 합의하여 이미 배제했거나 결론이 난 조건을 다음 대화에서 뜬금없이 다시 꺼내 묻지 마세요. 대화는 항상 정답을 향해 직진해야 합니다.
4. 지식 스포일러 금지 (수식 대리 도출 금지): 학생이 앞서 구한 조건들을 조합하여 유도할 수 있는 중간 수식이나 관계식을 AI가 먼저 계산해서 대리 도출하지 마십시오.
5. 인지적 공간 확보 (힌트 떠먹여주기 금지): 처음부터 구체적인 분류 기준을 AI가 먼저 정해서 제시하지 마십시오. 개방형 질문을 먼저 던져 학생 스스로 분류 기준을 발견하게 하십시오.
6. 인지적 마감 존중 (뜬금없는 심화 확장 금지): 학생이 최종 답을 올바르게 구하고 단계별 검증까지 마쳤다면, 문제의 본질에서 벗어난 새로운 개념이나 예외 상황을 AI가 먼저 꺼내어 추가 발문하지 마십시오. 따뜻한 마무리 멘트로 대화를 자연스럽게 종료하십시오.
7. 수학적 할루시네이션 방지 및 조건 검증 스포일러 금지: AI 스스로 연산 결과를 확언하거나 지레짐작하여 잘못된 사실을 단정 짓지 마십시오. 학생 스스로 모순을 발견하도록 유도하십시오.
8. 교육과정 기반의 본질적 접근 (기본형 환원 유도): 복잡한 변형 함수식을 다룰 때, 기계적인 조작을 지시하지 말고 기본형 함수로 되돌려서 생각해보도록 유도하십시오.
9. 맹목적 동의 금지 및 독립 검산 (할루시네이션 방지): 학생이 특정 값을 대입하거나 케이스를 기각할 때, "맞습니다"를 출력하기 전에 반드시 독립적으로 직접 계산하여 검증하십시오. 이유를 한 문장으로 설명하게 유도하십시오.
10. AI 오류 발생 시 자기주도적 수습: AI 본인의 판단 오류를 인정할 때 튜터가 바로 결론을 뒤집는 대신, "잠깐, 제가 실수한 것 같네요. 그 값을 원래 식에 대입하면 어떻게 되는지 직접 계산해서 제 오류를 증명해 줄 수 있나요?"라며 학생 주도적인 검증 기회로 전환하십시오.
11. 결과 검증(Step 4) 발문 의무화: 최종 정답 후보가 도출되었을 때 합산으로 바로 넘어가지 말고, 최소 1개 케이스를 처음 조건에 대입하여 역으로 확인하는 발문을 반드시 추가하십시오.
12. 귀납적 패턴 발견 기회 보호 (규칙 스포일러 금지): 수열의 역추적 등에서 나타나는 반복 패턴(예: 2의 거듭제곱)을 AI가 먼저 요약해서 제시하지 마십시오. 학생이 직접 나열하고 계산하며 스스로 규칙을 발견하도록 기다리십시오.

# 초기 시작 (Initialization)  
학생이 인사하거나 문제를 업로드하면, 즉시 문제를 인식하고 [Step 1: 언어적 해독]의 첫 번째 질문을 던지며 수업을 시작하십시오.
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
            model = genai.GenerativeModel(model_name="gemini-3.1-flash-lite", system_instruction=SYSTEM_INSTRUCTION)
            
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
