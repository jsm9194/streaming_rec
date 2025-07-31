import time
import subprocess
import threading
import csv
import random
import signal    
import sys
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver import ActionChains

# === 설정 ===
# 외부 파일 urls.py 에서 VIDEO_URLS 리스트를 가져옵니다
from urls import VIDEO_URLS
FFMPEG_PATH = r"F:\Desktop\ffmpeg-7.1.1-full_build\bin\ffmpeg.exe"  # full build 경로로 변경하세요
# 화면 포커스 보정용 Y 오프셋(px)
VIDEO_Y_ADJUST = 85  # 필요시 값을 조정하세요

# === 댓글 크롤링 스레드 함수 ===

def crawl_comments(driver, comments_data, stop_flag_ref):
    seen = set()
    while not stop_flag_ref[0]:
        try:
            sec = driver.execute_script("return document.querySelector('video')?.currentTime || 0;")
            hrs, mins, secs = map(int, (sec // 3600, (sec % 3600) // 60, sec % 60))
            timestamp = f"{hrs:02}:{mins:02}:{secs:02}"
            nick_elems = driver.find_elements(By.CSS_SELECTOR, ".NormalComment_nickname_K2\\+Tx")
            comm_elems = driver.find_elements(By.CSS_SELECTOR, ".NormalComment_comment_Yqlnf")
            for nick, comm in zip(nick_elems, comm_elems):
                nick_text = nick.text.strip()
                comm_text = comm.text.strip()
                if not nick_text or not comm_text:
                    continue
                key = (nick_text, comm_text)
                if key in seen:
                    continue
                seen.add(key)
                comments_data.append([timestamp, nick_text, comm_text])
        except Exception:
            pass
        time.sleep(random.uniform(0.5, 1.5))

# === 댓글 CSV 저장 함수 ===

def save_comments(csv_path, comments_data):
    with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(['timestamp', 'nickname', 'comment'])
        writer.writerows(comments_data)
    print(f"✅ 댓글 {len(comments_data)}개 저장 → {csv_path}")

# === 메인 실행 ===

if __name__ == '__main__':
    def shutdown(signum, frame):
        print("\n⚠️ SIGINT 감지! 정리 중…")
        raise KeyboardInterrupt

    signal.signal(signal.SIGINT, shutdown)

    for idx, video_url in enumerate(VIDEO_URLS, start=1):
        ts = time.strftime("%Y%m%d_%H%M%S")
        output_video = f"recorded_with_audio_{idx}_{ts}.mp4"
        output_csv   = f"comments_{idx}_{ts}.csv"

        comments_data = []
        stop_flag = [False]

        # --- Chrome 드라이버 설정 (봇 탐지 우회) ---
        options = Options()
        options.add_argument("--start-maximized")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.7204.169 Safari/537.36"
        )
        driver = webdriver.Chrome(options=options)
        driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"}
        )
        # ----------------------------------------------

        driver.get(video_url)
        print(f"🌐 [{idx}/{len(VIDEO_URLS)}] 페이지 로드 완료, 5초 대기...")
        time.sleep(random.uniform(3, 6))

        # 사람 같은 랜덤 스크롤
        try:
            scroll_y = random.randint(100, 300)
            driver.execute_script(f"window.scrollBy(0, {scroll_y});")
        except:
            pass
        time.sleep(random.uniform(1, 3))

        # 음소거 해제
        try:
            mute_btn = driver.find_element(By.CSS_SELECTOR,
                ".ContentsButton_wrap_oUflt.ContentsButton_has_background_zxEUL.SoundButton_wrap_vD3DA"
            )
            ActionChains(driver).move_to_element(mute_btn).pause(random.uniform(0.5,1.0)).click().perform()
            print("🔊 음소거 해제 완료")
        except:
            print("🔊 음소거 버튼 없음 or 이미 해제됨")

        # 자동 재생
        try:
            play_btn = driver.find_element(By.CSS_SELECTOR, "button.PlayButton_btn__1WhXM")
            ActionChains(driver).move_to_element(play_btn).pause(random.uniform(0.5,1.0)).click().perform()
            print("▶️ 자동 재생 시작")
        except:
            print("▶️ 자동 재생 생략 or 이미 재생 중")

        pos = driver.get_window_position()
        win_x, win_y = max(0, pos['x']), max(0, pos['y'])

        # 비디오 요소 선택 및 크롭 영역 계산
        try:
            container = driver.find_element(By.CSS_SELECTOR, 'video.webplayer-internal-video')
        except NoSuchElementException:
            container = driver.find_element(By.TAG_NAME, 'video')
        rect = driver.execute_script(
            "const r = arguments[0].getBoundingClientRect();"
            "return {left: r.left + window.scrollX, top: r.top + window.scrollY, width: r.width, height: r.height};",
            container
        )
        vid_x, vid_y = int(rect['left']), int(rect['top'])
        vid_w, vid_h = int(rect['width']), int(rect['height'])
        x = win_x + vid_x
        y = win_y + vid_y + VIDEO_Y_ADJUST
        w, h = vid_w, vid_h
        print(f"🖥[{idx}] 녹화 영역: x={x}, y={y}, w={w}, h={h}")

        # 댓글 크롤링 스레드 시작
        thread = threading.Thread(target=crawl_comments, args=(driver, comments_data, stop_flag))
        thread.start()
        print(f"💬[{idx}] 댓글 수집 시작")

                        # ffmpeg 녹화 명령 (WASAPI loopback 사용)
        # full build ffmpeg를 사용해야 합니다 (wasapi 지원)
        ffmpeg_cmd = [
            FFMPEG_PATH, '-y',
            # 화면 캡처 (gdigrab)
            '-f', 'gdigrab', '-framerate', '30',
            '-offset_x', str(x), '-offset_y', str(y),
            '-video_size', f"{w}x{h}", '-i', 'desktop',
            # 오디오 캡처 (VB-Audio Virtual Cable)
            '-f', 'dshow',
            '-i', 'audio=CABLE Output(VB-Audio Virtual Cable)',
            # 코덱 설정
            '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
            '-c:a', 'aac', '-b:a', '128k',
            '-movflags', '+empty_moov+default_base_moof+frag_keyframe',
            output_video
        ]
        proc = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE)
        print(f"⏺[{idx}] 녹화 시작 (영상+오디오)")

        try:
             # 1초에 한 번씩 비디오 종료 여부를 확인
            while True:
                # FFmpeg가 이미 죽었으면 루프 탈출
                if proc.poll() is not None:
                    break

                # Selenium JS로 <video> 요소의 ended 속성 확인
                try:
                    ended = driver.execute_script(
                        "return document.querySelector('video')?.ended || false;"
                    )
                except Exception:
                    ended = False

                if ended:
                    print("🎬 영상 재생 종료 감지! 녹화 종료 중…")
                    proc.terminate()
                    break

                time.sleep(1)
            # 여기서 블록: FFmpeg 프로세스가 종료(혹은 터미널에서 Ctrl+C)될 때까지 대기
            proc.wait()
        except KeyboardInterrupt:
            # Ctrl+C로 인터럽트 시—cleanup 로직
            stop_flag[0] = True
            proc.terminate()
            thread.join(timeout=5)
            save_comments(output_csv, comments_data)
            driver.quit()
            sys.exit(0)
        