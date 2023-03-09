from typing import Optional
import os
import json
import importlib

from pystats2md.stats_file import StatsFile
from networkxum.helpers import *


class P0Config(object):
    """
        A singleton configuration class.
        Retreives and parses environment variables and generates
        DB server URLs based on configuration files: `P0ConfigDBs.json`
        and `P0ConfigDatasets.json`.
    """

    __shared = None

    @staticmethod
    def shared():
        if P0Config.__shared is None:
            P0Config()
        return P0Config.__shared

    def __init__(self, device_name='MacbookPro'):
        if P0Config.__shared is not None:
            raise Exception("This class is a singleton!")

        self.device_name = os.getenv('DEVICE_NAME', device_name)
        self.count_finds = int(os.getenv('COUNT_FINDS', '20000'))
        self.count_analytics = int(os.getenv('COUNT_ANALYTICS', '300'))
        self.count_changes = int(os.getenv('COUNT_CHANGES', '10000'))

        self.default_stats_file = StatsFile(
            f'BenchGraphs/{device_name}/PyStorageDBs.json')
        self.databases = self.load_json('BenchGraphs/P0ConfigDBs.json')
        self.datasets = self.load_json('BenchGraphs/P0ConfigDatasets.json')
        self.test_dataset = {
            "name": "GraphTest",
            "path": "Datasets/GraphTest/edges.csv",
            "nodes": 8,
            "edges": 10,
            "size_mb": 1,
            "enabled": True
        }
        P0Config.__shared = self

    def make_db(self, database: dict, dataset: dict) -> Optional[object]:
        if (not database['enabled']) or (not dataset['enabled']):
            return None

        url = os.getenv(database['url_variable_name'],
                        database['url_default'])
        url = url.replace('${DATASET_NAME}', dataset['name'])

        module = importlib.import_module(database['module_name'])
        class_ = getattr(module, database['class_name'])
        instance = class_(url=url)

        return instance

    def normalize_path(self, path: str) -> str:
        return os.path.abspath(os.path.expanduser(path))

    def load_json(self, path: str) -> dict:
        with open(path, 'r') as f:
            return json.load(f)

    def run(self):
        pass


def class_name(cls: type) -> str:
    if isinstance(cls, type):
        return cls.__name__
    else:
        return cls.__class__.__name__


if __name__ == "__main__":
    P0Config().run()
