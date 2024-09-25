from playwright.sync_api import sync_playwright
from dataclasses import dataclass, asdict, field
import pandas as pd
import argparse
import os
import sys

@dataclass
class Business:
    """Holds business data"""
    name: str = None
    address: str = None
    website: str = None
    phone_number: str = None
    reviews_count: int = None
    reviews_average: float = None
    latitude: float = None
    longitude: float = None
    open_hours: str = None
    description: str = None
    image_urls: list = field(default_factory=list)
    category: str = None
    additional_info: str = None

@dataclass
class BusinessList:
    """Holds a list of Business objects and saves to both Excel and CSV"""
    business_list: list[Business] = field(default_factory=list)
    save_at: str = 'output'

    def dataframe(self):
        """Transforms business_list to pandas dataframe"""
        return pd.json_normalize(
            (asdict(business) for business in self.business_list), sep="_"
        )

    def save_to_excel(self, filename):
        """Saves pandas dataframe to Excel (xlsx) file"""
        if not os.path.exists(self.save_at):
            os.makedirs(self.save_at)
        self.dataframe().to_excel(f"{self.save_at}/{filename}.xlsx", index=False)

    def save_to_csv(self, filename):
        """Saves pandas dataframe to CSV file"""
        if not os.path.exists(self.save_at):
            os.makedirs(self.save_at)
        self.dataframe().to_csv(f"{self.save_at}/{filename}.csv", index=False)

def extract_coordinates_from_url(url: str) -> tuple[float, float]:
    """Helper function to extract coordinates from URL"""
    coordinates = url.split('/@')[-1].split('/')[0]
    return float(coordinates.split(',')[0]), float(coordinates.split(',')[1])

