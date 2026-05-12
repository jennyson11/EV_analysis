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
    layout="wide"
)

# ==========================================
# 2. 데이터베이스(SQLite) 연동 및 초기화
# ==========================================
DB_PATH = "전기차 분석.db"

def init_db():
    if not os.path.exists('database'):
        os.makedirs('database')
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS integrated_ev_data (
            sido TEXT,
            sigungu TEXT,
            ev_count INTEGER,
            subsidy_notice INTEGER,
            subsidy_applied INTEGER,
            station_count INTEGER
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# ==========================================
# 3. CSV 안전 로딩 함수 (인코딩 에러 방지)
# ==========================================
def load_csv_safely(file):
    """한글 인코딩(CP949)과 UTF-8을 모두 지원하는 안전한 파일 읽기 함수입니다."""
    try:
        # 먼저 일반적인 utf-8로 시도
        return pd.read_csv(file, encoding='utf-8')
    except UnicodeDecodeError:
        # 실패하면 파일 포인터를 처음으로 되돌리고 cp949(한국 공공데이터 표준)로 재시도
        file.seek(0)
        return pd.read_csv(file, encoding='cp949')

# ==========================================
# 4. 사이드바 - CSV 파일 업로드
# ==========================================
st.sidebar.header("📁 데이터 업로드")
st.sidebar.markdown("공공데이터 CSV 파일을 업로드해주세요.")

file_ev = st.sidebar.file_uploader("1. 전기차 등록 현황 (CSV)", type=['csv'])
file_station = st.sidebar.file_uploader("2. 충전소 현황 (CSV)", type=['csv'])

if file_ev and file_station:
    try:
        # 안전하게 파일 읽어오기
        df_ev = load_csv_safely(file_ev)
        df_station = load_csv_safely(file_station)
        
        # [중요] 컬럼명에 섞인 앞뒤 공백을 제거 (KeyError 방지)
        df_ev.columns = df_ev.columns.str.strip()
        df_station.columns = df_station.columns.str.strip()
        
        # 컬럼명 통일
        df_ev.rename(columns={'시도': 'sido', '시군구': 'sigungu', '전기차등록대수': 'ev_count', 
                              '보조금공고대수': 'subsidy_notice', '보조금신청대수': 'subsidy_applied'}, inplace=True)
        df_station.rename(columns={'시도': 'sido', '시군구': 'sigungu', '충전소수': 'station_count'}, inplace=True)

        # 필수 컬럼 존재 여부 체크
        if 'sido' not in df_ev.columns or 'sigungu' not in df_ev.columns:
            st.sidebar.error("❌ 1번 파일에 '시도', '시군구' 컬럼이 없습니다. 원본을 확인해주세요.")
        elif 'sido' not in df_station.columns or 'sigungu' not in df_station.columns:
            st.sidebar.error("❌ 2번 파일에 '시도', '시군구' 컬럼이 없습니다. 원본을 확인해주세요.")
        else:
            # 병합 전 데이터 공백 제거 및 문자열 변환 (JOIN 실패 방지)
            df_ev['sido'] = df_ev['sido'].astype(str).str.strip()
            df_ev['sigungu'] = df_ev['sigungu'].astype(str).str.strip()
            df_station['sido'] = df_station['sido'].astype(str).str.strip()
            df_station['sigungu'] = df_station['sigungu'].astype(str).str.strip()

            # 데이터 병합
            df_merged = pd.merge(df_ev, df_station, on=['sido', 'sigungu'], how='left')
            
            # 결측치 처리
            df_merged = df_merged.fillna(0)

            # SQLite 저장
            conn = sqlite3.connect(DB_PATH)
            df_merged.to_sql('integrated_ev_data', conn, if_exists='replace', index=False)
            conn.close()
            
            st.sidebar.success("데이터 업로드 및 DB 저장 완료! ✅")
            
    except Exception as e:
        st.sidebar.error(f"데이터 처리 중 오류 발생: {e}")

# ==========================================
# 5. DB에서 데이터 불러오기 및 파생변수 생성
# ==========================================
df = pd.DataFrame()
try:
    if os.path.exists(DB_PATH):
        conn = sqlite3.connect(DB_PATH)
        # 테이블이 존재하는지 확인 후 조회
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='integrated_ev_data'")
        if cursor.fetchone():
            df = pd.read_sql_query("SELECT * FROM integrated_ev_data", conn)
        conn.close()
        
    if not df.empty:
        # [중요] 0으로 나누기(ZeroDivisionError) 방지 로직
        safe_station_count = df['station_count'].apply(lambda x: x if x > 0 else 1)
        safe_subsidy_notice = df['subsidy_notice'].apply(lambda x: x if x > 0 else 1)
        
        df['density'] = (df['ev_count'] / safe_station_count).round(2)
        df['subsidy_rate'] = ((df['subsidy_applied'] / safe_subsidy_notice) * 100).round(2)
        
        # 시도 단위 통합 데이터 만들기 (문자열 컬럼이 섞여 에러가 나지 않도록 numeric_only=True 추가)
        df_sido = df.groupby('sido').sum(numeric_only=True).reset_index()
        
        safe_sido_station = df_sido['station_count'].apply(lambda x: x if x > 0 else 1)
        safe_sido_notice = df_sido['subsidy_notice'].apply(lambda x: x if x > 0 else 1)
        
        df_sido['density'] = (df_sido['ev_count'] / safe_sido_station).round(2)
        df_sido['subsidy_rate'] = ((df_sido['subsidy_applied'] / safe_sido_notice) * 100).round(2)

except Exception as e:
    st.error(f"DB 데이터를 불러오는 중 오류가 발생했습니다: {e}")

# ==========================================
# 6. 메인 화면 UI 구성
# ==========================================
st.title("⚡ 지역별 전기차 충전 인프라 적정성 분석 대시보드")
st.markdown("공공데이터를 기반으로 지역별 전기차 보급 확산에 따른 **충전 인프라의 과밀도 및 보조금 정책의 효과**를 분석합니다.")

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 데이터 개요", "⚖️ 수요 vs 공급", "🚨 과밀도 분석", "💰 보조금 분석", "💡 인사이트 요약"
])

