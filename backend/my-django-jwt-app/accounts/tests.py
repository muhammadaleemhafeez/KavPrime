from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model
import jwt
from django.conf import settings

User = get_user_model()

class UserRegistrationTests(APITestCase):
    def test_user_registration(self):
        url = reverse('register')  # Adjust the URL name as per your urls.py
        data = {
            'username': 'testuser',
            'password': 'testpassword123',
            'email': 'testuser@example.com'
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(User.objects.get().username, 'testuser')

class UserLoginTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpassword123',
            email='testuser@example.com'
        )

    def test_user_login(self):
        url = reverse('login')  # Adjust the URL name as per your urls.py
        data = {
            'username': 'testuser',
            'password': 'testpassword123'
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('token', response.data)

    def test_token_validation(self):
        url = reverse('login')  # Adjust the URL name as per your urls.py
        data = {
            'username': 'testuser',
            'password': 'testpassword123'
        }
        response = self.client.post(url, data, format='json')
        token = response.data['token']
        
        # Decode the token to validate
        decoded = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
        self.assertEqual(decoded['username'], 'testuser')  # Ensure the token contains the correct username
        self.assertIn('exp', decoded)  # Ensure the token has an expiration time
        self.assertLess(decoded['exp'], decoded['iat'] + 604800)  # Check if the token expires in 7 days (604800 seconds)