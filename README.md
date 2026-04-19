# mc-botserver

fork 并修改自 https://github.com/Minecraft-QQBot/BotServer

## 部署

克隆并进入项目目录下

### 创建共享网络

当前编排使用外部共享网络 mc-bot，供其他 mc bot 相关容器共同接入

如果首次部署，请先创建网络：

```bash
sudo docker network create mc-bot
```

### 运行

启动

```bash
sudo docker compose up -d
```

查看日志

```bash
sudo docker compose logs -f mc-botserver
```

关闭服务

```bash
sudo docker compose down
```

## 配置

### napcat

首先部署并启动 [napcat](https://github.com/NapNeko/NapCatQQ) 服务（需要在同一个共享网络 mc-bot 下），登录 qq

在其 webui 网络配置中（如：[http://127.0.0.1:6099/webui/network](http://127.0.0.1:6099/webui/network)）新建一个 websocket 客户端并启用，URL 配置参考：

```bash
# napcat 服务需要在同一个共享网络 mc-bot 下
# `mc-botserver` 是网络 mc-bot 中，此容器的名称
ws://mc-botserver:8000/onebot/v11/ws
```

### mc-botserver

在 webui（[http://127.0.0.1:8000/webui](http://127.0.0.1:8000/webui)）或配置文件 `.env` 中修改配置，之后重启即可应用