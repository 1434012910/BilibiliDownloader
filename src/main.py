import logging
import os
import sys
from urllib.parse import urljoin
from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtWidgets import QApplication
from src.utils.utils import  generate_qrcode, qrcode_to_pixmap, create_window
from src.core.data_loader import DataLoader
from src.core.network_fetcher import NetworkFetcher
from src.core.network_parser import NetworkParser
from src.core.submit_data import SubmitData
from src.utils.utils import (
    cookie_str_to_dict, get_sec_ch_ua, get_platform,
    get_random_ua, get_sec_ch_ua_mobile, extract_bv_id,
    check_file_integrity, find_highest_quality_file_index,
    merge_audio_video, get_file_format, delete_file, get_media_info, generate_random_cookie
)

class BilibiliDownloader:
    def __init__(self):
        self.login_timer = None
        self.audio_info = {}
        self.video_info = {}
        self.loader = DataLoader()
        self.fetcher = NetworkFetcher()
        self.parser = NetworkParser()
        self.submit = SubmitData()
        self.config = None
        self.logging=None


    def _initialize_config(self):
        """初始化并验证配置"""
        self.config = self.loader.loader("config")
        self.loader.loader("logging_config")
        # 获取日志记录器
        self.logging= logging.getLogger(__name__)
        # 处理 cookies
        if not isinstance(self.config.get("cookies", {}), dict) and self.config.get("cookies", ""):
            self.config["cookies"] = cookie_str_to_dict(self.config.get("cookies", ""))
        else:
            self.app = QApplication(sys.argv)
            pass
        # 设置请求头
        headers = self.config.setdefault("headers", {})
        if not headers.get("user-agent"):
            ua = get_random_ua()
            headers.update({
                "user-agent": ua,
                "sec-ch-ua": get_sec_ch_ua(ua),
                "sec-ch-ua-platform": get_platform(ua),
                "sec-ch-ua-mobile": get_sec_ch_ua_mobile(ua)
            })



    def _login_get_cookies(self):
        random_cookies=generate_random_cookie()
        passport_login=self.fetcher.fetch({
            "request_type":"passport_login",
            "link":self.config.get("passport_login", {}),
            "headers":self.config["headers"],
            "cookies":random_cookies,
        })
        passport_login_url=passport_login.get("json","").get("data","").get("url","")
        qrcode_key=passport_login.get("json","").get("data","").get("qrcode_key","")
        qr_image = generate_qrcode(passport_login_url)
        pixmap = qrcode_to_pixmap(qr_image)
        # 创建并显示窗口
        window = create_window(pixmap)
        window.show()
       #-------------------------------------
        timer = QTimer(parent=None)
        timer.timeout.connect(lambda: self._check_login_status(window, timer, qrcode_key))
        # 每3秒检查一次
        timer.start(3000)
        self.exit_code = self.app.exec_()

    def _check_login_status(self,window, timer, qrcode_key):
        """检查登录状态"""
        response =self.fetcher.fetch({
            "request_type":"login_state",
            "passport_login_state":self.config.get("passport_login_state", ""),
            "qrcode_key":qrcode_key
        })
        if response and response.get("data","").get("data", {}).get("code") == 0:  # 登录成功
            timer.stop()
            QMessageBox.information(window, "登录成功", "您已成功登录!")
            window.close()

    @staticmethod
    def _get_media_info(media_type, bv_json):
        """从 BV JSON 中获取媒体（音频/视频）信息"""
        audio_list=[]
        if media_type == "audio":
            try:
                # 尝试获取 FLAC 音频
                flac_data = bv_json.get("data", {}).get("dash", {}).get("flac", {}).get("audio", {})
                if flac_data is not None:
                    if flac_data.get("baseUrl"):
                        codecs = flac_data.get("codecs", "")
                        return {
                            "link": flac_data["baseUrl"],
                            "audio_format": codecs.lower(),
                            "is_flac": True
                        }
            except Exception as e:
                # 如果没有 FLAC，回退到普通音频
                audio_list = bv_json.get("data", {}).get("dash", {}).get("audio", [])
            if not audio_list:
                audio_list = bv_json.get("data", {}).get("dash", {}).get("audio", [])
            max_audio = audio_list[find_highest_quality_file_index(audio_list)]
            codecs = max_audio.get('codecs', "")
            return {
                "link": max_audio.get('baseUrl', ""),
                "audio_format": codecs.split('.')[0].lower(),
                "is_flac": False
            }
        #-----------------视频--------------------------
        elif media_type == "video":
            video_list = bv_json.get("data", {}).get("dash", {}).get("video", [])
            if not video_list:
                return None

            max_video = video_list[find_highest_quality_file_index(video_list)]
            mime_type = max_video.get('mime_type', "")
            return {
                "link": max_video.get('baseUrl', ""),
                "video_format": mime_type.split('/')[-1].lower()
            }

        return None

    def _download_media(self, media_type, media_info, bv_id, file_download_path):
        """下载媒体文件（音频或视频）"""
        # 准备下载信息
        download_info = {
            "link": media_info["link"],
            "request_type": "file_size",
            "data_type": media_type
        }

        # 获取文件大小
        size_info = self.fetcher.fetch(download_info)
        # 准备文件路径
        file_ext = media_info.get(f"{media_type}_format", "mp4")
        temp_filename = f"temp_{bv_id}_{size_info.get('type', '')}.{file_ext}"
        file_path = os.path.join(file_download_path, temp_filename)

        # 检查文件是否已存在
        existing_size = check_file_integrity(file_path)
        if existing_size == size_info["size"]:
            return {"complete": True, "filepath": file_path}

        # 下载文件内容
        download_info.update({
            "request_type": "file_content",
            "existing_size": existing_size,
            "total_size": size_info["size"]
        })
        try:
            content = self.fetcher.fetch(download_info)
        except Exception as e:
            self.logging.info("请求文件内容失败:{} {}".format(bv_id,e))
            return
        if not content.get("response"):
            self.logging.info(f"未能采集到{bv_id}的内容 - 响应状态: {content.get('status_code')}")

        # 保存文件
        save_result = self.submit.submit({
            "response": content["response"],
            "file_type": f"{media_type}_content",
            "filepath": file_path,
            "submit_type": "local",
            "total_size":size_info["size"],
            "bv_id": bv_id
        })

        save_result["filepath"] = file_path
        return save_result

    def download_audio(self, bv_json, bv_id, file_download_path):
        """下载 Bilibili 视频中的音频"""
        audio_info = self._get_media_info("audio", bv_json)
        if not audio_info:
            self.logging.info("未采集到相应音频链接:{}".format(bv_id))

        self.audio_info = self._download_media("audio", audio_info, bv_id, file_download_path) or {}

    def download_video(self, bv_json, bv_id, file_download_path):
        """下载 Bilibili 视频"""
        video_info = self._get_media_info("video", bv_json)
        if not video_info:
            self.logging.info("未采集到相应视频链接:{}".format(bv_id))

        self.video_info = self._download_media("video", video_info, bv_id, file_download_path) or {}

    def _process_download(self, link_info):
        """处理单个下载链接"""
        link = link_info.get("link", "")
        download_info = link_info.get("download_info", "").lower()
        bv_id = extract_bv_id(link)
        if not bv_id:
            self.logging.info(f"链接中无效的 BV ID: {link}")
            return
        # 获取视频信息
        try:
            bv_dict = self.fetcher.fetch({
                "link": urljoin(self.config["site"], link),
                "cookies": self.config["cookies"],
                "request_type": "bv_info",
                "headers": self.config["headers"],
                "site": self.config["site"]
            })
            if not bv_dict.get("text"):
                self.logging.info(f"BV ID 的信息为空: {bv_id}")
                return
        except Exception:
            self.logging.info(f"请求BV ID 的信息失败: {bv_id}")
            return
        try:
            bv_content = self.parser.parse(bv_dict)
        except Exception:
            self.logging.info("解析BV信息失败:{}".format(bv_id))
            return
        bv_json = bv_content.get("data", {})
        bv_title = bv_content.get("title", f"bilibili_{bv_id}")
        # 下载请求的媒体
        file_download_path = self.config["file_download_path"]
        #v是video
        if download_info in ("-v", ""):
            self.download_video(bv_json, bv_id, file_download_path)
        #a是audio
        if download_info in ("-a", ""):
            self.download_audio(bv_json, bv_id, file_download_path)

        # 处理下载的文件
        self._process_downloaded_files(bv_title, file_download_path,bv_id)

    def _process_downloaded_files(self, bv_title, file_download_path,bv_id):
        """合并或重命名下载的文件"""
        try:
            audio_complete = self.audio_info.get("complete", False)
            video_complete = self.video_info.get("complete", False)
            if audio_complete and video_complete:
                output_path = os.path.join(file_download_path, f"{bv_title}{get_file_format(self.video_info['filepath'])}")
                if os.path.exists(output_path):
                    self.logging.warning(f"输出文件已存在，将删除: {output_path}")
                    try:
                        os.remove(output_path)
                    except OSError as e:
                        self.logging.info(f"删除已存在文件失败: {str(e)}")
                        return
                # 合并音频和视频
                if merge_audio_video(
                        video_path=self.video_info["filepath"],
                        audio_path=self.audio_info["filepath"],
                        output_path=output_path
                ):
                    delete_file(self.video_info["filepath"])
                    delete_file(self.audio_info["filepath"])
            elif audio_complete:
                # 重命名音频文件
                old_path = self.audio_info["filepath"]
                file_format=get_media_info(self.audio_info['filepath'])
                file_format=file_format.get("audio_codec",".m4a")
                if file_format=="aac":
                    file_format="m4a"
                new_path = os.path.join(file_download_path, f"{bv_title}.{file_format}")
                os.rename(old_path, new_path)
        except Exception as e:
            self.logging.info(f"处理下载文件{bv_id}时出错: {str(e)}", exc_info=True)

    def main(self):
        """下载器的主入口点"""
        self._initialize_config()
        self.logging.info("Bilibili下载器启动")
        if not self.config.get("cookies", ""):
            self._login_get_cookies()
        download_links = self.loader.loader("download_link_path",download_link_path=self.config['download_link_path'])
        for index, link_info in enumerate(download_links, 1):
            try:
                self.logging.info(f"开始处理:{link_info.get("link","")}")
                self._process_download(link_info)
                self.logging.info(f"{link_info.get("link", "")} 处理完成")
            except Exception as e:
                self.logging.critical(f"Bilibili下载器:第 {index} 个任务出错:{str(e).replace("\n"," ")}", exc_info=True)
                continue
        sys.exit(self.exit_code)


if __name__ == '__main__':
    downloader = BilibiliDownloader()
    downloader.main()