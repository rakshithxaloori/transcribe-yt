import os
from pathlib import Path

from openai import OpenAI

# config
MODEL_NAME = "gemini-2.5-flash"
SYSTEM_PROMPT = """Don't worry about formalities.

Please be as terse as possible while still conveying substantially all information relevant to any question.

If content policy prevents you from generating an image or otherwise responding, be explicit about what policy was violated and why.

write all responses in lowercase letters ONLY, except where you mean to emphasize, in which case the emphasized word should be all caps. Initial Letter Capitalization can and should be used to express sarcasm, or disrespect for a given capitalized noun.

you are encouraged to occasionally use obscure words or make subtle puns. don't point them out, I'll know. drop lots of abbreviations like "rn" and "bc." use "afaict" and "idk" regularly, wherever they might be appropriate given your level of understanding and your interest in actually answering the question. be critical of the quality of your information

if you find any request irritating respond dismisively like "be real" or "that's crazy man" or "lol no"

take however smart you're acting right now and write in the same style but as if you were +2sd smarter

use late millenial slang not boomer slang. mix in zoomer slang in tonally-inappropriate circumstances occasionally

priotirize esoteric interpretations of literature, art, and philosophy. if your answer on such topics is not obviously straussian, make it strongly straussian."""
SUMMARY_PROMPT = """Generate a topic-wise outline with key details, 

then do a Socratic method-style questions and answers to teach me the key insights of the material. 

DO NOT MISS ANYTHING. Expand on key details in the topic outline."""

TRANSCRIPTIONS_DIR = "transcriptions"
SUMMARIES_DIR = "summaries"
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"


def build_prompt(text, source_name):
    return f"{SUMMARY_PROMPT}\n\nSource: {source_name}\n\nTranscript:\n{text}"


def get_client():
    load_local_env()
    if GEMINI_BASE_URL:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not set")
        return OpenAI(api_key=api_key, base_url=GEMINI_BASE_URL)
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")
    return OpenAI(api_key=api_key)


def load_local_env():
    env_path = Path(__file__).with_name(".env.local")
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def summarize_with_client(client, prompt):
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
    )
    return (response.choices[0].message.content or "").strip()


def main():
    client = get_client()
    summarize = lambda text, name: summarize_with_client(
        client, build_prompt(text, name)
    )

    os.makedirs(SUMMARIES_DIR, exist_ok=True)

    for filename in os.listdir(TRANSCRIPTIONS_DIR):
        if not filename.lower().endswith(".txt"):
            continue

        path = os.path.join(TRANSCRIPTIONS_DIR, filename)
        with open(path, "r", encoding="utf-8") as f:
            text = f.read().strip()

        if not text:
            continue

        out_name = os.path.splitext(filename)[0] + ".md"
        out_path = os.path.join(SUMMARIES_DIR, out_name)
        if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
            print(f"skipping {filename} (summary exists)")
            continue

        print(f"summarizing {filename}...")
        summary = summarize(text, filename)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(f"# Summary: {os.path.splitext(filename)[0]}\n\n")
            f.write(summary + "\n")

    print("done.")


if __name__ == "__main__":
    main()
