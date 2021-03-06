import pytest
import sys, os
import json
sys.path.insert(1, os.path.join(sys.path[0], '..'))
from app.utils.priority_queue import PriorityQueue, TweetIdQueue, RedisSet, TweetStore
from app.stream.redis_s3_queue import RedisS3Queue
from app.stream.es_queue import ESQueue
from app.utils.process_media import ProcessMedia
from app.settings import Config
from app.stream.trending_tweets import TrendingTweets
from app.stream.trending_topics import TrendingTopics
from app.utils.redis import Redis
from app.utils.predict_queue import PredictQueue
from app.utils.predict import Predict
from app.utils.data_dump_ids import DataDumpIds


# session fixtures
@pytest.fixture(scope='function')
def pq():
    pq = PriorityQueue('test_project', namespace='test', max_queue_length=10)
    yield pq
    pq.self_remove()

@pytest.fixture(scope='function')
def data_dump_ids():
    data_dump_ids = DataDumpIds('test_project')
    yield data_dump_ids
    data_dump_ids.self_remove()

@pytest.fixture(scope='session')
def rs():
    rs = RedisSet('test_project', namespace='test')
    yield rs
    rs.self_remove_all()

@pytest.fixture(scope='function')
def tid_q():
    tid_q = TweetIdQueue('test_project', namespace='test', priority_threshold=5, max_queue_length=10)
    yield tid_q
    tid_q.flush()

@pytest.fixture(scope='session')
def s3_q():
    redis_s3_queue = RedisS3Queue()
    yield redis_s3_queue
    redis_s3_queue.clear()

@pytest.fixture(scope='session')
def tweet_store():
    tweet_store = TweetStore(namespace='test')
    yield tweet_store
    tweet_store.remove_all()

@pytest.fixture(scope='session')
def es_queue():
    es_queue = ESQueue()
    yield es_queue
    es_queue.clear()

@pytest.fixture(scope='function')
def tt():
    tt = TrendingTweets('project_test', expiry_time_ms=10, max_queue_length=5)
    yield tt
    tt.self_remove()

@pytest.fixture(scope='function')
def predict_queue():
    predict_queue = PredictQueue('project_test')
    yield predict_queue
    predict_queue.clear_queue()

@pytest.fixture(scope='function')
def trending_topics():
    tt = TrendingTopics('project_test', project_keywords=['test'])
    yield tt
    tt.self_remove()

@pytest.fixture(scope='function')
def r():
    yield Redis()

@pytest.fixture(scope='function')
def predictor():
    yield Predict('test_endpoint', 'fasttext')

# test data
@pytest.fixture(scope='session')
def retweet():
    yield load_tweet('retweet')

@pytest.fixture(scope='session')
def tweet():
    yield load_tweet('tweet')

@pytest.fixture(scope='session')
def tweet_with_place():
    yield load_tweet('tweet_with_place')

@pytest.fixture(scope='session')
def tweet_with_images():
    yield load_tweet('tweet_with_media')

@pytest.fixture(scope='session')
def tweet_with_coordinates():
    yield load_tweet('tweet_with_coordinates')

def load_tweet(tweet_type):
    config = Config()
    with open(os.path.join(config.PROJECT_ROOT, 'tests', 'data', f'{tweet_type}.json')) as f:
        tweet = json.load(f)
    return tweet
