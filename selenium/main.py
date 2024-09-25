import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select
import traceback
import re
from datetime import datetime 
from selenium.common.exceptions import TimeoutException, ElementClickInterceptedException, StaleElementReferenceException
import urllib.request
from twocaptcha import TwoCaptcha
import sys
import ssl


class FormFiller:
    def __init__(self):
        print("Initializing FormFiller...")
        try:
            options = uc.ChromeOptions()
            options.add_argument("--start-maximized")
            options.add_argument("--disable-extensions")
            options.add_argument("--disable-gpu")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--remote-debugging-port=9222")

            print("Creating Chrome driver...")
            self.driver = uc.Chrome(options=options)
            print("Chrome driver created successfully.")
            self.wait = WebDriverWait(self.driver, 60)   
        except Exception as e:
            print(f"Error initializing FormFiller: {str(e)}")
            print("Traceback:")
            traceback.print_exc()
            raise


    def wait_and_click(self, locator):
        try:
            print(f"Waiting for element: {locator}")
            time.sleep(5)  # Add a 5-second delay
            element = self.wait.until(EC.presence_of_element_located(locator))
            print(f"Element found: {element}")
            
            # Scroll the element into view
            self.driver.execute_script("arguments[0].scrollIntoView(true);", element)
            
            element = self.wait.until(EC.element_to_be_clickable(locator))
            print(f"Element clickable: {element}")
            self.driver.execute_script("arguments[0].click();", element)
            print(f"Clicked element: {locator}")
        except Exception as e:
            print(f"Error in wait_and_click: {str(e)}")
            print("Current URL:", self.driver.current_url)
            print("Page source:")
            print(self.driver.page_source)
            self.take_screenshot("wait_and_click_error")
            raise

    def wait_and_send_keys(self, locator, keys):
        element = self.wait.until(EC.presence_of_element_located(locator))
        element.clear()
        element.send_keys(keys)

    def validate_date(self, date_string):
        try:
            datetime.strptime(date_string, "%m/%d/%Y")
            return True
        except ValueError:
            return False

    def validate_fincen_id(self, fincen_id):
        return bool(re.match(r'^[A-Z]\d{8}$', fincen_id))

    def start_form(self):
        print("Starting form...")
        try:
            self.driver.get('https://boiefiling.fincen.gov/boir/html')
            print(f"Current URL: {self.driver.current_url}")
            
            # Wait for the page to load completely
            self.wait.until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
            
            print(f"Page source length: {len(self.driver.page_source)}")

            time.sleep(5)  # Increase delay to 10 seconds

            try:
                agree_button = self.wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'I Agree')]")))
                agree_button.click()
                print("Clicked 'I Agree' button")
            except Exception as e:
                print(f"'I Agree' popup did not appear or could not be clicked: {str(e)}")

            # Wait for the Filing Information page to load
            try:
                self.wait.until(EC.presence_of_element_located((By.ID, 'fi.filingType.value1')))
                print("Filing Information page loaded successfully.")
            except Exception as e:
                print(f"Error waiting for Filing Information page: {str(e)}")
                print("Current page source:")
                print(self.driver.page_source)
                self.take_screenshot("filing_information_page_error")
                raise

        except Exception as e:
            print(f"Error in start_form: {str(e)}")
            self.take_screenshot("start_form_error")
            raise

    def select_identification_type(self, i, identification_type):
        try:
            # Scroll the element into view
            element = self.driver.find_element(By.ID, f"ca[{i}].identification.type.value")
            self.driver.execute_script("arguments[0].scrollIntoView(true);", element)
            # Click the input field to open the dropdown
            self.safe_click_element((By.ID, f"ca[{i}].identification.type.value"))

            # Try to select the identification type option
            if self.safe_click_element((By.CSS_SELECTOR, f'[data-testid="combo-box-option-{identification_type}"]')):
                print(f"Selected identification type: {identification_type}")
                return

            # Fallback: Try to select the identification type by sending keys to the input
            input_element = self.safe_find_element((By.ID, f"ca[{i}].identification.type.value"))
            if input_element:
                input_element.clear()
                input_element.send_keys(identification_type)
                input_element.send_keys(Keys.RETURN)
                print(f"Entered identification type: {identification_type}")
                return

            print(f"Failed to select identification type: {identification_type}")
        except Exception as e:
            print(f"Error in select_identification_type: {str(e)}")


    def select_address_type(self, index, address_type):
        """
        Selects the address type based on the provided value.
        :param index: The index of the address type (e.g., 1 or 2).
        :param address_type: The address type to select ('BUSINESS' or 'RESIDENTIAL').
        """
        radio_button_id = f"ca[{index}].addressType.value{1 if address_type == 'BUSINESS' else 2}"

        # Fallback locators: by ID, by XPATH, by CSS Selector
        locators = [
            (By.ID, radio_button_id),
            (By.XPATH, f"//input[@id='{radio_button_id}']"),
            (By.XPATH, f"//label[@for='{radio_button_id}']"),
            (By.CSS_SELECTOR, f"input#ca\\[{index}\\]\\.addressType\\.value{1 if address_type == 'BUSINESS' else 2}"),
            (By.CSS_SELECTOR, f"label[for='ca\\[{index}\\]\\.addressType\\.value{1 if address_type == 'BUSINESS' else 2}']")
        ]
        
        # Loop through each locator until the element is found and clickable
        for locator in locators:
            if self.wait_for_element_to_be_ready(locator):
                try:
                    # Attempt to click the element
                    self.wait_and_click(locator)
                    print(f"Selected {address_type} address type.")
                    return  # Exit if successful
                except Exception as e:
                    print(f"Failed to select {address_type} address type using locator {locator}: {e}")
        
        # If all locators fail
        print(f"Failed to select {address_type} address type after multiple attempts.")



    def click_checkbox(self, checkbox_id):
        """
        Clicks the checkbox using its ID. If direct click fails, use the associated label as a fallback.
        :param checkbox_id: The ID of the checkbox to click.
        """
        checkbox_locator = (By.ID, checkbox_id)
        label_locator = (By.XPATH, f"//label[@for='{checkbox_id}']")

        # Try clicking the checkbox directly
        if self.wait_for_element_to_be_ready(checkbox_locator):
            if not self.safe_click_element(checkbox_locator):
                print("Falling back to JavaScript click...")
                self.safe_click_element_js(checkbox_locator)
        else:
            print("Element is not ready to be clicked.")
            
            # Try clicking the associated label as a fallback
            if self.wait_for_element_to_be_ready(label_locator):
                if not self.safe_click_element(label_locator):
                    print("Falling back to JavaScript click on label...")
                    self.safe_click_element_js(label_locator)
            else:
                print("Label is not ready to be clicked.")

    def safe_select_dropdown(self, dropdown_id, option_text):
        try:
            # Click the dropdown to open it
            self.safe_click_element((By.ID, dropdown_id))
            time.sleep(1)  # Wait for dropdown to open

            # Try to select the option
            option_locators = [
                (By.XPATH, f"//li[@data-testid='combo-box-option-{option_text}']"),
                (By.XPATH, f"//li[contains(@class, 'usa-combo-box__list-option') and contains(text(), '{option_text}')]"),
                (By.CSS_SELECTOR, f"li[data-value='{option_text}']")
            ]

            for locator in option_locators:
                if self.safe_click_element(locator):
                    print(f"Selected '{option_text}' from dropdown")
                    return True

            # If clicking fails, try sending keys to the input
            input_element = self.safe_find_element((By.ID, dropdown_id))
            if input_element:
                input_element.clear()
                input_element.send_keys(option_text)
                input_element.send_keys(Keys.RETURN)
                print(f"Entered '{option_text}' into dropdown input")
                return True

            print(f"Failed to select '{option_text}' from dropdown")
            return False
        except Exception as e:
            print(f"Error in safe_select_dropdown: {str(e)}")
            return False

    def click_checkbox(self, locator):
        try:
            checkbox = self.safe_find_element(locator)
            if checkbox:
                self.driver.execute_script("arguments[0].click();", checkbox)
                print(f"Clicked checkbox using JavaScript: {locator}")
                return True
        except Exception as e:
            print(f"Failed to click checkbox: {locator}")
        return False

    def safe_click_element(self, locator):
        try:
            element = WebDriverWait(self.driver, 10).until(EC.element_to_be_clickable(locator))
            self.scroll_to_element(element)
            element.click()
            print(f"Clicked element: {locator}")
            return True
        except Exception as e:
            print(f"Failed to click element: {locator}")
            try:
                element = self.driver.find_element(*locator)
                self.driver.execute_script("arguments[0].click();", element)
                print(f"Clicked element using JavaScript: {locator}")
                return True
            except Exception as e:
                print(f"Failed to click element using JavaScript: {locator}")
                return False

    def safe_find_element(self, locator):
        try:
            return WebDriverWait(self.driver, 10).until(EC.presence_of_element_located(locator))
        except Exception as e:
            print(f"Element not found: {locator}")
            return None

    def scroll_to_element(self, element):
        self.driver.execute_script("arguments[0].scrollIntoView(true);", element)
        time.sleep(1)  # Give the page a moment to settle after scrolling

    def safe_send_keys(self, locator, keys):
        try:
            element = WebDriverWait(self.driver, 10).until(EC.presence_of_element_located(locator))
            self.scroll_to_element(element)
            element.clear()
            element.send_keys(keys)
            print(f"Sent keys to element: {locator}")
        except Exception as e:
            print(f"Failed to send keys to element: {locator}")
            raise 

    def select_state(self, state_code):
        try:
            # Scroll the element into view
            element = self.driver.find_element(By.ID, 'rc.state.value')
            self.driver.execute_script("arguments[0].scrollIntoView(true);", element)

            # Click the input field to open the dropdown
            self.safe_click_element((By.ID, 'rc.state.value'))

            # Try to select the state option using data-testid
            option_locator = (By.CSS_SELECTOR, f"[data-testid='combo-box-option-{state_code}']")
            if self.safe_click_element(option_locator):
                print(f"Selected state: {state_code}")
                return

            # Fallback: Try to select the state using the id
            option_id = f"rc.state.value--list--option-{self.get_option_index(state_code)}"
            option_locator = (By.ID, option_id)
            if self.safe_click_element(option_locator):
                print(f"Selected state: {state_code}")
                return

            # Fallback: Try to select the state by sending keys to the input
            input_element = self.safe_find_element((By.ID, 'rc.state.value'))
            if input_element:
                input_element.clear()
                input_element.send_keys(state_code)
                input_element.send_keys(Keys.RETURN)
                print(f"Entered state: {state_code}")
                return

            print(f"Failed to select state: {state_code}")
        except Exception as e:
            print(f"Error in select_state: {str(e)}")

    def get_option_index(self, state_code):
        # This function returns the index of the state option based on the state code
        state_options = {
            'AL': 0, 'AK': 1, 'AE': 2, 'AA': 3, 'AP': 4, 'AZ': 5, 'AR': 6, 'CA': 7, 'CO': 8, 'CT': 9,
            'DE': 10, 'DC': 11, 'FL': 12, 'GA': 13, 'HI': 14, 'ID': 15, 'IL': 16, 'IN': 17, 'IA': 18,
            'KS': 19, 'KY': 20, 'LA': 21, 'ME': 22, 'MD': 23, 'MA': 24, 'MI': 25, 'MN': 26, 'MS': 27,
            'MO': 28, 'MT': 29, 'NE': 30, 'NV': 31, 'NH': 32, 'NJ': 33, 'NM': 34, 'NY': 35, 'NC': 36,
            'ND': 37, 'OH': 38, 'OK': 39, 'OR': 40, 'PA': 41, 'RI': 42, 'SC': 43, 'SD': 44, 'TN': 45,
            'TX': 46, 'UT': 47, 'VT': 48, 'VA': 49, 'WA': 50, 'WV': 51, 'WI': 52, 'WY': 53
        }
        return state_options.get(state_code, -1)

    def select_jurisdiction(self, index, jurisdiction):
        """
        Selects the jurisdiction from the custom combo box.
        :param index: The index of the combo box (e.g., 0, 1, 2).
        :param jurisdiction: The jurisdiction to select (e.g., 'United States of America').
        """
        print(f"Attempting to select jurisdiction: {jurisdiction}")

        # Locators
        input_locator = (By.ID, f"ca[{index}].identification.jurisdiction.value")
        toggle_button_locator = (By.CSS_SELECTOR, f"[data-testid='combo-box-toggle']")
        option_locator = (By.XPATH, f"//li[@data-testid='combo-box-option-US']")

        try:
            # Click the input field to focus it
            self.wait_and_click(input_locator)
            print("Clicked the jurisdiction input field")

            # Click the toggle button to open the dropdown
            self.wait_and_click(toggle_button_locator)
            print("Clicked the dropdown toggle button")

            # Wait for the dropdown to open
            time.sleep(1)

            # Click the desired option
            self.wait_and_click(option_locator)
            print(f"Selected jurisdiction: {jurisdiction}")

            # Verify the selection
            input_element = self.wait.until(EC.presence_of_element_located(input_locator))
            selected_value = input_element.get_attribute('value')
            if selected_value == jurisdiction:
                print(f"Successfully selected jurisdiction: {jurisdiction}")
            else:
                print(f"Jurisdiction selection verification failed. Expected {jurisdiction}, got {selected_value}")

        except Exception as e:
            print(f"Failed to select jurisdiction {jurisdiction}: {str(e)}")

            # Fallback method: Try to set the value directly using JavaScript
            try:
                js_code = f"""
                var input = document.getElementById('ca[{index}].identification.jurisdiction.value');
                input.value = '{jurisdiction}';
                var event = new Event('change', {{ bubbles: true }});
                input.dispatchEvent(event);
                """
                self.driver.execute_script(js_code)
                print(f"Used JavaScript to set jurisdiction to {jurisdiction}")
            except Exception as js_e:
                print(f"JavaScript fallback also failed: {str(js_e)}")
 
    def select_identification_state(self, index, state):
        """
        Selects the state for identification from the custom combo box.
        :param index: The index of the combo box (e.g., 0, 1, 2).
        :param state: The state to select (e.g., 'California').
        """
        print(f"Attempting to select identification state: {state}")

        # Locators
        input_locator = (By.ID, f"ca[{index}].identification.state.value")
        toggle_button_locator = (By.CSS_SELECTOR, f"[data-testid='combo-box-toggle']")
        option_locator = (By.XPATH, f"//li[@data-testid='combo-box-option-CA']")

        try:
            # Click the input field to focus it
            self.wait_and_click(input_locator)
            print("Clicked the identification state input field")

            # Click the toggle button to open the dropdown
            self.wait_and_click(toggle_button_locator)
            print("Clicked the dropdown toggle button")

            # Wait for the dropdown to open
            time.sleep(1)

            # Click the desired option
            self.wait_and_click(option_locator)
            print(f"Selected identification state: {state}")

            # Verify the selection
            input_element = self.wait.until(EC.presence_of_element_located(input_locator))
            selected_value = input_element.get_attribute('value')
            if selected_value == state:
                print(f"Successfully selected identification state: {state}")
            else:
                print(f"Identification state selection verification failed. Expected {state}, got {selected_value}")

        except Exception as e:
            print(f"Failed to select identification state {state}: {str(e)}")

            # Fallback method: Try to set the value directly using JavaScript
            try:
                js_code = f"""
                var input = document.getElementById('ca[{index}].identification.state.value');
                input.value = '{state}';
                var event = new Event('change', {{ bubbles: true }});
                input.dispatchEvent(event);
                """
                self.driver.execute_script(js_code)
                print(f"Used JavaScript to set identification state to {state}")
            except Exception as js_e:
                print(f"JavaScript fallback also failed: {str(js_e)}")

    # Use JavaScript to set the value and trigger 'change' event
    def select_dropdown_option(self, dropdown_element, value_element):
        # Set the value using JavaScript and trigger the 'change' event manually
        self.driver.execute_script("""
            arguments[0].click();  // Open the dropdown
            arguments[1].click();  // Select the value
            const event = new Event('change', { bubbles: true });
            arguments[0].dispatchEvent(event);  // Trigger change event
        """, dropdown_element, value_element)

    def select_and_trigger_change(self, element, option_element):
        # Select the element with JavaScript and trigger the 'change' event manually
        self.driver.execute_script("""
            arguments[0].click(); // Click on the dropdown
            arguments[1].click(); // Select the option
            var event = new Event('change', { bubbles: true });
            arguments[0].dispatchEvent(event); // Trigger change event
        """, element, option_element)

    def safe_click_element_js(self, locator):
        try:
            element = self.driver.find_element(*locator)
            # Scroll element into view
            self.driver.execute_script("arguments[0].scrollIntoView(true);", element)
            # Click the element using JavaScript
            self.driver.execute_script("arguments[0].click();", element)
            # Optionally trigger a change event (depends on the form's behavior)
            self.driver.execute_script("""
                var event = new Event('change', { bubbles: true });
                arguments[0].dispatchEvent(event);
            """, element)
            return True
        except Exception as e:
            print(f"Error clicking element with JS: {str(e)}")
            return False

    def wait_for_element_to_be_ready(self, locator):
        try:
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located(locator)
            )
            WebDriverWait(self.driver, 10).until(
                EC.visibility_of_element_located(locator)
            )
            return True
        except Exception as e:
            print(f"Element not ready {locator}: {e}")
            return False




    def fill_form(self):
        print("Filling form...")
        try:
            self.fill_filing_information()
            self.fill_reporting_company_info()
            self.fill_company_applicants(1)  # Adjust number as needed
            self.fill_beneficial_owners(1)  # Adjust number as needed
            self.fill_submission_info()
        except Exception as e:
            print(f"Error in fill_form: {str(e)}")
            raise

    def fill_filing_information(self):
        print("Filling Filing Information...")
        try:
            # Wait for the page to load completely
            self.wait.until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
            
            # Check if we're on the correct page
            if 'Filing Information' not in self.driver.page_source:
                print("Not on Filing Information page. Current page source:")
                print(self.driver.page_source)
                raise Exception("Not on Filing Information page")

            # Try to find the element by different locators
            locators = [
                #(By.ID, 'fi.filingType.value1'),
                #(By.NAME, 'fi.filingType.value1'),
                #(By.XPATH, "//input[@value='Initial report']"),
                (By.XPATH, "//label[contains(text(), 'Initial report')]")
            ]

            for locator in locators:
                try:
                    self.wait_and_click(locator)
                    print(f"Successfully clicked using locator: {locator}")
                    break
                except Exception as e:
                    print(f"Failed to click using locator {locator}: {str(e)}")
            else:
                raise Exception("Failed to click 'Initial report' using all locators")

            # Click Next button
            self.safe_click_element((By.CSS_SELECTOR, '[data-testid="bottom-next-button"]'))
            print("Clicked 'Next' button")

            # Add a delay to allow the next page to load
            time.sleep(5)  # Wait for 5 seconds

            # Wait for the Reporting Company page to load
            self.wait.until(EC.presence_of_element_located((By.ID, 'rc.isRequestingId')))
            print("Reporting Company page loaded successfully.")

        except Exception as e:
            print(f"Error in fill_filing_information: {str(e)}")
            print("Current URL:", self.driver.current_url)
            print("Page source:")
            print(self.driver.page_source)
            self.take_screenshot("fill_filing_information_error")
            raise

    def fill_reporting_company_info(self):
        print("Filling reporting company info...")
        try:
            # Wait for the page to load completely
            self.wait.until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
            
            # Check if we're on the correct page
            if 'Reporting Company Information' not in self.driver.page_source:
                print("Not on Reporting Company Information page. Current page source:")
                print(self.driver.page_source)
                raise Exception("Not on Reporting Company Information page")

            # Print all input elements on the page
            inputs = self.driver.find_elements(By.TAG_NAME, 'input')
            print(f"Found {len(inputs)} input elements on the page:")
            for input_elem in inputs:
                print(f"Input ID: {input_elem.get_attribute('id')}, Type: {input_elem.get_attribute('type')}")

            # 3. Request to receive FinCEN ID
            self.safe_click_element((By.ID, 'rc.isRequestingId'))

            # 5. Reporting Company legal name
            self.safe_send_keys((By.ID, 'rc.legalName'), 'Test Company Name')

            # 6. Alternate name (optional)
            alternate_name_field = self.safe_find_element((By.ID, 'rc.alternateNames0.value'))
            if alternate_name_field:
                self.safe_send_keys((By.ID, 'rc.alternateNames0.value'), 'Test Alternate Name')
            else:
                print("Alternate name field not found, skipping...")

            # 7. Tax Identification type
            self.wait_and_click((By.ID, 'rc.taxType'))
            self.wait_and_click((By.CSS_SELECTOR, '[data-testid="combo-box-option-2"]'))  # Assuming EIN is option 2
            print("Selected Tax Identification type")

            # 8. Tax Identification number
            self.wait_and_send_keys((By.ID, 'rc.taxId'), '993817308')
            print("Filled Tax Identification number")

            # 9. Country/Jurisdiction (if foreign tax ID only) - skip for now

            # 10 a. Country/Jurisdiction of formation
            self.safe_click_element((By.ID, 'rc.jurisdiction'))
            print("Clicked jurisdiction dropdown")
            # Wait for the dropdown to open
            time.sleep(2)     
            # Try to select Country using different methods
            jurisdiction_option_locators = [
                #(By.CSS_SELECTOR, '[data-testid="combo-box-option-US"]'),
                #(By.XPATH, "//li[contains(text(), 'United States of America')]"),
                (By.XPATH, "//*[@id='rc.jurisdiction--list--option-0']")
            ]
            for locator in jurisdiction_option_locators:
                try:
                    self.safe_click_element(locator)
                    print(f"Selected US using locator: {locator}")
                    break
                except Exception as e:
                    print(f"Failed to select US using locator: {locator}")
            else:
                print("Failed to select US using all available methods")

            # 10 b. STATE
            self.safe_click_element((By.ID, 'rc.domesticState'))
            print("Clicked STATE dropdown")
            # Wait for the dropdown to open
            time.sleep(2)     
            # Try to select Country using different methods
            state_option_locators = [
                #(By.CSS_SELECTOR, '[data-testid="combo-box-option-US"]'),
                #(By.XPATH, "//li[contains(text(), 'United States of America')]"),
                (By.XPATH, "//*[@id='rc.domesticState--list--option-7']")
            ]
            for locator in state_option_locators:
                try:
                    self.safe_click_element(locator)
                    print(f"Selected STATE using locator: {locator}")
                    break
                except Exception as e:
                    print(f"Failed to select STATE using locator: {locator}")
            else:
                print("Failed to select STATE using all available methods")


            # 11. Address
            self.wait_and_send_keys((By.ID, 'rc.address.value'), '123 Test Street')
            print("Filled Address")

            # 12. City
            self.wait_and_send_keys((By.ID, 'rc.city.value'), 'Test City')
            print("Filled City")

            # 13. U.S. or U.S. Territory 
            self.safe_click_element((By.ID, 'rc.country.value'))  # Corrected here
            print("Clicked United States of America Territory dropdown - 1")
            time.sleep(2)   
            # Try to select US using different methods
            country_option_locators = [
               # (By.CSS_SELECTOR, '[data-testid="combo-box-option-US"]'),
               # (By.XPATH, "//li[contains(text(), 'United States of America')]"),
                (By.XPATH, "//*[@id='rc.country.value--list--option-0']")
            ]
            for locator in country_option_locators:
                try:
                    self.safe_click_element(locator)
                    print(f"Selected US using locator # 13.: {locator}")
                    break
                except Exception as e:
                    print(f"Failed to select Country using locator: {locator}")
            else:
                print("Failed to select Country using all available methods # 13.")

            # 14. State            
            self.safe_click_element((By.ID, 'rc.state.value'))  # Corrected here
            print("Clicked STATE from U.S. or U.S. Territory dropdown - 1")
            # Wait for the dropdown to open
            time.sleep(2)  
            # Try to select US using different methods
            state_option_locators = [
                #(By.CSS_SELECTOR, '[data-testid="combo-box-option-CA"]'),
                #(By.XPATH, "//li[contains(text(), 'California')]"),
                (By.XPATH, "//*[@id='rc.state.value--list--option-7']")
            ]
            for locator in state_option_locators:
                try:
                    self.safe_click_element(locator)
                    print(f"Selected US using locator # 14.: {locator}")
                    break
                except Exception as e:
                    print(f"Failed to select STATE  using locator: {locator}")
            else:
                print("Failed to select STATE using all available methods # 14.")
            
            # 15. ZIP code
            self.safe_send_keys((By.ID, 'rc.zip.value'), '12345')
            print("Filled ZIP code")

            # Click Next button
            next_button_locators = [
                (By.CSS_SELECTOR, '[data-testid="bottom-next-button"]'),
                (By.XPATH, "//button[contains(text(), 'Next')]"),
                (By.CSS_SELECTOR, "button.usa-button--primary")
            ]

            for locator in next_button_locators:
                if self.safe_click_element(locator):
                    print("Clicked Next button")
                    break
            else:
                print("Failed to find Next button")

            # Wait for the next page to load
            time.sleep(5)  # Wait for 5 seconds for the next page to load

        except Exception as e:
            print(f"Error in fill_reporting_company_info: {str(e)}")
            print("Current URL:", self.driver.current_url)
            print("Page source:")
            print(self.driver.page_source)
            self.take_screenshot("fill_reporting_company_info_error")
            raise

        print("Completed filling reporting company info")
 
    def fill_company_applicants(self, num_applicants):
        print(f"Filling company applicants info for {num_applicants} applicants...")
        try:
            # 16. Existing reporting company (check if existing reporting company as of January 1, 2024)
            #self.click_checkbox('rc.isExistingReportingCompany')   
            isExistingReportingCompany = False
            if isExistingReportingCompany == True:                
                self.safe_click_element((By.ID, 'rc.isExistingReportingCompany'))
                print ("isExistingReportingCompany is TRUE!! TODO")
                # Click Yes button
                try:
                    yes_button_locators = [
                        (By.CSS_SELECTOR, '[data-testid="modal-confirm-button"]'),
                    ]
                    for locator in yes_button_locators:
                        if self.safe_click_element(locator):
                            print("Clicked Yes button")
                            break
                    else:
                        print("Failed to find Yes button")

                    # Wait for the next page to load
                    time.sleep(5)  # Wait for 5 seconds for the next page to load

                except Exception as e:
                    print(f"Error in fill_reporting_company_info: {str(e)}")
                    print("Current URL:", self.driver.current_url)
                    print("Page source:")
                    print(self.driver.page_source)
                    self.take_screenshot("fill_reporting_company_info_error")
                    raise

                print("Completed filling reporting company info")

                # Click Yes button after filling all applicants
                try:
                    next_button_locators = [
                        (By.CSS_SELECTOR, '[data-testid="bottom-next-button"]'),
                        (By.XPATH, "//button[contains(text(), 'Next')]"),
                        (By.CSS_SELECTOR, "button.usa-button--primary") 
                
                    ]

                    for locator in next_button_locators:
                        if self.safe_click_element(locator):
                            print("Clicked Next button")
                            break
                    else:
                        print("Failed to find Next button")

                    # Wait for the next page to load
                    time.sleep(5)  # Adjust as needed

                except Exception as e:
                    print(f"Error in fill_company_applicants: {str(e)}")
                    raise
            print(f"{isExistingReportingCompany} - isExistingReportingCompany")
             
                # 17 This oart is reserved for future use
            for i in range(num_applicants):
                isExistingReportingCompany = False
                if isExistingReportingCompany == True:
                    # Fill applicant information 
                    #18  ca[0].fincenId
                    self.wait_and_send_keys((By.ID, f"ca[{i}].fincenId"), f"300000000000")
                #19
                self.wait_and_send_keys((By.ID, f"ca[{i}].lastName.value"), f"Valdez Galan")
                #20
                self.wait_and_send_keys((By.ID, f"ca[{i}].firstName.value"), f"Edison")
                #21
                self.wait_and_send_keys((By.ID, f"ca[{i}].middleName"), f"N")
                #22
                self.wait_and_send_keys((By.ID, f"ca[{i}].suffix"), f"Mr.")
                #23
                dob = "01/01/1980"
                if not self.validate_date(dob):
                    raise ValueError(f"Invalid date format: {dob}")
                self.wait_and_send_keys((By.ID, f"ca[{i}].dob.value"), dob)

 
                # #24 Select Address Type and fill in the address details
                for i in range(num_applicants):
                    address_type = 'BUSINESS'  # or 'RESIDENTIAL' based on your needs
                    self.select_address_type(i, address_type)
                #25      
                self.wait_and_send_keys((By.ID, f"ca[{i}].address.value"), f"456 Market St, Suite {300 + i}")
                #26
                self.wait_and_send_keys((By.ID, f"ca[{i}].city.value"), "San Francisco")

