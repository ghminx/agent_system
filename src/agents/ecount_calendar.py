import re
from playwright.sync_api import Playwright, sync_playwright, expect
from rich import print

def run(playwright: Playwright, date: str) -> None:

    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    page.goto("https://login.ecount.com/Login/")


    cc = '651820'
    id = 'GHMIN'
    pw = 'ghmin12345'


    page.get_by_role("textbox", name="회사코드").fill(cc)
    page.get_by_role("textbox", name="아이디").fill(id)
    page.get_by_role("textbox", name="비밀번호").fill(pw)

    page.get_by_role("button", name="로그인").click()

    # 네트워크 유휴 상태 대기
    # page.wait_for_load_state('networkidle')
    page.locator('table.caledar').wait_for(state='visible')

    # 수집 할 날짜 선택
    day_cell = page.locator('td[data-role="calendar.addScheduleClick"]', has_text=date)

    day_lst = day_cell.locator('a[data-role="calendar.scheduleClick"]')


    day = []
    for i in range(day_lst.count()):
        day_lst.nth(i).click()
        page.locator('.table-form').wait_for(state='visible')
        
        content = page.locator('.table-form').inner_text()
        
        day.append(content)
        
        page.locator('.ui-dialog-titlebar-close').click()
        
    context.close()
    browser.close()
    
    return day


with sync_playwright() as playwright:
    
    '''
    with 문 없이 사용 
    p = sync_playwright().start()

    browser = p.chromium.launch(headless=False)
    page = browser.new_page()

    page.goto("https://login.ecount.com/Login/")'''

    day = run(playwright, date="30")
    
    
    

from langchain.chat_models import init_chat_model
from langchain.messages import SystemMessage, HumanMessage

prompt = [
    SystemMessage(content= f"""너는 유능한 비서야. {day}는 일정 내용이야. 이 정보를 바탕으로 일정 요약을 작성해줘.
                  
                  만약 등록된 일정이 없으면 "등록된 일정이 없습니다."라고 답변해줘.
                  
                  제목, 날짜/시간, 참석자 정보를 포함해서 간결하게 작성해줘. 
                  
                  Example format:
                  [등록된 일정이 존재 하는 경우]
                  0000년 O월 OO일 일정을 알려드립니다.

                    - 제목: [일정 제목]
                    - 날짜/시간: [날짜/시간]
                    - 참석자: [참석자]
                                      
                  [등록된 일정이 없는 경우]
                    등록된 일정이 없습니다.
                    
                  """),
]

llm = init_chat_model("gpt-4o-mini", temperature=0)

response = llm.stream(prompt)

for chunk in response:
    print(chunk.content, end='', flush=True)


