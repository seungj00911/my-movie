import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


# --------------------------------------------------
# 기본 설정
# --------------------------------------------------

st.set_page_config(
    page_title="어제의 박스오피스",
    page_icon="🎬",
    layout="wide"
)

st.title("어제의 박스오피스")
st.caption("KOBIS 일일 박스오피스 · 한국 시간 기준")


# --------------------------------------------------
# 어제 날짜 계산
# --------------------------------------------------

def get_yesterday():
    """
    서버의 시간대가 한국이 아닐 수 있으므로
    한국 시간(Asia/Seoul)을 기준으로 어제 날짜를 계산한다.
    """
    korea_now = datetime.now(ZoneInfo("Asia/Seoul"))
    yesterday = korea_now - timedelta(days=1)

    # API에서 요구하는 날짜 형식: YYYYMMDD
    return yesterday.strftime("%Y%m%d")


# --------------------------------------------------
# KOBIS API 호출
# --------------------------------------------------

@st.cache_data(ttl=3600)
def get_boxoffice(target_date):
    """
    KOBIS API에서 해당 날짜의 박스오피스 정보를 가져온다.

    cache_data를 사용했기 때문에
    같은 날짜를 다시 조회하면 약 1시간 동안
    API를 다시 호출하지 않는다.
    """

    # 인증키는 Streamlit Secrets에서 가져온다.
    try:
        kobis_key = st.secrets["KOBIS_KEY"]
    except Exception:
        return {
            "success": False,
            "message": (
                "KOBIS_KEY를 찾을 수 없습니다.\n\n"
                "Streamlit Cloud의 앱 설정에서 Secrets에 "
                "KOBIS_KEY를 등록했는지 확인하세요."
            ),
            "data": None
        }

    url = (
        "https://www.kobis.or.kr/kobisopenapi/webservice/rest/"
        "boxoffice/searchDailyBoxOfficeList.json"
    )

    params = {
        "key": kobis_key,
        "targetDt": target_date
    }

    # API 요청 중 문제가 생기는 경우를 대비한다.
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

    # JSON으로 변환한다.
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

    # ----------------------------------------------
    # 인증키가 틀린 경우에도 HTTP 상태코드는 200일 수 있다.
    # 따라서 faultInfo가 있는지 반드시 확인한다.
    # ----------------------------------------------
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
                "KOBIS_KEY가 정확한지, Streamlit Secrets에 "
                "올바르게 등록했는지 확인하세요."
            ),
            "data": None
        }

    # boxOfficeResult가 없는 경우
    if "boxOfficeResult" not in result:
        return {
            "success": False,
            "message": (
                "박스오피스 결과를 찾을 수 없습니다.\n\n"
                "KOBIS API 응답 내용을 확인하세요."
            ),
            "data": None
        }

    boxoffice_result = result["boxOfficeResult"]

    # 영화 목록 가져오기
    movie_list = boxoffice_result.get(
        "dailyBoxOfficeList",
        []
    )

    # 영화 목록이 비어 있는 경우
    if not movie_list:
        return {
            "success": False,
            "message": (
                f"{target_date} 날짜의 영화 목록이 없습니다.\n\n"
                "조회 날짜에 박스오피스 데이터가 존재하는지 "
                "또는 KOBIS API 응답을 확인하세요."
            ),
            "data": None
        }

    return {
        "success": True,
        "message": "",
        "data": movie_list
    }


# --------------------------------------------------
# 데이터 불러오기
# --------------------------------------------------

target_date = get_yesterday()

result = get_boxoffice(target_date)


# --------------------------------------------------
# API 오류가 발생한 경우
# --------------------------------------------------

if not result["success"]:
    st.error(result["message"])
    st.stop()


# --------------------------------------------------
# 데이터를 표와 그래프에 사용할 수 있도록 정리
# --------------------------------------------------

movies = result["data"]

df = pd.DataFrame(movies)

# KOBIS에서는 숫자도 문자열로 보내므로
# 실제 숫자 자료형으로 변환한다.
numeric_columns = [
    "rank",
    "audiCnt",
    "audiAcc",
    "scrnCnt",
    "showCnt",
    "rankInten"
]

for column in numeric_columns:
    df[column] = pd.to_numeric(
        df[column],
        errors="coerce"
    ).fillna(0).astype(int)


# 순위를 숫자 기준으로 정렬
df = df.sort_values("rank")


# --------------------------------------------------
# 조회 날짜 표시
# --------------------------------------------------

display_date = datetime.strptime(
    target_date,
    "%Y%m%d"
).strftime("%Y년 %m월 %d일")

st.subheader(f"{display_date} 박스오피스")


# --------------------------------------------------
# 1위 영화 정보
# --------------------------------------------------

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


# --------------------------------------------------
# 전체 영화 목록 표
# --------------------------------------------------

st.markdown("### 전체 순위")

table_df = df[
    [
        "rank",
        "movieNm",
        "openDt",
        "audiCnt",
        "audiAcc",
        "scrnCnt"
    ]
].copy()

# 표에서 보기 좋은 한국어 이름으로 변경
table_df.columns = [
    "순위",
    "영화명",
    "개봉일",
    "관객수",
    "누적관객",
    "스크린수"
]

# 숫자를 천 단위 쉼표로 표시
table_df["관객수"] = table_df["관객수"].map(
    lambda x: f"{x:,}"
)

table_df["누적관객"] = table_df["누적관객"].map(
    lambda x: f"{x:,}"
)

table_df["스크린수"] = table_df["스크린수"].map(
    lambda x: f"{x:,}"
)

st.dataframe(
    table_df,
    use_container_width=True,
    hide_index=True
)


# --------------------------------------------------
# 관객수 상위 5편 그래프
# --------------------------------------------------

st.markdown("### 관객수 상위 5편")

top5 = (
    df.sort_values(
        "audiCnt",
        ascending=False
    )
    .head(5)
    .copy()
)

# 영화명을 인덱스로 설정해서 막대그래프로 표시
chart_df = top5[
    ["movieNm", "audiCnt"]
].set_index("movieNm")

st.bar_chart(
    chart_df,
    y="audiCnt",
    x_label="영화",
    y_label="관객수"
)
