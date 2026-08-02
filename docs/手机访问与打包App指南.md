# 贾维斯管家 · 手机访问 + 打包成 App 指南

> 您说「用手机多一点」—— 这篇文档列出所有可行方案，**从最简单到最专业**，您按自己的情况选一个。

---

## 🥇 方案一：PWA「添加到主屏幕」(5 分钟搞定，推荐先用这个)

贾维斯前端已经做好了移动端适配 + iOS/Android 的 PWA meta 标签。
这个方案的效果：**手机桌面上出现一个叫 "JARVIS" 的图标，点它直接全屏打开，跟 App 一模一样**，而且不需要装任何软件、不需要上架应用商店。

### 操作步骤（iPhone）：

1. 让贾维斯运行在您的电脑/服务器上（`python app.py`）
2. 先确保手机和电脑**连同一个 Wi-Fi**
3. 在电脑终端执行 `ipconfig`（Windows）或 `ifconfig`/`ip a`（Mac/Linux），找到电脑的局域网 IP，例如 `192.168.1.100`
4. iPhone 打开 **Safari**（必须 Safari，Chrome 不行）访问 `http://192.168.1.100:8000`
5. 点击屏幕底部中间的 **分享按钮**（方框加向上箭头）
6. 往下滑，找到 **「添加到主屏幕」** → 命名 `JARVIS` → 添加
7. 回到桌面，就有一个贾维斯的图标了！点进去是全屏的，没有浏览器地址栏，跟 App 完全一样。

### 操作步骤（安卓）：

1. 先拿到电脑的局域网 IP，手机和电脑在同一 Wi-Fi
2. 手机打开 **Chrome** 访问 `http://电脑IP:8000`
3. 浏览器会弹出 **「添加应用到主屏幕」** 的横幅 → 点它
4. 如果没弹横幅 → 点 Chrome 右上角菜单 → **「安装应用」** 或 **「添加到主屏幕」**

### 这个方案的优缺点：

| ✅ 优点 | ❌ 缺点 |
|---|---|
| 5 分钟搞定，不用写任何代码 | 只能在**同一个 Wi-Fi 下**用（除非配合方案三的外网穿透） |
| 跟原生 App 一样，全屏 + 桌面图标 | iOS 上 iOS 16.4 以下可能偶尔刷新 |
| 免费 | 推送通知有限（可以用 Server-Sent Events 简单实现） |

---

## 🥈 方案二：外网穿透（在家里跑贾维斯，但手机 4G/5G 也能用）

**原理**：您家电脑/树莓派上跑贾维斯，用一个"内网穿透工具"把它暴露到公网，手机走到哪里都能访问。

### 推荐 3 种穿透工具（按难度排序）：

#### A. Cloudflare Tunnel（最推荐！免费 + 不用公网 IP + 自带 HTTPS）

```bash
# 1. 下载 cloudflared 命令行工具（Mac/Linux/Windows 都有）
#    官网：https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/

# 2. 一条命令搞定（不需要注册域名也行，CF 给你一个 trycloudflare.com 的域名）
cloudflared tunnel --url http://localhost:8000
```

执行后会输出一个类似 `https://xxx-xxx-xxx.trycloudflare.com` 的 URL ——
**这个 URL 在全世界任何地方都能访问您的贾维斯，手机 4G/5G 也能用。**

然后回到**方案一**的 PWA 步骤，用这个 URL 加到手机主屏幕 → **搞定**。

#### B. Tailscale（适合多台设备自己用，打一个虚拟局域网）

1. 官网 https://tailscale.com/ 下载（免费版支持 100 台设备）
2. 您的电脑和手机都登录同一个 Tailscale 账号
3. 两边都连上后，电脑会拿到一个 `100.x.x.x` 的虚拟 IP
4. 手机浏览器访问 `http://100.x.x.x:8000` → 然后 PWA 添加到桌面

**优点**：完全私有，没有流量经过第三方服务器，速度最快
**缺点**：每台要访问贾维斯的设备都得装 Tailscale 客户端

#### C. frp（需要一台有公网 IP 的云服务器）

如果您已经有阿里云 / 腾讯云的云服务器，可以用 frp：
- 服务端 `frps` 装在云服务器上
- 客户端 `frpc` 装在家里的电脑上，把 `8000` 端口映射出去
- 云服务器再加个 Nginx 反代 + HTTPS（Let's Encrypt 免费证书）

适合有经验的用户，配置略复杂，速度最稳定。

---

## 🥉 方案三：打包成真正的桌面 + 移动 App（进阶）

### A. 桌面 App（Windows/Mac/Linux）→ **Electron 或 Tauri**（1~2 小时搞定）

#### Electron 版（新手友好，缺点：打包出来 ~150MB）

1. 前端再加一个 `electron/` 目录，写一个 main.js：
   ```javascript
   // electron/main.js（核心逻辑就 20 行）
   const { app, BrowserWindow } = require('electron')
   const { spawn } = require('child_process')
   const path = require('path')

   let backend = null
   function createWindow() {
     const win = new BrowserWindow({
       width: 1200, height: 800,
       title: 'JARVIS',
       icon: path.join(__dirname, 'icon.png'),
       backgroundColor: '#02060c',
     })
     // 先启动后端（python app.py），然后加载前端
     const python = process.platform === 'win32' ? 'python.exe' : 'python3'
     backend = spawn(python, ['app.py'], {
       cwd: path.join(__dirname, '..', 'backend'),
       stdio: 'inherit',
     })
     setTimeout(() => win.loadURL('http://localhost:8000'), 2500)
   }
   app.whenReady().then(createWindow)
   app.on('window-all-closed', () => {
     backend && backend.kill()
     app.quit()
   })
   ```
