#!/usr/bin/env python3
"""
send_batch.py
- يقرأ emails.csv (عمود مُسمّى "Email")
- يرسل إلى 10 عناوين غير مُرسَلَة بعد لكل تشغيل
- يخزّن العناوين التي أرسِلَت في sent.json
- يدفع (commit + push) sent.json إلى الريبو بحيث لا يعاد الإرسال
"""

import os
import csv
import json
import smtplib
import ssl
import mimetypes
from email.message import EmailMessage
import subprocess
import sys
from pathlib import Path

# -------------------------
# إعداد المسارات والملفات
ROOT = Path.cwd()
CSV_PATH = ROOT / "emails.csv"
SENT_PATH = ROOT / "sent.json"
ATTACHMENTS_DIR = ROOT / "attachments"  # إن أردت إرفاق ملفات ارفعها هنا
MAX_PER_RUN = 10
# -------------------------

# نص الرسالة (خذته من رسالتك)
BODY = """Sehr geehrte Damen und Herren,

hiermit bewerbe ich mich um einen Ausbildungsplatz als Pflegefachmann oder Pflegefachhelfer.

Ich heiße Mohamed Amine Maaroufi, habe das Abitur, ein B2-Deutschzertifikat sowie einige zusätzliche Qualifikationen.

Ich bin sehr motiviert, diesen Beruf zu erlernen und einen Beitrag zur Pflege und Unterstützung von Menschen zu leisten.

Im Anhang finden Sie meine vollständigen Bewerbungsunterlagen.

Ich freue mich sehr auf eine positive Rückmeldung von Ihnen.

Mit freundlichen Grüßen
Mohamed Amine Maaroufi
Marokko
+212 7 03355677
mohammed.amine.maaroufi1@gmail.com
"""

SUBJECT = "Bewerbung um einen Ausbildungsplatz"

def load_emails(csv_path):
    if not csv_path.exists():
        print("ERROR: emails.csv not found.", file=sys.stderr)
        sys.exit(1)
    emails = []
    with csv_path.open(newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        # إذا الملف فيه فقط عمود واحد بلا رأس، ندعمه أيضاً
        if not reader.fieldnames:
            f.seek(0)
            for row in csv.reader(f):
                if row:
                    emails.append(row[0].strip())
            return emails
        # نحاول العثور على العمود الذي يحتوي على كلمة Email (بأي حالة)
        col = None
        for name in reader.fieldnames:
            if name and name.strip().lower() == "email":
                col = name
                break
        if col is None:
            # خذ أول عمود كافتراضي
            col = reader.fieldnames[0]
        for r in reader:
            val = r.get(col)
            if val:
                emails.append(val.strip())
    # إزالة الفارغات وتكرارات بسيطة
    seen = set()
    clean = []
    for e in emails:
        if not e:
            continue
        if e in seen:
            continue
        seen.add(e)
        clean.append(e)
    return clean

def load_sent(path):
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return []

def save_sent(path, sent_list):
    path.write_text(json.dumps(sent_list, indent=2, ensure_ascii=False), encoding='utf-8')

def attach_files(msg, attachments_dir: Path):
    if not attachments_dir.exists() or not attachments_dir.is_dir():
        return
    for p in sorted(attachments_dir.iterdir()):
        if not p.is_file():
            continue
        ctype, encoding = mimetypes.guess_type(str(p))
        if ctype is None:
            maintype, subtype = 'application', 'octet-stream'
        else:
            maintype, subtype = ctype.split('/', 1)
        with p.open('rb') as f:
            data = f.read()
        msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=p.name)

def send_email(smtp_server, smtp_port, smtp_user, smtp_pass, recipient, subject, body, attachments_dir):
    msg = EmailMessage()
    msg['From'] = smtp_user
    msg['To'] = recipient
    msg['Subject'] = subject
    msg.set_content(body)
    attach_files(msg, attachments_dir)

    # SMTP over SSL (port 465)
    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(smtp_server, int(smtp_port), context=context) as server:
        server.login(smtp_user, smtp_pass)
        server.send_message(msg)

def git_commit_and_push(filepaths, actor):
    # تأكد أن git موجود
    try:
        subprocess.run(["git", "--version"], check=True, stdout=subprocess.DEVNULL)
    except Exception as e:
        print("git not available:", e)
        return False

    # جهّز معلومات المؤلف من GITHUB_ACTOR إن وجدت
    actor_name = actor or "github-actions"
    actor_email = f"{actor_name}@users.noreply.github.com"

    subprocess.run(["git", "config", "user.name", actor_name], check=True)
    subprocess.run(["git", "config", "user.email", actor_email], check=True)

    # أضف، كومِت، وبوش
    add_cmd = ["git", "add"] + filepaths
    subprocess.run(add_cmd, check=True)
    commit_msg = f"Update sent list ({', '.join(filepaths)})"
    try:
        subprocess.run(["git", "commit", "-m", commit_msg], check=True)
    except subprocess.CalledProcessError:
        print("Nothing to commit.")
        return True
    # push؛ في GitHub Actions يجب أن تعمل persist-credentials=true في checkout
    subprocess.run(["git", "push"], check=True)
    return True

def main():
    smtp_server = os.getenv("SMTP_SERVER")
    smtp_port = os.getenv("SMTP_PORT")
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASS")
    if not all([smtp_server, smtp_port, smtp_user, smtp_pass]):
        print("ERROR: SMTP credentials not set in environment variables.", file=sys.stderr)
        sys.exit(1)

    emails = load_emails(CSV_PATH)
    sent = load_sent(SENT_PATH)
    unsent = [e for e in emails if e not in sent]

    if not unsent:
        print("No unsent emails left. Exiting.")
        return

    to_send = unsent[:MAX_PER_RUN]
    print(f"Will send to {len(to_send)} recipients this run.")

    sent_now = []
    for recipient in to_send:
        try:
            print(f"Sending to {recipient} ...")
            send_email(smtp_server, smtp_port, smtp_user, smtp_pass, recipient, SUBJECT, BODY, ATTACHMENTS_DIR)
            print("Sent.")
            sent.append(recipient)
            sent_now.append(recipient)
        except Exception as ex:
            print(f"Failed to send to {recipient}: {ex}", file=sys.stderr)

    # احفظ ملف sent.json
    save_sent(SENT_PATH, sent)
    print(f"Saved sent.json with {len(sent)} addresses.")

    # حاول عمل commit + push
    gh_actor = os.getenv("GITHUB_ACTOR")
    try:
        success = git_commit_and_push([str(SENT_PATH)], gh_actor)
        if success:
            print("Committed and pushed sent.json (if changed).")
    except Exception as ex:
        print("Commit/push failed:", ex)

if __name__ == "__main__":
    main()
