"""GUI 配置工具 — automatic-lamp 本地设置入口。

双击运行：python gui_config.py  或  打包后 automatic-lamp.exe
保存到：~/.automatic-lamp/config.json （跨平台，下次免填）

配置加载顺序（后者覆盖前者）：
  1. ~/.automatic-lamp/config.json  ← GUI 保存的首选来源
  2. 进程环境变量（AI_API_KEY 等）   ← GitHub Actions / 命令行
"""

import json
import os
import sys
import threading
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from pathlib import Path


# ========== 常用 Provider 模板 ==========
# 键是 Provider 显示名，值是默认 model + base_url
PROVIDER_PRESETS = {
    "DeepSeek（推荐，最便宜）": {
        "model": "deepseek/deepseek-chat",
        "base_url": "",
        "api_key_env": "DEEPSEEK_API_KEY",
        "hint": "注册即送 500 万 tokens，￥0.1/1k tokens",
        "sign_up": "https://platform.deepseek.com/api_keys",
    },
    "硅基流动 SiliconFlow": {
        "model": "openai/deepseek-chat",
        "base_url": "https://api.siliconflow.cn/v1",
        "api_key_env": "SILICONFLOW_API_KEY",
        "hint": "国内加速，￥0.05/1k tokens",
        "sign_up": "https://cloud.siliconflow.cn/account/ak",
    },
    "通义千问 DashScope": {
        "model": "qwen/qwen-plus",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "api_key_env": "DASHSCOPE_API_KEY",
        "hint": "阿里云生态，有免费额度",
        "sign_up": "https://dashscope.console.aliyun.com/",
    },
    "火山方舟 Volcengine": {
        "model": "openai/ark-code-latest",
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "api_key_env": "ARK_API_KEY",
        "hint": "字节跳动出品",
        "sign_up": "https://console.volcengine.com/ark",
    },
    "本地 Ollama（完全免费）": {
        "model": "ollama/qwen2.5:7b",
        "base_url": "http://localhost:11434",
        "api_key_env": "",  # 本地不需要 Key
        "hint": "本地跑模型，零费用，首次需 ollama pull qwen2.5:7b",
        "sign_up": "",
    },
    "自定义（手动填）": {
        "model": "",
        "base_url": "",
        "api_key_env": "AI_API_KEY",
        "hint": "手动指定 model + base_url + API Key",
        "sign_up": "",
    },
}

CONFIG_DIR = Path.home() / ".automatic-lamp"
CONFIG_PATH = CONFIG_DIR / "config.json"


# ========== 读写配置 ==========

