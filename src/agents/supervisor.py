import asyncio
import operator
from rich import print 
from typing import Annotated, Optional, Literal

from langchain.chat_models import init_chat_model
from langchain_core.messages import MessageLikeRepresentation
from langgraph.graph import MessagesState
from pydantic import BaseModel, Field
from typing_extensions import TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.graph import START, END, StateGraph
from langgraph.types import Command

from src.config import Configuration
from src.agents.think_tool import think_tool
from src.prompts import (
    supervisor_system_prompt
    )
from langchain_core.messages import (
    HumanMessage, 
    SystemMessage, 
    AIMessage,
    ToolMessage,
    )

from src.utils import (
    get_today
    )

# ========================================
# Supervisor tool : Sub Agent 작업 위임
# ========================================
class FileSearch(BaseModel):
    """파일 검색 작업 위임"""
    # query: str = Field(description="검색할 파일 키워드")
    # path: str = Field(description="검색 시작 경로", default=".")
    
class EcountSchedule(BaseModel):
    """Ecount 일정 조회 작업 위임"""
    date: str = Field(description="조회할 날짜 (YYYY-MM-DD)")
    
class MailTask(BaseModel):
    """메일 발송 작업 위임"""
    recipient: str = Field(description="받는 사람")
    subject: str = Field(description="제목")
    body: str = Field(description="본문")

class QuotationTask(BaseModel):
    """견적서 처리 작업 위임 (생성, 유사 견적 비교, 분석)"""
    customer_name: str = Field(description="고객명")
    request_details: str = Field(description="견적 요청 상세 내용 (품목, 수량 등)")

class WorkflowComplete(BaseModel):
    """작업 완료 선언"""
    summary: str = Field(description="최종 결과 요약")
    
    
# ====================
# State Definitions
# ====================
class SupervisorState(MessagesState):
    """Supervisor state containing messages and workflow context.

    Attributes:
        messages: 사용자와의 대화 메시지 (MessagesState에서 상속)
        supervisor_messages: Supervisor 내부 사고 및 도구 호출 메시지
        agent_results: 각 에이전트 실행 결과 ({"agent": "file_search", "data": {...}, "summary": "..."})
        workflow_iterations: 워크플로우 반복 횟수 추적 (무한 루프 방지)
        final_response: 최종 사용자 응답 내용
    """

    supervisor_messages: Annotated[list[MessageLikeRepresentation], operator.add]
    agent_results: Annotated[list[dict], operator.add]
    workflow_iterations: int
    final_response: str

# async def supervisor_tools(state: SupervisorState, config: RunnableConfig) -> Command[Literal["supervisor", "__end__"]]:
async def supervisor(state: SupervisorState, config: RunnableConfig):
    """
    사용자의 요청을 처리하기 위해 적절한 하위 에이전트에게 작업을 위임하는 Supervisor

    요청의 의도를 파악하고, 필요한 에이전트를 선택하며, 작업을 순차적으로 실행

    WorkFlow
    1. 사용자 요청 수신 → think_tool로 의도 분석
    2. 적절한 에이전트 선택 (FileSearch, EcountSchedule, MailTask, QuotationTask)
    3. supervisor_tools로 이동하여 선택된 도구 실행
    4. 결과 평가 후 추가 작업 필요 시 반복, 완료 시 WorkflowComplete 호출    
    
    
    Args:
        state: SupervisorState - 현재 상태 정보
        config: RunnableConfig - 구성 정보
        
    Returns:
        도구 실행을 위해 supervisor_tools로 진행하는 Command
    """
    configurable = Configuration.from_runnable_config(config)
    
    # 사용 가능한 tool 정의
    supervisor_tool = [FileSearch, EcountSchedule, MailTask, QuotationTask, WorkflowComplete, think_tool]

    
    # 모델 설정 
    model_name = configurable.supervisor_model
    supervisor_model = (init_chat_model(model_name)
                        .bind_tools(supervisor_tool))
    
    # Supervisor 시스템 프롬프트 설정
    supervisor_prompt = supervisor_system_prompt.format(
        date=get_today(),
        max_workflow_iterations=configurable.max_workflow_iterations
    )
    messages = state.get("messages", [])
    supervisor_messages = state.get("supervisor_messages", [])
    response = await supervisor_model.ainvoke([SystemMessage(content=supervisor_prompt),
                                               messages[-1]] + supervisor_messages)
    
    return Command(goto="supervisor_tools", update={"supervisor_messages": [response]})


