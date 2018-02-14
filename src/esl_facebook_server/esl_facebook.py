import requests
import re
import urllib.parse
from collections import OrderedDict
from datetime import datetime, timedelta

import settings

esl_url = 'http://api.esl.tv/v1/channel/eventchannels?pid={esl_event_id}&hideservice=web'
# esl_url = 'http://cdn1.api.esl.tv/v1/channel/eventchannels?pid={esl_event_id}&hideservice=huomao'
facebook_graph_page_url = 'https://graph.facebook.com/{facebook_id}?fields=link,username&access_token={facebook_app_id}|{facebook_app_secret}'
facebook_stream_fetch_url = 'https://www.facebook.com/video/tahoe/async/{facebook_video_id}/?chain=true&isvideo=true&originalmediaid={facebook_video_id}&playerorigin=permalink&playersuborigin=tahoe&ispermalink=true&dpr=2'

cached_stream_urls = {}
cached_facebook_ids = {}


def get_facebook_stream_url(facebook_video_url):
    headers = {
        'User-Agent': settings.USER_AGENT,
    }
    video_page_text = requests.get(facebook_video_url, headers=headers).text
    video_stream_regex = re.search(r'hd_src:"(.*?)"', video_page_text)
    if video_stream_regex:
        video_stream_probable_url = video_stream_regex.group(1)
        if len(video_stream_probable_url) < 1024:
            return video_stream_probable_url


def get_facebook_stream_url_new(facebook_video_url):
    headers = {
        'User-Agent': settings.USER_AGENT,
    }
    payload = {
        '__user': '0',
        '__a': '1',
        '__req': '1',
        '__be': '-1',
        '__pc': 'PHASED:DEFAULT',
    }
    facebook_video_id = re.search(r'videos/(\d+?)/', facebook_video_url).group(1)
    facebook_stream_fetch_url_final = facebook_stream_fetch_url.format(facebook_video_id=facebook_video_id)
    video_page_text = requests.post(facebook_stream_fetch_url_final, data=payload, headers=headers).text
    video_stream_regex = re.search(r'hd_src":"(.*?)"', video_page_text)
    if video_stream_regex:
        video_stream_probable_url_escaped = video_stream_regex.group(1)
        video_stream_probable_url = re.sub(r'\\(.)', r'\1', video_stream_probable_url_escaped)
        if len(video_stream_probable_url) < 1024:
            return video_stream_probable_url


def fetch_streams(esl_event_id=8712):
    esl_facebook_streams = OrderedDict()
    esl_event_json = requests.get(esl_url.format(esl_event_id=esl_event_id)).json()
    for stream in esl_event_json:
        if stream.get('service') == 'facebook':
            embed_regex = re.search(r'href=(.*?)&', stream.get('override_embedcode'))
            event_dict = {
                'facebook_id': stream.get('account').split('-')[0],
                'video_id': stream.get('youtube_video_id'),
                'video_url': urllib.parse.unquote(embed_regex.group(1)),
                'stream_name': stream.get('name'),
            }
            esl_facebook_streams[stream['uid']] = event_dict

    for stream in esl_facebook_streams.values():
        if stream['facebook_id'] and stream['video_id']:
            if stream['facebook_id'] in cached_facebook_ids:
                facebook_page_json = cached_facebook_ids[stream['facebook_id']]
            else:
                facebook_page_json = requests.get(facebook_graph_page_url.format(
                    facebook_id=stream['facebook_id'],
                    facebook_app_id=settings.FACEBOOK_APP_ID,
                    facebook_app_secret=settings.FACEBOOK_APP_SECRET)
                ).json()
                cached_facebook_ids[stream['facebook_id']] = facebook_page_json
            facebook_video_url_alt = '{facebook_page_url}videos/{facebook_video_id}/'.format(
                facebook_page_url=facebook_page_json['link'], facebook_video_id=stream['video_id']
            )
            stream['video_url_alt'] = facebook_video_url_alt

    final_esl_facebook_streams = []

    for stream_id, stream in esl_facebook_streams.items():
        cached_video_stream_dict = cached_stream_urls.get(stream['video_url'])
        if settings.CACHE_STREAM_URLS and cached_video_stream_dict and datetime.utcnow() - cached_video_stream_dict['dt'] < timedelta(seconds=settings.CACHE_STREAM_URLS_TTL):
            stream['video_stream'] = cached_video_stream_dict['video_stream']
            print('{} fetched from cache'.format(stream['video_url']))
        else:
            video_stream = get_facebook_stream_url_new(stream['video_url'])
            if not video_stream:
                video_stream = get_facebook_stream_url(stream['video_url'])
            if video_stream:
                stream['video_stream'] = video_stream
                cached_stream_urls[stream['video_url']] = {
                    'video_stream': video_stream,
                    'dt': datetime.utcnow(),
                }

        if 'video_stream' in stream:
            if stream['video_stream'] in [e['video_stream'] for e in final_esl_facebook_streams]:
                continue
            final_stream_dict = {'esl_video_id': stream_id}
            final_stream_dict.update(stream)
            final_esl_facebook_streams.append(final_stream_dict)

    print(esl_facebook_streams)
    print(final_esl_facebook_streams)
    return final_esl_facebook_streams


if __name__ == "__main__":
    raise SystemExit(fetch_streams())
