import re
import logging
import requests
from io import BytesIO
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = "8353389128:AAFRwIXvys4K_vpKmP6V57lkAsZB42SSO2s"

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)

WELCOME_MESSAGE = """😤 প্রতিবার $10 দিয়া icon কিনতে কিনতে ক্লান্ত?
এই বটে আয়। HugeIcons বা FlatIcon\\-এর যেকোনো icon\\-এর link দে।
আমি SVG কইরা দিমু — একদম ফ্রি, একদম হালাল 😇
_\\(হালাল কিনা সেইটা তোর ব্যাপার\\)_

কীভাবে ব্যবহার করবি:
1\\. Icon\\-এর link copy কর
2\\. এই বটে paste কর
3\\. SVG নিয়া যা — কাজ শেষ ✌️"""

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


def detect_platform(url: str) -> str | None:
    if "hugeicons.com" in url:
        return "hugeicons"
    if "flaticon.com" in url:
        return "flaticon"
    return None


def fetch_hugeicons_svg(url: str) -> dict:
    match = re.search(r"hugeicons\.com/icon/([^?#]+)", url)
    if not match:
        raise ValueError("Invalid HugeIcons URL")

    icon_name = match.group(1)
    style_match = re.search(r"[?&]style=([^&]+)", url)
    style = style_match.group(1) if style_match else "stroke-rounded"

    cdn_url = f"https://cdn.hugeicons.com/icons/{icon_name}-{style}.svg?v=1.0.0"
    res = requests.get(cdn_url, headers={**HEADERS, "Referer": "https://hugeicons.com/"}, timeout=10)

    if res.status_code == 200 and "<svg" in res.text:
        return {"svg": res.text.strip(), "icon_name": icon_name, "style": style, "source": "HugeIcons"}

    # fallback: scrape the page
    page_res = requests.get(url, headers=HEADERS, timeout=10)
    svg_match = re.search(r"<svg[\s\S]*?</svg>", page_res.text, re.IGNORECASE)
    if svg_match:
        return {"svg": svg_match.group(0), "icon_name": icon_name, "style": style, "source": "HugeIcons"}

    raise ValueError("SVG not found on HugeIcons")


def fetch_flaticon_svg(url: str) -> dict:
    res = requests.get(url, headers=HEADERS, timeout=10)
    if res.status_code != 200:
        raise ValueError(f"FlatIcon page returned {res.status_code}")

    svg_match = re.search(r"<svg[\s\S]*?</svg>", res.text, re.IGNORECASE)
    if svg_match:
        return {"svg": svg_match.group(0), "source": "FlatIcon"}

    json_match = re.search(r'"svg"\s*:\s*"([^"]+)"', res.text)
    if json_match:
        svg = json_match.group(1).replace("\\n", "\n").replace('\\"', '"').replace("\\/", "/")
        return {"svg": svg, "source": "FlatIcon"}

    cdn_match = re.search(r"https://[^\s\"']+\.svg", res.text)
    if cdn_match:
        svg_res = requests.get(cdn_match.group(0), headers=HEADERS, timeout=10)
        if "<svg" in svg_res.text:
            return {"svg": svg_res.text.strip(), "source": "FlatIcon"}

    raise ValueError("SVG not found on FlatIcon")


def format_svg(svg: str) -> str:
    svg = re.sub(r"\s+", " ", svg)
    svg = svg.replace("> <", ">\n  <")
    return svg.strip()


def escape_md(text: str) -> str:
    return re.sub(r"([_*\[\]()~`>#+=|{}.!\\-])", r"\\\1", text)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(WELCOME_MESSAGE, parse_mode="MarkdownV2")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text or ""
    chat_id = update.effective_chat.id

    url_match = re.search(r"https?://[^\s]+", text)
    if not url_match:
        await update.message.reply_text(
            "⚠️ Bhai, ekta valid HugeIcons ba FlatIcon link de\\!\n\nExample:\n`https://hugeicons\\.com/icon/delete\\-01?style=stroke\\-sharp`",
            parse_mode="MarkdownV2",
        )
        return

    url = url_match.group(0)
    platform = detect_platform(url)

    if not platform:
        await update.message.reply_text(
            "❌ Ei link support kori na bhai\\. Shudhu HugeIcons ba FlatIcon link de\\.",
            parse_mode="MarkdownV2",
        )
        return

    status_msg = await update.message.reply_text("⏳ Fetch kortesi, ek second\\.\\.\\.", parse_mode="MarkdownV2")

    try:
        if platform == "hugeicons":
            result = fetch_hugeicons_svg(url)
        else:
            result = fetch_flaticon_svg(url)

        clean_svg = format_svg(result["svg"])
        icon_name = result.get("icon_name", "icon")
        style = result.get("style", result.get("source", "icon"))
        file_name = f"{icon_name}-{style}.svg"

        await status_msg.delete()

        label = f"✅ *{escape_md(icon_name)}* \\({escape_md(style)}\\)"
        await update.message.reply_text(label, parse_mode="MarkdownV2")

        # code block for copy
        await update.message.reply_text(
            f"```xml\n{clean_svg}\n```",
            parse_mode="MarkdownV2",
        )

        # .svg file for download
        file_bytes = BytesIO(clean_svg.encode("utf-8"))
        file_bytes.name = file_name
        await update.message.reply_document(
            document=file_bytes,
            filename=file_name,
            caption=f"📁 {file_name} — download kore direct use kor!",
        )

    except Exception as e:
        logging.error(f"Error: {e}")
        await status_msg.delete()
        await update.message.reply_text(
            "❌ Fetch korte parina bhai\\!\n\nPossible reason:\n• Link ta valid na\n• Site block kortese\n• Icon ta exist kore na\n\nArekbar try kor ba অন্য link de\\.",
            parse_mode="MarkdownV2",
        )


def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("🤖 SVG Unlock Bot running...")
    app.run_polling()


if __name__ == "__main__":
    main()
