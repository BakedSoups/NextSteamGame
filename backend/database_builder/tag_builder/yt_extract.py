import os
import json
from dotenv import load_dotenv
from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi

def request_channel_id(servicer: object) -> str:
    return servicer.channels().list(part = 'id', forHandle = '@gameranxTV').execute()['items'][0]['id']
    
def request_videos(servicer: object, channel_id: str, video_count: int) -> dict:
    return servicer.search().list(
        part = 'snippet',
        channelId = channel_id,
        type = 'video',
        videoCaption = 'closedCaption',
        maxResults = video_count,
        order = 'date').execute()
        
def dump_json(servicer: object, videos_response: dict) -> None:
    URL_TEMPLATE = "https://www.youtube.com/watch?v="
    videos = {item['id']['videoId']: [item['snippet']['title'], URL_TEMPLATE + item['id']['videoId']] 
              for item in videos_response['items']}
    
    all_verdicts = []
    ytt_api = YouTubeTranscriptApi()
    
    for vid, info in videos.items():
        video_response = servicer.videos().list(part = 'topicDetails,snippet', id = vid).execute()
        
        tags = video_response['items'][0]['snippet'].get('tags', [])
        
        if 'topicDetails' in video_response['items'][0] and 'topicCategories' in video_response['items'][0]['topicDetails']:
            topics = {url.split('/')[-1]: url for url in video_response['items'][0]['topicDetails']['topicCategories']}
        else:
            topics = {}
            
        try:
            transcript = "".join(line['text'] for line in ytt_api.get_transcript(vid))
        except Exception:
            transcript = ""
            
        ver_dict = {
            "name": info[0],
            "score": 0,
            "url": info[1],
            "tags": tags,
            "topics": topics,
            "transcript": transcript
        }
        
        all_verdicts.append(ver_dict)
    
    with open("game_verdicts_yt_complete.json", "w", encoding="utf-8") as fobject:
        json.dump(all_verdicts, fobject, indent=2)
def main():
    api_key = os.getenv("YT_API_KEY")
    servicer: object = build('youtube', 'v3', developerKey=api_key)
    channel_id: str = request_channel_id(servicer=servicer)
    video_response: dict = request_videos(servicer=servicer, channel_id=channel_id, video_count=5)
    dump_json(servicer=servicer, videos_response=video_response)
   
main()