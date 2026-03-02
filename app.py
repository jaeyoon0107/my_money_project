import streamlit as st
import pandas as pd
import urllib.request
import json
import time
import hmac
import hashlib
import base64
import requests
import plotly.express as px
import google.generativeai as genai
from supabase import create_client, Client

# --- [설정] 네이버 API 키 ---
NAVER_CLIENT_ID = "8cMXAxkdT090FVNCY9lu"
NAVER_CLIENT_SECRET = "JwD6n1jzex"
AD_CUSTOMER_ID = "100000000ebfbbc782df4a09a9ae79e0949828cc3731836005e15417df664a6d13cda8d93"
AD_ACCESS_LICENSE = "AQAAAADr+7x4LfSgmprnnglJgozDtuVprvLLhd9ukB7ITu7jVg=="
AD_SECRET_KEY = "발급받은_비밀키를_여기에_넣으세요" # 본인 키로 변경!

# 🚀 [설정] Gemini AI API (제공해주신 키 하드코딩)
# 주의: GitHub 업로드 전에는 반드시 st.secrets로 숨겨야 합니다!
genai.configure(api_key="AIzaSyD1lGpxyB0bsx_Y-qsj2lYlyHEOrK6oHOI")
model = genai.GenerativeModel('gemini-2.5-flash')

# 🚀 Supabase DB 연결
@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase: Client = init_connection()

# --- 페이지 기본 설정 ---
st.set_page_config(page_title="MoneyBot Pro | Intelligence", page_icon="⬡", layout="wide")

# --- 🎨 오리지널 프리미엄 CSS ---
st.markdown("""
    <style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
    html, body, [class*="css"] { font-family: 'Pretendard', sans-serif; }
    .stApp { background-color: #f4f5f7; color: #111827; }
    #MainMenu, header, footer {visibility: hidden;}
    .brand-logo { font-size: 32px; font-weight: 800; color: #111827; letter-spacing: -0.03em; display: flex; align-items: center; gap: 8px;}
    .brand-logo span { color: #4f46e5; }
    .login-wrapper { display: flex; justify-content: center; align-items: center; height: 85vh; }
    .login-box {
        background: rgba(255, 255, 255, 0.8); backdrop-filter: blur(24px); padding: 48px; border-radius: 24px;
        box-shadow: 0 10px 40px rgba(0, 0, 0, 0.05); border: 1px solid rgba(255, 255, 255, 0.6); width: 440px; text-align: center;
    }
    .login-subtitle { font-size: 15px; color: #6b7280; margin-bottom: 24px; margin-top: 8px; font-weight: 500; }
    .stTextInput>div>div>input { background-color: #f9fafb !important; border: 1px solid #e5e7eb !important; border-radius: 12px !important; padding: 14px !important; font-size: 15px; }
    .stButton>button { background-color: #111827 !important; color: white !important; border: none; font-weight: 600; border-radius: 12px; height: 48px; width: 100%; }
    .stButton>button:hover { background-color: #4f46e5 !important; transform: translateY(-1px); }
    .glass-card { background: rgba(255, 255, 255, 0.85); backdrop-filter: blur(20px); padding: 28px; border-radius: 20px; border: 1px solid rgba(255, 255, 255, 0.8); }
    .insight-section { background-color: #ffffff; border-radius: 16px; padding: 24px; border-left: 6px solid #4f46e5; margin: 24px 0; line-height: 1.6;}
    
    .trend-tag {
        display: inline-block; padding: 6px 14px; margin: 4px; background: #eef2ff; 
        color: #4f46e5; border-radius: 20px; font-weight: 600; font-size: 14px; border: 1px solid #c7d2fe;
    }
    </style>
    """, unsafe_allow_html=True)

# --- API 연동 로직 ---
def generate_signature(timestamp, method, uri, secret_key):
    message = f"{timestamp}.{method}.{uri}"
    hash = hmac.new(secret_key.encode('utf-8'), message.encode('utf-8'), hashlib.sha256)
    return base64.b64encode(hash.digest()).decode('utf-8')