if df.empty:
    st.info("👈 왼쪽 사이드바에서 2개의 CSV 데이터를 먼저 업로드해주세요.")
else:
    # ----------------------------------------
    # 탭 1: 데이터 개요
    # ----------------------------------------
    with tab1:
        st.subheader("📌 핵심 지표 (KPI)")
        total_ev = int(df['ev_count'].sum())
        total_station = int(df['station_count'].sum())
        avg_density = round(total_ev / total_station if total_station > 0 else 0, 2)
        
        col1, col2, col3 = st.columns(3)
        col1.metric("전국 총 전기차 등록대수", f"{total_ev:,} 대")
        col2.metric("전국 총 충전소 수", f"{total_station:,} 개소")
        col3.metric("전국 평균 과밀도", f"{avg_density} 대/개소", delta="높을수록 혼잡", delta_color="inverse")
        
        st.divider()
        st.subheader("📋 전체 데이터 미리보기")
        st.dataframe(df, use_container_width=True)
        
        csv = df.to_csv(index=False).encode('utf-8-sig') # 한글 깨짐 방지 utf-8-sig
        st.download_button("📥 분석 데이터 결과 다운로드 (CSV)", data=csv, file_name="ev_analysis_result.csv", mime="text/csv")

    # ----------------------------------------
    # 탭 2: 수요 vs 공급 분석
    # ----------------------------------------
    with tab2:
        st.subheader("⚖️ 지역별 전기차 수요(등록대수) 대비 공급(충전소) 현황")
        fig = go.Figure()
        fig.add_trace(go.Bar(x=df_sido['sido'], y=df_sido['ev_count'], name='전기차 등록대수', marker_color='#1f77b4'))
        fig.add_trace(go.Scatter(x=df_sido['sido'], y=df_sido['station_count'], name='충전소 수', mode='lines+markers', marker_color='#ff7f0e', yaxis='y2'))
        
        fig.update_layout(
            title='시도별 전기차 등록대수 및 충전소 수 비교',
            yaxis=dict(title='전기차 대수'),
            yaxis2=dict(title='충전소 수', overlaying='y', side='right'),
            barmode='group',
            legend=dict(x=0.01, y=0.99)
        )
        st.plotly_chart(fig, use_container_width=True)

    # ----------------------------------------
    # 탭 3: 과밀도 분석
    # ----------------------------------------
    with tab3:
        st.subheader("🚨 충전 인프라 과밀도 분석")
        st.markdown("**과밀도 = 전기차 등록대수 ÷ 충전소 수**")
        df_density_sorted = df_sido.sort_values('density', ascending=False)
        
        fig_density = px.bar(
            df_density_sorted, x='sido', y='density', color='density', color_continuous_scale='Reds',
            labels={'sido': '시도명', 'density': '충전소 1개당 감당 차량 수'}
        )
        st.plotly_chart(fig_density, use_container_width=True)

    # ----------------------------------------
    # 탭 4: 보조금 분석
    # ----------------------------------------
    with tab4:
        st.subheader("💰 지역별 전기차 보조금 신청률 분석")
        
        # [중요 수정] Treemap은 값이 0이거나 음수이면 에러가 납니다. 0 초과인 데이터만 사용합니다.
        df_tree = df[df['subsidy_applied'] > 0].copy()
        
        if df_tree.empty:
            st.warning("보조금 신청 데이터가 없거나 모두 0입니다.")
        else:
            # 버전 충돌 방지를 위해 px.Constant 대신 '국가'라는 최상위 컬럼을 직접 만들어줍니다.
            df_tree['국가'] = '대한민국'
            fig_subsidy = px.treemap(
                df_tree,
                path=['국가', 'sido', 'sigungu'],
                values='subsidy_applied',
                color='subsidy_rate',
                color_continuous_scale='Blues',
                labels={'subsidy_rate': '보조금 신청률(%)'}
            )
            fig_subsidy.update_traces(root_color="lightgrey")
            st.plotly_chart(fig_subsidy, use_container_width=True)

    # ----------------------------------------
    # 탭 5: 인사이트 요약
    # ----------------------------------------
    with tab5:
        st.subheader("💡 데이터 분석 인사이트")
        st.info("데이터 분석 결과를 바탕으로 도출된 핵심 인사이트입니다.")
        st.markdown("""
        ### 1. 수요 vs 공급 불균형
        * **현상:** 특정 지역(특히 수도권)은 전기차 등록대수가 매우 높으나 충전소 공급이 따라가지 못합니다.
        
        ### 2. 충전 인프라 과밀도 심화
        * **현상:** 과밀도 붉은색 상위 지역은 1개 충전소가 감당해야 할 전기차 대수가 압도적으로 높습니다. 충전 대기 시간이 크게 증가할 위험이 있습니다.
        
        ### 3. 보조금 정책의 효과
        * **현상:** 보조금 분석 맵에서 짙은 파란색(높은 신청률)을 띠는 지역은 실제 전기차 전환 비율도 높은 양상을 띱니다.
        """)
