#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
영상 및 음원 병합 스크립트 (자동 페이드 인/아웃, 자막 텍스트 삽입 & 루프 지원)
================================================================================

[기능 설명]
1. 시작 시 지정한 시간 동안 영상과 음원이 서서히 밝아지며 커지게(Fade-In) 할 수 있습니다.
2. 페이드 인 직후 지정한 텍스트(예: 곡명, 아티스트명)를 화면 중앙에 서서히 나타났다가
   사라지도록 세련되게 삽입할 수 있습니다 (macOS 한글 폰트 자동 감지 지원).
3. 음원 파일의 정확한 길이를 자동 측정하여, 노래가 끝나는 시점에 맞춰
   영상과 음원을 동시에 서서히 어두워지고 작아지게(Fade-Out) 처리합니다.
4. 백드롭 영상의 길이가 음원보다 짧을 경우, 음원 길이에 맞춰 영상을
   자동으로 무한 반복(Loop)시킨 후 끝부분에서 페이드 아웃합니다.

================================================================================
[사용법 1: 터미널 명령어 (CLI) 방식]
================================================================================
터미널에서 직접 비디오 파일과 음원 파일을 지정하여 실행할 수 있습니다.

기본 사용법 (페이드 아웃 2초):
    python3 merge_audio_fadeout.py --video output/backdrop_1.mp4 --audio input/songs/song.mp3 --output output/merged/result.mp4

페이드 인(1.5초) 직후 3초 동안 곡명 텍스트 삽입 + 끝날 때 페이드 아웃(3초):
    python3 merge_audio_fadeout.py -v output/backdrop_1.mp4 -a input/songs/song.mp3 -o output/merged/result.mp4 \
        --fade-in 1.5 --fade-out 3.0 --text "10CM - 그라데이션" --text-duration 3.0

