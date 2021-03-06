"""
Script to sync data between two Elasticsearch indices. Note that the indices must have a suitable mapping
"""
from utils import get_es_client, add_doc_query_args, build_doc_query
import json
import os
from elasticsearch import helpers
from datetime import datetime, timezone
import logging
import argparse
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)-5.5s] [%(name)-12.12s]: %(message)s')
logger = logging.getLogger(__name__)

def load_docs(es, args):
    query = build_doc_query(since=args.since, until=args.until, missing_field=args.missing_field, has_field=args.has_field, source=args.source, lang=args.lang)
    scan = helpers.scan(es.es, scroll='1m', query=query, index=args.index, doc_type=args.doc_type, request_timeout=60)
    for item in scan:
        yield {'_index': args.index, '_type': args.doc_type, '_id': item['_id'], '_source': item['_source']}

def main(args):
    es_source = get_es_client(env='prd')
    if not es_source.test_connection():
        raise Exception('Connection issue')

    # bulk index on development
    if args.out == 'es-dev':
        es_dev = get_es_client(env='dev')
        try:
            resp = helpers.bulk(es_dev.es, load_docs(es_source, args))
        except Exception as e:
            logger.error('Bulk indexing not unsuccessful!')
            print(e)
        else:
            logger.info(f'Successfully indexed {resp[0]:,} docs...')
    elif args.out == 'jsonl':
        ts = int(time.time())
        f_out = os.path.join('cache', f'sync_es_data_{args.index}_{ts}.jsonl')
        num_rows = 0
        with open(f_out, 'w') as f:
            for line in load_docs(es_source, args):
                f.write(json.dumps(line) + '\n')
                num_rows += 1
                if num_rows % int(1e4) == 0:
                    logger.info(f'Loaded {num_rows:,} documents...')

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--index', required=True, type=str, help='Name of index')
    parser.add_argument('-d', '--doc-type', dest='doc_type', default='tweet', required=False, type=str, help='Doc type')
    parser.add_argument('-o', '--out', choices=['es-dev', 'jsonl'], required=False, default='es-dev', type=str, help='Output format')
    parser = add_doc_query_args(parser)
    args = parser.parse_args()
    return args

if __name__ == "__main__":
    args = parse_args()
    main(args)
