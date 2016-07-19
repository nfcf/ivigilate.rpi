import logging, requests, json, time
import config, loghelper #, blescan

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
        __logger.info('Received from localevents response status: %s - %s', response.status_code)

        result = json.loads(response.text)

        # now = int(time.time() * 1000)
        # blescan.server_time_offset = result.get('timestamp', now) - now

        if response.status_code == 200:
            local_events = result.get('data', [])

    except Exception:
        __logger.exception('Failed to contact the server with error:')