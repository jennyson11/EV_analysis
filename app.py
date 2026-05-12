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
st.markdown("대한민국 지역별 전기차 보급 현황과 인프라 부족 문제를 AI로 분석합니다.")

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
        st.markdown("### 🔍 Used SQL Query")
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
        st.markdown("### 💡 Analysis Insight")
        st.info("여기에 첫 번째 탭의 분석 결과(예: 서울/경기 지역의 집중화 등)를 입력하세요.")

with tab2:
    st.subheader("충전 인프라 부족도 (충전소 1개당 EV 대수)")
    df_sorted = df.sort_values(by='충전소당_EV_대수', ascending=False)
    fig2 = px.bar(df_sorted, x='지역', y='충전소당_EV_대수', color='충전소당_EV_대수', color_continuous_scale='Reds')
    st.plotly_chart(fig2, use_container_width=True)

with tab3:
    st.subheader("지역별 보조금 신청률 Heatmap")
    fig3 = px.treemap(df, path=[px.Constant("대한민국"), '지역'], values='보조금_신청률', color='보조금_신청률', color_continuous_scale='Greens')
    st.plotly_chart(fig3, use_container_width=True)

st.write("---")

# ----------------------------------------------------------------------
# 7. AI 분석 및 DB 저장
# ----------------------------------------------------------------------
st.header("🤖 AI 인사이트 도출 및 DB 저장")

with st.form("ai_insight_form"):
    target_region = st.selectbox("분석할 지역 선택:", df['지역'].tolist())
    user_memo = st.text_area("✍️ 분석 메모 작성:")
    submit_btn = st.form_submit_button("AI 분석 및 저장 🚀")

if submit_btn:
    with st.spinner(f"{target_region} 지역 분석 중..."):
        try:
            region_data = df[df['지역'] == target_region].iloc[0]
            prompt = f"""
            너는 시니어 전기차 정책 분석가야. 아래 데이터를 분석해줘:
            지역: {target_region}
            EV 등록대수: {region_data['EV_등록대수']}대
            충전소 수: {region_data['충전소_수']}개소
            충전소당 EV 대수: {region_data['충전소당_EV_대수']}대
            보조금 신청률: {region_data['보조금_신청률']}%
            
            이 지역의 인프라 상태와 보조금 정책의 상관관계에 대한 인사이트를 3줄 이내로 요약해.
            """
            
            # API 호출 (모델명 gemini-2.0-flash-lite)
            response = ai_client.models.generate_content(
                model='gemini-2.0-flash-lite',
                contents=prompt
            )
            ai_summary = response.text
            
            st.success("✅ AI 분석 완료!")
            st.markdown(f"> {ai_summary}")
            
            # Supabase 저장
            db_data = {
                "region": target_region,
                "ai_summary": ai_summary,
                "user_memo": user_memo
            }
            supabase.table("ev_insights_history").insert(db_data).execute()
            st.info("💾 데이터베이스 저장 완료!")
            
        except Exception as e:
            st.error(f"오류 발생: {e}")
