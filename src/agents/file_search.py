import os 
import asyncio
import operator
from rich import print

from typing import Annotated, Optional



from langchain_core.runnables import RunnableConfig
from langchain.chat_models import init_chat_model
from langchain_core.tools import tool

from langgraph.graph import MessagesState
from langgraph.graph import START, END, StateGraph
from langgraph.types import Command


from langchain_core.messages import (
    HumanMessage,
    SystemMessage,
    ToolMessage,
    get_buffer_string
)


from src.config import Configuration
from src.prompts import file_search_agent_prompt

    
    
"""파일 검색 도구 - 파일명, 확장자 기반 검색"""





@tool(description="재귀적 파일 검색 도구. 키워드를 전체 경로(폴더+파일명)에서 검색. 자연어 키워드 지원, 부분 매칭 가능. Z: 드라이브 기준.")
def search_files(
    keywords: str,
    folder: Optional[str] = None,
    extensions: Optional[str] = None
) -> str:
    """키워드 기반 재귀 파일 검색 (전체 경로 매칭)

    Z: 드라이브에서 키워드를 "폴더 경로 + 파일명" 전체에서 검색합니다.
    자연어 키워드 지원, 부분 매칭 가능, 하위 폴더 자동 탐색.

    검색 방식:
        - 재귀 검색: folder 아래 모든 하위 폴더를 자동으로 탐색
        - 전체 경로 매칭: 키워드를 "폴더 경로 + 파일명"에서 검색
        - 부분 매칭: "디딤돌 사업" → "2026_디딤돌 지원 사업" 폴더와 매칭
        - 키워드 순서 무관: "디딤돌 사업계획서" = "사업계획서 디딤돌"
        - 모든 키워드 포함: 전체 경로에 모든 키워드가 있어야 함

    Args:
        keywords (str): 검색 키워드 (공백으로 구분, 순서 무관, 모두 포함해야 함)
            예: "디딤돌 사업 사업계획서" → "디딤돌", "사업", "사업계획서" 모두 포함된 파일
            예: "2024 계약서" → "2024", "계약서" 모두 포함된 파일

        folder (Optional[str]): Z: 드라이브 내의 검색 시작 폴더 (None이면 Z: 전체 검색)
            예: "전략기획팀" → Z:/전략기획팀 아래 모든 하위 폴더 검색
            예: "Documents/Projects" → Z:/Documents/Projects 아래 검색
            예: None → Z: 드라이브 전체 검색

        extensions (Optional[str]): 확장자 필터 (쉼표 구분, 하나라도 일치하면 포함)
            예: "pdf" → PDF 파일만
            예: "pdf,hwp,docx" → PDF, HWP, DOCX 파일만
            예: None → 모든 확장자

    Returns:
        str: 검색 결과 문자열
            성공: "총 N개 파일 발견:\n파일경로1\n파일경로2\n..."
            실패: "'키워드' 키워드와 일치하는 파일을 찾지 못했습니다."

    Notes:
        - 최대 100개 파일까지 반환
        - 대소문자 구분 없음 (자동 소문자 변환)
        - 경로가 존재하지 않으면 에러 메시지 반환
    """
    # 검색 경로 생성
    if folder:
        search_path = os.path.join(r"Z:/", folder)
    else:
        search_path = r"Z:/"
    
    # 경로 존재 확인
    if not os.path.exists(search_path):
        return f"경로를 찾을 수 없습니다: {search_path}"
    
    # 키워드 파싱
    keyword_list = keywords.lower().split()
    
    # 확장자 파싱
    ext_list = None
    if extensions:
        ext_list = [f".{ext.strip().lower().lstrip('.')}" for ext in extensions.split(',')]
    
    results = []

    # 파일 검색
    for root, dirs, files in os.walk(search_path):
        for filename in files:
            # 전체 경로 생성 (폴더 경로 + 파일명)
            full_path = os.path.join(root, filename)
            full_path_lower = full_path.lower()

            # 모든 키워드가 전체 경로에 포함되어야 함 (순서 무관)
            if all(kw in full_path_lower for kw in keyword_list):
                # 확장자 체크
                filename_lower = filename.lower()
                if not ext_list or any(filename_lower.endswith(ext) for ext in ext_list):
                    results.append(full_path)

                    if len(results) >= 20:  # 최대 결과
                        break
    
    if not results:
        return f"'{keywords}' 키워드와 일치하는 파일을 찾지 못했습니다."

    files_by_dir = {}
    for path in results:
        dirname = os.path.dirname(path)
        filename = os.path.basename(path)
        
        if dirname not in files_by_dir:
            files_by_dir[dirname] = []
            
        files_by_dir[dirname].append(filename)        


    blocks = []
    for directory in sorted(files_by_dir):
        lines = [f"📁 {directory}"]

        for filename in files_by_dir[directory]:
            lines.append(f"- {filename}")
        
        blocks.append('\n'.join(lines))

    return '\n\n'.join(blocks)



