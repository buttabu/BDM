import datetime
import operator
import os
import sys
import time
from pyspark import SparkContext
from operator import add
from math import radians, cos, sin, asin, sqrt

def haversine(lon1, lat1, lon2, lat2):
    # convert decimal degrees to radians
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])

    # haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    r = 3956 # Radius of earth in miles. Use 6371 for kilometers
    return c * r

def indexZones(shapeFilename):
    import rtree
    import fiona.crs
    import geopandas as gpd
    index = rtree.Rtree()
    zones = gpd.read_file(shapeFilename).to_crs(fiona.crs.from_epsg(2263))
    for idx,geometry in enumerate(zones.geometry):
        index.insert(idx, geometry.bounds)
    return (index, zones)
def find_Neighborhood(p, index, zones):
    match = index.intersection((p.x, p.y, p.x, p.y))
    for idx in match:
        if any(map(lambda x: x.contains(p), zones.geometry[idx])):
            return zones['neighborhood'][idx]
    return -1

def find_Borough(p, index, zones):
    match = index.intersection((p.x, p.y, p.x, p.y))
    for idx in match:
        if any(map(lambda x: x.contains(p), zones.geometry[idx])):
            return zones['borough'][idx]
    return -1

def mapToZone(parts):
    import pyproj
    import shapely.geometry as geom
    proj = pyproj.Proj(init="epsg:2263", preserve_units=True)
    index, zones = indexZones('neighborhoods.geojson')

    for line in parts:
        if line.startswith('vendor_id'): continue
        fields = line.strip('').split(',')
        if fields ==['']: continue
        if all((fields[5],fields[6],fields[9],fields[10])):
            if(haversine(float(fields[5]),float(fields[6]),float(fields[9]),float(fields[10]))<2.0):
                passenger_count = int(fields[3])
                pickup_location  = geom.Point(proj(float(fields[5]), float(fields[6])))
                dropoff_location = geom.Point(proj(float(fields[9]), float(fields[10])))

                pickup_zone = find_Neighborhood(pickup_location, index, zones)
                dropoff_zone = find_Neighborhood(dropoff_location, index, zones)

                if pickup_zone>=0 and dropoff_zone>=0:
                    yield ((dropoff_zone, pickup_zone), 1)

def mapper2(k2v2):
    from heapq import nlargest
    k, values = k2v2
    top10 = nlargest(10, values,key=lambda a: a[1])
    return (k,top10)

if __name__=='__main__':
    
    sc = SparkContext()

    trips = sc.textFile('user/abutt001/yellow_tripdata_2012-07.csv', use_unicode=False).cache()
    #trips = sc.textFile('user/abutt001/yellow_tripdata_2014-07.csv', use_unicode=False).cache()
    output = trips.mapPartitions(mapToZone).reduceByKey(add).map(lambda x: (x[0][0],(x[0][1],x[1]))).groupByKey().map(mapper2)
    output.saveAsTextFile('find-distance')