import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
from selenium.webdriver.common.keys import Keys

import traceback
import re
from datetime import datetime



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
            self.wait = WebDriverWait(self.driver, 60)  # Increase timeout to 60 seconds
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

            time.sleep(10)  # Increase delay to 10 seconds

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

    def select_country_and_city(self, index):
        """
        Selects the country and city for the given address index.
        :param index: The index of the address (e.g., 1 or 2).
        """
        # Select country
        country_dropdown = self.wait.until(EC.presence_of_element_located((By.ID, f"ca[{index}].country.value")))
        us_option = self.wait.until(EC.presence_of_element_located((By.XPATH, "//li[@data-testid='combo-box-option-US']")))

        self.scroll_to_element(country_dropdown)
        self.scroll_to_element(us_option)
        self.select_and_trigger_change(country_dropdown, us_option)

        # Select city
        city_dropdown = self.wait.until(EC.presence_of_element_located((By.ID, f"ca[{index}].city.value")))
        city_option = self.wait.until(EC.presence_of_element_located((By.XPATH, "//li[contains(text(), 'San Francisco')]")))

        self.scroll_to_element(city_dropdown)
        self.scroll_to_element(city_option)
        self.select_and_trigger_change(city_dropdown, city_option)

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
            self.wait_and_send_keys((By.ID, 'rc.taxId'), '12-3456789')
            print("Filled Tax Identification number")

            # 9. Country/Jurisdiction (if foreign tax ID only) - skip for now


            # 10. Country/Jurisdiction of formation
            self.safe_click_element((By.ID, 'rc.jurisdiction'))
            print("Clicked jurisdiction dropdown")

            # Wait for the dropdown to open
            time.sleep(2)

     
            # Try to select US using different methods
            us_option_locators = [
                (By.CSS_SELECTOR, '[data-testid="combo-box-option-US"]'),
                (By.XPATH, "//li[contains(text(), 'United States')]"),
                (By.XPATH, "//li[@data-value='US']")
            ]
            for locator in us_option_locators:
                try:
                    self.safe_click_element(locator)
                    print(f"Selected US using locator: {locator}")
                    break
                except Exception as e:
                    print(f"Failed to select US using locator: {locator}")
            else:
                print("Failed to select US using all available methods")
 

            # 11. Address
            self.wait_and_send_keys((By.ID, 'rc.address.value'), '123 Test Street')
            print("Filled Address")

            # 12. City
            self.wait_and_send_keys((By.ID, 'rc.city.value'), 'Test City')
            print("Filled City")

            # 13. U.S. or U.S. Territory
            try:
                self.safe_select_dropdown('rc.country.value', 'United States of America')
            except:
                self.safe_select_dropdown('rc.country.value', 'US')

            # 14. State
            try:
                self.safe_select_dropdown('rc.state.value', 'Florida')
            except:
                self.safe_select_dropdown('rc.state.value', 'FL')

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


    #Claude Haiku
    def fill_company_applicants(self, num_applicants):
        print(f"Filling company applicants info for {num_applicants} applicants...")
        try:
            # 16. Existing reporting Checkbox
            self.click_checkbox('rc.isExistingReportingCompany')

            for i in range(num_applicants):
                fincen_id = f"F{12345678 + i}"
                if not self.validate_fincen_id(fincen_id):
                    raise ValueError(f"Invalid FinCEN ID format: {fincen_id}")

                # 18. FinCEN ID
                self.wait_and_send_keys((By.ID, f"ca[{i}].fincenId"), fincen_id)
                # 19. Last Name
                self.wait_and_send_keys((By.ID, f"ca[{i}].lastName.value"), f"Doe{i}")
                # 20. First Name
                self.wait_and_send_keys((By.ID, f"ca[{i}].firstName.value"), f"John{i}")
                # 21. Middle Name
                self.wait_and_send_keys((By.ID, f"ca[{i}].middleName"), f"A{i}")
                # 22. Suffix
                self.wait_and_send_keys((By.ID, f"ca[{i}].suffix"), f"Jr{i}")
                # 23. Date of Birth
                dob = "01/01/1980"
                if not self.validate_date(dob):
                    raise ValueError(f"Invalid date format: {dob}")
                self.wait_and_send_keys((By.ID, f"ca[{i}].dob.value"), dob)
                # 24. Select Address Type and fill in the address details
                for i in range(num_applicants):
                    address_type = 'BUSINESS'  # or 'RESIDENTIAL' based on your needs
                    self.select_address_type(i, address_type)

                # 25. Address
                self.wait_and_send_keys((By.ID, f"ca[{i}].address.value"), f"456 Market St, Suite {300 + i}")
                # 26. City
                self.wait_and_send_keys((By.ID, f"ca[{i}].city.value"), "San Francisco")

                # 27. Select country as "US"
                self.select_country_and_city(i)

                # 28. Select state as "CA"
                state_dropdown = self.wait.until(EC.presence_of_element_located((By.ID, f"ca[{i}].state.value")))
                ca_option = self.wait.until(EC.presence_of_element_located((By.XPATH, "//li[@data-value='CA']")))

                self.scroll_to_element(state_dropdown)
                self.scroll_to_element(ca_option)
                self.select_and_trigger_change(state_dropdown, ca_option)

                # Fill ZIP code
                self.wait_and_send_keys((By.ID, f"ca[{i}].zip.value"), "94103")

                # Select Identification type and fill in details
                self.wait_and_click((By.ID, f"ca[{i}].identification.type.value"))
                if not self.safe_click_element((By.CSS_SELECTOR, '[data-testid="combo-box-option-2"]')):
                    print("Failed to select identification type, using JavaScript...")
                    self.safe_click_element_js((By.XPATH, "//li[@data-testid='combo-box-option-2']"))

                self.wait_and_send_keys((By.ID, f"ca[{i}].identification.id.value"), f"A{123456789 + i}")

                # Select jurisdiction as "US" for Identification
                self.wait_and_click((By.ID, f"ca[{i}].identification.jurisdiction.value"))
                if not self.safe_click_element((By.CSS_SELECTOR, '[data-testid="combo-box-option-US"]')):
                    print("Failed to select US in jurisdiction, using JavaScript...")
                    self.safe_click_element_js((By.XPATH, "//li[@data-testid='combo-box-option-US']"))

                # Select state for Identification
                self.wait_and_click((By.ID, f"ca[{i}].identification.state.value"))
                if not self.safe_click_element((By.CSS_SELECTOR, '[data-testid="combo-box-option-CA"]')):
                    print("Failed to select CA in state dropdown for identification, using JavaScript...")
                    self.safe_click_element_js((By.XPATH, "//li[@data-testid='combo-box-option-CA']"))

                # Fill tribal and local descriptions
                self.wait_and_send_keys((By.ID, f"ca[{i}].identification.localTribal.value"), f"Local Description {i}")
                self.wait_and_send_keys((By.ID, f"ca[{i}].identification.otherTribe.value"), f"Tribal Description {i}")

                # Handle file upload (might need tweaking depending on how file uploads are handled on this form)
                self.wait_and_send_keys((By.ID, f"ca[{i}].identification.image.value"), f"path/to/identification_image_{i}.png")

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
            print(f"Error in Company Applicant: {str(e)}")
            raise

    def fill_beneficial_owners(self, num_owners):
        print(f"Filling beneficial owners info for {num_owners} owners...")
        try:
            for i in range(num_owners):
                self.wait_and_click((By.ID, f"bo[{i}].isParentGuardianInformation"))

                fincen_id = f"BO{12345678 + i}"
                if not self.validate_fincen_id(fincen_id):
                    raise ValueError(f"Invalid FinCEN ID format: {fincen_id}")
                self.wait_and_send_keys((By.ID, f"bo[{i}].fincenId"), fincen_id)

                self.wait_and_click((By.ID, f"bo[{i}].isExemptEntity"))

                self.wait_and_send_keys((By.ID, f"bo[{i}].lastName.value"), f"OwnerLast{i}")
                self.wait_and_send_keys((By.ID, f"bo[{i}].firstName.value"), f"OwnerFirst{i}")
                self.wait_and_send_keys((By.ID, f"bo[{i}].middleName"), f"OwnerMiddle{i}")
                self.wait_and_send_keys((By.ID, f"bo[{i}].suffix"), f"Sr{i}")

                dob = f"01/01/{1980 + i}"
                if not self.validate_date(dob):
                    raise ValueError(f"Invalid date format: {dob}")
                self.wait_and_send_keys((By.ID, f"bo[{i}].dob.value"), dob)

                self.wait_and_send_keys((By.ID, f"bo[{i}].address.value"), f"789 Oak St, Apt {100 + i}")
                self.wait_and_send_keys((By.ID, f"bo[{i}].city.value"), "Anytown")

                self.wait_and_click((By.ID, f"bo[{i}].country.value"))
                self.wait_and_click((By.CSS_SELECTOR, "[data-testid='combo-box-option-US']"))

                self.wait_and_click((By.ID, f"bo[{i}].state.value"))
                self.wait_and_click((By.CSS_SELECTOR, "[data-testid='combo-box-option-CA']"))

                self.wait_and_send_keys((By.ID, f"bo[{i}].zip.value"), "12345")

                self.wait_and_click((By.ID, f"bo[{i}].identification.type.value"))
                self.wait_and_click((By.CSS_SELECTOR, "[data-testid='combo-box-option-1']"))

                self.wait_and_send_keys((By.ID, f"bo[{i}].identification.id.value"), f"ABC{123456 + i}")

                self.wait_and_click((By.ID, f"bo[{i}].identification.jurisdiction.value"))
                self.wait_and_click((By.CSS_SELECTOR, "[data-testid='combo-box-option-US']"))

                self.wait_and_click((By.ID, f"bo[{i}].identification.state.value"))
                self.wait_and_click((By.CSS_SELECTOR, "[data-testid='combo-box-option-CA']"))

                # Note: File upload might need a different approach
                self.wait_and_send_keys((By.ID, f"bo[{i}].identification.image.value"), f"path/to/identification_image_{i}.png")

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

            self.wait_and_click((By.ID, "certifyCB"))

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

 
