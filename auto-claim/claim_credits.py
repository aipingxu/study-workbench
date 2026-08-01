#!/usr/bin/env python3
"""
WorkBuddy 每日积分自动领取脚本
=============================
通过 Playwright 持久化浏览器上下文，自动调用 codebuddy.cn 的领取礼包 API。

使用方法：
1. 首次运行（登录）：python claim_credits.py --login
   会打开浏览器，手动登录 codebuddy.cn，登录后关闭浏览器即可
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

# API 路径
CHECK_API = "/billing/meter/check-gift-claimed"
CLAIM_API = "/billing/meter/claim-gift"

# 日志文件
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "claim_credits.log")

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
        page = context.new_page()

        # 打开 codebuddy.cn
        logger.info(f"正在访问 {BASE_URL} ...")
        try:
            page.goto(BASE_URL, wait_until="domcontentloaded", timeout=20000)
        except Exception as e:
            logger.warning(f"页面加载超时（可继续）: {e}")

        page.wait_for_timeout(3000)

        # GUI 模式：等待用户手动登录
        if headed:
            logger.info("=" * 50)
            logger.info("请在打开的浏览器窗口中登录 codebuddy.cn")
            logger.info("登录成功后，请回到这里按回车键继续...")
            logger.info("=" * 50)
            input()
            page.goto(BASE_URL, wait_until="domcontentloaded", timeout=20000)
            page.wait_for_timeout(3000)

        # 检查今日礼包状态
        logger.info("正在检查今日礼包状态...")
        check_result = page.evaluate("""
            async () => {
                try {
                    const resp = await fetch('%s', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
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

        logger.info(f"检查结果: {json.dumps(check_result, ensure_ascii=False, indent=2)}")

        # 处理检查结果
        status = check_result.get("status")
        data = check_result.get("data", {})

        if status == 401:
            logger.error("❌ 未登录或登录已过期！")
            logger.error("请运行: python claim_credits.py --login 重新登录")
            context.close()
            return False

        if status != 200:
            logger.error(f"❌ API 返回异常状态: {status}")
            logger.error(f"响应: {data}")
            context.close()
            return False

        # 检查是否已领取
        # 根据返回数据判断是否已领取
        claimed = False
        if isinstance(data, dict):
            # 尝试多种可能的字段名
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
            context.close()
            return True

        # 领取积分
        logger.info("🎁 正在领取今日积分...")
        claim_result = page.evaluate("""
            async () => {
                try {
                    const resp = await fetch('%s', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
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

        logger.info(f"领取结果: {json.dumps(claim_result, ensure_ascii=False, indent=2)}")

        claim_status = claim_result.get("status")
        claim_data = claim_result.get("data", {})

        if claim_status == 200:
            # 检查领取是否成功
            success = False
            if isinstance(claim_data, dict):
                success = (
                    claim_data.get("success", True)
                    and claim_data.get("code") != "already_claimed"
                    and claim_data.get("error") is None
                )
                # 如果有 error 字段，说明领取失败
                if claim_data.get("error"):
                    success = False
                    logger.error(f"❌ 领取失败: {claim_data.get('error')}")
                elif claim_data.get("code") == "already_claimed":
                    logger.info("✅ 今日积分已领取（重复领取提示）")
                    success = True
                else:
                    logger.info("✅ 今日积分领取成功！+100 积分")
                    success = True
            else:
                logger.info("✅ 今日积分领取成功！")
                success = True

            context.close()
            return success
        elif claim_status == 401:
            logger.error("❌ 未登录或登录已过期！")
            logger.error("请运行: python claim_credits.py --login 重新登录")
            context.close()
            return False
        else:
            logger.error(f"❌ 领取失败，状态码: {claim_status}")
            logger.error(f"响应: {claim_data}")
            context.close()
            return False


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
