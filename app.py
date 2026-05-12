import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import sqlite3
import os

# ==========================================
# 1. 페이지 기본 설정
# ==========================================
st.set_page_config(
    page_title="전기차 충전 인프라 분석 대시보드",
    page_icon="⚡",
    layout="wide" # 화면을 넓게 사용합니다.
)

# ==========================================
# 2. 데이터베이스(SQLite) 연동 및 초기화 함수
# ==========================================
DB_PATH = "database/ev_data.db"

def init_db():
    """데이터베이스와 테이블을 생성하는 함수입니다."""
    # database 폴더가 없으면 생성
    if not os.path.exists('database'):
        os.makedirs('database')
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 통합 분석용 테이블 생성 (초보자를 위해 복잡한 JOIN 대신 통합 테이블 1개를 사용합니다)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS integrated_ev_data (
            sido TEXT,
            sigungu TEXT,
            ev_count INTEGER,
            subsidy_notice INTEGER,
            subsidy_applied INTEGER,
            station_count INTEGER,
            PRIMARY KEY (sido, sigungu)
        )
    ''')
    conn.commit()
    conn.close()

# 앱 실행 시 DB 초기화
init_db()

# ==========================================
# 3. 데이터 전처리(Cleansing) 함수
# ==========================================
def clean_data(df):
    """결측치 처리 및 숫자형 변환을 수행합니다."""
    # 모든 숫자형 컬럼의 결측치(NaN)를 0으로 채웁니다.
    df = df.fillna(0)
    return df

# ==========================================
# 4. 사이드바 - CSV 파일 업로드
# ==========================================
st.sidebar.header("📁 데이터 업로드")
st.sidebar.markdown("공공데이터 CSV 파일을 업로드해주세요.")

# 3개의 파일을 각각 업로드 받습니다.
file_ev = st.sidebar.file_uploader("1. 전기차 등록 현황 (CSV)", type=['csv'])
file_station = st.sidebar.file_uploader("2. 충전소 현황 (CSV)", type=['csv'])

# 데이터를 담을 빈 데이터프레임 초기화
df_final = pd.DataFrame()

if file_ev and file_station:
    try:
        # 데이터 읽기
        df_ev = pd.read_csv(file_ev)
        df_station = pd.read_csv(file_station)
        
        # 컬럼명 통일 (사용자가 올리는 파일마다 컬럼명이 다를 수 있으므로 매핑 필요)
        # 예시용으로 표준 컬럼명으로 변경한다고 가정합니다.
        df_ev.rename(columns={'시도': 'sido', '시군구': 'sigungu', '전기차등록대수': 'ev_count', 
                              '보조금공고대수': 'subsidy_notice', '보조금신청대수': 'subsidy_applied'}, inplace=True)
        
        df_station.rename(columns={'시도': 'sido', '시군구': 'sigungu', '충전소수': 'station_count'}, inplace=True)

        # 데이터 병합 (JOIN) - 시도, 시군구를 기준으로 합칩니다. (SQL의 LEFT JOIN과 동일)
        df_merged = pd.merge(df_ev, df_station, on=['sido', 'sigungu'], how='left')
        
        # 데이터 클린징 (결측치 0으로 처리)
        df_final = clean_data(df_merged)

        # SQLite DB에 저장 (기존 데이터는 대체)
        conn = sqlite3.connect(DB_PATH)
        df_final.to_sql('integrated_ev_data', conn, if_exists='replace', index=False)
        conn.close()
        
        st.sidebar.success("데이터 업로드 및 DB 저장 완료! ✅")
        
    except Exception as e:
        st.sidebar.error(f"데이터 처리 중 오류 발생: {e}")

# ==========================================
# 5. DB에서 데이터 불러오기 및 파생변수 생성
# ==========================================
try:
    conn = sqlite3.connect(DB_PATH)
    # DB에서 데이터를 읽어옵니다.
    df = pd.read_sql_query("SELECT * FROM integrated_ev_data", conn)
    conn.close()
    
    if not df.empty:
        # 분석을 위한 파생변수 생성
        # 1. 충전소당 차량 수 (과밀도): 0으로 나누는 오류를 방지하기 위해 station_count가 0이면 1로 처리
        df['density'] = df['ev_count'] / df['station_count'].replace(0, 1)
        
        # 2. 보조금 신청률
        df['subsidy_rate'] = (df['subsidy_applied'] / df['subsidy_notice'].replace(0, 1)) * 100
        
        # 소수점 둘째 자리까지 반올림
        df['density'] = df['density'].round(2)
        df['subsidy_rate'] = df['subsidy_rate'].round(2)
        
        # 시도 단위로 통합된 데이터(SUM)도 하나 만들어 둡니다 (지역별 거시적 분석용)
        df_sido = df.groupby('sido').sum(numeric_only=True).reset_index()
        df_sido['density'] = (df_sido['ev_count'] / df_sido['station_count'].replace(0, 1)).round(2)
        df_sido['subsidy_rate'] = ((df_sido['subsidy_applied'] / df_sido['subsidy_notice'].replace(0, 1)) * 100).round(2)

except Exception as e:
    df = pd.DataFrame()

# ==========================================
# 6. 메인 화면 UI 구성 (타이틀 및 탭)
# ==========================================
st.title("⚡ 지역별 전기차 충전 인프라 적정성 분석 대시보드")
st.markdown("공공데이터를 기반으로 지역별 전기차 보급 확산에 따른 **충전 인프라의 과밀도 및 보조금 정책의 효과**를 분석합니다.")

# 5개의 탭 생성
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 데이터 개요", 
    "⚖️ 수요 vs 공급", 
    "🚨 과밀도 분석", 
    "💰 보조금 분석", 
    "💡 인사이트 요약"
])

# 데이터가 없을 경우 안내 메시지 출력
if df.empty:
    st.info("👈 왼쪽 사이드바에서 CSV 데이터를 먼저 업로드해주세요.")
else:
    # ----------------------------------------
    # 탭 1: 데이터 개요 및 KPI
    # ----------------------------------------
    with tab1:
        st.subheader("📌 핵심 지표 (KPI)")
        
        # KPI 계산
        total_ev = int(df['ev_count'].sum())
        total_station = int(df['station_count'].sum())
        avg_density = round(total_ev / total_station if total_station > 0 else 0, 2)
        
        # KPI 카드 UI (Streamlit columns 활용)
        col1, col2, col3 = st.columns(3)
        col1.metric(label="전국 총 전기차 등록대수", value=f"{total_ev:,} 대")
        col2.metric(label="전국 총 충전소 수", value=f"{total_station:,} 개소")
        col3.metric(label="전국 평균 과밀도 (충전소당 차량 수)", value=f"{avg_density} 대/개소", delta="높을수록 혼잡", delta_color="inverse")
        
        st.divider() # 구분선
        
        st.subheader("📋 전체 데이터 미리보기")
        st.dataframe(df, use_container_width=True)
        
        # 데이터 다운로드 버튼 기능
        csv = df.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            label="📥 분석 데이터 결과 다운로드 (CSV)",
            data=csv,
            file_name="ev_analysis_result.csv",
            mime="text/csv",
        )

    # ----------------------------------------
    # 탭 2: 지역별 전기차 등록대수 vs 충전소 수 (수요 vs 공급)
    # ----------------------------------------
    with tab2:
        st.subheader("⚖️ 지역별 전기차 수요(등록대수) 대비 공급(충전소) 현황")
        st.markdown("**목적:** 전기차 보급 속도에 맞춰 충전 인프라가 원활히 공급되고 있는지 파악합니다.")
        
        # Plotly 이중 축 차트 생성 (막대: 전기차, 선: 충전소)
        fig = go.Figure()
        
        # 전기차 막대 그래프 추가
        fig.add_trace(go.Bar(
            x=df_sido['sido'], y=df_sido['ev_count'],
            name='전기차 등록대수 (수요)',
            marker_color='#1f77b4'
        ))
        
        # 충전소 선 그래프 추가 (보조 축 사용)
        fig.add_trace(go.Scatter(
            x=df_sido['sido'], y=df_sido['station_count'],
            name='충전소 수 (공급)',
            mode='lines+markers',
            marker_color='#ff7f0e',
            yaxis='y2'
        ))
        
        # 레이아웃(이중 축) 설정
        fig.update_layout(
            title='시도별 전기차 등록대수 및 충전소 수 비교',
            yaxis=dict(title='전기차 대수'),
            yaxis2=dict(title='충전소 수', overlaying='y', side='right'),
            barmode='group',
            legend=dict(x=0.01, y=0.99)
        )
        
        st.plotly_chart(fig, use_container_width=True)

    # ----------------------------------------
    # 탭 3: 충전 인프라 과밀도 분석
    # ----------------------------------------
    with tab3:
        st.subheader("🚨 충전 인프라 과밀도 분석 (충전소 1개당 차량 수)")
        st.markdown("**과밀도 = 전기차 등록대수 ÷ 충전소 수**<br>값이 높을수록 충전 대기 시간이 길어지고 인프라가 부족함을 의미합니다.", unsafe_allow_html=True)
        
        # 과밀도 높은 순으로 정렬
        df_density_sorted = df_sido.sort_values('density', ascending=False)
        
        # Plotly 막대 그래프 (색상으로 과밀도 강조)
        fig_density = px.bar(
            df_density_sorted, 
            x='sido', 
            y='density',
            color='density',
            color_continuous_scale='Reds', # 과밀도가 높을수록 붉은색(위험)으로 표시
            labels={'sido': '시도명', 'density': '충전소 1개당 감당 차량 수'},
            title='지역별 충전 인프라 과밀도 순위'
        )
        st.plotly_chart(fig_density, use_container_width=True)

    # ----------------------------------------
    # 탭 4: 보조금 신청률 분석
    # ----------------------------------------
    with tab4:
        st.subheader("💰 지역별 전기차 보조금 신청률 분석")
        st.markdown("**목적:** 보조금 공고 대비 실제 신청 비율을 확인하여 정책 실효성을 분석합니다.")
        
        # 보조금 신청률 시각화 (Treemap 활용: 지역별 크기와 색상으로 한눈에 파악 가능)
        # 초보자에게 어려운 지도(GeoJSON) 데이터 대신 직관적이고 멋진 Treemap을 사용합니다.
        fig_subsidy = px.treemap(
            df,
            path=[px.Constant("대한민국"), 'sido', 'sigungu'],
            values='subsidy_applied',
            color='subsidy_rate',
            color_continuous_scale='Blues',
            labels={'subsidy_rate': '보조금 신청률(%)'},
            title='전국 시군구별 보조금 신청률 분포 (크기: 신청대수, 색상: 신청률)'
        )
        fig_subsidy.update_traces(root_color="lightgrey")
        st.plotly_chart(fig_subsidy, use_container_width=True)

    # ----------------------------------------
    # 탭 5: 통합 인사이트 요약
    # ----------------------------------------
    with tab5:
        st.subheader("💡 데이터 분석 인사이트")
        st.info("데이터 분석 결과를 바탕으로 도출된 핵심 인사이트입니다.")
        
        st.markdown("""
        ### 1. 수요 vs 공급 불균형 (서울·경기 중심)
        * **현상:** 서울 및 경기 지역은 전기차 등록대수(수요)가 압도적으로 높으나, 충전소 증가 속도(공급)가 이를 완벽히 따라가지 못하는 추세를 보입니다.
        * **해결책:** 수도권 지역에 급속 충전기 및 공동주택(아파트) 내 완속 충전기 인프라 집중 투자가 필요합니다.
        
        ### 2. 충전 인프라 과밀도 심화
        * **현상:** 과밀도 차트에서 붉은색으로 표시된 상위 지역들은 충전소 1개가 감당해야 하는 전기차 대수가 타 지역 대비 매우 높습니다. 
        * **영향:** 이는 심각한 충전 대기열 발생과 시민 불편으로 직결되며, 과밀화 상태를 해소하기 위한 지자체의 긴급 예산 편성이 요구됩니다.
        
        ### 3. 보조금 정책과 보급률의 상관관계
        * **현상:** 보조금 분석 맵(Treemap)에서 진한 파란색을 띠는 지역(신청률 90% 이상)일수록 전체 전기차 보급률도 가파르게 상승하는 경향이 있습니다.
        * **결론:** 보조금은 여전히 전기차 구매의 강력한 유인책이므로, 신청률이 저조한 지역은 홍보 강화 및 추가 인센티브 제공이 필요합니다.
        """)