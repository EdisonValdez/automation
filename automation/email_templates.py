welcome_email_template = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Welcome to Local Secrets Business Content Dashboard</title>
    <style>
        /* CSS styles go here */
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Welcome to Local Secrets Business Content Dashboard</h1>
        </div>
        <div class="content">
            <p>Dear {user_name},</p>
            <p>We are excited to welcome you to the Local Secrets Business Content Dashboard. This platform will be your gateway to exclusive content, tools, and resources to help you become a successful ambassador for our brand.</p>
            <p>To get started, please use the following information to access your account:</p>
            <ul>
                <li><strong>URL:</strong> <a href="{dashboard_url}">{dashboard_url}</a></li>
                <li><strong>Username:</strong> {username}</li>
                <li><strong>Password:</strong> {password}</li>
            </ul>
            <p>We encourage you to explore the dashboard and take advantage of all the features it has to offer. If you have any questions or need assistance, please don't hesitate to reach out to our support team.</p>
            <p>We look forward to working with you and helping you succeed as a Local Secrets Ambassador.</p>
            <p>Best regards,<br>
            The Local Secrets Team</p>
        </div>
        <div class="footer">
            <p>&copy; 2023 Local Secrets. All rights reserved.</p>
        </div>
    </div>
</body>
</html>
"""
