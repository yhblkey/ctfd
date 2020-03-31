# ctfd
ctfd环境 添加plugin-AWD plugin-dynamic 插件 

## ctfd 插件使用说明

### plugin-awd

---

将该目录完整的粘贴到ctfd/plugins/目录下

然后创建挑战类型 选择plugin-awd类型

配置好AWD竞赛的比分板页面和flag提交地址即可使用，此模块需要配合本项目的AWD框架使用。



### plugin-dynamic

---

本模块主要功能用于创建为每一用户创建专属的题目容器

安装方法：

将该目录完整的粘贴到ctfd/plugins/目录下

在ctfd/的同目录下创建frp/目录，并创建frpc.ini,根据实例填写内容

在插件的配置目录下根据提示填好配置信息即可

然后创建挑战类型 选择plugin-dynamic类型

注意在启动ctfd容器前需要首先启动 frps，使用本项目的docker-compose.yml启动ctfd容器。

```
frps.ini 配置实例

[common]
bind_port = 7000
vhost_http_port = 80
vhost_https_port = 443
subdomain_host = ctf-test.com    #此处填写自己的域名 使用二级域名时 需要将泛域名*.ctf-test.com 解析到自身服务器IP

frpc.ini
[common]
server_addr = 192.168.0.21  # 服务器IP
server_port = 7000
admin_addr = 0.0.0.0
admin_port = 7400

```

参考链接：

- https://github.com/glzjin/CTFd-Whale
- https://github.com/fatedier/frp/blob/master/README_zh.md



## 完整安装

可以在release处下载完整环境，解压后直接运行`docker-compose up -d`

如果拉取镜像过慢的话 可以配置加速器

```
{
  "registry-mirrors": [
    "https://dockerhub.azk8s.cn",
    "https://hub-mirror.c.163.com"
  ]
}

亲测 速度飞快
```

注意使用dynamic插件之前 一定要运行frps。
