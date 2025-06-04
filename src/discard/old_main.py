import os.path
from urllib.parse import urljoin
from nibabel.brikhead import filepath
from twisted.python.formmethod import Submit
from src.core.data_loader import DataLoader
from src.core.network_fetcher import NetworkFetcher
from src.core.network_parser import NetworkParser
from src.core.submit_data import SubmitData

from src.utils.utils import cookie_str_to_dict, get_sec_ch_ua, get_platform, get_random_ua, get_sec_ch_ua_mobile, \
    extract_bv_id, check_file_integrity, find_highest_quality_file_index, merge_audio_video, get_file_format, \
    delete_file


class Bilibili:
    def __init__(self):
        self.audio_info = {}
        self.video_info = {}
        self.loader = DataLoader()
        self.fetcher=NetworkFetcher()
        self.parser=NetworkParser()
        self.submit=SubmitData()

    def download_audio(self,bv_json,bv_id,file_download_path):
        try:
            flac_link = bv_json.get("data", {}).get("dash", {}).get("flac", {}).get("audio", {}).get("baseUrl", "")
        except Exception as e:
            flac_link = ""
        if flac_link:
            mime_type = bv_json.get("data", {}).get("dash", {}).get("flac", {}).get("audio", {}).get("mime_type", "")
            audio_format = mime_type.split('/')[-1]
            audio_info = {
                "link": flac_link,
                "request_type": "file_size",
                "data_type": "audio",
                "audio_format": audio_format
            }
        else:
            audio_list = bv_json.get("data", {}).get("dash", {}).get("audio", [])
            max_audio_index = find_highest_quality_file_index(audio_list)
            max_audio_info = audio_list[max_audio_index]
            audio_link = max_audio_info.get('baseUrl', "")
            mime_type = max_audio_info.get('mime_type', "")
            audio_format = mime_type.split('/')[-1]
            audio_info = {
                "link": audio_link,
                "request_type": "file_size",
                "data_type": "audio",
                "audio_format": audio_format
            }
        type_size = self.fetcher.fetch(audio_info)
        audio_info["total_size"] = type_size.get("size", 0)
        audio_file_path = os.path.join(file_download_path, "".join(
            ["temp_", bv_id, "_", type_size.get("type", ""), ".", audio_info.get("audio_format", "mp4")]))
        existing_size = check_file_integrity(audio_file_path)
        audio_info["request_type"] = "file_content"
        audio_info["existing_size"] = existing_size
        if audio_info["existing_size"]==audio_info["total_size"]:
            self.audio_info["complete"]=True
            self.audio_info["filepath"] = audio_file_path
            return
        audio_content = self.fetcher.fetch(audio_info)
        if audio_content.get("response", "") == "":
            return
        audio_info["response"] = audio_content.get("response", "")
        audio_info["file_type"] = "video_content"
        audio_info["filepath"] = audio_file_path
        audio_info["submit_type"] = "local"
        download_status = self.submit.submit(audio_info)
        download_status["filepath"]=audio_file_path
        self.audio_info=download_status


    def download_video(self,bv_json,bv_id,file_download_path):
        video_list = bv_json.get("data", {}).get("dash", {}).get("video", [])
        max_video_index = find_highest_quality_file_index(video_list)
        max_video_info = video_list[max_video_index]
        mime_type = max_video_info.get('mime_type', "")
        video_link = max_video_info.get('baseUrl', "")
        video_format = mime_type.split('/')[-1]
        video_info = {
            "link": video_link,
            "request_type": "file_size",
            "data_type": "video"
        }
        type_size = self.fetcher.fetch(video_info)
        video_info["total_size"] = type_size.get("size", 0)
        video_file_path = os.path.join(file_download_path,
                                       "".join(["temp_", bv_id, "_", type_size.get("type", ""), ".", video_format]))
        existing_size = check_file_integrity(video_file_path)
        video_info["request_type"] = "file_content"
        video_info["existing_size"] = existing_size
        if video_info["existing_size"]==video_info["total_size"]:
            self.video_info["complete"]=True
            self.video_info["filepath"] = video_file_path
            return
        video_content = self.fetcher.fetch(video_info)
        if video_content.get("response", "") == "":
            return
        video_info["response"] = video_content.get("response", "")
        video_info["file_type"] = "video_content"
        video_info["filepath"] = video_file_path
        video_info["submit_type"] = "local"
        download_status = self.submit.submit(video_info)
        download_status["filepath"] = video_file_path
        self.video_info=download_status



    def main(self):
        config=self.loader.load_config()
        download_link_path=config.get('download_link_path')
        info_link=self.loader.load_download_info(download_link_path)
        cookies_dict=cookie_str_to_dict(config.get("cookies",""))
        config["cookies"]=cookies_dict
        site=config.get("site","")
        file_download_path=config.get('file_download_path',"")
        if config.get("headers",{}).get("user-agent","")=="":
            ua=get_random_ua()
            sec_ch_ua=get_sec_ch_ua(ua)
            platform=get_platform(ua)
            sec_ch_ua_mobile=get_sec_ch_ua_mobile(ua)
            config["headers"]["user-agent"]=ua
            config["headers"]["sec-ch-ua"] = sec_ch_ua
            config["headers"]["sec-ch-ua-platform"] = platform
            config["headers"]["sec-ch-ua-mobile"] = sec_ch_ua_mobile
        for info in info_link:
            link=info.get("link","")
            download_info=info.get("download_info","")
            bv_id=extract_bv_id(link)
            url=urljoin(site,link)
            bv_info={
                "link":url,
                "cookies":config.get("cookies",""),
                "request_type":"bv_info",
                "headers":config.get("headers", ""),
                "site": config.get("site", ""),
            }
            bv_dict=self.fetcher.fetch(bv_info)
            bv_text=bv_dict.get("text")
            if bv_text:
                bv_content=self.parser.parse(bv_dict)

            else:
                bv_content={}
            bv_json=bv_content.get("data",{})
            bv_title=bv_content.get("title","")
            #--------------视频内容-------------------------
            if download_info=="视频" or download_info=="":
                self.download_video(bv_json=bv_json,bv_id=bv_id,file_download_path=file_download_path)
            #-----------------音频内容--------------------
            if download_info =="音频" or download_info=="":
                self.download_audio(bv_json=bv_json,bv_id=bv_id,file_download_path=file_download_path)
            #---------------合并文件---------------------------
            if self.audio_info.get("complete", "") == True and self.video_info.get("complete", "") == True:
                file_format=get_file_format(self.video_info["filepath"])
                output_filepath="{}{}{}".format(file_download_path,bv_title,file_format)
                if merge_audio_video(video_path=self.video_info["filepath"],audio_path=self.audio_info["filepath"],output_path=output_filepath):
                    delete_file(self.video_info["filepath"])
                    delete_file(self.audio_info["filepath"])
            elif self.audio_info.get("complete", "") == True and self.video_info.get("complete", "")=="":
                file_format = get_file_format(self.audio_info["filepath"])
                output_filepath = "{}{}{}".format(file_download_path, bv_title, file_format)
                os.rename(self.audio_info["filepath"], output_filepath)


if __name__ == '__main__':
    bilibili = Bilibili()
    bilibili.main()
