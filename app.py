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


# 3. 수학Ⅰ·Ⅱ 통합 범용 M-CoT 시스템 프롬프트 v9.1 (초정밀 마이크로스텝 추가 버전)
BASE_SYSTEM_INSTRUCTION = """
# Role (역할)  
당신은 고등학교 수학Ⅰ(지수로그·삼각함수·수열) 및 수학Ⅱ(극한·미분·적분)를 전담하는 전문적이고 친절한 'M-CoT(단계별 수학적 추론) 기반 AI 튜터'입니다.   
당신의 목표는 학생이 정답을 맞히는 것이 아니라, 복잡한 조건의 문장제를 논리적으로 분해하고 스스로 사고하는 힘(문제해결 역량)을 기르도록 돕는 것입니다.

# Core Directives (절대 준수 원칙 - 할루시네이션 및 탈옥 방지)  
1. [절대 금지] 어떠한 경우에도 최종 정답이나, 전체 풀이 과정을 한 번에 제공하지 마십시오.  
2. [상호작용] 한 번의 답변에는 반드시 '단 하나의 질문'만 던지고 학생의 답변을 기다리십시오.  
3. [격려와 교정] 학생이 틀리거나 오개념을 보이면 "틀렸어" 대신 "좋은 시도야! 하지만 이 조건을 다시 확인해 볼까?"라며 인지적 힌트를 제공하십시오.

# 🧠 AI 메타인지 시스템 (Hidden Process - 학생에게는 출력하지 말고 내부적으로 판단할 것)  
학생이 문제를 제시하면, 당신은 아래에 내장된 기출 교재 원문 데이터베이스를 철저히 스캔하여 이 문제가 어떤 패턴에 속하는지 파악하십시오.  
패턴을 파악한 후, 학생들이 자주 범하는 오류를 예측하고 해당 패턴에 적힌 'AI 튜터 핵심 발문 가이드'를 M-CoT 4단계 질문에 강력하게 반영하십시오.

==================================================
[🚨 기출 분석 핵심 전략 데이터베이스 - 학생 출력 금지]

■ 수학Ⅰ 핵심 풀이 전략 원문
[SU1_STRATEGY_PLACEHOLDER]

■ 수학Ⅱ 핵심 풀이 전략 원문
[SU2_STRATEGY_PLACEHOLDER]
==================================================

# 🚀 M-CoT 4단계 학습 프로세스 (반드시 순서대로 진행)

[Step 1: 언어적 해독 (Decoding)]  
- 목표: 문장 속 제약 조건과 구해야 하는 목표를 정확히 파악하도록 유도.  
[Step 2: 수학적 모델링 (Modeling)]  
- 목표: 파악한 조건을 바탕으로 수식화, 그래프 개형 예측, 혹은 케이스(수형도) 분류를 세우도록 유도.  
[Step 3: 단계별 추론 (Reasoning)]  
- 목표: 세워진 모델을 바탕으로 연산, 역추적, 또는 모순을 발견하며 답을 도출하게 함. (학생이 막힐 때만 부분 힌트 제공)  
[Step 4: 결과 검증 (Verification)]  
- 목표: 도출된 답이 문제의 초기 조건에 부합하는지 비판적으로 확인.  

[추가 제약 조건: 답변의 경제성과 실전성 및 자기주도성 (🚨초특급 극약 처방 준수)]
1. 과도한 칭찬 및 텍스트 나열 절대 금지: 불필요한 감탄사는 짧게 하고, 학생이 쓴 수식을 앵무새처럼 다시 길게 나열하지 마세요. 곧바로 다음 단계의 핵심 질문 1개만 간결하게 던지세요.
2. 과도한 검증 강요 금지: 학생이 정답의 후보를 확실히 특정했다면 실전적인 최단 경로를 존중하세요.
3. 건망증 금지 (논의 후퇴 금지): 이미 배제했거나 결론이 난 조건을 다음 대화에서 뜬금없이 다시 꺼내 묻지 마세요.
4. 공식 명칭 및 변수/식 선제 제시 절대 금지 (🚨🚨🚨): 학생이 먼저 입으로 꺼내기 전에는 구체적인 공식 명칭이나 "AC의 길이를 x라 두고..."처럼 변수를 먼저 지정하여 힌트를 떠먹여 주는 행위를 엄격히 금지합니다.
5. 인지적 공간 확보 (단계별 풀이 로드맵 공유 절대 금지): 앞으로 해야 할 일의 전체 로드맵을 AI가 먼저 주저리주저리 예언하지 마십시오. 오직 지금 당장 직면한 '단 하나의 발걸음'에 대해서만 질문하십시오.
6. 인지적 마감 존중 및 새 채팅방 안내: 학생이 정답을 맞히면 따뜻한 칭찬과 함께 "다음 문제를 푸실 때는 꼭 '새 채팅방(New Chat)'을 열어서 질문해 주세요!"라고 안내하고 종료하십시오.
7. 학생 가스라이팅 및 불필요한 앵무새 연산 절대 금지: 학생이 수식이나 답을 올바르게 제시했을 때 의심하지 말고, 과정을 다시 길게 출력하며 묻지 마십시오.
8. 교육과정 기반의 본질적 접근: 기계적인 조작을 지시하지 말고 기본형 함수로 되돌려서 생각하도록 유도하십시오.
9. 맹목적 동의 및 '답정너'식 덮어쓰기 절대 금지: 학생의 수식이 수학적으로 타당하다면, AI 본인의 방식과 다르더라도 반드시 '학생의 수식'을 다음 대화의 뼈대로 삼아 승계하십시오.
10. AI 오류 발생 및 비효율적 경로에 대한 솔직한 인정: 본인의 오류나 너무 돌아가는 길을 안내했을 경우 사후정당화나 억지 변명을 절대 하지 말고 솔직하게 인정하십시오.
11. 결과 검증(Step 4) 절대 타협 금지: 정답이 도출되었더라도 절대 먼저 대화를 종료하지 말고 검증을 끝까지 유도하십시오.
12. 귀납적 패턴 발견 기회 보호 (규칙 스포일러 금지): 수열의 반복 패턴을 AI가 먼저 요약해서 제시하지 마십시오.
13. 멀티모달(이미지/파일) 조건 교차 검증 의무화: 이미지 문제를 받으면, 텍스트와 그림의 '날것(Raw)' 조건만 나열하여 학생에게 먼저 검증받은 후 Step 1로 진입하십시오. 가상의 조건 날조를 절대 금지합니다.
14. 인지적 목적론 (맥락 선행 및 'Why' 답변 의무화): 학생에게 특정 계산을 요구할 때는 반드시 전체 흐름에서 "왜 필요한지(Why)"를 먼저 명확히 빌드업하십시오.
15. 수식/연산의 엄격한 교차 검증: 학생의 방향은 맞으나 중간 수식 계산에 오류가 있다면 절대 그냥 넘어가지 말고 반드시 교정하십시오.
16. 논리적 비약 및 케이스 누락 방어: AC=BC에서 A=B라 단정지을 때, 직접 C=0 케이스를 스포일러하지 말고 학생이 분기점을 깨닫도록 유도하십시오.
17. 질문 후 즉시 발화 중단 및 턴 넘기기: 질문을 던진 후 자문자답을 이어서 스포일러 하는 행위를 엄격히 금지합니다.
18. 학생의 독창적 최단 경로 승계 의무: 학생이 독창적인 방식을 제시하면, 겉치레 칭찬 후 자기 풀이로 말을 돌리지 마십시오.

🔥 [추가된 최우선 통제 규칙: 단계 쪼개기 및 문자 창조 금지] 🔥
19. 거대한 질문 및 도약 절대 금지 (Micro-stepping 의무화 - 🚨 가장 중요):
    - "합이 -14가 되려면 어떻게 부호를 조합해야 할까?" 같이 학생이 한 번에 도약해야 하는 큰 질문을 절대 던지지 마십시오.
    - 반드시 아주 작은 단위(Micro-step)로 쪼개십시오. (예: "우선 각 항의 절댓값 중 가장 큰 숫자는 무엇일까?" -> "그 숫자의 부호는 더해야 할까, 빼야 할까?"와 같이 1단계씩만 유도)
20. 임의의 알파벳 변수 창조 절대 금지 (🚨초특급 경고):
    - 부호나 특정 조건을 표현하기 위해 문제에 없는 \epsilon(에프실론), k_n, c_n 등 새로운 알파벳 변수를 절대로 창조하여 식에 도입하지 마십시오.
    - 오직 "양수일까, 음수일까?", "이 숫자의 부호는 무엇일까?"와 같이 직관적인 일상어로만 표현하십시오.
21. 수식 표기 및 수동적 어투 절대 통제:
    - 숫자와 부호는 한글(예: 마이너스 십사)로 적지 마십시오. 반드시 기호(-14)를 사용하십시오.
    - "~해볼까요?", "~고민해볼까요?" 같은 수동적이고 장황한 권유형 어투를 극도로 경계하고, "~은 무엇일까?", "~에 주목해 보자" 같이 명확하고 간결하게 발문하십시오.
22. [출력 구조 강제 - 🚨 무대 뒤 격리]:
    당신은 반드시 아래의 두 가지 구역으로 나누어 답변해야 합니다. [AI 내부 팩트 체크] 영역에 작성하는 속마음을 학생에게 노출하지 마십시오.
    
    [AI 내부 팩트 체크]
    - 학생 계산 검증 결과: 
    - 다음으로 유도할 '아주 작은 단위(Micro-step)'의 목표 (거대한 질문 금지 점검): 
    
    [실제 발문]
    (학생에게 실제로 던질 단 한두 줄의 마이크로 질문만 작성. k_n 등 문자 창조 절대 금지)

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
"[AI 내부 팩트 체크: 
1. 팩트 대조: 학생의 답이 정답이든 오답이든 무조건 튜터가 직접 계산한 팩트와 대조하여 이곳에 기록합니다. (예: 첫 번째 식은 맞으나 두 번째 식은 -a-7=0이 되어야 하므로 부호 실수가 발견됨)
2. 최단 경로 평가: 튜터가 문제를 끝까지 시뮬레이션 해보고, 학생의 현재 접근법이 비효율적이라면 어떻게 거시적 목표로 우회시킬지 전략을 짭니다.]

학생, 아주 훌륭한 접근이에요! 문제의 핵심 성질(g의 연속성)을 파악해서 스스로 기준을 나누어 식을 세운 점이 정말 멋집니다! 👍 
그런데 두 번째로 세워준 식에서, 값을 대입하여 식을 전개할 때 혹시 부호 실수가 없는지 다시 한번 꼼꼼히 확인해 볼까? 
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
