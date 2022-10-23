#!/usr/bin/env python3
import multiprocessing
import os
import re
from os.path import exists
from typing import Tuple, Any
from moviepy.editor import afx,vfx
from moviepy.audio.AudioClip import concatenate_audioclips, CompositeAudioClip
from moviepy.audio.io.AudioFileClip import AudioFileClip
from moviepy.video.VideoClip import ImageClip
from moviepy.video.compositing.CompositeVideoClip import CompositeVideoClip
from moviepy.video.compositing.concatenate import concatenate_videoclips
from moviepy.video.io.VideoFileClip import VideoFileClip
from moviepy.video.io.ffmpeg_tools import ffmpeg_extract_subclip
from rich.console import Console

from utils.cleanup import cleanup
from utils.console import print_step, print_substep
from utils.video import Video
from utils.videos import save_data
from utils import settings
import apiclient






W, H = 1080, 1920


def name_normalize(name: str) -> str:
    name = re.sub(r'[?\\"%*:|<>]', "", name)
    name = re.sub(r"( [w,W]\s?\/\s?[o,O,0])", r" without", name)
    name = re.sub(r"( [w,W]\s?\/)", r" with", name)
    name = re.sub(r"(\d+)\s?\/\s?(\d+)", r"\1 of \2", name)
    name = re.sub(r"(\w+)\s?\/\s?(\w+)", r"\1 or \2", name)
    name = re.sub(r"\/", r"", name)
    name[:30]

    lang = settings.config["reddit"]["thread"]["post_lang"]
    if lang:
        import translators as ts

        print_substep("Translating filename...")
        translated_name = ts.google(name, to_language=lang)
        return translated_name

    else:
        return name


