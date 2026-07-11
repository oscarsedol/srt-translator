import streamlit as st
import google.generativeai as genai
import os
import pysrt
import time
import re
import zipfile
import io
from dotenv import load_dotenv

# --- 환경변수 및 API 설정 / 環境変数 및 API 設定 ---
load_dotenv()

# 🔒 [보안 기능] Secrets에서 아이디/비밀번호 가져오기
VALID_USERNAME = st.secrets.get("APP_USERNAME", os.getenv("APP_USERNAME", "owner"))
VALID_PASSWORD = st.secrets.get("APP_PASSWORD", os.getenv("APP_PASSWORD", "password123"))

# --- 로그인 UI 처리 / ログインUI処理 ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.set_page_config(page_title="🔒 로그인 / ログイン", page_icon="🔐", layout="centered")
    st.title("🔐 시스템 접근 제한 / アクセ스制限")
    st.subheader("이 앱은 허가된 사용자만 사용할 수 있습니다.")
    st.write("このアプリは許可されたユーザーのみ使用できます。")
    
    # 💡 1번 수정: 브라우저 자동완성(오토필) 지원을 위해 st.form 사용
    with st.form("login_form", clear_on_submit=False):
        login_user = st.text_input("Username / ID", key="login_user")
        login_pass = st.text_input("Password / パスワード", type="password", key="login_pass")
        
        # ⚠️ st.form_submit_button 오타 수정 완료!
        submit_login = st.form_submit_button("🔑 로그인 / ログイン", type="primary", use_container_width=True)
        
        if submit_login:
            if login_user == VALID_USERNAME and login_pass == VALID_PASSWORD:
                st.session_state.authenticated = True
                st.rerun()  # ⚠️ st.rerun() 오타 수정 완료!
            else:
                st.error("아이디 또는 비밀번호가 틀렸습니다. / IDまたはパスワードが間違っています。")
    st.stop()  # 로그인 성공 전까지는 아래 코드를 절대 실행하지 않고 멈춤

# --- 로그인 성공 시 아래의 본 프로그램 실행 ---

api_key = os.getenv("GEMINI_API_KEY") or st.secrets.get("GEMINI_API_KEY")
if api_key:
    genai.configure(api_key=api_key)
else:
    st.error("앗, .env 파일이나 Secrets에 GEMINI_API_KEY가 없어. 확인해줘, 주인.")

# --- 번역 가능 언어 목록 (30개 언어 가나다순 정렬) / 翻訳可能言語リスト ---
LANGUAGES = {
    "네덜란드어 / オランダ語": "Dutch",
    "노르웨이어 / ノルウェー語": "Norwegian",
    "덴마크어 / デンマーク語": "Danish",
    "독일어 / ドイツ語": "German",
    "러시아어 / ロシア語": "Russian",
    "말레이어 / マレー語": "Malay",
    "베트남어 / ベトナム語": "Vietnamese",
    "스웨덴어 / スウェーデン語": "Swedish",
    "스페인어 / スペイン語": "Spanish",
    "아랍어 / アラビア語": "Arabic",
    "영어 / 英語": "English",
    "우즈베크어 / ウズベク語": "Uzbek",
    "우크라이나어 / ウ크라이나語": "Ukrainian",
    "이탈리아어 / イタリア語": "Italian",
    "인도네시아어 / インドネシア語": "Indonesian",
    "일본어 / 日本語": "Japanese",
    "중국어(간체) / 中国語(簡体字)": "Simplified Chinese",
    "중국어(대만) / 中国語(台湾)": "Traditional Chinese (Taiwan)",
    "중국어(홍콩) / 中国語(香港)": "Traditional Chinese (Hong Kong)",
    "카자흐어 / カザフ語": "Kazakh",
    "태국어 / タイ語": "Thai",
    "튀르키예어 / トルコ語": "Turkish",
    "페르시아어 / ペルシア語": "Persian",
    "포르투갈어 / ポルトガル語": "Portuguese",
    "폴란드어 / ポーランド語": "Polish",
    "프랑스어 / フランス語": "French",
    "핀란드어 / フィンランド語": "Finnish",
    "필리핀어 / フィリピン語": "Filipino",
    "한국어 / 韓国語": "Korean",
    "힌디어 / ヒンディー語": "Hindi"
}

# --- 스트림릿 세션 상태 초기화 / セッション状態の初期화 ---
for lang in LANGUAGES.keys():
    key = f"chk_{lang}"
    if key not in st.session_state:
        # 💡 2번 수정: 한국어만 기본으로 체크되도록 변경 (나머지는 해제)
        st.session_state[key] = ("한국어" in lang)

