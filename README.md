# 💰 Expense Tracker MCP Server

A [Model Context Protocol](https://modelcontextprotocol.io/) server, built with [FastMCP](https://github.com/jlowin/fastmcp), that lets an AI assistant manage your expenses. It logs spending to SQLite and connects to Gmail, Google Drive and Google Calendar. It runs over HTTP, so it can be deployed to the cloud.

![Python](https://img.shields.io/badge/Python-3776AB?logo=python&logoColor=white)
![FastMCP](https://img.shields.io/badge/FastMCP-MCP_Server-6B4FBB)
![Google APIs](https://img.shields.io/badge/Google_APIs-4285F4?logo=google&logoColor=white)

## 🧰 Tools

| Tool | What it does |
|---|---|
| `add_expense(amount, category, notes)` | Records an expense with today's date |
| `list_expenses(start_date, end_date)` | Lists expenses in a date range (defaults to the last 7 days) |
| `summarize_expenses(category)` | Shows a category total or a full spending breakdown |
| `email_weekly_report(recipient_email)` | Emails the summary and itemized list through Gmail SMTP |
| `backup_db_to_drive(folder_id)` | Uploads `expenses.db` to Google Drive |
| `schedule_bill_reminder(bill_name, amount, due_date)` | Creates a Google Calendar reminder for a bill |

`system_tools.py` also includes a system health MCP server (CPU, RAM, disk and uptime dashboard). See [Logs_MCP](https://github.com/Robin-Rajesh/Logs_MCP) for details.

## ⚙️ Configuration

| Variable | Used for |
|---|---|
| `GMAIL_USER`, `GMAIL_APP_PASSWORD` | Sending email reports (use a Gmail [app password](https://support.google.com/accounts/answer/185833)) |
| `GOOGLE_CREDENTIALS_JSON` | Google service account JSON, as a string (for cloud deployments) |
| `PORT` | HTTP port (default `8000`) |

Instead of `GOOGLE_CREDENTIALS_JSON`, you can place a service account file named `credentials.json` in the project folder. It is git-ignored.

## 🚀 Getting Started

```bash
pip install -r requirements.txt
python main.py           # serves the MCP endpoint on http://0.0.0.0:8000
```

Then add the server URL to your MCP client.
