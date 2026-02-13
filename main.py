import os
import sqlite3
import smtplib
import json  # <--- NEW: Required for secure loading
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, List, Tuple, Any, Dict

from fastmcp import FastMCP
from google.oauth2 import service_account
from googleapiclient.discovery import build, Resource
from googleapiclient.http import MediaFileUpload

# --- CONFIGURATION & ENV VARS ---
PORT: int = int(os.environ.get("PORT", 8000))
DB_FILE: str = "expenses.db"

# Credentials
GMAIL_USER: Optional[str] = os.environ.get("GMAIL_USER")
GMAIL_APP_PASSWORD: Optional[str] = os.environ.get("GMAIL_APP_PASSWORD")
SERVICE_ACCOUNT_FILE: str = "credentials.json"

# Initialize MCP Server
mcp = FastMCP("expense-tracker")

# --- DATABASE INIT ---
def init_db() -> None:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            amount REAL,
            category TEXT,
            notes TEXT,
            date TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

# --- HELPER: SMART GOOGLE AUTH ---
def get_google_service(api_name: str, version: str) -> Optional[Resource]:
    """
    Authenticates using a Secure Environment Variable (Cloud) OR a local file (Laptop).
    """
    SCOPES = [
        'https://www.googleapis.com/auth/calendar',
        'https://www.googleapis.com/auth/drive.file'
    ]
    
    creds = None
    
    # 1. Try Secure Environment Variable (Cloud Method)
    json_creds_text = os.environ.get("GOOGLE_CREDENTIALS_JSON")
    
    if json_creds_text:
        try:
            creds_dict = json.loads(json_creds_text)
            creds = service_account.Credentials.from_service_account_info(
                creds_dict, scopes=SCOPES
            )
            print("🔐 Authenticated via Environment Variable.")
        except json.JSONDecodeError as e:
            print(f"❌ Error decoding secure JSON: {e}")
            return None
            
    # 2. Fallback to Local File (Laptop Method)
    elif os.path.exists(SERVICE_ACCOUNT_FILE):
        try:
            creds = service_account.Credentials.from_service_account_file(
                SERVICE_ACCOUNT_FILE, scopes=SCOPES
            )
            print("📂 Authenticated via local credentials.json file.")
        except Exception as e:
             print(f"❌ Error reading local file: {e}")
             return None
    
    else:
        print("❌ No credentials found! Set GOOGLE_CREDENTIALS_JSON or add credentials.json")
        return None

    try:
        service = build(api_name, version, credentials=creds)
        return service
    except Exception as e:
        print(f"❌ Google Service Build Failed: {e}")
        return None

# --- TOOL 1: ADD EXPENSE ---
@mcp.tool()
def add_expense(amount: float, category: str, notes: str) -> str:
    """Add a new expense."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    date_str = datetime.now().strftime("%Y-%m-%d")
    cursor.execute(
        "INSERT INTO expenses (amount, category, notes, date) VALUES (?, ?, ?, ?)",
        (amount, category, notes, date_str)
    )
    conn.commit()
    conn.close()
    return f"✅ Added: ${amount} for {category} ({notes})"

# --- TOOL 2: LIST EXPENSES ---
@mcp.tool()
def list_expenses(start_date: Optional[str] = None, end_date: Optional[str] = None) -> str:
    """List expenses by date."""
    if not start_date:
        start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    if not end_date:
        end_date = datetime.now().strftime("%Y-%m-%d")

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM expenses WHERE date BETWEEN ? AND ?", 
        (start_date, end_date)
    )
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        return f"ℹ️ No expenses found between {start_date} and {end_date}."

    report = f"📉 Expenses from {start_date} to {end_date}:\n"
    for row in rows:
        report += f"- {row[4]}: ${row[1]} ({row[2]}) | {row[3]}\n"
    return report

# --- TOOL 3: SUMMARIZE ---
@mcp.tool()
def summarize_expenses(category: Optional[str] = None) -> str:
    """Show spending totals."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    msg = ""
    if category:
        cursor.execute("SELECT SUM(amount) FROM expenses WHERE category = ?", (category,))
        res = cursor.fetchone()
        total = res[0] if res and res[0] is not None else 0.0
        msg = f"💰 Total spent on {category}: ${total}"
    else:
        cursor.execute("SELECT category, SUM(amount) FROM expenses GROUP BY category")
        rows = cursor.fetchall()
        if not rows: return "No expenses recorded yet."
        msg = "📊 Spending Breakdown:\n"
        grand_total = 0.0
        for cat, amount in rows:
            msg += f"- {cat}: ${amount}\n"
            grand_total += amount
        msg += f"\n🔥 TOTAL SPENT: ${grand_total}"

    conn.close()
    return msg

# --- TOOL 4: EMAIL REPORT ---
@mcp.tool()
def email_weekly_report(recipient_email: str) -> str:
    """Email the summary via Gmail."""
    if not GMAIL_USER or not GMAIL_APP_PASSWORD:
        return "❌ Error: Gmail credentials missing."

    report_content = summarize_expenses()
    detailed_list = list_expenses()
    
    full_body = f"""
    Expense Report:
    {report_content}
    ----------------
    Details:
    {detailed_list}
    """

    msg = MIMEMultipart()
    msg['From'] = GMAIL_USER
    msg['To'] = recipient_email
    msg['Subject'] = f"Expense Report - {datetime.now().strftime('%Y-%m-%d')}"
    msg.attach(MIMEText(full_body, 'plain'))

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_USER, recipient_email, msg.as_string())
        server.quit()
        return f"✅ Email sent to {recipient_email}"
    except Exception as e:
        return f"❌ Email Failed: {str(e)}"

# --- TOOL 5: BACKUP TO DRIVE ---
@mcp.tool()
def backup_db_to_drive(folder_id: Optional[str] = None) -> str:
    """Upload database to Google Drive."""
    service = get_google_service('drive', 'v3')
    if not service: return "❌ Google Auth Failed."

    file_metadata = {
        'name': f"backup_expenses_{datetime.now().strftime('%Y-%m-%d')}.db",
        'mimeType': 'application/x-sqlite3'
    }
    if folder_id: file_metadata['parents'] = [folder_id]

    media = MediaFileUpload(DB_FILE, mimetype='application/x-sqlite3')

    try:
        file = service.files().create(
            body=file_metadata, media_body=media, fields='id'
        ).execute()
        return f"✅ Backup Success! File ID: {file.get('id')}"
    except Exception as e:
        return f"❌ Drive Upload Failed: {str(e)}"

# --- TOOL 6: CALENDAR REMINDER ---
@mcp.tool()
def schedule_bill_reminder(bill_name: str, amount: float, due_date: str) -> str:
    """Add reminder to Google Calendar."""
    service = get_google_service('calendar', 'v3')
    if not service: return "❌ Google Auth Failed."

    try:
        start_dt = datetime.strptime(due_date, "%Y-%m-%d")
        end_dt = start_dt + timedelta(hours=1)
    except ValueError:
        return "❌ Invalid date. Use YYYY-MM-DD."

    event_body = {
        'summary': f"💰 Pay {bill_name} (${amount})",
        'description': f'Reminder to pay {bill_name}.',
        'start': {'dateTime': start_dt.isoformat(), 'timeZone': 'UTC'},
        'end': {'dateTime': end_dt.isoformat(), 'timeZone': 'UTC'},
    }

    try:
        event = service.events().insert(calendarId='primary', body=event_body).execute()
        return f"✅ Reminder Set: {event.get('htmlLink')}"
    except Exception as e:
        return f"❌ Calendar Failed: {str(e)}"

if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=PORT)