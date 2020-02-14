import rollbar
from app.settings import Config
import pytz
from datetime import datetime
from flask import jsonify
import sys

def report_error(logger, msg, level='error'):
    if level == 'error':
        logger.error(msg)
        rollbar.report_exc_info(sys.exc_info())
    elif level == 'warning':
        logger.warning(msg)

def get_user_tz():
    config = Config()
    try:
        tz = pytz.timezone(config.TIMEZONE)
    except pytz.exceptions.UnknownTimeZoneError:
        tz = pytz.utc
    return tz

def get_tz_difference():
    """Returns time zone difference in hours between time specified by user and UTC."""
    local = datetime.now(get_user_tz())
    utc = local.astimezone(pytz.utc)
    local_utc_replaced = local.replace(tzinfo=pytz.utc) # replace tz in order to be able to compare two UTC times objects
    return utc - local_utc_replaced

def json_response(status_code, message):
    response = jsonify({
        'status': status_code,
        'message': message
        })
    response.status_code = status_code
    return response
