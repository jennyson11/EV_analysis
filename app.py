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
# 2. 사이드바 구성 (모델 안내 및 설정)
# ----------------------------------------------------------------------
with st.sidebar:
    st.title("⚡ EV 대시보드 설정")
    st.info(
        "**[안내] Gemini API 무료 티어 제한**\n\n"
        "본 앱은 가장 빠르고 가벼운 `gemini-2.5-flash-lite` 모델을 사용합니다.\n"
        "무료 티어 이용 시 **분당 최대 15회 요청(15 RPM)**으로 제한되니, "
        "AI 분석 버튼을 천천히 눌러주세요."
    )
    st.write("---")
    st.write("👨‍💻 **개발자:** Senior Data Engineer")
    st.write("📅 **기준일:** 2026년 기준 시뮬레이션")

# ----------------------------------------------------------------------
# 3. 데이터베이스 및 API 연결 초기화
# ----------------------------------------------------------------------
# Streamlit Secrets에서 환경변수 불러오기 (에러 방지를 위해 try-except 사용)
try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    
    # Supabase 클라이언트 생성
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    # Gemini 클라이언트 생성 (최신 google-genai 라이브러리 방식)
    ai_client = genai.Client(api_key=GEMINI_API_KEY)
except Exception as e:
    st.error("⚠️ 환경변수(Secrets)가 설정되지 않았습니다. 가이드를 참고하여 설정해주세요.")
    st.stop()

# ----------------------------------------------------------------------
# 4. 데이터 로드 (시뮬레이션 데이터 생성)
# ----------------------------------------------------------------------
@st.cache_data
def load_data():
    """대한민국 17개 시도별 전기차(EV) 시뮬레이션 데이터 생성"""
    data = {
        '지역': ['서울', '경기', '인천', '부산', '대구', '광주', '대전', '울산', '세종', '강원', '충북', '충남', '전북', '전남', '경북', '경남', '제주'],
        'EV_등록대수': [150000, 200000, 45000, 50000, 40000, 25000, 30000, 20000, 15000, 22000, 28000, 35000, 26000, 32000, 38000, 42000, 60000],
        '충전소_수': [12000, 15000, 4000, 5000, 4200, 2600, 3100, 2100, 1800, 3000, 3200, 4000, 3500, 4500, 5000, 5200, 8000],
        '보조금_신청률': [85.5, 88.2, 75.0, 68.5, 70.2, 65.0, 72.1, 60.5, 95.0, 80.0, 82.5, 85.0, 78.0, 88.0, 84.0, 81.0, 98.0]
    }
    df = pd.DataFrame(data)
    # 인프라 부족도 (1개 충전소당 감당해야 할 전기차 대수 - 높을수록 부족함)
    df['충전소당_EV_대수'] = round(df['EV_등록대수'] / df['충전소_수'], 1)
    return df

df = load_data()

# 데이터 다운로드 함수
def convert_df_to_csv(dataframe):
    return dataframe.to_csv(index=False).encode('utf-8')

csv_data = convert_df_to_csv(df)

# ----------------------------------------------------------------------
# 5. UI Layout - 상단 KPI 메트릭 카드
# ----------------------------------------------------------------------
st.title("🚗 전국 전기차(EV) 인프라 및 정책 분석 대시보드")
st.markdown("대한민국 지역별 전기차 보급 현황, 충전 인프라 부족 문제, 그리고 보조금 정책의 효과를 한눈에 분석합니다.")

# 주요 KPI 3가지 계산 및 표시
total_ev = df['EV_등록대수'].sum()
total_stations = df['충전소_수'].sum()
avg_subsidy_rate = df['보조금_신청률'].mean()

col1, col2, col3 = st.columns(3)
with col1:
    st.metric(label="총 전기차(EV) 등록대수", value=f"{total_ev:,} 대", delta="전년 대비 15% 📈")
with col2:
    st.metric(label="전국 전기차 충전소 수", value=f"{total_stations:,} 개소", delta="전년 대비 8% 📈")
with col3:
    st.metric(label="전국 평균 보조금 신청률", value=f"{avg_subsidy_rate:.1f} %", delta="목표치 달성 👍", delta_color="normal")

st.divider()

# ----------------------------------------------------------------------
# 6. UI Layout - 탭 구성 및 시각화
# ----------------------------------------------------------------------
tab1, tab2, tab3 = st.tabs(["📊 지역별 EV vs 충전소", "⚠️ 충전 인프라 부족도", "🗺️ 보조금 신청률 현황"])

# ----------------- (탭1) 지역별 전기차 등록대수 vs 충전소 수 -----------------
with tab1:
    st.subheader("지역별 전기차 등록대수 대비 충전소 구축 현황")
    st.error("💡 **핵심 인사이트:** 서울·경기는 EV 수요 대비 충전소 부족")
    
    # 이중 Y축 차트 생성 (Bar + Line)
    fig1 = make_subplots(specs=[[{"secondary_y": True}]])
    
    # 막대 그래프 (EV 등록대수)
    fig1.add_trace(
        go.Bar(x=df['지역'], y=df['EV_등록대수'], name="EV 등록대수 (대)", marker_color='#3498db'),
        secondary_y=False
    )
    # 꺾은선 그래프 (충전소 수)
    fig1.add_trace(
        go.Scatter(x=df['지역'], y=df['충전소_수'], name="충전소 수 (개소)", mode='lines+markers', line=dict(color='#e74c3c', width=3)),
        secondary_y=True
    )
    
    fig1.update_layout(title_text="EV 등록대수 및 충전소 수 (지역별)", hovermode="x unified")
    fig1.update_yaxes(title_text="<b>EV 등록대수</b>", secondary_y=False)
    fig1.update_yaxes(title_text="<b>충전소 수</b>", secondary_y=True)
    
    st.plotly_chart(fig1, use_container_width=True)
    st.download_button(label="📥 데이터 다운로드 (CSV)", data=csv_data, file_name="ev_stations_data.csv", mime="text/csv", key="tab1_csv")

