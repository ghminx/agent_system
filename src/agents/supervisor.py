import asyncio
import operator
from rich import print 
from typing import Annotated, Optional

from langchain.chat_models import init_chat_model
from langchain_core.messages import MessageLikeRepresentation
from langgraph.graph import MessagesState
from pydantic import BaseModel, Field

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END
from langgraph.types import Command

from src.config import Configuration
from src.prompts import (
    supervisor_system_prompt
    )
from langchain_core.messages import (
    SystemMessage, 
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
    user_content: str = Field(description="사용자 요청 내용 (메일 작성에 필요한 정보)")
    to_mail: str = Field(description="수신자 메일")
    from_mail: str = Field(description="발신자 메일")
    app_password: str = Field(description="발신자 메일 앱 비밀번호")
    send_name: str = Field(description="발신자 이름")
    position: str = Field(description="발신자 직책")
    ext: str = Field(description="발신자 내선번호")
    files : Optional[str] = Field(description="첨부파일 경로 (선택사항)", default=None)
    

    
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
    mail_content: dict

async def supervisor(state: SupervisorState, config: RunnableConfig):
    """
    사용자의 요청을 처리하기 위해 적절한 하위 에이전트에게 작업을 위임하는 Supervisor

    요청의 의도를 파악하고, 필요한 에이전트를 선택하며, 작업을 순차적으로 실행

    WorkFlow
    1. 사용자 요청 수신 → think_tool로 의도 분석
    2. 적절한 에이전트 선택 (FileSearch, EcountSchedule, MailTask, QuotationTask)
    3. supervisor_tools로 이동하여 선택된 도구 실행
    
    
    Args:
        state: SupervisorState - 현재 상태 정보
        config: RunnableConfig - 구성 정보
        
    Returns:
        도구 실행을 위해 supervisor_tools로 진행하는 Command
    """
    configurable = Configuration.from_runnable_config(config)
    
    # 사용 가능한 tool 정의
    supervisor_tool = [FileSearch, EcountSchedule, MailTask]

    
    # 모델 설정 
    model_name = configurable.supervisor_model
    supervisor_model = (init_chat_model(model_name, thinking={"type": "enabled", "budget_tokens": 5000})
                        .bind_tools(supervisor_tool))
    
    # Supervisor 시스템 프롬프트 설정
    supervisor_prompt = supervisor_system_prompt.format(
        date=get_today(),
        max_workflow_iterations=configurable.max_workflow_iterations
    )
    messages = state.get("messages", [])
    supervisor_messages = state.get("supervisor_messages", [])
    
    response = await supervisor_model.ainvoke([SystemMessage(content=supervisor_prompt)] +
                                               messages + supervisor_messages)
    
    return Command(goto="supervisor_tools", update={"supervisor_messages": [response]})


async def supervisor_tools(state: SupervisorState, config: RunnableConfig):
    
    """Supervisor에서 호출한 도구를 실행

    Supervisor는 다음 도구를 호출할 수 있음:
    - FileSearch: 파일 시스템 검색 작업 위임
    - MailTask: 이메일 작성 및 발송 작업 위임
    - EcountSchedule: Ecount 일정 조회 작업 위임

    각 도구 호출은 ToolMessage로 변환되어 supervisor에게 다시 전송되며,
    supervisor가 진행 상황을 추적하고 다음 단계를 계획할 수 있게함

    Args:
        state: 현재 supervisor 상태
        config: 런타임 구성 정보

    Returns:
        다음 supervisor 단계로 돌아가거나 연구 완료로 진행하는 Command
    """
    
    # 설정 및 현재 State 추출 
    supervisor_messages = state.get("supervisor_messages", [])
    recent_message = supervisor_messages[-1]
    

    # Tool 호출 처리 
    for tool_call in recent_message.tool_calls:
        
        # FileSearch 도구 호출 처리
        if tool_call["name"] == "FileSearch":
            
            tool_messages = ToolMessage(
                            content="FileSearch 도구 실행",
                            name=tool_call["name"],
                            tool_call_id=tool_call["id"])
                    
            return Command(
                goto="file_search_agent",
                update={
                    "supervisor_messages": [tool_messages]
                })

        elif tool_call["name"] == "MailTask":
            
            return Command(
                goto="send_mail_agent",
                update={
                    "mail_content": tool_call["args"]
                })
            
        elif tool_call["name"] == "EcountSchedule":
            
            return None
        

    # 도구 호출이 없으면 종료 돌아감
    return Command(goto=END)

