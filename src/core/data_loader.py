import json
import logging.config
import os
from datetime import date
from typing import Any

import pandas as pd


from src.interfaces.loader import Loader


class DataLoader(Loader):
    def __init__(self):
        self.config_path = os.path.join(os.path.dirname(__file__), '..', '..', 'config', 'config.json')
        self.logs_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'logs')
        self.config = None
    def loader(self,load_type,**kwargs):
        if load_type=="config":
            return self._load_config()
        elif load_type=="download_link_path":
            return self._load_download_info(kwargs.get("download_link_path"))
        elif load_type=="logging_config":
            return self._load_logging_config()

    def _load_config(self):
        with open(self.config_path, 'r', encoding='utf-8') as f:
            text=f.read()
            data=json.loads(text)
            self.config=data
        return data

    @staticmethod
    def _load_download_info(path):
        all_data=[]
        with open(path, 'r', encoding='utf-8') as f:
            for i in f:
                data = {}
                info=i.split(" ")
                data["link"]=info[0]
                if len(info)>1:
                    data["download_info"]="".join(info[-1]).replace("\n","").strip()
                else:
                    data["download_info"]=""
                all_data.append(data)
        return all_data

    def _load_logging_config(self):
        os.makedirs(self.logs_dir, exist_ok=True)
        self.config["logging"]['handlers']['file_handler']['filename'] = os.path.abspath(
            os.path.join(self.logs_dir, 'downloader.log')
        )
        logging.config.dictConfig(self.config["logging"])
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        ))
        logging.getLogger().addHandler(console_handler)






