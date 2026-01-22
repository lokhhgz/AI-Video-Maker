import streamlit as st
import os
import requests
import asyncio
import edge_tts
import json
import random
import google.generativeai as genai
from moviepy.editor import VideoFileClip, AudioFileClip, ImageClip, CompositeVideoClip, concatenate_videoclips
from PIL import Image, ImageDraw, ImageFont
import numpy as np
import importlib.metadata # 用來檢查版本

# ================= 雲端設定區 =================
st.set_page_config(page_title="AI 短影音工廠 (未來版)", page_icon="🚀")

# 📥 自動下載中文字體
def download_font():
    font_path = "NotoSansTC-Bold.otf"
    if not os.path.exists(font_path):
        url = "https://github.com/googlefonts/noto-cjk/raw/main/Sans/OTF/TraditionalChinese/NotoSansTC-Bold.otf"
        try:
            r = requests.get(url)
            with open(font_path, "wb") as f:
                f.write(r.content)
        except:
            pass
    return font_path

def get_font(size=80):
    font_path = "NotoSansTC-Bold.otf"
    if os.path.exists(font_path):
        return ImageFont.truetype(font_path, size)
    return ImageFont.load_default()

# 🧠 AI 寫腳本 (針對你的帳號特製版)
def generate_script_from_ai(api_key, topic, duration_sec):
    genai.configure(api_key=api_key)
    est_sentences = int(int(duration_sec) / 4.5)
    if est_sentences < 3: est_sentences = 3
    
    # 🌟 這裡根據你的診斷報告，改用你帳號裡有的模型！
    models_to_try = [
        'gemini-flash-latest',     # 這是你的清單裡有的！
        'gemini-2.0-flash',        # 你也有這個
        'gemini-2.5-flash',        # 你甚至有這個未來模型
        'gemini-pro-latest'        # 保底用
    ]
    
    for model_name in models_to_try:
        try:
            print(f"正在嘗試模型: {model_name}")
            model = genai.GenerativeModel(model_name)
            prompt = f"""
            你是一個短影音腳本專家。請根據主題「{topic}」寫出一個短影音腳本。
            【規格】：影片長度 {duration_sec} 秒，請提供 {est_sentences} 個分鏡句子。
            【要求】：每句 15-20 字，搭配一個英文搜尋單字 (Keyword)。
            【格式】：請只回傳純 JSON 陣列，不要有 markdown 符號：
            [
                {{"text": "第一句旁白...", "keyword": "Keyword1"}},
                {{"text": "第二句旁白...", "keyword": "Keyword2"}}
            ]
            """
            response = model.generate_content(prompt)
            clean_text = response.text.replace("```json", "").replace("```", "").strip()
            return json.loads(clean_text)
        except Exception as e:
            # 顯示黃色警告，讓我們知道哪個模型失敗了，程式會自動試下一個
            st.warning(f"⚠️ 模型 {model_name} 回應: {e}")
            continue
    return None

