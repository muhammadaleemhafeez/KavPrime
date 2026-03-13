# My Django JWT App

This project is a Django application that implements JSON Web Token (JWT) authentication for user registration and login. The application allows users to securely authenticate and access protected resources using JWT tokens.

## Features

- User registration
- User login
- JWT token generation and validation
- Token expiration set to 7 days

## Requirements

To run this project, you need to have Python and Django installed. Additionally, you will need the following packages for JWT implementation:

- djangorestframework
- djangorestframework-simplejwt

You can install the required packages using the following command:

```
pip install -r requirements.txt
```

## Setup Instructions

1. Clone the repository:

   ```
   git clone <repository-url>
   ```

2. Navigate to the project directory:

   ```
   cd my-django-jwt-app
   ```

3. Install the required packages:

   ```
   pip install -r requirements.txt
   ```

4. Apply migrations:

   ```
   python manage.py migrate
   ```

5. Create a superuser (optional, for accessing the admin panel):

   ```
   python manage.py createsuperuser
   ```

6. Run the development server:

   ```
   python manage.py runserver
   ```

## Usage

- **Register a new user**: Send a POST request to `/api/register/` with the user's details (username, password, etc.).
- **Login**: Send a POST request to `/api/login/` with the user's credentials to receive a JWT token.
- **Access protected resources**: Include the JWT token in the Authorization header as a Bearer token when making requests to protected endpoints.

## Token Expiration

JWT tokens are set to expire after 7 days. After expiration, users will need to log in again to receive a new token.

## License

This project is licensed under the MIT License.