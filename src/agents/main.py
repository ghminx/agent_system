import asyncio
from rich import print 

from langgraph.graph import START, END, StateGraph

from src.config import Configuration

from src.agents.supervisor import supervisor, supervisor_tools, SupervisorState
from src.agents.file_search import file_search_agent
from src.agents.send_mail import MailState, mail_classify, mail_generate, mail_template, mail_review, mail_send
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver    
from langgraph.types import interrupt, Command


# Mail Agent Graph
mail_builder = StateGraph(MailState, config_schema=Configuration)

mail_builder.add_node("mail_classify", mail_classify) 
mail_builder.add_node("mail_generate", mail_generate)  
mail_builder.add_node("mail_template", mail_template)  
mail_builder.add_node("mail_review", mail_review)  
mail_builder.add_node("mail_send", mail_send)  

mail_builder.add_edge(START, "mail_classify")  # Entry point to supervisor
mail_builder.add_edge("mail_generate", "mail_review")
mail_builder.add_edge("mail_template", "mail_review")
mail_builder.add_edge("mail_send", END)

supervisor_builder = StateGraph(SupervisorState, config_schema=Configuration)

# Add supervisor nodes for research management
supervisor_builder.add_node("supervisor", supervisor)           # Main supervisor logic
supervisor_builder.add_node("supervisor_tools", supervisor_tools)  # Tool execution handler
supervisor_builder.add_node("file_search_agent", file_search_agent)  # File search agent node
supervisor_builder.add_node("send_mail_agent", mail_builder.compile())  # File search agent node

# Define supervisor workflow edges
supervisor_builder.add_edge(START, "supervisor")  # Entry point to supervisor

# Compile supervisor subgraph for use in main workflow
agent = supervisor_builder.compile(checkpointer=MemorySaver())


async def run(config):
    # user =  '전략기획팀 폴더에서 2026년에 작성한 디딤돌 사업에 있는 파일 어떤거 있는지 확인해줘 pdf만'
    
    
    user = """
            {
                    "user_content": "발주처에게 보고서 결과가 아쉽다는 메일을 보내야하는데 메일 안을 작성해줘 조심스럽고 죄송한 어조로 작성해줘",
                    "to_mail": "casu106@naver.com",
                    
                    "from_mail": "ghmin@stinnovation.co.kr",
                    "app_password": "jmjopxnhcoxfzujg",
                    "send_name": "민근홍",
                    "position": "주임",
                    "ext": "070-0000-0000",
                    "files": "C:\\WIP\\agent_system\\src\\agents\\templates.yaml"
                    
                }
            """
    
    
    # response = await agent.ainvoke({"messages": user}, config=RunnableConfig())
    response = await agent.ainvoke({"messages": user}, config=config)
    
    return response

if __name__ == "__main__":
    import time 
    import uuid 
    
    config = {"configurable": {"thread_id": str(uuid.uuid4())}}
    
    start = time.time()
    response = asyncio.run(run(config))
    asyncio.run(agent.ainvoke(Command(resume="승인"), config=config))
    end = time.time()
    print(f"Execution Time: {end - start} seconds")

print(response)


