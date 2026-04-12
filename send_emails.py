import csv
import json
import os
import smtplib
import time
from datetime import date
from email.message import EmailMessage

# ===== بيانات Gmail =====

SMTP_USER = "bghit.mokabalamaakoum@gmail.com"

# هنا سيأتي App Password من GitHub Secret
SMTP_PASS = os.environ.get("SMTP_PASS")

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 465

PDF_FILE = "Unterlagen M ezzouain.pdf"
CONTACTS_FILE = "contacts.csv"
STATE_FILE = "state.json"

SUBJECT = "Bewerbung als Pflegefachmann"

BODY = """Sehr geehrte Damen und Herren,

mein Name ist Mohammed Ez Zouain. Hiermit bewerbe ich mich um einen Ausbildungsplatz als Pflegefachmann in Ihrer Einrichtung.

Ich verfüge über fließende Deutschkenntnisse und bin hochmotiviert, meine kommunikativen Fähigkeiten und meine Empathie in Ihr Team einzubringen. Die Pflege ist für mich eine Herzensangelegenheit.

Anbei erhalten Sie meine Bewerbungsunterlagen als PDF.

Mit freundlichen Grüßen

Mohammed Ez zouain
"""

# ===== قراءة الحالة =====

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)

    state = {
        "start_date": date.today().isoformat(),
        "cursor": 0
    }

    with open(STATE_FILE, "w") as f:
        json.dump(state, f)

    return state

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)

# ===== قراءة contacts =====

def load_contacts():

    contacts = []

    with open(CONTACTS_FILE, newline="", encoding="utf-8") as file:

        reader = csv.DictReader(file)

        for row in reader:

            contacts.append({
                "email": row["email"],
                "name": row.get("name", "")
            })

    return contacts

# ===== حساب عدد الرسائل حسب اليوم =====

def compute_batch_size(start_date):

    start = date.fromisoformat(start_date)

    days = (date.today() - start).days + 1

    if days > 20:
        return 20

    return days

# ===== إنشاء رسالة =====

def build_message(to_email):

    msg = EmailMessage()

    msg["Subject"] = SUBJECT
    msg["From"] = SMTP_USER
    msg["To"] = to_email

    msg.set_content(BODY)

    with open(PDF_FILE, "rb") as pdf:

        msg.add_attachment(
            pdf.read(),
            maintype="application",
            subtype="pdf",
            filename="Unterlagen.pdf"
        )

    return msg

# ===== الإرسال =====

def send_batch():

    state = load_state()

    contacts = load_contacts()

    batch_size = compute_batch_size(
        state["start_date"]
    )

    cursor = state["cursor"]

    print("Batch size today:", batch_size)

    with smtplib.SMTP_SSL(
        SMTP_SERVER,
        SMTP_PORT
    ) as smtp:

        smtp.login(
            SMTP_USER,
            SMTP_PASS
        )

        for i in range(batch_size):

            index = (cursor + i) % len(contacts)

            email = contacts[index]["email"]

            msg = build_message(email)

            smtp.send_message(msg)

            print("Sent to:", email)

            time.sleep(10)

    state["cursor"] = (
        cursor + batch_size
    ) % len(contacts)

    save_state(state)

# ===== تشغيل =====

if __name__ == "__main__":
    send_batch()
