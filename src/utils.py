from datetime import datetime
import smtplib
import imaplib
import time
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from email.utils import formatdate, make_msgid
from langchain.tools import tool 


def get_today() -> str:
    """현재 날짜를 YYYY-MM-DD 형식으로 반환"""
    return datetime.now().strftime("%Y-%m-%d")



@tool("send_mail", description="SMTP를 사용하여 이메일을 보내는 도구. 메일 발송에 필요한 정보를 입력받아 이메일을 발송.")
def send_smtp(from_mail,
              to_mail,
              app_password,
              title,
              context,
              files,
              send_name,
              **kwargs) -> dict:
    """SMTP를 사용하여 이메일을 보내고, 보낸편지함에 기록하는 함수

    Args:
        from_mail (str): 메일 발신자 주소
        to_mail (str): 메일 수신자 주소
        app_password (str): 발신자 메일 계정의 앱 비밀번호
        title (str): 메일 제목
        context (str): 메일 본문 내용
        files (str): 파일 경로

    Returns:
        dict: _description_
    """

    # 제목 및 본문
    smtp = MIMEMultipart()
    smtp["Subject"] = title  # 제목
    smtp["From"] = from_mail # 발신자
    smtp["To"] = to_mail     # 수신자
    smtp["Message-ID"] = make_msgid()
    # smtp.attach(MIMEText(context, _charset="utf-8")) # 본문 내용

    html_context = context.replace("\n", "<br>")
    
    # 서명 HTML 생성
    content = f"""
    <html>
    <body>
        <div>
        {html_context}
        </div>

    <div style="background: url('https://st-research.co.kr/images/member/[STR]_이메일서명_(중기부)_{send_name}.png') no-repeat;
                width:700px;
                height:340px;
                margin-top:50px;">
    </body>
    </html>
    """

    # 본문을 HTML로 첨부
    smtp.attach(MIMEText(content, "html", _charset="utf-8"))
    
    # 첨부파일
    if files:
        file_path = Path(files)
        with file_path.open("rb") as f:
            part = MIMEApplication(f.read(), _subtype="octet-stream")   # _subtype="octet-stream" : 일반 바이너리 파일로 취급
            part.add_header("Content-Disposition", "attachment", filename=file_path.name)
            smtp.attach(part)

    # SMTP 전송
    with smtplib.SMTP_SSL("smtp.daum.net", 465) as server:
        server.login(from_mail, app_password)
        server.send_message(smtp)

    # 보낸편지함 기록
    raw_bytes = smtp.as_bytes()
    with imaplib.IMAP4_SSL("imap.daum.net", 993) as imap:
        imap.login(from_mail, app_password)
        imap.append(
            "Sent",
            None,
            imaplib.Time2Internaldate(time.time()),
            raw_bytes,
        )
        
