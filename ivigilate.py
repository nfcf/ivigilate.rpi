#!/usr/bin/env python
from datetime import datetime, timedelta
import sys, subprocess, logging
import time, requests, json, Queue, threading
import config, autoupdate, blescan, localeventshelper, loghelper
import buzzer

__logger = logging.getLogger(__name__)
loghelper.init_logger(__logger)

__dev_id = 0

__invalid_beacons_lock = threading.Lock()
__invalid_beacons = {}

__invalid_detector_check_timestamp = 0

IGNORE_INTERVAL = 1 * 60 * 60 * 1000


def send_sightings_async(sightings):
    t = threading.Thread(target=send_sightings, args=(sightings,))
    t.start()


def send_sightings(sightings):
    global __invalid_detector_check_timestamp

    for sighting in sightings:
        sighting['detector_uid'] = config.get_detector_uid()
        sighting['detector_battery'] = None  # this can be used in the future...

    try:
        __logger.info('Sending %s sightings to the server...', len(sightings))
        response = requests.post(config.get('SERVER', 'address') + config.get('SERVER', 'addsightings_uri'),
                                 json.dumps(sightings), verify=True)
        __logger.info('Received from addsightings: %s', response.status_code)

        result = json.loads(response.text)
        now = int(time.time() * 1000)
        blescan.server_time_offset = result.get('timestamp', now) - now
        __invalid_detector_check_timestamp = 0

        if 400 <= response.status_code < 500:
            __invalid_detector_check_timestamp = now + blescan.server_time_offset
            __logger.warning('Detector is marked as invalid. Ignoring ALL sightings for %i ms', IGNORE_INTERVAL)
        elif response.status_code == 206:
            data = result.get('data', None)
            if data is not None and len(data) > 0 and \
                            data.get('invalid_beacons', None) is not None and len(data.get('invalid_beacons')) > 0:
                __invalid_beacons_lock.acquire()

                for ignore_sighting_key in data.get('invalid_beacons'):
                    __invalid_beacons[ignore_sighting_key] = now + blescan.server_time_offset

                __invalid_beacons_lock.release()

    except Exception:
        __logger.exception('Failed to contact the server with error:')


def init_ble_advertiser():
    # Configure Ble advertisement packet
    ble_adv_string = '1e02011a1aff4c000215' + config.get_detector_uid() + '00000000c500000000000000000000000000'
    ble_adv_array = [ble_adv_string[i:i+2] for i in range(0,len(ble_adv_string),2)]

    hci_tool_params = [config.HCITOOL_FILE_PATH, '-i', 'hci0', 'cmd', '0x08', '0x0008']
    hci_tool_params.extend(ble_adv_array)
    subprocess.call(hci_tool_params)

    # Configure Ble advertisement rate
    # (check http://stackoverflow.com/questions/21124993/is-there-a-way-to-increase-ble-advertisement-frequency-in-bluez for math)
    ble_config_string = '000800080300000000000000000700'
    ble_config_array = [ble_config_string[i:i+2] for i in range(0,len(ble_config_string),2)]

    hci_tool_params = [config.HCITOOL_FILE_PATH, '-i', 'hci0', 'cmd', '0x08', '0x0006']
    hci_tool_params.extend(ble_config_array)
    subprocess.call(hci_tool_params)

    # Start Ble advertisement
    subprocess.call([config.HCITOOL_FILE_PATH, '-i', 'hci0', 'cmd', '0x08', '0x000a', '01'])


def ble_scanner(queue):
    try:
        __logger.info('BLE scanner thread started')
        sock = blescan.hci_open_dev(__dev_id)
        __logger.info('BLE device started')
    except Exception:
        __logger.exception('BLE device failed to start:')

        __logger.critical('Will reboot RPi to see if it fixes the issue')
        # try to stop and start the BLE device somehow...
        # if that doesn't work, reboot the device.
        sys.exit(1)

    blescan.hci_le_set_scan_parameters(sock)
    blescan.hci_enable_le_scan(sock)

    while blescan.is_running:
        blescan.parse_events(sock, queue, 50)  # every 50 events 'refresh' the ble socket...whatever that means


