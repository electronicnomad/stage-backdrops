import time
import os
import sys
import glob
import json
import subprocess
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
    print("[오류 / Error] API 키가 설정되지 않았습니다. / API key is not configured.")
    print("프로젝트 루트 디렉토리의 .env 파일에 'GEMINI_KEY=your_key' 형식으로 키를 입력하시거나,")
    print("시스템 환경 변수 'GEMINI_API_KEY'를 설정해 주세요.")
    sys.exit(1)

client = genai.Client(api_key=gemini_key)

# 3. 설정 파일 로드 / Load pipeline configuration file
CONFIG_PATH = "./config_prompts.json"
if not os.path.exists(CONFIG_PATH):
    print(f"[오류 / Error] 설정 파일 '{CONFIG_PATH}'이 존재하지 않습니다. / Configuration file does not exist.")
    sys.exit(1)

with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    config = json.load(f)

VEO_MODEL = config.get("veo_model", "veo-3.1-generate-preview")
GENERATOR_MODEL = config.get("prompt_generator_model", "gemini-2.5-flash")
OUTPUT_DIR = config.get("output_dir", "./output")
LYRICS_DIR = config.get("lyrics_dir", "./input/lyrics")
PROMPTS_DIR = config.get("prompts_dir", "./input/prompts")
NUM_OUTPUTS = config.get("num_outputs", 3)
POLLING_TIMEOUT_SEC = config.get("polling_timeout_sec", 900)
POLLING_INTERVAL_SEC = config.get("polling_interval_sec", 20)
DEFAULT_PROMPT = config.get("default_prompt", "")
SONG_PROMPTS = config.get("song_prompts", {})

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(LYRICS_DIR, exist_ok=True)
os.makedirs(PROMPTS_DIR, exist_ok=True)
os.makedirs("./scratch", exist_ok=True)

