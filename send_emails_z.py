import csv
import os
import smtplib
import time
from email.message import EmailMessage

# =============================
# إعدادات الحساب الثاني
# =============================

SMTP_USER = "min.fadlikoumforsa1@gmail.com"

# App Password من GitHub Secrets
SMTP_PASS = os.environ["SMTP_PASS_Z"]

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 465

# =============================
# الملفات
# =============================

CONTACTS_FILE = "contacts-Z.csv"

PDF_FILE = "Bewerbung-Zakriae.pdf"

SUBJECT = "Bewerbung um einen Ausbildungsplatz"

# =============================
# نص الرسالة
# =============================

BODY = """Sehr geehrte Damen und Herren,

mein Name ist Zakariae Kassaba. Hiermit bewerbe ich mich um einen Ausbildungsplatz in Ihrem Unternehmen.

Ich spreche Deutsch gut und verfüge über Deutschkenntnisse auf dem Niveau B2.

Im Anhang finden Sie meine vollständigen Unterlagen. Ich würde mich sehr freuen, wenn Sie mir die Chance zu einem Vorstellungsgespräch geben würden.

Ich freue mich auf Ihre Rückmeldung und hoffe auf eine positive Antwort.

Mit freundlichen Grüßen

Zakariae Kassaba
"""

# =============================
# قراءة الإيميلات
# =============================

def load_contacts():

    contacts = []

    with open(CONTACTS_FILE, newline="", encoding="utf-8") as f:

        reader = csv.DictReader(f)

        for row in reader:

            email = (row.get("email") or "").strip()

            if email:
                contacts.append(email)

    return contacts


# =============================
# إنشاء الرسالة
# =============================

def build_message(to_email):

    msg = EmailMessage()

    msg["Subject"] = SUBJECT
    msg["From"] = SMTP_USER
    msg["To"] = to_email

    msg.set_content(BODY)

    # إضافة PDF

    with open(PDF_FILE, "rb") as f:

        msg.add_attachment(
            f.read(),
            maintype="application",
            subtype="pdf",
            filename=PDF_FILE
        )

    return msg


# =============================
# الإرسال
# =============================

def main():

    contacts = load_contacts()

    if not contacts:
        print("No contacts found.")
        return

    with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as smtp:

        smtp.login(SMTP_USER, SMTP_PASS)

        for email in contacts:

            try:

                msg = build_message(email)

                smtp.send_message(msg)

                print("Sent to:", email)

                # انتظار 10 ثواني
                time.sleep(10)

            except Exception as e:

                print("Error sending to", email, ":", str(e))


if __name__ == "__main__":
    main()
