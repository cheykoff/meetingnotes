import openai
import argparse
import sys
import os
import glob
import json
from datetime import datetime
from pydub import AudioSegment
import glob
from moviepy.editor import *


def split_audio(file, length=10):
    print("start split audio")
    audio = AudioSegment.from_mp3(file)
    audio_length_in_ms = len(audio)
    chunk_length_in_ms = length * 60 * 1000  # convert to milliseconds

    chunks = []
    for i in range(0, audio_length_in_ms, chunk_length_in_ms):
        chunks.append(audio[i:i + chunk_length_in_ms])

    for i, chunk in enumerate(chunks):
        chunk.export(f"{file[:-4]}_part{i+1}.mp3", format="mp3")


def check_and_split_files_in_directory(directory):
    print("start check and split files in directory")
    # Get a list of all .mp3 files in the directory
    mp3_files = glob.glob(os.path.join(directory, "*.mp3"))
    print("mp3_files: ", mp3_files)

    for file in mp3_files:
        audio = AudioSegment.from_mp3(file)
        audio_length_in_minutes = len(audio) / (60 * 1000)
        if audio_length_in_minutes > 10:
            split_audio(file)
            os.remove(file)


def check_existing_transcripts(directory):
    print("start check existing transcripts")
    # Get all txt files in the directory
    txt_files = glob.glob(directory + "/*.txt")

    if txt_files:  # Check if the list is not empty
        overwrite = input(
            f"Transcripts already exist in the directory '{directory}'. Do you want to overwrite them? [y/N]: ")
        if overwrite.lower() != "y":
            return False
    return True


def transcribe_audio(audio_file):
    print("start transcribe audio")
    try:
        with open(audio_file, "rb") as audio:
            transcript = openai.Audio.transcribe("whisper-1", audio)
            return transcript
    except FileNotFoundError:
        print(f"The file {audio_file} was not found.")
        sys.exit(1)  # Exit the script


def write_transcript_to_file(audio_file, transcript, directory):
    print("start write transcript to file")
    # Prepare the output file path
    txt_file_name = os.path.basename(audio_file).replace(".mp3", ".txt")

    output_file_path = os.path.join(
        directory, "transcriptions - txt", txt_file_name)
    output_dir = os.path.join(directory, "transcriptions - txt")

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    output_file_path = os.path.join(output_dir, txt_file_name)
    with open(output_file_path, "w", encoding="utf-8") as txt_file:
        txt_file.write(str(transcript))


def transcribe_all_audio_files_in_directory(directory):
    print("start transcribe all audio files in directory")
    # Check for existing transcripts at the beginning
    if not check_existing_transcripts(directory + "\\transcriptions - txt"):
        print("Aborted. No transcripts have been overwritten.")
        return

    # Glob pattern for all .mp3 files in the directory
    pattern = os.path.join(directory, "*.mp3")
    # Get a list of all .mp3 files in the directory
    audio_files = glob.glob(pattern)

    # Print the total number of audio files found
    num_files = len(audio_files)
    print(f"{num_files} audio files found")

    # Transcribe each audio file
    for i, audio_file in enumerate(audio_files, start=1):
        print(f"Transcribing {audio_file} ({i}/{num_files})")
        transcript = transcribe_audio(audio_file)
        write_transcript_to_file(audio_file, transcript, directory)

    # Print the total number of files successfully transcribed
    print(f"{num_files} files successfully transcribed")

    # If more than one file was transcribed, combine all transcripts into one
    if num_files > 1:
        combine_all_transcripts(directory)


