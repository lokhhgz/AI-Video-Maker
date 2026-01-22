import streamlit as st
import google.generativeai as genai
import os

st.set_page_config(page_title="金鑰醫生", page_icon="🩺")
st.title("🩺 Google API 金鑰健檢室")

# 1. 讀取你設定的金鑰
api_key = st.secrets.get("GEMINI_KEY", "")

# 顯示金鑰狀態 (只顯示前幾碼，確保安全)
if api_key:
    st.info(f"🔑 目前讀取到的金鑰：`{api_key[:5]}...{api_key[-3:]}`")
    st.caption("若上方顯示的金鑰與您在 Google AI Studio 看到的不同，請檢查 Secrets 設定。")
else:
    st.error("❌ 尚未讀取到金鑰！請檢查 Secrets 是否設定正確。")
    st.stop()

# 2. 開始測試
if st.button("🚀 開始連線測試", type="primary"):
    genai.configure(api_key=api_key)
    st.write("🔄 正在嘗試連線 Google 伺服器...")
    
    try:
        # 嘗試列出所有模型
        models = list(genai.list_models())
        
        if not models:
            st.error("❌ 連線成功，但「模型清單是空的」！")
            st.warning("👉 這代表您的 Google Cloud 專案沒有啟用 API 服務。請建立一個全新的專案。")
        else:
            st.success(f"✅ 測試成功！您的金鑰可以存取 {len(models)} 個模型：")
            
            # 檢查是否有我們需要的模型
            has_flash = any("gemini-1.5-flash" in m.name for m in models)
            
            for m in models:
                st.text(f"📄 {m.name}")
            
            st.divider()
            if has_flash:
                st.balloons()
                st.success("🎉 太棒了！這把鑰匙是健康的！\n現在您可以把原本的影片生成程式碼貼回來了！")
            else:
                st.error("⚠️ 悲劇：這把鑰匙能連線，但『沒有』Gemini 1.5 的權限。")
                
    except Exception as e:
        st.error("❌ 連線失敗！錯誤訊息如下：")
        st.code(str(e))
        if "404" in str(e):
            st.warning("👉 診斷結果：您的專案找不到模型服務 (Project Blindness)。請建立新專案。")
        elif "403" in str(e) or "400" in str(e):
            st.warning("👉 診斷結果：金鑰無效或複製錯誤。")