from caa import CivilAviationAuthority, AirplanesLive
from utils import Telegram
import os
import pickle

TELEGRAM_API_TOKEN = os.getenv('TELEGRAM_API_TOKEN')
CHANNEL_ID = os.getenv('CHANNEL_ID')
DATABASE = 'spitfire.db'


def pickle_to_file(ac_pickle):
    with open('prev_ac.txt', 'wb') as fl:
        pickle.dump(ac_pickle, fl)


if __name__ == '__main__':
    caa = CivilAviationAuthority(DATABASE)
    live_ac = AirplanesLive()
    t = Telegram(TELEGRAM_API_TOKEN)

    prev_ac = set()
    try:
        with open('prev_ac.txt', 'rb') as f:
            prev_ac = pickle.load(f)
    except FileNotFoundError:
        pickle_to_file(prev_ac)

    try:
        ac = live_ac.search_radius(51.30457774177224, -0.09535818745250407, 10)
    except caa.client.RequestException:
        ac = []

    ac_dict = dict(map(lambda x: (x[0], (x[1], x[2])), (filter(lambda x: x if x[0] else None, ac))))
    ac_set = set(map(lambda x: x[0], filter(lambda x: x if x[0] else None, ac)))

    alert_ac = ac_set & caa.war_ac

    for p in alert_ac:
        if p not in prev_ac:
            plane_details = ac_dict[p]
            alert = '🚨 War plane spotted 🚨\n\n' \
                    f'Plane: {plane_details[0]}\nReg: {p}\n\nClick to track 👇 \n'\
                    f'https://globe.airplanes.live/?icao={plane_details[1]}'
            t.send_message(CHANNEL_ID, alert)
            prev_ac.add(p)
    pickle_to_file(alert_ac & prev_ac)
    
