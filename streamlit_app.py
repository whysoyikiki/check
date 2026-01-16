import streamlit as st
import pandas as pd
import re
from datetime import datetime, timedelta
from io import BytesIO
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode

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

# ------------------------
# 1. 데이터 처리
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
            current_date = datetime(
                int(d.group(1)), int(d.group(2)), int(d.group(3))
            ).date()
            current_weekday = d.group(4)
            continue

        if not current_date or not (start_date <= current_date <= end_date):
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

    # ------------------------
    # 2. 대상자 선택
    # ------------------------
    names = sorted(df["이름"].unique())
    target_name = st.selectbox("👤 분석 대상자 선택", names)
    df = df[df["이름"] == target_name]

    # ------------------------
    # 3. 상세 분석 데이터 생성
    # ------------------------
    rows = []
    week_start = None
    week_worked = 0
    week_days = 0
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

    # ------------------------
    # 4. 전체 상세 결과 표시
    # ------------------------
    st.subheader("📋 전체 상세 분석 결과")
    
    # 클릭한 주간을 기억할 변수
    if "selected_week" not in st.session_state:
        st.session_state.selected_week = None

    # ------------------------
    # 5. 간략 주간 요약표 생성
    # ------------------------
    summary_rows = []
    for week_start, days in sorted(weekly_data.items()):
        row = {}
        total_week_minutes = 0
        for d in ["월", "화", "수", "목", "금"]:
            worked = days.get(d)
            if worked is None:
                row[d] = ""
            else:
                minutes_diff = worked - DAILY_STANDARD_MIN
                sign = "+" if minutes_diff >= 0 else "-"
                minutes_abs = abs(minutes_diff)
                row[d] = f"{sign}{minutes_abs//60}시간 {minutes_abs%60}분"
                total_week_minutes += worked
        total_diff = total_week_minutes - DAILY_STANDARD_MIN * len([v for v in days.values() if v is not None])
        sign = "+" if total_diff >= 0 else "-"
        total_diff_abs = abs(total_diff)
        row["주간합계"] = f"{sign}{total_diff_abs//60}시간 {total_diff_abs%60}분"
        summary_rows.append((week_start, row))

    # summary_df 생성
    summary_df = pd.DataFrame([r[1] for r in summary_rows])
    summary_df.index = [r[0].strftime("%Y-%m-%d") for r in summary_rows]

    # ------------------------
    # 6. AgGrid로 요약표 표시 (셀 클릭 이벤트)
    # ------------------------
    gb = GridOptionsBuilder.from_dataframe(summary_df)
    gb.configure_default_column(cellStyle={'textAlign': 'center'})  # 글자 가운데 정렬
    gb.configure_selection("single")  # 단일 선택
    gb.configure_grid_options(domLayout='normal')
    grid_options = gb.build()

    st.subheader("🟢🔴 간략 주간 요약표 (클릭 시 해당 주간합계 강조)")
    grid_response = AgGrid(
        summary_df,
        gridOptions=grid_options,
        update_mode=GridUpdateMode.SELECTION_CHANGED,
        height=250,
        fit_columns_on_grid_load=True,
    )

    # 선택된 주간 처리
    if grid_response['selected_rows']:
        selected_index = grid_response['selected_rows'][0]['index']
        st.session_state.selected_week = selected_index
    else:
        st.session_state.selected_week = None

    # ------------------------
    # 7. 전체 상세 분석 결과에서 선택된 주간합계 강조
    # ------------------------
    def highlight_weekly(row):
        if st.session_state.selected_week and row["이름"] == "주간합계":
            # 해당 주간합계 행 날짜 기준 체크
            week_str = st.session_state.selected_week
            week_start_date = datetime.strptime(week_str, "%Y-%m-%d").date()
            week_end_date = week_start_date + timedelta(days=4)
            # 상세 행 중 주간합계 위치 체크
            if row.name >= 0:  # 모든 행 대상
                return ['background-color:yellow']*len(row)
        return ['']*len(row)

    st.dataframe(result_df.style.apply(highlight_weekly, axis=1), use_container_width=True)

    # ------------------------
    # 8. 엑셀 다운로드
    # ------------------------
    buffer = BytesIO()
    result_df.to_excel(buffer, index=False)
    st.download_button(
        "⬇ 엑셀 다운로드",
        data=buffer.getvalue(),
        file_name="출퇴근_기록.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
