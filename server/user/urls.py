from django.urls import path
from user.views import loginView, registerView, token_refresh_view, logoutView, user, getSubscriptions

app_name = "user"

urlpatterns = [
    path('login', loginView),
    path('register', registerView),
    path('refresh-token', token_refresh_view),
    path('logout', logoutView),
    path('user', user),
    path('subscriptions', getSubscriptions)
]
