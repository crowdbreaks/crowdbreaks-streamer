from app.utils.redis import Redis
from app.stream.s3_handler import S3Handler
import logging
from app.settings import Config
import time
import os
import uuid
import shutil
from helpers import report_error, compress, decompress

logger = logging.getLogger(__name__)
config = Config()

class DataDumpIds(Redis):
    def __init__(self, project, mode=None, namespace='cb', key_namespace='data-dump-ids', **args):
        super().__init__(self, **args)
        self.project = project
        self.mode = mode
        self.namespace = namespace
        self.key_namespace = key_namespace
        self.tmp_path = os.path.join(config.APP_DIR, 'tmp')
        if self.mode is None:
            self.data_dump_f_name = f'data_dump_ids_{self.project}'
        else:
            self.data_dump_f_name = f'data_dump_ids_{self.project}_{self.mode}'
        self.local_file = os.path.join(self.tmp_path, self.data_dump_f_name)
        self.local_file_compr = os.path.join(self.tmp_path, self.data_dump_f_name + '.gz')
        self.local_file_tmp = os.path.join(self.tmp_path, self.data_dump_f_name + '.tmp')
        if config.ENV == 'prd':
            self.data_dump_key = f'data_dump/{self.project}/{self.data_dump_f_name}.txt.gz'
        else:
            self.data_dump_key = f'{config.ENV}/data_dump/{self.project}/{self.data_dump_f_name}.txt.gz'
        self.s3_handler = S3Handler(bucket='public')

    @property
    def key(self):
        if self.mode is None:
            return "{}:{}:{}".format(self.namespace, self.key_namespace, self.project)
        else:
            return "{}:{}:{}:{}".format(self.namespace, self.key_namespace, self.project, self.mode)

    def add(self, value):
        self._r.rpush(self.key, value)

    def __len__(self):
        return self._r.llen(self.key)

    def self_remove(self):
        self._r.delete(self.key)

    def pop_all(self):
        pipe = self._r.pipeline()
        res = pipe.lrange(self.key, 0, -1).delete(self.key).execute()
        return [r.decode() for r in res[0]]

    def pop_all_iter(self, chunk_size=1000):
        num_chunks = int(len(self)/chunk_size)
        while num_chunks > 0:
            pipe = self._r.pipeline()
            res = pipe.lrange(self.key, 0, chunk_size-1).ltrim(self.key, chunk_size, -1).execute()
            yield [r.decode() for r in res[0]]
            num_chunks -= 1
        if len(self) > 0:
            # yield rest of data
            yield self.pop_all()

    def download_existing_data_dump(self):
        logger.info(f'Downloading existing data dump with key {self.data_dump_key} to {self.local_file_compr}...')
        success = self.s3_handler.download_file(self.local_file_compr, self.data_dump_key)
        return success

    def sync(self):
        num_new_data = len(self)
        if num_new_data == 0:
            logger.info(f'No new data was collected. Aborting.')
            return
        logger.info(f'Writing {num_new_data:,} to file {self.data_dump_key}...')
        with open(self.local_file_tmp, 'w') as f:
            for chunk in self.pop_all_iter():
                chunk = list(set(chunk))
                if len(chunk) > 0:
                    f.write('\n'.join(chunk) + '\n')
        logger.info(f'Collected {num_new_data:,} ids')
        if self.s3_handler.file_exists(self.data_dump_key):
            success = self.download_existing_data_dump()
            if not success:
                logger.error(f'Something went wrong when trying to download the existing data. Aborting.')
                return
            # decompress data
            decompress(self.local_file_compr, self.local_file)
            os.remove(self.local_file_compr)
            # concatenating new data
            with open(self.local_file, 'a') as f:
                shutil.copyfileobj(open(self.local_file_tmp, 'r'), f)
        else:
            # There is no existing data, simply rename file
            os.rename(self.local_file_tmp, self.local_file)
        # reuploading file
        logger.info(f'Compressing file...')
        compress(self.local_file, self.local_file_compr)
        logger.info(f'Uploading file to S3 under key {self.data_dump_key}')
        success = self.s3_handler.upload_file(self.local_file_compr, self.data_dump_key, make_public=True)
        if not success:
            report_error(logger, msg='Uploading data dump Ids file to S3 unsuccessful.')
        # cleanup
        logger.info('Cleaning up temporary files...')
        for f in [self.local_file, self.local_file_tmp, self.local_file_compr]:
            if os.path.isfile(f):
                os.remove(f)
