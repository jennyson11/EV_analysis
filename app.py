import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from supabase import create_client, Client
from google import genai
import datetime

# ----------------------------------------------------------------------
# 1. 페이지 설정 및 초기화
# ----------------------------------------------------------------------
st.set_page_config(
    page_title="EV 인프라 및 정책 분석 대시보드",
    page_icon="⚡",
    layout="wide"
)

# ----------------------------------------------------------------------
# 2. 데이터베이스 및 API 연결 초기화
# ----------------------------------------------------------------------
try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    
    # Supabase 클라이언트 생성
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    # Gemini 클라이언트 생성
    ai_client = genai.Client(api_key=GEMINI_API_KEY)
except Exception as e:
    st.error("⚠️ 환경변수(Secrets) 설정 오류: `SUPABASE_URL`, `SUPABASE_KEY`, `GEMINI_API_KEY`를 확인하세요.")
    st.stop()

# ----------------------------------------------------------------------
# 4. 데이터 로드 (시뮬레이션 데이터 생성)
# ----------------------------------------------------------------------
@st.cache_data
def load_data():
    data = {
        '지역': ['서울', '경기', '인천', '부산', '대구', '광주', '대전', '울산', '세종', '강원', '충북', '충남', '전북', '전남', '경북', '경남', '제주'],
        'EV_등록대수': [150000, 200000, 45000, 50000, 40000, 25000, 30000, 20000, 15000, 22000, 28000, 35000, 26000, 32000, 38000, 42000, 60000],
        '충전소_수': [12000, 15000, 4000, 5000, 4200, 2600, 3100, 2100, 1800, 3000, 3200, 4000, 3500, 4500, 5000, 5200, 8000],
        '보조금_신청률': [85.5, 88.2, 75.0, 68.5, 70.2, 65.0, 72.1, 60.5, 95.0, 80.0, 82.5, 85.0, 78.0, 88.0, 84.0, 81.0, 98.0]
    }
    df = pd.DataFrame(data)
    df['충전소당_EV_대수'] = round(df['EV_등록대수'] / df['충전소_수'], 1)
    return df

df = load_data()

def convert_df_to_csv(dataframe):
    return dataframe.to_csv(index=False).encode('utf-8-sig') # 한글 깨짐 방지 위해 utf-8-sig 사용

csv_data = convert_df_to_csv(df)

# ----------------------------------------------------------------------
# 5. UI Layout - 상단 KPI
# ----------------------------------------------------------------------
st.title("🚗 전국 전기차(EV) 인프라 및 정책 분석 대시보드")

total_ev = df['EV_등록대수'].sum()
total_stations = df['충전소_수'].sum()
avg_subsidy_rate = df['보조금_신청률'].mean()

col1, col2, col3 = st.columns(3)
with col1:
    st.metric(label="총 전기차(EV) 등록대수", value=f"{total_ev:,} 대", delta="전년 대비 15% 📈")
with col2:
    st.metric(label="전국 전기차 충전소 수", value=f"{total_stations:,} 개소", delta="전년 대비 8% 📈")
with col3:
    st.metric(label="전국 평균 보조금 신청률", value=f"{avg_subsidy_rate:.1f} %", delta="목표치 달성 👍")

st.divider()

# ----------------------------------------------------------------------
# 6. UI Layout - 시각화 탭
# ----------------------------------------------------------------------
tab1, tab2, tab3 = st.tabs(["📊 지역별 EV vs 충전소", "⚠️ 인프라 부족도", "🗺️ 보조금 현황"])

