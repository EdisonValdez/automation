//static/ls_backend.js
$(document).ready(function() {

    // On page load, fetch levels from the local automation endpoint
    function loadLocalLevels() {
    $.ajax({
        url: '/api/levels/',  // This now calls the local automation view (above)
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
        success: function(response) {
        // 'response' is an array of {id, title, ls_id}
        $('#id_level').empty().append('<option value="">Select a level</option>');
        if (Array.isArray(response) && response.length > 0) {
            response.forEach(function(lvl) {
            // store 'ls_id' in the <option> value so we can pass it to get_categories
            $('#id_level').append(
                $('<option></option>')
                .attr('value', lvl.ls_id)  // IMPORTANT: we use the "ls_id" as the actual value
                .text(lvl.title)
            );
            });
        } else {
            $('#id_level').append('<option value="">No levels available</option>');
        }
        },
        error: function(xhr, status, error) {
        console.error('Error loading local levels:', error);
        $('#id_level').append('<option value="">Error loading levels</option>');
        }
    });
    }

    // Call this once on DOM ready
    loadLocalLevels();

    // 1) Load countries on page load
    function loadCountries() {
        // Optional: show a spinner
        showLoading('#id_country');
        $.ajax({
            url: '/api/countries/',
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
            success: function(response) {
                hideLoading('#id_country');
                // response = { results: [ {id: 47, name: 'United Arab Emirates'}, ... ] }
                
                // Clear and add default option
                $('#id_country').empty().append('<option value="">Select a country</option>');

                if (response.results && Array.isArray(response.results)) {
                    const countries = response.results;
                    countries.forEach(function(country) {
                        $('#id_country').append(
                            $('<option></option>')
                                .attr('value', country.id)
                                .text(country.name)
                        );
                    });
                } else {
                    $('#id_country').append('<option value="">No countries found</option>');
                }
            },
            error: function(xhr, status, error) {
                handleAjaxError('#id_country', error); 
            }
        });
    }

    // 2) Call loadCountries() once when the DOM is ready
    loadCountries();

        // 3) When the user selects a country => load its cities
        $('#id_country').change(function() {
            var countryId = $(this).val();
            $('#id_destination').empty().append('<option value="">Select a destination</option>');
            if (countryId) {
                showLoading('#id_destination');
                $.ajax({
                    url: '/api/cities/',
                    data: { 'country_id': countryId },
                    headers: { 'X-Requested-With': 'XMLHttpRequest' },
                    success: function(response) {
                        hideLoading('#id_destination');

                        // response = { results: [ {id: X, name: 'Some City'}, ... ] }
                        const cities = response.results;
                        if (Array.isArray(cities) && cities.length) {
                            cities.forEach(function(city) {
                                $('#id_destination').append(
                                    $('<option></option>')
                                        .attr('value', city.id)
                                        .text(city.name)
                                );
                            });
                        } else {
                            $('#id_destination').append('<option value="">No destinations found</option>');
                        }
                    },
                    error: function(xhr, status, error) {
                        handleAjaxError('#id_destination', error);
                    }
                });
            }
        });

        // Then, when user selects a level, we pass the "ls_id" to get categories
        $('#id_level').change(function() {
        var levelLsId = $(this).val();  // This is our 'ls_id' from the local DB
        $('#id_main_category').empty().append('<option value="">Select a category</option>');
        $('#id_subcategory').empty().append('<option value="">Select a subcategory (optional)</option>');

        if (levelLsId) {
            $.ajax({
            url: '/api/categories/',       // The existing view
            data: { 'level_id': levelLsId },
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
            success: function(response) {
                if (Array.isArray(response) && response.length) {
                response.forEach(function(category) {
                    $('#id_main_category').append(
                    $('<option></option>')
                        .attr('value', category.id)
                        .text(category.title)
                    );
                });
                } else {
                $('#id_main_category').append('<option value="">No categories available</option>');
                }
            },
            error: function(xhr, status, error) {
                console.error('Error fetching categories:', error);
                $('#id_main_category').append('<option value="">Error loading categories</option>');
            }
            });
        }
        });
            
        // Handle Main Category and Subcategory changes
        $('#id_main_category').change(function() {
            var categoryId = $(this).val();
            $('#id_subcategory').empty().append('<option value="">Select a subcategory (optional)</option>');
            if (categoryId) {
                $.ajax({
                    url: '/api/subcategories/',
                    data: { 'category_id': categoryId }, // Ensure you are sending the correct parameter
                    headers: { 'X-Requested-With': 'XMLHttpRequest' },
                    success: function(response) {
                        if (Array.isArray(response) && response.length) {
                            response.forEach(function(subcategory) {
                                $('#id_subcategory').append(
                                    $('<option></option>')
                                    .attr('value', subcategory.id)
                                    .text(subcategory.title)
                                );
                            });
                        } else {
                            $('#id_subcategory').append('<option value="">No subcategories available</option>');
                        }
                    },
                    error: function(xhr, status, error) {
                        console.error('Error fetching subcategories:', error);
                        $('#id_subcategory').append('<option value="">Error loading subcategories</option>');
                    }
                });
            }
        });

        // Add error handling utility
    function handleAjaxError(elementId, error) {
        console.error('Ajax error:', error);
        $(elementId).empty().append('<option value="">Error loading data</option>');
        hideLoading(elementId);
        
        // Show error message to user
        const errorDiv = $('<div>')
            .addClass('alert alert-danger mt-2')
            .text('Error loading data. Please try again.');
        $(elementId).parent().append(errorDiv);
        setTimeout(() => errorDiv.fadeOut('slow', function() { $(this).remove(); }), 5000);
    }
});
