import os
import shutil
import whisper

# directories
audio_dir = "audios"            # input folder containing audio
finished_dir = "finished"            # where to move processed files
transcriptions_dir = "transcriptions"  # where to save text outputs

# create output dirs if not exist
os.makedirs(finished_dir, exist_ok=True)
os.makedirs(transcriptions_dir, exist_ok=True)

# load whisper model
model = whisper.load_model("small")

# iterate over all files in audio_dir
for filename in os.listdir(audio_dir):
    filepath = os.path.join(audio_dir, filename)

    # skip non-audio files
    if not filename.lower().endswith((".mp3", ".wav", ".m4a", ".flac", ".ogg")):
        continue

    transcript_path = os.path.join(
        transcriptions_dir, os.path.splitext(filename)[0] + ".txt"
    )
    if os.path.exists(transcript_path) and os.path.getsize(transcript_path) > 0:
        print(f"skipping {filename} (transcript exists)")
        shutil.move(filepath, os.path.join(finished_dir, filename))
        continue

    print(f"transcribing {filename}...")

    # transcribe
    result = model.transcribe(filepath)

    # save transcription
    with open(transcript_path, "w", encoding="utf-8") as f:
        f.write(result["text"].strip())

    # move processed file
    shutil.move(filepath, os.path.join(finished_dir, filename))

print("done.")