if 'is_processing' not in st.session_state:
    st.session_state.is_processing = False
if 'results' not in st.session_state:
    st.session_state.results = {}
if 'video_title' not in st.session_state:
    st.session_state.video_title = ""
if 'show_balloons' not in st.session_state:
    st.session_state.show_balloons = False

# --- 콜백 함수 / コールバック関数 ---
def select_all():
    for lang in LANGUAGES.keys():
        st.session_state[f"chk_{lang}"] = True

def deselect_all():
    for lang in LANGUAGES.keys():
        st.session_state[f"chk_{lang}"] = False

def verify_timeline_final(original_srt, translated_srt_text):
    try:
        translated_srt = pysrt.from_string(translated_srt_text)
        if len(original_srt) != len(translated_srt):
            return False, "세그먼트 개수 불일치 / セグメント数の不一致"
        for orig, trans in zip(original_srt, translated_srt):
            if orig.start != trans.start or orig.end != trans.end:
                return False, f"타임라인 불일치 / タイムラインの不一致 (Index {orig.index})"
        return True, "무결성 완벽함 / 整合性完璧"
    except Exception as e:
        return False, f"SRT 파싱 에러 / SRTパースエラー: {e}"

# --- 번역 및 타임라인 강제 동기화 / 翻訳およびタイムライン同期 ---
def translate_and_verify(original_text, original_srt, target_lang, selected_model, progress_bar, status_text):
    model = genai.GenerativeModel(selected_model)
    
    # 💡 3번 수정: 원문의 느낌과 말투를 최대한 살리도록 프롬프트 정교화
    prompt_base = f"""
    You are an expert subtitle translator. Translate the following SRT file to {target_lang}.
    CRITICAL RULES:
    1. Keep the exact same number of subtitle blocks. The original has {len(original_srt)} blocks.
    2. DO NOT merge, combine, or split lines. Translate line by line.
    3. Output ONLY the raw SRT format. NO markdown tags like ```srt. Just start with '1'.
    4. ABSOLUTELY DO NOT output the original text. You MUST translate the content entirely into {target_lang}.
    5. Carefully preserve the original tone, nuance, style, and vibe of the speech (e.g., formal/informal politeness, slang, emotional expressions). Make it sound natural while respecting the original context.
    
    Original SRT:
    {original_text}
    """
    
    attempt = 1
    while attempt <= 3:
        if not st.session_state.is_processing:
            return None
            
        status_text.text(f"[{target_lang}] 번역 및 무결성 확보 중... / 翻訳および整合性確認中... ({attempt}/3)")
        progress_bar.progress(int(attempt * (100 / 3)))
        
        try:
            response = model.generate_content(prompt_base)
            translated_text = response.text.replace("```srt", "").replace("```", "").strip()
            
            try:
                translated_srt = pysrt.from_string(translated_text)
            except Exception:
                prompt_base += f"\n\nCorrection Request: Failed to parse your SRT output. Please ensure strict standard SRT syntax."
                time.sleep(2)
                attempt += 1
                continue

            if len(original_srt) != len(translated_srt):
                status_text.text(f"[{target_lang}] 문장 개수 불일치. 재시도 중... / 文章数の不一致。再試行中...")
                prompt_base += f"\n\nCorrection Request: Segment count mismatch! Try again."
                time.sleep(2)
                attempt += 1
                continue
            
            final_output = []
            for i in range(len(original_srt)):
                orig = original_srt[i]
                trans_text = translated_srt[i].text
                start_str = f"{orig.start.hours:02}:{orig.start.minutes:02}:{orig.start.seconds:02},{orig.start.milliseconds:03}"
                end_str = f"{orig.end.hours:02}:{orig.end.minutes:02}:{orig.end.seconds:02},{orig.end.milliseconds:03}"
                block = f"{orig.index}\n{start_str} --> {end_str}\n{trans_text}"
                final_output.append(block)
            
            status_text.text(f"[{target_lang}] 완료! / 完了! ({attempt}회 만에 성공 / {attempt}回目で成功)")
            progress_bar.progress(100)
            return "\n\n".join(final_output)

        except Exception as e:
            err_msg = str(e)
            if "429" in err_msg or "Quota" in err_msg or "quota" in err_msg:
                match = re.search(r"retry in ([\d\.]+)\s*s", err_msg)
                wait_time = int(float(match.group(1))) + 2 if match else 25
                status_text.text(f"⚠️ [API 한도 / API制限] {wait_time}초 대기 후 재시도... / {wait_time}秒待機後、再試行...")
                time.sleep(wait_time)
                continue
            else:
                status_text.text(f"[{target_lang}] 에러 발생 / エラー発生: {e}")
                time.sleep(3)
                attempt += 1
            
    status_text.text(f"[{target_lang}] 3회 시도 실패. 건너뜁니다. / 3回の試行失敗。スキップします。")
    progress_bar.progress(100)
    return None

