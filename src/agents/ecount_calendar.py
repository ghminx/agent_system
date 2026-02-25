import os
import re
from playwright.sync_api import Playwright, sync_playwright, expect
from playwright.async_api import async_playwright

from rich import print
from dotenv import load_dotenv

from langchain.tools import tool 
from langchain.chat_models import init_chat_model
from langchain.agents import create_agent
from langchain.messages import SystemMessage, HumanMessage

from src.utils import get_today

load_dotenv()




@tool
async def ecount_calendar_tool(date: str) -> list:
    
    """Ecount에 접속하여 특정 날짜에 등록된 일정을 크롤링하여 리스트로 반환하는 Tool 

    Args:
        date (int): 조회할 날짜(YYYY-MM-DD) 

    Returns:
        list: 크롤링된 일정 내용 리스트
    """
    
    year, month, day = date.split('-')
    day = day.lstrip("0")

    # with sync_playwright() as playwright:
    async with async_playwright() as playwright:

        browser = await playwright.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        
        await page.goto("https://login.ecount.com/Login/")
        await page.get_by_role("textbox", name="회사코드").fill(os.getenv('ECOUNT_CODE'))
        await page.get_by_role("textbox", name="아이디").fill(os.getenv('ECOUNT_ID'))
        await page.get_by_role("textbox", name="비밀번호").fill(os.getenv('ECOUNT_PW'))
        await page.get_by_role("button", name="로그인").click()

        # 네트워크 유휴 상태 대기
        await page.locator('table.caledar').wait_for(state='visible', timeout=10000)
        
        # 수집 할 날짜 선택
        # day_cell = page.locator('td[data-role="calendar.addScheduleClick"]', has_text=day)
        day_cell = page.locator(f'xpath=//span[contains(@class,"day") and normalize-space()="{day}"]/ancestor::td[1]')

        day_lst = day_cell.locator('a[data-role="calendar.scheduleClick"]')

        event = []
        for i in range(await day_lst.count()):
            await day_lst.nth(i).click()
            await page.locator('.table-form').wait_for(state='visible')

            content = await page.locator('.table-form').inner_text()
            event.append(content)
            
            await page.locator('.ui-dialog-titlebar-close').click()
            
        if not event:
            event.append("등록된 일정이 없습니다.")    
            
        await context.close()
        await browser.close()
        
        return event
        
    
    
system_prompt = """너는 Ecount에 등록된 일정을 알려주는 유능한 비서야 

                오늘은 {today} 이야.

                사용자가 원하는 날짜에 어떤 일정이 등록되어있는지 알려줘.
                
                사용자가 년도와 월을 명시하지 않으면, 오늘 날짜의 년도와 월을 기준으로 일정을 찾아줘.
                  
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
                    
                  """

system_prompt = system_prompt.format(today=get_today())


agent = create_agent(
    "openai:gpt-4o-mini",
    tools=[ecount_calendar_tool],
    system_prompt=system_prompt,
)


async def run(day):

    response = await agent.ainvoke({"messages": [{"role": "user", "content": f"2월 {day}일 등록된 일정 알려줘"}]})

    print(response['messages'][-1].content)

if __name__ == "__main__":
    import asyncio
    
    asyncio.run(run(24))