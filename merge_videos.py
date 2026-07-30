import os
import sys
import subprocess
import glob
import re
from collections import defaultdict

# ==========================================
# 사용자 설정 변수
# ==========================================
USE_TRANSITION = True          # True: 자연스러운 페이드 효과 적용 (재인코딩 발생), False: 즉시 병합 (효과 없음)
TRANSITION_TYPE = "fade"        # 페이드 종류 ("fade", "wipeleft", "slideleft", "circleopen" 등 FFmpeg xfade 필터 종류 지정 가능)
TRANSITION_DURATION = 1.0       # 페이드 겹침 시간 (초 단위, 예: 1.0초 동안 서서히 전환)
# ==========================================

def get_video_duration(filepath):
    """ffprobe를 사용하여 비디오의 정확한 길이를 초 단위로 획득합니다."""
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        filepath
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(res.stdout.strip())
    except Exception:
        # ffprobe 호출 실패 시 Veo Preview 비디오 기본값인 5.0초 반환
        return 5.0

def build_xfade_filter(files, transition="fade", duration=1.0):
    """다중 파일 병합을 위한 FFmpeg xfade 복합 필터 그래프를 동적으로 구성합니다."""
    durations = [get_video_duration(f) for f in files]
    
    filter_str = ""
    current_out = "[0:v]"
    current_offset = durations[0] - duration
    
    for idx in range(1, len(files)):
        next_in = f"[{idx}:v]"
        next_out = f"[v{idx}]"
        
        # xfade 필터 체인 조립 (프레임 단위 오프셋 정밀 계산)
        filter_str += f"{current_out}{next_in}xfade=transition={transition}:duration={duration}:offset={current_offset:.3f}"
        
        if idx == len(files) - 1:
            filter_str += "[outv]"
        else:
            filter_str += f"{next_out}; "
            
        current_out = next_out
        current_offset = current_offset + durations[idx] - duration
        
    return filter_str

def get_group_name(filename):
    name = os.path.splitext(filename)[0]
    name = name.replace("_backdrop", "")
    name = re.sub(r"_\d+$", "", name)
    return name

def merge_videos():
    input_dir = "./output"
    output_dir = "./output/merged"
    
    if not os.path.exists(input_dir):
        print(f"[오류] 입력 디렉토리가 존재하지 않습니다: {input_dir}")
        sys.exit(1)
        
    os.makedirs(output_dir, exist_ok=True)
        
    video_files = [
        f for f in glob.glob(os.path.join(input_dir, "*.mp4")) 
        if not f.endswith("_merged.mp4")
    ]
    
    if not video_files:
        print(f"[경고] 병합할 비디오 파일이 {input_dir}에 존재하지 않습니다.")
        return
        
    groups = defaultdict(list)
    for filepath in video_files:
        filename = os.path.basename(filepath)
        group_key = get_group_name(filename)
        groups[group_key].append(filepath)
        
    print(f"==================================================")
    print(f" 파일명 유사성 기반 그룹 병합 작업을 시작합니다.")
    print(f" 전환 효과 사용 여부: {USE_TRANSITION}")
    if USE_TRANSITION:
        print(f" 전환 효과 타입: {TRANSITION_TYPE} (전환 시간: {TRANSITION_DURATION}초)")
    print(f"==================================================")
    
    list_file_path = "temp_inputs.txt"
    
    for group_key, files in groups.items():
        if len(files) < 2:
            print(f"\n[-] 그룹 '{group_key}': 파일이 1개 뿐이므로 병합을 건너뜁니다. ({os.path.basename(files[0])})")
            continue
            
        # 순서 정렬
        def get_file_index(filepath):
            match = re.search(r"_(\d+)\.mp4$", filepath)
            return int(match.group(1)) if match else 0
            
        files.sort(key=get_file_index)
        
        base_output_name = f"{group_key}_merged.mp4"
        output_file = os.path.join(output_dir, base_output_name)
        if os.path.exists(output_file):
            index = 1
            while True:
                new_output_name = f"{group_key}_merged_{index}.mp4"
                new_output_file = os.path.join(output_dir, new_output_name)
                if not os.path.exists(new_output_file):
                    output_file = new_output_file
                    break
                index += 1
        
        print(f"\n[+] 그룹 '{group_key}' 병합 중 ({len(files)}개 파일)...")
        
        try:
            if USE_TRANSITION:
                # ----------------------------------------------------
                # 전환 효과(Crossfade)를 동반한 병합 (재인코딩 필요)
                # ----------------------------------------------------
                print("  => 영상 분석 및 FFmpeg xfade 전환 필터 그래프 빌드 중...")
                
                # ffmpeg 명령 조립
                ffmpeg_cmd = ["ffmpeg", "-y"]
                for f in files:
                    ffmpeg_cmd.extend(["-i", f])
                    
                filter_graph = build_xfade_filter(files, transition=TRANSITION_TYPE, duration=TRANSITION_DURATION)
                
                ffmpeg_cmd.extend([
                    "-filter_complex", filter_graph,
                    "-map", "[outv]",
                    "-c:v", "libx264",       # 고화질 H.264 코덱 설정
                    "-pix_fmt", "yuv420p",    # 재생 기기 호환성 극대화 포맷
                    "-preset", "medium",      # 인코딩 속도/압축률 균형 프리셋
                    output_file
                ])
                
                print("  => 비디오 전환 렌더링 중 (시간이 다소 소요될 수 있습니다)...")
                result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
                
            else:
                # ----------------------------------------------------
                # 즉시 병합 (스트림 단순 복사, 인코딩 없음)
                # ----------------------------------------------------
                with open(list_file_path, "w", encoding="utf-8") as lf:
                    for video in files:
                        abs_path = os.path.abspath(video)
                        lf.write(f"file '{abs_path}'\n")
                        
                ffmpeg_cmd = [
                    "ffmpeg",
                    "-y",
                    "-f", "concat",
                    "-safe", "0",
                    "-i", list_file_path,
                    "-c", "copy",
                    output_file
                ]
                print("  => 비디오 스트림 복사 중 (효과 없음)...")
                result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
                
            if result.returncode == 0:
                print(f"  => [성공] 병합 완료: {os.path.basename(output_file)}")
            else:
                print(f"  => [오류] FFmpeg 프로세스 실패")
                print(f"  Stderr:\n{result.stderr}")
                
        except Exception as e:
            print(f"  => [예외 발생] 병합 과정에서 에러 발생: {e}")
            
        finally:
            if os.path.exists(list_file_path):
                os.remove(list_file_path)
                
    print(f"\n==================================================")
    print("모든 그룹 병합 프로세스가 끝났습니다!")
    print(f"==================================================")

if __name__ == "__main__":
    merge_videos()