def load_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_config(cfg: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


def apply_config_to_env(cfg: dict) -> None:
    """把配置注入 os.environ，供 main.py 读取。"""
    if cfg.get("api_key"):
        os.environ["AI_API_KEY"] = cfg["api_key"]
    if cfg.get("model"):
        os.environ["AI_MODEL"] = cfg["model"]
    if cfg.get("base_url"):
        os.environ["AI_BASE_URL"] = cfg["base_url"]
    # 兼容各 provider 自己的 env 名
    if cfg.get("api_key") and cfg.get("api_key_env"):
        os.environ[cfg["api_key_env"]] = cfg["api_key"]


# ========== GUI ==========

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("🏮 automatic-lamp · AI 配置工具")
        self.geometry("640x560")
        self.resizable(False, False)

        # 加载已有配置
        cfg = load_config()

        # === 变量 ===
        self.provider_var = tk.StringVar(value=cfg.get("provider", "DeepSeek（推荐，最便宜）"))
        self.api_key_var = tk.StringVar(value=cfg.get("api_key", ""))
        self.model_var = tk.StringVar(value=cfg.get("model", "deepseek/deepseek-chat"))
        self.base_url_var = tk.StringVar(value=cfg.get("base_url", ""))
        self.wecom_var = tk.StringVar(value=cfg.get("wecom_webhook", ""))
        self.show_key_var = tk.BooleanVar(value=False)

        self._build_ui()
        self._on_provider_change()  # 同步默认值
        self._log("✅ 配置已加载" if cfg else "💡 首次使用，请填写 AI API Key 后点保存")

    def _build_ui(self):
        pad = {"padx": 10, "pady": 4}

        # === AI 配置区 ===
        ai_frame = ttk.LabelFrame(self, text="🤖 AI 模型配置（LiteLLM 统一接入）")
        ai_frame.pack(fill="x", **pad)

        # Provider 下拉
        ttk.Label(ai_frame, text="Provider（服务提供商）:").grid(row=0, column=0, sticky="w", padx=6, pady=6)
        provider_cb = ttk.Combobox(ai_frame, textvariable=self.provider_var,
                                   values=list(PROVIDER_PRESETS.keys()),
                                   state="readonly", width=30)
        provider_cb.grid(row=0, column=1, columnspan=2, sticky="w", padx=6, pady=6)
        provider_cb.bind("<<ComboboxSelected>>", lambda e: self._on_provider_change())

        # API Key
        ttk.Label(ai_frame, text="API Key:").grid(row=1, column=0, sticky="w", padx=6, pady=6)
        key_entry = ttk.Entry(ai_frame, textvariable=self.api_key_var, width=48,
                              show="" if self.show_key_var.get() else "*")
        key_entry.grid(row=1, column=1, sticky="we", padx=6, pady=6)
        self.key_entry = key_entry

        show_btn = ttk.Checkbutton(ai_frame, text="显示", variable=self.show_key_var,
                                   command=self._toggle_show_key)
        show_btn.grid(row=1, column=2, padx=4)

        ttk.Button(ai_frame, text="获取 Key", width=8,
                   command=self._open_signup).grid(row=1, column=3, padx=4)

        # Model
        ttk.Label(ai_frame, text="Model:").grid(row=2, column=0, sticky="w", padx=6, pady=6)
        ttk.Entry(ai_frame, textvariable=self.model_var, width=48).grid(
            row=2, column=1, sticky="we", padx=6, pady=6)

        # Base URL
        ttk.Label(ai_frame, text="Base URL（可选）:").grid(row=3, column=0, sticky="w", padx=6, pady=6)
        ttk.Entry(ai_frame, textvariable=self.base_url_var, width=48).grid(
            row=3, column=1, sticky="we", padx=6, pady=6)

        # Hint
        self.hint_label = ttk.Label(ai_frame, text="", foreground="#666")
        self.hint_label.grid(row=4, column=0, columnspan=4, sticky="w", padx=6, pady=(2, 6))

        ai_frame.columnconfigure(1, weight=1)

        # === 企业微信（可选）===
        wc_frame = ttk.LabelFrame(self, text="💬 企业微信 Webhook（可选，不配也能生成 PDF）")
        wc_frame.pack(fill="x", **pad)
        ttk.Label(wc_frame, text="Webhook URL:").pack(side="left", padx=6, pady=6)
        ttk.Entry(wc_frame, textvariable=self.wecom_var).pack(side="left", fill="x", expand=True, padx=6, pady=6)

        # === 按钮 ===
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill="x", **pad)

        ttk.Button(btn_frame, text="💾 保存配置", command=self._save).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="🔌 测试连接", command=self._test).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="▶️ 立即生成今日 PDF",
                   command=self._run_main).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="🗂 打开输出目录",
                   command=self._open_output).pack(side="left", padx=4)

        # === 日志 ===
        log_frame = ttk.LabelFrame(self, text="📋 运行日志")
        log_frame.pack(fill="both", expand=True, **pad)
        self.log_text = scrolledtext.ScrolledText(log_frame, height=10, state="disabled",
                                                  font=("Consolas", 9))
        self.log_text.pack(fill="both", expand=True, padx=6, pady=6)

    # === 事件处理 ===
    def _toggle_show_key(self):
        show = "" if self.show_key_var.get() else "*"
        self.key_entry.configure(show=show)

    def _on_provider_change(self):
        preset = PROVIDER_PRESETS.get(self.provider_var.get(), {})
        if preset:
            self.model_var.set(preset.get("model", ""))
            self.base_url_var.set(preset.get("base_url", ""))
            self.hint_label.configure(text=f"💡 {preset.get('hint', '')}")

    def _open_signup(self):
        preset = PROVIDER_PRESETS.get(self.provider_var.get(), {})
        url = preset.get("sign_up", "")
        if url:
            import webbrowser
            webbrowser.open(url)
        else:
            messagebox.showinfo("提示", "本地 Ollama 不需要在线注册。\n命令行执行：ollama pull qwen2.5:7b")

    def _collect_cfg(self) -> dict:
        preset = PROVIDER_PRESETS.get(self.provider_var.get(), {})
        return {
            "provider": self.provider_var.get(),
            "api_key": self.api_key_var.get().strip(),
            "model": self.model_var.get().strip(),
            "base_url": self.base_url_var.get().strip(),
            "api_key_env": preset.get("api_key_env", ""),
            "wecom_webhook": self.wecom_var.get().strip(),
        }

    def _save(self):
        cfg = self._collect_cfg()
        save_config(cfg)
        apply_config_to_env(cfg)
        # 企业微信也注入
        if cfg.get("wecom_webhook"):
            os.environ["WECOM_WEBHOOK"] = cfg["wecom_webhook"]
        self._log("✅ 配置已保存到 ~/.automatic-lamp/config.json")

    def _test(self):
        cfg = self._collect_cfg()
        apply_config_to_env(cfg)
        if cfg.get("wecom_webhook"):
            os.environ["WECOM_WEBHOOK"] = cfg["wecom_webhook"]
        self._log("🔌 正在测试 LiteLLM 连接...")
        threading.Thread(target=self._do_test, args=(cfg,), daemon=True).start()

    def _do_test(self, cfg: dict):
        try:
            from src.ai_enhancer import is_ai_available, _call_llm
            from src.config import AIConfig
            ai_cfg = AIConfig(model=cfg["model"], base_url=cfg.get("base_url", ""))

            if not is_ai_available(ai_cfg):
                self._log("❌ AI 未启用：请先填写 API Key")
                return

            self._log(f"  model={ai_cfg.model}  base_url={ai_cfg.base_url or '(默认)'}")
            self._log("  发送最小请求（仅测试连通性）...")

            resp = _call_llm(
                system_prompt="你是一个测试助手。",
                user_prompt="请只回答：连接成功",
                cfg=ai_cfg,
                expect_json=False,
            )
            if resp:
                self._log(f"✅ AI 连接成功！模型返回：{resp[:100]}")
            else:
                self._log("❌ AI 调用返回空值，请检查 model 格式或 Key 权限")
        except Exception as e:
            self._log(f"❌ 连接失败：{type(e).__name__}: {str(e)[:200]}")

    def _run_main(self):
        cfg = self._collect_cfg()
        apply_config_to_env(cfg)
        if cfg.get("wecom_webhook"):
            os.environ["WECOM_WEBHOOK"] = cfg["wecom_webhook"]
        self._save()
        self._log("▶️ 开始生成今日备考资料...")
        threading.Thread(target=self._do_run, daemon=True).start()

    def _do_run(self):
        try:
            # 重定向 main 的 log 到 GUI
            from src.utils import log
            log.info("=" * 50)
            from src.main import run
            comments, news = run()
            self._log(f"✅ 完成！评论 {comments} 篇，新闻 {news} 条")
            self._log(f"📄 PDF 已生成在 ./output/ 目录")
        except Exception as e:
            import traceback
            self._log(f"❌ 运行失败：{type(e).__name__}: {str(e)}")
            self._log(traceback.format_exc()[-400:])

    def _open_output(self):
        out = Path("./output").resolve()
        out.mkdir(parents=True, exist_ok=True)
        if sys.platform.startswith("win"):
            os.startfile(str(out))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            os.system(f'open "{out}"')
        else:
            os.system(f'xdg-open "{out}"')

    def _log(self, msg: str):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", msg + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")


def load_env_from_config():
    """如果 GUI config.json 存在，提前注入到环境变量。
    这样从命令行 python main.py 也能读到 GUI 保存的配置。"""
    cfg = load_config()
    if cfg:
        apply_config_to_env(cfg)
        if cfg.get("wecom_webhook"):
            os.environ["WECOM_WEBHOOK"] = cfg["wecom_webhook"]
        return True
    return False


if __name__ == "__main__":
    load_env_from_config()
    App().mainloop()