@st.cache_data(ttl=600)
def get_real_metrics(keyword):
    timestamp = str(int(time.time() * 1000))
    uri = "/keywordstool"
    signature = generate_signature(timestamp, "GET", uri, AD_SECRET_KEY)
    headers = {"X-Timestamp": timestamp, "X-API-KEY": AD_ACCESS_LICENSE, "X-Customer": AD_CUSTOMER_ID, "X-Signature": signature}
    try:
        res = requests.get(f"https://api.naver.com{uri}", params={"hintKeywords": keyword, "showDetail": "1"}, headers=headers)
        data = res.json().get('keywordList', [{}])[0]
        pc = 5 if data.get('monthlyPcQcCnt') == '< 10' else int(data.get('monthlyPcQcCnt', 10))
        mo = 5 if data.get('monthlyMobileQcCnt') == '< 10' else int(data.get('monthlyMobileQcCnt', 10))
        vol = pc + mo
    except: vol = 100
    
    encText = urllib.parse.quote(keyword)
    req = urllib.request.Request(f"https://openapi.naver.com/v1/search/shop.json?query={encText}&display=1")
    req.add_header("X-Naver-Client-Id", NAVER_CLIENT_ID)
    req.add_header("X-Naver-Client-Secret", NAVER_CLIENT_SECRET)
    try:
        cnt = json.loads(urllib.request.urlopen(req).read().decode('utf-8')).get('total', 0)
    except: cnt = 0
    return vol, cnt

# 🚀 AI 브리핑 생성 함수
def get_ai_briefing(df):
    summary = df[['키워드', '검색량(수요)', '상품수(공급)', '경쟁지수', '시장성']].to_string()
    prompt = f"""
    당신은 이커머스 전문 데이터 애널리스트입니다. 아래의 시장 데이터 분석 결과를 보고 
    가장 유망한 소싱 아이템 1개를 선정하여 그 이유를 설명하고, 
    어떤 타겟에게 어떻게 팔면 좋을지 마케팅 전략을 전문가답고 간결하게 한국어로 브리핑해주세요. 
    마크다운(볼드체 등)을 활용해 가독성 좋게 작성해주세요.
    
    [분석 데이터]
    {summary}
    """
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"AI 브리핑을 생성하는 중에 오류가 발생했습니다: {e}"

# --- 세션 관리 ---
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if 'user_id' not in st.session_state: st.session_state['user_id'] = None

# --- 1. 인증 화면 ---
if not st.session_state['logged_in']:
    st.markdown('<div class="login-wrapper"><div class="login-box">', unsafe_allow_html=True)
    st.markdown('<div class="brand-logo" style="justify-content: center;">⬡ MoneyBot <span>Pro</span></div>', unsafe_allow_html=True)
    
    mode = st.radio("Access Mode", ["Sign In", "Sign Up"], horizontal=True, label_visibility="collapsed")
    
    if mode == "Sign In":
        st.markdown('<div class="login-subtitle">Intelligence Dashboard Login</div>', unsafe_allow_html=True)
        with st.form("login_form"):
            u_id = st.text_input("아이디", label_visibility="collapsed", placeholder="사용자 ID")
            u_pw = st.text_input("비밀번호", type="password", label_visibility="collapsed", placeholder="비밀번호")
            if st.form_submit_button("접속하기"):
                res = supabase.table("users").select("*").eq("username", u_id).eq("password", u_pw).execute()
                if len(res.data) > 0:
                    st.session_state['logged_in'] = True
                    st.session_state['user_id'] = u_id
                    st.rerun()
                else: st.error("계정 정보가 일치하지 않습니다.")
    else:
        st.markdown('<div class="login-subtitle">새로운 비즈니스 계정 생성</div>', unsafe_allow_html=True)
        with st.form("signup_form"):
            new_id = st.text_input("아이디 설정", label_visibility="collapsed", placeholder="새로운 아이디 (4자 이상)")
            new_pw = st.text_input("비밀번호 설정", type="password", label_visibility="collapsed", placeholder="비밀번호")
            confirm_pw = st.text_input("비밀번호 확인", type="password", label_visibility="collapsed", placeholder="비밀번호 재입력")
            if st.form_submit_button("가입 완료"):
                if new_pw != confirm_pw: st.warning("비밀번호가 일치하지 않습니다.")
                elif len(new_id) < 4: st.warning("아이디가 너무 짧습니다.")
                else:
                    check = supabase.table("users").select("*").eq("username", new_id).execute()
                    if len(check.data) > 0: st.error("이미 사용 중인 아이디입니다.")
                    else:
                        supabase.table("users").insert({"username": new_id, "password": new_pw}).execute()
                        st.success("가입되었습니다! 로그인 탭으로 이동하세요.")
    st.markdown('</div></div>', unsafe_allow_html=True)

