#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
Audio & Video Merging Script
(Auto Fade-In/Out, Text Overlay & Looping)
================================================================================

[Description]
1. Applies a gradual visual and audio fade-in at the start of the video.
2. Renders custom text overlay (e.g. title/artist) with smooth fade effects.
3. Automatically calculates audio duration and applies synchronized fade-out.
4. Automatically loops the video track if its duration is shorter than the audio track.

================================================================================
[CLI Usage]
================================================================================
    python3 merge_audio_fadeout.py -v output/backdrop_1.mp4 -a input/songs/song.mp3 -o output/merged/result.mp4 \
        --fade-in 1.5 --fade-out 3.0 --text "10CM - Gradation" --text-duration 3.0

================================================================================
[Python Module Usage]
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
    """Detect default system font path on macOS."""
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
    """Get media duration in seconds using ffprobe."""
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
        print(f"[Error] Could not read duration of '{filepath}': {e}")
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
    Merge video and audio tracks with fade effects and text overlay.
    
    :param video_path: Input video file path
    :param audio_path: Input audio file path
    :param output_path: Output merged file path
    :param fade_out_duration: Fade-out duration in seconds
    :param fade_in_duration: Fade-in duration in seconds
    :param text: Text string to overlay
    :param text_duration: Text display duration in seconds
    :param fontsize: Font size
    :param fontcolor: Font color
    :param fontfile: Path to TTF/TTC font file
    """
    if not os.path.exists(video_path):
        print(f"[Error] Video file not found: {video_path}")
        return False
    if not os.path.exists(audio_path):
        print(f"[Error] Audio file not found: {audio_path}")
        return False

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    video_duration = get_media_duration(video_path)
    audio_duration = get_media_duration(audio_path)

    if audio_duration <= 0:
        print("[Error] Audio duration is invalid.")
        return False

    fade_start = max(0.0, audio_duration - fade_out_duration)

    print("=" * 60)
    print(f"[*] Starting Audio-Video Merge Process")
    print(f"    - Video : {video_path} ({video_duration:.2f}s)")
    print(f"    - Audio : {audio_path} ({audio_duration:.2f}s)")
    print(f"    - Output: {output_path}")
    if fade_in_duration > 0:
        print(f"    - Fade-In : {fade_in_duration}s from start")
    if text:
        print(f"    - Text Overlay: '{text}' (display for {text_duration}s at t={fade_in_duration}s)")
    print(f"    - Fade-Out: {fade_out_duration}s before end (starts at t={fade_start:.2f}s)")
    print("=" * 60)

    loop_video = video_duration < audio_duration
    if loop_video:
        print("  => [Info] Video is shorter than audio. Enabling automatic video looping.")

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
            print("[Warning] Pillow library not installed. Skipping text overlay.")
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

    print("  => Encoding merged video with FFmpeg...")
    try:
        res = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
        if res.returncode == 0:
            print(f"[Success] Merged file successfully saved: {output_path}")
            return True
        else:
            print("[Error] FFmpeg execution failed:")
            print(res.stderr)
            return False
    except Exception as e:
        print(f"[Exception] Exception occurred during FFmpeg encoding: {e}")
        return False
    finally:
        if temp_text_img and os.path.exists(temp_text_img):
            try:
                os.remove(temp_text_img)
            except Exception:
                pass

def main():
    parser = argparse.ArgumentParser(
        description="Merge video and audio tracks with automatic fade-in/out and text overlay.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("-v", "--video", required=True, help="Input video file path")
    parser.add_argument("-a", "--audio", required=True, help="Input audio file path (.mp3, .wav, etc.)")
    parser.add_argument("-o", "--output", required=True, help="Output video file path (.mp4)")
    parser.add_argument("-fo", "--fade-out", "--fade", type=float, default=2.0, dest="fade_out", help="Fade-out duration in seconds (default: 2.0)")
    parser.add_argument("-fi", "--fade-in", type=float, default=0.0, dest="fade_in", help="Fade-in duration in seconds (default: 0.0)")
    parser.add_argument("-t", "--text", type=str, default=None, help="Text string to overlay in screen center")
    parser.add_argument("-td", "--text-duration", type=float, default=3.0, dest="text_duration", help="Text display duration in seconds (default: 3.0)")
    parser.add_argument("-fs", "--fontsize", type=int, default=60, help="Text font size (default: 60)")
    parser.add_argument("-fc", "--fontcolor", type=str, default="white", help="Text font color (default: white)")
    parser.add_argument("-ff", "--fontfile", type=str, default=None, help="Path to custom TTF/TTC font file")

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
