import pytest
import sys
import pdb
from datetime import datetime, timedelta
import json
import sys;sys.path.append('../../../web/')
from app.utils.mailer import StreamStatusMailer
from app.stream.redis_s3_queue import RedisS3Queue


class TestRedisS3Queue:
    def test_counts(self, s3_q):
        project = 'test_project'
        now = datetime.now()
        day = now.strftime("%Y-%m-%d")
        assert s3_q.get_counts(project, day) == 0
        s3_q.update_counts(project)
        assert s3_q.get_counts(project, day) == 1

    def test_clear(self, s3_q):
        now = datetime.now()
        day = now.strftime("%Y-%m-%d")
        project = 'test_project'
        s3_q.clear()
        assert s3_q.get_counts(project, day) == 0
        s3_q.update_counts(project)
        s3_q.update_counts(project)
        assert s3_q.get_counts(project, day) == 2
        past_day = (now - timedelta(days=100)).strftime("%Y-%m-%d")
        s3_q.update_counts(project, day=past_day)
        assert s3_q.get_counts(project, past_day) == 1
        s3_q.clear_counts()
        assert s3_q.get_counts(project, past_day) == 0
        assert s3_q.get_counts(project, day) == 2
        s3_q.clear_all_counts()
        assert s3_q.get_counts(project, past_day) == 0
        assert s3_q.get_counts(project, day) == 0

    def test_pop(self, s3_q):
        tweet = json.dumps({'id': 20, 'text': 'some text'})
        project = 'project_test'
        assert s3_q.find_projects_in_queue() == []
        s3_q.push(tweet, project)
        projects = s3_q.find_projects_in_queue()
        assert projects[0].decode().split(':')[-1] == 'project_test'
        assert s3_q.get_counts(project) == 1
        popped_tweet = s3_q.pop(project)
        assert popped_tweet.decode() == tweet

    def test_pop_all(self, s3_q):
        tweet1 = json.dumps({'id': 20, 'text': 'some text'})
        tweet2 = json.dumps({'id': 21, 'text': 'some text'})
        project = 'project_test'
        assert s3_q.find_projects_in_queue() == []
        s3_q.push(tweet1, project)
        s3_q.push(tweet2, project)
        key = s3_q.queue_key(project).encode()
        popped_tweets = s3_q.pop_all(key)
        assert len(popped_tweets) == 2
        assert popped_tweets[0].decode() == tweet1
        assert popped_tweets[1].decode() == tweet2

    def test_mailer(self, s3_q):
        project = 'project_vaccine_sentiment'
        s3_q.update_counts(project)
        mailer = StreamStatusMailer(status_type='weekly')
        body = mailer._get_projects_stats()
        print(body)

    def test_daterange(self, s3_q):
        now = datetime.utcnow()
        one_day_ago = now - timedelta(days=1)
        dr = s3_q.daterange(one_day_ago, now)
        assert len(list(dr)) == 1
        dr = s3_q.daterange(one_day_ago, now, hourly=True)
        assert len(list(dr)) == 24

    def test_passing_redis_connection(self, r):
        conn = r.get_connection()
        s3_q = RedisS3Queue(connection=conn)
        assert s3_q.connection is not None

    @pytest.mark.focus
    def test_pop_all_iter(self, s3_q):
        tweet1 = json.dumps({'id': 20, 'text': 'some text'})
        tweet2 = json.dumps({'id': 21, 'text': 'some text'})
        project = 'project_test'
        assert s3_q.find_projects_in_queue() == []
        s3_q.push(tweet1, project)
        s3_q.push(tweet2, project)
        key = s3_q.queue_key(project).encode()
        c = 0
        for batch in s3_q.pop_all_iter(key, batch_size=1):
            assert len(batch) == 1
            c += 1
        assert c == 2


if __name__ == "__main__":
    # if running outside of docker, make sure redis is running on localhost
    import os; os.environ["REDIS_HOST"] = "localhost"
    # @pytest.mark.focus
    pytest.main(['-s', '-m', 'focus'])
    # pytest.main(['-s'])
