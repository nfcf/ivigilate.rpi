import logging, requests, json, math
import config, loghelper #, blescan
from datetime import datetime, timedelta, timezone

__logger = logging.getLogger(__name__)
loghelper.init_logger(__logger)

local_events = []


def fetch():
    global local_events

    try:
        __logger.info('Checking if there are local_events configured on the server for this detector...')
        response = requests.get(config.get('SERVER', 'address') + config.get('SERVER', 'localevents_uri') +
                                '?detector_uid=' + config.get_detector_uid(),
                                 verify=True)
        __logger.info('Received from localevents response status: %s', response.status_code)

        result = json.loads(response.text)

        # now = int(time.time() * 1000)
        # blescan.server_time_offset = result.get('timestamp', now) - now

        if response.status_code == 200:
            local_events = result.get('data', [])
            # Remove inactive local_events (that shouldn't be here anyway...)
            local_events = [le for le in local_events if le.get('is_active', True) == True]

    except Exception:
        __logger.exception('Failed to contact the server with error:')


def get_active_events():
    active_local_events = []

    now = datetime.now(timezone.utc)
    current_week_day_representation = math.pow(2, now.weekday())

    if local_events is not None and len(local_events) > 0:
        for local_event in local_events:
            schedule_now_with_timezone = now + datetime.timedelta(minutes = local_event.get('schedule_timezone_offset', 0))
            schedule_start_time = local_event.get('schedule_start_time', '00:00:00')
            schedule_end_time = local_event.get('schedule_start_time', '23:59:59')

            if int(local_event.get('schedule_days_of_week', 127)) & int(current_week_day_representation) > 0 and \
                schedule_start_time <= schedule_now_with_timezone.strftime('%H:%M:%S') <= schedule_end_time:

                metadata = json.loads(local_event.get('metadata', '{}'))
                actions = json.loads(metadata.get('actions', '[{}]'))
                # local events only have one action and in this case we only care about the duration_in_seconds
                local_event['action_duration_in_seconds'] = actions[0].get('duration_in_seconds')

                active_local_events.append(local_event)

                print "Authorized: ", set(local_event('authorized_beacons', []))
                print "Unauthorized: ", set(local_event('unauthorized_beacons', []))

    return active_local_events