#########################2728272827282728272827282728#########################2728272827282728272827282728#########################2728272827282728272827282728
#########################2728272827282728272827282728#########################2728272827282728272827282728#########################2728272827282728272827282728
#########################2728272827282728272827282728#########################2728272827282728272827282728#########################2728272827282728272827282728


                # 27. Country/Jurisdiction of formation
                self.safe_click_element((By.XPATH, f'//*[@id="ca[{i}].country.value"]'))  # Use XPath for dynamic elements
                print("Clicked jurisdiction dropdown")
                # Wait for the dropdown to open
                time.sleep(2)
                # Try to select Country using different methods
                jurisdiction_option_locators = [
                    #(By.CSS_SELECTOR, '[data-testid="combo-box-option-US"]'),
                    #(By.XPATH, "//li[contains(text(), 'United States of America')]"),
                    (By.XPATH, f"//*[@id='ca[{i}].country.value--list--option-0']")
                ]
                for locator in jurisdiction_option_locators:
                    try:
                        self.safe_click_element(locator)
                        print(f"Selected US using locator: {locator}")
                        break
                    except Exception as e:
                        print(f"Failed to select US using locator: {locator}")
                else:
                    print("Failed to select US using all available methods")


                # 28. STATE
                self.safe_click_element((By.XPATH, f'//*[@id="ca[{i}].state.value"]'))  # Use XPath for dynamic elements
                print("Clicked STATE dropdown")
                # Wait for the dropdown to open
                time.sleep(2)
                # Try to select state_option_locators using different methods
                state_option_locators = [
                   # (By.CSS_SELECTOR, '[data-testid="combo-box-option-CA"]'),
                   # (By.XPATH, "//li[contains(text(), 'California')]"),
                    (By.XPATH, f"//*[@id='ca[{i}].state.value--list--option-7']")
                ]
                for locator in state_option_locators:
                    try:
                        self.safe_click_element(locator)
                        print(f"Selected STATE using locator: {locator}")
                        break
                    except Exception as e:
                        print(f"Failed to select STATE using locator: {locator}")
                else:
                    print("Failed to select STATE using all available methods")

