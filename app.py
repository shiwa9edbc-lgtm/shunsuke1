import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from dateutil.parser import parse
import os
import re
import json
from dotenv import load_dotenv
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import time

# 環境変数を読み込み
load_dotenv()

# クォータ使用量の永続化ファイルパス
QUOTA_FILE = "quota_usage.json"

# クォータ使用量の読み込み
def load_quota_usage():
    try:
        if os.path.exists(QUOTA_FILE):
            with open(QUOTA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                today = datetime.now().strftime('%Y-%m-%d')
                # 今日のデータがあれば使用量を復元、なければリセット
                if data.get('date') == today:
                    return data.get('quota_used', 0)
                else:
                    # 日付が変わっていればリセット
                    return 0
        return 0
    except Exception:
        return 0

# クォータ使用量の保存
def save_quota_usage(quota_used):
    try:
        today = datetime.now().strftime('%Y-%m-%d')
        data = {
            'date': today,
            'quota_used': quota_used
        }
        with open(QUOTA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass  # 保存に失敗しても継続

# セッション状態の初期化
def initialize_session_state():
    if 'quota_used' not in st.session_state:
        st.session_state.quota_used = load_quota_usage()
    if 'quota_limit' not in st.session_state:
        st.session_state.quota_limit = 9000
    if 'last_search_time' not in st.session_state:
        st.session_state.last_search_time = None
    if 'search_results' not in st.session_state:
        st.session_state.search_results = None
    if 'filtered_channels' not in st.session_state:
        st.session_state.filtered_channels = []

# 最初に初期化を実行
initialize_session_state()

# StreamlitのCSSを直接注入
def inject_css():
    st.markdown("""
    <style>
    /* サイドバーの×ボタンのみをターゲット - より具体的なセレクタ */
    [data-testid="stSidebar"] button[kind="header"],
    [data-testid="stSidebar"] button[aria-label*="Close"],
    [data-testid="stSidebar"] .css-1rs6os {
        position: relative !important;
        background: transparent !important;
    }
    
    /* サイドバーの×ボタンのSVGのみ非表示 */
    [data-testid="stSidebar"] button[kind="header"] svg,
    [data-testid="stSidebar"] button[aria-label*="Close"] svg,
    [data-testid="stSidebar"] .css-1rs6os svg {
        opacity: 0 !important;
        visibility: hidden !important;
    }
    
    /* サイドバーの×ボタンにのみ疑似要素で×マークを作成 */
    [data-testid="stSidebar"] button[kind="header"]::before,
    [data-testid="stSidebar"] button[aria-label*="Close"]::before,
    [data-testid="stSidebar"] .css-1rs6os::before {
        content: "×" !important;
        position: absolute !important;
        top: 50% !important;
        left: 50% !important;
        transform: translate(-50%, -50%) !important;
        color: black !important;
        font-size: 18px !important;
        font-weight: 900 !important;
        z-index: 1000 !important;
    }
    
    /* メインエリアの検索実行ボタンのスタイルを確保 */
    .main button[kind="primary"],
    button[data-testid="baseButton-primary"] {
        background-color: #ff4b4b !important;
        color: white !important;
        border: none !important;
        border-radius: 0.5rem !important;
        position: relative !important;
    }
    
    /* 検索実行ボタンの疑似要素を無効化 */
    .main button[kind="primary"]::before,
    button[data-testid="baseButton-primary"]::before {
        display: none !important;
    }
    </style>
    """, unsafe_allow_html=True)

# ISO 8601 duration を時間文字列に変換する関数
def parse_duration(duration):
    """
    YouTube API の ISO 8601 duration (PT4M13S) を時間文字列 (4:13) に変換
    """
    import re
    
    if not duration:
        return "不明"
    
    # PT4M13S のような形式をパース
    pattern = r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?'
    match = re.match(pattern, duration)
    
    if not match:
        return "不明"
    
    hours, minutes, seconds = match.groups()
    hours = int(hours) if hours else 0
    minutes = int(minutes) if minutes else 0
    seconds = int(seconds) if seconds else 0
    
    if hours > 0:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    else:
        return f"{minutes}:{seconds:02d}"

# ページ設定
st.set_page_config(
    page_title="YouTube動画分析アプリ",
    page_icon="📺",
    layout="wide",
    initial_sidebar_state="expanded"
)

# カスタムCSS
st.markdown("""
<style>
    .main-title {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f1f1f;
        text-align: center;
        margin-bottom: 0.2rem;
    }
    .subtitle-red {
        font-size: 1.2rem;
        color: #ff4b4b;
        text-align: center;
        margin-bottom: 0.2rem;
        font-weight: 600;
    }
    .subtitle-gray {
        font-size: 1rem;
        color: #666666;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-container {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #ff4b4b;
    }
    .warning-box {
        background-color: #fff3cd;
        border: 1px solid #ffeaa7;
        border-radius: 0.5rem;
        padding: 1rem;
        margin: 1rem 0;
    }
    .danger-box {
        background-color: #f8d7da;
        border: 1px solid #f5c6cb;
        border-radius: 0.5rem;
        padding: 1rem;
        margin: 1rem 0;
    }
    /* サイドバーの背景色変更 - より広範なセレクタを使用 */
    .css-1d391kg, 
    .css-17lntkn, 
    .css-1lcbmhc, 
    .css-1y4p8pa,
    [data-testid="stSidebar"] > div:first-child,
    section[data-testid="stSidebar"] > div {
        background-color: #1e3a8a !important;
    }
    
    /* サイドバーのテキストを白色に（入力フィールドと×ボタンは除外） */
    .css-1d391kg *:not(input):not(textarea):not(line),
    .css-17lntkn *:not(input):not(textarea):not(line),
    .css-1lcbmhc *:not(input):not(textarea):not(line),
    .css-1y4p8pa *:not(input):not(textarea):not(line),
    [data-testid="stSidebar"] *:not(input):not(textarea):not(line),
    section[data-testid="stSidebar"] *:not(input):not(textarea):not(line) {
        color: white !important;
    }
    
    /* サイドバーのヘッダー */
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3 {
        color: white !important;
    }
    
    /* 入力フィールドのラベル */
    [data-testid="stSidebar"] label {
        color: white !important;
    }
    
    /* スライダーのスタイル調整 */
    [data-testid="stSidebar"] .stSlider > div > div > div > div {
        color: white !important;
    }
    
    /* 入力フィールドのスタイル調整 */
    [data-testid="stSidebar"] input {
        background-color: white !important;
        color: black !important;
        border: 1px solid #ccc !important;
    }
    
    /* ヘルプアイコン（?マーク）のスタイル */
    [data-testid="stSidebar"] .css-1cpxqw2,
    [data-testid="stSidebar"] [data-testid="stTooltipIcon"],
    [data-testid="stSidebar"] .css-1wgd1hx,
    [data-testid="stSidebar"] .st-emotion-cache-1wgd1hx {
        color: white !important;
    }
    
    /* ヘルプアイコンのSVG - 円の枠線は白、中身は透明、?マークは白 */
    [data-testid="stSidebar"] svg circle {
        fill: none !important;
        stroke: white !important;
        stroke-width: 1.5 !important;
    }
    
    [data-testid="stSidebar"] svg path {
        fill: white !important;
    }
    
    /* サイドバーの×ボタンのみの全体的なスタイル */
    section[data-testid="stSidebar"] button[kind="header"],
    section[data-testid="stSidebar"] button[aria-label*="Close"],
    section[data-testid="stSidebar"] .css-1rs6os,
    section[data-testid="stSidebar"] [data-testid="baseButton-header"] {
        background-color: transparent !important;
        background: transparent !important;
        border: none !important;
    }
    
    /* ×ボタンのSVG - 全ての可能なセレクタを網羅 */
    section[data-testid="stSidebar"] svg,
    section[data-testid="stSidebar"] button svg,
    section[data-testid="stSidebar"] .css-1rs6os svg,
    section[data-testid="stSidebar"] [data-testid="baseButton-header"] svg,
    section[data-testid="stSidebar"] .st-emotion-cache-1rs6os svg {
        background-color: transparent !important;
        background: transparent !important;
    }
    
    /* ×ボタンを完全に非表示にして、CSS疑似要素で代替 */
    section[data-testid="stSidebar"] button[kind="header"],
    section[data-testid="stSidebar"] button[aria-label*="Close"],
    section[data-testid="stSidebar"] .css-1rs6os {
        position: relative !important;
        background: transparent !important;
        border: none !important;
        width: 24px !important;
        height: 24px !important;
    }
    
    /* 既存のSVGを非表示 */
    section[data-testid="stSidebar"] button[kind="header"] svg,
    section[data-testid="stSidebar"] button[aria-label*="Close"] svg,
    section[data-testid="stSidebar"] .css-1rs6os svg {
        display: none !important;
    }
    
    /* CSS疑似要素で×マークを作成 */
    section[data-testid="stSidebar"] button[kind="header"]::before,
    section[data-testid="stSidebar"] button[aria-label*="Close"]::before,
    section[data-testid="stSidebar"] .css-1rs6os::before {
        content: "✕" !important;
        position: absolute !important;
        top: 50% !important;
        left: 50% !important;
        transform: translate(-50%, -50%) !important;
        color: #000000 !important;
        font-size: 16px !important;
        font-weight: bold !important;
        line-height: 1 !important;
    }
    
    /* 代替として、CSSで線を描画 */
    section[data-testid="stSidebar"] button[kind="header"]::after,
    section[data-testid="stSidebar"] button[aria-label*="Close"]::after,
    section[data-testid="stSidebar"] .css-1rs6os::after {
        content: "" !important;
        position: absolute !important;
        top: 50% !important;
        left: 50% !important;
        width: 14px !important;
        height: 2px !important;
        background: #000000 !important;
        transform: translate(-50%, -50%) rotate(45deg) !important;
        border-radius: 1px !important;
    }
    
    section[data-testid="stSidebar"] button[kind="header"]::before,
    section[data-testid="stSidebar"] button[aria-label*="Close"]::before,
    section[data-testid="stSidebar"] .css-1rs6os::before {
        content: "" !important;
        position: absolute !important;
        top: 50% !important;
        left: 50% !important;
        width: 14px !important;
        height: 2px !important;  
        background: #000000 !important;
        transform: translate(-50%, -50%) rotate(-45deg) !important;
        border-radius: 1px !important;
    }
    
    /* メインエリアのボタンスタイルを保護 */
    .main button,
    .block-container button {
        position: static !important;
    }
    
    /* メインエリアのボタンの疑似要素を完全に無効化 */
    .main button::before,
    .main button::after,
    .block-container button::before,
    .block-container button::after {
        display: none !important;
        content: none !important;
    }
    
    /* primaryボタン（検索実行ボタン）の正常なスタイル */
    button[kind="primary"] {
        background-color: rgb(255, 75, 75) !important;
        color: white !important;
        border: 1px solid rgb(255, 75, 75) !important;
        border-radius: 0.5rem !important;
    }
    
    /* secondaryボタン（再生ボタン）の正常なスタイル */
    button[kind="secondary"] {
        background-color: white !important;
        color: rgb(49, 51, 63) !important;
        border: 1px solid rgb(230, 234, 241) !important;
        border-radius: 0.5rem !important;
    }
</style>
""", unsafe_allow_html=True)

# YouTube API v3クライアントを初期化
@st.cache_resource
def get_youtube_client():
    api_key = os.getenv('YOUTUBE_API_KEY')
    if not api_key:
        st.error("環境変数 'YOUTUBE_API_KEY' が設定されていません。")
        st.info("プロジェクトルートに .env ファイルを作成し、YOUTUBE_API_KEY=your_api_key を設定してください。")
        return None
    
    try:
        youtube = build('youtube', 'v3', developerKey=api_key)
        return youtube
    except Exception as e:
        st.error(f"YouTube API クライアントの初期化に失敗しました: {e}")
        return None

# 動画検索機能
def search_videos(query, published_after, japan_only=True, max_results=50):
    youtube = get_youtube_client()
    if not youtube:
        return None
    
    try:
        # 検索リクエスト（約100ユニット消費）
        # UTC形式でISO 8601タイムスタンプを作成
        published_after_utc = published_after.replace(tzinfo=None).isoformat() + 'Z'
        
        # 検索パラメータを設定
        search_params = {
            'q': query,
            'part': 'id,snippet',
            'maxResults': max_results,
            'order': 'date',
            'type': 'video',
            'publishedAfter': published_after_utc,
            'regionCode': 'JP'
        }
        
        # 日本チャンネル限定の場合、日本語の検索語を追加
        if japan_only:
            search_params['relevanceLanguage'] = 'ja'
            # 検索クエリに日本語キーワードを追加してより日本関連のコンテンツを取得
            search_params['q'] = f"{query} 日本"
        
        search_response = youtube.search().list(**search_params).execute()
        
        # 動画IDを収集
        video_ids = [item['id']['videoId'] for item in search_response['items']]
        
        if not video_ids:
            return pd.DataFrame()
        
        # 動画詳細情報を取得（約1ユニット/動画）
        videos_response = youtube.videos().list(
            part='statistics,snippet,contentDetails',
            id=','.join(video_ids)
        ).execute()
        
        # チャンネル情報を取得するためのチャンネルIDを収集
        channel_ids = list(set([item['snippet']['channelId'] for item in videos_response['items']]))
        
        # チャンネル詳細情報を取得（約1ユニット/チャンネル）
        channels_response = youtube.channels().list(
            part='statistics,snippet,localizations',
            id=','.join(channel_ids)
        ).execute()
        
        # チャンネル情報を辞書形式で整理
        channel_info = {}
        filtered_count = 0
        total_channels = len(channels_response['items'])
        
        for channel in channels_response['items']:
            # 日本チャンネル判定（国コード、言語、チャンネル名の日本語文字含有で判定）
            is_japanese_channel = True
            if japan_only:
                country = channel['snippet'].get('country', '')
                default_language = channel['snippet'].get('defaultLanguage', '')
                channel_title = channel['snippet']['title']
                
                # 日本語文字が含まれているかチェック
                has_japanese = bool(re.search(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FAF]', channel_title))
                
                # 日本チャンネル判定条件（より厳密に）
                is_japanese_channel = (
                    country == 'JP' or 
                    default_language == 'ja' or 
                    has_japanese
                )
                
                # 追加の判定：動画タイトルや説明文に日本語が含まれているかチェック
                if not is_japanese_channel:
                    # 対応する動画のタイトルをチェック
                    matching_videos = [v for v in videos_response['items'] if v['snippet']['channelId'] == channel['id']]
                    for video in matching_videos:
                        video_title = video['snippet']['title']
                        video_description = video['snippet'].get('description', '')
                        if (re.search(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FAF]', video_title) or 
                            re.search(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FAF]', video_description)):
                            is_japanese_channel = True
                            break
                
                if not is_japanese_channel:
                    filtered_count += 1
            
            if is_japanese_channel:
                channel_info[channel['id']] = {
                    'name': channel['snippet']['title'],
                    'subscriber_count': int(channel['statistics'].get('subscriberCount', 0)),
                    'country': country,
                    'language': default_language,
                    'has_japanese': has_japanese if japan_only else None
                }
            else:
                # デバッグ用：除外されたチャンネルの情報を記録
                if not hasattr(st.session_state, 'filtered_channels'):
                    st.session_state.filtered_channels = []
                st.session_state.filtered_channels.append({
                    'name': channel['snippet']['title'],
                    'country': country,
                    'language': default_language,
                    'has_japanese': has_japanese
                })
        
        # データフレーム作成（日本チャンネルのみフィルタリング）
        videos_data = []
        for video in videos_response['items']:
            channel_id = video['snippet']['channelId']
            # 日本チャンネル限定の場合、チャンネル情報があるもののみ追加
            if channel_id in channel_info:
                duration = video.get('contentDetails', {}).get('duration', '')
                videos_data.append({
                    '動画ID': video['id'],
                    'タイトル': video['snippet']['title'],
                    '視聴回数': int(video['statistics'].get('viewCount', 0)),
                    '投稿日時': parse(video['snippet']['publishedAt']).strftime('%Y-%m-%d %H:%M'),
                    '動画時間': parse_duration(duration),
                    'チャンネル名': channel_info[channel_id]['name'],
                    '登録者数': channel_info[channel_id]['subscriber_count']
                })
        
        # クォータ使用量を更新（概算）
        quota_used = 100 + len(video_ids) + len(channel_ids)
        st.session_state.quota_used += quota_used
        # 使用量を永続化
        save_quota_usage(st.session_state.quota_used)
        
        # デバッグ情報をセッション状態に保存
        st.session_state.debug_info = {
            'total_videos_found': len(search_response['items']),
            'total_channels': total_channels,
            'filtered_channels': filtered_count,
            'final_videos': len(videos_data)
        }
        
        return pd.DataFrame(videos_data)
        
    except HttpError as e:
        st.error(f"YouTube API エラー: {e}")
        return None
    except Exception as e:
        st.error(f"検索中にエラーが発生しました: {e}")
        return None

# メイン関数
def main():
    # セッション状態を最初に初期化
    initialize_session_state()
    
    # 追加のCSSを注入
    inject_css()
    
    # タイトル部分
    st.markdown('<div class="main-title">YouTube動画分析アプリ</div>', unsafe_allow_html=True)
    st.markdown('<div class="subtitle-red">2025_岩崎_年間目標②</div>', unsafe_allow_html=True)
    st.markdown('<div class="subtitle-gray">設定項目に一致する最新のYoutube動画を分析した結果を表示します</div>', unsafe_allow_html=True)
    
    # サイドバー設定
    st.sidebar.header("🔍 検索設定")
    
    # 検索クエリ入力
    search_query = st.sidebar.text_input(
        "検索キーワード",
        value="AIエージェント",
        help="検索したい動画のキーワードを入力してください"
    )
    
    # 投稿日の閾値スライダー
    days_back = st.sidebar.slider(
        "投稿日の範囲（日前まで）",
        min_value=1,
        max_value=365,
        value=30,
        help="今日から何日前までの動画を検索するか設定してください"
    )
    
    # 日本チャンネル限定オプション
    japan_only = st.sidebar.checkbox(
        "日本のチャンネルのみ",
        value=True,
        help="日本のチャンネルの動画のみを検索対象にします"
    )
    
    published_after = datetime.now() - timedelta(days=days_back)
    
    # 検索ボタン
    search_button = st.sidebar.button("🔍 検索実行", type="primary")
    
    # メインフレーム
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("📊 現在選択中のパラメータ")
        st.markdown(f"""
        <div class="metric-container">
            <strong>検索キーワード:</strong> {search_query}<br>
            <strong>投稿日範囲:</strong> {published_after.strftime('%Y-%m-%d')} 以降<br>
            <strong>日本チャンネル限定:</strong> {'はい' if japan_only else 'いいえ'}<br>
            <strong>最大表示件数:</strong> 50件
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.subheader("📈 API使用量")
        quota_percentage = (st.session_state.quota_used / st.session_state.quota_limit) * 100
        
        # プログレスバー
        st.progress(quota_percentage / 100)
        st.metric(
            "使用量 / 上限",
            f"{st.session_state.quota_used} / {st.session_state.quota_limit}",
            f"{quota_percentage:.1f}%"
        )
        
        # アラート表示
        if quota_percentage >= 100:
            st.markdown("""
            <div class="danger-box">
                ⚠️ <strong>クォータ上限に達しました</strong><br>
                API呼び出しが停止されています。
            </div>
            """, unsafe_allow_html=True)
        elif quota_percentage >= 90:
            st.markdown("""
            <div class="warning-box">
                ⚠️ <strong>クォータ使用量が90%を超えました</strong><br>
                残り使用量にご注意ください。
            </div>
            """, unsafe_allow_html=True)
        
        st.info("💡 検索1回あたり約100ユニット消費")
    
    # 検索実行
    if search_button:
        if st.session_state.quota_used >= st.session_state.quota_limit:
            st.error("❌ クォータ上限に達しているため、検索を実行できません。")
        else:
            with st.spinner("🔍 動画を検索中..."):
                # 前回の除外チャンネルリストをクリア
                st.session_state.filtered_channels = []
                results = search_videos(search_query, published_after, japan_only)
                st.session_state.search_results = results
                st.session_state.last_search_time = datetime.now()
    
    # 検索結果表示
    if st.session_state.search_results is not None:
        st.subheader("📋 検索結果")
        
        if len(st.session_state.search_results) > 0:
            st.write(f"**{len(st.session_state.search_results)}件** の動画が見つかりました（投稿日時が新しい順）")
            
            # デバッグ情報表示
            if hasattr(st.session_state, 'debug_info') and japan_only:
                debug_info = st.session_state.debug_info
                with st.expander("🔍 フィルタリング詳細情報"):
                    st.write(f"- **検索で見つかった動画数**: {debug_info['total_videos_found']}件")
                    st.write(f"- **ユニークチャンネル数**: {debug_info['total_channels']}チャンネル")
                    st.write(f"- **フィルタで除外されたチャンネル**: {debug_info['filtered_channels']}チャンネル")
                    st.write(f"- **最終表示動画数**: {debug_info['final_videos']}件")
                    
                    # 除外されたチャンネルの詳細
                    if hasattr(st.session_state, 'filtered_channels') and st.session_state.filtered_channels:
                        st.write("**除外されたチャンネルの例:**")
                        for i, ch in enumerate(st.session_state.filtered_channels[:5]):  # 最大5件表示
                            st.write(f"  {i+1}. {ch['name']} (国: {ch['country']}, 言語: {ch['language']}, 日本語: {ch['has_japanese']})")
            
            # データフレーム表示
            st.dataframe(
                st.session_state.search_results,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "視聴回数": st.column_config.NumberColumn(
                        "視聴回数",
                        format="%d 回"
                    ),
                    "登録者数": st.column_config.NumberColumn(
                        "登録者数",
                        format="%d 人"
                    )
                }
            )
        else:
            st.warning("検索条件に一致する動画が見つかりませんでした。")
        
        if st.session_state.last_search_time:
            st.caption(f"最終検索時刻: {st.session_state.last_search_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 動画再生セクション
    st.subheader("🎬 動画再生")
    
    video_id_input = st.text_input(
        "動画IDを入力",
        placeholder="例: dQw4w9WgXcQ",
        help="YouTubeの動画IDを入力してください"
    )
    
    play_button = st.button("▶️ 再生", type="secondary")
    
    if play_button and video_id_input:
        try:
            st.video(f"https://www.youtube.com/watch?v={video_id_input}")
        except Exception as e:
            st.error(f"動画の再生に失敗しました: {e}")
    
    # フッター
    st.markdown("---")
    st.markdown("""
    <div style="text-align: center; color: #666666; font-size: 0.9rem;">
        📺 YouTube Data API v3 を使用 | 日次クォータ上限: 9,000 ユニット<br>
        <br>
        <strong>©2025 岩崎俊介</strong>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()