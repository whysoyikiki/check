import streamlit as st
import pandas as pd
import re
from datetime import datetime, timedelta
from io import BytesIO

st.set_page_config(page_title="카카오톡 출퇴근 분석", layout="wide")

st.title("📊 카카오톡 출퇴근 기록 분석")

uploaded_file = st.file_uploader("📁 카카오톡 TXT 파일 업로드", type=["txt"])
start_monday = st.text_input("📅 시작 날짜 (월요일, yyyymmdd)", placeholder="20251006")

DAILY_STANDARD_MIN = 9 * 60

date_pattern = re.compile(
    r"-{5,}\s(\d{4})년\s(\d{1,2})월\s(\d{1,2})일\s([월화수목금토일])요일"
)

msg_pattern = re.compile(
    r"^\[(?P<name>[^\]]+)\]\s+\[(?P<ampm>오전|오후)\s(?P<hour>\d{1,2}):(?P<minute>\d{2})\]"
)

def format_diff(minutes):
    sign = "+" if minutes >= 0 else "-"
    minutes = abs(minutes)
    return f"{sign}{minutes//60}시간 {minutes%60}분"

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
            current_date = datetime(
                int(d.group(1)), int(d.group(2)), int(d.group(3))
            ).date()
            current_weekday = d.group(4)
            continue

        if not current_date:
            continue
        if not (start_date <= current_date <= end_date):
            continue
        if current_weekday not in ["월", "화", "수", "목", "금"]:
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
            "시간": datetime.combine(current_date, datetime.min.time()) +
                    timedelta(hours=hour, minutes=minute)
        })

    df = pd.DataFrame(records)

    if df.empty:
        st.warning("데이터를 찾을 수 없습니다.")
        st.stop()

    names = sorted(df["이름"].unique())
    target_name = st.selectbox("👤 분석 대상자 선택", names)

    df = df[df["이름"] == target_name]

    rows = []
    week_start = None
    week_worked = 0
    week_days = 0

    # 주간 단위 기록
    weekly_data = {}

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
                "주간합계": format_diff(week_worked - week_days * DAILY_STANDARD_MIN)
            })
            week_worked = 0
            week_days = 0

        if len(g) >= 2:
            start = g.iloc[0]["시간"]
            end = g.iloc[-1]["시간"]
            worked = int((end - start).total_seconds() // 60)

            rows.append({
                "이름": target_name,
                "날짜": date.strftime("%Y-%m-%d"),
                "요일": g.iloc[0]["요일"],
                "출근": start.strftime("%H:%M"),
                "퇴근": end.strftime("%H:%M"),
                "시간": format_diff(worked - DAILY_STANDARD_MIN),
                "주간합계": ""
            })

            week_worked += worked
            week_days += 1

            # 요약표용
            weekly_data.setdefault(current_week_start, {})[g.iloc[0]["요일"]] = worked
        else:
            only_time = g.iloc[0]["시간"]
            rows.append({
                "이름": target_name,
                "날짜": date.strftime("%Y-%m-%d"),
                "요일": g.iloc[0]["요일"],
                "출근": only_time.strftime("%H:%M"),
                "퇴근": "",
                "시간": "퇴근 기록 없음",
                "주간합계": ""
            })
            # 요약표용: 기록 없음
            weekly_data.setdefault(current_week_start, {})[g.iloc[0]["요일"]] = None

        week_start = current_week_start

    if week_days > 0:
        rows.append({
            "이름": "주간합계",
            "날짜": "",
            "요일": "",
            "출근": "",
            "퇴근": "",
            "시간": "",
            "주간합계": format_diff(week_worked - week_days * DAILY_STANDARD_MIN)
        })

    result_df = pd.DataFrame(rows)

    st.subheader("📋 분석 결과")
    st.dataframe(result_df, use_container_width=True)

    buffer = BytesIO()
    result_df.to_excel(buffer, index=False)
    st.download_button(
        "⬇ 엑셀 다운로드",
        data=buffer.getvalue(),
        file_name="출퇴근_기록.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    # ------------------------
    # 간략 요약표
    # ------------------------
    st.subheader("🟢🔴 간략 주간 요약표")
    summary_rows = []

    for week_start, days in sorted(weekly_data.items()):
        row = {}
        total_week_minutes = 0
        for d in ["월", "화", "수", "목", "금"]:
            worked = days.get(d)
            if worked is None:
                row[d] = ""
            else:
                row[d] = worked
                total_week_minutes += worked
        row["주간합계"] = total_week_minutes
        summary_rows.append((week_start, row))

    if summary_rows:
        summary_df = pd.DataFrame([r[1] for r in summary_rows])
        summary_df.index = [r[0].strftime("%Y-%m-%d") for r in summary_rows]

        def color_cells(val):
            if val == "":
                return "background-color:white"
            elif val >= DAILY_STANDARD_MIN:
                return "background-color:lightgreen"
            else:
                return "background-color:salmon"

        st.dataframe(summary_df.style.applymap(color_cells), use_container_width=True)