#########################2728272827282728272827282728#########################2728272827282728272827282728#########################2728272827282728272827282728
#########################2728272827282728272827282728#########################2728272827282728272827282728#########################2728272827282728272827282728
#########################2728272827282728272827282728#########################2728272827282728272827282728#########################2728272827282728272827282728


                # 29 Fill ZIP code
                self.wait_and_send_keys((By.ID, f"ca[{i}].zip.value"), "94103")

                # 30 Select Identification type and fill in details

                self.wait_and_click((By.ID, f"ca[{i}].identification.type.value"))
                self.wait_and_click((By.CSS_SELECTOR, '[data-testid="combo-box-option-37"]'))  # Assuming State issued driver's license is option 37
                print("Selected State issued driver's license")                 

                # 31
                self.wait_and_send_keys((By.ID, f"ca[{i}].identification.id.value"), f"A{123456789 + i}")

                # 32 a. Country/Jurisdiction of formation //*[@id="ca[0].identification.jurisdiction.value"]
                self.safe_click_element((By.XPATH, f'//*[@id="ca[{i}].identification.jurisdiction.value"]'))  # Use XPath for dynamic elements
                print("Clicked jurisdiction dropdown")
                # Wait for the dropdown to open
                time.sleep(2)
                # Try to select Country using different methods
                jurisdiction_option_locators = [
                   # (By.CSS_SELECTOR, '[data-testid="combo-box-option-US"]'),
                   # (By.XPATH, "//li[contains(text(), 'United States of America')]"),
                    (By.XPATH, f"//*[@id='ca[0].identification.jurisdiction.value--list--option-0']") # 
                ]
                for locator in jurisdiction_option_locators:
                    try:
                        self.safe_click_element(locator)
                        print(f"Selected Country using locator: {locator}")
                        break
                    except Exception as e:
                        print(f"Failed to select Country using locator: {locator}")
                else:
                    print("Failed to select Country using all available methods")


                # 32 b. STATE  //*[@id="ca[0].identification.state.value"]
                self.safe_click_element((By.XPATH, f'//*[@id="ca[{i}].identification.state.value"]'))  # Use XPath for dynamic elements
                print("Clicked STATE dropdown")
                # Wait for the dropdown to open
                time.sleep(2)
                # Try to select state_option_locators using different methods
                state_option_locators = [
                   # (By.CSS_SELECTOR, '[data-testid="combo-box-option-CA"]'),
                   # (By.XPATH, "//li[contains(text(), 'California')]"),
                    (By.XPATH, f"//*[@id='ca[{i}].identification.state.value--list--option-7']")
                ]
                for locator in state_option_locators:
                    try:
                        self.safe_click_element(locator)
                        print(f"Selected STATE using locator: {locator}")
                        break
                    except Exception as e:
                        print(f"Failed to select STATE using locator: {locator}")
                else:
                    print("Failed to select STATE using all available methods")


                # 32 c. Fill tribal and local descriptions
                #self.wait_and_send_keys((By.ID, f"ca[{i}].identification.localTribal.value"), f"Local Description {i}")

                # 32 d.
                #self.wait_and_send_keys((By.ID, f"ca[{i}].identification.otherTribe.value"), f"Tribal Description {i}")
                # 33. Handle file upload
                file_input_xpath = f'//*[@id="ca[{i}].identification.image.value"]'  # Correct XPath for file input

                # You should provide the absolute path to the file you are uploading
                file_path = "https://www.dmv.pa.gov/REALID/PublishingImages/Pages/REAL-ID-Images/REAL%20ID-Compliant%20Non-Commercial%20Driver%27s%20License.jpg" #f"path/to/identification_image_{i}.png"  # Update with the actual path

                try:
                    # Wait until the file input element is present and interactable
                    file_input_element = WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.XPATH, file_input_xpath)))
                    
                    # Send the file path to the file input field
                    file_input_element.send_keys(file_path)
                    print(f"Successfully uploaded file: {file_path}")
                except Exception as e:
                    print(f"Failed to upload file: {file_path}. Error: {e}")


                # Add next applicant if there are more
                if i < num_applicants - 1:
                    self.wait_and_click((By.ID, "addCompanyApplicant"))
                    self.wait.until(EC.presence_of_element_located((By.ID, f"ca[{i+1}].fincenId")))

                # Click Next button after filling all applicants
                next_button_locators = [
                    (By.CSS_SELECTOR, '[data-testid="bottom-next-button"]'),
                    (By.XPATH, "//button[contains(text(), 'Next')]"),
                    (By.CSS_SELECTOR, "button.usa-button--primary") 
             
                ]

                for locator in next_button_locators:
                    if self.safe_click_element(locator):
                        print("Clicked Next button")
                        break
                else:
                    print("Failed to find Next button")

                # Wait for the next page to load
                time.sleep(5)  # Adjust as needed

        except Exception as e:
            print(f"Error in fill_company_applicants: {str(e)}")
            raise
 

    def fill_beneficial_owners(self, num_owners):
        print(f"Filling beneficial owners info for {num_owners} owners...")
        try:
            for i in range(num_owners):
                # 35
                parentInfo = False   #Should write a conditioning where calculates the dob of Beneficial Owner, if minor checked to TRUE!!
                if parentInfo == True:
                    self.safe_click_element((By.ID, f"bo[{i}].isParentGuardianInformation"))
                  #  self.wait_and_click((By.ID, f"bo[{i}].isParentGuardianInformation"))
                    print(f"parentInfo - {parentInfo}")
                print(f"parentInfo - {parentInfo}")

                # 36
                fincenId = False
                if fincenId == True:
                    self.wait_and_send_keys((By.ID, f"bo[{i}].fincenId"), f"300000000000")
                # 37
                isExcempt = False
                if isExcempt == True:
                    self.safe_click_element((By.ID, f"bo[{i}].isExemptEntity"))
                #    self.wait_and_click((By.ID, f"bo[{i}].isExemptEntity"))
                    print(f"{isExcempt} It is Excempt!!")
                    # 38
                    self.wait_and_send_keys((By.ID, f"bo[{i}].lastName.value"), f"OwnerLast")
                    self.wait_and_click((By.CSS_SELECTOR, "[data-testid='bottom-next-button']"))
                    print("Beneficial owners info filled successfully.")

               
                      # todo a click button skipping for the next page!!!!!!!!
              #  print(f"{isExcempt} Is not Excempt") 

                #self.wait_and_click((By.ID, f"bo[{i}].isExemptEntity"))
                # 38
                self.wait_and_send_keys((By.ID, f"bo[{i}].lastName.value"), f"OwnerLast")
                # 39
                self.wait_and_send_keys((By.ID, f"bo[{i}].firstName.value"), f"OwnerFirst")
                # 40
                self.wait_and_send_keys((By.ID, f"bo[{i}].middleName"), f"OwnerMiddle")
                # 41
                self.wait_and_send_keys((By.ID, f"bo[{i}].suffix"), f"Sr")
                # 42
                dob = f"01/01/{1980 + i}"
                if not self.validate_date(dob):
                    raise ValueError(f"Invalid date format: {dob}")
                self.wait_and_send_keys((By.ID, f"bo[{i}].dob.value"), dob)
                # 43
                self.wait_and_send_keys((By.ID, f"bo[{i}].address.value"), f"789 Oak St, Apt {100 + i}")
                # 44
                self.wait_and_send_keys((By.ID, f"bo[{i}].city.value"), "Anytown")


                # 45 Country/Jurisdiction of formation //*//*[@id="bo[0].country.value"]
                self.safe_click_element((By.XPATH, f'//*[@id="bo[{i}].country.value"]'))  # Use XPath for dynamic elements
                print("Clicked jurisdiction dropdown - 45 Country/Jurisdiction of formation ")
                # Wait for the dropdown to open
                time.sleep(2)
                # Try to select Country using different methods
                jurisdiction_option_locators = [
                    #(By.CSS_SELECTOR, '[data-testid="combo-box-option-US"]'),
                    #(By.XPATH, "//li[contains(text(), 'United States of America')]"),
                    (By.XPATH, f"//*[@id='bo[0].country.value--list--option-0']")  
                ]
                for locator in jurisdiction_option_locators:
                    try:
                        self.safe_click_element(locator)
                        print(f"Selected Country using locator: {locator}")
                        break
                    except Exception as e:
                        print(f"Failed to select Country using locator: {locator}")
                else:
                    print("Failed to select Country using all available methods")


                # 46 STATE  //*[@id="bo[0].state.value"]
                self.safe_click_element((By.XPATH, f'//*[@id="bo[{i}].state.value"]'))  # Use XPath for dynamic elements
                print("Clicked STATE dropdown - state.value")
                # Wait for the dropdown to open
                time.sleep(2)
                # Try to select state_option_locators using different methods
                state_option_locators = [
                    #(By.CSS_SELECTOR, '[data-testid="combo-box-option-CA"]'),
                    #(By.XPATH, "//li[contains(text(), 'California')]"),
                    (By.XPATH, f"//*[@id='bo[{i}].state.value--list--option-7']")
                ]
                for locator in state_option_locators:
                    try:
                        self.safe_click_element(locator)
                        print(f"Selected STATE using locator: {locator}")
                        break
                    except Exception as e:
                        print(f"Failed to select STATE using locator: {locator}")
                else:
                    print("Failed to select STATE using all available methods")


                #47
                self.wait_and_send_keys((By.ID, f"bo[{i}].zip.value"), "12345")

                # 48  //*[@id="bo[0].identification.type.value"]
                self.wait_and_click((By.ID, f"bo[{i}].identification.type.value"))
                self.wait_and_click((By.CSS_SELECTOR, "[data-testid='combo-box-option-37']"))
                print("Selected State issued driver's license")  

                #49
                self.wait_and_send_keys((By.ID, f"bo[{i}].identification.id.value"), f"ABC{123456 + i}")


                # 50 a. Country/Jurisdiction of formation  //*[@id="bo[0].identification.jurisdiction.value"]
                self.safe_click_element((By.XPATH, f'//*[@id="bo[{i}].identification.jurisdiction.value"]'))  # Use XPath for dynamic elements
                print("Clicked jurisdiction dropdown - 50 a. Country/Jurisdiction of formation ")
                # Wait for the dropdown to open
                time.sleep(2)
                # Try to select Country using different methods
                jurisdiction_option_locators = [
                # (By.CSS_SELECTOR, '[data-testid="combo-box-option-US"]'),
                    #(By.XPATH, "//li[contains(text(), 'United States of America')]"),
                    (By.XPATH, f"//*[@id='bo[{i}].identification.jurisdiction.value--list--option-0']")  
                ]
                for locator in jurisdiction_option_locators:
                    try:
                        self.safe_click_element(locator)
                        print(f"Selected Country using locator: {locator}")
                        break
                    except Exception as e:
                        print(f"Failed to select Country using locator: {locator}")
                else:
                    print("Failed to select Country using all available methods")


                # 50 b. STATE    //*[@id="bo[0].identification.state.value"]
                self.safe_click_element((By.XPATH, f'//*[@id="bo[{i}].identification.state.value"]'))  # Use XPath for dynamic elements
                print("Clicked STATE dropdown - identification.state.value")
                # Wait for the dropdown to open
                time.sleep(2)
                # Try to select state_option_locators using different methods
                state_option_locators = [
                    # (By.CSS_SELECTOR, '[data-testid="combo-box-option-CA"]'),
                    #(By.XPATH, "//li[contains(text(), 'California')]"),
                    (By.XPATH, f"//*[@id='bo[{i}].identification.state.value--list--option-7']")
                ]
                for locator in state_option_locators:
                    try:
                        self.safe_click_element(locator)
                        print(f"Selected STATE using locator: {locator}")
                        break
                    except Exception as e:
                        print(f"Failed to select STATE using locator: {locator}")
                else:
                    print("Failed to select STATE using all available methods")

                # 50 c.

                # 50 d.

                # 51. Handle file upload  //*[@id="bo[0].identification.image.value"]
                file_input_xpath = f'//*[@id="bo[{i}].identification.image.value"]'  # Correct XPath for file input

                # provide the absolute path to the file  
                file_path = "https://www.dmv.pa.gov/REALID/PublishingImages/Pages/REAL-ID-Images/REAL%20ID-Compliant%20Non-Commercial%20Driver%27s%20License.jpg" #f"path/to/identification_image_{i}.png"  # Update with the actual path

                try:
                    # Wait until the file input element is present and interactable
                    file_input_element = WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.XPATH, file_input_xpath)))
                    
                    # Send the file path to the file input field
                    file_input_element.send_keys(file_path)
                    print(f"Successfully uploaded file: {file_path}")
                except Exception as e:
                    print(f"Failed to upload file: {file_path}. Error: {e}")

                if i < num_owners - 1:
                    self.wait_and_click((By.ID, "addBeneficialOwner"))
                    self.wait.until(EC.presence_of_element_located((By.ID, f"bo[{i+1}].fincenId")))
                 
            self.wait_and_click((By.CSS_SELECTOR, "[data-testid='bottom-next-button']"))
            print("Beneficial owners info filled successfully.")
        except Exception as e:
            print(f"Error in fill_beneficial_owners: {str(e)}")
            raise

    def fill_submission_info(self):
        print("Filling submission info...")
        try:
            self.wait.until(EC.presence_of_element_located((By.ID, "email")))

            self.wait_and_send_keys((By.ID, "email"), "your_email@example.com")
            self.wait_and_send_keys((By.ID, "confirmEmail"), "your_email@example.com")
            self.wait_and_send_keys((By.ID, "firstName"), "YourFirstName")
            self.wait_and_send_keys((By.ID, "lastName"), "YourLastName")

            # I agree
            self.safe_click_element((By.XPATH, '//*[@id="certifyCB"]'))

            if True:
                self.wait_and_click((By.CSS_SELECTOR, "[data-testid='modal-confirm-button']"))
 
