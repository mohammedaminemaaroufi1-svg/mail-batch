#!/usr/bin/env python3
"""
send_batch.py
- كل تشغيل يرسل رسالة واحدة إلى أول عنوان لم يُرسَل له بعد (حسب emails.csv و sent.json)
- إعادة محاولة SMTP حتى 3 مرات (exponential backoff)
- يسجّل إلى sent.json و sent.log
- يقوم بعمل commit+push لـ sent.json فقط إن تغيّر
"""

import os, csv, json, time, smtplib, ssl, mimetypes, subprocess, sys
from email.message import EmailMessage
from pathlib import Path
from datetime import datetime

ROOT = Path.cwd()
CSV_PATH = ROOT / "emails.csv"
SENT_PATH = ROOT / "sent.json"
LOG_PATH = ROOT / "sent.log"
ATTACHMENTS_DIR = ROOT / "attachments"
MAX_PER_RUN = 1            # <<--- أرسل رسالة واحدة فقط في كل تشغيل
SMTP_RETRY_ATTEMPTS = 3
SMTP_RETRY_BASE = 5        # ثواني (لـ exponential backoff)

SUBJECT = "Anfrage zu einer Ausbildung im Pflegebereich"
BODY = """Sehr geehrte Damen und Herren,
hiermit bewerbe ich mich um einen Ausbildungsplatz als Pflegefachmann oder Pflegefachhelfer.
Mein Name ist Mohamed Amine Maaroufi. Ich habe das Abitur und ein Deutschzertifikat auf dem Niveau B2.
Gerne möchte ich nachfragen, ob Sie Bewerbungen von ausländischen Bewerbern annehmen und ob Sie ein anerkannter Ausbildungsbetrieb sind.
Meine Bewerbungsunterlagen finden Sie im Anhang.
Mit freundlichen Grüßen
Mohamed Amine Maaroufi
Marokko
+212 7 03 35 56 77
mohammed.amine.maaroufi1@gmail.com
"""

def log(s):
    ts = datetime.utcnow().isoformat() + "Z"
    line = f"[{ts}] {s}"
    print(line)
    try:
        with LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass

def load_emails(csv_path):
    if not csv_path.exists():
        log("ERROR: emails.csv not found.")
        sys.exit(1)
    emails = []
    with csv_path.open(newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        if reader.fieldnames:
            # العثور على عمود Email أو استعمال العمود الأول
            col = None
            for name in reader.fieldnames:
                if name and name.strip().lower() == "email":
                    col = name
                    break
            if col is None:
                col = reader.fieldnames[0]
            for r in reader:
                val = r.get(col)
                if val:
                    emails.append(val.strip())
        else:
            f.seek(0)
            for r in csv.reader(f):
                if r:
                    emails.append(r[0].strip())
    # تنظيف وتوحيد
    seen = set()
    out = []
    for e in emails:
        if not e: continue
        if e in seen: continue
        seen.add(e)
        out.append(e)
    return out

def load_sent(path):
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return []

def save_sent(path, sent_list):
    path.write_text(json.dumps(sent_list, indent=2, ensure_ascii=False), encoding='utf-8')

def attach_files(msg, attachments_dir):
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

def send_email_once(smtp_server, smtp_port, smtp_user, smtp_pass, recipient, subject, body, attachments_dir):
    msg = EmailMessage()
    msg['From'] = smtp_user
    msg['To'] = recipient
    msg['Subject'] = subject
    msg.set_content(body)
    attach_files(msg, attachments_dir)
    context = ssl.create_default_context()

    last_exc = None
    for attempt in range(1, SMTP_RETRY_ATTEMPTS + 1):
        try:
            # استخدم SMTP SSL (port 465)
            with smtplib.SMTP_SSL(smtp_server, int(smtp_port), context=context, timeout=30) as server:
                server.login(smtp_user, smtp_pass)
                server.send_message(msg)
            return True, None
        except Exception as e:
            last_exc = e
            wait = SMTP_RETRY_BASE * (2 ** (attempt - 1))
            log(f"Warning: send attempt {attempt} to {recipient} failed: {e} — retry in {wait}s")
            time.sleep(wait)
    return False, last_exc

def git_commit_and_push_if_changed(filepaths, actor):
    try:
        subprocess.run(["git", "--version"], check=True, stdout=subprocess.DEVNULL)
    except Exception as e:
        log(f"git not available: {e}")
        return False
    actor_name = actor or os.getenv("GITHUB_ACTOR") or "github-actions"
    actor_email = f"{actor_name}@users.noreply.github.com"
    try:
        subprocess.run(["git", "config", "user.name", actor_name], check=True)
        subprocess.run(["git", "config", "user.email", actor_email], check=True)
        subprocess.run(["git", "add"] + filepaths, check=True)
        commit_msg = f"Update sent list: {', '.join(filepaths)}"
        res = subprocess.run(["git", "diff", "--staged", "--quiet"])
        # إذا هناك تغييرات ستقوم العملية commit
        subprocess.run(["git", "commit", "-m", commit_msg], check=True)
        subprocess.run(["git", "push"], check=True)
        log("Committed and pushed changes.")
        return True
    except subprocess.CalledProcessError as e:
        log("No changes to commit or commit failed.")
        return False
    except Exception as ex:
        log(f"Commit/push failed: {ex}")
        return False

def main():
    smtp_server = os.getenv("SMTP_SERVER")
    smtp_port = os.getenv("SMTP_PORT")
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASS")
    if not all([smtp_server, smtp_port, smtp_user, smtp_pass]):
        log("ERROR: SMTP credentials not set in environment variables.")
        sys.exit(1)

    emails = load_emails(CSV_PATH)
    sent = load_sent(SENT_PATH)
    unsent = [e for e in emails if e not in sent]

    if not unsent:
        log("No unsent addresses left. Exiting.")
        return

    to_send = unsent[:MAX_PER_RUN]
    log(f"Will send to {len(to_send)} recipient(s) this run.")

    sent_now = []
    for recipient in to_send:
        log(f"Sending to {recipient} ...")
        ok, exc = send_email_once(smtp_server, smtp_port, smtp_user, smtp_pass, recipient, SUBJECT, BODY, ATTACHMENTS_DIR)
        if ok:
            log(f"Sent to {recipient}.")
            sent.append(recipient)
            sent_now.append(recipient)
        else:
            log(f"Failed to send to {recipient}: {exc}")

    if sent_now:
        # احفظ sent.json
        try:
            save_sent(SENT_PATH, sent)
            log(f"Saved sent.json ({len(sent)} total).")
        except Exception as e:
            log(f"Failed to save sent.json: {e}")

        # حاول commit+push فقط إذا تغيّر sent.json
        gh_actor = os.getenv("GITHUB_ACTOR")
        try:
            git_commit_and_push_if_changed([str(SENT_PATH)], gh_actor)
        except Exception as ex:
            log(f"Commit/push error: {ex}")

if __name__ == "__main__":
    main()
