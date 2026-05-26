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
SUPABASE_URL = "https://jvwiwemizcvrbgjamuyu.supabase.co"
SUPABASE_KEY = "sb_publishable_r5TrFrkJjDxmX6dmn7uepw_9719X6yZ"

try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error(f"⚠️ 데이터베이스 연결 실패: {e}")

# ----------------------------------------------------
# 📂 학생 대화 기록 관리 필수 함수 (Supabase 클라우드 버전)
# ----------------------------------------------------

# [수정] 프로그램 시작 시 에러 방지를 위해 함수 내부에서 실시간으로 가져오도록 변경합니다.
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

# ----------------------------------------------------

# --- 🔐 설정 파일 (비밀번호 저장용) 관리 --- [클라우드 DB 버전으로 완전 교체]
def load_settings():
    try:
        # DB의 admin_settings 테이블에서 첫 번째 행의 비밀번호 데이터를 가져옵니다.
        response = supabase.table("admin_settings").select("student_pw", "admin_pw").execute()
        if response.data:
            return response.data[0]
    except Exception as e:
        st.error(f"⚠️ DB에서 비밀번호를 불러오지 못했습니다: {e}")
    # 에러 발생 시 시스템 다운을 막기 위한 백업용 기본값
    return {"student_pw": "1234", "admin_pw": "admin1234"}

def save_settings(settings_data):
    try:
        # DB에 비밀번호를 업데이트합니다. (id가 1인 행을 수정하거나 없으면 새로 넣음)
        supabase.table("admin_settings").upsert({
            "id": 1,  # 고정된 id값을 사용하여 항상 하나의 행만 덮어쓰도록 유도
            "student_pw": settings_data["student_pw"],
            "admin_pw": settings_data["admin_pw"]
        }).execute()
        return True
    except Exception as e:
        st.error(f"💾 클라우드 비밀번호 동기화 실패: {e}")
        return False

# 프로그램 시작 시 DB에서 실시간으로 최신 비밀번호를 읽어옵니다.
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
                
                # --- 💡 [여기에 이 한 줄을 추가해 주세요!] ---
                # 로그인하는 순간, 이 학생의 기존 클라우드 대화 기록이 있다면 가져옵니다.
                st.session_state.all_chats = load_all_chats()
                # ---------------------------------------------
                
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
    col_title, col_btn = st.columns([8, 2])
    with col_title:
        st.subheader("📡 학생 대화 기록 모니터링")
    with col_btn:
        if st.button("🔄 새로고침", use_container_width=True):
            st.rerun() # 👈 이 마법의 한 줄이 화면을 즉시 최신 상태로 갱신합니다!
            
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

        # 🗑️ 학생 데이터 영구 삭제 (오터치 방지 2단계 확인 절차)
        if st.button(f"🚨 '{selected_student}' 학생 기록 영구 삭제", type="primary", use_container_width=True):
            # 첫 번째 버튼을 누르면 어떤 학생을 지우려고 했는지 기억해둡니다.
            st.session_state.show_confirm = selected_student

        # 삭제 확인 버튼을 눌렀을 때만 아래 경고창과 선택 버튼이 팝업처럼 등장합니다.
        if st.session_state.get("show_confirm") == selected_student:
            st.error(f"⚠️ **[최종 확인]** '{selected_student}' 학생의 모든 대화 기록이 데이터베이스에서 영구 삭제되며, 절대로 복구할 수 없습니다. 정말 진행하시겠습니까?")
            
            # 가로로 버튼 2개 배치 (진짜 삭제 / 취소)
            col_yes, col_no = st.columns(2)
            with col_yes:
                if st.button("🔥 네, 진짜로 삭제합니다", type="primary", use_container_width=True):
                    try:
                        # 진짜 삭제 수행
                        supabase.table("student_chats").delete().eq("user_id", selected_student).execute()
                        st.session_state.show_confirm = None  # 확인 상태 초기화
                        st.toast(f"✅ {selected_student} 학생의 기록이 완전히 삭제되었습니다.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"⚠️ 삭제 실패: {e}")
            with col_no:
                if st.button("❌ 아니오, 취소합니다", use_container_width=True):
                    st.session_state.show_confirm = None  # 확인 상태 초기화
                    st.rerun()
            st.markdown("---")
        
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



# 2. 구글 API 키 세팅
try:
    api_key = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=api_key)
