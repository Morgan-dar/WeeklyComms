import os
import csv
import urllib.request
from google import genai
from datetime import datetime, timedelta

# ==========================================
# 1. WEEKLY CONTROL PANEL (Update these each week!)
# ==========================================
CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSKKcq07WVCePpVsrX-1pNn5PBiDHZoV3Svl0EHIEelISNHJCnvndvUrlxaa4SZRm1y7YnbIiWkUgaj/pub?output=csv" 

# --- A. WORKSPACE UPDATE ---
WORKSPACE_ARTICLE_URL = "https://workspaceupdates.googleblog.com/2026/03/introducing-guest-accounts.html"
WORKSPACE_COURSE_NAME = "Chat Smarter, Work Better"
WORKSPACE_COURSE_URL = "https://training.ceyx.app/{{ client_id }}/learn/courses/12/chat-smarter-work-better-mastering-google-chat-for-effective-communication"

# --- B. NEW & TRENDING: MAIN COURSE ---
TRENDING_MAIN_NAME = "Getting Started with Google Workspace - Communication Tools"
TRENDING_MAIN_URL = "https://training.ceyx.app/{{ client_id }}/learn/courses/3/getting-started-with-google-workspace-communication-tools"

# --- C. NEW & TRENDING: SECONDARY COURSE 1 ---
TRENDING_SUB1_NAME = "Power up your Presentations 1: Designing with Google Slides"
TRENDING_SUB1_DATETIME = "Wed 15th Apr @ 14:00"
TRENDING_SUB1_URL = "https://training.ceyx.app/{{ client_id }}/learn/courses/11/presenting-with-google-slides"

# --- D. NEW & TRENDING: SECONDARY COURSE 2 ---
TRENDING_SUB2_NAME = "Bringing Gemini into Your Daily Work"
TRENDING_SUB2_DATETIME = "Fri 17th Apr @ 11:00"
TRENDING_SUB2_URL = "https://training.ceyx.app/{{ client_id }}/learn/courses/131/bringing-gemini-into-your-daily-work/"

# --- E. CLIENT BANNERS ---
CLIENTS = {
    "livelearningco": "https://github.com/Morgan-dar/WeeklyComms/blob/main/Emailbanner_b2b_Google.png?raw=true",
    "b2b": "https://github.com/Morgan-dar/WeeklyComms/blob/main/Emailbanner_b2b_Google.png?raw=true", 
    "nihr": "https://github.com/Morgan-dar/WeeklyComms/blob/main/Emailbanner_NIHR.png?raw=true",
    "puk": "https://github.com/Morgan-dar/WeeklyComms/blob/main/Emailbanner_PUK.png?raw=true"
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
days_to_target_monday = 14 - today.weekday() 
target_start_date = today + timedelta(days=days_to_target_monday)
target_start_date = target_start_date.replace(hour=0, minute=0, second=0, microsecond=0)
target_end_date = target_start_date + timedelta(days=6) 
target_end_date = target_end_date.replace(hour=23, minute=59, second=59)

print(f"Filtering for courses between {target_start_date.strftime('%d/%m/%Y')} and {target_end_date.strftime('%d/%m/%Y')}")

valid_courses = []
seen_courses = set()

for row in reader:
    if len(row) < 5 or not row[0].strip():
        continue 
        
    template_filename = row[0].strip()
    date_str = row[1].strip()
    time_str = row[2].strip()
    course_url = row[3].strip()
    image_url = row[4].strip()

    # CRITICAL URL FIX
    course_url = course_url.replace("/livelearningco/", "/{{ client_id }}/")

    try:
        date_obj = datetime.strptime(date_str, '%d/%m/%Y') 
    except ValueError:
        continue
        
    if not (target_start_date <= date_obj <= target_end_date):
        continue 
        
    # AGGRESSIVE DEDUPLICATION
    clean_time = time_str.strip()[:5] 
    dedup_key = (template_filename, date_obj, clean_time)
    if dedup_key in seen_courses:
        continue
    seen_courses.add(dedup_key)
    
    try:
        with open(template_filename, 'r', encoding='utf-8') as f:
            course_html = f.read()
    except FileNotFoundError:
        continue

    course_html = course_html.replace("{{ day_of_week }}", date_obj.strftime('%A'))
    course_html = course_html.replace("{{ day_number }}", date_obj.strftime('%d').lstrip('0'))
    course_html = course_html.replace("{{ month_name }}", date_obj.strftime('%b'))
    course_html = course_html.replace("{{ course_time }}", time_str)
    course_html = course_html.replace("{{ course_url }}", course_url)
    course_html = course_html.replace("{{ image_url }}", image_url)
    
    sort_key = (date_obj, clean_time) 
    valid_courses.append((sort_key, course_html))

# SORT CHRONOLOGICALLY
valid_courses.sort(key=lambda x: x[0])

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

# Inject Gemini updates
master_html = master_html.replace("{{ workspace_title }}", ws_title)
master_html = master_html.replace("{{ workspace_content }}", ws_summary)
master_html = master_html.replace("{{ workspace_link }}", WORKSPACE_ARTICLE_URL)
master_html = master_html.replace("{{ workspace_course_title }}", WORKSPACE_COURSE_NAME)
master_html = master_html.replace("{{ workspace_course_link }}", WORKSPACE_COURSE_URL)

# Inject New & Trending updates
master_html = master_html.replace("{{ trending_main_title }}", TRENDING_MAIN_NAME)
master_html = master_html.replace("{{ trending_main_link }}", TRENDING_MAIN_URL)
master_html = master_html.replace("{{ trending_sub1_title }}", TRENDING_SUB1_NAME)
master_html = master_html.replace("{{ trending_sub1_datetime }}", TRENDING_SUB1_DATETIME)
master_html = master_html.replace("{{ trending_sub1_link }}", TRENDING_SUB1_URL)
master_html = master_html.replace("{{ trending_sub2_title }}", TRENDING_SUB2_NAME)
master_html = master_html.replace("{{ trending_sub2_datetime }}", TRENDING_SUB2_DATETIME)
master_html = master_html.replace("{{ trending_sub2_link }}", TRENDING_SUB2_URL)

# Inject the full calendar
master_html = master_html.replace("{{ course_modules_html }}", all_courses_html)

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
