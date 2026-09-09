import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


# ==================================================
# 기본 설정
# ==================================================

st.set_page_config(
    page_title="박스오피스 조회",
    page_icon="🎬",
    layout="wide"
)

st.title("어제의 박스오피스")
st.caption("KOBIS 일일 박스오피스")


# ==================================================
# 한국 시간 기준 날짜 설정
# ==================================================

korea_now = datetime.now(ZoneInfo("Asia/Seoul"))

# 오늘은 선택할 수 없고 어제까지만 선택 가능
yesterday = (korea_now - timedelta(days=1)).date()

selected_date = st.date_input(
    "조회할 날짜를 선택하세요.",
    value=yesterday,
    min_value=datetime(2000, 1, 1).date(),
    max_value=yesterday
)

# KOBIS가 요구하는 날짜 형식으로 변환
target_date = selected_date.strftime("%Y%m%d")


# ==================================================
# KOBIS API 호출
# ==================================================

@st.cache_data(ttl=3600)
def get_boxoffice(target_date):

    # Streamlit Secrets에서 API 키 가져오기
    try:
        kobis_key = st.secrets["KOBIS_KEY"]

    except Exception:
        return {
            "success": False,
            "message": (
                "KOBIS_KEY를 찾을 수 없습니다.\n\n"
                "Streamlit Cloud의 Settings → Secrets에서 "
                "KOBIS_KEY가 등록되어 있는지 확인하세요."
            ),
            "data": None
        }

    url = (
        "https://www.kobis.or.kr/"
        "kobisopenapi/webservice/rest/"
        "boxoffice/searchDailyBoxOfficeList.json"
    )

    params = {
        "key": kobis_key,
        "targetDt": target_date
    }

    # API 요청
    try:
        response = requests.get(
            url,
            params=params,
            timeout=10
        )

        response.raise_for_status()

    except requests.exceptions.Timeout:
        return {
            "success": False,
            "message": (
                "KOBIS API 요청 시간이 초과되었습니다.\n\n"
                "인터넷 연결이나 KOBIS API 서버 상태를 확인하세요."
            ),
            "data": None
        }

    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "message": (
                "KOBIS API 요청에 실패했습니다.\n\n"
                f"오류 내용: {e}"
            ),
            "data": None
        }

    # JSON 응답 읽기
    try:
        result = response.json()

    except ValueError:
        return {
            "success": False,
            "message": (
                "KOBIS API의 응답을 읽을 수 없습니다.\n\n"
                "API 서버의 응답 형식을 확인하세요."
            ),
            "data": None
        }

    # faultInfo 확인
    if "faultInfo" in result:

        fault = result["faultInfo"]

        fault_message = fault.get(
            "message",
            "KOBIS API에서 오류가 발생했습니다."
        )

        return {
            "success": False,
            "message": (
                "KOBIS API에서 오류가 반환되었습니다.\n\n"
                f"{fault_message}\n\n"
                "KOBIS_KEY가 정확한지 확인하세요."
            ),
            "data": None
        }

    # boxOfficeResult 확인
    if "boxOfficeResult" not in result:
        return {
            "success": False,
            "message": (
                "박스오피스 결과를 찾을 수 없습니다.\n\n"
                "KOBIS API 응답을 확인하세요."
            ),
            "data": None
        }

    # 영화 목록 가져오기
    movie_list = result["boxOfficeResult"].get(
        "dailyBoxOfficeList",
        []
    )

    # 영화 목록이 비어 있는 경우
    if not movie_list:
        return {
            "success": False,
            "message": "그날은 아직 집계 전입니다.",
            "data": None
        }

    return {
        "success": True,
        "message": "",
        "data": movie_list
    }


# ==================================================
# 데이터 가져오기
# ==================================================

result = get_boxoffice(target_date)


# ==================================================
# 오류 처리
# ==================================================

if not result["success"]:
    st.warning(result["message"])
    st.stop()


# ==================================================
# 데이터프레임 만들기
# ==================================================

df = pd.DataFrame(result["data"])


# KOBIS에서 문자열로 오는 숫자를 숫자로 변환
numeric_columns = [
    "rank",
    "rankInten",
    "audiCnt",
    "audiAcc",
    "scrnCnt",
    "showCnt"
]

