from rich import print
import yaml

from typing import TypedDict, Literal
from pydantic import BaseModel, Field

from langchain_core.runnables import RunnableConfig
from langchain.chat_models import init_chat_model

from langgraph.types import interrupt, Command


from src.utils import send_smtp
from src.config import Configuration
from src.prompts import mail_classify_prompt, mail_generate_prompt
from langgraph.checkpoint.memory import MemorySaver    



# ====================
# State Definitions
# ====================
class MailState(TypedDict):
    """메일 생성 및 발송 에이전트 상태
    
    Attributes:
        mail_content (dict): 사용자의 메일 작성 요청 내용 (메일 작성에 필요한 정보)
        send_mail_type (str): 분류된 메일 유형 (예: 일반, 보고서, 견적서 등)
    """
    mail_content: dict
    send_mail_type: str
    result: str 


# ====================
# Structured Output 
# ====================
class MailType(BaseModel):
    type: Literal["일반", "보고서", "견적서_신규고객", "견적서_기존고객"] = Field(description="분류된 메일 유형")

class GenMail(BaseModel):
    title: str = Field(description="생성된 메일 제목")
    context: str = Field(description="생성된 메일 내용")
    
    

# ====================
# Mail Send Agent
# ====================
def mail_classify(state: MailState, config: RunnableConfig) -> Command[Literal["mail_generate", "mail_template"]]:
    """사용자의 요청을 분석하여 메일 유형을 분류하는 노드"""

    configurable = Configuration.from_runnable_config(config)

    # 사용자의 메일 작성 요청 내용
    user_content = state['mail_content']['user_content']
    
    # 메일 유형 분류 모델 
    model_name = configurable.sub_agent_model
    classify_model = init_chat_model(model_name, temperature=0).with_structured_output(MailType)
    
    system_prompt = mail_classify_prompt.format(user_content=user_content)
    response = classify_model.invoke(system_prompt)
    
    # 분류된 메일 유형
    mail_type = response.type
    
    # 메일 유형에 따라 다음 노드로 이동 (일반 메일은 mail_generate, 보고서/견적서는 mail_template)
    return Command(
        goto="mail_generate" if mail_type == "일반" else "mail_template",
        update={"send_mail_type": mail_type}
    )

def mail_generate(state: MailState, config: RunnableConfig):
    """사용자의 요청을 분석하여 메일을 생성하는 노드"""
    
    mail_content = state['mail_content']
    
    configurable = Configuration.from_runnable_config(config)

    model_name = configurable.sub_agent_model
    generate_mail_model = init_chat_model(model_name).with_structured_output(GenMail)
    
    system_prompt = mail_generate_prompt.format(user_content=mail_content['user_content'],
                                                send_name=mail_content['send_name'],
                                                position=mail_content['position'],
                                                ext=mail_content['ext'])
    
    response = generate_mail_model.invoke(system_prompt)

    # 메일 발송에 필요한 정보 구성 state 업데이트 
    mail_content = {
        **mail_content,                         # 기존 메일 내용 유지
        "title": response.title,
        "context": response.context,
        
    }
    
    return {"mail_content": mail_content}


def mail_template(state: MailState):
    """"템플릿 기반의 메일 생성 노드 분류된 메일 유형에 따라 템플릿을 로드하여 메일 제목과 내용을 생성"""
    
    mail_content = state['mail_content']
    
    
    # 메일 템플릿 LOAD
    with open("src/agents/templates.yaml", encoding = 'utf-8') as f:
        templates = yaml.safe_load(f)

    # 메일 유형에 따른 템플릿 선택
    mail_templates = templates[state['send_mail_type']]

    # 메일 생성 
    title = mail_templates['title']
    context = mail_templates['context'].format(**mail_content)

    # 메일 발송에 필요한 정보 구성 state 업데이트 
    mail_content = {
        **mail_content,      # 기존 메일 내용 유지
        "title": title,
        "context": context,
    }

    return {"mail_content": mail_content}


def mail_review(state: MailState) -> Command[Literal["mail_send", "mail_generate"]]:
    """생성된 메일을 사용자에게 보여주고 승인 여부에 따라 다음 행동 결정 노드"""
    
    mail_content = state['mail_content']
    
    # interrupt 메세지 
    interrupt_message = (
        f"""
        생성된 메일을 검토해주세요
        
        메일 제목:
        {mail_content['title']}
        
        메일 내용: 
        {mail_content['context']}"""
        )

    feedback = interrupt(interrupt_message)
    
    if feedback == "승인":
        return Command(goto="mail_send")
    else:
        # "일반" 은 거절된다면 "mail_generate"로 이동 
        updated = {**state['mail_content'], "user_content": feedback}
        return Command(goto='mail_generate', update={"mail_content": updated})


def mail_send(state: MailState):
    """SMTP를 사용하여 메일을 발송하는 노드"""
    
    mail_content = state['mail_content']
    
    send_smtp.invoke(mail_content)
    return {"result": '메일 발송 완료'}


# builder = StateGraph(MailState, config_schema=Configuration)

# builder.add_node("mail_classify", mail_classify) 
# builder.add_node("mail_generate", mail_generate)  
# builder.add_node("mail_template", mail_template)  
# builder.add_node("mail_review", mail_review)  
# builder.add_node("mail_send", mail_send)  

# builder.add_edge(START, "mail_classify")  # Entry point to supervisor
# builder.add_edge("mail_generate", "mail_review")
# builder.add_edge("mail_template", "mail_review")
# builder.add_edge("mail_send", END)


# agent = builder.compile(checkpointer=MemorySaver())


# async def run(msg, config):
        
#     response = await agent.ainvoke(msg, config=config)
    
#     return response

# if __name__ == "__main__":
#     config = {"configurable": {"thread_id": str(uuid.uuid4())}}
    
#     msg = {
#             "mail_content": {
#                 "user_content": "기존 클라이언트에게 작성된 견적서를 전달해줘",
#                 "to_mail": "casu106@naver.com",
#                 "from_mail": "ghmin@stinnovation.co.kr",
#                 "app_password": "jmjopxnhcoxfzujg",
#                 "send_name": "민근홍",
#                 "position": "주임",
#                 "ext": "070-0000-0000",
#                 "files": "C:\\WIP\\agent_system\\src\\agents\\templates.yaml"
#         }
#             }
    
#     import time 
    
#     start = time.time()
#     response = asyncio.run(run(msg, config))
#     asyncio.run(agent.ainvoke(Command(resume="승인"), config=config))
    
#     end = time.time()
#     print(f"Execution Time: {end - start} seconds")
    
