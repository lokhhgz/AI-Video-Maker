import streamlit as st
import os
import requests
import asyncio
import edge_tts
import json
import random
import gc
import google.generativeai as genai
from moviepy.editor import VideoFileClip, AudioFileClip, ImageClip, CompositeVideoClip, concatenate_videoclips, ColorClip
from PIL import Image, ImageDraw, ImageFont
import numpy as np

# ================= 設定區 =================
st.set_page_config(page_title="AI Video (English Ver.)", page_icon="🇺🇸")

# 📉 解析度設定 (維持輕量化)
VIDEO_W, VIDEO_H = 540, 960 

# 🧠 AI 寫英文腳本
def generate_script(api_key, topic, duration):
    genai.configure(api_key=api_key)
    est_sentences = int(int(duration) / 5)
    if est_sentences < 3: est_sentences = 3
    
    # 這裡指定用 "英文" 回答
    prompt = f"""
    You are a short video script writer. Create a script about topic: "{topic}".
    Target duration: {duration} seconds.
    Generate exactly {est_sentences} sentences.
    Requirements:
    1. Language: English.
    2. Length: Each sentence should be 10-15 words.
    3. Keyword: Provide 1 English search keyword for stock video.
    4. Format: Return ONLY a raw JSON array:
    [
        {{"text": "First sentence...", "keyword": "Airplane"}},
        {{"text": "Second sentence...", "keyword": "Sky"}}
    ]
    """
    
    models = ['gemini-flash-latest', 'gemini-2.0-flash', 'gemini-pro']
    for m in models:
        try:
            model = genai.GenerativeModel(m)
            response = model.generate_content(prompt)
            clean = response.text.replace("```json", "").replace("```", "").strip()
            return json.loads(clean)
        except:
            continue
    return None

# 📥 下載影片
def download_video(api_key, query, filename):
    url = "https://api.pexels.com/videos/search"
    headers = {"Authorization": api_key}
    params = {"query": query, "per_page": 1, "orientation": "portrait"}
    try:
        r = requests.get(url, headers=headers, params=params, timeout=5)
        if r.status_code == 200:
            data = r.json()
            if data.get('videos'):
                link = data['videos'][0]['video_files'][0]['link']
                with open(filename, 'wb') as f:
                    f.write(requests.get(link).content)
                return True
    except:
        pass
    return False

# 🗣️ TTS (產生語音檔案)
async def get_voice(text, voice, rate):
    communicate = edge_tts.Communicate(text, voice, rate=rate)
    data = b""
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            data += chunk["data"]
    return data

# 🖼️ 製作英文字幕 (使用內建字體，絕對安全)
def create_subtitle(text, width, height):
    # 全透明背景
    img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # 使用預設字體 (這是系統內建的，不需要下載)
    # 雖然有點小，但絕對不會導致程式崩潰
    font = ImageFont.load_default() 
    
    # 簡單的文字置中
    # 英文每個字比較窄，稍微估算一下
    text_len = len(text) * 7 
    x = (width - text_len) / 2
    if x < 20: x = 20
    y = height - 120 # 字幕位置
    
    # 黑色陰影 + 白色文字
    draw.text((x+2, y+2), text, font=font, fill="black")
    draw.text((x, y), text, font=font, fill="white")
    
    return np.array(img)

# --- 主程式 ---
st.title("🇺🇸 AI Shorts Maker (English)")

with st.sidebar:
    st.header("Settings")
    gemini_key = st.text_input("Gemini Key", type="password") or st.secrets.get("GEMINI_KEY", "")
    pexels_key = st.text_input("Pexels Key", type="password") or st.secrets.get("PEXELS_KEY", "")
    
    # 英文配音員選擇
    voice_map = {
        "Female (Ava)": "en-US-AvaNeural",
        "Male (Andrew)": "en-US-AndrewNeural",
        "Female (Emma)": "en-US-EmmaNeural",
        "Male (Brian)": "en-US-BrianNeural"
    }
    voice_name = st.selectbox("Voice", list(voice_map.keys()))
    voice_role = voice_map[voice_name]
    
    rate = st.slider("Speed", 0.5, 1.5, 1.0, 0.1)
    duration = st.slider("Duration (sec)", 15, 60, 30, 5)

# 1. 輸入主題
topic = st.text_input("Topic (Try English for best results)", "The history of Coffee")

# 初始化 Session State (用來記憶劇本)
if "script" not in st.session_state:
    st.session_state.script = None
if "audio_preview" not in st.session_state:
    st.session_state.audio_preview = None