"""파일 검색 에이전트"""
# ====================
# State Definitions
# ====================
class FileSearchState(MessagesState):
    """파일 검색 에이전트 상태
    
    Attributes:
        messages: 메시지 (MessagesState에서 상속)
        search_results: 검색 결과 문자열
    """
    search_results: str



# ====================
# File Search Agent
# ====================
async def file_search_agent(state: FileSearchState, config: RunnableConfig):
    """파일 검색 에이전트
    
    사용자 요청을 분석하여 적절한 검색 도구를 선택하고 실행
    
    Args:
        state: FileSearchState - 현재 상태
        config: RunnableConfig - 구성 정보
        
    Returns:
        검색 결과를 포함한 상태 업데이트
    """
    configurable = Configuration.from_runnable_config(config)
    
    # 사용 가능한 검색 도구
    search_tools = [search_files]
    
    # 모델 설정
    model_name = configurable.sub_agent_model
    file_search_model = (init_chat_model(model_name)
                         .bind_tools(search_tools))
    
    messages = state.get("messages", [])
    
    system_prompt = file_search_agent_prompt.format(
        messages = get_buffer_string(messages)
    )
    
    # LLM 호출
    response = await file_search_model.ainvoke([SystemMessage(content=system_prompt)])
    
    # 도구 호출이 있으면 실행
    if response.tool_calls:
        tool_messages = []
        search_results = ''
        
        for tool_call in response.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            
            try:
                result = await search_files.ainvoke(tool_args)
            except Exception as e:
                result = f"파일 검색 도구 실행 중 오류 발생: {str(e)}"
            
            search_results = result
            tool_messages.append(ToolMessage(
                content=result,
                name=tool_name,
                tool_call_id=tool_call["id"]
            ))
        
        return Command(
            goto=END,
            update={
                "messages": [response] + tool_messages,
                "search_results": search_results
            }
        )
    
    # 도구 호출 없으면 그냥 종료
    return Command(
        goto=END,
        update={"messages": [response]}
    )


# ====================
# Build Agent
# ====================
file_search_builder = StateGraph(FileSearchState, config_schema=Configuration)
file_search_builder.add_node("file_search_agent", file_search_agent)
file_search_builder.add_edge(START, "file_search_agent")

file_search_agent_graph = file_search_builder.compile()


# ====================
# Test
# ====================
state = {
    'messages': [
        HumanMessage(
            content='전략기획팀 폴더에서 2026년 디딤돌 사업에 있는 사업계획서 파일 찾아줘',
            additional_kwargs={},
            response_metadata={},
            id='5f29da7e-a123-4e89-a290-a7f310496fa1'
        ),
        ToolMessage(
            content="사용자 요청: 전략기획팀 폴더에서 2026년 디딤돌 사업에 있는 사업계획서 파일 찾아줘. 이건 단일 작업으로 FileSearch에이전트만 필요. 전략: FileSearch에게 검색경로/키워드로 \'전략기획팀/디딤돌 사업\' 또는 폴더 내\'디딤돌\' 관련 파일을 찾도록 지시. 결과로 파일명,   전체 경로, 파일 유형(예: docx, xlsx, pdf), 마지막    수정일을 포함한 목록을 받는다. 다음 단계: FileSearch 호출.",
            name='think_tool',
            tool_call_id='call_VW4EeayQdZyuFzGPMHqtuyG9'
        )
    ]
}


async def test_file_search():
    """파일 검색 에이전트 테스트"""
    response = await file_search_agent_graph.ainvoke(
        state,
        config=RunnableConfig()
    )
    
    return response


if __name__ == "__main__":
    response = asyncio.run(test_file_search())


print(response['search_results'])