# 📥 下載影片
def download_video(api_key, query, filename):
    url = "https://api.pexels.com/videos/search"
    headers = {
        "Authorization": api_key,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    params = {"query": query, "per_page": 1, "orientation": "portrait"}
    
    try:
        r = requests.get(url, headers=headers, params=params, timeout=15)
        if r.status_code == 200:
            data = r.json()
            if data.get('videos') and len(data['videos']) > 0:
                video_url = data['videos'][0]['video_files'][0]['link']
                v_r = requests.get(video_url, headers=headers, timeout=30)
                if v_r.status_code == 200:
                    with open(filename, 'wb') as f:
                        f.write(v_r.content)
                    return True
    except Exception as e:
        print(f"Download fail: {e}")
    return False

# 🗣️ TTS
def run_tts(text, filename, voice, rate):
    rate_str = f"{int((rate - 1.0) * 100):+d}%"
    async def _tts():
        communicate = edge_tts.Communicate(text, voice, rate=rate_str)
        await communicate.save(filename)
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(_tts())
        loop.close()
        return True
    except:
        return False

# 🖼️ 字幕圖片
def create_text_image(text, width, height):
    img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font = get_font(70)
    max_width = width * 0.85
    lines, current_line = [], ""
    for char in text:
        if draw.textlength(current_line + char, font=font) <= max_width:
            current_line += char
        else:
            lines.append(current_line)
            current_line = char
    lines.append(current_line)
    total_h = len(lines) * 80
    current_y = (height - total_h) / 2
    for line in lines:
        w = draw.textlength(line, font=font)
        x = (width - w) / 2
        for adj in range(-2, 3):
             for adj2 in range(-2, 3):
                 draw.text((x+adj, current_y+adj2), line, font=font, fill="black")
        draw.text((x, current_y), line, font=font, fill="white")
        current_y += 80
    return np.array(img)

# --- 主程式 ---
st.title("🚀 AI 短影音工廠 (未來版)")

# 顯示環境檢查 (確保我們用了正確的庫)
try:
    ver = importlib.metadata.version("google-generativeai")
    st.caption(f"🔧 Google AI 核心版本: {ver} (應 >= 0.8.3)")
except:
    pass

download_font()

with st.sidebar:
    st.header("⚙️ 參數設定")
    gemini_key_input = st.text_input("Gemini API Key", type="password")
    pexels_key_input = st.text_input("Pexels API Key", type="password")
    
    gemini_key = gemini_key_input if gemini_key_input else st.secrets.get("GEMINI_KEY", "")
    pexels_key = pexels_key_input if pexels_key_input else st.secrets.get("PEXELS_KEY", "")
    
    if st.secrets.get("GEMINI_KEY"): st.caption("✅ 已啟用雲端 Gemini 金鑰")
    if st.secrets.get("PEXELS_KEY"): st.caption("✅ 已啟用雲端 Pexels 金鑰")

    st.divider()
    voice_option = st.selectbox("配音員", ("女聲 - 曉臻", "男聲 - 雲哲"))
    voice_role = "zh-TW-HsiaoChenNeural" if "女聲" in voice_option else "zh-TW-YunJheNeural"
    speech_rate = st.slider("語速調整", 0.5, 2.0, 1.2, 0.1)
    duration = st.slider("影片目標長度 (秒)", 30, 300, 45, 10)

topic = st.text_input("💡 請輸入影片主題", placeholder="例如：未來的交通工具")

if st.button("🚀 開始生成影片", type="primary"):
    if not gemini_key or not pexels_key:
        st.error("❌ 缺少 API Key！")
    elif not topic:
        st.error("❌ 請輸入主題")
    else:
        status = st.status("🧠 正在構思劇本...", expanded=True)
        try:
            # 1. 生成劇本
            script_data = generate_script_from_ai(gemini_key, topic, duration)
            if not script_data:
                status.update(label="❌ 劇本生成失敗", state="error")
                st.error("👉 所有模型都失敗了。如果出現 429 錯誤，代表你的免費額度已用完，或此模型不支援免費版。")
                st.stop()
            
            status.write(f"✅ 劇本完成！共 {len(script_data)} 個分鏡")
            progress_bar = st.progress(0)
            clips = []
            
            # 2. 製作片段
            for i, data in enumerate(script_data):
                status.write(f"正在製作第 {i+1} 個片段: {data['keyword']}...")
                
                safe_kw = "".join([c for c in data['keyword'] if c.isalnum()])
                v_file = f"video_{safe_kw}.mp4"
                a_file = f"temp_{i}.mp3"
                
                if not download_video(pexels_key, data['keyword'], v_file):
                    # 備案：如果找不到關鍵字影片，用通用影片
                    if not download_video(pexels_key, "Abstract", "video_fallback.mp4"):
                        continue
                    v_file = "video_fallback.mp4"
                
                run_tts(data['text'], a_file, voice_role, speech_rate)
                
                try:
                    v_clip = VideoFileClip(v_file).resize(newsize=(1080, 1920))
                    a_clip = AudioFileClip(a_file)
                    if a_clip.duration > v_clip.duration:
                        v_clip = v_clip.loop(duration=a_clip.duration)
                    else:
                        v_clip = v_clip.subclip(0, a_clip.duration)
                    
                    v_clip = v_clip.set_audio(a_clip)
                    txt_clip = ImageClip(create_text_image(data['text'], 1080, 1920)).set_duration(a_clip.duration)
                    clips.append(CompositeVideoClip([v_clip, txt_clip]))
                    
                except Exception as e:
                    print(f"Clip error: {e}")
                
                progress_bar.progress((i + 1) / len(script_data))
            
            if clips:
                status.write("🎬 正在合成最終影片...")
                final = concatenate_videoclips(clips)
                output_name = f"result_{random.randint(1000,9999)}.mp4"
                final.write_videofile(output_name, fps=24, codec='libx264', audio_codec='aac')
                status.update(label="✨ 製作完成！", state="complete")
                st.video(output_name)
            else:
                status.update(label="❌ 製作失敗", state="error")
                
        except Exception as e:
            st.error(f"系統錯誤: {e}")