# --- 2. 메인 대시보드 ---
else:
    with st.sidebar:
        st.markdown(f"<h3 style='color:#111827; font-weight:700;'>📂 {st.session_state['user_id']}님의 기록</h3>", unsafe_allow_html=True)
        st.write("최근 탐색한 소싱 아이템")
        try:
            history_res = supabase.table("search_history").select("keyword").eq("username", st.session_state['user_id']).order("created_at", desc=True).limit(15).execute()
            if len(history_res.data) > 0:
                seen = set()
                unique_history = []
                for row in history_res.data:
                    kw = row['keyword']
                    if kw not in seen:
                        seen.add(kw)
                        unique_history.append(kw)
                
                for kw in unique_history[:8]:
                    st.markdown(f"<div style='padding: 10px; background: #f9fafb; border-radius: 8px; border: 1px solid #e5e7eb; margin-bottom: 6px; font-size: 14px;'>⏱️ {kw}</div>", unsafe_allow_html=True)
            else:
                st.info("검색 기록이 없습니다.")
        except Exception as e:
            st.error("기록을 불러올 수 없습니다.")
            
        st.write("---")
        if st.button("로그아웃 🔒"):
            st.session_state['logged_in'] = False
            st.session_state['user_id'] = None
            st.rerun()

    col_nav1, col_nav2 = st.columns([8, 2])
    with col_nav1:
        st.markdown("<div class='brand-logo'>⬡ MoneyBot <span>Pro</span></div>", unsafe_allow_html=True)
        st.markdown("<p style='color: #6b7280; font-size: 15px; margin-top: 5px;'>데이터 기반 셀링 & AI 소싱 엔진</p>", unsafe_allow_html=True)
    with col_nav2:
        st.markdown("<div style='font-size:13px; font-weight:700; color:#6b7280; margin-bottom:4px;'>🔥 실시간 셀러 트렌드 TOP 5</div>", unsafe_allow_html=True)
        try:
            trend_res = supabase.table("search_history").select("keyword").order("created_at", desc=True).limit(100).execute()
            if len(trend_res.data) > 0:
                trend_df = pd.DataFrame(trend_res.data)
                top_5_keywords = trend_df['keyword'].value_counts().head(5).index.tolist()
                tags_html = "".join([f"<span class='trend-tag'>{i+1}. {kw}</span>" for i, kw in enumerate(top_5_keywords)])
                st.markdown(f"<div>{tags_html}</div>", unsafe_allow_html=True)
        except:
            st.write("트렌드 집계 중...")
            
    st.write("---")

    input_text = st.text_area("분석 및 소싱할 키워드 입력", "휴대폰 알코올 솜\n무소음 탁자 선풍기\n아이폰 케이스\n캠핑의자", height=120)

    if st.button("시장 분석 및 AI 인텔리전스 가동"):
        keywords = [k.strip() for k in input_text.split('\n') if k.strip()]
        if keywords:
            results = []
            db_records = []
            progress_bar = st.progress(0)
            
            for i, k in enumerate(keywords):
                vol, cnt = get_real_metrics(k)
                ratio = round(cnt / vol if vol > 0 else 0, 2)
                status = "💎 블루오션" if ratio < 10 else "✅ 진입가능" if ratio < 100 else "❌ 포화상태"
                
                db_records.append({"username": st.session_state['user_id'], "keyword": k, "search_count": vol, "product_count": cnt, "competition_idx": float(ratio)})
                
                encoded_k = urllib.parse.quote(k)
                domeggook_link = f"https://domeggook.com/main/item/item_list.php?sfc=dt&sf=ttl&sw={encoded_k}"
                naver_link = f"https://search.shopping.naver.com/search/all?query={encoded_k}"
                
                results.append({"키워드": k, "검색량(수요)": vol, "상품수(공급)": cnt, "경쟁지수": ratio, "시장성": status, "도매꾹 링크": domeggook_link, "네이버 링크": naver_link})
                progress_bar.progress((i + 1) / len(keywords))
                time.sleep(0.05) 
            
            progress_bar.empty()
            
            if db_records:
                try: supabase.table("search_history").insert(db_records).execute()
                except: pass
            
            df = pd.DataFrame(results).sort_values(by="경쟁지수")
            best_keyword = df.iloc[0]['키워드']
            opp_count = len(df[df["시장성"]=="💎 블루오션"])

            st.write("")
            c1, c2, c3 = st.columns(3)
            c1.markdown(f'<div class="glass-card"><span class="card-label">분석된 아이템</span><span class="card-value">{len(df)}개</span></div>', unsafe_allow_html=True)
            c2.markdown(f'<div class="glass-card"><span class="card-label">발견된 블루오션</span><span class="card-value card-highlight">{opp_count}건</span></div>', unsafe_allow_html=True)
            c3.markdown(f'<div class="glass-card"><span class="card-label">1순위 추천 소싱</span><span class="card-value" style="font-size:30px; padding-top:6px;">{best_keyword}</span></div>', unsafe_allow_html=True)

            # 🚀 AI 브리핑 출력
            with st.spinner("🤖 AI가 시장 데이터를 정밀 분석 중입니다..."):
                briefing = get_ai_briefing(df)
                
            st.markdown(f"""
            <div class="insight-section">
                <div style="font-weight: 800; font-size: 18px; margin-bottom: 12px; color: #4f46e5;">🤖 MoneyBot AI 마켓 리포트</div>
                {briefing}
            </div>
            """, unsafe_allow_html=True)

            col1, col2 = st.columns(2)
            color_map = {"💎 블루오션": "#4f46e5", "✅ 진입가능": "#10b981", "❌ 포화상태": "#ef4444"}

            with col1:
                st.markdown("<h3 style='font-size:18px; color:#111827;'>키워드별 경쟁 강도</h3>", unsafe_allow_html=True)
                fig_bar = px.bar(df, x="키워드", y="경쟁지수", color="시장성", color_discrete_map=color_map, log_y=True)
                fig_bar.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", margin=dict(l=0, r=0, t=10, b=0), showlegend=False)
                st.plotly_chart(fig_bar, use_container_width=True, key="bar_chart")

            with col2:
                st.markdown("<h3 style='font-size:18px; color:#111827;'>수요 대비 공급 현황</h3>", unsafe_allow_html=True)
                fig_scatter = px.scatter(df, x="상품수(공급)", y="경쟁지수", color="시장성", size="검색량(수요)", size_max=50, color_discrete_map=color_map, hover_name="키워드", log_x=True, log_y=True)
                fig_scatter.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", margin=dict(l=0, r=0, t=10, b=0), showlegend=False)
                st.plotly_chart(fig_scatter, use_container_width=True, key="scatter_chart")

            st.write("")
            st.markdown("<h3 style='font-size:18px; color:#111827;'>원시 데이터 및 소싱 링크</h3>", unsafe_allow_html=True)
            st.dataframe(df, use_container_width=True)
            
            st.write("---")
            csv_data = df.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                label="📥 분석 결과 엑셀(CSV)로 다운로드",
                data=csv_data,
                file_name=f"moneybot_sourcing_{int(time.time())}.csv",
                mime="text/csv"
            )
