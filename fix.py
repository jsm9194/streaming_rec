# Required: pip install undetected-chromedriver
import os
import time
import random
import threading
import csv
import subprocess
import signal
import sys

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains

# === 사용자 설정 ===
from urls import VIDEO_URLS  # URL 리스트가 정의된 모듈
FFMPEG_PATH = r"F:\\Desktop\\ffmpeg-7.1.1-full_build\\bin\\ffmpeg.exe"
# FFMPEG 경로 (full build 버전 사용)
VIDEO_Y_ADJUST = 85           # 화면 Y 오프셋 조정

# === Stealth Driver 생성 ===
def create_stealth_driver():
    options = uc.ChromeOptions()
    w, h = random.randint(1024,1440), random.randint(768,900)
    x_pos, y_pos = random.randint(0,200), random.randint(0,200)
    options.add_argument(f"--window-size={w},{h}")
    options.add_argument(f"--window-position={x_pos},{y_pos}")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    ua_list = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/115.0.5790.170 Safari/537.36",
    ]
    options.add_argument(f"user-agent={random.choice(ua_list)}")
    driver = uc.Chrome(options=options)
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": """
            window.chrome = { runtime: {} };
            Object.defineProperty(navigator, 'plugins', { get: () => [1,2,3,4,5] });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US','en'] });
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        """
    })
    return driver

# === 댓글 크롤링 ===
def crawl_comments(driver, comments, stop_flag):
    seen = set()
    while not stop_flag[0]:
        try:
            sec = driver.execute_script("return document.querySelector('video')?.currentTime || 0;")
            hrs, mins, secs = map(int, (sec//3600, (sec%3600)//60, sec%60))
            timestamp = f"{hrs:02}:{mins:02}:{secs:02}"
            nicks = driver.find_elements(By.CSS_SELECTOR, ".NormalComment_nickname_K2\\+Tx")
            comms = driver.find_elements(By.CSS_SELECTOR, ".NormalComment_comment_Yqlnf")
            for nick, comm in zip(nicks, comms):
                key = (nick.text.strip(), comm.text.strip())
                if key not in seen and key[0] and key[1]:
                    seen.add(key)
                    comments.append([timestamp, key[0], key[1]])
        except:
            pass
        time.sleep(random.uniform(0.5,1.5))

# === CSV 저장 ===
def save_comments(path, comments):
    with open(path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f, quoting=csv.QUOTE_ALL)
        writer.writerow(['timestamp','nickname','comment'])
        writer.writerows(comments)
    print(f"✅ 댓글 {len(comments)}개 저장 → {path}")

# === SIGINT 핸들러 ===
def handle_sigint(signum, frame):
    raise KeyboardInterrupt

# === 메인 실행 ===
if __name__ == "__main__":
    signal.signal(signal.SIGINT, handle_sigint)
    for idx, url in enumerate(VIDEO_URLS, 1):
        ts = time.strftime("%Y%m%d_%H%M%S")
        out_vid = f"recorded_{idx}_{ts}.mp4"
        out_csv = f"comments_{idx}_{ts}.csv"
        comments, stop_flag = [], [False]
        driver = create_stealth_driver()
        try:
            driver.get(url)
            print(f"[{idx}] 로딩 완료")
            time.sleep(random.uniform(3,6))
            driver.execute_script(f"window.scrollBy(0,{random.randint(100,300)});")
            time.sleep(random.uniform(1,2))
            for selector in [
                ".ContentsButton_wrap_oUflt.ContentsButton_has_background_zxEUL.SoundButton_wrap_vD3DA",
                "button.PlayButton_btn__1WhXM"
            ]:
                try:
                    btn = driver.find_element(By.CSS_SELECTOR, selector)
                    ActionChains(driver).move_to_element(btn).pause(random.uniform(0.5,1)).click().perform()
                except:
                    pass
            pos = driver.get_window_position()
            rect = driver.execute_script("const r = arguments[0].getBoundingClientRect(); return {left:r.left+window.scrollX,top:r.top+window.scrollY,width:r.width,height:r.height};", driver.find_element(By.TAG_NAME,"video"))
            x, y = max(0, pos['x']+int(rect['left'])), max(0, pos['y']+int(rect['top'])+VIDEO_Y_ADJUST)
            w, h = int(rect['width']), int(rect['height'])
            print(f"🖥 x={x}, y={y}, w={w}, h={h}")
            thread = threading.Thread(target=crawl_comments, args=(driver, comments, stop_flag))
            thread.start()
            cmd = [
                FFMPEG_PATH,'-y',
                '-f','gdigrab','-framerate','30',
                '-offset_x',str(x),'-offset_y',str(y),
                '-video_size',f"{w}x{h}",'-i','desktop',
                '-f','dshow','-i','audio=CABLE Output(VB-Audio Virtual Cable)',
                '-c:v','libx264','-preset','fast','-crf','23',
                '-c:a','aac','-b:a','128k','-movflags','+empty_moov+default_base_moof+frag_keyframe',
                out_vid
            ]
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
            print(f"⏺ 녹화 시작: {out_vid}")
            while True:
                if proc.poll() is not None:
                    break
                if driver.execute_script("return document.querySelector('video')?.ended||false;"):
                    proc.terminate()
                    break
                time.sleep(1)
            proc.wait()
        except KeyboardInterrupt:
            print("⚠️ 중단 감지")
        finally:
            stop_flag[0] = True
            thread.join(timeout=5)
            save_comments(out_csv, comments)
            driver.quit()
    print("✅ 전체 작업 완료")