def main():
    locally_seen_macs = set() # Set that contains unique locally seen beacons
    locally_seen_uids = set() # Set that contains unique locally seen beacons

    ble_queue = Queue.Queue()
    buzzer.init()

    #autoupdate.check()
    last_update_check = datetime.now()
    last_respawn_date = datetime.strptime(config.get('DEVICE', 'last_respawn_date'), '%Y-%m-%d').date()

    localeventshelper.fetch()

    # need to try catch and retry this as it some times fails...
    subprocess.call([config.HCICONFIG_FILE_PATH, 'hci0', 'up'])

    init_ble_advertiser()

    ble_thread = threading.Thread(target=ble_scanner, args=(ble_queue,))
    ble_thread.daemon = True
    ble_thread.start()

    __logger.info('Going into the main loop...')

    try:
        while True:
            now = datetime.now()
            now_timestamp = int(time.time() * 1000)
            # if configured daily_respawn_hour, stop the ble_thread and respawn the process
            # if now.date() > last_respawn_date and now.hour == config.getint('BASE', 'daily_respawn_hour'):
                # autoupdate.respawn_script(ble_thread)
                # autoupdate.restart_pi()
            # elif now > last_update_check + timedelta(minutes=5):
                # autoupdate.check(ble_thread)
                # last_update_check = datetime.now()

            # Take new sightings from queue
            sightings = []
            for i in range(100):
                if ble_queue.empty():
                    break
                else:
                    sighting = ble_queue.get()
                    sighting_key = sighting['beacon_mac'] + sighting['beacon_uid']

                    ignore_sighting = now_timestamp - __invalid_detector_check_timestamp < IGNORE_INTERVAL
                    if not ignore_sighting:
                        __invalid_beacons_lock.acquire()

                        invalid_beacon_timestamp = __invalid_beacons.get(sighting_key, 0)
                        if invalid_beacon_timestamp > 0 and \
                            now_timestamp - invalid_beacon_timestamp < IGNORE_INTERVAL:
                            ignore_sighting = True
                        elif sighting_key in __invalid_beacons:
                            del __invalid_beacons[sighting_key]

                        __invalid_beacons_lock.release()

                    if not ignore_sighting:
                        sightings.append(sighting)
                        # Probably join all unauthorized lists into one and see if this new exists there or not
                        if sighting['beacon_mac'] != '':
                            locally_seen_macs.add(sighting['beacon_mac']) # Append the beacon_mac of the latest sighting
                        if sighting['beacon_uid'] != '':
                            locally_seen_uids.add(sighting['beacon_uid']) # Append the beacon_uid of the latest sighting
                        # Launch threading.timer here
                    else:
                        __logger.info('Sighting ignored (invalid beacon): %s', sighting_key)
                    
            local_events = localeventshelper.get_active_events()
            for local_event in local_events:
                unauthorized = set(local_event.get('unauthorized_beacons', []))
                authorized = set(local_event.get('authorized_beacons', []))
                __logger.debug("Authorized: %s", authorized)
                __logger.debug("Unauthorized: %s", unauthorized)

                if not locally_seen_macs.isdisjoint(unauthorized) or \
                    not locally_seen_uids.isdisjoint(unauthorized):
                    # Rogue beacon is trying to escape!!
                    # TODO Add delay to checking authorized sightings
                    print "oh oh"
                    if (len(locally_seen_macs) == 0 or
                            locally_seen_macs.isdisjoint(authorized)) and \
                        (len(locally_seen_uids) == 0 or
                            locally_seen_uids.isdisjoint(authorized)):
                        # no authorized beacon in sigh
                        buzzer.play_alert(local_event.get('action_duration_in_seconds', 5))
                        break
                    else:
                        print 'saved by an authorized beacon...'

            print "All your base are belong to us."
            locally_seen_macs.clear()
            locally_seen_uids.clear()


            # if new sightings, send them to the server
            if len(sightings) > 0:
                send_sightings(sightings)

            time.sleep(1)
            
    except Exception:
        buzzer.end() # Ensure we leave everything nice and clean
        __logger.exception('main() loop failed with error:')
        autoupdate.respawn_script(ble_thread)
        

if __name__ == '__main__':
    main()