def format_duration(seconds):
    """초를 분과 초 형태의 읽기 쉬운 문자열로 변환합니다. / Converts seconds into a human-readable duration string."""
    mins = int(seconds // 60)
    secs = int(seconds % 60)
    if mins > 0:
        return f"{mins}분 {secs}초 ({mins}m {secs}s)"
    return f"{secs}초 ({secs}s)"

def find_image_file(song_name, img_dir="./input/images"):
    """곡명에 일치하는 스타일 레퍼런스 이미지 검색 / Locate style reference image for a given song"""
    img_exts = ['.png', '.jpg', '.jpeg', '.PNG', '.JPG']
    if not os.path.exists(img_dir):
        return None
    for ext in img_exts:
        path = os.path.join(img_dir, f"{song_name}{ext}")
        if os.path.exists(path):
            return path
    return None

def find_media_file(song_name, media_dir="./input/songs"):
    """곡명에 일치하는 참조 미디어(음원/영상) 파일 검색 / Locate reference media file for a given song"""
    if not os.path.exists(media_dir):
        return None
    media_exts = [
        '.mp4', '.mov', '.mkv', '.avi', '.flv', '.webm',
        '.mp3', '.wav', '.m4a', '.ogg', '.flac',
        '.MP4', '.MOV', '.MKV', '.AVI', '.FLV', '.WEBM',
        '.MP3', '.WAV', '.M4A', '.OGG', '.FLAC'
    ]
    for ext in media_exts:
        path = os.path.join(media_dir, f"{song_name}{ext}")
        if os.path.exists(path):
            return path
    return None

def save_prompt(song_name, prompt_text, prompts_dir="./input/prompts"):
    """생성된 프롬프트 순차 아카이빙 및 저장 / Sequentially archive and save generated prompt"""
    os.makedirs(prompts_dir, exist_ok=True)
    index = 1
    while True:
        filepath = os.path.join(prompts_dir, f"{song_name}_prompt_{index}.txt")
        if not os.path.exists(filepath):
            with open(filepath, "w", encoding="utf-8") as pf:
                pf.write(prompt_text)
            print(f"      [프롬프트 저장 완료 / Prompt Saved] {filepath}")
            return filepath
        index += 1

def scan_batch_jobs():
    """디렉토리 내의 리소스를 스캔하여 배치 작업 동적 생성 / Dynamically scan input directories to build batch jobs"""
    img_dir = "./input/images"
    media_dir = "./input/songs"
    
    img_exts = ['*.png', '*.jpg', '*.jpeg', '*.PNG', '*.JPG']
    media_exts = [
        '*.mp4', '*.mov', '*.mkv', '*.avi', '*.flv', '*.webm',
        '*.mp3', '*.wav', '*.m4a', '*.ogg', '*.flac',
        '*.MP4', '*.MOV', '*.MKV', '*.AVI', '*.FLV', '*.WEBM',
        '*.MP3', '*.WAV', '*.M4A', '*.OGG', '*.FLAC'
    ]
    
    img_files = []
    if os.path.exists(img_dir):
        for ext in img_exts:
            img_files.extend(glob.glob(os.path.join(img_dir, ext)))
            
    media_files = []
    if os.path.exists(media_dir):
        for ext in media_exts:
            media_files.extend(glob.glob(os.path.join(media_dir, ext)))
        
    songs = set()
    for f in img_files:
        base = os.path.splitext(os.path.basename(f))[0]
        songs.add(base)
        
    for f in media_files:
        base = os.path.splitext(os.path.basename(f))[0]
        songs.add(base)
        
    jobs = []
    for song in sorted(list(songs)):
        prompt = SONG_PROMPTS.get(song, DEFAULT_PROMPT)
        jobs.append({
            "song_name": song,
            "base_concept": prompt
        })
        
    return jobs

def extract_audio(media_path, song_name):
    """비디오/미디어 파일에서 오디오 트랙 추출 / Extract audio track from media file using FFmpeg"""
    ext = os.path.splitext(media_path)[1].lower()
    # 이미 오디오 파일인 경우 별도 추출 없이 원본 파일 경로 리턴 / Return original path if already audio
    if ext in ['.mp3', '.wav', '.m4a', '.ogg', '.flac']:
        print(f"   -> [{song_name}] 오디오 파일 감지됨 / Audio file detected ({media_path}).")
        return media_path
        
    temp_audio_path = os.path.join("./scratch", f"{song_name}_temp.mp3")
    print(f"   -> [{song_name}] 오디오 추출 중 / Extracting audio ({media_path} -> {temp_audio_path})...")
    
    # FFmpeg를 이용하여 오디오 트랙 추출 / Extract audio stream via FFmpeg
    cmd = ["ffmpeg", "-y", "-i", media_path, "-vn", "-acodec", "libmp3lame", "-q:a", "4", temp_audio_path]
    result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    if result.returncode == 0 and os.path.exists(temp_audio_path):
        return temp_audio_path
    else:
        print(f"      [경고 / Warning] 오디오 추출 실패. / Audio extraction failed.")
        return None

def extract_lyrics(client, audio_file_path, song_name, model_name):
    """Gemini API를 이용한 가사 전사 / Transcribe song lyrics using Gemini API"""
    print(f"   -> [{song_name}] 가사 추출 진행 중 / Transcribing lyrics (Gemini API)...")
    
    # 1. Gemini File API에 업로드 / Upload audio to Gemini File API
    uploaded_audio = client.files.upload(file=audio_file_path)
    
    try:
        # 2. 오디오 분석을 통한 가사 추출 / Transcribe lyrics from audio stream
        prompt = "Please transcribe the lyrics of the song in this audio file. If the song is in Korean, transcribe it in Korean. Output only the lyrics text, formatting it line by line, without any introduction, explanations, or metadata."
        
        response = client.models.generate_content(
            model=model_name,
            contents=[uploaded_audio, prompt]
        )
        lyrics = response.text.strip()
        return lyrics, uploaded_audio
    except Exception as e:
        client.files.delete(name=uploaded_audio.name)
        raise e

def analyze_media_style(client, uploaded_file, song_name, model_name):
    """Gemini API를 이용한 사운드 및 음악 스타일 분석 / Analyze sound style and mood using Gemini API"""
    print(f"   -> [{song_name}] 음악 스타일 분석 중 / Analyzing sound style (Gemini API)...")
    prompt = (
        "Analyze the audio of this song and describe the following characteristics in English:\n"
        "1. Overall Mood and Emotion (e.g., dreamy, nostalgic, energetic)\n"
        "2. Tempo and Dynamics (e.g., slow acoustic drift, fast upbeat pulse)\n"
        "3. Recommended Color Palette (e.g., warm golden light, pastel pinks and purples)\n"
        "4. Ideal motion pacing for a stage backdrop video.\n"
        "Please provide the output as a concise, structured bulleted list (under 80 words) without any introduction."
    )
    
    response = client.models.generate_content(
        model=model_name,
        contents=[uploaded_file, prompt]
    )
    return response.text.strip()

def generate_rich_prompt(client, image_path, lyrics, music_style, song_name, base_concept, config, model_name):
    """멀티모달 요소들을 결합하여 Veo 최적화 연출 프롬프트 합성 / Synthesize enriched visual prompt for Veo"""
    print(f"   -> [{song_name}] 멀티모달 프롬프트 합성 중 / Building enriched visual prompt...")
    
    uploaded_image = None
    contents = []
    
    # 이미지 파일이 존재하면 업로드하여 포함 / Upload style reference image if present
    if image_path and os.path.exists(image_path):
        print(f"      스타일 이미지 업로드 중 / Uploading style reference: {image_path}")
        uploaded_image = client.files.upload(file=image_path)
        contents.append(uploaded_image)
        
    user_prompt = config["prompt_generator_user_template"].format(
        song_name=song_name,
        base_concept=base_concept,
        lyrics=lyrics if lyrics else "No lyrics available.",
        music_style=music_style if music_style else "No style analysis available."
    )
    contents.append(user_prompt)
    
    try:
        response = client.models.generate_content(
            model=model_name,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=config["prompt_generator_system_instruction"]
            )
        )
        rich_prompt = response.text.strip()
        return rich_prompt, uploaded_image
    except Exception as e:
        if uploaded_image:
            client.files.delete(name=uploaded_image.name)
        raise e

