import os
import sys
import time
import glob
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

# 3. 설정 / Configuration
OMNI_MODEL = os.getenv("OMNI_MODEL", "gemini-omni-flash-preview")
INPUT_DIR = os.getenv("OUTPUT_DIR", "./output")

# 4. 파일 업로드 및 활성화 대기 함수 / Upload media file and wait for indexing
def upload_and_wait_file(filepath):
    """Upload video file and poll active state."""
    print(f"-> Uploading media to server: {os.path.basename(filepath)}")
    file_obj = client.files.upload(file=filepath)
    
    state_str = str(file_obj.state).upper()
    while "PROCESSING" in state_str:
        print("   Indexing video on server... (Waiting 10s)")
        time.sleep(10)
        file_obj = client.files.get(name=file_obj.name)
        state_str = str(file_obj.state).upper()
        
    if "FAILED" in state_str:
        raise ValueError(f"Server media indexing failed: {os.path.basename(filepath)}")
        
    print(f"   Upload complete & active: {file_obj.name}")
    return file_obj

def analyze_video(filepath):
    """Analyze video backdrop visual characteristics and report."""
    filename = os.path.basename(filepath)
    base_name = os.path.splitext(filename)[0]
    
    report_filename = f"{base_name}_analysis.txt"
    report_path = os.path.join(INPUT_DIR, report_filename)
    
    if os.path.exists(report_path):
        print(f"[Skip] Report '{report_filename}' already exists.")
        return True
        
    print(f"\n[Start] Requesting visual analysis for '{filename}'...")
    
    uploaded_file = None
    try:
        uploaded_file = upload_and_wait_file(filepath)
        
        prompt = """
	This is an AI-generated background video designed for use as a stage backdrop during a performance.
        Please analyze the video and provide the following details in Korean:
        
        1. [Stage Atmosphere] A summary of the video's overall mood, as well as the intended stage atmosphere and production concept (2–3 lines).
        2. [Visual Characteristics & Colors] An analysis of key objects, lighting forms, and the primary color palette (e.g., RGB tones).
        3. [Music Recommendations] Recommended musical style to complement the video as a backdrop (e.g., tempo, beat intensity, genre).
        4. [Hashtags] A list of hashtags suitable for production planning (at least 5, separated by commas).
        """
        
        print(f"-> Executing multimodal analysis with Gemini ({OMNI_MODEL})...")
        response = client.models.generate_content(
            model=OMNI_MODEL,
            contents=[uploaded_file, prompt]
        )
        
        with open(report_path, "w", encoding="utf-8") as rf:
            rf.write(response.text)
            
        print(f"[Success] Analysis complete! Report saved to: {report_path}")
        return True
        
    except errors.APIError as e:
        print(f"[API Error] Analysis failed for '{filename}': {e}")
        if e.code in [401, 403] or "unauthorized" in str(e).lower() or "API_KEY_INVALID" in str(e):
            print("Authentication error detected. Halting batch execution.")
            sys.exit(1)
        return False
    except Exception as e:
        print(f"[Exception] Unexpected error processing '{filename}': {e}")
        return False
    finally:
        if uploaded_file:
            try:
                print(f"-> Deleting temporary server file: {uploaded_file.name}")
                client.files.delete(name=uploaded_file.name)
            except Exception as clean_err:
                print(f"[Warning] Failed to delete temporary server file: {clean_err}")

def main():
    if not os.path.exists(INPUT_DIR):
        print(f"[Error] Video directory does not exist: {INPUT_DIR}")
        sys.exit(1)
        
    video_files = [
        f for f in glob.glob(os.path.join(INPUT_DIR, "*.mp4"))
        if not f.endswith("_merged.mp4")
    ]
    video_files.sort()
    
    if not video_files:
        print(f"[Warning] No backdrop video files found to analyze in {INPUT_DIR}.")
        return
        
    print(f"==================================================")
    print(f" Starting Gemini visual analysis for {len(video_files)} videos")
    print(f" Model: {OMNI_MODEL}")
    print(f" Report Directory: {os.path.abspath(INPUT_DIR)}")
    print(f"==================================================")
    
    success_count = 0
    fail_count = 0
    
    for i, filepath in enumerate(video_files):
        print(f"\n[Progress: {i+1}/{len(video_files)}]")
        success = analyze_video(filepath)
        if success:
            success_count += 1
        else:
            fail_count += 1
            
        if i < len(video_files) - 1:
            time.sleep(5)
            
    print(f"\n==================================================")
    print(" All video analysis tasks completed!")
    print(f" Success: {success_count} | Failed: {fail_count}")
    print(f"==================================================")

if __name__ == "__main__":
    main()
