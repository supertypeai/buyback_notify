import os
from dotenv import load_dotenv
load_dotenv()

# AWS SES
AWS_REGION = os.getenv("AWS_REGION", "ap-southeast-1")
SENDER_EMAIL = os.environ["SENDER_EMAIL"]
RECEIVER_EMAIL = os.environ["RECEIVER_EMAIL"]

# Announcement settings
KEYWORD = os.getenv("KEYWORD", "buyback")
SEEN_FILE = os.getenv("SEEN_FILE", "seen_announcements.json")

# IDX endpoints
IDX_API_URL = "https://www.idx.co.id/primary/NewsAnnouncement/GetAllAnnouncement"
IDX_PAGE_URL = "https://www.idx.co.id/en/news/announcement"