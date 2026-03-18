import os
import csv
import urllib.request
from google import genai
from datetime import datetime, timedelta

# ==========================================
# 1. WEEKLY SETTINGS (Update these each week!)
# ==========================================
CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSKKcq07WVCePpVsrX-1pNn5PBiDHZoV3Svl0EHIEelISNHJCnvndvUrlxaa4SZRm1y7YnbIiWkUgaj/pub?output=csv" 

# The Workspace Update
WORKSPACE_ARTICLE_URL = "https://workspaceupdates.googleblog.com/2026/03/improving-connection-between-Google-Calendar-events-and-Google-Meet-calls.html"
FEATURED_COURSE_NAME = "Meeting the Future"
FEATURED_COURSE_URL = "https://training.ceyx.app/{{ client_id }}/learn/courses/14/meeting-the-future"

# Your Clients and their Banner Images
# Your Clients and their Banner Images
CLIENTS = {
    "livelearningco": "https://gcehif.stripocdn.email/content/guids/CABINET_ccbfbb74097fc5c6468b2533f6ce6a32909772bbb1aa99cb6260df642c16ff90/images/emailbanner_livelearningco_1.png",
    "b2b": "https://raw.githubusercontent.com/Morgan-dar/WeeklyComms/main/Emailbanner%20b2b%20Google.png", 
    "nihr": "https://raw.githubusercontent.com/Morgan-dar/WeeklyComms/main/Emailbanner%20NIHR.png",
    "puk": "https://raw.githubusercontent.com/Morgan-dar/WeeklyComms/main/Emailbanner%20PUK.png"
}

# ==========================================
# 2. ASK GEMINI FOR THE WORKSPACE SUMMARY
# ==========================================
print("Asking Gemini to summarize the Workspace update...")
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

prompt = f"""
Read this Google Workspace update article: {WORKSPACE_ARTICLE_URL}
Provide a response in this EXACT format with no other text:
Title: [A short, catchy title for the update]
Summary: [A 2-sentence summary explaining why this matters to everyday users]
"""
response = client.models.generate_content(
    model='gemini-2.5-flash',
    contents=prompt
)
response_lines = response.text.strip().split('\n')

ws_title = response_lines[0].replace("Title: ", "").strip()
ws_summary = response_lines[1].replace("Summary: ", "").strip()

# ==========================================
# 3. BUILD THE COURSE MODULES FROM GOOGLE SHEETS
# ==========================================
print("Downloading dates from Google Sheets...")
response = urllib.request.urlopen(CSV_URL)
lines = [l.decode('utf-8') for l in response.readlines()]
reader = csv.reader(lines)
next(reader) # Skip the header row

# DATE FILTER LOGIC: Find the Monday two weeks from now
today = datetime.now()
days_to_target_monday = 14 - today.weekday() # Calculates days until the week after next
target_start_date = today + timedelta(days=days_to_target_monday)
target_start_date = target_start_date.replace(hour=0, minute=0, second=0, microsecond=0)
target_end_date = target_start_date + timedelta(days=6) # Sunday of that week
target_end_date = target_end_date.replace(hour=23, minute=59, second=59)

print(f"Filtering for courses between {target_start_date.strftime('%d/%m/%Y')} and {target_end_date.strftime('%d/%m/%Y')}")

valid_courses = []
seen_courses = set()

# Assuming Columns: Template File, Date, Time, Course URL, Image URL
for row in reader:
    if len(row) < 5 or not row[0].strip():
        continue # Skip empty rows
        
    template_filename = row[0].strip()
    date_str = row[1].strip()
    time_str = row[2].strip()
    course_url = row[3].strip()
    image_url = row[4].strip()

    # Convert date string
    try:
        date_obj = datetime.strptime(date_str, '%d/%m/%Y') 
    except ValueError:
        continue
        
    # Check if the course falls within our target week!
    if not (target_start_date <= date_obj <= target_end_date):
        continue 
        
    # Deduplicate! (If the sheet has the schedule pasted multiple times)
    dedup_key = (template_filename, date_str, time_str)
    if dedup_key in seen_courses:
        continue
    seen_courses.add(dedup_key)
    
    # Open the specific HTML template for this course from GitHub
    try:
        with open(template_filename, 'r', encoding='utf-8') as f:
            course_html = f.read()
    except FileNotFoundError:
        continue

    # Inject the data into the placeholders
    course_html = course_html.replace("{{ day_of_week }}", date_obj.strftime('%A'))
    course_html = course_html.replace("{{ day_number }}", date_obj.strftime('%d').lstrip('0'))
    course_html = course_html.replace("{{ month_name }}", date_obj.strftime('%b'))
    course_html = course_html.replace("{{ course_time }}", time_str)
    course_html = course_html.replace("{{ course_url }}", course_url)
    course_html = course_html.replace("{{ image_url }}", image_url)
    
    # Store it for sorting: Sort by Date, then by Time
    sort_key = (date_obj, time_str[:5]) 
    valid_courses.append((sort_key, course_html))

# SORT THE COURSES CHRONOLOGICALLY
valid_courses.sort(key=lambda x: x[0])

# Build the final string
all_courses_html = ""
for course in valid_courses:
    all_courses_html += course[1] + "\n<br>\n"

# ==========================================
# 4. STITCH TOGETHER & GENERATE CLIENT EMAILS
# ==========================================
print("Building final emails...")
try:
    with open('base_template.html', 'r', encoding='utf-8') as f:
        master_html = f.read()
except FileNotFoundError:
    print("CRITICAL ERROR: 'base_template.html' is missing from your repository!")
    exit(1)

# Inject Gemini updates and featured course
master_html = master_html.replace("{{ workspace_title }}", ws_title)
master_html = master_html.replace("{{ workspace_content }}", ws_summary)
master_html = master_html.replace("{{ workspace_link }}", WORKSPACE_ARTICLE_URL)
master_html = master_html.replace("{{ workspace_course_title }}", FEATURED_COURSE_NAME)
master_html = master_html.replace("{{ workspace_course_link }}", FEATURED_COURSE_URL)
master_html = master_html.replace("{{ course_modules_html }}", all_courses_html)

# Create an output folder
os.makedirs('output', exist_ok=True)

# Generate an email for each client
for client_id, banner_url in CLIENTS.items():
    client_html = master_html.replace("{{ client_id }}", client_id)
    client_html = client_html.replace("{{ banner_image_url }}", banner_url)
    
    output_filename = f"output/newsletter_{client_id}.html"
    with open(output_filename, 'w', encoding='utf-8') as f:
        f.write(client_html)
        
    print(f"✅ Generated: {output_filename}")

print("🎉 All newsletters generated successfully!")
