Win7 贾维斯懒人包 · 使用说明
=====================================

这个目录是给 Win7 老笔记本专用的一键脚本，不用懂命令行，双击就行。

┌─────────────────────────────────────┐
│  0. 下载必须软件（先做，1 小时搞定） │
└─────────────────────────────────────┘
- Python 3.8.10 (唯一支持 Win7 的 Python 版本)
    64位：https://www.python.org/ftp/python/3.8.10/python-3.8.10-amd64.exe
    32位：https://www.python.org/ftp/python/3.8.10/python-3.8.10.exe
    ⚠️ 安装时最下面一定要勾：Add Python 3.8 to PATH
    建议装到 C:\Python38（不带空格的路径最稳）

- Git for Windows 2.40.1（下载代码用，嫌麻烦可以不装，用 GitHub ZIP）
    64位：https://github.com/git-for-windows/git/releases/download/v2.40.1.windows.1/Git-2.40.1-64-bit.exe

- NSSM 2.24（注册成 Windows 服务，开机自启用）
    官网：https://nssm.cc/release/nssm-2.24.zip
    解压 → 取 win64/nssm.exe → 复制到 C:\Windows\System32\
    （或者直接复制到 本 scripts\win7\ 目录，脚本会自动复制）

- Cloudflare cloudflared 2023.8.2（出门手机访问贾维斯用，可选）
    64位：https://github.com/cloudflare/cloudflared/releases/download/2023.8.2/cloudflared-windows-amd64.msi
    32位：https://github.com/cloudflare/cloudflared/releases/download/2023.8.2/cloudflared-windows-386.msi
    （2023.8.2 是最后一个支持 Win7 的版本）

┌─────────────────────────────────────┐
│  1. 先做电源设置（非常重要！）       │
└─────────────────────────────────────┘
1. 开始 → 控制面板 → 电源选项 → 选「高性能」
2. 更改计划设置：
   - 关闭显示器（接电源）：1 分钟
   - 使计算机进入睡眠：从不 ← 最关键！
3. 「更改高级电源设置」：
   - 硬盘 → 在此时间后关闭硬盘 → 0（从不）
   - USB 选择性暂停 → 禁用
   - 关闭盖子操作（接电源）→ 不采取任何操作
4. 开机自动登录（断电重启自动进系统）：
   Win+R → 输入 control userpasswords2 → 确定
   取消勾选「要使用本机，用户必须输入用户名和密码」→ 应用
   输入您的 Win7 登录密码两次 → 确定
5. 关闭 Windows Update（老机器别更了，容易蓝屏）：
   开始 → 控制面板 → Windows Update → 更改设置 → 从不检查更新

┌─────────────────────────────────────┐
│  2. 按顺序双击脚本运行              │
└─────────────────────────────────────┘
  1_安装依赖.bat        ← 第一个运行，安装 Python 库（10 分钟）
  2_本地测试启动.bat    ← 第二个运行，测试大脑能不能跑
                            看到 "Uvicorn running on http://0.0.0.0:8000" 就成功
                            浏览器打开 http://127.0.0.1:8000 能看到界面 → OK
                            然后 Ctrl+C 关掉窗口
  3_安装服务_贾维斯.bat ← 右键「以管理员身份运行」！
                            把贾维斯注册成系统服务（开机自启 + 崩溃自动重启）
                            完成后不用开任何窗口，贾维斯后台默默跑
  4_数据备份.bat        ← 每月点一次，把记忆数据库压缩备份
  99_卸载服务.bat       ← 不想用了右键管理员运行

┌─────────────────────────────────────┐
│  3. 访问贾维斯的几种方式            │
└─────────────────────────────────────┘
✅ 本机（老笔记本自己）:
  http://127.0.0.1:8000  或  https://emmioop.github.io/kizuna-ai/
  （GitHub Pages 前端，Settings 页后端地址填 http://127.0.0.1:8000 测试）

✅ 家里同 Wi-Fi 手机/电脑：
  老笔记本查 IP（CMD 里 ipconfig，一般是 192.168.1.xxx）
  手机浏览器 → http://192.168.1.xxx:8000

✅ 出门 4G/5G（永久固定地址）：
  - 买 1 个便宜域名（.top 8块钱一年）
  - 注册 Cloudflare → 域名托管过去
  - 管理员 CMD：
      cloudflared tunnel login
      cloudflared tunnel create jarvis
      cloudflared tunnel route dns jarvis jarvis.您的域名.top
  - 生成配置文件：C:\Windows\System32\config\systemprofile\.cloudflared\config.yml
    参考 docs/ 目录下的完整文档
  - 再运行一次 3_安装服务_贾维斯.bat，会询问「要不要一起装隧道服务？」输入 Y
  - 手机随时访问 https://jarvis.您的域名.top

┌─────────────────────────────────────┐
│  4. 常见问题 FAQ                    │
└─────────────────────────────────────┘
Q: 1_安装依赖.bat 运行完 pip install 有红色 ERROR？
A: 别慌，90% 是网络问题。重新双击 1_安装依赖.bat 再跑一次，第二次一般就能装好。
   真不行的话把最后 20 行红色报错截图复制给贾维斯（AI），它会给您解决办法。

Q: 服务启动了但浏览器打不开？
A: 先看 logs\jarvis-err.log 有没有报错；
   然后 CMD 管理员运行：netsh advfirewall firewall add rule name=Jarvis8000 dir=in action=allow protocol=TCP localport=8000

Q: 忘了数据库备份？
A: 把 backend\data\ 整个文件夹复制到 U 盘也行，里面 kizuna.db 就是全部记忆。

Q: 想升级贾维斯代码？
A: 未来有新版本了，把新项目的代码覆盖旧的（别覆盖 backend\data\ 目录！）
   然后：
     管理员 CMD：nssm restart JarvisAI
   （不用重新装依赖，除非新版本 requirements.txt 变了）
