#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
영상 및 음원 병합 스크립트 / Audio & Video Merging Script
(자동 페이드 인/아웃, 자막 텍스트 삽입 & 루프 지원 / Auto Fade-In/Out, Text Overlay & Looping)
================================================================================

[기능 설명 / Description]
1. 시작 시 지정한 시간 동안 영상과 음원이 서서히 밝아지며 커집니다 (Fade-In).
   Applies a gradual visual and audio fade-in at the start of the video.
2. 페이드 인 직후 지정한 텍스트(예: 곡명, 아티스트명)를 화면 중앙에 표시합니다.
   Renders custom text overlay (e.g. title/artist) with smooth fade effects.
3. 음원 파일의 길이에 맞춰 끝나는 시점에 동시에 페이드 아웃(Fade-Out)합니다.
   Automatically calculates audio duration and applies synchronized fade-out.
4. 비디오가 음원보다 짧을 경우, 음원에 맞춰 영상이 자동 루프(Loop)됩니다.
   Automatically loops the video track if its duration is shorter than the audio track.

================================================================================
[사용법 1: CLI 방식 / Usage 1: Command Line Interface]
================================================================================
    python3 merge_audio_fadeout.py -v output/backdrop_1.mp4 -a input/songs/song.mp3 -o output/merged/result.mp4 \
        --fade-in 1.5 --fade-out 3.0 --text "10CM - Gradation" --text-duration 3.0

================================================================================
[사용법 2: Python 모듈 방식 / Usage 2: Python Import]
================================================================================
    from merge_audio_fadeout import merge_video_audio_with_fadeout

    merge_video_audio_with_fadeout(
        video_path="./output/my_video.mp4",
        audio_path="./input/songs/my_song.mp3",
        output_path="./output/merged/my_song_backdrop.mp4",
        fade_in_duration=1.5,
        fade_out_duration=2.5,
        text="10CM - Gradation",
        text_duration=3.0,
        fontsize=64
    )
