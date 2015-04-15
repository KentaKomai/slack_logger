# coding:utf-8
#! /usr/bin/python

from datetime import *
from email.MIMEText import MIMEText
from email.Header import Header
from email.Utils import formatdate
import sys
import time
import urllib
import urllib2
import json
import smtplib


# ログを取得してメールする(デフォルトで前日)

""" API関連のグローバル変数 """
api_base_url = "https://slack.com/api/"
api_channel_history_url = api_base_url + "channels.history"
api_channel_info_url = api_base_url + "channels.info"
api_channel_list_url = api_base_url + "channels.list"
api_user_list_url = api_base_url + "users.list"

""" N日前からM日間のログを取得するかの設定 """
now = datetime.now()
oldest_day=-1 #1日前から
duration_day=1 #１日間
oldest = datetime(now.year, now.month, now.day,0,0,0,0) + timedelta(days=oldest_day)
latest = oldest + timedelta(days=duration_day)

def main(mail_to_address, channel_name, path_to_configure ):

  notice_config = json_parse(path_to_configure)
  token = notice_config['token']
  oldest_day= notice_config['start_day']
  duration_day= notice_config['duration_day']
  mail_from_address = notice_config['from_mail_address']

  # user一覧を取得
  users = get_users_info(token)
  # channel-infoを取得
  channel_list = find_channel(token, channel_name)
  # TODO:channelが見つからなければ終了
  c_id = channel_list[0]['id']
  channel_info = get_chennel_info(token, c_id)

  # チャンネル内のユーザの詳細取得
  channel_users_list = []
  for user in users:
    for member in channel_info['members']:
      if user['id'] == member:
        channel_users_list.append(user)
  
  history = get_channel_history(token, c_id)
  mail_body = u"\n\n"
  log_list = []
  if(len(history) == 0):
    mail_body = mail_body + oldest.strftime("%Y/%m/%d") + u"のログはありません"
  else:
    mail_body = mail_body + channel_name + oldest.strftime(" %Y/%m/%d") + u" Slackログ\n\n"

  for msg in history:
    dt = datetime.utcfromtimestamp(float(msg['ts']))
    if 'user' in msg:
      user = find_user(token, msg['user'], channel_users_list)
      if not isinstance(user, type(None)):
        log_list.append(SlackLog(user['name'], dt, msg['text']))
      else: # 既に存在しないユーザの場合
        log_list.append(SlackLog(msg['user'], dt, msg['text']))
    elif 'attachments' in msg:
      # プラグインが投げてるjsonフォーマットはプラグインごとに違うので、とりあえず中身全部つっこむ
      log_list.append(SlackLog("PLUGIN", dt, str(msg['attachments'])))
    else:
      # よくわからないメッセージはとりあえず突っ込む
      log_list.append(SlackLog("UNKNOWN", dt, str(msg['attachments'])))

  log_list.reverse()
  for log in log_list:
    mail_body = mail_body + log.format_message().decode("utf-8")

  mail_send(mail_from_address, mail_body, "Slack #" + channel_name + " " + oldest.strftime("%Y/%m/%d") + u"ログ", mail_to_address )

# 名前からチャンネル情報を取得する
def find_channel(token, channel_name):
  params = urllib.urlencode({'token':token})
  channel_list = request_to_json(api_channel_list_url, params)

  # 完全一致するものをリストで返す
  channelList = []
  for channel in channel_list['channels']:
    if(channel['name'] == channel_name):
        channelList.append(channel)

  return channelList

def json_parse(file_path):
  f = open(file_path, 'r')
  json_data = json.load(f)
  return json_data

def get_users_info(token):
  params = urllib.urlencode({'token':token})
  users_info = request_to_json(api_user_list_url, params)
  return users_info['members']

# channel_idからチャンネルの詳細を取得する
def get_chennel_info(token, channel_id):
  params = urllib.urlencode({'token':token, 'channel':channel_id})
  channel_info = request_to_json(api_channel_info_url,  params)
  return channel_info['channel']

# ログを取得する(1000件が最大なので1000件)
# oldest_day:何日前から取得するか
# latest_day:oldest_dayから何日分取得するか
def get_channel_history(token, channel_id):
  oldest_ts = time.mktime( oldest.timetuple() )
  latest_ts = time.mktime( latest.timetuple() )
  params = urllib.urlencode({'token':token, 'channel':channel_id, 'inclusive':'0', 'oldest':oldest_ts, 'latest':latest_ts, 'count':1000})
  channel_history = request_to_json(api_channel_history_url, params)
  return channel_history['messages']

def find_user(token, id, channel_user):
  for member in channel_user:
    if member['id'] == id:
      return member

def request_to_json(url, params):
  req = urllib2.Request(url, params)
  res = urllib2.urlopen(req)
  json_data = json.loads(res.read())

  if not json_data['ok']:
    exit #正しく取得できなかったら終了

  return json_data

def mail_send(mail_from_address, mail_body,mail_subject,mail_to_address):

  # mail_from_address = "slack-log@team-lab.com"
  # mail_to_address = "komaikenta@team-lab.com"
  #mail_subject = u"Slack #joyful-ec channel log"

  charset = "UTF8"

  msg = MIMEText(mail_body.encode(charset), "plain", charset)
  msg["Subject"] = Header(mail_subject, charset)
  msg["From"] = mail_from_address
  msg["Reply-to"] = mail_from_address
  msg["To"] = mail_to_address
  msg["Date"] = formatdate(localtime=True)

  smtp = smtplib.SMTP("mail.team-lab.com")
  smtp.sendmail(mail_from_address, mail_to_address, msg.as_string())
  smtp.close()


class SlackLog:
  def __init__(self, who, when, what):
    self.name = who
    self.time = when
    self.message = what

  def format_message(self):
    return self.name.encode('utf_8') + "\t" + str(self.time) + "\n\t\t" + self.message.encode('utf_8') + "\n"


if __name__ == "__main__":
  argvs = sys.argv
  if(len(argvs) != 4):
    print("<usage> python " + argvs[0] + " [to mail_address] [slack_channel_name] [path to configure json]")
    sys.exit
  else:
    main(argvs[1], argvs[2], argvs[3])