# --- UI 레이아웃 구성 / UIレイアウト構成 ---
st.set_page_config(page_title="SRT 다국어 번역기 / SRT多言語翻訳機", page_icon="🌐", layout="centered")

st.title("글로벌 자막 번역기 🚀")
st.subheader("グローバル字幕翻訳機")
st.markdown("---")

is_locked = st.session_state.is_processing

# 1. 파일 업로드란
uploaded_file = st.file_uploader("원본 SRT 파일을 올려줘, 주인. / 元のSRTファイルをアップロードしてください。", type=['srt'], disabled=is_locked)

# 업로드 즉시 파일 검증 및 파싱 로직
original_srt = None
original_content = ""

if uploaded_file:
    raw_bytes = uploaded_file.getvalue()
    try:
        original_content = raw_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            original_content = raw_bytes.decode("cp949")
        except UnicodeDecodeError:
            original_content = raw_bytes.decode("shift_jis")
            
    try:
        original_srt = pysrt.from_string(original_content)
        
        if len(original_srt) == 0:
            st.error("🚨 자막이 비어있거나 올바른 SRT 형식이 아닙니다. / 字幕が空であるか、正しいSRT形式ではありません。")
            original_srt = None
        else:
            timeline_errors = 0
            for i in range(len(original_srt)):
                if original_srt[i].start >= original_srt[i].end:
                    timeline_errors += 1
                if i > 0 and original_srt[i].start < original_srt[i-1].start:
                    timeline_errors += 1
            
            if timeline_errors > 0:
                st.warning(f"⚠️ 원본 자막의 타임라인에 이상한 부분(시간 역전 등)이 {timeline_errors}곳 발견됐어. 번역은 진행되지만 결과물을 확인해줘. / 元의 자막의 타임라인에 이상이 {timeline_errors}箇所見つかりました。")
            else:
                st.success(f"✅ 검증 완료! 타임라인에 문제가 없으며, 총 **{len(original_srt)}**줄의 자막이 확인됐어. / 検証完了！タイムラインに問題はなく、計 **{len(original_srt)}** 行の字幕が確認されました。")
                
    except Exception as e:
        st.error(f"🚨 SRT 파일을 파싱하는 중 오류가 발생했어 / SRTファイルのパース中にエラーが発生しました: {e}")
        original_srt = None

# 2. 영상 제목 입력란
video_title = st.text_input("영상 제목을 입력해줘. (파일명에 사용됨) / 動画のタイトルを入力してください。(ファイル名に使用)", value=st.session_state.video_title, disabled=is_locked)
st.session_state.video_title = video_title

# 💡 5번 수정: 제미나이 모델 선택 기능 추가 (라디오 버튼 배치)
MODEL_OPTIONS = {
    "Gemini 3.5 Flash (한국어 번역시 추천)": "gemini-3.5-flash",
    "Gemini 3.1 Flash-Lite (한국어 외 다국어 번역시 추천)": "gemini-3.1-flash-lite"
}
selected_model_label = st.radio(
    "사용할 제미나이 모델을 선택해줘, 주인. / 使用するGeminiモデルを選択してください。",
    options=list(MODEL_OPTIONS.keys()),
    index=0,  # 기본 선택은 3.5 플래시
    disabled=is_locked
)
selected_model = MODEL_OPTIONS[selected_model_label]

st.markdown("---")
st.subheader("🌐 번역할 언어 선택 / 翻訳する言語の選択")
btn_col1, btn_col2, btn_col3 = st.columns([1.5, 1.5, 3])
with btn_col1:
    st.button("전체 선택 / 全選択", on_click=select_all, use_container_width=True, disabled=is_locked)
with btn_col2:
    st.button("전체 해제 / 全解除", on_click=deselect_all, use_container_width=True, disabled=is_locked)

cols = st.columns(3) 
for i, lang in enumerate(LANGUAGES.keys()):
    with cols[i % 3]:
        st.checkbox(lang, key=f"chk_{lang}", disabled=is_locked)

st.markdown("---")
selected_langs = [lang for lang in LANGUAGES.keys() if st.session_state[f"chk_{lang}"]]

