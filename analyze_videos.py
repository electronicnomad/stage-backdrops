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
    print("[오류 / Error] API 키가 설정되지 않았습니다. / API key is not configured.")
    print("프로젝트 루트 디렉토리의 .env 파일에 'GEMINI_KEY=your_key' 형식으로 키를 입력해 주세요.")
    sys.exit(1)

client = genai.Client(api_key=gemini_key)

# 3. 설정 / Configuration
OMNI_MODEL = os.getenv("OMNI_MODEL", "gemini-omni-flash-preview")
INPUT_DIR = os.getenv("OUTPUT_DIR", "./output")

# 4. 파일 업로드 및 활성화 대기 함수 / Upload media file and wait for indexing
def upload_and_wait_file(filepath):
    """Gemini File API에 비디오 업로드 및 활성화 상태 폴링 / Upload video file and poll active state"""
    print(f"-> 서버로 미디어 업로드 중 / Uploading media: {os.path.basename(filepath)}")
    file_obj = client.files.upload(file=filepath)
    
    state_str = str(file_obj.state).upper()
    while "PROCESSING" in state_str:
        print("   서버에서 비디오 인덱싱 중... (10초 대기) / Indexing video on server... (Waiting 10s)")
        time.sleep(10)
        file_obj = client.files.get(name=file_obj.name)
        state_str = str(file_obj.state).upper()
        
    if "FAILED" in state_str:
        raise ValueError(f"서버 미디어 인덱싱 실패 / Indexing failed: {os.path.basename(filepath)}")
        
    print(f"   업로드 완료 및 활성화 상태 / Upload active: {file_obj.name}")
    return file_obj

def analyze_video(filepath):
    """비디오 분위기, 색상, 추천 음악 분석 리포트 작성 / Analyze video backdrop visual characteristics and report"""
    filename = os.path.basename(filepath)
    base_name = os.path.splitext(filename)[0]
    
    report_filename = f"{base_name}_analysis.txt"
    report_path = os.path.join(INPUT_DIR, report_filename)
    
    # 중복 분석 방지 / Skip if report already exists
    if os.path.exists(report_path):
        print(f"[건너뛰기 / Skip] '{report_filename}'이(가) 이미 존재합니다.")
        return True
        
    print(f"\n[시작 / Start] '{filename}' 비주얼 분석 요청 중 / Requesting visual analysis...")
    
    uploaded_file = None
    try:
        uploaded_file = upload_and_wait_file(filepath)
        
        prompt = """
        이 비디오는 공연 백월(backdrop) 무대용으로 AI로 생성된 배경 영상입니다.
        이 비디오에 대해 다음 항목들을 분석해서 한국어로 작성해 주세요:
        
        1. [무대 연출 분위기] 영상 전체의 감성, 어울리는 무대 연출 의도 및 분위기 요약 (2-3줄)
        2. [비주얼 특징 & 색상] 주요 오브젝트 및 빛(조명)의 형태, 핵심 색상 톤(RGB 감성 등) 분석
        3. [음악 매칭 추천] 이 영상에 무대 배경으로 어울리는 추천 음악 분위기 (템포, 비트 강도, 장르 등)
        4. [해시태그] 공연 기획에서 쓸 수 있는 연출 해시태그 목록 (쉼표로 구분하여 최소 5개)
        """
        
        print(f"-> Gemini 모델 ({OMNI_MODEL}) 멀티모달 분석 실행 중...")
        response = client.models.generate_content(
            model=OMNI_MODEL,
            contents=[uploaded_file, prompt]
        )
        
        with open(report_path, "w", encoding="utf-8") as rf:
            rf.write(response.text)
            
        print(f"[성공 / Success] 분석 완료! 리포트 파일 저장 완료: {report_path}")
        return True
        
    except errors.APIError as e:
        print(f"[API 오류 / API Error] '{filename}' 분석 실패: {e}")
        if e.code in [401, 403] or "unauthorized" in str(e).lower() or "API_KEY_INVALID" in str(e):
            print("인증 오류가 발견되어 작업을 강제 중단합니다.")
            sys.exit(1)
        return False
    except Exception as e:
        print(f"[예외 발생 / Exception] '{filename}' 처리 중 에러: {e}")
        return False
    finally:
        if uploaded_file:
            try:
                print(f"-> 서버 임시 비디오 파일 삭제 중 / Deleting temp server file: {uploaded_file.name}")
                client.files.delete(name=uploaded_file.name)
            except Exception as clean_err:
                print(f"[경고 / Warning] 서버 임시 파일 삭제 실패: {clean_err}")

def main():
    if not os.path.exists(INPUT_DIR):
        print(f"[오류 / Error] 비디오 디렉토리가 존재하지 않습니다: {INPUT_DIR}")
        sys.exit(1)
        
    video_files = [
        f for f in glob.glob(os.path.join(INPUT_DIR, "*.mp4"))
        if not f.endswith("_merged.mp4")
    ]
    video_files.sort()
    
    if not video_files:
        print(f"[경고 / Warning] 분석할 백월 비디오가 {INPUT_DIR} 디렉토리에 없습니다.")
        return
        
    print(f"==================================================")
    print(f" 총 {len(video_files)}개 비디오의 Gemini 분석을 시작합니다.")
    print(f" 사용 모델 / Model: {OMNI_MODEL}")
    print(f" 리포트 저장 위치 / Output path: {os.path.abspath(INPUT_DIR)}")
    print(f"==================================================")
    
    success_count = 0
    fail_count = 0
    
    for i, filepath in enumerate(video_files):
        print(f"\n[분석 진행률 / Progress: {i+1}/{len(video_files)}]")
        success = analyze_video(filepath)
        if success:
            success_count += 1
        else:
            fail_count += 1
            
        if i < len(video_files) - 1:
            time.sleep(5)
            
    print(f"\n==================================================")
    print("모든 비디오 분석 작업이 완료되었습니다 / All video analysis completed.")
    print(f"성공 / Success: {success_count}개 | 실패 / Failed: {fail_count}개")
    print(f"==================================================")

if __name__ == "__main__":
    main()
