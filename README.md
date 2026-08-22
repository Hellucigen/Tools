# Tools

自用小工具集。

## 工具列表

### steam_workshop_subscriber.py

Steam 创意工坊批量订阅器:扫描本地已安装模组,提取 Workshop ID,生成 HTML 清单 / SteamCMD 订阅脚本,或通过 Steam Web API 自动订阅。

```bash
# API key 从环境变量读取,不会保存在脚本里
set STEAM_API_KEY=你的key
python steam_workshop_subscriber.py --help
```

### card.py

终端扑克牌收集追踪器:54 张牌的网格展示、高亮切换、缺牌统计。

```bash
python card.py
```
