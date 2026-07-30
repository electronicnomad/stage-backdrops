import os
import sys
import glob
import re
import json
import time
from datetime import datetime
from google import genai
from google.genai import types
from google.genai import errors
from dotenv import load_dotenv

# 1. 환경 변수 로드
load_dotenv()

# 2. GEMINI API 키 설정 및 클라이언트 초기화
gemini_key = os.getenv("GEMINI_KEY")
if not gemini_key or gemini_key == "YOUR_GEMINI_API_KEY":
    gemini_key = os.getenv("GEMINI_API_KEY")

if not gemini_key:
    print("[오류] API 키가 설정되지 않았습니다.")
    print("프로젝트 루트의 .env 파일에 'GEMINI_KEY=your_key' 형식으로 키를 입력해 주세요.")
    sys.exit(1)

client = genai.Client(api_key=gemini_key)

# 3. 설정 파일 로드
CONFIG_PATH = "./config_prompts.json"
if not os.path.exists(CONFIG_PATH):
    print(f"[오류] 설정 파일 '{CONFIG_PATH}'이 존재하지 않습니다.")
    sys.exit(1)

with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    config = json.load(f)

VEO_MODEL = config.get("veo_model", "veo-3.1-generate-preview")
OUTPUT_DIR = config.get("output_dir", "./output")
PROMPTS_DIR = config.get("prompts_dir", "./input/prompts")
POLLING_TIMEOUT_SEC = config.get("polling_timeout_sec", 900)
POLLING_INTERVAL_SEC = config.get("polling_interval_sec", 20)

os.makedirs(OUTPUT_DIR, exist_ok=True)


def format_duration(seconds):
    mins = int(seconds // 60)
    secs = int(seconds % 60)
    if mins > 0:
        return f"{mins}분 {secs}초"
    return f"{secs}초"


def get_prompt_files(prompts_dir):
    if not os.path.exists(prompts_dir):
        return []
    # prompts 디렉토리 하위의 txt 파일들을 리스팅
    files = glob.glob(os.path.join(prompts_dir, "*.txt"))
    # 파일명 순으로 정렬
    files.sort(key=os.path.basename)
    return files


def extract_song_name(prompt_filepath):
    filename = os.path.basename(prompt_filepath)
    # {song_name}_prompt_{index}.txt 패턴 매칭
    match = re.match(r"^(.*)_prompt_\d+\.txt$", filename)
    if match:
        return match.group(1)
    # 패턴 매칭이 안 될 경우 파일 이름에서 확장자를 제외한 값을 기본 곡명으로 사용
    return os.path.splitext(filename)[0]


def main():
    print("==================================================")
    print(" 저장된 프롬프트 기반 단일 비디오 생성 프로그램")
    print("==================================================")

    # 1. 프롬프트 파일 탐색 및 리스팅
    prompt_files = get_prompt_files(PROMPTS_DIR)
    if not prompt_files:
        print(f"[경고] '{PROMPTS_DIR}' 경로에 저장된 프롬프트(.txt) 파일이 존재하지 않습니다.")
        return

    print("\n[+] 사용 가능한 프롬프트 목록:")
    for idx, filepath in enumerate(prompt_files, start=1):
        filename = os.path.basename(filepath)
        print(f"  [{idx}] {filename}")

    # 2. 사용자 입력: 프롬프트 선택
    while True:
        try:
            choice = input(f"\n생성할 프롬프트 번호를 선택해 주세요 (1~{len(prompt_files)}): ").strip()
            if not choice:
                continue
            choice_idx = int(choice) - 1
            if 0 <= choice_idx < len(prompt_files):
                selected_file = prompt_files[choice_idx]
                break
            else:
                print(f"[오류] 1부터 {len(prompt_files)} 사이의 숫자를 입력해 주세요.")
        except ValueError:
            print("[오류] 올바른 숫자를 입력해 주세요.")

    # 3. 사용자 입력: 생성 개수 선택
    while True:
        try:
            num_input = input("\n생성할 영상 개수를 입력해 주세요 (기본: 1): ").strip()
            if not num_input:
                num_needed = 1
                break
            num_needed = int(num_input)
            if num_needed > 0:
                break
            else:
                print("[오류] 1개 이상의 개수를 입력해 주세요.")
        except ValueError:
            print("[오류] 올바른 숫자를 입력해 주세요.")

    # 4. 프롬프트 및 곡명 로드
    song_name = extract_song_name(selected_file)
    with open(selected_file, "r", encoding="utf-8") as f:
        prompt_content = f.read().strip()

    print(f"\n[선택된 곡명]: {song_name}")
    print(f"[선택된 프롬프트 파일]: {os.path.basename(selected_file)}")
    print("--------------------------------------------------")
    print(prompt_content)
    print("--------------------------------------------------")

    # 5. 저장할 파일명 인덱스 결정 (중복 방지)
    needed_indices = []
    index = 1
    while len(needed_indices) < num_needed:
        filename = f"{song_name}_backdrop_{index}.mp4"
        filepath = os.path.join(OUTPUT_DIR, filename)
        if not os.path.exists(filepath):
            needed_indices.append(index)
        index += 1

    print(f"\n[시작] '{song_name}' 영상 생성 프로세스 가동 (총 {num_needed}개 생성 예정)")
    print(f"저장될 인덱스 번호: {needed_indices}")

    # 6. 비디오 생성 실행
    for i, index in enumerate(needed_indices, start=1):
        filename = f"{song_name}_backdrop_{index}.mp4"
        filepath = os.path.join(OUTPUT_DIR, filename)

        print(f"\n   -> [{song_name}] {i}/{num_needed} 번째 영상 생성 중 (인덱스: {index})...")
        single_start_time = time.time()
        start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"      시작 시각: {start_timestamp}")

        try:
            operation = client.models.generate_videos(
                model=VEO_MODEL,
                prompt=prompt_content,
                config=types.GenerateVideosConfig(
                    aspect_ratio="16:9",
                    resolution="1080p",
                ),
            )

            start_time = time.time()
            while not operation.done:
                elapsed = time.time() - start_time
                if elapsed > POLLING_TIMEOUT_SEC:
                    print(f"      [오류] 대기 시간 초과 ({POLLING_TIMEOUT_SEC}초 경과)")
                    break
                time.sleep(POLLING_INTERVAL_SEC)
                operation = client.operations.get(operation)

            if not operation.done:
                print(f"      [실패] {filename} 생성 시간 초과로 패스합니다.")
                continue

            generated_video = operation.response.generated_videos[0]
            video_bytes = client.files.download(file=generated_video.video)
            with open(filepath, "wb") as f:
                f.write(video_bytes)

            single_elapsed = time.time() - single_start_time
            end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"      끝난 시각: {end_timestamp}")
            print(f"      소요 시간: {format_duration(single_elapsed)}")
            print(f"      [성공] 파일 저장 완료: {filepath}")

        except errors.APIError as e:
            print(f"      [API 오류] 생성 실패: {e}")
            if e.code in [401, 403] or "unauthorized" in str(e).lower() or "API_KEY_INVALID" in str(e):
                print("인증 오류가 발견되어 작업을 중단합니다. API 키를 다시 확인해 주세요.")
                sys.exit(1)
        except Exception as e:
            print(f"      [예외 발생] 처리 중 예상치 못한 에러: {e}")

        # 마지막 루프가 아니면 5초 대기
        if i < num_needed:
            time.sleep(5)

    print("\n==================================================")
    print(" 모든 비디오 생성 작업이 완료되었습니다!")
    print("==================================================")


if __name__ == "__main__":
    main()
