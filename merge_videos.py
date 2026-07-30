import os
import sys
import subprocess
import glob
import re
from collections import defaultdict

# ==========================================
# 사용자 설정 변수 / User Configuration Settings
# ==========================================
USE_TRANSITION = True          # True: 크로스페이드 효과 적용 / Apply crossfade transition (requires re-encoding)
TRANSITION_TYPE = "fade"        # 페이드 종류 / Transition filter type ("fade", "wipeleft", "slideleft", "circleopen", etc.)
TRANSITION_DURATION = 1.0       # 페이드 겹침 시간(초) / Crossfade duration in seconds
# ==========================================

def get_video_duration(filepath):
    """ffprobe를 사용하여 비디오 재생 시간을 초 단위로 측정 / Get video duration in seconds using ffprobe"""
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
        # ffprobe 실패 시 기본값 5.0초 반환 / Fallback to default 5.0s on failure
        return 5.0

def build_xfade_filter(files, transition="fade", duration=1.0):
    """다중 비디오 병합을 위한 FFmpeg xfade 필터 그래프 구성 / Dynamically build FFmpeg xfade filtergraph for multi-file concatenation"""
    durations = [get_video_duration(f) for f in files]
    
    filter_str = ""
    current_out = "[0:v]"
    current_offset = durations[0] - duration
    
    for idx in range(1, len(files)):
        next_in = f"[{idx}:v]"
        next_out = f"[v{idx}]"
        
        # xfade 필터 체인 조립 / Assemble xfade filter chain
        filter_str += f"{current_out}{next_in}xfade=transition={transition}:duration={duration}:offset={current_offset:.3f}"
        
        if idx == len(files) - 1:
            filter_str += "[outv]"
        else:
            filter_str += f"{next_out}; "
            
        current_out = next_out
        current_offset = current_offset + durations[idx] - duration
        
    return filter_str

def get_group_name(filename):
    """파일명에서 곡 그룹 키 추출 / Extract group key from video filename"""
    name = os.path.splitext(filename)[0]
    name = name.replace("_backdrop", "")
    name = re.sub(r"_\d+$", "", name)
    return name

def merge_videos():
    """같은 곡의 여러 백월 비디오를 그룹화하여 하나로 결합 / Concatenate video clips per song group with crossfade"""
    input_dir = "./output"
    output_dir = "./output/merged"
    
    if not os.path.exists(input_dir):
        print(f"[오류 / Error] 입력 디렉토리가 존재하지 않습니다: {input_dir}")
        sys.exit(1)
        
    os.makedirs(output_dir, exist_ok=True)
        
    video_files = [
        f for f in glob.glob(os.path.join(input_dir, "*.mp4")) 
        if not f.endswith("_merged.mp4")
    ]
    
    if not video_files:
        print(f"[경고 / Warning] 병합할 비디오 파일이 {input_dir}에 존재하지 않습니다.")
        return
        
    groups = defaultdict(list)
    for filepath in video_files:
        filename = os.path.basename(filepath)
        group_key = get_group_name(filename)
        groups[group_key].append(filepath)
        
    print(f"==================================================")
    print(f" 백월 비디오 그룹 병합 시작 / Starting video group concatenation")
    print(f" 전환 효과 적용 여부 / Use Transition: {USE_TRANSITION}")
    if USE_TRANSITION:
        print(f" 전환 필터 / Transition Type: {TRANSITION_TYPE} ({TRANSITION_DURATION}s)")
    print(f"==================================================")
    
    list_file_path = "temp_inputs.txt"
    
    for group_key, files in groups.items():
        if len(files) < 2:
            print(f"\n[-] 그룹 / Group '{group_key}': 파일이 1개이므로 건너뜁니다 ({os.path.basename(files[0])}).")
            continue
            
        # 순서 정렬 / Sort by index
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
        
        print(f"\n[+] 그룹 / Group '{group_key}' 병합 중 ({len(files)}개 파일 / files)...")
        
        try:
            if USE_TRANSITION:
                # 크로스페이드 전환 효과를 적용한 병합 / Concatenate with crossfade transition
                print("  => FFmpeg xfade 전환 필터 그래프 구성 중...")
                
                ffmpeg_cmd = ["ffmpeg", "-y"]
                for f in files:
                    ffmpeg_cmd.extend(["-i", f])
                    
                filter_graph = build_xfade_filter(files, transition=TRANSITION_TYPE, duration=TRANSITION_DURATION)
                
                ffmpeg_cmd.extend([
                    "-filter_complex", filter_graph,
                    "-map", "[outv]",
                    "-c:v", "libx264",
                    "-pix_fmt", "yuv420p",
                    "-preset", "medium",
                    output_file
                ])
                
                print("  => 비디오 전환 인코딩 중 / Rendering video transitions...")
                result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
                
            else:
                # 단순 스트림 복사 병합 / Simple stream copy concatenation
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
                print("  => 비디오 스트림 복사 중 / Copying video streams...")
                result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
                
            if result.returncode == 0:
                print(f"  => [성공 / Success] 병합 완료: {os.path.basename(output_file)}")
            else:
                print(f"  => [오류 / Error] FFmpeg 실행 실패")
                print(f"  Stderr:\n{result.stderr}")
                
        except Exception as e:
            print(f"  => [예외 발생 / Exception] 병합 중 에러: {e}")
            
        finally:
            if os.path.exists(list_file_path):
                os.remove(list_file_path)
                
    print(f"\n==================================================")
    print("모든 비디오 병합 작업 완료 / All video merge jobs completed.")
    print(f"==================================================")

if __name__ == "__main__":
    merge_videos()