for column in numeric_columns:
    df[column] = pd.to_numeric(
        df[column],
        errors="coerce"
    ).fillna(0).astype(int)


# 순위순으로 정렬
df = df.sort_values("rank")


# ==================================================
# 날짜 표시
# ==================================================

display_date = selected_date.strftime(
    "%Y년 %m월 %d일"
)

st.subheader(f"{display_date} 박스오피스")


# ==================================================
# 1위 영화
# ==================================================

first_movie = df.iloc[0]

st.markdown("### 1위 영화")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        "영화명",
        str(first_movie["movieNm"])
    )

with col2:
    st.metric(
        "관객수",
        f"{first_movie['audiCnt']:,}명"
    )

with col3:
    st.metric(
        "누적관객",
        f"{first_movie['audiAcc']:,}명"
    )


# ==================================================
# 전체 순위 표
# ==================================================

st.markdown("### 전체 순위")


# HTML 표의 행을 저장
rows = ""

for _, row in df.iterrows():

    movie_name = str(row["movieNm"])

    rank = int(row["rank"])
    rank_inten = int(row["rankInten"])
    audience = int(row["audiCnt"])
    audience_acc = int(row["audiAcc"])
    screen_count = int(row["scrnCnt"])

    open_date = str(row["openDt"])


    # ----------------------------------------------
    # 누적관객 100만 이상이면 트로피 표시
    # ----------------------------------------------

    if audience_acc >= 1_000_000:
        movie_name += " 🏆"


    # ----------------------------------------------
    # 순위 증감 표시
    # ----------------------------------------------

    if rank_inten > 0:

        # 양수 = 순위 상승 → 빨간색
        rank_change = (
            '<span style="color:#e53935; '
            'font-weight:bold;">'
            f'↑ {rank_inten}'
            '</span>'
        )

    elif rank_inten < 0:

        # 음수 = 순위 하락 → 파란색
        rank_change = (
            '<span style="color:#1976d2; '
            'font-weight:bold;">'
            f'↓ {abs(rank_inten)}'
            '</span>'
        )

    else:

        rank_change = "-"


    # ----------------------------------------------
    # 표의 한 행 만들기
    # ----------------------------------------------

    rows += (
        "<tr>"
        f"<td>{rank}</td>"
        f'<td style="text-align:left;">{movie_name}</td>'
        f"<td>{open_date}</td>"
        f"<td>{audience:,}</td>"
        f"<td>{audience_acc:,}</td>"
        f"<td>{screen_count:,}</td>"
        f"<td>{rank_change}</td>"
        "</tr>"
    )


# ==================================================
# HTML 표 출력
# ==================================================

html_table = (
    '<style>'
    '.boxoffice-table {'
    'width: 100%;'
    'border-collapse: collapse;'
    'text-align: center;'
    'font-size: 15px;'
    '}'

    '.boxoffice-table th {'
    'padding: 12px 8px;'
    'border-bottom: 2px solid #888;'
    'font-weight: bold;'
    '}'

    '.boxoffice-table td {'
    'padding: 11px 8px;'
    'border-bottom: 1px solid #ddd;'
    '}'

    '.boxoffice-table tr:hover {'
    'background-color: rgba(128, 128, 128, 0.08);'
    '}'
    '</style>'

    '<table class="boxoffice-table">'

    '<thead>'
    '<tr>'
    '<th>순위</th>'
    '<th>영화명</th>'
    '<th>개봉일</th>'
    '<th>관객수</th>'
    '<th>누적관객</th>'
    '<th>스크린수</th>'
    '<th>전일 대비</th>'
    '</tr>'
    '</thead>'

    '<tbody>'
    + rows +
    '</tbody>'

    '</table>'
)


# HTML을 그대로 렌더링
st.markdown(
    html_table,
    unsafe_allow_html=True
)


# ==================================================
# 관객수 상위 5편 그래프
# ==================================================

st.markdown("### 관객수 상위 5편")


# 관객수가 많은 순서대로 5편 선택
top5 = (
    df
    .sort_values(
        "audiCnt",
        ascending=False
    )
    .head(5)
    .copy()
)


# 그래프용 데이터
chart_df = top5[
    ["movieNm", "audiCnt"]
].set_index("movieNm")


# 막대그래프
st.bar_chart(
    chart_df,
    y="audiCnt",
    x_label="영화",
    y_label="관객수"
)