2. 用 `electron-builder` 一键打包成 `.exe` / `.dmg` / `.AppImage`
3. **效果**：用户双击图标就能打开贾维斯，**完全不需要懂 Python，不需要装 Node**，跟普通软件一模一样。

#### Tauri 版（体积小 ~10MB，但是要装 Rust）

适合追求体积的用户，套路跟 Electron 几乎一样，只是用 Rust 包一层 WebView。

---

### B. 真正的手机 App（安卓 APK / 苹果 IPA）→ Capacitor 或 Flutter（1~2 天）

⚠️ 注意：这个方案**前提是您先做了方案二的外网穿透**（不然 App 装了也连不到家里的贾维斯）。

#### Capacitor 方式（推荐！因为前端已经是 Vue 3，几乎不用改代码）

```bash
cd frontend
npm install @capacitor/core @capacitor/cli @capacitor/android @capacitor/ios
npx cap init JARVIS com.yourname.jarvis
# 把 vite.config.js 的 base 改成 './'
npm run build
npx cap add android
npx cap add ios
npx cap sync

# 安卓：
npx cap open android   # 打开 Android Studio，点 Build → Build APK
# iOS：
npx cap open ios       # 打开 Xcode，插上 iPhone → Run
```

**核心改动**：前端 API 地址从 `/api/*` 改成 `https://您的穿透域名/api/*`（或者写一个设置页面让用户填服务器地址）。

**效果**：生成一个 `jarvis.apk`，直接在手机上安装 → 桌面图标 → 点开就是 App，跟微信 / 支付宝一样，**不需要浏览器**。

#### 上架 App Store / Google Play？（没必要，也很难）

- 安卓：直接发 APK 给朋友安装就行（手机要开"允许未知来源"）
- iPhone：用 TestFlight（免费），或者自己开发者账号 688 元/年 → 自签 7 天会过期，长期用建议还是 PWA 方案 + 付费开发者账号

---

### C. 微信 / 飞书 / Telegram 机器人（终极方案，手机体验最好）

这个方案**体验最好**——因为您天天都用微信/飞书，不用装额外 App。

**原理**：
1. 后端 FastAPI 不动
2. 新增一个 `bot.py` 文件，对接：
   - 飞书 / 钉钉自建应用（webhook）
   - Telegram Bot API（最简单，免费）
   - 企业微信应用
   - 微信公众号 / 企业微信（难点：个人号不好对接，建议用企业微信）
3. 收到用户消息 → 调后端的 `POST /api/chat` → 拿到回复 → 发回给聊天窗口

**效果**：在微信 / 飞书 / Telegram 里直接发消息给贾维斯，跟跟普通聊天一样，**手机 4G/5G 直接用，还能收到倒计时提醒**（机器人主动发消息）。

我给您写一个最小可用的 Telegram Bot 模板（30 行），只要把 Token 填进去就能跑：

```python
""" bot_telegram.py — 放到 backend/ 下，python bot_telegram.py 启动
申请 Bot：找 @BotFather → /newbot → 拿到一串 TOKEN
"""
import asyncio
import httpx
from aiogram import Bot, Dispatcher, types

BOT_TOKEN = "在这里填您的 BotFather 给的 TOKEN"
BACKEND_URL = "http://127.0.0.1:8000"  # 跟贾维斯后端对话

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message()
async def chat_with_jarvis(message: types.Message):
    if not message.text or not message.text.strip():
        return
    status = await message.answer("（贾维斯正在处理…）")
    try:
        async with httpx.AsyncClient(timeout=120) as c:
            r = await c.post(f"{BACKEND_URL}/api/chat", json={"text": message.text})
        data = r.json()
        reply = data.get("reply", "（无响应）")
        # 如果有工具结果，一起附上
        if data.get("tool_display"):
            reply += "\n\n🔧 工具结果：\n" + data["tool_display"]
        await status.edit_text(reply)
    except Exception as e:
        await status.edit_text(f"⚠ 连接失败：{e}")

if __name__ == "__main__":
    asyncio.run(dp.start_polling(bot))
```

依赖：`pip install aiogram httpx`

---

## 📋 我的推荐（按您的情况排优先级）

| 您的情况 | 推荐方案 |
|---|---|
| **先试试能不能用 / 最简单** | 🥇 方案一：PWA 添加到主屏幕 + 同一 Wi-Fi |
| **出了门也想用，手机 4G/5G 访问** | 🥇+🥈A：PWA + Cloudflare Tunnel（一条命令搞定） |
| **希望完全不用浏览器，像微信一样聊** | 🥉C：飞书 / Telegram 机器人（收消息主动推） |
| **想发给朋友也能用、真·安装包** | 🥉B：Capacitor 打 APK + 外网穿透 |
| **换电脑都要能打开，不用本地安装** | 🥉A：Electron 打包桌面版发给您自己 |

---

## 📱 移动端 UI 适配说明（已内置完成）

我已经在代码里做了这些手机适配：

1. `index.html` 加了 `viewport-fit=cover` + iOS 全屏 meta + 主题色 + 100dvh 防键盘
2. `Chat.vue` 加了 iOS 键盘监听（focusout + visualViewport resize），键盘弹起自动滚到底 + 底部加 padding 不遮挡
3. `Chat.vue` 移动端发送按钮缩成图标 + textarea 只占 1 行
4. `App.vue` ≤900px 时侧边栏缩成 64px 图标栏
5. `style.scss` 移除了移动端点击高亮和长按菜单（更像原生 App）

如果您还想让我帮您实现：Telegram 机器人 / 飞书机器人 / Electron 打包 / Capacitor 打包 → 直接跟我说，我把相应的代码文件加进项目就可以了 🛡️
