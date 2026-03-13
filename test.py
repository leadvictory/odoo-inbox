import smtplib
from imapclient import IMAPClient
from email.message import EmailMessage
from email.utils import make_msgid, formatdate
from datetime import datetime, timezone

IMAP_SERVER = "mail2.streamstorm.tv"
IMAP_PORT = 993

SMTP_SERVER = "mail2.streamstorm.tv"
SMTP_PORT = 465

EMAIL = "info@performance-ag.ch"
PASSWORD = "0TXK$ZWQLkr9Kf9l"

TO_EMAIL = "intelliresponse911@gmail.com"


# -----------------------
# Create message
# -----------------------
msg = EmailMessage()

msg["Subject"] = "Python IMAPClient test"
msg["From"] = EMAIL
msg["To"] = TO_EMAIL
msg["Message-ID"] = make_msgid()
msg["Date"] = formatdate(localtime=True)

msg.set_content("Plain text fallback")
msg.add_alternative("<h3>Hello</h3><p>Email sent with Python</p>", subtype="html")

raw_message = msg.as_bytes()


# -----------------------
# Send email via SMTP
# -----------------------
with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as smtp:
    smtp.login(EMAIL, PASSWORD)
    smtp.send_message(msg)

print("Email sent")


# -----------------------
# Save email to Sent folder using IMAPClient
# -----------------------
with IMAPClient(IMAP_SERVER, port=IMAP_PORT, ssl=True) as imap:
    imap.login(EMAIL, PASSWORD)

    # If your Thunderbird shows folder "Sent", this is correct
    sent_folder = "Sent"

    imap.append(
        sent_folder,
        raw_message,
        flags=["\\Seen"],
        msg_time=datetime.now(timezone.utc)
    )

print("Email saved to Sent folder")