def generate_video_job(job):
    """곡 단위 배치 작업 수행 / Process video generation job for a single song"""
    song = job["song_name"]
    base_concept = job["base_concept"]
    
    # 대상 디렉토리에 존재하는 기존 비디오 파일 개수 확인 / Count existing output files
    existing_files = glob.glob(os.path.join(OUTPUT_DIR, f"{song}_backdrop_*.mp4"))
    existing_count = len(existing_files)
    
    if existing_count >= NUM_OUTPUTS:
        print(f"[건너뛰기 / Skip] '{song}' 관련 영상이 이미 총 {existing_count}개 존재합니다 (목표: {NUM_OUTPUTS}개).")
        return True
        
    num_needed = NUM_OUTPUTS - existing_count
    
    # 중복되지 않는 비어 있는 파일 인덱스 결정 / Find vacant file indices
    needed_indices = []
    index = 1
    while len(needed_indices) < num_needed:
        filename = f"{song}_backdrop_{index}.mp4"
        filepath = os.path.join(OUTPUT_DIR, filename)
        if not os.path.exists(filepath):
            needed_indices.append(index)
        index += 1
        
    print(f"\n[시작 / Start] '{song}' 영상 생성 프로세스 가동 (현재 {existing_count}개 존재 -> {num_needed}개 추가 생성 예정)")
    
    # 미디어 자산 탐색 / Locate reference assets
    image_path = find_image_file(song)
    media_path = find_media_file(song)
    
    lyrics = ""
    music_style = ""
    temp_audio_path = None
    uploaded_files_to_clean = []
    
    # 1단계: 가사 및 스타일 분석 (캐시 재사용) / Phase 1: Lyrics & Sound Style Analysis
    if media_path:
        lyrics_file_path = os.path.join(LYRICS_DIR, f"{song}_lyrics.txt")
        style_file_path = os.path.join(LYRICS_DIR, f"{song}_music_style.txt")
        
        # 가사 캐시 재사용 확인 / Load cached lyrics
        if os.path.exists(lyrics_file_path):
            print(f"      [가사 캐시 재사용 / Cache Hit] {lyrics_file_path}")
            with open(lyrics_file_path, "r", encoding="utf-8") as lf:
                lyrics = lf.read()
                
        # 스타일 캐시 재사용 확인 / Load cached sound style
        if os.path.exists(style_file_path):
            print(f"      [스타일 캐시 재사용 / Cache Hit] {style_file_path}")
            with open(style_file_path, "r", encoding="utf-8") as sf:
                music_style = sf.read()
                
        # 캐시가 없는 경우 오디오 분석 수행 / Perform audio analysis if cache misses
        if not lyrics or not music_style:
            temp_audio_path = extract_audio(media_path, song)
            if temp_audio_path:
                try:
                    print(f"      [업로드 / Upload] 분석용 오디오 파일 업로드 중 (Gemini API)...")
                    uploaded_audio = client.files.upload(file=temp_audio_path)
                    uploaded_files_to_clean.append(uploaded_audio)
                    
                    if not lyrics:
                        lyrics_prompt = "Please transcribe the lyrics of the song in this audio file. If the song is in Korean, transcribe it in Korean. Output only the lyrics text, formatting it line by line, without any introduction, explanations, or metadata."
                        print(f"   -> [{song}] 가사 추출 진행 중...")
                        response = client.models.generate_content(
                            model=GENERATOR_MODEL,
                            contents=[uploaded_audio, lyrics_prompt]
                        )
                        lyrics = response.text.strip()
                        with open(lyrics_file_path, "w", encoding="utf-8") as lf:
                            lf.write(lyrics)
                        print(f"      [가사 저장 완료 / Saved] {lyrics_file_path}")
                        
                    if not music_style:
                        music_style = analyze_media_style(client, uploaded_audio, song, GENERATOR_MODEL)
                        with open(style_file_path, "w", encoding="utf-8") as sf:
                            sf.write(music_style)
                        print(f"      [스타일 저장 완료 / Saved] {style_file_path}")
                except Exception as e:
                    print(f"      [경고 / Warning] 미디어 분석 중 오류 발생: {e}")
            
    # 2단계: 프롬프트 강화 작업 / Phase 2: Prompt Enrichment
    rich_prompt = base_concept
    try:
        rich_prompt_result, uploaded_image = generate_rich_prompt(
            client, image_path, lyrics, music_style, song, base_concept, config, GENERATOR_MODEL
        )
        if uploaded_image:
            uploaded_files_to_clean.append(uploaded_image)
        rich_prompt = rich_prompt_result
    except Exception as e:
        print(f"      [경고 / Warning] 강화 프롬프트 생성 실패 (기본 콘셉트 사용): {e}")
        
    print(f"\n      >>> 합성된 강화 프롬프트 / Enriched Prompt:")
    print(f"      {rich_prompt}\n")
    
    # 생성된 프롬프트 아카이빙 저장 / Archive enriched prompt
    save_prompt(song, rich_prompt, PROMPTS_DIR)
    
    # Gemini 임시 파일 정리 / Clean up uploaded Gemini files
    for f in uploaded_files_to_clean:
        try:
            client.files.delete(name=f.name)
            print(f"      [정리 / Cleaned] Gemini 임시 파일 삭제 완료: {f.name}")
        except Exception as e:
            print(f"      [경고 / Warning] Gemini 임시 파일 삭제 실패: {e}")
            
    # 로컬 임시 오디오 파일 정리 / Clean up local temp audio file
    if temp_audio_path and os.path.exists(temp_audio_path) and temp_audio_path != media_path:
        os.remove(temp_audio_path)
        print(f"      [정리 / Cleaned] 로컬 임시 오디오 파일 삭제 완료: {temp_audio_path}")
        
    # 3단계: Veo 모델 비디오 생성 / Phase 3: Veo Video Generation
    success_all = True
    
    for i, index in enumerate(needed_indices):
        filename = f"{song}_backdrop_{index}.mp4"
        filepath = os.path.join(OUTPUT_DIR, filename)
        
        print(f"\n   -> [{song}] {index}/{NUM_OUTPUTS} 번째 영상 생성 중 / Generating video...")
        
        single_start_time = time.time()
        start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"      시작 시각 / Start Time: {start_timestamp}")
        
        try:
            operation = client.models.generate_videos(
                model=VEO_MODEL,
                prompt=rich_prompt,
                config=types.GenerateVideosConfig(
                    aspect_ratio="16:9",
                    resolution="1080p",
                ),
            )
            
            start_time = time.time()
            while not operation.done:
                elapsed = time.time() - start_time
                if elapsed > POLLING_TIMEOUT_SEC:
                    print(f"      [오류 / Timeout] 대기 시간 초과 ({POLLING_TIMEOUT_SEC}초 경과)")
                    success_all = False
                    break
                    
                time.sleep(POLLING_INTERVAL_SEC)
                operation = client.operations.get(operation)
                
            if not operation.done:
                continue
                
            generated_video = operation.response.generated_videos[0]
            video_bytes = client.files.download(file=generated_video.video)
            with open(filepath, "wb") as f:
                f.write(video_bytes)
                
            single_elapsed = time.time() - single_start_time
            end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"      끝난 시각 / End Time: {end_timestamp}")
            print(f"      소요 시간 / Duration: {format_duration(single_elapsed)}")
            print(f"      [성공 / Success] 비디오 파일 저장 완료: {filepath}")
            
        except errors.APIError as e:
            print(f"      [API 오류 / API Error] 생성 실패: {e}")
            if e.code in [401, 403] or "unauthorized" in str(e).lower() or "API_KEY_INVALID" in str(e):
                print("인증 오류가 발견되어 작업을 중단합니다. / Authentication error, stopping batch.")
                sys.exit(1)
            success_all = False
        except Exception as e:
            print(f"      [예외 발생 / Exception] 처리 중 예상치 못한 에러: {e}")
            success_all = False
            
        if i < len(needed_indices) - 1:
            time.sleep(5)
            
    return success_all

