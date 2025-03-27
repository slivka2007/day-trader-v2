import datetime
import pytz

# Define the EST timezone
TIMEZONE = pytz.timezone('America/New_York')

def get_current_datetime():
    """Get the current datetime in timezone"""
    return datetime.datetime.now(TIMEZONE)

def get_current_date():
    """Get the current date in timezone"""
    return get_current_datetime().date()

def get_current_time():
    """Get the current time in timezone"""
    return get_current_datetime().time()