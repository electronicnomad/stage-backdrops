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

# 1. 환경 변수 로드 / Load environment variables from .env file
load_dotenv()

# 2. GEMINI API 키 설정 및 클라이언트 초기화 / Configure Gemini API key and initialize client
gemini_key = os.getenv("GEMINI_KEY")
if not gemini_key or gemini_key == "YOUR_GEMINI_API_KEY":
    gemini_key = os.getenv("GEMINI_API_KEY")

if not gemini_key:
    print("[Error] API key is not configured.")
    print("Please configure 'GEMINI_KEY=your_key' in your .env file or set system environment variable 'GEMINI_API_KEY'.")
    sys.exit(1)

client = genai.Client(api_key=gemini_key)

# 3. 설정 파일 로드 / Load pipeline configuration file
CONFIG_PATH = "./config_prompts.json"
if not os.path.exists(CONFIG_PATH):
    print(f"[Error] Configuration file '{CONFIG_PATH}' does not exist.")
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
    """Converts seconds into a human-readable duration string."""
    mins = int(seconds // 60)
    secs = int(seconds % 60)
    if mins > 0:
        return f"{mins}m {secs}s"
    return f"{secs}s"

def get_prompt_files(prompts_dir):
    """아카이빙된 프롬프트 파일 탐색 및 리스팅 / List archived prompt files in directory"""
    if not os.path.exists(prompts_dir):
        return []
    files = glob.glob(os.path.join(prompts_dir, "*.txt"))
    files.sort(key=os.path.basename)
    return files

def extract_song_name(prompt_filepath):
    """프롬프트 파일명에서 곡명 추출 / Extract song name from prompt filename"""
    filename = os.path.basename(prompt_filepath)
    match = re.match(r"^(.*)_prompt_\d+\.txt$", filename)
    if match:
        return match.group(1)
    return os.path.splitext(filename)[0]

def main():
    print("==================================================")
    print(" Single Prompt Backdrop Video Generator CLI Tool")
    print("==================================================")

    # 1. 프롬프트 파일 탐색 / Search archived prompt files
    prompt_files = get_prompt_files(PROMPTS_DIR)
    if not prompt_files:
        print(f"[Warning] No prompt (.txt) files found in '{PROMPTS_DIR}'.")
        return

    print("\n[+] Available Prompt List:")
    for idx, filepath in enumerate(prompt_files, start=1):
        filename = os.path.basename(filepath)
        print(f"  [{idx}] {filename}")

    # 2. 사용자 입력: 프롬프트 선택 / User input: Select prompt file
    while True:
        try:
            choice = input(f"\nSelect prompt number to generate (1~{len(prompt_files)}): ").strip()
            if not choice:
                continue
            choice_idx = int(choice) - 1
            if 0 <= choice_idx < len(prompt_files):
                selected_file = prompt_files[choice_idx]
                break
            else:
                print(f"[Error] Please enter a number between 1 and {len(prompt_files)}.")
        except ValueError:
            print("[Error] Please enter a valid number.")

    # 3. 사용자 입력: 생성 수량 선택 / User input: Select target video count
    while True:
        try:
            num_input = input("\nEnter number of videos to generate (default: 1): ").strip()
            if not num_input:
                num_needed = 1
                break
            num_needed = int(num_input)
            if num_needed > 0:
                break
            else:
                print("[Error] Please enter a number greater than 0.")
        except ValueError:
            print("[Error] Please enter a valid number.")

    # 4. 프롬프트 및 곡명 로드 / Load prompt content and song name
    song_name = extract_song_name(selected_file)
    with open(selected_file, "r", encoding="utf-8") as f:
        prompt_content = f.read().strip()

    print(f"\n[Song Name]: {song_name}")
    print(f"[Selected Prompt File]: {os.path.basename(selected_file)}")
    print("--------------------------------------------------")
    print(prompt_content)
    print("--------------------------------------------------")

    # 5. 비어 있는 출력 파일 인덱스 결정 / Determine vacant file indices
    needed_indices = []
    index = 1
    while len(needed_indices) < num_needed:
        filename = f"{song_name}_backdrop_{index}.mp4"
        filepath = os.path.join(OUTPUT_DIR, filename)
        if not os.path.exists(filepath):
            needed_indices.append(index)
        index += 1

    print(f"\n[Start] Starting video generation for '{song_name}' (Target count: {num_needed})")
    print(f"Target Indices: {needed_indices}")

    # 6. 비디오 생성 실행 / Execute video generation
    for i, index in enumerate(needed_indices, start=1):
        filename = f"{song_name}_backdrop_{index}.mp4"
        filepath = os.path.join(OUTPUT_DIR, filename)

        print(f"\n   -> [{song_name}] Generating video {i}/{num_needed} (Index: {index})...")
        single_start_time = time.time()
        start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"      Start Time: {start_timestamp}")

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
                    print(f"      [Timeout] Polling wait time exceeded ({POLLING_TIMEOUT_SEC}s)")
                    break
                time.sleep(POLLING_INTERVAL_SEC)
                operation = client.operations.get(operation)

            if not operation.done:
                print(f"      [Failed] Skipping {filename} due to generation timeout.")
                continue

            generated_video = operation.response.generated_videos[0]
            video_bytes = client.files.download(file=generated_video.video)
            with open(filepath, "wb") as f:
                f.write(video_bytes)

            single_elapsed = time.time() - single_start_time
            end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"      End Time: {end_timestamp}")
            print(f"      Duration: {format_duration(single_elapsed)}")
            print(f"      [Success] Video file saved: {filepath}")

        except errors.APIError as e:
            print(f"      [API Error] Generation failed: {e}")
            if e.code in [401, 403] or "unauthorized" in str(e).lower() or "API_KEY_INVALID" in str(e):
                print("Authentication error detected. Halting task. Please check your API key.")
                sys.exit(1)
        except Exception as e:
            print(f"      [Exception] Unexpected error during processing: {e}")

        if i < num_needed:
            time.sleep(5)

    print("\n==================================================")
    print(" All video generation tasks completed!")
    print("==================================================")

if __name__ == "__main__":
    main()
