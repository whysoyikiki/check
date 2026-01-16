import streamlit as st
import pandas as pd
import re
from datetime import datetime, timedelta
from io import BytesIO

st.set_page_config(page_title="카카오톡 출퇴근 분석", layout="wide")
st.title("📊 카카오톡 출퇴근 기록 분석")

uploaded_file = st.file_uploader("📁 카카오톡 TXT 파일 업로드", type=["txt"])
start_monday = st.text_input("📅 시작 날짜 (월요일, yyyymmdd)", placeholder="20251006")

BASE_STANDARD_MIN = 9 * 60

# ------------------------
# 정규식
# ------------------------
date_pattern = re.compile(
    r"-{5,}\s(\d{4})년\s(\d{1,2})월\s(\d{1,2})일\s([월화수목금토일])요일"
)

msg_pattern = re.compile(
    r"^\[(?P<name>[^\]]+)\]\s+\[(?P<ampm>오전|오후)\s(?P<hour>\d{1,2}):(?P<minute>\d{2})\]"
)

# ------------------------
# 함수
# ------------------------
def format_diff(minutes):
    sign = "+" if minutes >= 0 else "-"
    minutes = abs(minutes)
    return f"{sign}{minutes//60}시간 {minutes%60}분"

def get_daily_standard(text):
    if "반반차" in text:
        return 7 * 60
    elif "반차" in text:
        return 4 * 60
    return BASE_STANDARD_MIN

def get_suffix(text):
    if "반반차" in text:
        return " (반반차)"
    elif "반차" in text:
        return " (반차)"
    return ""

# ------------------------
# 데이터 로딩
# ------------------------
if uploaded_file and start_monday:
    try:
        start_date = datetime.strptime(start_monday, "%Y%m%d").date()
        end_date = datetime.now().date()
    except:
        st.error("❌ 날짜 형식이 잘못되었습니다 (yyyymmdd)")
        st.stop()

    lines = uploaded_file.read().decode("utf-8").splitlines()
    records = []
    current_date, current_weekday = None, None

    for line in lines:
        line = line.strip()

        d = date_pattern.match(line)
        if d:
            current_date = datetime(int(d.group(1)), int(d.group(2)), int(d.group(3))).date()
            current_weekday = d.group(4)
            continue

        if not current_date:
            continue
        if not (start_date <= current_date <= end_date):
            continue
        if current_weekday not in ["월","화","수","목","금"]:
            continue

        m = msg_pattern.match(line)
        if not m:
            continue

        hour = int(m.group("hour"))
        minute = int(m.group("minute"))
        if m.group("ampm") == "오후" and hour != 12:
            hour += 12
        if m.group("ampm") == "오전" and hour == 12:
            hour = 0

        records.append({
            "이름": m.group("name"),
            "날짜": current_date,
            "요일": current_weekday,
            "시간": datetime.combine(current_date, datetime.min.time()) + timedelta(hours=hour, minutes=minute),
            "일일기준분": get_daily_standard(line),
            "원문": line
        })

    df = pd.DataFrame(records)
    if df.empty:
        st.warning("데이터를 찾을 수 없습니다.")
        st.stop()

    target_name = st.selectbox("👤 분석 대상자 선택", sorted(df["이름"].unique()))
    df = df[df["이름"] == target_name]

    # ------------------------
    # 상세 분석표
    # ------------------------
    rows = []
    weekly_data = {}
    week_worked, week_standard = 0, 0
    week_start = None

    for date, g in df.groupby("날짜"):
        g = g.sort_values("시간")
        current_week_start = date - timedelta(days=date.weekday())

        if week_start and current_week_start != week_start:
            rows.append({
                "이름": "주간합계",
                "날짜": "",
                "요일": "",
                "출근": "",
                "퇴근": "",
                "시간": "",
                "주간합계": format_diff(week_worked - week_standard)
            })
            week_worked, week_standard = 0, 0

        daily_standard = g.iloc[0]["일일기준분"]
        suffix = get_suffix(g.iloc[0]["원문"])

        if len(g) >= 2:
            start, end = g.iloc[0]["시간"], g.iloc[-1]["시간"]
            worked = int((end - start).total_seconds() // 60)

            rows.append({
                "이름": target_name,
                "날짜": date.strftime("%Y-%m-%d"),
                "요일": g.iloc[0]["요일"],
                "출근": start.strftime("%H:%M"),
                "퇴근": end.strftime("%H:%M"),
                "시간": format_diff(worked - daily_standard) + suffix,
                "주간합계": ""
            })

            week_worked += worked
            week_standard += daily_standard
            weekly_data.setdefault(current_week_start, {})[g.iloc[0]["요일"]] = g

        else:
            rows.append({
                "이름": target_name,
                "날짜": date.strftime("%Y-%m-%d"),
                "요일": g.iloc[0]["요일"],
                "출근": g.iloc[0]["시간"].strftime("%H:%M"),
                "퇴근": "",
                "시간": "퇴근 기록 없음",
                "주간합계": ""
            })
            weekly_data.setdefault(current_week_start, {})[g.iloc[0]["요일"]] = g

        week_start = current_week_start

    rows.append({
        "이름": "주간합계",
        "날짜": "",
        "요일": "",
        "출근": "",
        "퇴근": "",
        "시간": "",
        "주간합계": format_diff(week_worked - week_standard)
    })

    result_df = pd.DataFrame(rows)
    st.subheader("📋 분석 결과")
    st.dataframe(result_df, use_container_width=True)

    buffer = BytesIO()
    result_df.to_excel(buffer, index=False)
    st.download_button(
        "⬇ 엑셀 다운로드",
        data=buffer.getvalue(),
        file_name="출퇴근_기록.xlsx"
    )

# ------------------------
# 간략 주간 요약표
# ------------------------
st.subheader("🟢🔴 간략 주간 요약표")

summary_rows = []
for week_start, days in sorted(weekly_data.items()):
    row = {}
    total_worked, total_standard = 0, 0

    for d in ["월","화","수","목","금"]:
        g = days.get(d)
        if g is None or g.empty:
            row[d] = ""
            continue

        suffix = get_suffix(g.iloc[0]["원문"])
        standard = g.iloc[0]["일일기준분"]

        if len(g) < 2:
            row[d] = "기록 부족"
            continue

        worked = int((g.iloc[-1]["시간"] - g.iloc[0]["시간"]).total_seconds() // 60)
        diff = worked - standard
        row[d] = format_diff(diff) + suffix

        total_worked += worked
        total_standard += standard

    row["주간합계"] = format_diff(total_worked - total_standard)
    summary_rows.append((week_start, row))

summary_df = pd.DataFrame([r[1] for r in summary_rows])
summary_df.index = [r[0].strftime("%Y-%m-%d") for r in summary_rows]

def color_cells(val):
    if val == "":
        return "background-color:white; text-align:center"
    if "기록 부족" in str(val):
        return "background-color:khaki; text-align:center"
    if val.startswith("+"):
        return "background-color:lightgreen; text-align:center"
    return "background-color:salmon; text-align:center"

st.dataframe(summary_df.style.applymap(color_cells), use_container_width=True)
