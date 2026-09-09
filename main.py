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

# 배포 서버가 한국 시간이 아닐 수 있기 때문에
# 반드시 한국 시간(Asia/Seoul)을 기준으로 계산한다.
korea_now = datetime.now(ZoneInfo("Asia/Seoul"))

# 오늘은 아직 집계 전이므로 어제까지만 선택할 수 있다.
yesterday = (korea_now - timedelta(days=1)).date()

# 사용자가 달력에서 조회 날짜를 선택한다.
selected_date = st.date_input(
    "조회할 날짜를 선택하세요.",
    value=yesterday,
    min_value=datetime(2000, 1, 1).date(),
    max_value=yesterday
)

# KOBIS API가 요구하는 YYYYMMDD 형식으로 변환한다.
target_date = selected_date.strftime("%Y%m%d")


# ==================================================
# KOBIS API 호출 함수
# ==================================================

@st.cache_data(ttl=3600)
def get_boxoffice(target_date):
    """
    선택한 날짜의 KOBIS 박스오피스 데이터를 가져온다.

    ttl=3600
    → 같은 날짜의 결과를 1시간 동안 캐시한다.
    → 같은 날짜를 다시 조회해도 API를 계속 호출하지 않는다.
    """

    # ------------------------------------------------
    # Secrets에서 KOBIS 인증키 가져오기
    # ------------------------------------------------

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


    # ------------------------------------------------
    # KOBIS API 주소
    # ------------------------------------------------

    url = (
        "https://www.kobis.or.kr/"
        "kobisopenapi/webservice/rest/"
        "boxoffice/searchDailyBoxOfficeList.json"
    )

    params = {
        "key": kobis_key,
        "targetDt": target_date
    }


    # ------------------------------------------------
    # API 요청
    # ------------------------------------------------

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


    # ------------------------------------------------
    # JSON 응답 읽기
    # ------------------------------------------------

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


    # ------------------------------------------------
    # faultInfo 확인
    # ------------------------------------------------

    # KOBIS는 인증키가 잘못되어도
    # HTTP 상태코드가 200으로 올 수 있다.
    # 따라서 faultInfo가 있는지 반드시 확인한다.

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
                "KOBIS_KEY가 정확한지, "
                "Streamlit Secrets에 올바르게 등록했는지 확인하세요."
            ),
            "data": None
        }


    # ------------------------------------------------
    # boxOfficeResult 확인
    # ------------------------------------------------

    if "boxOfficeResult" not in result:

        return {
            "success": False,
            "message": (
                "박스오피스 결과를 찾을 수 없습니다.\n\n"
                "KOBIS API 응답을 확인하세요."
            ),
            "data": None
        }


    boxoffice_result = result["boxOfficeResult"]


    # ------------------------------------------------
    # 영화 목록 가져오기
    # ------------------------------------------------

    movie_list = boxoffice_result.get(
        "dailyBoxOfficeList",
        []
    )


    # 영화 목록이 비어 있으면
    # 집계 전이라고 안내한다.
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


# ==================================================
# 문자열로 온 숫자를 숫자로 변환
# ==================================================

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


# 순위를 숫자 기준으로 정렬한다.
df = df.sort_values("rank")


# ==================================================
# 조회 날짜 표시
# ==================================================

display_date = selected_date.strftime(
    "%Y년 %m월 %d일"
)

st.subheader(
    f"{display_date} 박스오피스"
)


# ==================================================
# 1위 영화
# ==================================================

first_movie = df.iloc[0]

st.markdown("### 1위 영화")

col1, col2, col3 = st.columns(3)


with col1:

    st.metric(
        label="영화명",
        value=str(first_movie["movieNm"])
    )


with col2:

    st.metric(
        label="관객수",
        value=f"{first_movie['audiCnt']:,}명"
    )


with col3:

    st.metric(
        label="누적관객",
        value=f"{first_movie['audiAcc']:,}명"
    )


# ==================================================
# 전체 순위 표 만들기
# ==================================================

st.markdown("### 전체 순위")


# HTML 표의 행을 저장할 변수
rows = ""


# 영화 목록을 한 줄씩 처리한다.
for _, row in df.iterrows():

    movie_name = str(row["movieNm"])

    rank = int(row["rank"])
    rank_inten = int(row["rankInten"])

    open_date = str(row["openDt"])

    audience = int(row["audiCnt"])
    audience_acc = int(row["audiAcc"])

    screen_count = int(row["scrnCnt"])


    # ------------------------------------------------
    # 100만 관객 이상이면 트로피 표시
    # ------------------------------------------------

    if audience_acc >= 1_000_000:

        movie_name += " 🏆"


    # ------------------------------------------------
    # 순위 증감 표시
    # ------------------------------------------------

    if rank_inten > 0:

        # 양수 = 순위 상승
        rank_change = (
            f'<span style="'
            f'color:#e53935;'
            f'font-weight:bold;'
            f'">'
            f'↑ {rank_inten}'
            f'</span>'
        )

    elif rank_inten < 0:

        # 음수 = 순위 하락
        rank_change = (
            f'<span style="'
            f'color:#1976d2;'
            f'font-weight:bold;'
            f'">'
            f'↓ {abs(rank_inten)}'
            f'</span>'
        )

    else:

        # 변동 없음
        rank_change = "-"


    # ------------------------------------------------
    # HTML 표 한 행 만들기
    # ------------------------------------------------

    rows += f"""
    <tr>
        <td>{rank}</td>
        <td style="text-align:left;">{movie_name}</td>
        <td>{open_date}</td>
        <td>{audience:,}</td>
        <td>{audience_acc:,}</td>
        <td>{screen_count:,}</td>
        <td>{rank_change}</td>
    </tr>
    """


# ==================================================
# HTML 표 출력
# ==================================================

st.markdown(
    f"""
    <style>

    .boxoffice-table {{
        width: 100%;
        border-collapse: collapse;
        text-align: center;
        font-size: 15px;
    }}

    .boxoffice-table th {{
        padding: 12px 8px;
        border-bottom: 2px solid #888;
        font-weight: bold;
    }}

    .boxoffice-table td {{
        padding: 11px 8px;
        border-bottom: 1px solid #ddd;
    }}

    .boxoffice-table tr:hover {{
        background-color: rgba(128, 128, 128, 0.08);
    }}

    </style>

    <table class="boxoffice-table">

        <thead>

            <tr>
                <th>순위</th>
                <th>영화명</th>
                <th>개봉일</th>
                <th>관객수</th>
                <th>누적관객</th>
                <th>스크린수</th>
                <th>전일 대비</th>
            </tr>

        </thead>

        <tbody>

            {rows}

        </tbody>

    </table>
    """,
    unsafe_allow_html=True
)


# ==================================================
# 관객수 상위 5편
# ==================================================

st.markdown("### 관객수 상위 5편")


# 관객수가 많은 순서대로 정렬한 뒤 5편만 가져온다.
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


# 막대그래프 출력
st.bar_chart(
    chart_df,
    y="audiCnt",
    x_label="영화",
    y_label="관객수"
)