================================================================================
"""

import os
import sys
import argparse
import subprocess

def get_default_fontfile():
    """macOS 기본 한글/시스템 폰트 경로 탐색 / Detect default system font path on macOS"""
    candidates = [
        "/System/Library/Fonts/AppleSDGothicNeo.ttc",
        "/System/Library/Fonts/Supplemental/AppleGothic.ttf",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/Library/Fonts/Arial Unicode.ttf",
        "/System/Library/Fonts/Helvetica.ttc"
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return ""

def get_media_duration(filepath):
    """ffprobe를 사용한 정확한 미디어 재생 시간(초) 측정 / Get media duration in seconds using ffprobe"""
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
    except Exception as e:
        print(f"[오류 / Error] '{filepath}' 재생 길이를 읽을 수 없습니다: {e}")
        return 0.0

def merge_video_audio_with_fadeout(
    video_path,
    audio_path,
    output_path,
    fade_out_duration=2.0,
    fade_in_duration=0.0,
    text=None,
    text_duration=3.0,
    fontsize=60,
    fontcolor="white",
    fontfile=None
):
    """
    영상과 음원을 병합하며 페이드 인/아웃 및 자막 텍스트 오버레이 적용 /
    Merge video and audio tracks with fade effects and text overlay.
    
    :param video_path: 입력 비디오 파일 경로 / Input video file path
    :param audio_path: 입력 음원 파일 경로 / Input audio file path
    :param output_path: 출력 파일 경로 / Output merged file path
    :param fade_out_duration: 페이드 아웃 시간(초) / Fade-out duration in seconds
    :param fade_in_duration: 페이드 인 시간(초) / Fade-in duration in seconds
    :param text: 오버레이 텍스트 문구 / Text string to overlay
    :param text_duration: 텍스트 표시 시간(초) / Text display duration in seconds
    :param fontsize: 폰트 크기 / Font size
    :param fontcolor: 폰트 색상 / Font color
    :param fontfile: 폰트 파일 경로 / Path to TTF/TTC font file
    """
    if not os.path.exists(video_path):
        print(f"[오류 / Error] 비디오 파일을 찾을 수 없습니다: {video_path}")
        return False
    if not os.path.exists(audio_path):
        print(f"[오류 / Error] 음원 파일을 찾을 수 없습니다: {audio_path}")
        return False

    # 출력 디렉토리 자동 생성 / Ensure output directory exists
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    # 1. 미디어 길이 측정 / Measure media durations
    video_duration = get_media_duration(video_path)
    audio_duration = get_media_duration(audio_path)

    if audio_duration <= 0:
        print("[오류 / Error] 음원 길이가 유효하지 않습니다.")
        return False

    # 2. 페이드 아웃 시작 시점 계산 / Calculate fade-out start timestamp
    fade_start = max(0.0, audio_duration - fade_out_duration)

    print("=" * 60)
    print(f"[*] 병합 작업 시작 / Starting Audio-Video Merge")
    print(f"    - 비디오 / Video: {video_path} ({video_duration:.2f}s)")
    print(f"    - 음  원 / Audio: {audio_path} ({audio_duration:.2f}s)")
    print(f"    - 출  력 / Output: {output_path}")
    if fade_in_duration > 0:
        print(f"    - 페이드 인 / Fade-In: {fade_in_duration}s")
    if text:
        print(f"    - 텍스트 오버레이 / Text: '{text}' ({text_duration}s)")
    print(f"    - 페이드 아웃 / Fade-Out: {fade_out_duration}s (Start: {fade_start:.2f}s)")
    print("=" * 60)

    # 3. 비디오가 짧을 경우 자동 루프 적용 / Auto-loop video if shorter than audio
    loop_video = video_duration < audio_duration
    if loop_video:
        print("  => [알림 / Info] 비디오가 음원보다 짧아 자동 무한 반복(Loop)을 적용합니다.")

    # 4. FFmpeg 복합 필터 구성 / Construct FFmpeg complex filtergraph
    v_filters = []
    a_filters = []
    
    if fade_in_duration > 0:
        v_filters.append(f"fade=t=in:st=0:d={fade_in_duration}")
        a_filters.append(f"afade=t=in:st=0:d={fade_in_duration}")
        
    if fade_out_duration > 0:
        v_filters.append(f"fade=t=out:st={fade_start:.3f}:d={fade_out_duration}")
        a_filters.append(f"afade=t=out:st={fade_start:.3f}:d={fade_out_duration}")
        
    v_filter_str = ",".join(v_filters) if v_filters else "null"
    a_filter_str = ",".join(a_filters) if a_filters else "anull"

    # 텍스트 오버레이 이미지 생성 (Pillow 라이브러리 활용) / Generate text overlay image using Pillow
    temp_text_img = None
    if text:
        try:
            from PIL import Image, ImageDraw, ImageFont
            temp_text_img = os.path.join("./scratch", f"temp_text_overlay_{os.getpid()}.png")
            os.makedirs("./scratch", exist_ok=True)
            
            if not fontfile:
                fontfile = get_default_fontfile()
            try:
                font = ImageFont.truetype(fontfile, fontsize) if fontfile else ImageFont.load_default()
            except Exception:
                font = ImageFont.load_default()

            # 텍스트 크기 계산 및 투명 PNG 생성 / Measure text bounds and create transparent PNG
            dummy_img = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
            dummy_draw = ImageDraw.Draw(dummy_img)
            bbox = dummy_draw.textbbox((0, 0), text, font=font)
            w = bbox[2] - bbox[0] + 80
            h = bbox[3] - bbox[1] + 80
            
            img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            draw.text((40 - bbox[0], 40 - bbox[1]), text, font=font, fill=fontcolor)
            img.save(temp_text_img, "PNG")
        except ImportError:
            print("[경고 / Warning] Pillow 라이브러리가 설치되어 있지 않아 텍스트 오버레이를 건너뜁니다.")
            text = None

    if text and temp_text_img and os.path.exists(temp_text_img):
        t_start = fade_in_duration
        t_end = t_start + text_duration
        fade_t = min(0.5, text_duration / 3.0)
        
        filter_complex = (
            f"[0:v]{v_filter_str}[v0];"
            f"[1:a]{a_filter_str}[a];"
            f"[2:v]format=rgba,fade=t=in:st={t_start:.3f}:d={fade_t:.3f}:alpha=1,fade=t=out:st={t_end-fade_t:.3f}:d={fade_t:.3f}:alpha=1[txt];"
            f"[v0][txt]overlay=(W-w)/2:(H-h)/2:enable='between(t,{t_start:.3f},{t_end:.3f})'[v]"
        )
    else:
        filter_complex = f"[0:v]{v_filter_str}[v];[1:a]{a_filter_str}[a]"

    # 5. FFmpeg 명령어 구성 및 실행 / Build and run FFmpeg command
    ffmpeg_cmd = ["ffmpeg", "-y"]
    
    if loop_video:
        ffmpeg_cmd.extend(["-stream_loop", "-1"])
        
    ffmpeg_cmd.extend([
        "-i", video_path,
        "-i", audio_path
    ])
    
    if text and temp_text_img and os.path.exists(temp_text_img):
        ffmpeg_cmd.extend(["-loop", "1", "-i", temp_text_img])
        
    ffmpeg_cmd.extend([
        "-filter_complex", filter_complex,
        "-map", "[v]",
        "-map", "[a]",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-preset", "medium",
        "-c:a", "aac",
        "-shortest",
        output_path
    ])

    print("  => FFmpeg 인코딩 실행 중 / Encoding video with FFmpeg...")
    try:
        res = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
        if res.returncode == 0:
            print(f"[성공 / Success] 병합 파일 저장 완료: {output_path}")
            return True
        else:
            print("[오류 / Error] FFmpeg 실행 실패:")
            print(res.stderr)
            return False
    except Exception as e:
        print(f"[예외 발생 / Exception] FFmpeg 실행 도중 에러: {e}")
        return False
    finally:
        if temp_text_img and os.path.exists(temp_text_img):
            try:
                os.remove(temp_text_img)
            except Exception:
                pass

def main():
    parser = argparse.ArgumentParser(
        description="영상과 음원을 합치며, 페이드 인/아웃 및 텍스트 오버레이를 지원합니다. / Merge video and audio tracks with fade and text overlay support.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("-v", "--video", required=True, help="입력 비디오 파일 경로 / Input video file path")
    parser.add_argument("-a", "--audio", required=True, help="입력 음원 파일 경로 / Input audio file path")
    parser.add_argument("-o", "--output", required=True, help="출력 비디오 파일 경로 / Output video file path")
    parser.add_argument("-fo", "--fade-out", "--fade", type=float, default=2.0, dest="fade_out", help="페이드 아웃 시간(초) / Fade-out duration (default: 2.0)")
    parser.add_argument("-fi", "--fade-in", type=float, default=0.0, dest="fade_in", help="페이드 인 시간(초) / Fade-in duration (default: 0.0)")
    parser.add_argument("-t", "--text", type=str, default=None, help="화면에 표시할 오버레이 텍스트 / Overlay text string")
    parser.add_argument("-td", "--text-duration", type=float, default=3.0, dest="text_duration", help="텍스트 표시 시간(초) / Text display duration (default: 3.0)")
    parser.add_argument("-fs", "--fontsize", type=int, default=60, help="폰트 크기 / Font size (default: 60)")
    parser.add_argument("-fc", "--fontcolor", type=str, default="white", help="폰트 색상 / Font color (default: white)")
    parser.add_argument("-ff", "--fontfile", type=str, default=None, help="폰트 파일 경로 / Custom font file path")

    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(0)

    args = parser.parse_args()
    merge_video_audio_with_fadeout(
        args.video,
        args.audio,
        args.output,
        fade_out_duration=args.fade_out,
        fade_in_duration=args.fade_in,
        text=args.text,
        text_duration=args.text_duration,
        fontsize=args.fontsize,
        fontcolor=args.fontcolor,
        fontfile=args.fontfile
    )

if __name__ == "__main__":
    main()