def main():
    batch_jobs = scan_batch_jobs()
    
    if not batch_jobs:
        print("[경고 / Warning] 스캔된 작업이 없습니다. ./input/images 또는 ./input/songs 디렉토리를 확인하세요.")
        return
        
    print(f"==================================================")
    print(f" 백월 영상 배치 생성을 시작합니다 / Starting backdrop video batch pipeline.")
    print(f" 총 작업 수 / Total jobs: {len(batch_jobs)}개 (곡당 {NUM_OUTPUTS}개 생성)")
    print(f" 저장 경로 / Output dir: {os.path.abspath(OUTPUT_DIR)}")
    print(f" 분석 모델 / Prompt Model: {GENERATOR_MODEL} | 생성 모델 / Video Model: {VEO_MODEL}")
    print(f"==================================================")
    
    for idx, job in enumerate(batch_jobs):
        print(f" - [{job['song_name']}] (기본 컨셉: {job['base_concept'][:60]}...)")
        
    success_count = 0
    fail_count = 0
    total_start_time = time.time()
    
    for i, job in enumerate(batch_jobs):
        total_elapsed = time.time() - total_start_time
        print(f"\n[작업 진행률 / Progress: {i+1}/{len(batch_jobs)}] (누적 소요 시간: {format_duration(total_elapsed)})")
        success = generate_video_job(job)
        
        if success:
            success_count += 1
        else:
            fail_count += 1
            
        if i < len(batch_jobs) - 1:
            print("다음 작업 대기 중 (15초) / Waiting for next job (15s)...")
            time.sleep(15)

    total_elapsed = time.time() - total_start_time
    print(f"\n==================================================")
    print("모든 비디오 생성 배치 작업이 완료되었습니다 / Batch generation completed.")
    print(f"총 누적 소요 시간 / Total elapsed time: {format_duration(total_elapsed)}")
    print(f"성공 / Success: {success_count}개 | 실패 / Failed: {fail_count}개")
    print(f"==================================================")

if __name__ == "__main__":
    main()