================================================================================
[사용법 2: 파이썬 코드 내에서 모듈로 임포트하여 사용하는 방식]
================================================================================
다른 파이썬 스크립트에서 이 파일의 함수를 호출하여 사용할 수 있습니다.

    from merge_audio_fadeout import merge_video_audio_with_fadeout

    merge_video_audio_with_fadeout(
        video_path="./output/my_video.mp4",
        audio_path="./input/songs/my_song.mp3",
        output_path="./output/merged/my_song_backdrop.mp4",
        fade_in_duration=1.5,
        fade_out_duration=2.5,
        text="10CM - 그라데이션",
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
    """macOS에서 한글을 정상적으로 표현할 수 있는 기본 시스템 폰트 경로를 탐색합니다."""
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
    """ffprobe를 사용하여 미디어 파일(영상 또는 음원)의 정확한 재생 길이(초)를 반환합니다."""
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
        print(f"[오류] '{filepath}'의 길이를 읽을 수 없습니다: {e}")
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
    영상과 음원을 병합하면서 페이드 인/아웃 및 자막 텍스트 삽입을 적용합니다.
    
    :param video_path: 입력 비디오 파일 경로
    :param audio_path: 입력 음원 파일 경로
    :param output_path: 출력 파일 경로
    :param fade_out_duration: 페이드 아웃이 진행될 시간(초), 기본값 2.0초
    :param fade_in_duration: 페이드 인이 진행될 시간(초), 기본값 0.0초
    :param text: 페이드 인 직후 표시할 텍스트 문구
    :param text_duration: 텍스트가 화면에 유지되는 시간(초), 기본값 3.0초
    :param fontsize: 폰트 크기, 기본값 60
    :param fontcolor: 폰트 색상, 기본값 white
    :param fontfile: 사용할 TTF/TTC 폰트 경로 (미지정 시 자동 탐색)
    """
    if not os.path.exists(video_path):
        print(f"[오류] 비디오 파일을 찾을 수 없습니다: {video_path}")
        return False
    if not os.path.exists(audio_path):
        print(f"[오류] 음원 파일을 찾을 수 없습니다: {audio_path}")
        return False

    # 출력 디렉토리 자동 생성
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    # 1. 미디어 길이 측정
    video_duration = get_media_duration(video_path)
    audio_duration = get_media_duration(audio_path)

    if audio_duration <= 0:
        print("[오류] 음원 길이가 유효하지 않습니다.")
        return False

    # 2. 페이드 아웃 시작 지점 계산 (전체 음원 길이 - 페이드 시간)
    fade_start = max(0.0, audio_duration - fade_out_duration)

    print("=" * 60)
    print(f"[*] 병합 작업 시작")
    print(f"    - 비디오: {video_path} ({video_duration:.2f}초)")
    print(f"    - 음  원: {audio_path} ({audio_duration:.2f}초)")
    print(f"    - 출  력: {output_path}")
    if fade_in_duration > 0:
        print(f"    - 페이드 인 : 시작 후 {fade_in_duration}초 동안")
    if text:
        print(f"    - 텍스트 삽입: '{text}' ({fade_in_duration}초 시점부터 {text_duration}초간 표시)")
    print(f"    - 페이드 아웃: 끝내기 전 {fade_out_duration}초 동안 (시작 지점: {fade_start:.2f}초)")
    print("=" * 60)

    # 3. 비디오가 음원보다 짧으면 자동 루프(-stream_loop -1) 적용
    loop_video = video_duration < audio_duration
    if loop_video:
        print("  => [알림] 비디오가 음원보다 짧아, 음원이 끝날 때까지 영상을 자동 무한 반복(Loop)합니다.")

    # 4. FFmpeg 복합 필터 구성 (비디오/오디오 페이드 인/아웃 및 텍스트 삽입)
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

    # 텍스트 이미지 임시 파일 생성 (drawtext 필터 없이 PIL + overlay로 해결)
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

            # 텍스트 여백 및 크기 계산
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
            print("[경고] Pillow(PIL) 라이브러리가 없어 텍스트 삽입을 건너뜁니다. ('pip install pillow' 실행 필요)")
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

    # 5. FFmpeg 명령어 조립
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

    print("  => FFmpeg 인코딩 진행 중... (영상의 길이에 따라 몇 분 정도 소요될 수 있습니다)")
    try:
        res = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
        if res.returncode == 0:
            print(f"[성공] 파일이 안전하게 생성되었습니다: {output_path}")
            return True
        else:
            print("[오류] FFmpeg 실행 실패:")
            print(res.stderr)
            return False
    except Exception as e:
        print(f"[예외 발생] FFmpeg 실행 중 오류가 발생했습니다: {e}")
        return False
    finally:
        if temp_text_img and os.path.exists(temp_text_img):
            try:
                os.remove(temp_text_img)
            except Exception:
                pass

def main():
    parser = argparse.ArgumentParser(
        description="영상과 음원을 합치며, 페이드 인/아웃 및 텍스트 삽입을 지원합니다.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("-v", "--video", required=True, help="입력 비디오 파일 경로")
    parser.add_argument("-a", "--audio", required=True, help="입력 음원 파일 경로 (mp3, wav 등)")
    parser.add_argument("-o", "--output", required=True, help="출력 비디오 파일 경로 (.mp4)")
    parser.add_argument("-fo", "--fade-out", "--fade", type=float, default=2.0, dest="fade_out", help="페이드 아웃 시간(초), 기본값: 2.0")
    parser.add_argument("-fi", "--fade-in", type=float, default=0.0, dest="fade_in", help="페이드 인 시간(초), 기본값: 0.0")
    parser.add_argument("-t", "--text", type=str, default=None, help="페이드 인 직후 화면 중앙에 삽입할 텍스트")
    parser.add_argument("-td", "--text-duration", type=float, default=3.0, dest="text_duration", help="텍스트 표시 유지 시간(초), 기본값: 3.0")
    parser.add_argument("-fs", "--fontsize", type=int, default=60, help="텍스트 폰트 크기, 기본값: 60")
    parser.add_argument("-fc", "--fontcolor", type=str, default="white", help="텍스트 색상, 기본값: white")
    parser.add_argument("-ff", "--fontfile", type=str, default=None, help="사용할 TTF/TTC 폰트 파일 경로 (미지정 시 자동 감지)")

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
