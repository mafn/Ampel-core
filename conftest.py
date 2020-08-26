
import pytest
import subprocess
import time
import os
import tempfile
import itertools

from io import BytesIO
from glob import glob
import fastavro

collect_ignore = ['ampel/test/fixtures.py']
pytest_plugins = ['ampel.test.fixtures']

def alert_blobs():
    parent = os.path.dirname(os.path.realpath(__file__)) + '/../'
    for fname in glob(parent+'alerts/ipac/*.avro'):
        with open(fname, 'rb') as f:
            yield f.read()

@pytest.fixture
def cutout_alert_generator():
    from ampel.t0.load.TarballWalker import TarballWalker
    def alerts(with_schema=False):
        atat = TarballWalker('/ztf/cutouts/ztf_20180523_programid1.tar.gz')
        for fileobj in itertools.islice(atat.get_files(), 0, 1000, 100):
            reader = fastavro.reader(fileobj)
            alert = next(reader)
            if with_schema:
                yield alert, reader.schema
            else:
                yield alert
    yield alerts