# Captcha # Captcha # Captcha # Captcha # Captcha # Captcha # Captcha # Captcha # Captcha # Captcha 
# Captcha # Captcha # Captcha # Captcha # Captcha # Captcha # Captcha # Captcha # Captcha # Captcha 
# Captcha # Captcha # Captcha # Captcha # Captcha # Captcha # Captcha # Captcha # Captcha # Captcha 

            # Initialize the 2Captcha solver
            solver = TwoCaptcha('YOUR_2CAPTCHA_API_KEY') 
            # Wait for the reCAPTCHA to load
            WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.CLASS_NAME, 'g-recaptcha')))
            # Get the reCAPTCHA site key
            site_key = self.driver.find_element(By.CLASS_NAME, 'g-recaptcha').get_attribute('data-sitekey')
            page_url = self.driver.current_url
            # Request CAPTCHA solving from 2Captcha
            print("Solving CAPTCHA...")
            captcha_result = solver.recaptcha(sitekey=site_key, url=page_url)
            # Once CAPTCHA is solved, you receive a token
            captcha_token = captcha_result['code']
            print(f"CAPTCHA solved: {captcha_token}")
            # Inject the token into the reCAPTCHA form
            self.driver.execute_script(f"document.getElementById('g-recaptcha-response').innerHTML = '{captcha_token}';")
            # Submit the form
            self.driver.find_element(By.ID, 'recaptcha-demo-submit').click()
            # Wait for the form submission to complete
            time.sleep(5)
            # Optionally: Take action after CAPTCHA is solved
            print("CAPTCHA bypassed and form submitted.")

         
            print("Please solve the hCaptcha manually if it appears.")
            input("Press Enter after solving the CAPTCHA...")

            self.wait_and_click((By.ID, "FormSubmit"))

            self.wait.until(EC.presence_of_element_located((By.ID, "submissionConfirmation")))
            print("Form submitted successfully!")
        except Exception as e:
            print(f"Error in fill_submission_info: {str(e)}")
            raise

    def take_screenshot(self, name):
        self.driver.save_screenshot(f"{name}.png")

    def is_browser_responsive(self):
        try:
            # Try to execute a simple JavaScript command
            self.driver.execute_script("return 1;")
            return True
        except Exception as e:
            print(f"Browser seems unresponsive: {str(e)}")
            return False

    def run(self):
        try:
            self.start_form()
            self.fill_filing_information()
            
            if not self.is_browser_responsive():
                print("Browser became unresponsive after filling Filing Information")
                self.take_screenshot("unresponsive_browser")
                return

            self.fill_reporting_company_info()
            self.fill_company_applicants(1)
            self.fill_beneficial_owners(1)
            self.fill_submission_info()
        except Exception as e:
            print(f"An error occurred: {str(e)}")
            print("Traceback:")
            traceback.print_exc()
            self.take_screenshot("error_screenshot")
        finally:
            print("Closing the driver...")
            self.driver.quit()

if __name__ == "__main__":
    form_filler = FormFiller()
    form_filler.run()

 


