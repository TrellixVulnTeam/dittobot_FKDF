# Imports
import os, json, sys, time
from collections import defaultdict
import tweepy

# API keys as environment variables
from dotenv import load_dotenv
load_dotenv()

# Pre-trained Tokenizer
from transformers import OpenAIGPTTokenizer, OpenAIGPTLMHeadModel
from huggingface.train import add_special_tokens_
from huggingface.utils import download_pretrained_model, get_dataset

CONSUMER_KEY = os.getenv('CONSUMER_KEY')
CONSUMER_SECRET = os.getenv('CONSUMER_SECRET')
ACCESS_TOKEN = os.getenv('ACCESS_TOKEN')
ACCESS_TOKEN_SECRET = os.getenv('ACCESS_TOKEN_SECRET')
BEARER_TOKEN = os.getenv('BEARER_TOKEN')

TIMELINES_PATH = "timelines"
FREQS_PATH = "word-freqs"

auth = tweepy.AppAuthHandler(CONSUMER_KEY, CONSUMER_SECRET)
# auth.set_access_token(ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
api = tweepy.API(auth)
        
def get_timeline(screen_name, count=3200, save_json=True, sleep_every=0):
    timeline = []
    statuses = tweepy.Cursor(api.user_timeline, 
        screen_name=screen_name, count=count, tweet_mode='extended').items()
    for i, status in enumerate(statuses):
        timeline.append(status.full_text)
        if sleep_every and (i+1) % sleep_every == 0: # Wait out the API rate limit
            print(f"Got {i} statuses. Sleeping 15 mins...")
            for _ in range(15):
                time.sleep(60)
    
    if save_json:
        json_path = os.path.join(TIMELINES_PATH, f'{screen_name}.json')
        with open(json_path, mode='w', encoding='utf-8') as f:
            json.dump(timeline, f, indent=2, ensure_ascii=False)
    
    return timeline

def proc_timeline(timeline):
    ret = []
    for twt in timeline:
        # remove retweets
        if twt[:3] == "RT ":
            continue
        # remove @s, links, ellipses for truncated tweets
        twt = ' '.join(word for word in twt.split(' ') if (word and
            word[0] != '@' and word[:4] != 'http' and 
            word[-1] != '…' and word[0] != '#'))
        
        if twt:
            ret.append(twt)
    return ret

def freqs_from_tweets(tweets, tokenizer):
    tweets = proc_timeline(tweets)
    freqs = defaultdict(int)
    for twt in tweets:
        tokens = tokenizer.encode(twt)
        for tok in tokens:
            freqs[tok] += 1
    return freqs

def word_freq(screen_name, tokenizer, save_json=True):
    timeline_path = os.path.join(TIMELINES_PATH, f'{screen_name}.json')
    if os.path.exists(timeline_path):
        with open(timeline_path, mode='r', encoding='utf-8') as f:
            timeline = json.load(f)
    else:
        timeline = get_timeline(screen_name, count=3200, save_json=save_json)

    timeline = proc_timeline(timeline)

    freqs = defaultdict(int)
    for tweet in timeline:
        tokens = tokenizer.encode(tweet)
        for token in tokens:
            freqs[token] += 1

    if save_json:
        json_path = os.path.join(FREQS_PATH, f'{screen_name}.json')
        with open(json_path, mode='w', encoding='utf-8') as f:
            json.dump(freqs, f, indent=2, ensure_ascii=False)

    return freqs

def get_persona_freqs(dataset):
    if os.path.exists('word-freqs/persona.json'):
        freqs = json.load(open('word-freqs/persona.json', 'r', encoding='utf-8'))
        freqs = defaultdict(int, {int(k):v for k, v in freqs.items()})
    # dataset['train'/'test'][#]['personality'/'utterances'][#]['history'/'candidates']
    else:
        dataset = get_dataset(tokenizer, "", './dataset_cache') # Warning: Slow, ~10 minutes
        freqs = defaultdict(int)
        for ds in dataset.values():
            for item in ds:
                for msg in item['utterances'][-1]['history']: # final history is full history
                    for id_ in msg:
                        freqs[id_] += 1
    return freqs

if __name__ == "__main__":
    screen_name = sys.argv[1]

    tokenizer_class, model_class = OpenAIGPTTokenizer, OpenAIGPTLMHeadModel
    print('Getting model...')
    pretrained_model = download_pretrained_model() #downloads the pretrained model from S3
    model = model_class.from_pretrained(pretrained_model)
    tokenizer = tokenizer_class.from_pretrained(pretrained_model)

    add_special_tokens_(model, tokenizer)

    freqs = word_freq(screen_name, tokenizer, save_json=True)
    # print(sorted(list(freqs.keys()), key=lambda i: freqs[i]))

    