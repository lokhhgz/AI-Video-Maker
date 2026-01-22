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
st.set_page_config(page_title="AI Shorts Maker (Ultimate)", page_icon="🇺🇸")

# 📉 解析度設定 (維持輕量化)
VIDEO_W, VIDEO_H = 540, 960 

# 🧠 AI 寫英文腳本
def generate_script(api_key, topic, duration):
    genai.configure(api_key=api_key)
    est_sentences = int(int(duration) / 6)
    if est_sentences < 3: est_sentences = 3
    
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

# 🗣️ TTS (產生語音檔案) - 這是最穩定的核心
def run_tts_sync(text, filename, voice, rate):
    async def _tts():
        communicate = edge_tts.Communicate(text, voice, rate=rate)
        await communicate.save(filename)
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(_tts())
        loop.close()
        return True
    except Exception as e:
        print(f"TTS Error: {e}")
        return False

# 🖼️ 製作英文字幕
def create_subtitle(text, width, height):
    img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default() 
    
    text_len = len(text) * 7 
    x = (width - text_len) / 2
    if x < 20: x = 20
    y = height - 120
    
    draw.text((x+2, y+2), text, font=font, fill="black")
    draw.text((x, y), text, font=font, fill="white")
    
    return np.array(img)

# --- 主程式 ---
st.title("🇺🇸 AI Shorts Maker (Ultimate)")

with st.sidebar:
    st.header("⚙️ Settings")
    
    # === 1. API Key 設定與狀態燈 ===
    gemini_input = st.text_input("Gemini Key", type="password")
    pexels_input = st.text_input("Pexels Key", type="password")
    
    gemini_key = gemini_input if gemini_input else st.secrets.get("GEMINI_KEY", "")
    pexels_key = pexels_input if pexels_input else st.secrets.get("PEXELS_KEY", "")
    
    if gemini_key:
        st.success("✅ Gemini Key Ready")
    else:
        st.warning("⚠️ Missing Gemini Key")
        
    if pexels_key:
        st.success("✅ Pexels Key Ready")
    else:
        st.warning("⚠️ Missing Pexels Key")

    st.divider()

    # === 2. 配音設定與快速試聽 ===
    voice_map = {
        "Female (Ava)": "en-US-AvaNeural",
        "Male (Andrew)": "en-US-AndrewNeural",
        "Female (Emma)": "en-US-EmmaNeural",
        "Male (Brian)": "en-US-BrianNeural"
    }
    voice_name = st.selectbox("Voice Actor", list(voice_map.keys()))
    voice_role = voice_map[voice_name]
    
    rate = st.slider("Speaking Speed", 0.5, 1.5, 1.0, 0.1)
    
    # 🔊 側邊欄快速試聽按鈕 (【關鍵修復】)
    if st.button("🔊 Test Voice Now"):
        test_file = "preview_temp.mp3"
        rate_str = f"{int((rate - 1.0) * 100):+d}%"
        test_text = "Hello! This is a test for your AI video. Everything is working fine."
        
        # 1. 刪除舊檔
        if os.path.exists(test_file):
            os.remove(test_file)
            
        # 2. 生成新檔
        success = run_tts_sync(test_text, test_file, voice_role, rate_str)
        
        # 3. 【關鍵步驟】讀取成 Bytes 再餵給播放器
        if success and os.path.exists(test_file):
            with open(test_file, "rb") as f:
                audio_bytes = f.read()
            st.audio(audio_bytes, format="audio/mp3")
            st.caption("☝️ Preview of current settings")
            
            # 播放完刪除 (保持清潔)
            os.remove(test_file)
        else:
            st.error("❌ Audio generation failed. Please check internet connection.")

    st.divider()
    duration = st.slider("Duration (sec)", 15, 300, 30, 5)

# --- 右側主畫面 ---

if "script" not in st.session_state:
    st.session_state.script = None

topic = st.text_input("Topic", "The history of Coffee")

# Step 1
if st.button("Step 1: Generate Script", type="primary"):
    if not gemini_key or not pexels_key:
        st.error("Please provide API Keys first!")
        st.stop()
        
    with st.spinner("Writing script..."):
        script = generate_script(gemini_key, topic, duration)
        if script:
            st.session_state.script = script
            st.rerun()
        else:
            st.error("Failed to generate script.")

# 顯示劇本
if st.session_state.script:
    st.subheader("📝 Script Preview")
    for i, item in enumerate(st.session_state.script):
        st.text(f"{i+1}. [{item['keyword']}] {item['text']}")

    st.divider()

    # Step 2
    if st.button("Step 2: Render Video", type="primary"):
        status = st.status("🎬 Rendering video... Please wait.", expanded=True)
        progress_bar = st.progress(0)
        clips = []
        script = st.session_state.script
        
        try:
            for i, data in enumerate(script):
                status.write(f"Processing scene {i+1}: {data['keyword']}...")
                
                clean_kw = "".join([c for c in data['keyword'] if c.isalnum()])
                v_file = f"v_{i}_{clean_kw}.mp4"
                a_file = f"a_{i}.mp3"
                
                download_video(pexels_key, data['keyword'], v_file)
                
                rate_str = f"{int((rate - 1.0) * 100):+d}%"
                
                # 使用同步 TTS
                run_tts_sync(data['text'], a_file, voice_role, rate_str)
                
                try:
                    if os.path.exists(a_file):
                        a_clip = AudioFileClip(a_file)
                    else:
                        a_clip = None
                    
                    if os.path.exists(v_file) and os.path.getsize(v_file) > 1000:
                        v_clip = VideoFileClip(v_file).resize(newsize=(VIDEO_W, VIDEO_H))
                    else:
                        dur = a_clip.duration if a_clip else 3
                        v_clip = ColorClip(size=(VIDEO_W, VIDEO_H), color=(0,0,0), duration=dur)
                    
                    final_dur = a_clip.duration if a_clip else v_clip.duration
                    if v_clip.duration < final_dur:
                        v_clip = v_clip.loop(duration=final_dur)
                    else:
                        v_clip = v_clip.subclip(0, final_dur)
                    
                    if a_clip:
                        v_clip = v_clip.set_audio(a_clip)
                    
                    txt_img = create_subtitle(data['text'], VIDEO_W, VIDEO_H)
                    txt_clip = ImageClip(txt_img).set_duration(final_dur)
                    
                    clips.append(CompositeVideoClip([v_clip, txt_clip]))
                    
                    del v_clip, a_clip, txt_clip
                    gc.collect()
                    
                except Exception as e:
                    print(f"Error in clip {i}: {e}")
                    continue
                
                progress_bar.progress((i + 1) / len(script))
            
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