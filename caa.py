from utils import Database, Server


class CivilAviationAuthority:
    def __init__(self, db):
        self.db = Database(db)
        self.db.create_table('aircraft', ('mark TEXT',
                                          'aircraft_type TEXT'))
        self.war_ac = {x[0] for x in self.db.c.execute('SELECT mark FROM aircraft').fetchall()}
        self.client = Server()

    def search_aircraft(self, aircraft):
        data = {'AircraftType': aircraft}
        resp = self.client.connect('POST', 'https://ginfoapi.caa.co.uk/api/aircraft/search', json=data, output='json')
        ac = list(map(lambda x: (x['Mark'], x['AircraftType']), resp))
        return ac

    def save_aircraft(self, ac):
        self.db.insert_into('aircraft', ('mark', 'aircraft_type'), ac)

    def get_aircraft(self):
        return dict(self.db.c.execute('SELECT * FROM aircraft').fetchall())


class AirplanesLive:

    def __init__(self):
        self._domain = 'https://api.airplanes.live/v2/'
        self.client = Server()

    def search_radius(self, lat, long, radius):
        url = self._domain + f'point/{lat}/{long}/{radius}'
        ac = self.client.connect('GET', url, output='json')
        ac = list(map(lambda x: (x.get('r'), x.get('desc'), x.get('hex')), ac['ac']))
        return ac
