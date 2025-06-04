from urllib.parse import urljoin

import requests
from fake_useragent import UserAgent

from src.interfaces.fetch import NetworkFetch


class NetworkFetcher(NetworkFetch):
    def __init__(self):
        self.session = requests.Session()

    def fetch(self, data):
        request_type=data.get("request_type","")
        if request_type == "bv_info":
            cookies=data.get("cookies",{})
            headers=data.get("headers", {})
            params=data.get("params", {})
            link=data.get("link","")
            return self._request_bv_info(url=link,cookies=cookies,headers=headers,params=params)
        elif request_type == "file_size":
            link=data.get("link","")
            data_type=data.get("data_type","")
            return self._request_file_size(link,data_type)
        elif request_type == "file_content":
            link=data.get("link","")
            existing_size=data.get("existing_size",0)
            total_size=data.get("total_size",0)
            return self._request_link_content(link,existing_size,total_size)
        elif request_type == "passport_login":
            link=data.get("link","")
            headers=data.get("headers",{})
            cookies=data.get("cookies",{})
            return self._passport_login(link=link,headers=headers,cookies=cookies)
        elif request_type == "login_state":
            qrcode_key=data.get("qrcode_key","")
            passport_login_state=data.get("passport_login_state","")
            return self.qrcode_login_state(qrcode_key,passport_login_state)


    def _request_bv_info(self,cookies,headers,params,url):
        # self.session.headers.update(headers)
        # self.session.cookies.update(cookies)
        response = self.session.get(url,params=params)
        if response.status_code == 200:
            bv_info={
                "text": response.text,
                "parse_type":"bv_info"
            }
            return bv_info
        else:
            bv_info={
                "text": "",
                "parse_type":"bv_info"
            }
            return bv_info


    def _request_file_size(self,url,data_type):
        try:
            head_response = self.session.head(url)
            head_response.raise_for_status()
            total_size = int(head_response.headers.get('content-length', 0))
        except requests.exceptions.RequestException as e:
            total_size=-1

        data={
            "type":data_type,
            "size":total_size
        }
        return data


    def _request_link_content(self,url,existing_size,total_size):
        # head_response =self.session.head(url)
        # head_response.raise_for_status()
        # total_size = int(head_response.headers.get('content-length', 0))
        if 0 < total_size <= existing_size:
            return {"response":"","file_type":"video_content"}
        else:
            headers = {'Range': f'bytes={existing_size}-'}
            response = self.session.get(url, headers=headers, stream=True)
            response.raise_for_status()
            # if response.status_code != 206:
            #     print("服务器不支持断点下载")
            #     return {"response":"", "file_type":"video_content"}
            return {"response":response,"file_type":"video_content"}

    def _passport_login(self,link,headers,cookies):
        self.session.headers.update(headers)
        self.session.headers.update(cookies)
        response=self.session.get(link)
        # print("=== 会话Cookies ===")
        # print("Debug: After request, cookies =", self.session.cookies.get_dict())
        # for cookie in self.session.cookies:
        #     print(
        #         f"{cookie.name}: {cookie.value} "
        #         f"(Domain: {cookie.domain}, Path: {cookie.path}, Expires: {cookie.expires})")
        #     print("=================")
        return {"json":response.json(),"file_type":"passport_login"}


    def qrcode_login_state(self, qrcode_key,link):
        """轮询二维码登录状态"""
        params = {'qrcode_key': qrcode_key}
        response = self.session.get(
            link,
            params=params,
        )
        return {"data":response.json(),"file_type":"passport_login_state"}



