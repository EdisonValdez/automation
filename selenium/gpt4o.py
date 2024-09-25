
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException
import time
from selenium.webdriver.support.ui import Select

import traceback

class FormFiller:
    def __init__(self):
        # Set up the WebDriver options
        options = webdriver.ChromeOptions()
        options.add_argument('--headless')  # Run Chrome in headless mode (no GUI)
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920x1080')
        self.driver = webdriver.Chrome(options=options)

        # WebDriverWait instance with a 10-second timeout
        self.wait = WebDriverWait(self.driver, 10)

    def start_form(self):
        try:
            # Load the form URL
            form_url = "https://boiefiling.fincen.gov/boir/html"  # Change to actual form URL
            self.driver.get(form_url)

            # Ensure the page has loaded completely
            self.wait.until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
            print("Form page loaded.")
        except Exception as e:
            print(f"Error starting form: {str(e)}")
            raise

    def safe_click_element(self, locator):
        try:
            element = self.wait.until(EC.element_to_be_clickable(locator))
            element.click()
            return True
        except Exception as e:
            print(f"Error clicking element: {str(e)}")
            return False

    def safe_send_keys(self, locator, keys):
        try:
            element = self.wait.until(EC.presence_of_element_located(locator))
            element.clear()
            element.send_keys(keys)
            return True
        except Exception as e:
            print(f"Error sending keys to element: {str(e)}")
            return False

    def go_to_next_step(self):
        try:
            # Click the 'Next' button to move to the next page of the form
            next_button_locator = (By.CSS_SELECTOR, 'button[aria-label="Next"]')
            if self.safe_click_element(next_button_locator):
                print("Navigated to the next step.")
                time.sleep(2)  # Give it time to load the next section
                return True
            else:
                print("Failed to click the 'Next' button.")
                return False
        except Exception as e:
            print(f"Error navigating to next step: {str(e)}")
            return False

    def fill_country_field(self, country):
        try:
            # Find and fill the 'Country' input field
            country_input_locator = (By.CSS_SELECTOR, 'input[name="country"]')
            if self.safe_send_keys(country_input_locator, country):
                print(f"Filled country field with: {country}")
                return True
            else:
                print("Failed to fill the 'Country' field.")
                return False
        except Exception as e:
            print(f"Error filling country field: {str(e)}")
            return False

    def fill_city_field(self, city):
        try:
            # Find and fill the 'City' input field
            city_input_locator = (By.CSS_SELECTOR, 'input[name="city"]')
            if self.safe_send_keys(city_input_locator, city):
                print(f"Filled city field with: {city}")
                return True
            else:
                print("Failed to fill the 'City' field.")
                return False
        except Exception as e:
            print(f"Error filling city field: {str(e)}")
            return False

    def validate_field(self, locator, field_name):
        try:
            # Check if the field has any validation error messages
            error_locator = (By.XPATH, f"//input[@name='{field_name}']/following-sibling::span[@class='error-message']")
            error_element = self.driver.find_element(*error_locator)
            if error_element and error_element.is_displayed():
                print(f"Validation error found for {field_name}: {error_element.text}")
                return False
            else:
                print(f"No validation error found for {field_name}.")
                return True
        except NoSuchElementException:
            # No error found means the field is valid
            print(f"No validation error for {field_name}.")
            return True
        except Exception as e:
            print(f"Error validating field {field_name}: {str(e)}")
            return False

    def check_for_general_errors(self):
        try:
            # Check if there are any general error messages on the form
            general_error_locator = (By.CSS_SELECTOR, 'div.general-error-message')
            error_element = self.driver.find_element(*general_error_locator)
            if error_element and error_element.is_displayed():
                print(f"General error found: {error_element.text}")
                return False
            else:
                print("No general errors found.")
                return True
        except NoSuchElementException:
            # No general errors found
            print("No general errors present.")
            return True
        except Exception as e:
            print(f"Error checking for general errors: {str(e)}")
            return False

    def check_required_field(self, field_name):
        try:
            # Ensure that a required field is filled
            required_field_locator = (By.XPATH, f"//input[@name='{field_name}' and @required]")
            field_element = self.driver.find_element(*required_field_locator)
            if field_element.get_attribute('value'):
                print(f"Required field '{field_name}' is filled.")
                return True
            else:
                print(f"Required field '{field_name}' is empty.")
                return False
        except NoSuchElementException:
            print(f"Required field '{field_name}' not found.")
            return False
        except Exception as e:
            print(f"Error checking required field '{field_name}': {str(e)}")
            return False

    def click_next_button(self):
        try:
            # Find and click the "Next" button to go to the next step
            next_button = self.driver.find_element(By.CSS_SELECTOR, 'button.next-button')
            if next_button.is_enabled():
                next_button.click()
                print("Clicked on the 'Next' button.")
                return True
            else:
                print("'Next' button is disabled.")
                return False
        except NoSuchElementException:
            print("The 'Next' button was not found on the page.")
            return False
        except Exception as e:
            print(f"Error clicking 'Next' button: {str(e)}")
            return False

    def click_previous_button(self):
        try:
            # Find and click the "Previous" button to go back to the previous step
            prev_button = self.driver.find_element(By.CSS_SELECTOR, 'button.previous-button')
            if prev_button.is_enabled():
                prev_button.click()
                print("Clicked on the 'Previous' button.")
                return True
            else:
                print("'Previous' button is disabled.")
                return False
        except NoSuchElementException:
            print("The 'Previous' button was not found on the page.")
            return False
        except Exception as e:
            print(f"Error clicking 'Previous' button: {str(e)}")
            return False

    def go_to_step(self, step_number):
        try:
            # Navigate directly to a specific step by clicking on its corresponding step marker
            step_locator = (By.CSS_SELECTOR, f'div.step-indicator[data-step="{step_number}"]')
            step_element = self.driver.find_element(*step_locator)
            if step_element.is_enabled():
                step_element.click()
                print(f"Navigated to step {step_number}.")
                return True
            else:
                print(f"Step {step_number} is not clickable or disabled.")
                return False
        except NoSuchElementException:
            print(f"Step {step_number} not found.")
            return False
        except Exception as e:
            print(f"Error navigating to step {step_number}: {str(e)}")
            return False

    def verify_current_step(self, expected_step_number):
        try:
            # Verify that the current step in the wizard is the expected one
            active_step_locator = (By.CSS_SELECTOR, 'div.step-indicator.active')
            active_step_element = self.driver.find_element(*active_step_locator)
            current_step = active_step_element.get_attribute('data-step')
            if current_step == str(expected_step_number):
                print(f"Successfully navigated to step {expected_step_number}.")
                return True
            else:
                print(f"Currently on step {current_step}, expected {expected_step_number}.")
                return False
        except NoSuchElementException:
            print("Could not verify the current step.")
            return False
        except Exception as e:
            print(f"Error verifying the current step: {str(e)}")
            return False

    def is_field_required(self, field_name):
        try:
            # Check if a specific form field has the 'required' attribute
            field_element = self.driver.find_element(By.NAME, field_name)
            required = field_element.get_attribute('required')
            if required:
                print(f"The field '{field_name}' is required.")
                return True
            else:
                print(f"The field '{field_name}' is not required.")
                return False
        except NoSuchElementException:
            print(f"Field '{field_name}' was not found.")
            return False
        except Exception as e:
            print(f"Error checking if field '{field_name}' is required: {str(e)}")
            return False

    def is_form_valid(self):
        try:
            # Check if the form can be submitted, i.e., all required fields are filled
            submit_button = self.driver.find_element(By.CSS_SELECTOR, 'button.submit-button')
            if submit_button.is_enabled():
                print("The form is valid and can be submitted.")
                return True
            else:
                print("The form is not ready for submission.")
                return False
        except NoSuchElementException:
            print("Submit button was not found.")
            return False
        except Exception as e:
            print(f"Error checking form validity: {str(e)}")
            return False

    def get_field_validation_message(self, field_name):
        try:
            # Get the validation message of a form field (if any)
            field_element = self.driver.find_element(By.NAME, field_name)
            validation_message = field_element.get_attribute('validationMessage')
            if validation_message:
                print(f"Validation message for field '{field_name}': {validation_message}")
                return validation_message
            else:
                print(f"No validation message for field '{field_name}'.")
                return ""
        except NoSuchElementException:
            print(f"Field '{field_name}' was not found.")
            return ""
        except Exception as e:
            print(f"Error retrieving validation message for field '{field_name}': {str(e)}")
            return ""

    def select_from_dropdown(self, dropdown_id, option_text):
        try:
            dropdown = self.wait.until(EC.presence_of_element_located((By.ID, dropdown_id)))
            dropdown.click()
            option = self.wait.until(EC.presence_of_element_located((By.XPATH, f"//li[contains(text(), '{option_text}')]")))
            option.click()
            print(f"Selected '{option_text}' from dropdown '{dropdown_id}'.")
        except Exception as e:
            print(f"Error selecting '{option_text}' from dropdown '{dropdown_id}': {str(e)}")
            self.take_screenshot(f"select_from_dropdown_{dropdown_id}_{option_text}")

    def click_button(self, button_selector):
        try:
            button = self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, button_selector)))
            button.click()
            print(f"Clicked button with selector '{button_selector}'.")
        except Exception as e:
            print(f"Error clicking button with selector '{button_selector}': {str(e)}")
            self.take_screenshot(f"click_button_{button_selector}")

    def safe_click_element(self, locator):
        try:
            element = self.wait.until(EC.element_to_be_clickable(locator))
            element.click()
            print(f"Safely clicked element with locator '{locator}'.")
            return True
        except Exception as e:
            print(f"Error safely clicking element with locator '{locator}': {str(e)}")
            self.take_screenshot(f"safe_click_element_{locator}")
            return False

    def wait_and_click(self, locator):
        try:
            element = self.wait.until(EC.element_to_be_clickable(locator))
            element.click()
            print(f"Waited for and clicked element with locator '{locator}'.")
            return True
        except Exception as e:
            print(f"Error waiting for and clicking element with locator '{locator}': {str(e)}")
            self.take_screenshot(f"wait_and_click_{locator}")
            return False

    def safe_find_element(self, locator):
        try:
            element = self.wait.until(EC.presence_of_element_located(locator))
            print(f"Safely found element with locator '{locator}'.")
            return element
        except Exception as e:
            print(f"Error safely finding element with locator '{locator}': {str(e)}")
            self.take_screenshot(f"safe_find_element_{locator}")
            return None

    def scroll_to_element(self, element):
        try:
            self.driver.execute_script("arguments[0].scrollIntoView();", element)
            print("Scrolled to element.")
        except Exception as e:
            print(f"Error scrolling to element: {str(e)}")
            self.take_screenshot("scroll_to_element_error")

    def select_and_trigger_change(self, dropdown, option):
        try:
            self.scroll_to_element(dropdown)
            self.scroll_to_element(option)
            option.click()
            # Trigger the change event
            self.driver.execute_script("arguments[0].dispatchEvent(new Event('change', { bubbles: true }));", dropdown)
            print("Selected option and triggered change event.")
        except Exception as e:
            print(f"Error selecting option and triggering change: {str(e)}")
            self.take_screenshot("select_and_trigger_change_error")

    def fill_filing_information(self, filing_type, filing_date):
        try:
            print("Filling filing information...")

            # Wait for the filing type dropdown to be present
            filing_type_dropdown = self.wait.until(EC.presence_of_element_located((By.ID, "filingType")))
            filing_date_field = self.wait.until(EC.presence_of_element_located((By.ID, "filingDate")))

            # Select filing type
            Select(filing_type_dropdown).select_by_visible_text(filing_type)

            # Enter filing date
            filing_date_field.clear()
            filing_date_field.send_keys(filing_date)

            print("Completed filling filing information")
        
        except Exception as e:
            print(f"Error in fill_filing_information: {e}")
            self.take_screenshot("fill_filing_information_error")

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
            time.sleep(2)  # Adjust if needed

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
            time.sleep(5)  # Adjust as needed

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
            # 16. Existing reporting Checkbox
            self.click_checkbox('rc.isExistingReportingCompany')

            for i in range(num_applicants):
                # Generate FinCEN ID for each applicant
                fincen_id = f"F{12345678 + i}"
                if not self.validate_fincen_id(fincen_id):
                    raise ValueError(f"Invalid FinCEN ID format: {fincen_id}")

                # Fill applicant information
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
                dob = "01/01/1980"  # Example date of birth, should be dynamic if needed
                if not self.validate_date(dob):
                    raise ValueError(f"Invalid date format: {dob}")
                self.wait_and_send_keys((By.ID, f"ca[{i}].dob.value"), dob)

                # 24. Address Type
                address_type = 'BUSINESS'  # Or 'RESIDENTIAL' based on your needs
                self.select_address_type(i, address_type)

                # 25. Address
                self.wait_and_send_keys((By.ID, f"ca[{i}].address.value"), f"456 Market St, Suite {300 + i}")

                # 26. City
                self.wait_and_send_keys((By.ID, f"ca[{i}].city.value"), "San Francisco")

                # 27. Country
                country_dropdown = self.wait.until(EC.presence_of_element_located((By.ID, f"ca[{i}].country.value")))
                us_option = self.wait.until(EC.presence_of_element_located((By.XPATH, "//li[@data-testid='combo-box-option-US']")))
                self.scroll_to_element(country_dropdown)
                self.scroll_to_element(us_option)
                self.select_and_trigger_change(country_dropdown, us_option)

                # 28. State
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
            print(f"Error in fill_company_applicants: {str(e)}")
            self.take_screenshot("fill_company_applicants_error")
            raise
        finally:
            print("Completed filling company applicants info")

    def fill_beneficial_owners(self, num_owners):
        print(f"Filling beneficial owners info for {num_owners} owners...")
        try:
            for i in range(num_owners):
                # Generate FinCEN ID for each beneficial owner
                fincen_id = f"B{12345678 + i}"
                if not self.validate_fincen_id(fincen_id):
                    raise ValueError(f"Invalid FinCEN ID format: {fincen_id}")

                # 16. FinCEN ID
                self.wait_and_send_keys((By.ID, f"bo[{i}].fincenId"), fincen_id)

                # 17. Last Name
                self.wait_and_send_keys((By.ID, f"bo[{i}].lastName.value"), f"Smith{i}")

                # 18. First Name
                self.wait_and_send_keys((By.ID, f"bo[{i}].firstName.value"), f"Jane{i}")

                # 19. Middle Name
                self.wait_and_send_keys((By.ID, f"bo[{i}].middleName"), f"B{i}")

                # 20. Suffix
                self.wait_and_send_keys((By.ID, f"bo[{i}].suffix"), f"Sr{i}")

                # 21. Date of Birth
                dob = "02/15/1975"  # Example date of birth, should be dynamic if needed
                if not self.validate_date(dob):
                    raise ValueError(f"Invalid date format: {dob}")
                self.wait_and_send_keys((By.ID, f"bo[{i}].dob.value"), dob)

                # 22. Address Type
                address_type = 'RESIDENTIAL'  # Or 'BUSINESS' based on your needs
                self.select_address_type(i, address_type)

                # 23. Address
                self.wait_and_send_keys((By.ID, f"bo[{i}].address.value"), f"789 Elm St, Apt {100 + i}")

                # 24. City
                self.wait_and_send_keys((By.ID, f"bo[{i}].city.value"), "Los Angeles")

                # 25. Country
                country_dropdown = self.wait.until(EC.presence_of_element_located((By.ID, f"bo[{i}].country.value")))
                us_option = self.wait.until(EC.presence_of_element_located((By.XPATH, "//li[@data-testid='combo-box-option-US']")))
                self.scroll_to_element(country_dropdown)
                self.scroll_to_element(us_option)
                self.select_and_trigger_change(country_dropdown, us_option)

                # 26. State
                state_dropdown = self.wait.until(EC.presence_of_element_located((By.ID, f"bo[{i}].state.value")))
                ca_option = self.wait.until(EC.presence_of_element_located((By.XPATH, "//li[@data-value='CA']")))
                self.scroll_to_element(state_dropdown)
                self.scroll_to_element(ca_option)
                self.select_and_trigger_change(state_dropdown, ca_option)

                # Fill ZIP code
                self.wait_and_send_keys((By.ID, f"bo[{i}].zip.value"), "90001")

                # Select Identification type and fill in details
                self.wait_and_click((By.ID, f"bo[{i}].identification.type.value"))
                if not self.safe_click_element((By.CSS_SELECTOR, '[data-testid="combo-box-option-1"]')):
                    print("Failed to select identification type, using JavaScript...")
                    self.safe_click_element_js((By.XPATH, "//li[@data-testid='combo-box-option-1']"))
                self.wait_and_send_keys((By.ID, f"bo[{i}].identification.id.value"), f"B{987654321 + i}")

                # Select jurisdiction as "US" for Identification
                self.wait_and_click((By.ID, f"bo[{i}].identification.jurisdiction.value"))
                if not self.safe_click_element((By.CSS_SELECTOR, '[data-testid="combo-box-option-US"]')):
                    print("Failed to select US in jurisdiction, using JavaScript...")
                    self.safe_click_element_js((By.XPATH, "//li[@data-testid='combo-box-option-US']"))

                # Select state for Identification
                self.wait_and_click((By.ID, f"bo[{i}].identification.state.value"))
                if not self.safe_click_element((By.CSS_SELECTOR, '[data-testid="combo-box-option-CA"]')):
                    print("Failed to select CA in state dropdown for identification, using JavaScript...")
                    self.safe_click_element_js((By.XPATH, "//li[@data-testid='combo-box-option-CA']"))

                # Fill tribal and local descriptions
                self.wait_and_send_keys((By.ID, f"bo[{i}].identification.localTribal.value"), f"Local Description {i}")
                self.wait_and_send_keys((By.ID, f"bo[{i}].identification.otherTribe.value"), f"Tribal Description {i}")

                # Handle file upload (might need tweaking depending on how file uploads are handled on this form)
                self.wait_and_send_keys((By.ID, f"bo[{i}].identification.image.value"), f"path/to/identification_image_{i}.png")

                # Add next owner if there are more
                if i < num_owners - 1:
                    self.wait_and_click((By.ID, "addBeneficialOwner"))
                    self.wait.until(EC.presence_of_element_located((By.ID, f"bo[{i+1}].fincenId")))

            # Click Next button after filling all beneficial owners
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
            print(f"Error in fill_beneficial_owners: {str(e)}")
            self.take_screenshot("fill_beneficial_owners_error")
            raise
        finally:
            print("Completed filling beneficial owners info")

    def fill_submission_info(self):
        print("Filling submission info...")
        try:
            self.wait.until(EC.presence_of_element_located((By.ID, "email")))
            self.safe_send_keys((By.ID, "email"), "your_email@example.com")
            self.safe_send_keys((By.ID, "confirmEmail"), "your_email@example.com")
            self.safe_send_keys((By.ID, "firstName"), "YourFirstName")
            self.safe_send_keys((By.ID, "lastName"), "YourLastName")
            self.safe_click_element((By.ID, "certifyCB"))
            print("Please solve the hCaptcha manually if it appears.")
            input("Press Enter after solving the CAPTCHA...")
            self.safe_click_element((By.ID, "FormSubmit"))
            self.wait.until(EC.presence_of_element_located((By.ID, "submissionConfirmation")))
            print("Form submitted successfully!")
        except Exception as e:
            print(f"Error in fill_submission_info: {str(e)}")
            self.take_screenshot("fill_submission_info_error")
            raise

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
            self.fill_filing_information("Initial Report", "2024-09-01")
            if not self.is_browser_responsive():
                print("Browser became unresponsive after filling Filing Information")
                self.take_screenshot("unresponsive_browser")
                return
            self.fill_reporting_company_info()
            self.fill_company_applicants(1)  # Adjust the number of applicants as needed
            self.fill_beneficial_owners(1)  # Adjust the number of owners as needed
            self.fill_submission_info()
        except Exception as e:
            print(f"An error occurred: {str(e)}")
            print("Traceback:")
            traceback.print_exc()
            self.take_screenshot("error_screenshot")
        finally:
            print("Closing the driver...")
            if self.driver:
                try:
                    self.driver.quit()
                except Exception as e:
                    print(f"Error closing the driver: {str(e)}")

if __name__ == "__main__":
    form_filler = FormFiller()
    form_filler.run()
