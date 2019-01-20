import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
from app.settings import Config
from datetime import datetime, timedelta
from app.stream.stream_config_reader import StreamConfigReader
from app.stream.redis_s3_queue import RedisS3Queue
import os
import re
import subprocess

class Mailer():
    """Handles Emailing"""
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.config = Config()
        self.server = None

    def send(self, from_addr, to_addr, msg):
        self.connect()
        self.server.sendmail(from_addr, to_addr, msg)

    def connect(self):
        self.server = smtplib.SMTP('{}:{}'.format(self.config.EMAIL_SERVER, self.config.EMAIL_PORT))
        self.server.ehlo()
        self.server.starttls()
        self.server.login(self.config.EMAIL_USERNAME, self.config.EMAIL_PASSWORD)


class StreamStatusMailer(Mailer):
    def __init__(self, status_type='daily'):
        super().__init__()
        self.status_type = status_type
        self.msg = None
        self.from_addr = self.config.EMAIL_USERNAME
        if self.status_type == 'daily':
            self.to_addr = self.config.EMAIL_STREAM_STATUS_DAILY
        elif self.status_type == 'weekly':
            self.to_addr = self.config.EMAIL_STREAM_STATUS_WEEKLY
        else:
            raise Exception('Status type {} is not recognized'.format(self.status_type))

    def compose_message(self, body):
        self.msg = MIMEMultipart()
        self.msg['From'] = self.from_addr
        self.msg['To'] = self.to_addr
        self.msg['Subject'] = 'Crowdbreaks {} stream update'.format(self.status_type)
        self.msg.attach(MIMEText(body, 'html'))

    def get_body_daily(self):
        today = datetime.now()
        projects_stats, total_count = self._get_projects_stats(num_days=1, hourly=True)
        html_text = """\
            <html>
              <head></head>
                <body>
                    <h2>Crowdbreaks stream status</h2>
                    Date: {date}<br>
                    Total today: {total_count:,}<br>
                    {projects_stats}
                    <h2>Error log (past 7 days)</h2>
                    {errors}
                </body>
            </html>

        """.format(date=today.strftime("%Y-%m-%d"), total_count=total_count, projects_stats=projects_stats, errors=self._get_error_log(5), subtype='html')
        return html_text

    def get_body_weekly(self):
        today = datetime.now().strftime("%Y-%m-%d")
        projects_stats, total_count = self._get_projects_stats()
        html_text = """\
            <html>
              <head></head>
                <body>
                    <h2>Crowdbreaks stream status</h2>
                    Date: {date}<br>
                    Total this week: {total_count:,}<br>
                    {projects_stats}
                    <h2>Error log (past 7 days)</h2>
                    {errors}
                </body>
            </html>

        """.format(date=today, total_count=total_count, projects_stats=projects_stats, errors=self._get_error_log(5), subtype='html')
        return html_text

    def _get_projects_stats(self, num_days=7, hourly=False):
        stream_config_reader = StreamConfigReader()
        redis_s3_queue = RedisS3Queue()

        end_day = datetime.now()
        start_day = end_day - timedelta(days=num_days)
        stats = ''
        dates = list(redis_s3_queue.daterange(start_day, end_day, hourly=hourly))
        total = 0
        for stream in stream_config_reader.read():
            project = stream['es_index_name']
            project_slug = stream['slug']
            stats += "<h3>{}</h3>".format(project)
            total_by_project = 0
            for d in dates:
                if hourly:
                    d, h = d.split(':')
                    count = redis_s3_queue.get_counts(project_slug, d, h)
                    stats += '{0} ({1}:00 - {1}:59): {2:,}<br>'.format(d, h, count)
                else:
                    count = redis_s3_queue.get_counts(project_slug, d)
                    stats += '{}: {:,}<br>'.format(d, count)
                total += count
                total_by_project += count
            stats += 'Total: {:,}<br>'.format(total_by_project)
        return stats, total

    def _get_error_log(self, n=1, num_days=7, max_length=30):
        error_log = os.path.join(self.config.PROJECT_ROOT, 'logs', 'error.log')
        output = ''
        if os.path.isfile(error_log):
            # Use tail in order to prevent going through the full error log
            proc = subprocess.Popen(['tail', '-n', str(max_length), error_log], stdout=subprocess.PIPE)
            lines = proc.stdout.readlines()
            output += '<pre>'
            ignore_beyond = datetime.now() - timedelta(days=num_days)
            for line in lines:
                line = line.decode()
                # find timestamp in current error log line
                match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
                if not match is None:
                    try:
                        date = datetime.strptime(match[0], '%Y-%m-%d %H:%M:%S')
                    except:
                        # discard line if date cannot be parsed
                        continue
                    if date > ignore_beyond:
                        output += line
            output += '</pre>'
        return output
    
    def send_status(self):
        if self.msg is None:
            raise Exception('Cannot send empty Email')
        self.send(self.from_addr, self.to_addr, self.msg.as_string())
