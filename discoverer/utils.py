from geopy.geocoders import Nominatim

_geolocator = Nominatim()


def geolookup(address_field, query):
    ret = _geolocator.reverse(query)
    address = ret.raw.get('address')
    if address:
        return address.get(address_field, None)
