# -*- coding: utf-8 -*-
"""
Created on Tue Jul  2 21:11:05 2019

@author: quanfita
"""
import sys,os
import imageio
from bs4 import BeautifulSoup
imageio.plugins.ffmpeg.download()

import requests, time, hashlib, urllib.request, re, json
from moviepy.editor import *
from PyQt5.QtWidgets import (QDialog,QLabel,QLineEdit,QApplication,
                             QComboBox,QPushButton,QColorDialog,
                             QFileDialog,QWidget,QProgressBar,QListWidget,
                             QListWidgetItem)
from PyQt5.QtCore import Qt,QRegExp,QSettings,QThread,pyqtSignal
from PyQt5.QtGui import QIcon,QRegExpValidator,QFont,QColor

class MainWindow(QWidget):
    signal = pyqtSignal(int)
    def __init__(self):
        super().__init__()
        self.setWindowModality(Qt.ApplicationModal)
        self.resize(640, 480)
        self.setFixedSize(640, 480)
        self.setWindowTitle('bilibili Videos Download')
        self.video_queue = []
        self.quality='80'
        self.cid_list = []
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/55.0.2883.87 Safari/537.36'
        }
        
        self.search_label = QLabel('url/av:',self)
        self.search_label.setGeometry(60,50,50,30)
        
        self.search_line = QLineEdit(self)
        self.search_line.setPlaceholderText("Please input the video's url or number")
        self.search_line.setGeometry(120,50,400,30)
        
        
        self.search_button = QPushButton('search',self)
        self.search_button.setGeometry(520,50,80,30)
        self.search_button.clicked.connect(self.showVideoInfo)
        
        self.download_button = QPushButton('Start Download',self)
        self.download_button.setGeometry(280,100,120,30)
        self.download_button.clicked.connect(self.download_videos)
        
        self.queue_button = QPushButton('Add to Queue',self)
        self.queue_button.setGeometry(80,100,120,30)
        self.queue_button.clicked.connect(self.addToQueue)
        
        self.video_label = QLabel('',self)
        self.video_label.setGeometry(60,150,250,200)
        self.video_label.setWordWrap(True)
        self.video_label.setAlignment(Qt.AlignLeft|Qt.AlignTop)
        
        self.video_list = QListWidget(self)
        self.video_list.setGeometry(320,150,250,200)
        
        self.download_progress = QProgressBar(self)
        self.download_progress.setGeometry(60,420,560,30)
        self.download_progress.setRange(0,100)
        
        self.show()
        
    def getVideoInfo(self,url):
        html = requests.get(url,headers=self.headers).content
        soup = BeautifulSoup(html,'lxml')
        divs = soup.select('#viewbox_report')
        title = divs[0].h1.span.text
        cat = divs[0].select('.video-data')[0].span.text
        date = divs[0].select('.video-data')[0].find_all('span')[-1].text
        print(title)
        print(cat)
        print(date)
        return title,cat,date
    
    def showVideoInfo(self):
        # 获取视频的cid,title
        url = self.search_line.text()
        title,cat,date = self.getVideoInfo(url)
        self.start_url = 'https://api.bilibili.com/x/web-interface/view?aid=' + re.search(r'/av(\d+)/*', url).group(1)
        html = requests.get(self.start_url, headers=self.headers).json()
        data = html['data']
        self.video_title=data["title"].replace(" ","_")
        
        string = 'title:' + title + '\npartition:' + cat +'\ndate:' + date +'\n'
        self.video_label.setText(string)
        pass
    
    def addToQueue(self):
        newitem = QListWidgetItem()
        newitem.setText(self.video_title)
        newitem.setTextAlignment(Qt.AlignLeft)
        self.video_list.addItem(newitem)
        self.video_queue.append(self.start_url)
        pass
    
    def download_videos(self):
        self.down = Downloader(self.video_queue)
        self.down.signal.connect(self.setProgressValue)
        self.down.signal_final.connect(self.clearList)
        self.down.start()
    
    def setProgressValue(self,value):
        self.download_progress.setValue(value)
        
    def clearList(self):
        self.video_list.clear()
        self.video_queue.clear()
        self.download_progress.setValue(0)