with tab1:
    st.subheader("지역별 전기차 등록대수 대비 충전소 구축 현황")
    fig1 = make_subplots(specs=[[{"secondary_y": True}]])
    fig1.add_trace(go.Bar(x=df['지역'], y=df['EV_등록대수'], name="EV 등록대수", marker_color='#3498db'), secondary_y=False)
    fig1.add_trace(go.Scatter(x=df['지역'], y=df['충전소_수'], name="충전소 수", mode='lines+markers', line=dict(color='#e74c3c', width=3)), secondary_y=True)
    fig1.update_layout(hovermode="x unified")
    st.plotly_chart(fig1, use_container_width=True)

    # --- SQL 및 인사이트 추가 구간 ---
    col1_sql, col1_ins = st.columns(2)
    with col1_sql:
        st.markdown("### 🔍 사용된 SQL")
        st.code("""
SELECT 
    reg.시도 AS [등록현황_지역명],
    chg.시도 AS [충전소_지역명],
    -- 2022년 등록 대수 합계
    SUM(reg.`2022년 출고대수`) AS [전기차_등록대수],
    -- 2022년 충전소 수
    MAX(chg.`2022`) AS [충전소_수],
    -- 비율 계산
    ROUND(SUM(reg.`2022년 출고대수`) * 1.0 / MAX(chg.`2022`), 2) AS [충전소1개당_차량수]
FROM `지역별 전기 자동차 등록 및 보조금 신청 현황` reg
JOIN `지역별 전기차 충전소 현황정보` chg 
  -- 지역명의 앞 2글자만 추출하여 비교 (예: '서울' vs '서울특별시')
  ON SUBSTR(reg.시도, 1, 2) = SUBSTR(chg.시도, 1, 2)
GROUP BY reg.시도, chg.시도
ORDER BY [전기차_등록대수] DESC; """, language='sql')
    with col1_ins:
        st.markdown("### 💡 분석 인사이트")
        st.info("불균형적인 인프라 공급: 전기차 보급량 대비 충전 인프라는 전국적으로 매우 불균형하게 공급되고 있다. 단순히 등록 대수가 많은 곳이 가장 혼잡한 것이 아니라, 인천이나 대전처럼 '등록 차량 증가 속도를 충전소 구축 속도가 따라가지 못하는 광역시'에서 심각한 병목이 발생하고 있다. 
        지역적 특수성 반영: 강원이나 제주(22.95대)의 경우 거주 인구 대비 충전소가 많은 것은 '관광지'라는 특성이 반영되어 지자체 차원에서 선제적으로 인프라를 확충했을 가능성이 높다. 반면 인천은 물류 및 출퇴근용 차량의 급증을 인프라가 수용하지 못하는 병목 현상으로 해석된다.")

with tab2:
    st.subheader("충전 인프라 부족도 (충전소 1개당 EV 대수)")
    df_sorted = df.sort_values(by='충전소당_EV_대수', ascending=False)
    fig2 = px.bar(df_sorted, x='지역', y='충전소당_EV_대수', color='충전소당_EV_대수', color_continuous_scale='Reds')
    st.plotly_chart(fig2, use_container_width=True)

# --- SQL 및 인사이트 추가 구간 ---
    col2_sql, col2_ins = st.columns(2)
    with col2_sql:
        st.markdown("### 🔍 사용된 SQL")
        st.code("""
SELECT 
    시도,
    COUNT(단지명) AS 총_단지수,
    -- 0이나 NULL 데이터를 제외하고 실제 숫자가 있는 것만 합산
    SUM(CAST(IFNULL(`차량보유대수(전기차)`, 0) AS FLOAT)) AS 단지내_전기차수_합계,
    SUM(CAST(IFNULL(`전기차 충전시설 설치대수(지상)`, 0) AS FLOAT) + 
        CAST(IFNULL(`전기차 충전시설 설치대수(지하)`, 0) AS FLOAT)) AS 단지내_충전기수_합계,
    -- 계산식: (전기차 수 / 충전기 수)
    ROUND(
        SUM(CAST(IFNULL(`차량보유대수(전기차)`, 0) AS FLOAT)) / 
        NULLIF(SUM(CAST(IFNULL(`전기차 충전시설 설치대수(지상)`, 0) AS FLOAT) + 
                   CAST(IFNULL(`전기차 충전시설 설치대수(지하)`, 0) AS FLOAT)), 0)
    , 2) AS 단지내_충전기1개당_차량수
FROM `단지_기본정보`
-- 데이터가 아예 없는 행은 제외하여 정확도 향상
WHERE 시도 IS NOT NULL AND 시도 != ''
GROUP BY 시도
ORDER BY 단지내_충전기1개당_차량수 DESC; """, language='sql')
    with col2_ins:
        st.markdown("### 💡 분석 인사이트")
        st.warning("거주지 ↔ 공용 인프라의 불균형: 전체 충전소 기준으로는 여유로웠던 제주가 단지 내 기준으로는 전국 최악의 부족 사태를 겪고 있다. 이는 제주의 인프라가 관광지나 렌터카 위주의 '공용 인프라'에만 편중되어 도민들의 실거주지 충전 환경을 방치했음을 보여준다. 반면 서울·경기는 전체 인프라 대비 주거지 내 충전기 보급 방어율이 매우 뛰어나다. 향후 정책은 거주지(단지 내) 인프라가 부족한 특정 지자체를 타겟으로 한 핀셋 보조금 지원으로 전환되어야 한다.")

with tab3:
    st.subheader("지역별 보조금 신청률 Heatmap")
    fig3 = px.treemap(df, path=[px.Constant("대한민국"), '지역'], values='보조금_신청률', color='보조금_신청률', color_continuous_scale='Greens')
    st.plotly_chart(fig3, use_container_width=True)

    # --- SQL 및 인사이트 추가 구간 ---
    col3_sql, col3_ins = st.columns(2)
    with col3_sql:
        st.markdown("### 🔍 사용된 SQL")
        st.code("""SELECT 
    시도,
    -- 공고 물량과 출고 대수를 각각 확인하기 위해 추출
    SUM(`2022년 공고대수(전체)`) AS [총_공고물량],
    SUM(`2022년 출고대수`) AS [총_출고대수],
    
    -- 신청률 (소수점 2자리까지 확인)
    ROUND(
        SUM(CAST(`2022년 접수대수(우선순위)` AS FLOAT) + `2022년 접수대수(법인_기관)` + `2022년 접수대수(택시)` + `2022년 접수대수(일반)`) 
        / NULLIF(SUM(`2022년 공고대수(전체)`), 0) * 100
    , 2) AS [보조금_신청률(%)],
    
    -- 예산 집행률 (소수점 2자리까지 확인)
    ROUND(
        SUM(CAST(`2022년 출고대수` AS FLOAT)) 
        / NULLIF(SUM(`2022년 공고대수(전체)`), 0) * 100
    , 2) AS [예산_집행률(%)]
FROM `지역별 전기 자동차 등록 및 보조금 신청 현황`
GROUP BY 시도
ORDER BY [예산_집행률(%)] DESC;
""", language='sql')
    with col3_ins:
        st.markdown("### 💡 분석 인사이트")
        st.success("보조금 정책의 효과와 할당의 미스매치: 보조금 정책 자체는 전기차 수요를 견인하는 데 확실한 효과를 내고 있으나, 지역별 예산 배정 수요 예측에는 실패했다. 구매 의사가 높은 지방(경북, 전북, 제주 등)은 예산 조기 소진으로 전기차 확산에 제동이 걸리는 반면, 인구가 많은 수도권(서울, 경기)은 오히려 예산이 남아돌며 정체되고 있다. 따라서 연초에 고정된 물량을 할당하는 방식에서 벗어나, 분기별 실제 소진 속도에 맞춰 수도권의 남는 예산을 지방으로 이관하는 탄력적인 예산 재배치 시스템이 필요하다.")

st.write("---")
