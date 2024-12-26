import os
from datetime import datetime, timedelta
import pandas as pd
import requests
from dotenv import load_dotenv
from googleapiclient.discovery import build
from supabase import create_client, Client



def get_YT(api_key: str):
    """
    Returns an instance of the YouTube Data API service.
    """
    return build("youtube", "v3", developerKey=api_key)


def search_videos(youtube, query: str, days: int = 7, max_results: int = 50):
    """
    Search for videos on YouTube based on a term (query) with pagination.
    """
    date_video = (datetime.now() - timedelta(days=days)).isoformat("T") + "Z"
    results = []
    total_results = 0
    next_page_token = None

    while total_results < max_results:

        response = (
            youtube.search()
            .list(
                q=query,
                part="snippet",
                maxResults=min(50, max_results - total_results),
                type="video",
                publishedAfter=date_video,
                videoDuration="long",
                videoDefinition="high",
                order="relevance",
                pageToken=next_page_token
            )
            .execute()
        )

        for item in response.get("items", []):
            if video_id := item.get("id", {}).get("videoId"):
                video_response = (
                    youtube.videos()
                    .list(part="snippet,statistics,contentDetails", id=video_id)
                    .execute()
                )

                if video_response["items"]:
                    snippet = video_response["items"][0]["snippet"]
                    results.append(
                        {
                            "Title": snippet["title"],
                            "Description": snippet.get("description", "No Description"),
                            "channel": snippet["channelTitle"],
                            "Link": f"https://www.youtube.com/watch?v={video_id}",
                        }
                    )
        
        total_results += len(response.get("items", []))
        next_page_token = response.get("nextPageToken")

        if not next_page_token:
            break

    return results


def evaluate_video(title: str, description: str, channel: str, gemini_key: str):
    """
    Sends a request to the Gemini model for video quality analysis.
    """
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent?key={gemini_key}"
    headers = {"Content-Type": "application/json"}
    text_content = (
        f"Title: {title}\nDescription: {description}\nChannel: {channel}\n"
        "Evaluate the video’s quality and teaching methodology, focusing on the didactics used "
        "for presenting and explaining algorithms and data structures. Was the content clear and engaging, "
        "or did it lead to confusion? Provide a detailed evaluation based on the implementation and learning "
        "of the following key topics:\n"
        "1. Arrays\n"
        "2. Linked Lists\n"
        "3. Stacks\n"
        "4. Trees\n"
        "5. Graphs\n"
        "6. Asymptotic Analysis\n"
        "For each topic, assess whether it was included in the video, how it was implemented, and how effectively "
        "it was taught. Highlight any strengths or areas for improvement in making these concepts understandable "
        "and applicable for learners."
    )

    payload = {
        "contents": [
            {
                "text": text_content
            }
        ]
    }

    response = requests.post(url, headers=headers, json=payload)
    
    if response.status_code == 200:
        try:
            analysis = response.json()
            text = analysis["candidates"][0]["content"]["parts"][0]["text"]
            return text 
        except (KeyError, IndexError):
            return "Erro ao processar a análise do vídeo."
    else:
        return f"Erro na requisição: {response.status_code}"
    
    """
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 200:
        return response.json()
    return {"error": response.text}
    """

def file_in_use(file_name):
    """
    Checks if a file is in use by trying to open it in append mode.
    """
    try:
        with open(file_name, "a"):
            return False
    except IOError:
        return True

def save_excel(data, file_name: str = "youtube_videos_evaluated.xlsx"):
    """
    Saves data in an Excel file.
    """
    if file_in_use(file_name):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_name = f"youtube_videos_evaluated_{timestamp}.xlsx"
        print(f"File was open. Saving as a new file: {file_name}")

    pd.DataFrame(data).to_excel(file_name, index=False)
    print(f"Data saved in the file: {file_name}")

def extract_videoId(link: str):
    """
    Extracts the videoId from the YouTube link.
    """
    return link.split("v=")[-1]

def already_saved(supabase, video_id: str):
    """
    Checks if a video is already in the database based on its videoId.
    """
    response = supabase.table("videos").select("id").eq("link", f"https://www.youtube.com/watch?v={video_id}").execute()
    return len(response.data) > 0

def save_database(data, supabase):
    """
    Saves video data in the Database 'videos' table.
    """
    for item in data:
        video_id = extract_videoId(item["Link"])

        if already_saved(supabase, video_id):
            print(f"Video '{item['Title']}' is already in the database. Ignoring...")
            continue
        response = supabase.table("videos").insert({
            "title": item["Title"],
            "description": item["Description"],
            "channel": item["channel"],
            "link": item["Link"],
            "qualitative_analysis": item.get("Qualitative analysis"),
        }).execute()

        if response.data:
            print(f"Video '{item['Title']}' saved successfully.")
        else:
            print(f"Failed to save video '{item['Title']}': {response.data}")


def load_config():
    load_dotenv()
    return {
        "youtube_api_key": os.getenv("YOUTUBE_API_KEY"),
        "gemini_key": os.getenv("GEMINI_API_KEY"),
        "supabase_url": os.getenv("SUPABASE_URL"),
        "supabase_key": os.getenv("SUPABASE_KEY"),
    }

def setup_supabase(url, key):
    return create_client(url, key)

def fetch_videos(youtube_service, query):
    return search_videos(youtube_service, query, days=5, max_results=100)

def evaluate_videos(videos, gemini_key):
    for video in videos:
        print(f"Evaluating: {video['Title']}")
        analysis = evaluate_video(
            title=video["Title"],
            description=video["Description"],
            channel=video["channel"],
            gemini_key=gemini_key,
        )
        video["Qualitative analysis"] = analysis
    return videos

def main():
    config = load_config()
    supabase = setup_supabase(config["supabase_url"], config["supabase_key"])
    youtube_service = get_YT(config["youtube_api_key"])
    query = "Algorithm+Advent of Code+Python+2024"

    videos = fetch_videos(youtube_service, query)
    results_with_analysis = evaluate_videos(videos, config["gemini_key"])

    save_excel(results_with_analysis)
    save_database(results_with_analysis, supabase)

if __name__ == "__main__":
    main()