def combine_all_transcripts(directory):
    print("start combine all transcripts")
    # Glob pattern for all .txt files in the directory
    output_file = directory + "\\combined_transcripts.json"

    pattern = os.path.join(directory, "transcriptions - txt", "*.txt")

    # Get a list of all .txt files in the directory
    txt_files = glob.glob(pattern)

    # Sort the text files alphabetically
    txt_files.sort()

    # Create a dictionary to hold the filename-content pairs
    transcripts = {}

    for fname in txt_files:
        with open(fname, encoding="utf-8") as infile:
            # Load the JSON content of the file into a Python dictionary
            content = json.load(infile)
            # Use the basename of the file (without the .txt extension) as the key
            key = os.path.basename(fname).replace(".txt", "")
            # Add the "text" value from the content dictionary to the transcripts dictionary
            transcripts[key] = content["text"]

    # Write the dictionary to the output file in JSON format
    with open(output_file, 'w', encoding="utf-8") as outfile:
        json.dump(transcripts, outfile, indent=4)

    print(f"All transcripts combined into '{output_file}'")


def create_plain_text_from_json(json_file, output_file):
    print("start create plain text from json")
    # Open the JSON file and load the data into a Python dictionary
    with open(json_file, 'r', encoding="utf-8") as jfile:
        data = json.load(jfile)

    # Open the output text file
    with open(output_file, 'w', encoding='utf-8') as txt_file:
        # Loop through each value in the dictionary
        for value in data.values():
            # Write the value to the text file
            txt_file.write(f"{value}\n")

    print(f"Plain text file '{output_file}' created from '{json_file}'")


def summarize_text(model, text):
    print("start summarize text")
    openai.api_key = os.environ["OPENAI_API_KEY"]

    response = openai.ChatCompletion.create(
        model=model,
        messages=[
            {"role": "system", "content": "Take the following text. Summarize the results and to dos in bullet points."},
            {"role": "user", "content": text}
        ]
    )
    return response['choices'][0]['message']['content'].strip()


def summarize_transcripts(directory):
    print("start summarize transcripts")
    # Read the input JSON document
    with open(directory + "\\combined_transcripts.json", "r", encoding="utf-8") as file:
        data = json.load(file)

    summary_data = {}

    # Iterate over the key-value pairs in the JSON object
    for key, value in data.items():
        # Generate the summary
        summary = summarize_text("gpt-3.5-turbo", value)
        # Store both the original and summarized texts
        summary_data[key] = {'original_text': value, 'summary': summary}

    # Write the data to a new JSON file
    with open(directory + "\\summary.json", "w", encoding="utf-8") as file:
        json.dump(summary_data, file, ensure_ascii=False, indent=4)


def format_to_markdown(json_file, output_file):
    print("start format to markdown")
    with open(json_file, "r", encoding="utf-8") as file:
        data = json.load(file)

    markdown_text = "# Meeting Summaries\n"

    current_datetime_and_title = ""
    for key, value in sorted(data.items()):
        if "_part" in key:
            print("_part in key", key)
            # Exclude the last part (e.g. "part1")
            meeting = key.split("_")[0:-1]
            meeting = "_".join(meeting)
        else:
            print("_part not in key", key)
            meeting = key

        date_object = datetime.strptime(meeting, "%Y_%m_%d_%H_%M_%S")
        datetime_and_title = date_object.strftime("%Y-%m-%d %H:%M")

        if datetime_and_title != current_datetime_and_title:
            # If datetime_and_title changes, add a new header
            markdown_text += f"\n## {datetime_and_title}\n"
            current_datetime_and_title = datetime_and_title

        markdown_text += f"{value['summary']}\n"

    with open(output_file, "w", encoding="utf-8") as file:
        file.write(markdown_text)


def main(directory):
    print("start main script in " + directory)
    check_and_split_files_in_directory(directory)
    transcribe_all_audio_files_in_directory(directory)
    combine_all_transcripts(directory)
    create_plain_text_from_json(
        directory + "\\combined_transcripts.json", directory + "\\combined_transcripts.txt")
    summarize_transcripts(directory)
    format_to_markdown(directory + "\\summary.json",
                       directory + "\\summary.md")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="Transcribe audio files in a directory.")
    parser.add_argument('directory', type=str,
                        help="The path to the directory containing the audio files.")
    args = parser.parse_args()

    # Make sure the path is a valid directory
    if os.path.isdir(args.directory):
        main(args.directory)
    else:
        print(f"Error: {args.directory} is not a valid directory.")