# 3. 작업 시작 / 중단 버튼
if not st.session_state.is_processing:
    if st.button("✨ 번역 시작 / 翻訳開始", type="primary", use_container_width=True):
        if not uploaded_file:
            st.warning("먼저 원본 SRT 파일을 업로드해 줘. / まず元のSRTファイルをアップロードしてください。")
        elif not original_srt:
            st.error("자막 파일에 오류가 있어 번역을 시작할 수 없어. / 字幕ファイルにエラーがあり、翻訳を開始できません。")
        elif not video_title.strip():
            st.warning("영상 제목을 입력해 줘, 주인. / 動画のタイトルを入力してください。")
        elif not selected_langs:
            st.warning("번역할 언어를 하나 이상 선택해 줘. / 翻訳する言語を1つ以上選択してください。")
        else:
            st.session_state.is_processing = True
            st.session_state.results = {}
            st.session_state.show_balloons = True  # 💡 4번 수정: 작업 완료 시점에만 애니메이션이 나오도록 준비
            st.rerun()  # ⚠️ 오타 수정 완료!
else:
    if st.button("🛑 작업 중단 / 作業中断", type="primary", use_container_width=True):
        st.session_state.is_processing = False
        st.session_state.show_balloons = False
        st.warning("작업을 중단했어, 주인. 화면을 갱신합니다. / 作業を中断しました。画面を更新します。")
        time.sleep(1)
        st.rerun()  # ⚠️ 오타 수정 완료!

# --- 실제 번역 처리 루프 / 翻訳処理ループ ---
if st.session_state.is_processing and uploaded_file and original_srt and video_title.strip():
    total_langs = len(selected_langs)
    st.subheader("📊 실시간 진행 상황 / リアルタイム進行状況")
    
    total_progress_bar = st.progress(0)
    total_status_text = st.empty()
    lang_progress_bar = st.progress(0)
    lang_status_text = st.empty()
    
    for idx, lang in enumerate(selected_langs):
        if not st.session_state.is_processing:
            break
            
        clean_lang_name = lang.split(" / ")[0] 
        total_status_text.text(f"📊 전체 진행 상황: {idx+1} / {total_langs} 언어 작업 중 ({clean_lang_name}) \n 全体進行状況: {idx+1} / {total_langs} 言語作業中")
        target_lang_en = LANGUAGES[lang]
        
        # 💡 5번 수정: 선택된 모델 변수(selected_model) 전달
        translated_srt = translate_and_verify(
            original_content, 
            original_srt, 
            target_lang_en, 
            selected_model,
            lang_progress_bar, 
            lang_status_text
        )
        
        if translated_srt:
            is_valid, msg = verify_timeline_final(original_srt, translated_srt)
            if is_valid:
                st.session_state.results[clean_lang_name] = translated_srt
            
        total_progress_bar.progress((idx + 1) / total_langs)

    st.session_state.is_processing = False
    st.rerun()  # ⚠️ 오타 수정 완료!

# --- 최종 검수 및 다운로드 영역 / 最終確認およびダウンロード領域 ---
if st.session_state.results and not st.session_state.is_processing:
    st.markdown("---")
    st.subheader("🎉 작업 완료 및 다운로드 / 作業完了およびダウンロード")
    
    results = st.session_state.results
    title = st.session_state.video_title.strip()
    
    st.success(f"총 {len(results)}개 언어의 자막이 완벽하게 준비됐어! / 計{len(results)}言語の字幕が完璧に準備されました！")
    
    if len(results) == 1:
        lang_name = list(results.keys())[0]
        srt_content = list(results.values())[0]
        file_name = f"{title}_{lang_name}.srt"
        
        st.download_button(
            label=f"📥 {file_name} 다운로드 / ダウンロード",
            data=srt_content.encode("utf-8-sig"), 
            file_name=file_name,
            mime="text/plain",
            type="primary",
            use_container_width=True
        )
    else:
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for lang_name, srt_content in results.items():
                file_name = f"{title}_{lang_name}.srt"
                zip_file.writestr(file_name, srt_content.encode("utf-8-sig"))
        
        zip_buffer.seek(0)
        zip_filename = f"{title}_자막들.zip"
        
        st.download_button(
            label=f"📦 {zip_filename} 전체 다운로드 / 一括ダウンロード",
            data=zip_buffer,
            file_name=zip_filename,
            mime="application/zip",
            type="primary",
            use_container_width=True
        )

    # 💡 4번 수정: 애니메이션 플래그가 True일 때만 한 번 발생시키고 즉시 False로 전환
    if st.session_state.show_balloons:
        st.balloons()
        st.session_state.show_balloons = False
