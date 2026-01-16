import re
import pandas as pd
from datetime import datetime, timedelta
from collections import defaultdict
from IPython.display import display, HTML

# =========================
# 1. 카카오톡 로그 경로
# =========================
FILE_PATH = "/content/kakao.txt"

with open(FILE_PATH, encoding="utf-8") as f:
    lines = f.readlines()

# =========================
# 2. 패턴 정의
# =========================
LOG_PATTERN = re.compile(
    r"\[(.*?)\] \[(오전|오후) (\d{1,2}):(\d{2})\] (.*)"
)

DATE_PATTERN = re.compile(r"\d{4}년 \d{1,2}월 \d{1,2}일")

# =========================
# 3. 실행 주차 (월~금)
# =========================
today = datetime.now().date()
monday = today - timedelta(days=today.weekday())
friday = monday + timedelta(days=4)

# =========================
# 4. 날짜별 데이터 수집
# =========================
data = defaultdict(lambda: defaultdict(lambda: {
    "in": None,
    "out": None,
    "texts": []
}))

for line in lines:
    m = LOG_PATTERN.search(line)
    d = DATE_PATTERN.search(line)
    if not m or not d:
        continue

    name, ap, hh, mm, text = m.groups()
    date = datetime.strptime(d.group(), "%Y년 %m월 %d일").date()

    if not (monday <= date <= friday):
        continue

    hh, mm = int(hh), int(mm)
    time = hh * 60 + mm
    if ap == "오후" and hh != 12:
        time += 12 * 60
    if ap == "오전" and hh == 12:
        time = mm

    # 메시지 내용 누적
    data[name][date]["texts"].append(text)

    if "출근" in text:
        data[name][date]["in"] = time
    if "퇴근" in text:
        data[name][date]["out"] = time

# =========================
# 5. 반차/반반차 판별
# =========================
def detect_half(texts):
    joined = " ".join(texts)
    if re.search(r"반\s*반\s*차", joined):
        return 7 * 60, " (반반차)"
    if re.search(r"반\s*차", joined):
        return 4 * 60, " (반차)"
    return 9 * 60, ""

# =========================
# 6. 표 데이터 생성
# =========================
detail_rows = []
summary_rows = []

for name, days in data.items():
    weekly_sum = 0

    for d in sorted(days):
        info = days[d]
        standard, suffix = detect_half(info["texts"])

        cin, cout = info["in"], info["out"]

        if cin is not None and cout is not None:
            worked = cout - cin
            diff = worked - standard
            weekly_sum += diff

            detail_rows.append([
                name,
                d.strftime("%Y-%m-%d"),
                f"{cin//60:02d}:{cin%60:02d}",
                f"{cout//60:02d}:{cout%60:02d}",
                f"{diff//60:+d}시간 {abs(diff)%60:02d}분{suffix}",
                ""
            ])
        else:
            # 출근만 or 퇴근만
            state = "출근만" if cin and not cout else "퇴근만"
            detail_rows.append([
                name,
                d.strftime("%Y-%m-%d"),
                "" if cin is None else f"{cin//60:02d}:{cin%60:02d}",
                "" if cout is None else f"{cout//60:02d}:{cout%60:02d}",
                f"기록 누락{suffix}",
                "partial"
            ])

    detail_rows.append([
        name,
        "주간합계",
        "",
        "",
        f"{weekly_sum//60:+d}시간 {abs(weekly_sum)%60:02d}분",
        "weekly"
    ])

df = pd.DataFrame(
    detail_rows,
    columns=["이름", "날짜", "출근", "퇴근", "근무차이", "class"]
)

# =========================
# 7. HTML 출력
# =========================
html = """
<style>
table { border-collapse: collapse; width:100%; }
th, td { border:1px solid #ccc; padding:6px; text-align:center; }
.partial { background:#fff3cd; }
.weekly { background:#f0f0f0; font-weight:bold; }
</style>

<h3>📊 전체 상세 분석 결과</h3>
<table>
<tr><th>이름</th><th>날짜</th><th>출근</th><th>퇴근</th><th>근무차이</th></tr>
"""

for _, r in df.iterrows():
    html += f"<tr class='{r['class']}'><td>{r['이름']}</td><td>{r['날짜']}</td><td>{r['출근']}</td><td>{r['퇴근']}</td><td>{r['근무차이']}</td></tr>"

html += "</table>"

display(HTML(html))
