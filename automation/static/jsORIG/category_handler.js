// automation/static/js/category_handler.js
document.addEventListener('DOMContentLoaded', function() {
    const levelSelect = document.getElementById('id_level');
    const categorySelect = document.getElementById('id_main_category');
    const subcategorySelect = document.getElementById('id_subcategory');

    levelSelect.addEventListener('change', function() {
        const levelId = this.value;
        fetch(`/get-categories/?level_id=${levelId}`)
            .then(response => response.json())
            .then(data => {
                categorySelect.innerHTML = '<option value="">Select Category</option>';
                data.forEach(category => {
                    categorySelect.innerHTML += `<option value="${category.id}">${category.title}</option>`;
                });
            });
    });

    categorySelect.addEventListener('change', function() {
        const categoryId = this.value;
        fetch(`/get-subcategories/?category_id=${categoryId}`)
            .then(response => response.json())
            .then(data => {
                subcategorySelect.innerHTML = '<option value="">Select Subcategory</option>';
                data.forEach(subcategory => {
                    subcategorySelect.innerHTML += `<option value="${subcategory.id}">${subcategory.title}</option>`;
                });
            });
    });
});