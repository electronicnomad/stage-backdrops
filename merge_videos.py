import os
import sys
import subprocess
import glob
import re
from collections import defaultdict

# ==========================================
# 사용자 설정 변수 / User Configuration Settings
# ==========================================
USE_TRANSITION = True          # True: Apply crossfade transition (requires re-encoding)
TRANSITION_TYPE = "fade"        # Transition filter type ("fade", "wipeleft", "slideleft", "circleopen", etc.)
TRANSITION_DURATION = 1.0       # Crossfade duration in seconds
# ==========================================

def get_video_duration(filepath):
    """Get video duration in seconds using ffprobe."""
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
        return 5.0

def build_xfade_filter(files, transition="fade", duration=1.0):
    """Dynamically build FFmpeg xfade filtergraph for multi-file concatenation."""
    durations = [get_video_duration(f) for f in files]
    
    filter_str = ""
    current_out = "[0:v]"
    current_offset = durations[0] - duration
    
    for idx in range(1, len(files)):
        next_in = f"[{idx}:v]"
        next_out = f"[v{idx}]"
        
        filter_str += f"{current_out}{next_in}xfade=transition={transition}:duration={duration}:offset={current_offset:.3f}"
        
        if idx == len(files) - 1:
            filter_str += "[outv]"
        else:
            filter_str += f"{next_out}; "
            
        current_out = next_out
        current_offset = current_offset + durations[idx] - duration
        
    return filter_str

def get_group_name(filename):
    """Extract group key from video filename."""
    name = os.path.splitext(filename)[0]
    name = name.replace("_backdrop", "")
    name = re.sub(r"_\d+$", "", name)
    return name

def merge_videos():
    """Concatenate video clips per song group with crossfade."""
    input_dir = "./output"
    output_dir = "./output/merged"
    
    if not os.path.exists(input_dir):
        print(f"[Error] Input directory does not exist: {input_dir}")
        sys.exit(1)
        
    os.makedirs(output_dir, exist_ok=True)
        
    video_files = [
        f for f in glob.glob(os.path.join(input_dir, "*.mp4")) 
        if not f.endswith("_merged.mp4")
    ]
    
    if not video_files:
        print(f"[Warning] No video files found to merge in {input_dir}.")
        return
        
    groups = defaultdict(list)
    for filepath in video_files:
        filename = os.path.basename(filepath)
        group_key = get_group_name(filename)
        groups[group_key].append(filepath)
        
    print(f"==================================================")
    print(f" Starting video group concatenation based on filename pattern")
    print(f" Use Transitions: {USE_TRANSITION}")
    if USE_TRANSITION:
        print(f" Transition Filter: {TRANSITION_TYPE} (Duration: {TRANSITION_DURATION}s)")
    print(f"==================================================")
    
    list_file_path = "temp_inputs.txt"
    
    for group_key, files in groups.items():
        if len(files) < 2:
            print(f"\n[-] Group '{group_key}': Only 1 file found. Skipping merge ({os.path.basename(files[0])}).")
            continue
            
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
        
        print(f"\n[+] Merging Group '{group_key}' ({len(files)} files)...")
        
        try:
            if USE_TRANSITION:
                print("  => Analyzing video files & constructing FFmpeg xfade filtergraph...")
                
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
                
                print("  => Rendering video transitions with FFmpeg...")
                result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
                
            else:
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
                print("  => Copying video streams without re-encoding...")
                result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
                
            if result.returncode == 0:
                print(f"  => [Success] Successfully merged: {os.path.basename(output_file)}")
            else:
                print(f"  => [Error] FFmpeg process failed")
                print(f"  Stderr:\n{result.stderr}")
                
        except Exception as e:
            print(f"  => [Exception] Exception occurred during merge: {e}")
            
        finally:
            if os.path.exists(list_file_path):
                os.remove(list_file_path)
                
    print(f"\n==================================================")
    print(" All video group merge tasks completed!")
    print(f"==================================================")

if __name__ == "__main__":
    merge_videos()
