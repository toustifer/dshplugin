# 安装、多盘符与环境配置指南

本指南面向需要在新环境安装、重构或调试本插件的开发者与 Agent。

---

## 1. 架构组件清单

整个可视化套件由四个协同组件组成：

1. **`manim-mcp`**：Python stdio MCP 服务，暴露 8 个动画制作与校验工具。
2. **`media-mcp`**：Python stdio MCP 服务，暴露 `mcp__media__publish_file`，实现多模态文件在聊天流中的安全发布。
3. **`dsh-manim-gallery`**：DSH 前端原生插件，注册在右侧抽屉栏的「动画库」Tab。
4. **`dsh-media-view`**：DSH 前端原生插件，接管 `mcp__media__publish_file` 的专用卡片渲染器。

---

## 2. 标准安装流水线

核心安装逻辑由 `tools/dsh_installer.py` 保障，它通过 pytest 进行逐字节的安装/卸载还原断言。

```powershell
cd <path-to-dshplugin>

# 1. 模拟执行：检查各项环境与即将修改的文件（绝不写入任何文件）
.\install.ps1 -DryRun

# 2. 真实执行：安装插件、挂载 MCP、建立符号链接
.\install.ps1
```

### 安装完成后的必须动作
**必须重启 DSH Web 进程才能生效！**
```powershell
& "$HOME\.dsh\restart-web.ps1"
```
原因：DSH 客户端插件在 Web 服务启动时打包编译到 rev-keyed 静态资源图中，仅刷新浏览器页面无法加载新插件。

---

## 3. 多盘符（Multi-Drive）与路径陷阱

这是 Windows 系统与 Node.js 宿主环境最具欺骗性的陷阱，务必牢记：

### 陷阱机制
在前端对话流中，Markdown 仅接受以 `/` 开头的同源路径（如 `![anim](/path/to/renders/.../out.gif)`）。
Node.js 宿主端收到该路径后通过 `node:path.resolve(cwd, target)` 解析：
- 当实参以 `/` 开头时，**Node.js 会直接抛弃 `cwd` 中的所有目录层级，仅仅保留 `cwd` 的驱动器盘符（Drive Letter）！**
- 若宿主运行在 `C:\Users\...`，而动画渲染存放在 `D:\projects\...`：
  - `resolve('C:\...', '/projects/.../out.gif')` 会解析为 `C:\projects\...`（直接触发 **404 Not Found**）！

### 官方标准解法
`install.ps1` 会在 `~/.dsh/profiles/web/cordis.patch.yml` 中自动植入 `fs-sandbox` 覆盖配置，将文件系统的解析基准盘符锁定到与渲染根目录相同的盘符：
```yaml
- id: fs-sandbox
  config:
    cwd: '<render_root_parent_dir>'
```
只要 cwd 处于同一盘符，去掉盘符的绝对路径（如 `/projects/...`）就能被 `path.resolve` 正确映射。

---

## 4. 探针验证

排查图片是否显示时，切勿瞎猜。在终端运行专用探针：

```powershell
$c = Get-Content "$env:USERPROFILE\.dsh\.credentials.yaml" -Raw
$env:DSH_SECRET = [regex]::Match($c,'client-connection/browser-session:[\s\S]*?secret:\s*(\S+)').Groups[1].Value
node tests/manual/probe_file_api.mjs
```
- 若返回 `200 image/gif`，说明路径形式、同源签名、盘符钉扎全部正常。
- 若返回 `404`，核对盘符是否飘回了 C 盘。
- 若返回 `401`，说明缺少 session token 或 cookie。