async def supervisor_tools(state: SupervisorState, config: RunnableConfig) -> Command[Literal["supervisor", "__end__"]]:
    
    """Supervisor에서 호출한 도구를 실행

    
    Supervisor는 다음 도구를 호출할 수 있음:
    - think_tool: 전략적 사고 및 의사결정 (요청 분석, 에이전트 선택, 결과 평가)
    - FileSearch: 파일 시스템 검색 작업 위임
    - EcountSchedule: Ecount 일정 조회 작업 위임
    - MailTask: 이메일 작성 및 발송 작업 위임
    - QuotationTask: 견적서 생성, 비교, 분석 작업 위임
    - WorkflowComplete: 모든 작업 완료 선언

    각 도구 호출은 ToolMessage로 변환되어 supervisor에게 다시 전송되며,
    supervisor가 진행 상황을 추적하고 다음 단계를 계획할 수 있게함

    Args:
        state: 현재 supervisor 상태
        config: 런타임 구성 정보

    Returns:
        다음 supervisor 단계로 돌아가거나 연구 완료로 진행하는 Command
    """
    
    # 설정 및 현재 State 추출 
    configurable = Configuration.from_runnable_config(config)
    workflow_iterations = state.get("workflow_iterations", 0)
    supervisor_messages = state.get("supervisor_messages", [])
    recent_message = supervisor_messages[-1]
    
    # 반복 종료 조건 
    allowed_iterations = workflow_iterations > configurable.max_workflow_iterations
    no_tool_called = not recent_message.tool_calls
    
    # WorkflowComplete 호출 시 
    workflow_complete = False
    
    for tool_call in recent_message.tool_calls:
        if tool_call["name"] == "WorkflowComplete":
            workflow_complete = True
            break
        
    # Workflow 조건 충족 시 END로 이동 
    if allowed_iterations or no_tool_called or workflow_complete:
        return Command(
            goto=END,
            update = {"final_response": recent_message.content}
            )
    
    # Tool 호출 처리 
    all_tool_messages = []
    update_response = {"supervisor_messages": []}
    
    # Think_tool 
    think_tool_calls = []
    for tool_call in recent_message.tool_calls:
        if tool_call["name"] == "think_tool":
            think_tool_calls.append(tool_call)
        
    for tool_call in think_tool_calls:
        think_content = tool_call['args']['reflection']
        all_tool_messages.append(ToolMessage(
            content=think_content, 
            name = "think_tool",
            tool_call_id = tool_call['id']
        ))
    
    # 다른 도구들 처리~~ 

    file_search_calls = [
        tool_call for tool_call in recent_message.tool_calls 
        if tool_call["name"] == "FileSearch"
    ]
    
    ddd = {
                "messages": state["messages"] + all_tool_messages  # 전체 컨텍스트
            }
    
    print(ddd)
    
    if file_search_calls:
        return Command(
            goto="file_search_agent",
            update={
                "messages": state["messages"] + all_tool_messages  # 전체 컨텍스트
            })
    
    update_response["supervisor_messages"] = all_tool_messages
    return Command(
        goto="supervisor",
        update=update_response
    ) 
    
supervisor_builder = StateGraph(SupervisorState, config_schema=Configuration)

# Add supervisor nodes for research management
supervisor_builder.add_node("supervisor", supervisor)           # Main supervisor logic
supervisor_builder.add_node("supervisor_tools", supervisor_tools)  # Tool execution handler

# Define supervisor workflow edges
supervisor_builder.add_edge(START, "supervisor")  # Entry point to supervisor

# Compile supervisor subgraph for use in main workflow
agent = supervisor_builder.compile()


async def run():
    response = await agent.ainvoke({"messages": '전략기획팀 폴더에서 디딤돌 사업에 있는 파일 어떤거 있는지 확인해줘'}, config=RunnableConfig())
    
    return response

if __name__ == "__main__":
    response = asyncio.run(run())
    print(response)
    
# # # if __name__ == "__main__":
# # #     response = asyncio.run(supervisor({"messages": '전략기획팀 폴더에서 디딤돌 사업계획서 파일 찾아줘'}, config=RunnableConfig()))

# print(response['agent_results'])