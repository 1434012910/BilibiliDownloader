import json
import re

from bs4 import BeautifulSoup
from lxml import etree

from src.interfaces.parse import DataParse



class NetworkParser(DataParse):
    def parse(self,data):
        parse_type=data.get("parse_type")
        text=data.get("text","")
        if parse_type=="bv_info":
            return self._parse_bv_info(text)



    @staticmethod
    def _parse_bv_info(text):
        data=""
        tree=etree.HTML(text)
        title="".join(tree.xpath('.//div[@class="video-info-title-inner"]/h1/text()'))
        title = re.sub(r'[\\/*?:"<>|]', '', title)
        title = title.strip(' .')
        soup = BeautifulSoup(text, 'html.parser')
        for script in soup.find_all('script'):
            script_text = script.string
            if script_text and 'window.__playinfo__' in script_text:
                match = re.search(
                    r'window\.__playinfo__\s*=\s*({.*?})(?:\s*;|\s*$)',
                    script_text,
                    re.DOTALL
                )
                if match:
                    json_str = match.group(1)
                    if len(json_str) > 8000:
                        data = json.loads(json_str)
        return {"title":title,"data":data}

