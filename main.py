
import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


# --------------------------------------------------
# 기본 설정
# --------------------------------------------------

st.set_page_config(
    page_title="박스오피스 조회",
    page_icon="🎬",
    layout="wide"
)

st.title("박스오피스 조회")
st.caption("KOBIS 일일 박스오피스")


# --------------------------------------------------
# 날짜 계산
# --------------------------------------------------

# 한국 시간을 기준으로 오늘 날짜를 구한다.
korea_now = datetime.now(ZoneInfo("Asia/Seoul"))

# 오늘은 아직 집계 전이므로 어제까지만 선택할 수 있다.
yesterday = (korea_now - timedelta(days=1)).date()

# 달력에서 선택할 날짜
selected_date = st.date_input(
    "조회할 날짜를 선택하세요.",
    value=yesterday,
    min_value=datetime(2000, 1, 1).date(),
    max_value=yesterday
)

# KOBIS API가 요구하는 YYYYMMDD 형식으로 변환
target_date = selected_date.strftime("%Y%m%d")


# --------------------------------------------------
# KOBIS API 호출
# --------------------------------------------------

@st.cache_data(ttl=3600)
def get_boxoffice(target_date):
    """
    KOBIS API에서 선택한 날짜의 박스오피스 정보를 가져온다.
    같은 날짜를 다시 조회하면 약 1시간 동안 저장된 결과를 사용한다.
    """

    # Streamlit Secrets에서 인증키를 가져온다.
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
        "https://www.kobis.or.kr/kobisopenapi/webservice/rest/"
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

    # 인증키가 잘못된 경우 faultInfo가 들어온다.
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

    # 박스오피스 결과가 없는 경우
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

    # 영화 목록 가져오기
    movie_list = boxoffice_result.get(
        "dailyBoxOfficeList",
        []
    )

    # 영화 목록이 비어 있으면 집계 전으로 안내한다.
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


# --------------------------------------------------
# 데이터 가져오기
# --------------------------------------------------

result = get_boxoffice(target_date)


# --------------------------------------------------
# 오류 처리
# --------------------------------------------------

if not result["success"]:
    st.warning(result["message"])
    st.stop()


# --------------------------------------------------
# 데이터프레임 만들기
# --------------------------------------------------

df = pd.DataFrame(result["data"])


# KOBIS에서는 숫자도 문자열로 보내므로 숫자로 변환한다.
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


# --------------------------------------------------
# 조회 날짜 표시
# --------------------------------------------------

display_date = selected_date.strftime("%Y년 %m월 %d일")

st.subheader(f"{display_date} 박스오피스")


# --------------------------------------------------
# 1위 영화
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
# 표에 표시할 데이터 만들기
# --------------------------------------------------

table_df = df[
    [
        "rank",
        "movieNm",
        "openDt",
        "audiCnt",
        "audiAcc",
        "scrnCnt",
        "rankInten"
    ]
].copy()


# 영화명 옆에 트로피 표시
def add_trophy(row):
    """
    누적관객이 100만 명을 넘었으면
    영화명 뒤에 트로피 이모지를 붙인다.
    """
    movie_name = str(row["movieNm"])

    if row["audiAcc"] >= 1_000_000:
        return movie_name + " 🏆"

    return movie_name


table_df["movieNm"] = table_df.apply(
    add_trophy,
    axis=1
)


# 순위 증감 표시
def format_rank_change(value):
    """
    rankInten을 보고 순위 변화를 표시한다.

    양수 = 순위 상승 → 빨간 위 화살표
    음수 = 순위 하락 → 파란 아래 화살표
    0 = 변동 없음
    """

    value = int(value)

    if value > 0:
        return f":red[↑ {value}]"

    elif value < 0:
        return f":blue[↓ {abs(value)}]"

    else:
        return "-"


table_df["rankChange"] = table_df["rankInten"].apply(
    format_rank_change
)


# 표에서 사용할 열 이름
table_df = table_df[
    [
        "rank",
        "movieNm",
        "openDt",
        "audiCnt",
        "audiAcc",
        "scrnCnt",
        "rankChange"
    ]
]

table_df.columns = [
    "순위",
    "영화명",
    "개봉일",
    "관객수",
    "누적관객",
    "스크린수",
    "전일 대비"
]


# 숫자를 보기 편하게 표시
table_df["관객수"] = table_df["관객수"].map(
    lambda x: f"{x:,}"
)

table_df["누적관객"] = table_df["누적관객"].map(
    lambda x: f"{x:,}"
)

table_df["스크린수"] = table_df["스크린수"].map(
    lambda x: f"{x:,}"
)


# --------------------------------------------------
# 박스오피스 표
# --------------------------------------------------

st.markdown("### 전체 순위")

st.markdown(
    """
    **순위 변화:** :red[↑ 상승] · :blue[↓ 하락]  
    **🏆 누적관객 100만 명 이상**
    """
)

st.dataframe(
    table_df,
    use_container_width=True,
    hide_index=True
)


# --------------------------------------------------
# 관객수 상위 5편 막대그래프
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

chart_df = top5[
    ["movieNm", "audiCnt"]
].set_index("movieNm")

st.bar_chart(
    chart_df,
    y="audiCnt",
    x_label="영화",
    y_label="관객수"
)
