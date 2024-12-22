import requests
import json
import re
import os
import zipfile
import io
import glob
import shutil
import geopandas
# noinspection PyUnresolvedReferences
import pyogrio
from pyproj import Transformer
from tempfile import TemporaryDirectory
import logging

logging.basicConfig(level=logging.INFO)

os.makedirs("waypoints", exist_ok=True)

for csdi_dataset_id in [
    # 巴士路線
    # https://portal.csdi.gov.hk/geoportal/?lang=zh-hk&datasetId=td_rcd_1638844988873_41214
    "td_rcd_1638844988873_41214",
    # 專線小巴路線
    # https://portal.csdi.gov.hk/geoportal/?lang=zh-hk&datasetId=td_rcd_1697082463580_57453
    "td_rcd_1697082463580_57453"
]:
    logging.info("csdi_dataset_id=" + csdi_dataset_id)
    logging.info("Fetching metadata")
    r = requests.get(
        "https://portal.csdi.gov.hk/geoportal/rest/metadata/item/" +
        csdi_dataset_id)
    src_id = json.loads(r.content)['_source']['fileid'].replace('-', '')

    epsgTransformer = Transformer.from_crs('epsg:2326', 'epsg:4326')

    logging.info("Fetching FGDB")
    r = requests.get(
        "https://static.csdi.gov.hk/csdi-webpage/download/" + src_id + "/fgdb")
    z = zipfile.ZipFile(io.BytesIO(r.content))
    gdb_name = next(s[0:s.index('/')]
                    for s in z.namelist() if s != "__MACOSX")

    with TemporaryDirectory() as tmpdir:
        logging.info("Extracting data")
        z.extractall(tmpdir)
        gdb_path = os.path.join(tmpdir, gdb_name)
        logging.info("Reading data (1)")
        gdf = geopandas.read_file(gdb_path, encoding='utf-8', engine="pyogrio")
        logging.info("Reading data (2)")
        data = json.loads(gdf.to_json(drop_id=True))

    logging.info("Transforming data")
    for i, feature in enumerate(data["features"]):
        if feature["geometry"]["type"] == "MultiLineString":
            for j, coordinates in enumerate(
                    feature["geometry"]["coordinates"]):
                for k, coordinate in enumerate(coordinates):
                    lat, lng = epsgTransformer.transform(
                        coordinate[1], coordinate[0])
                    data["features"][i]["geometry"]["coordinates"][j][k] = [
                        lng, lat]
        else:
            for j, coordinate in enumerate(feature["geometry"]["coordinates"]):
                lat, lng = epsgTransformer.transform(
                    coordinate[1], coordinate[0])
                data["features"][i]["geometry"]["coordinates"][j] = [lng, lat]

    logging.info("Storing data")
    for feature in data["features"]:
        properties = feature["properties"]
        with open("waypoints/" + str(properties["ROUTE_ID"]) + "-" + ("O" if properties["ROUTE_SEQ"] == 1 else "I") + ".json", "w", encoding='utf-8') as f:
            f.write(
                re.sub(
                    r"([0-9]+\.[0-9]{5})[0-9]+",
                    r"\1",
                    json.dumps({
                        "features": [feature],
                        "type": "FeatureCollection"
                    },
                        ensure_ascii=False,
                        separators=(",", ":")
                    )
                )
            )


logging.info("Copying static data")
for file in glob.glob(r'./mtr/*.json'):
    shutil.copy(file, "waypoints")
for file in glob.glob(r'./lrt/*.json'):
    shutil.copy(file, "waypoints")
for file in glob.glob(r'./ferry/*.json'):
  shutil.copy(file, "waypoints")
for file in glob.glob(r'./mtr-bus/*.json'):
  shutil.copy(file, "waypoints")
