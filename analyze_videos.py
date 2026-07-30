import os
import sys
import time
import glob
from google import genai
from google.genai import types
from google.genai import errors
from dotenv import load_dotenv

# 1. 환경 변수 로드 (.env 파일이 있으면 읽어옴)
load_dotenv()

# 2. GEMINI API 키 설정 및 클라이언트 초기화
gemini_key = os.getenv("GEMINI_KEY")
if not gemini_key or gemini_key == "YOUR_GEMINI_API_KEY":
    gemini_key = os.getenv("GEMINI_API_KEY")

if not gemini_key:
    print("[오류] API 키가 설정되지 않았습니다.")
    print("프로젝트 루트 디렉토리의 .env 파일에 'GEMINI_KEY=your_key' 형식으로 키를 입력하시거나,")
    print("시스템 환경 변수 'GEMINI_API_KEY'를 설정해 주세요.")
    sys.exit(1)

client = genai.Client(api_key=gemini_key)

# 3. 설정
OMNI_MODEL = os.getenv("OMNI_MODEL", "gemini-omni-flash-preview")
INPUT_DIR = os.getenv("OUTPUT_DIR", "./output")

# 4. 파일 업로드 및 서버 측 처리 대기 함수
def upload_and_wait_file(filepath):
    print(f"-> 서버로 미디어 업로드 중: {os.path.basename(filepath)}")
    file_obj = client.files.upload(file=filepath)
    
    # 비디오 파일은 PROCESSING 상태에서 ACTIVE가 될 때까지 대기가 필요합니다.
    state_str = str(file_obj.state).upper()
    while "PROCESSING" in state_str:
        print("   서버에서 비디오 인덱싱 중... (10초 대기)")
        time.sleep(10)
        file_obj = client.files.get(name=file_obj.name)
        state_str = str(file_obj.state).upper()
        
    if "FAILED" in state_str:
        raise ValueError(f"서버 미디어 인덱싱 실패: {os.path.basename(filepath)}")
        
    print(f"   업로드 완료 및 활성화 상태: {file_obj.name}")
    return file_obj

def analyze_video(filepath):
    filename = os.path.basename(filepath)
    base_name = os.path.splitext(filename)[0]
    
    # 분석 리포트 저장 파일 설정
    report_filename = f"{base_name}_analysis.txt"
    report_path = os.path.join(INPUT_DIR, report_filename)
    
    # 중복 분석 방지 (이미 텍스트 리포트가 있으면 건너뜀)
    if os.path.exists(report_path):
        print(f"[건너뛰기] '{report_filename}'이(가) 이미 존재합니다.")
        return True
        
    print(f"\n[시작] '{filename}' 비주얼 분석 요청 중...")
    
    uploaded_file = None
    try:
        # 비디오 파일 업로드 & 활성화 대기
        uploaded_file = upload_and_wait_file(filepath)
        
        # 분석을 위한 멀티모달 프롬프트 설정
        prompt = """
        이 비디오는 공연 백월(backdrop) 무대용으로 AI로 생성된 배경 영상입니다.
        이 비디오에 대해 다음 항목들을 분석해서 한국어로 작성해 주세요:
        
        1. [무대 연출 분위기] 영상 전체의 감성, 어울리는 무대 연출 의도 및 분위기 요약 (2-3줄)
        2. [비주얼 특징 & 색상] 주요 오브젝트 및 빛(조명)의 형태, 핵심 색상 톤(RGB 감성 등) 분석
        3. [음악 매칭 추천] 이 영상에 무대 배경으로 어울리는 추천 음악 분위기 (템포, 비트 강도, 장르 등)
        4. [해시태그] 공연 기획에서 쓸 수 있는 연출 해시태그 목록 (쉼표로 구분하여 최소 5개)
        """
        
        print(f"-> Gemini Omni ({OMNI_MODEL}) 모델을 사용한 멀티모달 분석 실행 중...")
        response = client.models.generate_content(
            model=OMNI_MODEL,
            contents=[uploaded_file, prompt]
        )
        
        # 분석 보고서 파일 쓰기
        with open(report_path, "w", encoding="utf-8") as rf:
            rf.write(response.text)
            
        print(f"[성공] 분석 완료! 리포트 파일 저장 완료: {report_path}")
        return True
        
    except errors.APIError as e:
        print(f"[API 오류] '{filename}' 분석 실패: {e}")
        if e.code in [401, 403] or "unauthorized" in str(e).lower() or "API_KEY_INVALID" in str(e):
            print("인증 오류가 발견되어 배치 작업을 강제 중단합니다.")
            sys.exit(1)
        return False
    except Exception as e:
        print(f"[예외 발생] '{filename}' 처리 중 예상치 못한 에러: {e}")
        return False
    finally:
        # 업로드한 임시 파일 즉시 청소
        if uploaded_file:
            try:
                print(f"-> 서버 임시 비디오 파일 삭제 중: {uploaded_file.name}")
                client.files.delete(name=uploaded_file.name)
            except Exception as clean_err:
                print(f"[경고] 서버 임시 파일 삭제 실패: {clean_err}")

def main():
    if not os.path.exists(INPUT_DIR):
        print(f"[오류] 비디오 디렉토리가 존재하지 않습니다: {INPUT_DIR}")
        sys.exit(1)
        
    # output 아래의 개별 백월 비디오 스캔 (이미 병합된 *_merged.mp4 제외)
    video_files = [
        f for f in glob.glob(os.path.join(INPUT_DIR, "*.mp4"))
        if not f.endswith("_merged.mp4")
    ]
    
    # 순서 정렬
    video_files.sort()
    
    if not video_files:
        print(f"[경고] 분석할 백월 비디오가 {INPUT_DIR} 디렉토리에 없습니다.")
        return
        
    print(f"==================================================")
    print(f" 총 {len(video_files)}개 비디오의 Gemini Omni 분석을 시작합니다.")
    print(f" 사용 모델: {OMNI_MODEL}")
    print(f" 리포트 저장 위치: {os.path.abspath(INPUT_DIR)}")
    print(f"==================================================")
    
    success_count = 0
    fail_count = 0
    
    for i, filepath in enumerate(video_files):
        print(f"\n[분석 진행률: {i+1}/{len(video_files)}]")
        success = analyze_video(filepath)
        if success:
            success_count += 1
        else:
            fail_count += 1
            
        # API 제한 조율을 위한 대기
        if i < len(video_files) - 1:
            time.sleep(5)
            
    print(f"\n==================================================")
    print("모든 비디오 분석 배치 작업이 끝났습니다!")
    print(f"성공: {success_count}개 / 실패: {fail_count}개")
    print(f"==================================================")

if __name__ == "__main__":
    main()
