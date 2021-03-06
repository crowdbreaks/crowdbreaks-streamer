from tweepy import Stream
import tweepy
import logging
from app.utils.project_config import ProjectConfig

class StreamManager():
    def __init__(self, auth, listener, chunk_size=1536):
        # High chunk_size means lower latency but higher processing efficiency
        self.logger = logging.getLogger('stream')
        self.stream = Stream(auth=auth, listener=listener, tweet_mode='extended', parser=tweepy.parsers.JSONParser(), chunk_size=chunk_size)
        self.stream_config = ProjectConfig()

    def start(self):
        config = self.stream_config.get_pooled_config()
        self.logger.info('Starting to track for keywords {} in languages {}'.format(config['keywords'], config['lang']))
        self.stream.filter(track=config['keywords'], languages=config['lang'], encoding='utf-8', stall_warnings=True)

    def stop(self):
        self.logger.info('Stopping stream...')
        try:
            self.stream.disconnect()
        except:
            pass
