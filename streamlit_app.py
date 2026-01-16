import re
import pandas as pd
from datetime import datetime, timedelta
from collections import defaultdict
from IPython.display import display, HTML

# =========================
# 1. 카카오톡 로그 불러오기
# =========================
FILE_PATH = "/content/kakao.txt"  # ⬅ 카카오톡 txt 경로

with open(FILE_PATH, encoding="utf-8") as f:
    lines = f.readlines()

# =========================
# 2. 날짜 패턴
# =========================
LOG_PATTERN = re.compile(
    r"\[(.*?)\] \[(오전|오후) (\d{1,2}):(\d{2})\] (.*)"
)

# =========================
# 3. 반차 / 반반차 판별 함수
# =========================
def get_daily_standard(text):
    if re.search(r"반\s*반\s*차", text):
        return 7 * 60
    elif re.search(r"반\s*차", text):
        return 4 * 60
    return 9 * 60

def get_suffix(text):
    if re.search(r"반\s*반\s*차", text):
        return " (반반차)"
    elif re.search(r"반\s*차", text):
        return " (반차)"
    return ""

# =========================
# 4. 실행 주차 (월~금)
# =========================
today = datetime.now().date()
monday = today - timedelta(days=today.weekday())
friday = monday + timedelta(days=4)

# =========================
# 5. 로그 파싱
# =========================
records = defaultdict(lambda: defaultdict(dict))

for line in lines:
    m = LOG_PATTERN.search(line)
    if not m:
        continue

    name, ap, hh, mm, text = m.groups()
    time = int(hh) * 60 + int(mm)
    if ap == "오후" and hh != "12":
        time += 12 * 60
    if ap == "오전" and hh == "12":
        time = int(mm)

    date_match = re.search(r"\d{4}년 \d{1,2}월 \d{1,2}일", line)
    if not date_match:
        continue

    date = datetime.strptime(date_match.group(), "%Y년 %m월 %d일").date()
    if not (monday <= date <= friday):
        continue

    if "출근" in text:
        records[name][date]["in"] = time
        records[name][date]["text"] = text
    elif "퇴근" in text:
        records[name][date]["out"] = time
        records[name][date]["text"] = text

# =========================
# 6. 상세 분석표 생성
# =========================
detail_rows = []
summary_rows = []

for name, days in records.items():
    weekly_total = 0

    for d in sorted(days):
        info = days[d]
        standard = get_daily_standard(info.get("text", ""))
        suffix = get_suffix(info.get("text", ""))

        if "in" in info and "out" in info:
            worked = info["out"] - info["in"]
            diff = worked - standard
            weekly_total += diff

            detail_rows.append([
                name, d.strftime("%Y-%m-%d"),
                f"{info['in']//60:02d}:{info['in']%60:02d}",
                f"{info['out']//60:02d}:{info['out']%60:02d}",
                f"{diff//60:+d}시간 {abs(diff)%60:02d}분{suffix}"
            ])
        else:
            summary_rows.append((name, d, "partial"))

    detail_rows.append([
        name, "주간합계", "", "",
        f"{weekly_total//60:+d}시간 {abs(weekly_total)%60:02d}분"
    ])

# =========================
# 7. DataFrame
# =========================
detail_df = pd.DataFrame(
    detail_rows,
    columns=["이름", "날짜", "출근", "퇴근", "근무차이"]
)

# =========================
# 8. HTML 렌더링
# =========================
html = """
<style>
table { border-collapse: collapse; width:100%; }
th, td { border:1px solid #ccc; padding:6px; text-align:center; }
.partial { background-color:#fff3cd; }
.highlight { background-color:yellow; }
</style>

<h3>📊 전체 상세 분석 결과</h3>
<table id="detail">
<tr><th>이름</th><th>날짜</th><th>출근</th><th>퇴근</th><th>근무차이</th></tr>
"""

for _, r in detail_df.iterrows():
    cls = "weekly" if r["날짜"] == "주간합계" else ""
    html += f"<tr class='{cls}'><td>{r['이름']}</td><td>{r['날짜']}</td><td>{r['출근']}</td><td>{r['퇴근']}</td><td>{r['근무차이']}</td></tr>"

html += "</table>"

html += """
<h3>🗓 간략 주간 요약표</h3>
<table>
<tr><th>이름</th><th>날짜</th><th>상태</th></tr>
"""

for name, d, _ in summary_rows:
    html += f"<tr class='partial'><td>{name}</td><td>{d.strftime('%Y-%m-%d')}</td><td>출근/퇴근 누락</td></tr>"

html += "</table>"

display(HTML(html))
