#!/usr/bin/env python3
"""
WorkBuddy 每日积分自动领取脚本
=============================
通过 Playwright 持久化浏览器上下文，自动调用 codebuddy.cn 的领取礼包 API。

使用方法：
1. 首次运行（登录）：python claim_credits.py --login
   会打开浏览器，自动跳转登录页，登录成功后自动继续
2. 日常自动运行：python claim_credits.py
   headless 模式，自动检查并领取每日积分
3. 配合 Windows 任务计划程序，每天定时自动执行

API 说明：
- POST /billing/meter/check-gift-claimed  检查今日礼包是否已领取
- POST /billing/meter/claim-gift          领取今日礼包（100积分）
"""

import sys
import os
import json
import time
import logging
from datetime import datetime
from pathlib import Path

# ============================================================
# 配置区
# ============================================================
# 浏览器数据目录（保存登录状态）
BROWSER_DATA_DIR = os.path.expanduser(r"~\.workbuddy\browser-data")

# codebuddy.cn 地址
BASE_URL = "https://www.codebuddy.cn"

# 需要登录才能访问的页面（用于检测登录状态）
PROFILE_URL = "https://www.codebuddy.cn/profile"

# API 路径
CHECK_API = "/billing/meter/check-gift-claimed"
CLAIM_API = "/billing/meter/claim-gift"

# 日志文件
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "claim_credits.log")

# 登录等待超时（秒）
LOGIN_TIMEOUT = 300  # 5分钟

# ============================================================
# 日志配置
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


def check_gift_status(page):
    """检查今日礼包状态，返回 (status_code, data)"""
    result = page.evaluate("""
        async () => {
            try {
                const resp = await fetch('%s', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: '{}',
                    credentials: 'include',
                });
                const text = await resp.text();
                let data;
                try { data = JSON.parse(text); } catch(e) { data = text; }
                return { status: resp.status, data: data };
            } catch(e) {
                return { error: e.toString() };
            }
        }
    """ % CHECK_API)
    return result.get("status"), result.get("data", {}), result.get("error")


def claim_gift(page):
    """领取今日礼包，返回 (status_code, data)"""
    result = page.evaluate("""
        async () => {
            try {
                const resp = await fetch('%s', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: '{}',
                    credentials: 'include',
                });
                const text = await resp.text();
                let data;
                try { data = JSON.parse(text); } catch(e) { data = text; }
                return { status: resp.status, data: data };
            } catch(e) {
                return { error: e.toString() };
            }
        }
    """ % CLAIM_API)
    return result.get("status"), result.get("data", {}), result.get("error")


def wait_for_login(page, timeout=LOGIN_TIMEOUT):
    """
    自动等待用户登录成功。
    每3秒检查一次API状态，返回200表示已登录。
    """
    logger.info("=" * 50)
    logger.info("等待登录中...")
    logger.info("请在弹出的浏览器窗口中登录 codebuddy.cn")
    logger.info(f"超时时间: {timeout}秒 ({timeout//60}分钟)")
    logger.info("登录成功后会自动继续，无需手动操作")
    logger.info("=" * 50)

    start = time.time()
    check_count = 0

    while time.time() - start < timeout:
        check_count += 1
        elapsed = int(time.time() - start)

        try:
            # 先访问 profile 页面，触发登录状态检查
            page.goto(PROFILE_URL, wait_until="domcontentloaded", timeout=10000)
            page.wait_for_timeout(1000)

            # 检查API状态
            status, data, error = check_gift_status(page)

            if status == 200:
                logger.info(f"✅ 登录成功！(耗时 {elapsed}秒，检查 {check_count} 次)")
                return True
            elif status == 401:
                # 还没登录，继续等待
                if check_count == 1:
                    logger.info(f"尚未登录，等待中... (已等 {elapsed}s)")
                elif check_count % 10 == 0:
                    logger.info(f"仍在等待登录... (已等 {elapsed}s，检查 {check_count} 次)")
            else:
                logger.info(f"API 状态: {status}，继续等待... (已等 {elapsed}s)")
        except Exception as e:
            logger.debug(f"检查登录时异常（可继续）: {e}")

        # 等待3秒再检查
        time.sleep(3)

    logger.error(f"❌ 登录超时（{timeout}秒），请重新运行 --login")
    return False


