import re
from playwright.sync_api import Playwright, sync_playwright, expect
from rich import print

date = '2025-12-03'
year, month, day = date.split('-')
day = day[1:]  # 0 제거

    
p = sync_playwright().start()

browser = p.chromium.launch(headless=False)
page = browser.new_page()

page.goto("https://login.ecount.com/Login/")

cc = '651820'
id = 'GHMIN'
pw = 'ghmin12345'


page.get_by_role("textbox", name="회사코드").fill(cc)
page.get_by_role("textbox", name="아이디").fill(id)
page.get_by_role("textbox", name="비밀번호").fill(pw)

page.get_by_role("button", name="로그인").click()

# 네트워크 유휴 상태 대기
page.locator('table.caledar').wait_for(state='visible', timeout=10000)



# 수집 할 날짜 선택
# day_cell = page.locator('td[data-role="calendar.addScheduleClick"]', has_text='3')
day_cell = page.locator('td[data-role="calendar.addScheduleClick"]', has_text='3')

day_cell = page.locator(f'span.day:text-is("{day}")')
day_cell.all_inner_texts()



day_lst = day_cell.locator('a[data-role="calendar.scheduleClick"]')
day_lst.all_inner_texts()



dd = []
for i in range(day_lst.count()):
    day_lst.nth(i).click()
    page.locator('.table-form').wait_for(state='visible')
    
    content = page.locator('.table-form').inner_text()
    
    dd.append(content)
    
    page.locator('.ui-dialog-titlebar-close').click()