# 2. 按鈕一：生成劇本與試聽
if st.button("Step 1: Generate Script & Audio Preview", type="primary"):
    if not gemini_key or not pexels_key:
        st.error("Please provide API Keys")
        st.stop()
        
    with st.spinner("Writing script & Generating audio..."):
        # 生成劇本
        script = generate_script(gemini_key, topic, duration)
        if not script:
            st.error("Failed to generate script.")
            st.stop()
        st.session_state.script = script
        
        # 生成預覽音訊 (把所有句子的聲音串起來)
        full_text = " ".join([s['text'] for s in script])
        rate_str = f"{int((rate - 1.0) * 100):+d}%"
        
        # 這裡用 asyncio 跑 TTS
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        audio_data = loop.run_until_complete(get_voice(full_text, voice_role, rate_str))
        
        st.session_state.audio_preview = audio_data
        st.rerun() # 重新整理頁面以顯示結果

# 3. 顯示劇本與試聽區
if st.session_state.script:
    st.divider()
    st.subheader("📝 Script Preview")
    
    # 顯示播放器
    if st.session_state.audio_preview:
        st.audio(st.session_state.audio_preview, format="audio/mp3")
        st.caption("🎧 Listen to the voice over before rendering.")
        
    # 顯示分鏡表
    for i, item in enumerate(st.session_state.script):
        st.text(f"{i+1}. [{item['keyword']}] {item['text']}")

    st.divider()

    # 4. 按鈕二：開始合成影片
    if st.button("Step 2: Render Video (Takes time)", type="primary"):
        status = st.status("🎬 Rendering video... Please wait.", expanded=True)
        progress_bar = st.progress(0)
        clips = []
        script = st.session_state.script
        
        try:
            for i, data in enumerate(script):
                status.write(f"Processing scene {i+1}: {data['keyword']}...")
                
                # 檔案命名
                clean_kw = "".join([c for c in data['keyword'] if c.isalnum()])
                v_file = f"v_{i}_{clean_kw}.mp4"
                a_file = f"a_{i}.mp3"
                
                # 下載素材 & 生成單句語音
                download_video(pexels_key, data['keyword'], v_file)
                
                # 生成單句語音
                rate_str = f"{int((rate - 1.0) * 100):+d}%"
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                wav_data = loop.run_until_complete(get_voice(data['text'], voice_role, rate_str))
                with open(a_file, "wb") as f:
                    f.write(wav_data)
                
                # --- 合成單一片段 ---
                try:
                    # 1. 聲音
                    if os.path.exists(a_file):
                        a_clip = AudioFileClip(a_file)
                    else:
                        a_clip = None
                    
                    # 2. 影片 (維持 540x960 輕量化)
                    if os.path.exists(v_file) and os.path.getsize(v_file) > 1000:
                        v_clip = VideoFileClip(v_file).resize(newsize=(VIDEO_W, VIDEO_H))
                    else:
                        # 備用黑畫面
                        dur = a_clip.duration if a_clip else 3
                        v_clip = ColorClip(size=(VIDEO_W, VIDEO_H), color=(0,0,0), duration=dur)
                    
                    # 3. 對齊長度
                    final_dur = a_clip.duration if a_clip else v_clip.duration
                    if v_clip.duration < final_dur:
                        v_clip = v_clip.loop(duration=final_dur)
                    else:
                        v_clip = v_clip.subclip(0, final_dur)
                    
                    if a_clip:
                        v_clip = v_clip.set_audio(a_clip)
                    
                    # 4. 加上字幕 (現在是英文，絕對不會崩潰)
                    txt_img = create_subtitle(data['text'], VIDEO_W, VIDEO_H)
                    txt_clip = ImageClip(txt_img).set_duration(final_dur)
                    
                    # 組合
                    clips.append(CompositeVideoClip([v_clip, txt_clip]))
                    
                    # 記憶體回收
                    del v_clip, a_clip, txt_clip
                    gc.collect()
                    
                except Exception as e:
                    print(f"Error in clip {i}: {e}")
                    continue
                
                progress_bar.progress((i + 1) / len(script))
            
            # 最終合併
            if clips:
                status.write("✨ Stitching clips together...")
                final_video = concatenate_videoclips(clips, method="compose")
                output_path = f"final_video_{random.randint(1000,9999)}.mp4"
                final_video.write_videofile(output_path, fps=24, codec='libx264', audio_codec='aac', preset='ultrafast')
                
                status.update(label="✅ Done!", state="complete")
                st.balloons()
                st.video(output_path)
            else:
                st.error("No clips generated.")
                
        except Exception as e:
            st.error(f"Render failed: {e}")