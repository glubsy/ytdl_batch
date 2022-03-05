

class File():
  def __init__(self, filename, videoId,  date) -> None:
      self.name = filename
      self.videoId = videoId
      self.date = date

  def __repr__(self) -> str:
      return f"{self.name}"

class Video(File):
  pass

class TwitchVideo(Video):
  pass

class YoutubeVideo(Video):
  pass

class Sub(File):
  pass

class TwitchSub(Sub):
  pass

class YoutubeSub(Sub):
  pass


TEST_CASES = [
  TwitchVideo(
    "20220121 AmarisYuri PARANORMAL-SCARY VIDEOS [270]_1271243650.mp4",
    "1271243650",
    "20220121"),
  TwitchSub(
    "20220121_1271243650.json",
    "1271243650",
    "20220121"),
  TwitchVideo(
    "20211223 AmarisYuri You want to do WHAT with the bear! [270]_v1241120429.mp4",
    "1241120429",
    "20211223"),
  YoutubeVideo(
    "20220106 Gawr Gura Ch. hololive-EN chat with mee_[240]_zp0sfEVWH9A.mkv",
    "zp0sfEVWH9A",
    "20220106"),
  YoutubeSub(
    "20220106 Gawr Gura Ch. hololive-EN chat with mee_[240]_zp0sfEVWH9A.live_chat.json",
    "zp0sfEVWH9A",
    "20220106"),
  YoutubeVideo(
    "20220201 Gawr Gura [test] testname [240]_zwEIsPcwwdk.mp4",
    "zwEIsPcwwdk",
    "20220201"),
  TwitchVideo(
    '20220204 [Amaris Yuri] LETS GET TO KNOW EACH OTHER MORE! [270]_v1286818234.mp4',
    '1286818234',
    '20220204'),
  TwitchVideo(
    '20220124 Amaris Yuri SUPER SEISO LEOPARD PLAYING WITH HER FOOD(SUBSCRIBERS!) [270]_1274522871.mp4',
    '1274522871',
    '20220124'),
]