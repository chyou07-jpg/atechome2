"""회의 메모 → Word 회의 결과 보고서 생성기 (Streamlit + Gemini)."""

from __future__ import annotations

import io
import json
import re
from datetime import date
from pathlib import Path

from google import genai
from google.genai import types
import streamlit as st
from docxtpl import DocxTemplate

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent if BASE_DIR.name == "meeting_report" else BASE_DIR


def find_template_path() -> Path:
    candidates = [
        PROJECT_ROOT / "회의 결과 보고서 템플릿.docx",
        PROJECT_ROOT / "회의결과 보고서 템플릿" / "회의 결과 보고서 템플릿.docx",
    ]
    for path in candidates:
        if path.exists():
            return path
    return candidates[0]

REPORT_FIELDS = [
    ("date", "일시"),
    ("location", "회의 장소"),
    ("attendees", "참석자"),
    ("reporter", "보고자"),
    ("title", "회의명"),
    ("agenda", "회의 안건"),
    ("content", "회의 내용"),
    ("tasks", "향후 업무 계획"),
    ("references", "참고 자료"),
]

SYSTEM_PROMPT = """당신은 회의 메모를 공식 회의 결과 보고서 형식으로 정리하는 전문 비서입니다.
입력된 회의 메모(대화 내용)를 분석하여 아래 JSON 형식으로만 응답하세요. 다른 설명은 절대 포함하지 마세요.

## 출력 형식 (JSON만)
{
  "date": "회의 일시 (메모에 없으면 오늘 날짜 사용, 예: 2026년 7월 9일)",
  "location": "회의 장소",
  "attendees": "참석자 (쉼표로 구분)",
  "reporter": "보고자",
  "title": "회의명",
  "agenda": "회의 안건 (개조식, 각 항목은 '- '로 시작)",
  "content": "회의 내용",
  "tasks": "향후 업무 계획",
  "references": "참고 자료 (없으면 '없음')"
}

## 작성 규칙

### 공통
- 대화체를 그대로 복사하지 말고, 개조식 보고서 말투로 정리합니다.
- 회의에서 나온 주요 논의와 결정사항이 빠짐없이 반영되어야 합니다.
- 메모에 없는 정보는 합리적으로 추론하되, 확실하지 않으면 '미정'으로 표시합니다.

### agenda (회의 안건)
- 각 항목은 '- '로 시작하는 짧은 개조식 문장으로 작성합니다.

### content (회의 내용)
- 내용에 맞는 소제목 2~3개로 나눕니다.
- 소제목은 '■'로 시작합니다 (예: ■ 프로젝트 일정 논의).
- 각 소제목 아래는 '- '로 시작하는 짧은 개조식 문장으로 정리합니다.
- 소제목 사이는 빈 줄(\\n\\n)로 구분합니다.

### tasks (향후 업무 계획)
- '반영', '확정', '정리' 등 실행 의미가 있는 문장을 빠짐없이 포함합니다.
- 담당자·마감일이 있으면 함께 표시합니다.
- 담당자가 불명확하면 '김팀장/전체'처럼 표시합니다.
- 같은 담당자는 이름을 한 번만 적고, 아래에 '- ' 리스트로 업무를 묶습니다.
- 형식 예시:
  ■ 김팀장
  - 7월 15일까지 견적서 제출
  - 고객사 피드백 반영

  ■ 전체
  - 7월 말까지 최종안 확정

### references (참고 자료)
- 참고 자료가 없으면 반드시 '없음'으로 표시합니다.

### date (일시)
- 오늘 날짜: {today}
- 메모에 회의 일시가 명시되어 있으면 그것을 사용하고, 없으면 오늘 날짜를 사용합니다.
"""


def get_gemini_api_key() -> str | None:
    try:
        return st.secrets["GEMINI_API_KEY"]
    except (KeyError, FileNotFoundError):
        return None


def get_gemini_model() -> str:
    try:
        return st.secrets["GEMINI_MODEL"]
    except (KeyError, FileNotFoundError):
        return "gemini-2.0-flash-lite"


def format_gemini_error(exc: Exception) -> str:
    msg = str(exc)
    if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
        return (
            "Gemini API **사용 한도(quota)를 초과**했습니다.\n\n"
            "**해결 방법**\n"
            "1. **1~2분 후** 다시 시도 (분당 요청 제한)\n"
            "2. [Google AI Studio](https://aistudio.google.com/apikey)에서 "
            "**`AIzaSy`로 시작하는** Gemini API 키를 새로 발급\n"
            "3. `secrets.toml`에 다른 모델 지정:\n"
            "   `GEMINI_MODEL = \"gemini-2.0-flash-lite\"`\n"
            "4. [사용량 확인](https://aistudio.google.com/) → API 키별 quota 확인"
        )
    return msg


def extract_json(text: str) -> dict:
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if fence:
        text = fence.group(1).strip()
    return json.loads(text)


