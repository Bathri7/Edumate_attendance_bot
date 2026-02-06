import logging
import os
from playwright.async_api import async_playwright

# Logging configuration
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

LOGIN_URL = "https://student.sairam.edu.in/"

async def get_percentage_by_label(page, label):
    """
    Helper function to extract percentage for a given label ("Attendance", "OD", etc.)
    using playwright page locator.
    """
    try:
        # Parent container search based on previous analysis
        container = page.locator(f"div:has(> span:text-is('{label}'))").first
        if await container.count() == 0:
            container = page.locator(f"div:has(span:text-is('{label}'))").last
        
        # Now find the svg text inside this container
        pct_el = container.locator("svg text").first
        if await pct_el.count() > 0:
            return await pct_el.text_content()
        
        return "N/A"
    except Exception as e:
        logger.error(f"Error extracting {label}: {e}")
        return "N/A"

async def fetch_attendance(email, password):
    """
    Launches browser, logs in to Edumate, extracts attendance/OD, and returns a formatted string.
    """
    logger.info(f"Starting Edumate scraping for {email}...")
    
    # Determine Login URL based on email
    if "sit" in email.split("@")[0] or "sairamit.edu.in" in email:
        target_url = "https://student.sairamit.edu.in/"
    else:
        target_url = "https://student.sairam.edu.in/"
        
    async with async_playwright() as p:
        # Launch browser
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        try:
            # 1. Login
            logger.info(f"Navigating to {target_url}...")
            await page.goto(target_url)
            
            logger.info("Logging in...")
            await page.wait_for_selector('input[placeholder="Email"]')
            await page.fill('input[placeholder="Email"]', email)
            await page.fill('input[placeholder="*********"]', password)
            await page.click('button.bg-btnPrimary')
            
            # Wait for dashboard
            try:
                await page.wait_for_url("**/dashboard", timeout=15000)
            except:
                logger.error("Login failed or timed out.")
                screenshot_path = f"error_{email}.png"
                await page.screenshot(path=screenshot_path)
                return None, "Login failed. Check password or try again.", screenshot_path

            logger.info("Login successful.")

            # 2. Navigate to "Me" Section
            logger.info("Navigating to 'Me' section...")
            try:
                await page.click('a[href="/me"]')
            except:
                logger.warning("Could not click 'Me' link, trying direct navigation...")
                await page.goto("https://student.sairam.edu.in/me")
            
            await page.wait_for_url("**/me*", timeout=15000)

            # 3. Go to Attendance Tab
            logger.info("Switching to Attendance tab...")
            try:
                await page.click("text=Attendance", timeout=5000)
            except:
                logger.error("Could not find Attendance tab.")
                screenshot_path = f"error_{email}_tab.png"
                await page.screenshot(path=screenshot_path)
                return None, "Could not find Attendance tab.", screenshot_path
            
            # Wait for charts
            try:
                await page.wait_for_selector(".recharts-wrapper", timeout=15000)
            except:
                logger.warning("Charts did not load, possibly no data.")

            # 4. Extract Data
            logger.info("Extracting values...")
            
            attendance_pct = await get_percentage_by_label(page, "Attendance %")
            if attendance_pct == "N/A":
                attendance_pct = await get_percentage_by_label(page, "Attendance")
            
            od_pct = await get_percentage_by_label(page, "OD %")
            if od_pct == "N/A":
                 od_pct = await get_percentage_by_label(page, "OD")
            
            return {
                "email": email,
                "attendance": attendance_pct,
                "od": od_pct
            }, None, None

        except Exception as e:
            logger.error(f"Scraping failed: {e}")
            screenshot_path = f"error_{email}_exception.png"
            try:
                await page.screenshot(path=screenshot_path)
            except:
                screenshot_path = None
            raise e
        finally:
            await browser.close()
