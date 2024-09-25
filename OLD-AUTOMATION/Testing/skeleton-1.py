import csv
import time
import random
import logging
from typing import List, Tuple
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class GoogleMapScraper:
    def __init__(self, output_file_name: str = "google_map_business_data.csv", headless: bool = False):
        self.output_file_name = output_file_name
        self.headless = headless
        self.driver = None
        self.unique_check = set()

    def config_driver(self):
        options = webdriver.ChromeOptions()
        if self.headless:
            options.add_argument("--headless")
        options.add_argument("--ignore-certificate-errors")
        options.add_argument("--ignore-ssl-errors")
        s = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=s, options=options)

        
    def save_data(self, data: List[str]):
        header = ['id', 'company_name', 'rating', 'reviews_count', 'address', 'category', 'phone', 'website', 'open_hours', 'image_urls']
        with open(self.output_file_name, 'a', newline='', encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)
            if csvfile.tell() == 0:  # Write header if file is empty
                writer.writerow(header)
            writer.writerow(data)

    def parse_business_info(self, business) -> Tuple[str, str, str, str, str, str, str, str]:
        name = business.find_element(By.CLASS_NAME, 'qBF1Pd.fontHeadlineSmall').text
        rating, reviews_count = self.parse_rating_and_review_count(business)
        address, category = self.parse_address_and_category(business)
        contact = self.parse_contact(business)
        open_hours = self.parse_open_hours(business)
        try:
            website = business.find_element(By.CLASS_NAME, "lcr4fd").get_attribute("href")
        except NoSuchElementException:
            website = ""
        image_urls = self.parse_image_urls(business)
        return name, rating, reviews_count, address, category, contact, website, open_hours, image_urls

    def parse_rating_and_review_count(self, business) -> Tuple[str, str]:
        try:
            reviews_block = business.find_element(By.CLASS_NAME, 'e4rVHe.fontBodyMedium').text.split(" ")
            rating = reviews_block[0].strip()
            reviews_count = reviews_block[1].strip()
        except:
            rating = ""
            reviews_count = ""
        return rating, reviews_count

    def parse_address_and_category(self, business) -> Tuple[str, str]:
        try:
            address_block = business.find_elements(By.CLASS_NAME, "W4Efsd")[0].text.split("·")
            if len(address_block) >= 2:
                address = address_block[0].strip()
                category = address_block[1].strip()
            elif len(address_block) == 1:
                address = ""
                category = address_block[0].strip()
        except:
            address = ""
            category = ""
        return address, category

    def parse_contact(self, business) -> str:
        try:
            contact = business.find_elements(By.CLASS_NAME, "W4Efsd")[1].text.split("·")[-1].strip()
        except:
            contact = ""
        if "+1" not in contact:
            try:
                contact = business.find_elements(By.CLASS_NAME, "W4Efsd")[2].text.split("·")[-1].strip()
            except:
                contact = ""
        return contact

    def parse_open_hours(self, business) -> str:
        try:
            open_hours = business.find_element(By.CLASS_NAME, 'W4Efsd').text
        except NoSuchElementException:
            open_hours = ""
        return open_hours

    def parse_image_urls(self, business) -> List[str]:
        image_urls = []
        try:
            images = business.find_elements(By.CLASS_NAME, "xwpmRb.qisNDe")
            for image in images:
                img_tag = image.find_element(By.TAG_NAME, "img")
                image_urls.append(img_tag.get_attribute("src"))
        except NoSuchElementException:
            pass
        return image_urls

    def get_business_info(self, url: str):
        logging.info(f"Getting business info: {url}")
        self.driver.get(url)

        panel_xpath = '//*[@id="QA0Szd"]/div/div/div[1]/div[2]/div/div[1]/div/div/div[2]/div[1]'

        try:
            # Wait for the scrollable div to load
            scrollable_div = WebDriverWait(self.driver, 30).until(
                EC.presence_of_element_located((By.XPATH, panel_xpath))
            )

            # Initialize scrolling
            previous_height = 0
            current_height = self.driver.execute_script("return arguments[0].scrollHeight", scrollable_div)
            while True:
                # Scroll down
                self.driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", scrollable_div)
                time.sleep(random.uniform(2, 4))  # Add random delay to mimic human-like behavior

                # Check new height
                new_height = self.driver.execute_script("return arguments[0].scrollHeight", scrollable_div)
                if new_height == current_height:  # If height hasn't changed, we've reached the bottom
                    logging.info("Reached the end of the list.")
                    break

                current_height = new_height  # Update the height for the next iteration

                # Optional: limit the number of scrolls (e.g., to avoid infinite loops in edge cases)
                if new_height == previous_height:
                    logging.info("Reached the end of the list.")
                    break

                previous_height = current_height

                # Extract the business info as you scroll
                for business in self.driver.find_elements(By.CLASS_NAME, 'THOPZb'):
                    unique_id = "".join(self.parse_business_info(business))
                    if unique_id not in self.unique_check:
                        data = list(self.parse_business_info(business))
                        self.save_data(data)
                        self.unique_check.add(unique_id)

        except (NoSuchElementException, TimeoutException) as e:
            logging.error(f"Error: {str(e)}")
        finally:
            self.driver.quit()

if __name__ == "__main__":
    urls = [
        "https://www.google.com/maps/search/Nashville+Masonry+contractor"
    ]
    business_scraper = GoogleMapScraper()
    business_scraper.config_driver()
    for url in urls:
        business_scraper.get_business_info(url)