def format_report_with_gemini(memo: str) -> dict:
    api_key = get_gemini_api_key()
    if not api_key:
        raise ValueError(
            "Gemini API 키가 설정되지 않았습니다. "
            ".streamlit/secrets.toml 파일에 GEMINI_API_KEY를 추가해 주세요."
        )

    client = genai.Client(api_key=api_key)

    today = date.today().strftime("%Y년 %m월 %d일")
    prompt = SYSTEM_PROMPT.replace("{today}", today) + f"\n\n## 회의 메모\n{memo}"

    response = client.models.generate_content(
        model=get_gemini_model(),
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
        ),
    )
    result = extract_json(response.text or "")

    if not result.get("references"):
        result["references"] = "없음"
    if not result.get("date"):
        result["date"] = today

    return result


def build_docx(context: dict) -> bytes:
    template_path = find_template_path()
    if not template_path.exists():
        raise FileNotFoundError(f"Word 템플릿을 찾을 수 없습니다: {template_path}")

    doc = DocxTemplate(str(template_path))
    doc.render(context)
    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()


def init_session_state() -> None:
    defaults = {
        "report_data": None,
        "memo_input": "",
        "step": 1,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def render_header() -> None:
    st.set_page_config(
        page_title="회의 결과 보고서 생성기",
        page_icon="📋",
        layout="wide",
    )
    st.title("📋 회의 결과 보고서 생성기")
    st.caption("회의 메모를 입력하면 AI가 정리하고, Word 보고서로 다운로드할 수 있습니다.")


def render_step1() -> None:
    st.subheader("1단계 · 회의 메모 입력")
    memo = st.text_area(
        "회의 메모 (대화 내용 그대로 붙여넣기)",
        value=st.session_state.memo_input,
        height=320,
        placeholder="예)\n김팀장: 오늘 신규 프로젝트 일정 논의하겠습니다.\n이대리: 견적서는 다음 주까지 제출 가능합니다.\n...",
    )
    st.session_state.memo_input = memo

    if st.button("AI로 회의록 정리하기", type="primary", disabled=not memo.strip()):
        with st.spinner("Gemini가 회의 내용을 정리하는 중..."):
            try:
                st.session_state.report_data = format_report_with_gemini(memo.strip())
                st.session_state.step = 2
                st.rerun()
            except Exception as exc:
                st.error(format_gemini_error(exc))


def render_step2() -> None:
    st.subheader("2단계 · 내용 확인 및 수정")

    if st.button("← 메모 입력으로 돌아가기"):
        st.session_state.step = 1
        st.rerun()

    data = st.session_state.report_data or {}
    edited: dict[str, str] = {}

    col1, col2 = st.columns(2)
    with col1:
        for key, label in REPORT_FIELDS[:5]:
            edited[key] = st.text_input(
                label,
                value=data.get(key, ""),
                key=f"field_{key}",
            )
    with col2:
        edited["agenda"] = st.text_area(
            "회의 안건",
            value=data.get("agenda", ""),
            height=120,
            key="field_agenda",
        )
        edited["references"] = st.text_input(
            "참고 자료",
            value=data.get("references", "없음"),
            key="field_references",
        )

    edited["content"] = st.text_area(
        "회의 내용 (소제목: ■, 항목: -)",
        value=data.get("content", ""),
        height=280,
        key="field_content",
    )
    edited["tasks"] = st.text_area(
        "향후 업무 계획 (담당자별 그룹)",
        value=data.get("tasks", ""),
        height=220,
        key="field_tasks",
    )

    st.session_state.report_data = edited

    st.divider()
    st.subheader("3단계 · Word 다운로드")

    safe_title = re.sub(r'[\\/:*?"<>|]', "_", edited.get("title", "회의결과보고서"))
    filename = f"{safe_title or '회의결과보고서'}.docx"

    try:
        docx_bytes = build_docx(edited)
        st.download_button(
            label="📥 Word 보고서 다운로드",
            data=docx_bytes,
            file_name=filename,
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            type="primary",
        )
    except Exception as exc:
        st.error(f"Word 파일 생성 중 오류: {exc}")


def main() -> None:
    init_session_state()
    render_header()

    if not get_gemini_api_key():
        st.warning(
            "`.streamlit/secrets.toml`에 `GEMINI_API_KEY`를 설정해 주세요. "
            "예시는 `.streamlit/secrets.toml.example`을 참고하세요."
        )
    elif not get_gemini_api_key().startswith("AIza"):
        st.warning(
            "현재 API 키 형식이 일반 Gemini API 키(`AIzaSy...`)와 다릅니다. "
            "[Google AI Studio](https://aistudio.google.com/apikey)에서 "
            "Gemini API 키를 새로 발급받아 `secrets.toml`에 넣어 주세요."
        )

    if st.session_state.step == 1 or not st.session_state.report_data:
        render_step1()
    else:
        render_step2()


if __name__ == "__main__":
    main()