def make_final_video(
    number_of_clips: int,
    length: int,
    reddit_obj: dict,
    background_config: Tuple[str, str, str, Any],
):
    """Gathers audio clips, gathers all screenshots, stitches them together and saves the final video to assets/temp
    Args:
        number_of_clips (int): Index to end at when going through the screenshots'
        length (int): Length of the video
        reddit_obj (dict): The reddit object that contains the posts to read.
        background_config (Tuple[str, str, str, Any]): The background config to use.
    """
    # try:  # if it isn't found (i.e you just updated and copied over config.toml) it will throw an error
    #    VOLUME_MULTIPLIER = settings.config["settings"]['background']["background_audio_volume"]
    # except (TypeError, KeyError):
    #    print('No background audio volume found in config.toml. Using default value of 1.')
    #    VOLUME_MULTIPLIER = 1
    id = re.sub(r"[^\w\s-]", "", reddit_obj["thread_id"])
    print_step("Creating the final video 🎥")
    VideoFileClip.reW = lambda clip: clip.resize(width=W)
    VideoFileClip.reH = lambda clip: clip.resize(width=H)
    opacity = settings.config["settings"]["opacity"]
    transition = settings.config["settings"]["transition"]
    background_clip = (
        VideoFileClip(f"assets/temp/{id}/background.mp4")
        .without_audio()
        .resize(height=H)
        .crop(x1=1166.6, y1=0, x2=2246.6, y2=1920)
    )

    # Gather all audio clips
    audio_clips = [AudioFileClip(f"assets/temp/{id}/mp3/{i}.mp3") for i in range(number_of_clips)]
    audio_clips.insert(0, AudioFileClip(f"assets/temp/{id}/mp3/title.mp3"))
    audio_concat = concatenate_audioclips(audio_clips)
    audio_composite = CompositeAudioClip([audio_concat])

    #console.log(f"[bold green] Video Will Be: {length} Seconds Long")
    # add title to video
    image_clips = []
    # Gather all images
    new_opacity = 1 if opacity is None or float(opacity) >= 1 else float(opacity)
    new_transition = 0 if transition is None or float(transition) > 2 else float(transition)
    image_clips.insert(
        0,
        ImageClip(f"assets/temp/{id}/png/title.png")
        .set_duration(audio_clips[0].duration)
        .resize(width=W - 100)
        .set_opacity(new_opacity)
        .crossfadein(new_transition)
        .crossfadeout(new_transition),
    )

    for i in range(0, number_of_clips):
        image_clips.append(
            ImageClip(f"assets/temp/{id}/png/comment_{i}.png")
            .set_duration(audio_clips[i + 1].duration)
            .resize(width=W - 100)
            .set_opacity(new_opacity)
            .crossfadein(new_transition)
            .crossfadeout(new_transition)
        )

    # if os.path.exists("assets/mp3/posttext.mp3"):
    #    image_clips.insert(
    #        0,
    #        ImageClip("assets/png/title.png")
    #        .set_duration(audio_clips[0].duration + audio_clips[1].duration)
    #        .set_position("center")
    #        .resize(width=W - 100)
    #        .set_opacity(float(opacity)),
    #    )
    # else: story mode stuff
    img_clip_pos = background_config[3]
    image_concat = concatenate_videoclips(image_clips).set_position(
        img_clip_pos
    )  # note transition kwarg for delay in imgs
    image_concat.audio = audio_composite
    final = CompositeVideoClip([background_clip, image_concat])
    title = re.sub(r"[^\w\s-]", "", reddit_obj["thread_title"])
    idx = re.sub(r"[^\w\s-]", "", reddit_obj["thread_id"])

    filename = f"{name_normalize(title)[:251]}.mp4"
    subreddit = settings.config["reddit"]["thread"]["subreddit"]

    if not exists(f"./results/{subreddit}"):
        print_substep("The results folder didn't exist so I made it")
        os.makedirs(f"./results/{subreddit}")

    # if settings.config["settings"]['background']["background_audio"] and exists(f"assets/backgrounds/background.mp3"):
    #    audioclip = mpe.AudioFileClip(f"assets/backgrounds/background.mp3").set_duration(final.duration)
    #    audioclip = audioclip.fx( volumex, 0.2)
    #    final_audio = mpe.CompositeAudioClip([final.audio, audioclip])
    #    # lowered_audio = audio_background.multiply_volume( # todo get this to work
    #    #    VOLUME_MULTIPLIER)  # lower volume by background_audio_volume, use with fx
    #    final.set_audio(final_audio)
    final = Video(final).add_watermark(
        text=f"Background credit: {background_config[2]}", opacity=0, redditid=reddit_obj
     )
    final.write_videofile(
        f"assets/temp/{id}/temp.mp4",
        fps=26,
        audio_codec="aac",
        audio_bitrate="119k",
        verbose=False,
        threads=multiprocessing.cpu_count(),
    )
 

    ffmpeg_extract_subclip(
        f"assets/temp/{id}/temp.mp4",
        0,
        length,
        targetname=f"results/{subreddit}/{filename}",
    )
    save_data(subreddit, filename, title, idx, background_config[2])
    print_step("Removing temporary files 🗑")
    cleanups = cleanup(id)
    print_substep(f"Removed {cleanups} temporary files 🗑")
    print_substep("See result in the results folder!")
    

    print_step(
        f'Reddit title: {reddit_obj["thread_title"]} \n Background Credit: {background_config[2]}'
    )
    #Abubakar :adding backgroun music
    #print("on my way")
    #addsong=AudioFileClip("song.mp3").fx(afx.volumex,0.1)
    #combined=VideoFileClip(f"results/{subreddit}/{filename}")
    #duration=combined.duration
    #songlength=addsong.set_duration(duration)
    #combined.audio=CompositeAudioClip([songlength])
        #combined.write_videofile(f"1{filename}")    

    import httplib2
    import os
    import random
    import sys
    import time

    from apiclient.discovery import build
    from apiclient.errors import HttpError
    from apiclient.http import MediaFileUpload
    from oauth2client.client import flow_from_clientsecrets
    from oauth2client.file import Storage
    from oauth2client.tools import argparser, run_flow


    # Explicitly tell the underlying HTTP transport library not to retry, since
    # we are handling retry logic ourselves.
    httplib2.RETRIES = 1

    # Maximum number of times to retry before giving up.
    MAX_RETRIES = 10

    # Always retry when these exceptions are raised.
    RETRIABLE_EXCEPTIONS = (httplib2.HttpLib2Error, IOError)

    # Always retry when an apiclient.errors.HttpError with one of these status
    # codes is raised.
    RETRIABLE_STATUS_CODES = [500, 502, 503, 504]
    CLIENT_SECRETS_FILE = "client_secrets.json"

    # This OAuth 2.0 access scope allows an application to upload files to the
    # authenticated user's YouTube channel, but doesn't allow other types of access.
    YOUTUBE_UPLOAD_SCOPE = "https://www.googleapis.com/auth/youtube.upload"
    YOUTUBE_API_SERVICE_NAME = "youtube"
    YOUTUBE_API_VERSION = "v3"

    # This variable defines a message to display if the CLIENT_SECRETS_FILE is
    # missing.
    MISSING_CLIENT_SECRETS_MESSAGE = """
    WARNING: Please configure OAuth 2.0
    To make this sample run you will need to populate the client_secrets.json file
    found at:
    %s
    with information from the API Console
    https://console.developers.google.com/
    For more information about the client_secrets.json file format, please visit:
    https://developers.google.com/api-client-library/python/guide/aaa_client_secrets
    """ % os.path.abspath(os.path.join(os.path.dirname(__file__),
                                    CLIENT_SECRETS_FILE))

    VALID_PRIVACY_STATUSES = ("public", "private", "unlisted")
    
    def get_authenticated_service(args):
        flow = flow_from_clientsecrets(CLIENT_SECRETS_FILE,
          scope=YOUTUBE_UPLOAD_SCOPE,
          message=MISSING_CLIENT_SECRETS_MESSAGE)
        storage = Storage("%s-oauth2.json" % sys.argv[0])
        credentials = storage.get()  
        if credentials is None or credentials.invalid:
            credentials = run_flow(flow, storage, args) 
        return build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION,
            http=credentials.authorize(httplib2.Http()))
    def initialize_upload(youtube, options):        
        tags = None
        body=dict(
             snippet=dict(
                title=options['title'],
                description=options['description'],
                tags=tags,
                #categoryId=options['category']
            ),
            status=dict(
                privacyStatus=options['privacyStatus']
            )
        )
        # Call the API's videos.insert method to create and upload the video.
        insert_request = youtube.videos().insert(
            part=",".join(body.keys()),
            body=body,
            media_body=MediaFileUpload(options['file'], chunksize=-1, resumable=True)
        )
        resumable_upload(insert_request)

    def resumable_upload(insert_request):
        response = None
        error = None
        retry = 0   
        while response is None:
            try:
                print("Uploading file...")
                status, response = insert_request.next_chunk()
                if response is not None:
                    if 'id' in response:
                        print("Video id '%s' was successfully uploaded." % response['id'])
                    else:
                        exit("The upload failed with an unexpected response: %s" % response)                               
            except HttpError as e:
                if e.resp.status in RETRIABLE_STATUS_CODES:
                     error = "A retriable HTTP error %d occurred:\n%s" % (e.resp.status,
                                                             e.content)
                else:
                    raise
            except RETRIABLE_EXCEPTIONS as e:
                error = "A retriable error occurred: %s" % e  
            if error is not None:
                print(error)
                retry += 1
                if retry > MAX_RETRIES:
                    exit("No longer attempting to retry.")
                max_sleep = 2 ** retry
                sleep_seconds = random.random() * max_sleep
                print("Sleeping %f seconds and then retrying..." % sleep_seconds)
                time.sleep(sleep_seconds)    
    def upload_video(video_data):
        args = argparser.parse_args()
        if not os.path.exists(video_data['file']):
            exit("Please specify a valid file using the --file= parameter.")
        youtube = get_authenticated_service(args)
        try:
            initialize_upload(youtube, video_data)
        except HttpError as e:
            print("An HTTP error %d occurred:\n%s" % (e.resp.status, e.content))

    if 1 == 1:
        video_data = {
            "file": f"results/{subreddit}/{filename}",
            "title": f"{name_normalize(title)[:251]}|Best of memes!#shorts",
            "description": "#shorts \n Giving you the hottest memes of the day with funny comments!",
            "keywords":"meme,reddit",
            "privacyStatus":"public"
        }   
        
        upload_video(video_data)
        print('Upload done')
        print("Abubakar deleting file")
        os.remove(f"results/{subreddit}/{filename})
        



                
            


    
    