def do_claim(page):
    """执行领取流程"""
    # 检查今日礼包状态
    logger.info("正在检查今日礼包状态...")
    status, data, error = check_gift_status(page)

    if error:
        logger.error(f"❌ API 调用失败: {error}")
        return False

    logger.info(f"检查结果: status={status}")

    if status == 401:
        logger.error("❌ 未登录或登录已过期！")
        logger.error("请运行: python claim_credits.py --login 重新登录")
        return False

    if status != 200:
        logger.error(f"❌ API 返回异常状态: {status}")
        logger.error(f"响应: {data}")
        return False

    # 检查是否已领取
    claimed = False
    if isinstance(data, dict):
        claimed = (
            data.get("claimed")
            or data.get("is_claimed")
            or data.get("hasClaimed")
            or data.get("data", {}).get("claimed")
            or data.get("data", {}).get("is_claimed")
            or data.get("code") == "already_claimed"
            or False
        )

    if claimed:
        logger.info("✅ 今日积分已领取，无需重复领取")
        return True

    # 领取积分
    logger.info("🎁 正在领取今日积分...")
    status, data, error = claim_gift(page)

    if error:
        logger.error(f"❌ API 调用失败: {error}")
        return False

    logger.info(f"领取结果: status={status}")

    if status == 200:
        if isinstance(data, dict):
            if data.get("error"):
                logger.error(f"❌ 领取失败: {data.get('error')}")
                return False
            elif data.get("code") == "already_claimed":
                logger.info("✅ 今日积分已领取（重复领取提示）")
                return True
            else:
                logger.info("✅ 今日积分领取成功！+100 积分")
                return True
        else:
            logger.info("✅ 今日积分领取成功！")
            return True
    elif status == 401:
        logger.error("❌ 未登录或登录已过期！")
        logger.error("请运行: python claim_credits.py --login 重新登录")
        return False
    else:
        logger.error(f"❌ 领取失败，状态码: {status}")
        logger.error(f"响应: {data}")
        return False


def run_claim(headed=False):
    """运行积分领取流程"""
    from playwright.sync_api import sync_playwright

    logger.info("=" * 50)
    logger.info("WorkBuddy 每日积分自动领取")
    logger.info(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"模式: {'GUI（手动登录）' if headed else 'Headless（自动）'}")
    logger.info("=" * 50)

    # 确保浏览器数据目录存在
    os.makedirs(BROWSER_DATA_DIR, exist_ok=True)

    with sync_playwright() as p:
        # 使用持久化上下文（保存登录状态）
        context = p.chromium.launch_persistent_context(
            BROWSER_DATA_DIR,
            headless=not headed,
            viewport={"width": 1280, "height": 720},
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = context.pages[0] if context.pages else context.new_page()

        # 打开 codebuddy.cn
        logger.info(f"正在访问 {BASE_URL} ...")
        try:
            page.goto(BASE_URL, wait_until="domcontentloaded", timeout=20000)
        except Exception as e:
            logger.warning(f"页面加载超时（可继续）: {e}")
        page.wait_for_timeout(2000)

        if headed:
            # ============================================================
            # GUI 模式：自动等待用户登录
            # ============================================================
            # 先检查是否已经登录（可能之前登录过，cookie还在）
            logger.info("检查当前登录状态...")
            status, _, _ = check_gift_status(page)

            if status == 200:
                logger.info("✅ 已处于登录状态，无需重新登录")
            else:
                logger.info(f"当前未登录（status={status}），开始等待登录...")
                # 尝试导航到 profile 页面，触发登录跳转
                try:
                    page.goto(PROFILE_URL, wait_until="domcontentloaded", timeout=15000)
                except Exception:
                    pass

                # 自动等待登录
                if not wait_for_login(page):
                    logger.error("登录失败，退出")
                    context.close()
                    return False

            # 登录成功后，执行领取
            logger.info("")
            success = do_claim(page)
            context.close()
            return success
        else:
            # ============================================================
            # Headless 模式：直接尝试领取
            # ============================================================
            success = do_claim(page)
            context.close()
            return success


def main():
    """主函数"""
    headed = "--login" in sys.argv or "--headed" in sys.argv

    try:
        success = run_claim(headed=headed)
        if success:
            logger.info("任务完成 ✅")
            sys.exit(0)
        else:
            logger.error("任务失败 ❌")
            sys.exit(1)
    except KeyboardInterrupt:
        logger.info("用户中断")
        sys.exit(0)
    except Exception as e:
        logger.exception(f"发生异常: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