# ----------------- (탭2) 지역별 충전 인프라 부족도 -----------------
with tab2:
    st.subheader("충전 인프라 부족도 (충전소 1개당 감당하는 EV 대수)")
    st.warning("🚨 **핵심 인사이트 (수도권 과밀 현상 확인 가능):** 수도권은 충전소 절대 수는 높지만, 전기차 증가 속도 대비 인프라 부족 현상이 나타난다.")
    
    # 데이터 정렬하여 부족한 곳을 눈에 띄게 시각화
    df_sorted = df.sort_values(by='충전소당_EV_대수', ascending=False)
    
    # 막대 그래프 (색상 스케일을 적용하여 부족도가 높을수록 붉은색)
    fig2 = px.bar(
        df_sorted, 
        x='지역', 
        y='충전소당_EV_대수',
        color='충전소당_EV_대수',
        color_continuous_scale='Reds',
        labels={'충전소당_EV_대수': '충전소 1개당 EV 대수 (높을수록 인프라 부족)'},
        title="지역별 인프라 부족 지수"
    )
    st.plotly_chart(fig2, use_container_width=True)
    st.download_button(label="📥 데이터 다운로드 (CSV)", data=csv_data, file_name="ev_scarcity_data.csv", mime="text/csv", key="tab2_csv")

# ----------------- (탭3) 지역별 보조금 신청률 현황 -----------------
with tab3:
    st.subheader("지역별 전기차 보조금 신청률 Heatmap")
    st.success("💰 **핵심 인사이트:** 보조금 정책이 EV 확산에 미친 영향 (신청률이 높은 지역일수록 보급 속도가 빠름)")
    
    # 지역별 보조금 신청률을 Heatmap(Treemap 방식)으로 시각화하여 지도를 대체 (호환성 및 디자인 고려)
    fig3 = px.treemap(
        df, 
        path=[px.Constant("대한민국"), '지역'], 
        values='보조금_신청률',
        color='보조금_신청률',
        color_continuous_scale='Greens',
        title="전국 보조금 신청률 분포 (크기와 색상이 신청률을 나타냄)"
    )
    fig3.update_traces(hovertemplate='<b>%{label}</b><br>신청률: %{color:.1f}%')
    st.plotly_chart(fig3, use_container_width=True)
    st.download_button(label="📥 데이터 다운로드 (CSV)", data=csv_data, file_name="ev_subsidy_data.csv", mime="text/csv", key="tab3_csv")

st.write("---")

# ----------------------------------------------------------------------
# 7. AI 인사이트 자동 요약 및 Supabase 저장 (Form 활용)
# ----------------------------------------------------------------------
st.header("🤖 AI 인사이트 도출 및 DB 저장")
st.write("선택한 지역의 데이터를 바탕으로 Gemini AI가 인사이트를 분석하고 메모와 함께 DB에 저장합니다.")

# 폼(Form)을 활용하여 버튼 클릭 시 한 번에 실행되도록 구성
with st.form("ai_insight_form"):
    target_region = st.selectbox("분석할 지역을 선택하세요:", df['지역'].tolist())
    user_memo = st.text_area("✍️ 분석 메모를 작성해주세요 (예: 다음 분기 예산 편성 시 참고할 것)")
    
    submit_btn = st.form_submit_button("Gemini AI 분석 및 Supabase에 저장 🚀")

if submit_btn:
    with st.spinner(f"{target_region} 지역의 데이터를 분석 중입니다..."):
        try:
            # 1. AI 프롬프트 구성을 위해 선택한 지역의 데이터 추출
            region_data = df[df['지역'] == target_region].iloc[0]
            prompt = f"""
            너는 시니어 데이터 엔지니어이자 전기차 정책 분석가야.
            다음은 대한민국의 '{target_region}' 지역 전기차 데이터야:
            - 전기차 등록대수: {region_data['EV_등록대수']}대
            - 충전소 수: {region_data['충전소_수']}개소
            - 충전소 1개당 감당하는 EV 대수(부족도): {region_data['충전소당_EV_대수']}대
            - 보조금 신청률: {region_data['보조금_신청률']}%
            
            이 데이터를 바탕으로 '{target_region}' 지역의 인프라 상태와 보조금 정책의 상관관계에 대한 핵심 인사이트를 3줄 이내로 간결하게 요약해줘.
            """
            
            # 2. Gemini API 호출 (최신 버전 사용)
            response = ai_client.models.generate_content(
                model='gemini-2.5-flash-lite',
                contents=prompt
            )
            ai_summary = response.text
            
            # AI 결과 화면 출력
            st.success("✅ AI 인사이트 분석 완료!")
            st.markdown(f"> **AI 분석 결과:**\n> {ai_summary}")
            
            # 3. Supabase 데이터베이스에 저장
            db_insert_data = {
                "region": target_region,
                "ai_summary": ai_summary,
                "user_memo": user_memo
            }
            # supabase-py 클라이언트를 사용해 테이블에 insert 
            result = supabase.table("ev_insights_history").insert(db_insert_data).execute()
            
            st.info("💾 분석 결과와 메모가 Supabase DB(`ev_insights_history` 테이블)에 성공적으로 저장되었습니다!")
            
        except Exception as e:
            st.error(f"오류가 발생했습니다: {e}")
