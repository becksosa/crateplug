import subprocess
import os
import sys

#file paths for packaged binaries

def resource_path(relative):
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative)
    return os.path.join(os.path.abspath("."), relative)

#receive variables from server.py:
def download_video(url, output_dir,status_callback):

    output_template = os.path.join(output_dir, "%(title)s.%(ext)s")

    #command to download the audio:
    command = [
        resource_path("yt-dlp.exe"), #use yt-dlp
        "--no-playlist", #download only the video not the whole playlist
        "--ffmpeg-location", resource_path("ffmpeg.exe"),  #point to ffmpeg.exe
        "-x", #extract audio
        "--audio-format", "mp3", #tells it to use mp3 format
        "--audio-quality", "0", 
        "--print", "after_move:filepath", 
        "-o", output_template, #where and how to save the file
        url, #calls back to url variable previously defined
    ]

    process = subprocess.Popen(
        command,
        creationflags=0x08000000,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )

    current_prefix = ""

    for line in process.stdout:
        line = line.strip()
        lower = line.lower()

        # SUCCESS PREFIX
        if line.startswith("[") and "]" in line:
            current_prefix = line
            continue

        # SUCCESS FILE
        if line.endswith(".mp3"):
            status_callback(f"{current_prefix} mp3 downloaded")
            continue

        # FAILURES (from merged stderr)
        if "already been recorded in the archive" in lower:
            status_callback(f"{current_prefix} skipped (already downloaded)")

        elif "private video" in lower:
            status_callback(f"{current_prefix} download failed: private video")

        elif "age-restricted" in lower or "confirm your age" in lower:
            status_callback(f"{current_prefix} download failed: age restricted")

        elif "members-only" in lower or "join this channel" in lower:
            status_callback(f"{current_prefix} download failed: members-only video")

        elif "not available in your country" in lower or "geo-restricted" in lower:
            status_callback(f"{current_prefix} download failed: geo-blocked - try a new ip address :)")

        elif "requires login" in lower or "cookies" in lower:
            status_callback(f"{current_prefix} download failed: login required")

        elif "video unavailable" in lower or "has been removed" in lower:
            status_callback(f"{current_prefix} download failed: video unavailable")

        elif "429" in lower or "rate limit" in lower:
            status_callback(f"{current_prefix} session rate limited: try a new ip address")

        elif "timed out" in lower or "connection reset" in lower:
            status_callback(f"{current_prefix} download failed: network error")

        elif "unsupported url" in lower:
            status_callback("invalid URL: unsupported or malformed link")

        elif "no video formats found" in lower:
            status_callback("invalid URL: no downloadable video")

        elif "does not exist" in lower:
            status_callback("invalid URL: video or playlist does not exist")

        elif "unable to extract" in lower:
            status_callback("invalid URL: could not extract video data")

        elif "no entries found" in lower:
            status_callback("invalid URL: empty or invalid playlist")

        elif "error:" in lower:
            status_callback(f"{current_prefix} download failed: unidentified error")


    process.wait()