def main():
    ########
    # Input 
    ########
    parser = argparse.ArgumentParser()
    parser.add_argument("-s", "--search", type=str)
    parser.add_argument("-t", "--total", type=int)
    args = parser.parse_args()
    
    if args.search:
        search_list = [args.search]
        
    if args.total:
        total = args.total
    else:
        total = 1_000_000

    if not args.search:
        search_list = []
        input_file_name = 'input.txt'
        input_file_path = os.path.join(os.getcwd(), input_file_name)
        if os.path.exists(input_file_path):
            with open(input_file_path, 'r') as file:
                search_list = file.readlines()
        if len(search_list) == 0:
            print('Error: You must either pass the -s search argument or add searches to input.txt')
            sys.exit()

    ###########
    # Scraping
    ###########
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        page.goto("https://www.google.com/maps", timeout=120000)
        page.wait_for_timeout(5000)

        for search_for_index, search_for in enumerate(search_list):
            print(f"-----\n{search_for_index} - {search_for}".strip())

            # Wait for the search box to be visible
            page.wait_for_selector('//input[@id="searchboxinput"]', timeout=60000)

            # Fill in the search term
            page.locator('//input[@id="searchboxinput"]').fill(search_for)

            page.keyboard.press("Enter")
            page.wait_for_timeout(5000)

            previously_counted = 0
            while True:
                page.mouse.wheel(0, 10000)
                page.wait_for_timeout(3000)

                current_count = page.locator('//a[contains(@href, "https://www.google.com/maps/place")]').count()

                if current_count >= total:
                    listings = page.locator('//a[contains(@href, "https://www.google.com/maps/place")]').all()[:total]
                    listings = [listing.locator("xpath=..") for listing in listings]
                    print(f"Total Scraped: {len(listings)}")
                    break
                else:
                    if current_count == previously_counted:
                        listings = page.locator('//a[contains(@href, "https://www.google.com/maps/place")]').all()
                        print(f"Arrived at all available\nTotal Scraped: {len(listings)}")
                        break
                    else:
                        previously_counted = current_count
                        print(f"Currently Scraped: {current_count}")

            business_list = BusinessList()

            for listing in listings:
                try:
                    listing.click()
                    page.wait_for_timeout(5000)

                    name_attribute = 'aria-label'
                    address_xpath = '//button[@data-item-id="address"]//div[contains(@class, "fontBodyMedium")]'
                    website_xpath = '//a[@data-item-id="authority"]//div[contains(@class, "fontBodyMedium")]'
                    phone_number_xpath = '//button[contains(@data-item-id, "phone:tel:")]//div[contains(@class, "fontBodyMedium")]'
                    review_count_xpath = '//button[@jsaction="pane.reviewChart.moreReviews"]//span'
                    reviews_average_xpath = '//div[@jsaction="pane.reviewChart.moreReviews"]//div[@role="img"]'

                    # Updated XPaths for additional fields
                    open_hours_xpath = '//div[@data-section-id="hours"]//span[contains(@class, "section-info-text")]'
                    description_xpath = '//div[@class="section-hero-header-description"]//span'
                    images_xpath = '//div[contains(@class, "gallery-image")]/img'

                    # Fallback CSS selectors
                    open_hours_css = 'div[data-section-id="hours"] span.section-info-text'
                    description_css = 'div.section-hero-header-description span'
                    images_css = 'div.gallery-image img'

                    # Additional fallback classes provided by user
                    category_xpath = '//div[contains(@class, "W4Efsd") or contains(@class, "Z8fK3b")]'
                    opening_times_xpath = '//div[contains(@class, "W4Efsd") and contains(text(), "Apertura") or contains(@class, "W4Efsd") and contains(text(), "Cerrado")]'
                    image_container_css = 'div.xwpmRb.qisNDe img'

                    address_css = 'div.W4Efsd'  # Fallback for address
                    additional_info_css = 'div.W6VQef, div.ah5Ghc'  # Additional details like "Comer allí" or "Para llevar"

                    business = Business()

                    # Name
                    business.name = listing.get_attribute(name_attribute) or ""

                    # Address
                    business.address = (page.locator(address_xpath).first.inner_text() 
                                        if page.locator(address_xpath).count() > 0 
                                        else page.locator(address_css).first.inner_text() 
                                        if page.locator(address_css).count() > 0 else "")

                    # Website
                    business.website = (page.locator(website_xpath).first.inner_text() 
                                        if page.locator(website_xpath).count() > 0 else "")

                    # Phone Number
                    business.phone_number = (page.locator(phone_number_xpath).first.inner_text() 
                                            if page.locator(phone_number_xpath).count() > 0 else "")

                    # Reviews Count
                    business.reviews_count = (int(page.locator(review_count_xpath).inner_text().split()[0].replace(',', '').strip()) 
                                            if page.locator(review_count_xpath).count() > 0 else 0)

                    # Reviews Average
                    business.reviews_average = (float(page.locator(reviews_average_xpath).get_attribute(name_attribute).split()[0].replace(',', '.').strip()) 
                                                if page.locator(reviews_average_xpath).count() > 0 else 0.0)

                    # Open Hours (with updated logic and fallback handling)
                    try:
                        if page.locator(open_hours_xpath).count() > 0:
                            business.open_hours = page.locator(open_hours_xpath).first.inner_text()
                        else:
                            # Fallback to additional classes or CSS selector
                            business.open_hours = (page.locator(open_hours_css).first.inner_text() 
                                                if page.locator(open_hours_css).count() > 0 
                                                else page.locator(opening_times_xpath).first.inner_text() 
                                                if page.locator(opening_times_xpath).count() > 0 else "Not Available")
                    except Exception as e:
                        print(f"Error extracting open hours: {e}")
                        business.open_hours = "Not Available"

                    # Description (with updated logic and fallback handling)
                    try:
                        if page.locator(description_xpath).count() > 0:
                            business.description = page.locator(description_xpath).first.inner_text()
                        else:
                            # Fallback to CSS selector
                            business.description = (page.locator(description_css).first.inner_text() 
                                                    if page.locator(description_css).count() > 0 else "Not Available")
                    except Exception as e:
                        print(f"Error extracting description: {e}")
                        business.description = "Not Available"

                    # Image URLs (with fallback handling and higher resolution handling)
                    try:
                        image_urls = set()
                        image_urls.update([img.get_attribute('src').replace('w80-h92', 'w400-h400') for img in page.locator(images_xpath).all()])
                        image_urls.update([img.get_attribute('src').replace('w80-h92', 'w400-h400') for img in page.locator(image_container_css).all()])
                        business.image_urls = list(image_urls)

                    except Exception as e:
                        print(f"Error extracting image URLs: {e}")
                        business.image_urls = []
                        for selector in [images_xpath, image_container_css]:
                            for img in page.locator(selector).all():
                                url = img.get_attribute('src').replace('w80-h92', 'w400-h400')
                                if url not in business.image_urls:
                                    business.image_urls.append(url)


                    # Category (Additional fallback)
                    business.category = (page.locator(category_xpath).first.inner_text() 
                                        if page.locator(category_xpath).count() > 0 else "")

                    # Additional Info (Service types, etc.)
                    business.additional_info = (page.locator(additional_info_css).first.inner_text() 
                                                if page.locator(additional_info_css).count() > 0 else "")

                    # Coordinates
                    business.latitude, business.longitude = extract_coordinates_from_url(page.url)

                    business_list.business_list.append(business)

                except Exception as e:
                    print(f'Error: {e}')

            # Output
            business_list.save_to_excel(f"google_maps_data_{search_for.strip()}".replace(' ', '_'))
            business_list.save_to_csv(f"google_maps_data_{search_for.strip()}".replace(' ', '_'))

        browser.close()
if __name__ == "__main__":
    main()