class Downloader(QThread):
    signal = pyqtSignal(int)
    signal_final = pyqtSignal()
    def __init__(self,urls):
        super().__init__()
        self.is_working = True
        self.urls = urls
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/55.0.2883.87 Safari/537.36'
        }
        pass
    def run(self):
        for url in self.urls:
            try:
                html = requests.get(url, headers=self.headers).json()
                data = html['data']
                if '?p=' in url:
                    # 单独下载分P视频中的一集
                    p = re.search(r'\?p=(\d+)',url).group(1)
                    self.cid_list.append(data['pages'][int(p) - 1])
                else:
                    # 如果p不存在就是全集下载
                    self.cid_list = data['pages']
                for item in self.cid_list:
                    cid = str(item['cid'])
                    title = item['part']
                    if not title:
                        title = self.video_title
                    title = re.sub(r'[\/\\:*?"<>|]', '', title)  # 替换为空的
                    print(cid,title)
                    page = str(item['page'])
                    url = url + "/?p=" + page
                    video_list = self.get_play_list(url, cid, '80')
                    self.start_time = time.time()
                    self.down_video(video_list, title, url, page)
                    self.combine_video(video_list, title)
            except:
                print("ERROR")
        self.signal_final.emit()
        pass
    
    def get_play_list(self, start_url, cid, quality):
        entropy = 'rbMCKn@KuamXWlPMoJGsKcbiJKUfkPF_8dABscJntvqhRSETg'
        appkey, sec = ''.join([chr(ord(i) + 2) for i in entropy[::-1]]).split(':')
        params = 'appkey=%s&cid=%s&otype=json&qn=%s&quality=%s&type=' % (appkey, cid, quality, quality)
        chksum = hashlib.md5(bytes(params + sec, 'utf8')).hexdigest()
        url_api = 'https://interface.bilibili.com/v2/playurl?%s&sign=%s' % (params, chksum)
        headers = {
            'Referer': start_url,  # 注意加上referer
            'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/55.0.2883.87 Safari/537.36'
        }
        # print(url_api)
        html = requests.get(url_api, headers=headers).json()
        # print(json.dumps(html))
        video_list = [html['durl'][0]['url']]
        # print(video_list)
        return video_list
    
    def Schedule_cmd(self,blocknum, blocksize, totalsize):
        speed = (blocknum * blocksize) / (time.time() - self.start_time)
        # speed_str = " Speed: %.2f" % speed
        speed_str = " Speed: %s" % self.format_size(speed)
        recv_size = blocknum * blocksize
    
        # 设置下载进度条
        f = sys.stdout
        pervent = recv_size / totalsize
        #self.download_progress.setValue(int(pervent * 100))
        self.signal.emit(int(pervent * 100))
        percent_str = "%.2f%%" % (pervent * 100)
        n = round(pervent * 50)
        s = ('#' * n).ljust(50, '-')
        f.write(percent_str.ljust(8, ' ') + '[' + s + ']' + speed_str)
        f.flush()
        # time.sleep(0.1)
        f.write('\r')
    
    
    def Schedule(self,blocknum, blocksize, totalsize):
        speed = (blocknum * blocksize) / (time.time() - self.start_time)
        # speed_str = " Speed: %.2f" % speed
        speed_str = " Speed: %s" % self.format_size(speed)
        recv_size = blocknum * blocksize
    
        # 设置下载进度条
        #f = sys.stdout
        pervent = recv_size / totalsize
        self.download_progress.setValue(int(pervent * 100))
        #percent_str = "%.2f%%" % (pervent * 100)
        #n = round(pervent * 50)
        #s = ('#' * n).ljust(50, '-')
        #print(percent_str.ljust(6, ' ') + '-' + speed_str)
        #f.flush()
        time.sleep(2)
        # print('\r')
    
    
    # 字节bytes转化K\M\G
    def format_size(self,bytes):
        try:
            bytes = float(bytes)
            kb = bytes / 1024
        except:
            print("传入的字节格式不对")
            return "Error"
        if kb >= 1024:
            M = kb / 1024
            if M >= 1024:
                G = M / 1024
                return "%.3fG" % (G)
            else:
                return "%.3fM" % (M)
        else:
            return "%.3fK" % (kb)
    
    
    #  下载视频
    def down_video(self,video_list, title, start_url, page):
        num = 1
        print('[正在下载P{}段视频,请稍等...]:'.format(page) + title)
        currentVideoPath = os.path.join(sys.path[0], 'bilibili_video', title)  # 当前目录作为下载目录
        for i in video_list:
            opener = urllib.request.build_opener()
            # 请求头
            opener.addheaders = [
                # ('Host', 'upos-hz-mirrorks3.acgvideo.com'),  #注意修改host,不用也行
                ('User-Agent', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.13; rv:56.0) Gecko/20100101 Firefox/56.0'),
                ('Accept', '*/*'),
                ('Accept-Language', 'en-US,en;q=0.5'),
                ('Accept-Encoding', 'gzip, deflate, br'),
                ('Range', 'bytes=0-'),  # Range 的值要为 bytes=0- 才能下载完整视频
                ('Referer', start_url),  # 注意修改referer,必须要加的!
                ('Origin', 'https://www.bilibili.com'),
                ('Connection', 'keep-alive'),
            ]
            urllib.request.install_opener(opener)
            # 创建文件夹存放下载的视频
            if not os.path.exists(currentVideoPath):
                os.makedirs(currentVideoPath)
            # 开始下载
            if len(video_list) > 1:
                urllib.request.urlretrieve(url=i, filename=os.path.join(currentVideoPath, r'{}-{}.mp4'.format(title, num)),reporthook=Schedule_cmd)  # 写成mp4也行  title + '-' + num + '.flv'
            else:
                urllib.request.urlretrieve(url=i, filename=os.path.join(currentVideoPath, r'{}.mp4'.format(title)),reporthook=self.Schedule_cmd)  # 写成mp4也行  title + '-' + num + '.flv'
            num += 1
    
    # 合并视频
    def combine_video(self,video_list, title):
        currentVideoPath = os.path.join(sys.path[0], 'bilibili_video', title)  # 当前目录作为下载目录
        if len(video_list) >= 2:
            # 视频大于一段才要合并
            print('[下载完成,正在合并视频...]:' + title)
            # 定义一个数组
            L = []
            # 访问 video 文件夹 (假设视频都放在这里面)
            root_dir = currentVideoPath
            # 遍历所有文件
            for file in sorted(os.listdir(root_dir), key=lambda x: int(x[x.rindex("-") + 1:x.rindex(".")])):
                # 如果后缀名为 .mp4/.flv
                if os.path.splitext(file)[1] == '.flv':
                    # 拼接成完整路径
                    filePath = os.path.join(root_dir, file)
                    # 载入视频
                    video = VideoFileClip(filePath)
                    # 添加到数组
                    L.append(video)
            # 拼接视频
            final_clip = concatenate_videoclips(L)
            # 生成目标视频文件
            final_clip.to_videofile(os.path.join(root_dir, r'{}.mp4'.format(title)), fps=24, remove_temp=False)
            print('[视频合并完成]' + title)
    
        else:
            # 视频只有一段则直接打印下载完成
            print('[视频合并完成]:' + title)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = MainWindow()
    sys.exit(app.exec_())