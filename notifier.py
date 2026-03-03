import boto3
from datetime import datetime
from config import AWS_REGION, SENDER_EMAIL, RECEIVER_EMAIL, KEYWORD, IDX_PAGE_URL


def _build_email(matches: list[dict]) -> tuple[str, str, str]:
    """Return (subject, html_body, text_body) for the notification email"""
    subject = (
        f"[IDX Alert] {len(matches)} new '{KEYWORD}' announcement(s) "
        f"— {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    )

    rows_html = ""
    rows_text = ""
    for a in matches:
        rows_html += (
            "<tr>"
            f'<td style="padding:8px;border:1px solid #ddd;">{a["date"]}</td>'
            f'<td style="padding:8px;border:1px solid #ddd;">{a["company"]}</td>'
            f'<td style="padding:8px;border:1px solid #ddd;">'
            f'<a href="{a["link"]}">{a["title"]}</a></td>'
            "</tr>"
        )
        rows_text += (
            f"  - [{a['date']}] {a['company']} — {a['title']}\n"
            f"    {a['link']}\n\n"
        )

    html_body = f"""\
<html><body style="font-family:Arial,sans-serif;color:#333;">
  <h2 style="color:#c0392b;">📢 IDX Buyback Announcement Alert</h2>
  <p>The following new <strong>"{KEYWORD}"</strong> announcements were found on
     <a href="{IDX_PAGE_URL}">IDX</a>:</p>
  <table style="border-collapse:collapse;width:100%;font-size:14px;">
    <thead>
      <tr style="background:#2c3e50;color:#fff;">
        <th style="padding:8px;">Date</th>
        <th style="padding:8px;">Company</th>
        <th style="padding:8px;">Title</th>
      </tr>
    </thead>
    <tbody>{rows_html}</tbody>
  </table>
  <p style="margin-top:16px;font-size:12px;color:#888;">
    Sent automatically by buyback_notify · {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
  </p>
</body></html>"""

    text_body = f"New '{KEYWORD}' announcements on IDX:\n\n{rows_text}"

    return subject, html_body, text_body


def send_email(matches: list[dict]):
    """Send an HTML email via AWS SES listing all new buyback announcements."""
    subject, html_body, text_body = _build_email(matches)

    ses = boto3.client("ses", region_name=AWS_REGION)
    ses.send_email(
        Source=SENDER_EMAIL,
        Destination={"ToAddresses": [RECEIVER_EMAIL]},
        Message={
            "Subject": {"Data": subject, "Charset": "UTF-8"},
            "Body": {
                "Text": {"Data": text_body, "Charset": "UTF-8"},
                "Html": {"Data": html_body, "Charset": "UTF-8"},
            },
        },
    )

    print(f"✅ Email sent via SES: {subject}")