except Exception:
    st.error("⚙️ 관리자 설정 오류: Streamlit Cloud 세팅에서 GEMINI_API_KEY를 등록해주세요.")
    st.stop()


# --- 📂 [안전 장치] 외부 마크다운 파일 원문 실시간 로드 ---
# 중괄호{ }가 들어간 수식 충돌을 막기 위해 최고의 효율을 내는 핵심 파일 2개만 실시간 로드합니다.
try:
    with open("8. 수학1_핵심 풀이 전략.md", "r", encoding="utf-8") as f:
        su1_strategy = f.read()
    # 가장 완성도가 높은 (최종 병합2) 파일로 변경 적용
    with open("10. 수학2 문제풀이 핵심 전략 (최종 병합2).md", "r", encoding="utf-8") as f:
        su2_strategy = f.read()
except FileNotFoundError as e:
    st.error(f"⚠️ 기출 분석 마크다운 파일을 찾을 수 없습니다: {e.filename}. 파일 이름을 확인해 주세요.")
    st.stop()


# 3. 수학Ⅰ·Ⅱ 통합 범용 M-CoT 시스템 프롬프트 v3.1 (최종 최적화 버전)
BASE_SYSTEM_INSTRUCTION = """
# Role (역할)  
당신은 고등학교 수학Ⅰ(지수로그·삼각함수·수열) 및 수학Ⅱ(극한·미분·적분)를 전담하는 전문적이고 친절한 'M-CoT(단계별 수학적 추론) 기반 AI 튜터'입니다.   
당신의 목표는 학생이 정답을 맞히는 것이 아니라, 복잡한 조건의 문장제를 논리적으로 분해하고 스스로 사고하는 힘(문제해결 역량)을 기르도록 돕는 것입니다.

# Core Directives (절대 준수 원칙 - 할루시네이션 및 탈옥 방지)  
1. [절대 금지] 어떠한 경우에도 최종 정답이나, 전체 풀이 과정을 한 번에 제공하지 마십시오.  
2. [상호작용] 한 번의 답변에는 반드시 '단 하나의 질문'만 던지고 학생의 답변을 기다리십시오.  
3. [격려와 교정] 학생이 틀리거나 오개념을 보이면 "틀렸어" 대신 "좋은 시도야! 하지만 이 조건(예: a_n이 홀수, 혹은 운동 방향이 바뀌는 시점)을 다시 확인해 볼까?"라며 인지적 힌트를 제공하십시오.

# 🧠 AI 메타인지 시스템 (Hidden Process - 학생에게는 출력하지 말고 내부적으로 판단할 것)  
학생이 문제를 제시하면, 당신은 아래에 내장된 '수학Ⅰ 10대 패턴'과 '수학Ⅱ 13대 패턴'의 기출 교재 원문 데이터베이스를 철저히 스캔하여 이 문제가 어떤 패턴에 속하는지 파악하십시오.  
패턴을 파악한 후, 학생들이 자주 범하는 오류(케이스 누락, 조건 위배 등)를 예측하고 해당 패턴에 적힌 'AI 튜터 핵심 발문 가이드'를 M-CoT 4단계 질문에 강력하게 반영하십시오.

==================================================
[🚨 기출 분석 핵심 전략 데이터베이스 - 학생 출력 금지]

■ 수학Ⅰ 핵심 풀이 전략 원문
[SU1_STRATEGY_PLACEHOLDER]

■ 수학Ⅱ 핵심 풀이 전략 원문
[SU2_STRATEGY_PLACEHOLDER]
==================================================

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

[추가 제약 조건: 답변의 경제성과 실전성 및 자기주도성 (🚨초특급 극약 처방 준수)]
1. 과도한 칭찬 및 텍스트 나열 절대 금지: 불필요한 감탄사는 짧게 하고, 학생이 쓴 수식을 앵무새처럼 다시 길게 나열하지 마세요. 곧바로 다음 단계의 핵심 질문 1개만 간결하게 던지세요.
2. 과도한 검증 강요 금지: 학생이 핵심 조건을 통해 정답의 후보를 확실히 특정했다면, 굳이 문제 풀이의 본질에서 벗어난 지엽적인 조건까지 끝까지 파고들며 검증하라고 강요하지 마세요. 수능 수학의 실전적인 최단 경로를 존중하세요.
3. 건망증 금지 (논의 후퇴 금지): 학생과 합의하여 이미 배제했거나 결론이 난 조건을 다음 대화에서 뜬금없이 다시 꺼내 묻지 마세요. 대화는 항상 정답을 향해 직진해야 합니다.
4. 공식 명칭 및 변수/식 선제 제시 절대 금지 (🚨🚨🚨): 학생이 먼저 입으로 꺼내기 전에는 "코사인법칙", "사인법칙", "삼각형 넓이 공식" 등 구체적인 공식 명칭이나 수학적 도구를 AI가 먼저 절대 발설하지 마십시오. 또한 "AC의 길이를 x라 두고 식을 세워보자"처럼 변수를 먼저 지정하거나 중간 수식을 대리 도출하여 힌트를 떠먹여 주는 행위를 엄격히 금지합니다. 조건의 기하학적 의미 해석도 학생의 몫입니다.
5. 인지적 공간 확보 (단계별 풀이 로드맵 공유 절대 금지 - 🚨🚨🚨): 각 단계(Step)에 진입할 때, 앞으로 해야 할 일의 전체 로드맵을 AI가 먼저 주저리주저리 예언하지 마십시오. (예: "S1을 구한 뒤 S2를 이용해 AD, CD를 구합시다" 등의 오지랖 전면 금지). 오직 지금 당장 학생이 직면한 '단 하나의 발걸음'에 대해서만 질문하십시오. "우리가 정리한 조건 중 아직 사용하지 않은 단서는 무엇이 있나요?", "이 단서들을 조합하면 어떤 정보들을 먼저 얻을 수 있을까요?"와 같이 학생 스스로 도구를 매핑하게 하십시오.
6. 인지적 마감 존중 및 새 채팅방 안내 (🚨🚨 시스템 오염 방지): 학생이 최종 답을 올바르게 구하고 계산을 마쳤다면, 과정을 역으로 분해하여 다시 계산하라는 둥 뜬금없는 심화 확장이나 불필요한 검증을 요구하지 마십시오. 정답이 맞으면 내부 검산 후 즉시 인정하되, 따뜻한 칭찬과 함께 **"다음 문제를 푸실 때는 이전 문제의 조건 잔상이 남아 시스템이 오염되는 것을 막기 위해, 꼭 '새 채팅방(New Chat)'을 열어서 질문해 주세요!"**라는 안내 문구를 반드시 출력하고 대화를 자연스럽게 종료하십시오.
7. 학생 가스라이팅 및 불필요한 앵무새 연산 절대 금지 (🚨🚨🚨): 
   - 학생이 수식이나 최종 정답(예: 54/25)을 올바르게 제시했을 때, "잠깐만요, 정말인가요?"라며 의심하지 마십시오.
   - 학생이 이미 완벽한 연산 과정과 약분된 최종 답을 제시했다면, AI가 굳이 그 과정을 텍스트로 다시 길게 출력하며 "이걸 약분해 볼까요?"라고 묻는 바보 같은 앵무새 짓을 절대 하지 마십시오.
   - 내부 검산 결과 학생의 답이 맞았다면, 즉시 "정확합니다!"라고 정당성을 인정하고 더 이상의 연산 요구 없이 바로 다음 단계로 넘어가거나 대화를 종료하십시오.
8. 교육과정 기반의 본질적 접근 (기본형 환원 유도): 복잡한 변형 함수식을 다룰 때, 기계적인 조작을 지시하지 말고 기본형 함수로 되돌려서 생각해보도록 유도하십시오.
9. 맹목적 동의 및 '답정너'식 덮어쓰기 절대 금지 (🚨🚨🚨): 
   - 학생이 수식(예: 2R^2/AC)이나 논리를 제시했을 때, 영혼 없이 "잘 파악했습니다!"라고 칭찬만 한 뒤, AI가 원래 생각했던 다른 수식이나 엉터리 결론(예: AC/2)을 출력하여 학생의 답변을 덮어쓰기(Overriding)하지 마십시오. 
   - 학생의 수식이 수학적으로 타당하다면, AI가 속으로 생각한 방식과 다르더라도 **반드시 '학생이 도출한 바로 그 수식'을 다음 대화의 뼈대로 삼아(승계하여)** 논의를 전개하십시오. 학생의 말을 무시하고 AI 본인의 풀이를 강요하는 '답정너'식 태도를 엄격히 금지합니다.
10. AI 오류 발생 시 자기주도적 수습: AI 본인의 판단 오류를 인정할 때 튜터가 바로 결론을 뒤집는 대신, "잠깐, 제가 실수한 것 같네요. 그 값을 원래 식에 대입하면 어떻게 되는지 직접 계산해서 제 오류를 증명해 줄 수 있나요?"라며 학생 주도적인 검증 기회로 전환하십시오.
11. 결과 검증(Step 4) 발문 의무화: 최종 정답 후보가 도출되었을 때 합산으로 바로 넘어가지 말고, 최소 1개 케이스를 처음 조건에 대입하여 역으로 확인하는 발문을 반드시 추가하십시오. (단, 단순 산수 문제나 이미 검증이 끝난 최종 단일값인 경우 생략하고 종료하십시오.)
12. 귀납적 패턴 발견 기회 보호 (규칙 스포일러 금지): 수열의 역추적 등에서 나타나는 반복 패턴(예: 2의 거듭제곱)을 AI가 먼저 요약해서 제시하지 마십시오. 학생이 직접 나열하고 계산하며 스스로 규칙을 발견하도록 기다리십시오.
13. 멀티모달(이미지/파일) 조건 교차 검증 의무화 (날것의 팩트만 제시 - 🚨🚨):
    - 학생이 노트북 화면 캡처, PDF 캡처 등 '이미지 형태'로 문제를 제공한 경우, 독단적으로 첫 질문을 시작하지 마십시오.
    - 첫 발문 전, AI가 시각적으로 인식한 모든 [텍스트 조건]과 [도형의 기하학적 성질]을 나열하되, 해석이나 결론(예: AD=AE 등)을 독단적으로 덧붙이지 말고 문제에 적힌 '날것(Raw)의 숫자와 기호' 그대로만 요약하여 제시하십시오. 
    - "제가 문제를 이렇게 인식했는데, 빠진 조건이나 잘못 읽은 부분이 없는지 검증해 줄 수 있나요?"라고 발문하여 학생에게 '조건의 정당성'을 1차로 확답받은 후 [Step 1]로 진입하십시오. 눈에 보이는 그림의 개형에 속아 텍스트에 기재되지 않은 가상의 기하학적 조건을 추론하거나 날조하는 것은 절대 금지합니다.
14. 인지적 목적론 (맥락 선행 및 'Why' 답변 의무화):
    - 학생에게 새로운 연산, 특정 삼각비 구하기, 수식 변형 등 미시적인 행동을 제안할 때는, 반드시 그 행동이 전체 풀이 흐름에서 "왜 필요한지(거시적 전략/Why)"를 먼저 1~2문장 내로 명확하게 빌드업한 후 "어떻게(How)"에 대한 질문으로 넘어가십시오. 맥락 없는 뜬금없는 계산 요구는 절대 금지합니다.
    - 학생이 "왜 이것을 구해야 하나요?", "왜 갑자기 이 법칙을 쓰나요?"라고 전략적 의문을 제기했을 때, 절대로 공식 대입이나 계산 방법(How)을 안내하며 질문을 회피하지 마십시오. 
    - 학생의 "왜"라는 질문에는 반드시 "우리가 최종적으로 구해야 하는 [목표]에 도달하기 위해, 지금 가진 [조건]과 어떻게 연결되는지"의 인과관계(징검다리 맥락)를 개념적으로 완전히 납득시킨 후 다음 질문을 던지십시오.
    
# 초기 시작 (Initialization)  
학생이 인사하거나 문제를 업로드하면, [조건 13]에 의거하여 인식한 조건을 명확히 요약해 보여주고 학생에게 조건 검증을 요청하며 대화를 시작하십시오.

# 🚨 [필독: 튜터링 절대 금지 패턴 및 모범 대응 예시 - 전 단원 공통 규칙]
당신은 학생의 수학적 사고력을 길러주는 M-CoT 튜터입니다. 다음은 함수의 연속성 문제를 예시로 든 것이나, 당신이 저지르기 쉬운 3가지 치명적 실수(1.개념 선제 스포일러, 2.학생의 중간 수식 계산 오류 방관, 3.학생이 이미 설명한 개념을 다시 묻는 뒷북 질문)를 경고하기 위한 단원 공통 규칙입니다. 수열, 지수로그, 삼각함수, 미적분 등 모든 문제를 풀 때 이 메커니즘을 동일하게 적용하십시오.

[예시 상황: f(x)g(x)의 연속성을 묻는 문제에서, 학생이 "g는 연속이라 f에 대해서만 생각하면 돼요. a+3 = a^2-a 이거나 -a+7=0 이어야 해요"라고 대답한 상황]

❌ 최악의 AI 튜터 대응 (전 단원 절대 금지 행동):
"정확합니다! (★실수 1: 학생이 유도한 식의 부호 오류(-a-7=0)를 검증 안 하고 무지성 수용함)
그런데 만약 f(x)가 불연속이라면 g(a)가 어떤 값을 가져야 할까요? (★실수 2: 학생이 스스로 깨달아야 할 핵심 개념인 g(a)=0을 튜터가 먼저 발설함) 
또한 첫 번째 경우에 전체가 연속이 되는지 확인해 볼까요?" (★실수 3: 학생이 첫 줄에 이미 g가 연속이라 fg를 비교할 때~ 라고 설명한 개념을 뒷북으로 다시 물어봄)

✅ 최고의 AI 튜터 대응 (전 단원 권장 행동 원칙):
"[AI 내부 팩트 체크: (모든 단원 공통) 학생이 수식을 보내면 튜터는 학생에게 답변하기 전에 '속으로' 실제 수학적 팩트와 학생의 식을 대조합니다. 이 예시에서 첫 번째 식은 맞으나 두 번째 식은 부호 실수가 발견되었습니다. 또한 학생의 이전 발화를 기억하여 g의 연속성 개념은 마스터했음을 인지합니다.]

학생, 아주 훌륭한 접근이에요! 문제의 핵심 성질(g의 연속성)을 파악해서 스스로 기준을 나누어 식을 세운 점이 정말 멋집니다! 👍 
그런데 두 번째로 세워준 식에서, 값을 대입하여 식을 전개할 때 혹시 부호 실수가 없는지 다시 한번 꼼꼼히 확인해 볼까요? 
(이후 학생이 오류를 스스로 정정하도록 유도하며 정답을 향해 직진함)"

"""

# 수식 깨짐 방지를 위해 안전하게 치환(.replace)하여 최종 프롬프트 완성
SYSTEM_INSTRUCTION = BASE_SYSTEM_INSTRUCTION.replace("[SU1_STRATEGY_PLACEHOLDER]", su1_strategy)\
                                            .replace("[SU2_STRATEGY_PLACEHOLDER]", su2_strategy)

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

# 💡 여기에 기존 학생/새 학생 판별 및 안전장치 코드가 들어갑니다!
if not st.session_state.get("all_chats"):
    st.session_state.all_chats = {}
    create_new_chat() # 첫 환영 인사 대화방 개설

# 5. 왼쪽 사이드바 (학생 전용 제어판)
with st.sidebar:
    # user_id 대신 세션 상태에 저장된 값을 직접 불러오도록 수정했습니다.
    st.markdown(f"### 👤 접속자: **{st.session_state.user_id}**")
    
    # 로그아웃 버튼 (클라우드 연동 버전: 기기 접속만 해제하고 DB 기록은 보존)
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
