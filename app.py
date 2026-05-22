import streamlit as st
import google.generativeai as genai

# 1. 페이지 설정 및 디자인
st.set_page_config(page_title="M-CoT AI 수학 튜터", page_icon="🧮", layout="centered")
st.title("🧠 2026 수능형 문장제 완파! M-CoT AI 수학 튜터")
st.caption("정답은 알려주지 않아요! 단계별 질문을 따라 스스로 생각해보세요.")

# 2. 구글 Gemini API 연동 (환경 변수 또는 입력창)
# 테스트의 편의성을 위해 화면에서 직접 API Key를 입력받도록 설계했습니다.
if "api_key" not in st.session_state:
    st.session_state.api_key = ""

with st.sidebar:
    st.header("⚙️ 설정")
    user_key = st.text_input("Google API Key를 입력하세요", type="password", value=st.session_state.api_key)
    if user_key:
        st.session_state.api_key = user_key

if not st.session_state.api_key:
    st.warning("왼쪽 사이드바에 Google API Key를 입력해야 튜터링이 시작됩니다.")
    st.stop()

# API 설정 활성화
genai.configure(api_key=st.session_state.api_key)

# 3. 우리가 설계한 고도화된 M-CoT 프롬프트 v2.0 이식
SYSTEM_INSTRUCTION = """
당신은 고등학교 수학I 및 수학II를 전담하는 전문적인 'M-CoT(단계별 수학적 추론) 기반 AI 튜터'입니다.
목표는 학생이 정답을 맞히는 것이 아니라, 복잡한 조건의 문장제를 논리적으로 분해하고 스스로 사고하는 힘을 기르도록 돕는 것입니다.

[절대 준수 원칙]
1. 어떠한 경우에도 최종 정답이나 전체 풀이 과정을 한 번에 제공하지 마십시오.
2. 한 번의 답변에는 반드시 '단 하나의 질문'만 던지고 학생의 답변을 기다리십시오.
3. 학생이 틀리면 "틀렸어" 대신 인지적 힌트(비계)를 제공하십시오.

[메타인지 스캔 및 M-CoT 4단계 순차 진행]
- 학생이 문제를 주면 수학I 10대 패턴 및 수학II 13대 패턴을 내부적으로 분류하고 오답을 예측하십시오.
- Step 1(언어적 해독) -> Step 2(수학적 모델링) -> Step 3(단계별 추론) -> Step 4(결과 검증)를 철저히 지키며 상호작용하십시오.
"""

# 4. 챗봇 대화 기록 초기화
if "messages" not in st.session_state:
    st.session_state.messages = []
    # 첫 인사 자동 생성
    st.session_state.messages.append({"role": "assistant", "content": "반갑습니다! 오늘 함께 고민해볼 수학I 또는 수학II 문장제 문제를 올려주세요. 가장 먼저 주의 깊게 봐야 할 제약 조건부터 함께 찾아봅시다!"})

# 기존 대화 렌더링
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# 5. 학생의 입력 처리 및 AI 답변 생성
if prompt := st.chat_input("문제를 입력하거나 AI 튜터의 질문에 답해보세요!"):
    # 학생 메시지 표시 및 저장
    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    # Gemini 모델 호출 (무료이며 빠른 gemini-1.5-flash 모델 적용)
    try:
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            system_instruction=SYSTEM_INSTRUCTION
        )
        
        # 이전 대화 맥락 반영을 위한 포맷팅
        chat_history = []
        for msg in st.session_state.messages[:-1]:
            role = "user" if msg["role"] == "user" else "model"
            chat_history.append({"role": role, "parts": [msg["content"]]})
        
        chat = model.start_chat(history=chat_history)
        response = chat.send_message(prompt)
        
        # AI 답변 표시 및 저장
        with st.chat_message("assistant"):
            st.markdown(response.text)
        st.session_state.messages.append({"role": "assistant", "content": response.text})
        
    except Exception as e:
        st.error(f"오류가 발생했습니다: {e}")
