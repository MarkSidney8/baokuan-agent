# 部署指南（CentOS 服务器，Docker 方式）

## 1. 服务器准备

```bash
# 安装 Docker（CentOS 7/8/9 通用）
sudo yum install -y yum-utils
sudo yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
sudo yum install -y docker-ce docker-ce-cli containerd.io
sudo systemctl enable --now docker

# 放行端口（如用云厂商安全组，也要在控制台放行 8000）
sudo firewall-cmd --permanent --add-port=8000/tcp
sudo firewall-cmd --reload
```

## 2. 拉代码并启动

```bash
git clone https://github.com/MarkSidney8/baokuan-agent.git
cd baokuan-agent
docker build -t baokuan-agent .

# 生成一个随机密钥（只做一次，记下来）
openssl rand -hex 32

# 启动（把下面 <随机密钥> 换成上一步的结果）
docker run -d --name baokuan --restart always \
  -p 8000:8000 \
  -e SECRET_KEY="<随机密钥>" \
  -v /opt/baokuan-data:/srv/baokuan \
  baokuan-agent

docker logs -f baokuan   # 看到 init 日志即启动成功，Ctrl+C 退出查看
```

## 3. 登录使用

- 浏览器打开 `http://服务器IP:8000`
- 管理员账号 `admin` / `admin123`，**首次登录会强制改密码**
- 在「团队管理」里给成员开账号
- 在「系统设置」页选择 AI 服务商（DeepSeek / OpenAI / 通义千问 / Kimi /
  智谱 GLM / 豆包 / 自定义）并填写 API Key，Base URL 和模型名会自动填好、
  也可手动改任意模型，点「测试连接」验证后保存即生效，无需改服务器环境变量；
  不填也不影响其他功能，只是 AI 按钮会提示未配置

## 4. 日常更新

```bash
cd baokuan-agent
git pull
docker build -t baokuan-agent .
docker rm -f baokuan
docker run -d --name baokuan --restart always \
  -p 8000:8000 \
  -e SECRET_KEY="<之前那个随机密钥>" \
  -v /opt/baokuan-data:/srv/baokuan \
  baokuan-agent
```

数据库在 `/opt/baokuan-data/baokuan.db`，定期备份这个文件即可。

## 5. 可选：域名 + HTTPS（nginx 反代）

```bash
sudo yum install -y nginx certbot python3-certbot-nginx
```

nginx 配置示例（`/etc/nginx/conf.d/baokuan.conf`）：

```nginx
server {
    listen 80;
    server_name your-domain.com;
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

```bash
sudo nginx -t && sudo systemctl enable --now nginx
sudo certbot --nginx -d your-domain.com   # 自动签发 HTTPS 证书
```
