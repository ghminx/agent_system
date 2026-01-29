import asyncio
import operator
from rich import print

from typing import Annotated, Optional, Literal

from pydantic import BaseModel, Field

from langchain.chat_models import init_chat_model
from langchain_core.messages import MessageLikeRepresentation
from langgraph.graph import MessagesState

from langchain_core.runnables import RunnableConfig
from langgraph.graph import START, END, StateGraph
from langgraph.types import Command

from src.config import Configuration
from src.prompts import file_search_agent_prompt

from langchain_core.messages import (
    HumanMessage,
    SystemMessage,
    AIMessage,
    ToolMessage,
    get_buffer_string
)



    
    
"""파일 검색 도구 - 파일명, 확장자 기반 검색"""

import os
import re
import fnmatch
from pathlib import Path
from typing import List, Optional
from langchain_core.tools import tool




@tool(description="유연한 파일 검색 (자연어 지원)")
def search_files(
    keywords: str,  # "디딤돌 사업계획서 2024"
    folder: Optional[str] = None,
    extensions: Optional[str] = None  # "pdf,hwp,docx" 또는 None
) -> str:
    """키워드 기반 유연한 파일 검색
    
    Args:
        keywords: 검색 키워드 (공백으로 구분, 순서 무관, 모두 포함)
        folder: Z: 드라이브 내의 폴더 경로 (None이면 Z: 전체 검색)
               예: "전략기획팀", "Z:/전략기획팀"
        extensions: 확장자 (쉼표 구분, 하나라도 일치)
    """
    # 검색 경로 생성
    if folder:
        search_path = os.path.join(r"Z:", folder)
    else:
        search_path = r"Z:"
    
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

                    if len(results) >= 100:  # 최대 결과
                        break
    
    if not results:
        return f"'{keywords}' 키워드와 일치하는 파일을 찾지 못했습니다."
    
    result_str = f"총 {len(results)}개 파일 발견:\n"
    result_str += "\n".join(results)
    return result_str



"""파일 검색 에이전트"""


# ====================
# State Definitions
# ====================
class FileSearchState(MessagesState):
    """파일 검색 에이전트 상태
    
    Attributes:
        messages: 메시지 (MessagesState에서 상속)
        search_results: 검색 결과 리스트
    """
    search_results: Annotated[list[str], operator.add]



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
    
    
    print("=== File Search Agent Response ===")
    print(response)
    
    # 도구 호출이 있으면 실행
    if response.tool_calls:
        tool_messages = []
        search_results = []
        
        for tool_call in response.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            
            print(f"\n=== Calling {tool_name} ===")
            print(f"Args: {tool_args}")
            

            result = search_files.invoke(tool_args)

            
            print(f"Result: {result}")
            
            search_results.append(result)
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
    




