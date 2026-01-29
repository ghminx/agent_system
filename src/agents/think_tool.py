"""Think tool for Supervisor strategic planning and analysis."""

from langchain_core.tools import tool


@tool(description="Strategic thinking tool for request analysis and agent orchestration planning")
def think_tool(reflection: str) -> str:
    """Tool for strategic reflection on user request analysis and agent orchestration.

    Use this tool to create deliberate decision-making pauses in the workflow.
    This enables systematic analysis of user requests and thoughtful agent selection.

    When to use:
    - Before agent selection: What is the user really asking for?
    - After analyzing request: Which agents are needed and in what order?
    - After agent execution: Did the result meet the user's needs?
    - Before responding: Is additional agent execution needed?
    - When planning complex workflows: How should multiple agents be orchestrated?

    Do NOT extract specific parameters like:
    - File paths, folder names, or file extensions
    - Dates or time ranges
    - Email addresses or recipients
    - Any other detailed parameters

    Reflection should address:
    1. Request analysis - What is the core intent of the user's request?
    2. Agent selection - Which agent(s) should handle this task?
       - file_search: 파일 탐색이 필요한가?
       - ecount: Ecount 일정 조회가 필요한가?
       - mail: 메일 작성/발송이 필요한가?
       - quotation: 견적서 처리가 필요한가?
    3. Execution strategy - Should agents run sequentially or is one enough?
    4. Intermediate results - What did the previous agent find? Is it sufficient?
    5. Next step decision - Continue with another agent, or provide final response?

    Examples:
    - "User wants to find files related to '계약서'. Need file_search agent."
    - "User wants to check today's schedule. Need ecount agent."
    - "User requested quotation comparison. Need quotation agent, then mail agent to send results."
    - "file_search found 3 files. User's request is satisfied. Ready to respond."

    Args:
        reflection: Your detailed strategic thinking about the request, agent selection,
                   execution results, and next steps

    Returns:
        Confirmation that reflection was recorded
    """
    return f"Strategic reflection recorded: {reflection}"


# @tool(description="요청 분석 및 에이전트 조율 계획을 위한 전략적 사고 도구")
# def think_tool_kr(사고_내용: str) -> str:
#     """사용자 요청 분석 및 에이전트 조율을 위한 전략적 사고 도구.

#     워크플로우에서 의도적인 의사결정 중단 지점을 만들기 위해 이 도구를 사용합니다.
#     이를 통해 사용자 요청을 체계적으로 분석하고 신중한 에이전트 선택이 가능합니다.

#     사용 시점:
#     - 에이전트 선택 전: 사용자가 진짜 원하는 것이 무엇인가?
#     - 요청 분석 후: 어떤 에이전트가 필요하고 어떤 순서로 실행할까?
#     - 에이전트 실행 후: 결과가 사용자의 요구를 충족했는가?
#     - 응답 전: 추가 에이전트 실행이 필요한가?
#     - 복잡한 워크플로우 계획 시: 여러 에이전트를 어떻게 조율할까?

#     사고 내용에 포함할 요소:
#     1. 요청 분석 - 사용자 요청의 핵심 의도는 무엇인가?
#     2. 에이전트 선택 - 어떤 에이전트가 이 작업을 처리해야 하는가?
#        - file_search: 파일 탐색이 필요한가?
#        - ecount: Ecount 일정 조회가 필요한가?
#        - mail: 메일 작성/발송이 필요한가?
#        - quotation: 견적서 처리가 필요한가?
#     3. 실행 전략 - 에이전트를 순차적으로 실행해야 하는가, 하나로 충분한가?
#     4. 중간 결과 - 이전 에이전트가 무엇을 찾았는가? 충분한가?
#     5. 다음 단계 결정 - 다른 에이전트를 계속 실행할 것인가, 최종 응답을 제공할 것인가?

#     예시:
#     - "사용자가 '계약서' 관련 파일을 찾고 싶어함. file_search 에이전트 필요."
#     - "사용자가 오늘 일정을 확인하고 싶어함. ecount 에이전트 필요."
#     - "사용자가 견적 비교를 요청함. quotation 에이전트 실행 후 mail 에이전트로 결과 발송 필요."
#     - "file_search가 3개 파일을 찾음. 사용자 요청이 충족됨. 응답 준비 완료."

#     Args:
#         사고_내용: 요청, 에이전트 선택, 실행 결과, 다음 단계에 대한 상세한 전략적 사고

#     Returns:
#         사고 내용이 기록되었다는 확인 메시지
#     """
#     return f"전략적 사고 기록됨: {사고_내용}"
