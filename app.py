import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np

# 1. 페이지 설정
st.set_page_config(page_title="EV Data Dashboard", page_icon="🚗", layout="wide")
st.title("🚗 전국 전기차(EV) 인프라 및 정책 분석 대시보드")

# 2. 데이터 로드 및 전처리 (캐싱으로 로딩 속도 최적화)
@st.cache_data
def load_data():
    # 파일 읽기
    df_subsidy = pd.read_csv('지역별 전기 자동차 등록 및 보조금 신청 현황.csv')
    df_charger = pd.read_csv('지역별 전기차 충전소 현황정보.csv')
    df_apt = pd.read_csv('단지_기본정보_클린징.csv', low_memory=False)

    # --- [데이터 전처리 1] 보조금 및 등록대수 ---
    # 보조금 현황 시도명 전처리 (예: 서울특별시 -> 서울)
    df_subsidy['지역_단축'] = df_subsidy['시도'].str[:2]
    # 접수대수 합산 (우선+법인+택시+일반)
    df_subsidy['총_접수대수'] = df_subsidy[['2022년 접수대수(우선순위)', '2022년 접수대수(법인_기관)', '2022년 접수대수(택시)', '2022년 접수대수(일반)']].sum(axis=1)
    df_subsidy_agg = df_subsidy.groupby('지역_단축').agg(
        공고대수=('2022년 공고대수(전체)', 'sum'),
        접수대수=('총_접수대수', 'sum'),
        출고대수=('2022년 출고대수', 'sum')
    ).reset_index()
    # 신청률 계산
    df_subsidy_agg['보조금_신청률'] = (df_subsidy_agg['접수대수'] / df_subsidy_agg['공고대수'] * 100).round(1)

    # --- [데이터 전처리 2] 충전소 현황 ---
    # 충전소 지역명 전처리 (예: 강원특별자치도 -> 강원, 광주광역시 -> 광주)
    df_charger['지역_단축'] = df_charger['지역'].str[:2]
    df_charger_agg = df_charger[['지역_단축', '2022']].rename(columns={'2022': '충전소_수'})

    # --- [데이터 전처리 3] 단지 내 인프라 현황 ---
    df_apt['지역_단축'] = df_apt['시도'].str[:2]
    # 결측치 0으로 변환 후 숫자형 변환
    cols_to_num = ['차량보유대수(전기차)', '전기차 충전시설 설치대수(지상)', '전기차 충전시설 설치대수(지하)']
    for col in cols_to_num:
        df_apt[col] = pd.to_numeric(df_apt[col], errors='coerce').fillna(0)
    
    df_apt['단지내_총충전기'] = df_apt['전기차 충전시설 설치대수(지상)'] + df_apt['전기차 충전시설 설치대수(지하)']
    df_apt_agg = df_apt.groupby('지역_단축').agg(
        단지_전기차수=('차량보유대수(전기차)', 'sum'),
        단지_충전기수=('단지내_총충전기', 'sum')
    ).reset_index()
    # 인프라 부족도 (충전기 1대당 전기차 수)
    df_apt_agg['단지충전기당_전기차수'] = np.where(df_apt_agg['단지_충전기수'] > 0, 
                                        (df_apt_agg['단지_전기차수'] / df_apt_agg['단지_충전기수']).round(2), 0)

    # --- 데이터 병합 (최종 통합본) ---
    df_merged = pd.merge(df_subsidy_agg, df_charger_agg, on='지역_단축', how='inner')
    df_merged = pd.merge(df_merged, df_apt_agg, on='지역_단축', how='inner')
    
    return df_merged

# 데이터 불러오기 (파일이 없으면 오류 방지 안내)
try:
    df = load_data()
except FileNotFoundError:
    st.error("데이터 파일을 찾을 수 없습니다. 3개의 CSV 파일이 app.py와 같은 폴더에 있는지 확인해주세요.")
    st.stop()

# 3. 탭 구성
tab1, tab2, tab3 = st.tabs([
    "📊 1. 등록대수 vs 충전소", 
    "⚠️ 2. 단지 내 충전 인프라 부족", 
    "💰 3. 보조금 신청률 Heatmap"
])

# ==========================================
# 탭 1: 지역별 전기차 등록대수 vs 충전소 수 (공용+전체)
# ==========================================
with tab1:
    st.subheader("지역별 전기차 수요 대비 충전 인프라 공급 현황")
    st.info("💡 **인사이트:** 서울·경기는 EV 수요 대비 충전소가 절대적으로 부족한 병목 현상이 뚜렷하게 나타납니다.")
    
    fig1 = go.Figure()
    
    # 막대: 출고(등록)대수
    fig1.add_trace(go.Bar(
        x=df['지역_단축'], y=df['출고대수'], name='전기차 출고(등록)대수', marker_color='cornflowerblue', yaxis='y1'
    ))
    # 선: 22년 기준 충전소 수
    fig1.add_trace(go.Scatter(
        x=df['지역_단축'], y=df['충전소_수'], name='충전소 수', mode='lines+markers',
        marker=dict(color='crimson', size=8), line=dict(width=3), yaxis='y2'
    ))
    
    fig1.update_layout(
        title="전기차 등록대수(막대) vs 지역별 충전소 수(선)",
        yaxis=dict(title='전기차 출고대수 (대)'),
        yaxis2=dict(title='충전소 수 (개소)', overlaying='y', side='right'),
        barmode='group', height=500
    )
    st.plotly_chart(fig1, use_container_width=True)

# ==========================================
# 탭 2: 지역별 단지 내 충전 인프라 부족
# ==========================================
with tab2:
    st.subheader("전기차 수요 대비 거주지(단지 내) 인프라는 얼마나 부족한가?")
    st.info("💡 **인사이트:** 수도권 과밀 현상 확인 가능. 수도권은 충전소 절대 수는 높지만, 전기차 증가 속도 대비 거주지 인프라 부족 현상이 나타납니다.")
    
    df_sorted = df.sort_values(by='단지충전기당_전기차수', ascending=False)
    
    fig2 = px.bar(
        df_sorted, x='지역_단축', y='단지충전기당_전기차수', color='단지충전기당_전기차수',
        color_continuous_scale='Reds', text_auto='.2f',
        title="아파트 단지 내 충전기 1대당 감당 전기차 수 (높을수록 인프라 부족)"
    )
    fig2.update_layout(height=500, yaxis_title="충전기당 전기차 수 (대)")
    st.plotly_chart(fig2, use_container_width=True)

# ==========================================
# 탭 3: 지역별 보조금 신청률 Heatmap
# ==========================================
with tab3:
    st.subheader("보조금 정책이 EV 확산에 미친 영향")
    st.info("💡 **인사이트:** 보조금 정책은 EV 확산에 큰 영향을 미쳤으나, 특정 지역(예: 신청률 100% 초과 지역)에서는 예산 조기 소진으로 확산에 제동이 걸립니다.")
    
    # Heatmap용 데이터 가공 (1행 매트릭스)
    heatmap_data = df[['지역_단축', '보조금_신청률']].set_index('지역_단축').T
    
    fig3 = px.imshow(
        heatmap_data, text_auto='.1f', color_continuous_scale='YlGnBu',
        title="지역별 보조금 신청률 (%) - 100% 초과시 예산 부족"
    )
    fig3.update_layout(height=300)
    st.plotly_chart(fig3, use_container_width=True)

    # 최종 병합 데이터 확인 창
    with st.expander("원본 가공 데이터 확인"):
        st.dataframe(df)
